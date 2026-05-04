"""
Utility and helper functions for common operations.
"""

from datetime import datetime, timedelta, timezone
from flask import current_app, has_app_context, jsonify

from .models import EnvironmentBooking, ComponentBuild, DeploymentRequest, Environment, format_datetime
from .constants import (
    BOOKING_LIFECYCLE_STATUS,
    BOOKING_STATUS,
    BOOKING_STATUS_ALIASES,
    COMPONENT_VERSIONS,
    PACKAGE_VERSIONS,
    VALID_ROLES,
    VALID_TEAMS,
)
from .deployment_targets import derive_component_type, get_target_definition


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


def normalize_role(role):
    """Normalize role to valid value or default to 'user'."""
    role = (role or "user").strip().lower()
    return role if role in VALID_ROLES else "user"


def normalize_team(team):
    """Normalize team to valid value or default to 'support'."""
    team = (team or "support").strip().lower()
    return team if team in VALID_TEAMS else "support"


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


def get_list_bookings():
    """Retrieve bookings plus standalone deployment requests for workspace views."""
    bookings = EnvironmentBooking.query.order_by(EnvironmentBooking.start_time).all()
    deployment_requests = DeploymentRequest.query.order_by(
        DeploymentRequest.planned_start_time
    ).all()
    items = [serialize_booking(booking) for booking in bookings]
    items.extend(
        serialize_deployment_request_for_workspace(deployment_request)
        for deployment_request in deployment_requests
    )
    return sorted(items, key=lambda item: item.get("start_time") or "")


def get_environments():
    """Retrieve all environments grouped by type."""
    environments = Environment.query.order_by(
        Environment.env_type, Environment.env_id
    ).all()
    return [
        {
            "env_id": environment.env_id,
            "env_type": environment.env_type,
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


def get_component_versions(component_type, package_key=None):
    """Get available versions for a component type."""
    requested_target_key = (component_type or "").strip().upper()
    package_key = (package_key or "").strip().lower()
    if not requested_target_key:
        return []

    if requested_target_key == "TOOLS" and package_key:
        versions = [
            row.version
            for row in ComponentBuild.query.filter(
                (ComponentBuild.component_type == "TOOLS") &
                (
                    (ComponentBuild.component_name == package_key) |
                    (ComponentBuild.artifact_name == package_key)
                )
            ).order_by(ComponentBuild.version).all()
        ]
        if versions:
            return versions
        return PACKAGE_VERSIONS.get(package_key, COMPONENT_VERSIONS.get("TOOLS", []))

    target_definition = get_target_definition(requested_target_key) or {}
    canonical_type = derive_component_type(requested_target_key, requested_target_key).upper()
    component_name = (target_definition.get("component_name") or "").strip()

    query = ComponentBuild.query
    if component_name:
        query = query.filter(
            (ComponentBuild.component_type == canonical_type) |
            (ComponentBuild.component_name == component_name)
        )
    else:
        query = query.filter(ComponentBuild.component_type == canonical_type)

    versions = [
        row.version
        for row in query.order_by(ComponentBuild.version).all()
    ]
    if versions:
        return versions

    return (
        COMPONENT_VERSIONS.get(requested_target_key) or
        COMPONENT_VERSIONS.get(canonical_type, [])
    )
