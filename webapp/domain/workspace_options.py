"""
Shared workspace/page configuration used by booking and deployment templates.
"""

from .deployment_targets import get_deployment_target_options


DEPLOYMENT_TESTING_MODES = [
    {"value": "TFT", "label": "TFT"},
    {"value": "RT", "label": "RT"},
]

DEPLOYMENT_SERVICE_TYPES = [
    {"value": "domplus", "label": "DOMPLUS"},
    {"value": "dom", "label": "DOM"},
    {"value": "conv", "label": "CONV"},
]

EDIT_DEPLOYMENT_COMPONENTS = [
    {"value": "TCS", "label": "TCS"},
    {"value": "DB", "label": "DB"},
    {"value": "PAM", "label": "PAM"},
    {"value": "TOOLS", "label": "TOOLS"},
    {"value": "MQ", "label": "MQ"},
]

EDIT_COMPONENT_PACKAGE_OPTIONS = {
    "TCS": ["cor-tcs", "gateway-tcs", "lg"],
    "DB": ["pam-db", "core-db"],
    "PAM": ["pam-app", "pam-api"],
    "TOOLS": ["scheduler", "monitoring"],
    "MQ": ["mq-broker", "mq-client"],
}

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


def get_workspace_deployment_form_options():
    """Return shared deployment-form choices for workspace templates."""
    return {
        "targets": get_deployment_target_options() or [],
        "testing_modes": DEPLOYMENT_TESTING_MODES,
        "service_types": DEPLOYMENT_SERVICE_TYPES,
        "edit_components": EDIT_DEPLOYMENT_COMPONENTS,
        "edit_component_packages": EDIT_COMPONENT_PACKAGE_OPTIONS,
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
