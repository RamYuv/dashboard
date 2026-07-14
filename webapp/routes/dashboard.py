from datetime import datetime, timezone

from flask import current_app, render_template

from monitoring.api import _build_environment_health_payload, _get_active_booking_env_ids
from ..helpers import can_user_access_environment
from ..models import Environment, PayUiAccessType, ServerTypeKey

from .blueprint import main_bp
from ..auth_service import current_user, get_allowed_screens, login_required


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    allowed_screens = []
    for screen in get_allowed_screens(user):
        endpoint = screen.get("endpoint") or ""
        if "." not in endpoint:
            endpoint = "booking.{}".format(endpoint) if endpoint == "booking_screen" else "main.{}".format(endpoint)
        screen_data = dict(screen)
        screen_data["url_endpoint"] = endpoint
        allowed_screens.append(screen_data)
    return render_template("dashboard.html", screens=allowed_screens)


@main_bp.route("/environment-health")
@login_required
def environment_health():
    current_app.monitor_state.refresh_from_persisted()
    user = current_user()
    env_statuses, last_update = current_app.monitor_state.snapshot()
    active_booking_envs = _get_active_booking_env_ids()
    refresh_seconds = current_app.config.get("MONITOR_REFRESH_SECONDS", 30)

    dashboard_payload = _build_environment_health_payload(
        env_statuses,
        last_update,
        active_booking_envs,
    )
    statuses = dashboard_payload["statuses"]
    summary = dashboard_payload["summary"]
    bookable_env_ids = [
        environment.env_id
        for environment in Environment.query.order_by(Environment.env_id).all()
        if can_user_access_environment(user, environment)
    ]

    grouped_statuses = {}
    for status in statuses:
        grouped_statuses.setdefault(status["team"], []).append(status)
    grouped_statuses = {team: grouped_statuses[team] for team in sorted(grouped_statuses)}
    access_actions = {
        "access-core-server": {
            "kind": "terminal",
            "access_type": ServerTypeKey.CORE.value,
            "label": "Access Core Server",
        },
        "access-gateway-server": {
            "kind": "terminal",
            "access_type": ServerTypeKey.GATEWAY.value,
            "label": "Access Gateway Server",
        },
        "access-core-database": {
            "kind": "terminal",
            "access_type": ServerTypeKey.COREDB.value,
            "label": "Access Core Database",
        },
        "access-lg-database": {
            "kind": "terminal",
            "access_type": ServerTypeKey.LGDB.value,
            "label": "Access LG Database",
        },
        "user-pay-weblink": {
            "kind": "link",
            "access_type": PayUiAccessType.PAY_URL.value,
            "label": "User Pay Weblink",
        },
        "access-pay-admin-link": {
            "kind": "link",
            "access_type": PayUiAccessType.PAY_ADMIN.value,
            "label": "Access Pay Admin link",
        },
    }

    return render_template(
        "env_health_dashboard.html",
        app_short_name="Envista",
        app_full_name="Development Envioment Services",
        app_version=current_app.config.get("APP_VERSION", "1.0"),
        grouped_statuses=grouped_statuses,
        id=user.id,
        role=user.normalized_role,
        team_names=getattr(user, "team_names", []) or [],
        bookable_env_ids=bookable_env_ids,
        statuses=statuses,
        summary=summary,
        refresh_seconds=refresh_seconds,
        active_envs=dashboard_payload["active_envs"],
        access_actions=access_actions,
    )
