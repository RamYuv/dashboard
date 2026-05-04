"""
Booking routes: environment booking calendar and booking management UI.
"""
from flask import Blueprint, current_app, render_template, session

from webapp.auth_service import can_access_env_team_screen, current_user, login_required
from webapp.services.deployment_request_service import DeploymentRequestService
from webapp.models import Environment, User
from webapp.domain.workspace_options import (
    get_workspace_deployment_form_options,
    get_workspace_status_options,
)

booking_bp = Blueprint("booking", __name__)


def _get_booking_page_context():
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    environments = Environment.query.order_by(
        Environment.env_type, Environment.env_id).all()

    return {
        "user": {
            "user_id": user.user_id if user else "guest",
            "role": user.role if user else "user",
            "team_names": getattr(user, "team_names", ["support"]) if user else ["support"],
            "team_name": getattr(user, "team_name", "support") if user else "support",
        },
        "environment_types": sorted({env.env_type for env in environments}),
        "environments": [
            {
                "env_id": env.env_id,
                "env_type": env.env_type,
            }
            for env in environments
        ],
        "server_timezone": current_app.config.get("SERVER_TIMEZONE", "UTC"),
        "reservation_policy": {
            "mutual_env_reservation_enabled": current_app.config.get(
                "MUTUAL_ENV_RESERVATION_ENABLED",
                False,
            ),
            "deployment_reservation_window_minutes": current_app.config.get(
                "DEPLOYMENT_RESERVATION_WINDOW_MINUTES",
                60,
            ),
        },
        "workspace_status_options": get_workspace_status_options(),
    }


@booking_bp.route("/")
@login_required
def booking_screen():
    return render_template(
        "booking_calendar_workspace.html",
        **_get_booking_page_context(),
    )


@booking_bp.route("/grid")
@login_required
def booking_grid():
    return render_template(
        "booking_grid.html",
        **_get_booking_page_context(),
    )


@booking_bp.route("/deployment")
@login_required
def deployment_request():
    context = _get_booking_page_context()
    deployment_form_options = get_workspace_deployment_form_options()
    deployment_targets = [
        target
        for target in deployment_form_options["targets"]
        if target.get("target_key") != "TOOLS"
    ]
    return render_template(
        "deployment_request_workspace.html",
        **context,
        deployment_targets=deployment_targets,
        deployment_form_options=deployment_form_options,
        deployment_mode="standard",
    )


@booking_bp.route("/deployment/tools")
@login_required
def tool_deployment_request():
    context = _get_booking_page_context()
    deployment_form_options = get_workspace_deployment_form_options()
    deployment_targets = [
        target
        for target in deployment_form_options["targets"]
        if target.get("target_key") == "TOOLS"
    ]
    return render_template(
        "deployment_request_workspace.html",
        **context,
        deployment_targets=deployment_targets,
        deployment_form_options=deployment_form_options,
        deployment_mode="tools",
    )


@booking_bp.route("/deployment/manage")
@login_required
def manage_deployment_requests():
    user = current_user()
    if not can_access_env_team_screen(user):
        return render_template(
            "deployment_manage_workspace.html",
            **_get_booking_page_context(),
            env_dashboard_enabled=False,
            deployment_requests=[],
        )

    deployment_requests, _, _ = DeploymentRequestService.list_requests(
        user,
        scope="env",
    )
    return render_template(
        "deployment_manage_workspace.html",
        **_get_booking_page_context(),
        env_dashboard_enabled=True,
        deployment_requests=deployment_requests,
    )


@booking_bp.route("/manage")
@login_required
def manage_bookings():
    return render_template(
        "manage_bookings_workspace.html",
        **_get_booking_page_context(),
        manage_deployment_options=get_workspace_deployment_form_options(),
    )
