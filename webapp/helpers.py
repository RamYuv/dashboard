"""
Utility and helper functions for common operations.
"""

from datetime import datetime, timedelta, timezone
from flask import current_app, has_app_context, jsonify

from .models import ComponentBuild, DeploymentRequest, Environment, EnvironmentBooking, Role, Team, format_datetime
from .domain.deployment_targets import get_target_definition
from .constants import (
    BOOKING_LIFECYCLE_STATUS,
    BOOKING_STATUS,
    BOOKING_STATUS_ALIASES,
    COMPONENT_VERSIONS,
    PACKAGE_VERSIONS,
)

DEFAULT_ROLE_NAMES = ["user", "admin"]


def get_user_team_names(user):
    """Return normalized team names for a user."""
    if user is None:
        return set()
    return {
        (team_name or "").strip().lower()
        for team_name in getattr(user, "team_names", []) or []
        if (team_name or "").strip()
    }


def can_user_access_environment(user, environment):
    """Return whether the user may access/book the given environment."""
    if user is None or environment is None:
        return False
    if getattr(user, "is_admin", False):
        return True

    team = (getattr(environment, "team", "") or "").strip().lower()
    if not team:
        return False
    return team in get_user_team_names(user)

def json_error(message, status_code):
    """Create a JSON error response."""
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


def parse_iso_datetime(value):
    """Parse ISO datetime string with support for multiple formats."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value

    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    candidates = [cleaned]
    if len(cleaned) > 6 and cleaned[-3] == ":" and cleaned[-6] in ["+", "-"]:
        candidates.append(cleaned[:-3] + cleaned[-2:])

    for candidate in candidates:
        for date_format in formats:
            try:
                return datetime.strptime(candidate, date_format)
            except ValueError:
                pass

    raise ValueError("Invalid ISO datetime")


def to_utc_naive(value):
    """Convert datetime to UTC and remove timezone info."""
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def get_deployment_reservation_window_minutes():
    """Return the configured reserved window for env-scoped deployment requests."""
    if has_app_context():
        try:
            return max(
                1,
                int(current_app.config.get("DEPLOYMENT_RESERVATION_WINDOW_MINUTES", 60))
            )
        except (TypeError, ValueError):
            return 60
    return 60


def build_deployment_request_window(planned_start_time, duration_minutes=None):
    """Return the reserved start/end window for a deployment request."""
    if planned_start_time is None:
        return None, None
    if duration_minutes is None:
        duration_minutes = get_deployment_reservation_window_minutes()
    return planned_start_time, planned_start_time + timedelta(minutes=duration_minutes)


def normalize_booking_stored_status(status):
    """Map legacy persisted booking states to the canonical stored/lifecycle values."""
    aliases = {
        BOOKING_STATUS_ALIASES["INACTIVE"]: BOOKING_STATUS["SCHEDULED"],
        BOOKING_STATUS_ALIASES["EXPIRED"]: BOOKING_LIFECYCLE_STATUS["COMPLETED"],
    }
    normalized_status = (status or "").strip().lower()
    return aliases.get(normalized_status, normalized_status)


def normalize_booking_status(status):
    """Backward-compatible wrapper for normalized stored booking status."""
    return normalize_booking_stored_status(status)


def get_booking_stored_status(booking):
    """Return the canonical stored status for a booking model or raw status value."""
    if isinstance(booking, EnvironmentBooking):
        return booking.normalized_status
    return normalize_booking_stored_status(booking)


def get_booking_lifecycle_status(booking, now=None):
    """Return the time-based lifecycle status for a booking."""
    if isinstance(booking, EnvironmentBooking):
        return booking.lifecycle_status(now=now)

    if now is None:
        now = datetime.utcnow()

    stored_status = get_booking_stored_status(getattr(booking, "status", None))
    if stored_status == BOOKING_STATUS["CANCELLED"]:
        return BOOKING_STATUS["CANCELLED"]
    if booking.start_time is not None and now < booking.start_time:
        return BOOKING_LIFECYCLE_STATUS["SCHEDULED"]
    if (
        booking.start_time is not None and
        booking.end_time is not None and
        booking.start_time <= now <= booking.end_time
    ):
        return BOOKING_LIFECYCLE_STATUS["ACTIVE"]
    return BOOKING_LIFECYCLE_STATUS["COMPLETED"]


def get_booking_status_label(status):
    """Return the UI label for a booking lifecycle status."""
    labels = {
        "scheduled": "Scheduled",
        "active": "Active",
        "completed": "Completed",
        "cancelled": "Cancelled",
    }
    return labels.get(status, status.title())


def get_deployment_request_status_label(status):
    """Return the UI label for a deployment workflow status."""
    labels = {
        "OPEN": "Open",
        "READY_FOR_DEPLOYMENT": "Ready For Deployment",
        "AUTO_DEPLOYMENT_RUNNING": "Auto Deployment Running",
        "MANUAL_DEPLOYMENT_IN_PROGRESS": "Manual Deployment In Progress",
        "COMPLETED": "Completed",
        "FAILED": "Failed",
        "CANCELLED": "Cancelled",
        "REJECTED": "Rejected",
    }
    return labels.get(status, (status or "").replace("_", " ").title())


def get_valid_roles():
    """Return active roles from the database, with a startup-safe fallback."""
    if not has_app_context():
        return list(DEFAULT_ROLE_NAMES)

    try:
        roles = [
            role.role_name
            for role in Role.query.filter_by(is_active=True).order_by(Role.role_name).all()
            if (role.role_name or "").strip()
        ]
    except Exception:
        roles = []

    return roles or list(DEFAULT_ROLE_NAMES)


def get_valid_team_names():
    """Return active team names from the database, with a startup-safe fallback."""
    if not has_app_context():
        return []

    try:
        teams = [
            (team.team_name or "").strip().lower()
            for team in Team.query.order_by(Team.team_name).all()
            if (team.team_name or "").strip()
        ]
    except Exception:
        teams = []

    return teams


def normalize_role(role):
    """Normalize role to valid value or default to 'user'."""
    role = (role or "user").strip().lower()
    return role if role in get_valid_roles() else "user"


def normalize_team(team):
    """Normalize team to valid value or default to 'support'."""
    team = (team or "support").strip().lower()
    valid_teams = get_valid_team_names()
    return team if team in valid_teams else "support"


def serialize_booking(booking):
    """Serialize booking object to dictionary."""
    data = booking.to_dict()
    stored_status = get_booking_stored_status(booking)
    data["stored_status"] = stored_status
    data["status"] = stored_status
    lifecycle_status = get_booking_lifecycle_status(booking)
    data["lifecycle_status"] = lifecycle_status
    data["status_label"] = get_booking_status_label(lifecycle_status)
    return data


def serialize_deployment_request_for_workspace(deployment_request):
    """Serialize a standalone deployment request into the booking/workspace shape."""
    data = deployment_request.to_dict()
    planned_start = deployment_request.planned_start_time
    _, synthetic_end = build_deployment_request_window(planned_start)
    workflow_status = (deployment_request.status or "OPEN").strip().upper()
    lifecycle_status = workflow_status.lower()

    return {
        "booking_id": deployment_request.deployment_request_id,
        "deployment_request_id": deployment_request.deployment_request_id,
        "env_id": deployment_request.env_id,
        "requested_by": deployment_request.requested_by,
        "requested_by_name": data.get("requested_by_name"),
        "requested_by_team": data.get("requested_by_team"),
        "requested_by_display": data.get("requested_by_display"),
        "start_time": format_datetime(planned_start),
        "end_time": format_datetime(synthetic_end),
        "booking_type": "DEPLOYMENT",
        "status": workflow_status,
        "lifecycle_status": lifecycle_status,
        "status_label": get_deployment_request_status_label(workflow_status),
        "description": deployment_request.description or deployment_request.remarks,
        "user_timezone": None,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "is_standalone_deployment_request": True,
        "deployment_request": data,
    }


def get_list_bookings(user=None):
    """Retrieve bookings plus standalone deployment requests for workspace views."""
    bookings = EnvironmentBooking.query.order_by(EnvironmentBooking.start_time).all()
    if user is not None:
        bookings = [
            booking
            for booking in bookings
            if can_user_access_environment(user, booking.environment)
        ]

    deployment_requests = DeploymentRequest.query.order_by(
        DeploymentRequest.planned_start_time
    ).all()
    if user is not None:
        deployment_requests = [
            deployment_request
            for deployment_request in deployment_requests
            if (
                deployment_request.env_id and
                can_user_access_environment(user, deployment_request.environment)
            ) or deployment_request.requested_by == getattr(user, "user_id", None)
        ]
    items = [serialize_booking(booking) for booking in bookings]
    items.extend(
        serialize_deployment_request_for_workspace(deployment_request)
        for deployment_request in deployment_requests
    )
    return sorted(items, key=lambda item: item.get("start_time") or "")


def filter_bookings_for_history(items, env_type="", booking_type="", status="", search=""):
    """Apply Request History filter semantics to booking/deployment items."""
    normalized_env_type = (env_type or "").strip()
    normalized_booking_type = (booking_type or "").strip().upper()
    normalized_status = (status or "").strip().lower()
    normalized_search = (search or "").strip().lower()

    filtered_items = []
    for item in items or []:
        deployment = item.get("deployment_request") or {}
        item_env_type = deployment.get("requested_env_type") or item.get("env_type") or ""
        resolved_hosts = deployment.get("resolved_hosts_summary") or ""
        search_haystack = " ".join([
            str(item.get("booking_id") or ""),
            str(item.get("env_id") or ""),
            str(deployment.get("environment_display") or item.get("env_id") or ""),
            str(item_env_type or ""),
            str(resolved_hosts or ""),
            str(item.get("requested_by") or ""),
            str(item.get("requested_by_name") or ""),
            str(item.get("requested_by_team") or ""),
            str(item.get("requested_by_display") or ""),
            str(item.get("description") or ""),
            str(deployment.get("selected_servers_summary") or ""),
        ]).lower()

        if normalized_env_type and item_env_type != normalized_env_type:
            continue
        if normalized_booking_type and (item.get("booking_type") or "").strip().upper() != normalized_booking_type:
            continue
        if normalized_status and (item.get("lifecycle_status") or "").strip().lower() != normalized_status:
            continue
        if normalized_search and normalized_search not in search_haystack:
            continue

        filtered_items.append(item)

    return filtered_items


def _serialize_booking_operation_item(booking):
    booking_data = serialize_booking(booking)
    return {
        "request_type": "BOOKING",
        "request_type_label": "Booking",
        "request_id": booking_data.get("booking_id"),
        "booking_id": booking_data.get("booking_id"),
        "deployment_request_id": None,
        "env_id": booking_data.get("env_id"),
        "env_type": booking.environment.env_type if booking.environment else None,
        "environment_display": booking_data.get("env_id"),
        "window_start": booking_data.get("start_time"),
        "window_end": booking_data.get("end_time"),
        "requested_by": booking_data.get("requested_by"),
        "requested_by_name": booking_data.get("requested_by_name"),
        "requested_by_team": booking_data.get("requested_by_team"),
        "requested_by_display": booking_data.get("requested_by_display"),
        "status": booking_data.get("lifecycle_status"),
        "status_label": booking_data.get("status_label"),
        "description": booking_data.get("description"),
        "target_key": "",
        "requested_version": "",
        "tcs_deployment_mode": "",
        "tcs_service_ids": [],
        "tcs_service_names": [],
        "package_keys": [],
        "resolved_hosts_summary": "",
        "available_actions": [],
        "created_at": booking_data.get("created_at"),
        "updated_at": booking_data.get("updated_at"),
        "sort_time": booking_data.get("start_time") or "",
    }


def _serialize_deployment_operation_item(deployment_request_data):
    return {
        "request_type": "DEPLOYMENT",
        "request_type_label": "Deployment",
        "request_id": deployment_request_data.get("deployment_request_id"),
        "booking_id": None,
        "deployment_request_id": deployment_request_data.get("deployment_request_id"),
        "env_id": deployment_request_data.get("env_id"),
        "env_type": deployment_request_data.get("requested_env_type"),
        "environment_display": deployment_request_data.get("environment_display"),
        "window_start": deployment_request_data.get("planned_start_time"),
        "window_end": None,
        "requested_by": deployment_request_data.get("requested_by"),
        "requested_by_name": deployment_request_data.get("requested_by_name"),
        "requested_by_team": deployment_request_data.get("requested_by_team"),
        "requested_by_display": deployment_request_data.get("requested_by_display"),
        "status": deployment_request_data.get("status"),
        "status_label": deployment_request_data.get("status_label"),
        "description": deployment_request_data.get("description") or deployment_request_data.get("remarks"),
        "target_key": deployment_request_data.get("target_key"),
        "requested_version": deployment_request_data.get("requested_version"),
        "tcs_deployment_mode_id": deployment_request_data.get("tcs_deployment_mode_id"),
        "tcs_deployment_mode": deployment_request_data.get("tcs_deployment_mode") or "",
        "tcs_service_ids": deployment_request_data.get("tcs_service_ids") or [],
        "tcs_service_names": deployment_request_data.get("tcs_service_names") or [],
        "package_keys": deployment_request_data.get("package_keys") or [],
        "selected_server_mapping_ids": deployment_request_data.get("selected_server_mapping_ids") or [],
        "selected_servers": deployment_request_data.get("selected_servers") or [],
        "selected_servers_summary": deployment_request_data.get("selected_servers_summary") or "",
        "resolved_hosts_summary": deployment_request_data.get("resolved_hosts_summary") or "",
        "available_actions": deployment_request_data.get("available_actions") or [],
        "created_at": deployment_request_data.get("created_at"),
        "updated_at": deployment_request_data.get("updated_at"),
        "sort_time": deployment_request_data.get("planned_start_time") or "",
    }


def list_environment_operations(user):
    """Return a combined env-team operational view of bookings and deployments."""
    bookings = EnvironmentBooking.query.order_by(
        EnvironmentBooking.start_time.desc(),
        EnvironmentBooking.created_at.desc(),
    ).all()
    bookings = [
        booking
        for booking in bookings
        if can_user_access_environment(user, booking.environment)
    ]

    operations = [
        _serialize_booking_operation_item(booking)
        for booking in bookings
    ]

    from .services.deployment_request_service import DeploymentRequestService

    deployment_requests, error, status_code = DeploymentRequestService.list_requests(
        user,
        scope="env",
    )
    if error:
        return [], error, status_code

    operations.extend(
        _serialize_deployment_operation_item(item)
        for item in deployment_requests
    )
    operations.sort(key=lambda item: item.get("sort_time") or "", reverse=True)
    return operations, None, 200


def get_environments(user=None):
    """Retrieve environments, optionally filtered to those accessible by the user."""
    environments = Environment.query.order_by(
        Environment.env_type, Environment.env_id
    ).all()
    if user is not None:
        environments = [
            environment
            for environment in environments
            if can_user_access_environment(user, environment)
        ]
    return [
        {
            "env_id": environment.env_id,
            "env_type": environment.env_type,
            "team": environment.team,
            "description": environment.description,
        }
        for environment in environments
    ]


def get_environment_types():
    """Retrieve unique environment types."""
    from .models import db

    rows = (
        db.session.query(Environment.env_type)
        .distinct()
        .order_by(Environment.env_type)
        .all()
    )
    return [row[0] for row in rows]


def get_target_versions(target_key, package_key=None):
    """Get available versions for a deployment target."""
    requested_target_key = (target_key or "").strip().upper()
    package_key = (package_key or "").strip().lower()
    if not requested_target_key:
        return []

    if requested_target_key == "TOOLS" and package_key:
        versions = []
        for row in ComponentBuild.query.filter_by(
            target_key="TOOLS",
            build_name=package_key,
        ).order_by(ComponentBuild.version).all():
            if row.version not in versions:
                versions.append(row.version)
        if versions:
            return versions
        return PACKAGE_VERSIONS.get(package_key, COMPONENT_VERSIONS.get("TOOLS", []))

    query = ComponentBuild.query.filter(ComponentBuild.target_key == requested_target_key)

    versions = []
    for row in query.order_by(ComponentBuild.version).all():
        if row.version not in versions:
            versions.append(row.version)
    if versions:
        return versions

    return (
        COMPONENT_VERSIONS.get(requested_target_key) or
        []
    )
