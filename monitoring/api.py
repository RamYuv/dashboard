"""
Monitoring API endpoints and payload builders.
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify

from webapp.models import EnvironmentBooking, EnvironmentHostMapping, ServerRole
from webapp.helpers import get_booking_lifecycle_status

monitoring_bp = Blueprint("monitoring", __name__)


def _included_server_roles():
    raw_value = current_app.config.get("MONITOR_INCLUDED_SERVER_ROLES", "")
    included = []
    for item in str(raw_value).split(","):
        role_key = (item or "").strip()
        if role_key and role_key not in included:
            included.append(role_key)
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


def _infer_env_type(env_id):
    if not env_id:
        return "Unknown"
    if "-" in env_id:
        return env_id.split("-", 1)[0]
    return env_id.rstrip("0123456789") or env_id


def _build_server_role_map(env_ids):
    env_server_roles = {}
    included_server_roles = set(_included_server_roles())

    for env_id in env_ids:
        role_ids = [
            row[0]
            for row in EnvironmentHostMapping.query.with_entities(EnvironmentHostMapping.server_role_id)
            .filter(
                EnvironmentHostMapping.env_id == env_id,
                EnvironmentHostMapping.is_shared.is_(False),
            )
            .distinct()
            .all()
        ]
        role_keys = []
        for role_id in role_ids:
            server_role = ServerRole.query.get(role_id)
            if (
                server_role is not None and
                server_role.role_key in included_server_roles
            ):
                role_keys.append(server_role.role_key)
        env_server_roles[env_id] = role_keys

    return env_server_roles


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
    env_server_roles = _build_server_role_map(env_ids)

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

        status_item = {
            "env_id": env_id,
            "env_type": env_type,
            "status": normalized_status,
            "host": status_data.get("host", ""),
            "owner_team": status_data.get("owner_team", ""),
            "message": status_data.get("message", ""),
            "component_summary": {
                "running": int(component_summary.get("running", 0) or 0),
                "notrunning": int(component_summary.get("notrunning", 0) or 0),
                "unknown": int(component_summary.get("unknown", 0) or 0),
            },
            "server_roles": env_server_roles.get(env_id, []),
        }
        statuses.append(status_item)
        summary["total"] += 1

        if normalized_status in summary:
            summary[normalized_status] += 1

    return {
        "statuses": statuses,
        "summary": summary,
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
