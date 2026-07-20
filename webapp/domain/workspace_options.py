"""
Shared workspace/page configuration used by booking and deployment templates.
"""

from flask import has_app_context

from .deployment_targets import get_deployment_target_options
from ..models import TCSDeploymentMode, TcsService


DEPLOYMENT_TCS_DEPLOYMENT_MODES = [
    {"value": "RT", "label": "RT"},
    {"value": "TFT", "label": "TFT"},
]

DEPLOYMENT_TCS_SERVICES = [
    {"value": "STL", "label": "STL"},
    {"value": "NOW", "label": "NOW"},
]

WORKSPACE_STATUS_DEFINITIONS = [
    {"value": "scheduled", "label": "Scheduled", "legend_label": "Scheduled"},
    {"value": "active", "label": "Active", "legend_label": "Active"},
    {"value": "completed", "label": "Completed", "legend_label": "Completed"},
    {"value": "cancelled", "label": "Cancelled", "legend_label": "Cancelled"},
    {"value": "open", "label": "Open", "legend_label": "Open"},
    {"value": "ready_for_deployment", "label": "Ready For Deployment", "legend_label": "Ready"},
    {"value": "auto_deployment_running", "label": "Auto Deployment Running", "legend_label": "Auto Running"},
    {"value": "manual_deployment_in_progress", "label": "Manual Deployment In Progress", "legend_label": "Manual Running"},
    {"value": "failed", "label": "Failed", "legend_label": "Failed"},
    {"value": "rejected", "label": "Rejected", "legend_label": "Rejected"},
]

DEPLOYMENT_QUEUE_STATUS_OPTIONS = [
    {"value": "OPEN", "label": "Open"},
    {"value": "READY_FOR_DEPLOYMENT", "label": "Ready For Deployment"},
    {"value": "AUTO_DEPLOYMENT_RUNNING", "label": "Auto Deployment Running"},
    {"value": "MANUAL_DEPLOYMENT_IN_PROGRESS", "label": "Manual Deployment In Progress"},
    {"value": "COMPLETED", "label": "Completed"},
    {"value": "FAILED", "label": "Failed"},
    {"value": "CANCELLED", "label": "Cancelled"},
    {"value": "REJECTED", "label": "Rejected"},
]


def _visible_deployment_targets():
    return [
        target
        for target in (get_deployment_target_options() or [])
        if (target.get("target_key") or "").strip().upper() != "TOOLS"
    ]


def get_workspace_deployment_form_options():
    """Return shared deployment-form choices for workspace templates."""
    tcs_deployment_modes = []
    tcs_services = []
    if has_app_context():
        try:
            tcs_deployment_modes = [
                {
                    "value": item.tcs_deployment_mode_id,
                    "label": item.mode_name,
                }
                for item in TCSDeploymentMode.query.filter_by(is_active=True).order_by(
                    TCSDeploymentMode.tcs_deployment_mode_id
                ).all()
            ]
        except Exception:
            tcs_deployment_modes = []
        try:
            tcs_services = [
                {
                    "value": item.tcs_service_id,
                    "label": item.service_name,
                }
                for item in TcsService.query.filter_by(is_active=True).order_by(
                    TcsService.tcs_service_id
                ).all()
            ]
        except Exception:
            tcs_services = []

    return {
        "targets": _visible_deployment_targets(),
        "tcs_deployment_modes": tcs_deployment_modes or DEPLOYMENT_TCS_DEPLOYMENT_MODES,
        "tcs_services": tcs_services or DEPLOYMENT_TCS_SERVICES,
    }


def get_workspace_status_options():
    """Return shared booking/deployment status metadata for workspace pages."""
    status_labels = {item["value"]: item["label"] for item in WORKSPACE_STATUS_DEFINITIONS}
    deployment_queue_labels = {
        item["value"]: item["label"] for item in DEPLOYMENT_QUEUE_STATUS_OPTIONS
    }
    return {
        "booking_statuses": WORKSPACE_STATUS_DEFINITIONS,
        "calendar_legend_statuses": WORKSPACE_STATUS_DEFINITIONS,
        "deployment_queue_statuses": DEPLOYMENT_QUEUE_STATUS_OPTIONS,
        "status_labels": status_labels,
        "deployment_queue_status_labels": deployment_queue_labels,
    }
