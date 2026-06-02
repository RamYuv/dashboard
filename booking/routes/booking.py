"""
Booking routes: environment booking calendar and booking management UI.
"""
from flask import Blueprint, current_app, render_template, session

from webapp.auth_service import can_access_env_team_screen, current_user, login_required
from webapp.domain.workspace_options import (
    get_workspace_deployment_form_options,
    get_workspace_status_options,
)
from webapp.helpers import can_user_access_environment
from webapp.models import Environment, User
from webapp.services.deployment_request_service import DeploymentRequestService

booking_bp = Blueprint("booking", __name__)


def _get_booking_page_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def _is_tool_environment(environment):
    if environment is None:
        return False
    env_type = (getattr(environment, "env_type", "") or "").strip().upper()
    domain = (getattr(environment, "domain", "") or "").strip().lower()
    env_id = (getattr(environment, "env_id", "") or "").strip().upper()
    return env_type == "TOOLS" or domain == "tool" or "_TOOL_" in env_id


def _get_accessible_environments(
    user,
    include_tool_environments=False,
    enforce_access_policy=True,
):
    return [
        environment
        for environment in Environment.query.order_by(
            Environment.env_type,
            Environment.env_id,
        ).all()
        if _is_tool_environment(environment) == include_tool_environments
        and (
            user is not None
            if include_tool_environments
            else (
                can_user_access_environment(user, environment)
                if enforce_access_policy
                else user is not None
            )
        )
    ]


def _serialize_workspace_user(user):
    if user is None:
        return {
            "user_id": "guest",
            "role": "user",
            "team_names": ["support"],
            "team_name": "support",
            "is_env_member": False,
        }

    team_names = getattr(user, "team_names", None) or ["support"]
    team_name = getattr(user, "team_name", None) or team_names[0]
    return {
        "user_id": user.user_id,
        "role": user.role,
        "team_names": team_names,
        "team_name": team_name,
        "is_env_member": can_access_env_team_screen(user),
    }


def _get_booking_page_context(
    include_tool_environments=False,
    enforce_access_policy=True,
):
    user = _get_booking_page_user()
    environments = _get_accessible_environments(
        user,
        include_tool_environments=include_tool_environments,
        enforce_access_policy=enforce_access_policy,
    )

    return {
        "user": _serialize_workspace_user(user),
        "environment_types": sorted({env.env_type for env in environments}),
        "environments": [
            {
                "env_id": env.env_id,
                "env_type": env.env_type,
                "domain": env.domain,
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


def _render_deployment_request_page(deployment_mode):
    context = _get_booking_page_context(
        include_tool_environments=(deployment_mode == "tools"),
    )
    deployment_form_options = get_workspace_deployment_form_options()
    is_tools_mode = deployment_mode == "tools"
    deployment_targets = [
        target
        for target in deployment_form_options["targets"]
        if (target.get("target_key") == "TOOLS") == is_tools_mode
    ]
    return render_template(
        "deployment_request_workspace.html",
        **context,
        deployment_targets=deployment_targets,
        deployment_form_options=deployment_form_options,
        deployment_mode=deployment_mode,
    )


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
    return _render_deployment_request_page("standard")


@booking_bp.route("/deployment/tools")
@login_required
def tool_deployment_request():
    return _render_deployment_request_page("tools")


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
