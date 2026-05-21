from datetime import datetime, timezone

from flask import current_app, render_template

from monitoring.api import _build_environment_health_payload, _get_active_booking_env_ids

from .blueprint import main_bp
from ..auth_service import current_user, get_allowed_screens, login_required, screen_required


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

    dashboard_payload = _build_environment_health_payload(
        env_statuses,
        last_update,
        active_booking_envs,
    )
    statuses = dashboard_payload["statuses"]
    summary = dashboard_payload["summary"]

    grouped_statuses = {}
    for status in statuses:
        grouped_statuses.setdefault(status["env_type"], []).append(status)
    grouped_statuses = {env_type: grouped_statuses[env_type] for env_type in sorted(grouped_statuses)}

    return render_template(
        "env_health_dashboard.html",
        grouped_statuses=grouped_statuses,
        id=user.id,
        role=user.role,
        statuses=statuses,
        summary=summary,
        refresh_seconds=30,
        active_envs=dashboard_payload["active_envs"],
    )


@main_bp.route("/screen/manager")
@screen_required("manager_screen")
def manager_screen():
    return render_template("screen.html", title="Manager Screen")


@main_bp.route("/screen/alpha")
@screen_required("alpha_screen")
def alpha_screen():
    return render_template("screen.html", title="Alpha Team Screen")


@main_bp.route("/screen/general")
@screen_required("general_screen")
def general_screen():
    return render_template("screen.html", title="General Screen")


@main_bp.route("/dashboard-preview")
def dashboard_preview():
    grouped_statuses = {
        "DEV": [
            {
                "env_id": "DEV01", "env_type": "DEV", "host": "host1.local", "owner_team": "alpha",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "DEV02", "env_type": "DEV", "host": "host1.local", "owner_team": "alpha",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "DEV03", "env_type": "DEV", "host": "host1.local", "owner_team": "beta",
                "status": "warning", "message": "Running: 5, Not running: 0, Unknown: 0",
                "server_types": ["Getway"],
            },
            {
                "env_id": "DEV04", "env_type": "DEV", "host": "host1.local", "owner_team": "support",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "DEV05", "env_type": "DEV", "host": "host1.local", "owner_team": "alpha",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "DEV06", "env_type": "DEV", "host": "host1.local", "owner_team": "beta",
                "status": "warning", "message": "Running: 3, Not running: 2, Unknown: 0",
                "server_types": ["Getway"],
            },
            {
                "env_id": "DEV07", "env_type": "DEV", "host": "host1.local", "owner_team": "support",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "DEV08", "env_type": "DEV", "host": "host1.local", "owner_team": "alpha",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "DEV09", "env_type": "DEV", "host": "host1.local", "owner_team": "beta",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Getway"],
            },
            {
                "env_id": "DEV10", "env_type": "DEV", "host": "host1.local", "owner_team": "alpha",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
        ],
        "QA": [
            {
                "env_id": "QA01", "env_type": "QA", "host": "host2.local", "owner_team": "qa",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "QA02", "env_type": "QA", "host": "host2.local", "owner_team": "qa",
                "status": "warning", "message": "Running: 3, Not running: 1, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "QA03", "env_type": "QA", "host": "host2.local", "owner_team": "qa",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Getway"],
            },
        ],
        "ST": [
            {
                "env_id": "ST01", "env_type": "ST", "host": "host2.local", "owner_team": "qa",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "ST02", "env_type": "ST", "host": "host2.local", "owner_team": "qa",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "ST03", "env_type": "ST", "host": "host2.local", "owner_team": "qa",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Getway"],
            },
        ],
        "PROD": [
            {
                "env_id": "PROD01", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "healthy", "message": "Running: 8, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "PROD02", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "PROD03", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "critical", "message": "Running: 2, Not running: 4, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
            {
                "env_id": "PROD04", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "healthy", "message": "Running: 4, Not running: 0, Unknown: 0",
                "server_types": ["Getway"],
            },
            {
                "env_id": "PROD05", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "critical", "message": "Running: 1, Not running: 3, Unknown: 0",
                "server_types": ["Core"],
            },
            {
                "env_id": "PROD06", "env_type": "PROD", "host": "host2.local", "owner_team": "support",
                "status": "maintenance", "message": "Running: 0, Not running: 0, Unknown: 0",
                "server_types": ["Core", "Getway"],
            },
        ],
    }
    test_data = {
        "id": "preview.admin",
        "role": "admin",
        "summary": {
            "total": 33,
            "healthy": 26,
            "warning": 4,
            "critical": 2,
            "maintenance": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        "refresh_seconds": 30,
        "grouped_statuses": grouped_statuses,
        "statuses": [item for items in grouped_statuses.values() for item in items],
        "active_envs": ["DEV01", "PROD01"],
    }
    return render_template("env_health_dashboard.html", **test_data)
