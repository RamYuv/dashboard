"""
Monitoring API endpoints and payload builders.
"""
from datetime import datetime
import re

from flask import Blueprint, current_app, jsonify

from webapp.models import CurrentDeploymentState, EnvironmentBooking, EnvironmentHostMapping, ServerType
from webapp.helpers import get_booking_lifecycle_status

monitoring_bp = Blueprint("monitoring", __name__)


def _included_server_types():
    raw_value = current_app.config.get(
        "MONITOR_INCLUDED_SERVER_TYPES",
        current_app.config.get("MONITOR_INCLUDED_SERVER_ROLES", ""),
    )
    included = []
    for item in str(raw_value).split(","):
        server_type_key = (item or "").strip()
        if server_type_key and server_type_key not in included:
            included.append(server_type_key)
    return included


def _get_active_booking_env_ids():
    now = datetime.utcnow()
    active_env_ids = []
    bookings = EnvironmentBooking.query.all()
    for booking in bookings:
        if get_booking_lifecycle_status(booking, now=now) == "active":
            active_env_ids.append(booking.env_id)
    return sorted(set(active_env_ids))


def _normalize_status(env_color):
    color = (env_color or "").strip().lower()
    color_map = {
        "green": "healthy",
        "yellow": "warning",
        "red": "critical",
        "blue": "maintenance",
        "black": "unknown",
    }
    return color_map.get(color, "unknown")


def _status_label(normalized_status):
    label_map = {
        "healthy": "Healthy",
        "warning": "Idle",
        "critical": "Critical",
        "maintenance": "Unavailable",
        "unknown": "Unavailable",
    }
    return label_map.get(normalized_status, "Unavailable")


def _version_sort_key(version):
    value = (version or "").strip()
    if not value:
        return ((), -1, "")

    numeric_parts = tuple(
        int(part)
        for part in re.findall(r"\d+", value)
    )
    patch_match = re.search(r"_patch(\d+)", value, re.IGNORECASE)
    patch_number = int(patch_match.group(1)) if patch_match else 0
    return (numeric_parts, patch_number, value.lower())


def _preferred_tcs_version(versions):
    candidates = [value.strip() for value in (versions or []) if (value or "").strip()]
    if not candidates:
        return ""
    return max(candidates, key=_version_sort_key)


def _extract_version_date(version):
    value = (version or "").strip()
    if not value:
        return ""

    match = re.search(r"_(\d{8})$", value)
    if not match:
        return ""
    return match.group(1)


def _display_tcs_version(versions):
    candidates = [value.strip() for value in (versions or []) if (value or "").strip()]
    if not candidates:
        return ""
    if len(set(candidates)) == 1:
        return candidates[0]

    dated_candidates = [
        version_date
        for version_date in (_extract_version_date(value) for value in candidates)
        if version_date
    ]
    if dated_candidates:
        return max(dated_candidates)

    return _preferred_tcs_version(candidates)


def _infer_env_type(env_id):
    if not env_id:
        return "Unknown"
    if "-" in env_id:
        return env_id.split("-", 1)[0]
    return env_id.rstrip("0123456789") or env_id


def _build_server_type_map(env_ids):
    env_server_types = {}
    included_server_types = set(_included_server_types())

    for env_id in env_ids:
        server_type_ids = [
            row[0]
            for row in EnvironmentHostMapping.query.with_entities(EnvironmentHostMapping.server_type_id)
            .filter(
                EnvironmentHostMapping.env_id == env_id,
            )
            .distinct()
            .all()
        ]
        server_type_keys = []
        for server_type_id in server_type_ids:
            server_type = ServerType.query.get(server_type_id)
            if (
                server_type is not None and
                server_type.server_type_key in included_server_types
            ):
                server_type_keys.append(server_type.server_type_key)
        env_server_types[env_id] = server_type_keys

    return env_server_types


def _build_tcs_runtime_map(env_ids):
    runtime_map = {
        env_id: {
            "versions": [],
            "service_types": [],
            "testing_modes": [],
        }
        for env_id in env_ids
    }
    if not env_ids:
        return runtime_map

    rows = (
        CurrentDeploymentState.query
        .filter(
            CurrentDeploymentState.env_scope_type == "ENV",
            CurrentDeploymentState.env_id.in_(env_ids),
            CurrentDeploymentState.target_key == "TCS_APP",
        )
        .all()
    )

    for row in rows:
        bucket = runtime_map.setdefault(
            row.env_id,
            {"versions": [], "service_types": [], "testing_modes": []},
        )
        version = (row.current_version or "").strip()
        if version and version not in bucket["versions"]:
            bucket["versions"].append(version)

        testing_mode = (row.testing_mode or "").strip()
        if testing_mode and testing_mode not in bucket["testing_modes"]:
            bucket["testing_modes"].append(testing_mode)

        for service_type in row.get_service_types():
            value = (service_type or "").strip()
            if value and value not in bucket["service_types"]:
                bucket["service_types"].append(value)

    return runtime_map


def _collect_not_running_components(vm_details):
    names = []
    for vm_status in (vm_details or {}).values():
        component_data = vm_status.get("component_data", {})
        for component_name, component_info in component_data.items():
            run_status = (component_info.get("run_status") or "").strip().lower()
            if run_status == "notrunning" and component_name not in names:
                names.append(component_name)
    return names


def _build_environment_health_payload(env_statuses, last_update, active_booking_envs):
    env_statuses = env_statuses or {}
    active_booking_envs = active_booking_envs or []
    env_ids = sorted(
        {
            env_id
            for env_id in list(env_statuses.keys()) + list(active_booking_envs)
            if isinstance(env_id, str) and env_id.strip()
        }
    )
    env_server_types = _build_server_type_map(env_ids)
    tcs_runtime = _build_tcs_runtime_map(env_ids)
    statuses = []
    summary = {
        "total": 0,
        "healthy": 0,
        "warning": 0,
        "critical": 0,
        "maintenance": 0,
        "last_updated": last_update or "Never",
    }

    for env_id in env_ids:
        status_data = env_statuses.get(env_id, {})
        normalized_status = _normalize_status(status_data.get("env_color"))
        component_summary = status_data.get("component_summary", {})
        env_type = status_data.get("env_type") or _infer_env_type(env_id)
        vm_details = status_data.get("vm_details", {})
        runtime_details = tcs_runtime.get(env_id, {})
        not_running_components = _collect_not_running_components(vm_details)

        status_item = {
            "env_id": env_id,
            "env_type": env_type,
            "status": normalized_status,
            "status_label": _status_label(normalized_status),
            "host": status_data.get("host", ""),
            "owner_team": status_data.get("owner_team", ""),
            "message": status_data.get("message", ""),
            "component_summary": {
                "running": int(component_summary.get("running", 0) or 0),
                "notrunning": int(component_summary.get("notrunning", 0) or 0),
                "unknown": int(component_summary.get("unknown", 0) or 0),
            },
            "server_types": env_server_types.get(env_id, []),
            "tcs_runtime": {
                "versions": runtime_details.get("versions", []),
                "display_version": _display_tcs_version(runtime_details.get("versions", [])),
                "has_mixed_versions": len(runtime_details.get("versions", [])) > 1,
                "service_types": runtime_details.get("service_types", []),
                "testing_modes": runtime_details.get("testing_modes", []),
            },
            "not_running_components": not_running_components,
        }
        statuses.append(status_item)
        summary["total"] += 1

        if normalized_status in summary:
            summary[normalized_status] += 1
        elif normalized_status == "unknown":
            # Surface the grey/no-light TCS status in the final summary card.
            summary["maintenance"] += 1

    return {
        "statuses": statuses,
        "summary": summary,
        "summary_labels": {
            "healthy": "Healthy",
            "warning": "Idle",
            "critical": "Critical",
            "maintenance": "Unavailable",
        },
        "active_envs": [env_id for env_id in active_booking_envs if isinstance(env_id, str) and env_id.strip()],
    }


@monitoring_bp.route("/api/environment-health")
def api_environment_health():
    current_app.monitor_state.refresh_from_persisted()
    env_statuses, last_update = current_app.monitor_state.snapshot()
    if not env_statuses and hasattr(current_app, "container"):
        env_statuses = current_app.container.env_worker.refresh()
        env_statuses, last_update = current_app.monitor_state.snapshot()

    active_booking_envs = _get_active_booking_env_ids()
    payload = _build_environment_health_payload(env_statuses, last_update, active_booking_envs)
    return jsonify(payload)
