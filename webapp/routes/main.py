import logging
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from monitoring.api import _build_environment_health_payload, _get_active_booking_env_ids

from ..models import CurrentDeploymentState, Team, TeamMember, User, db
from ..auth_service import (
    can_access_env_team_screen,
    current_user,
    login_required,
    screen_required,
    get_allowed_screens,
)
from ..services.booking_service import BookingService
from ..services.deployment_request_service import DeploymentRequestService
from ..helpers import (
    json_error,
    normalize_role,
    normalize_team,
    serialize_booking,
    get_list_bookings,
    get_environments,
    get_environment_types,
    get_target_versions,
)

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


# Registration and Authentication Routes
@main_bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("main.environment_health"))
    return redirect(url_for("main.login"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = normalize_role(request.form.get("role", "user"))
        team = normalize_team(request.form.get("team", "support"))

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        team_record = Team.query.filter_by(team_name=team).first()
        if team_record is None:
            team_record = Team(team_name=team)
            db.session.add(team_record)
            db.session.flush()

        user = User(
            username=username,
            name=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(
            TeamMember(
                user_id=user.user_id,
                team_id=team_record.team_id,
                role=role,
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.warning("Registration failed because username %s already exists.", username)
            flash("That username is already registered.", "danger")
            return render_template("register.html")

        logger.info("User %s registered with role=%s team=%s", username, role, team)
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")

@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not check_password_hash(user.password_hash, password):
            logger.warning("Login failed for username %s", username or "unknown")
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user.user_id
        logger.info("User %s logged in successfully", user.username)
        return redirect(url_for("main.environment_health"))

    return render_template("login.html")

@main_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        logger.info("User %s logged out", user_id)
    return redirect(url_for("main.login"))

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
    
    # For env_health_dashboard.html
    grouped_statuses = {}
    for status in statuses:
        grouped_statuses.setdefault(status['env_type'], []).append(status)
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

@main_bp.route("/api/bookings", methods=["GET"])
@login_required
def api_list_bookings():
    return jsonify(get_list_bookings())

@main_bp.route("/api/bookings", methods=["POST"])
@login_required
def api_create_booking():
    user = current_user()
    data = request.get_json(silent=True) or {}
    booking, error, status_code = BookingService.create(data, user)
    if error:
        return json_error(error, status_code)

    response = jsonify(
        {
            "message": "Booking created successfully.",
            "booking_id": booking.booking_id,
            "booking": serialize_booking(booking),
        }
    )
    response.status_code = status_code
    return response

@main_bp.route("/api/bookings/<booking_id>", methods=["PUT"])
@login_required
def api_update_booking(booking_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    booking, error, status_code = BookingService.update(booking_id, data, user)
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Booking updated successfully.",
            "booking": serialize_booking(booking),
        }
    )

@main_bp.route("/api/bookings/<booking_id>", methods=["DELETE"])
@login_required
def api_delete_booking(booking_id):
    user = current_user()
    booking, error, status_code = BookingService.delete(booking_id, user)
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Booking cancelled successfully.",
            "booking": serialize_booking(booking),
        }
    )

@main_bp.route("/api/component-versions")
@login_required
def api_component_versions():
    target_key = request.args.get("target_key")
    package_key = request.args.get("package_key")
    return jsonify({"versions": get_target_versions(target_key, package_key=package_key)})

@main_bp.route("/api/environments")
@login_required
def api_environments():
    return jsonify({"environments": get_environments()})

@main_bp.route("/api/environment-types")
@login_required
def api_environment_types():
    return jsonify({"environment_types": get_environment_types()})


@main_bp.route("/api/deployment-requests", methods=["GET"])
@login_required
def api_list_deployment_requests():
    user = current_user()
    scope = request.args.get("scope", "auto")
    status = request.args.get("status")
    requests_data, error, status_code = DeploymentRequestService.list_requests(
        user,
        scope=scope,
        status=status,
    )
    if error:
        return json_error(error, status_code)
    return jsonify({"deployment_requests": requests_data})


@main_bp.route("/api/deployment-requests", methods=["POST"])
@login_required
def api_create_deployment_request():
    user = current_user()
    data = request.get_json(silent=True) or {}
    deployment_request, error, status_code = DeploymentRequestService.create(data, user)
    if error:
        return json_error(error, status_code)
    response = jsonify(
        {
            "message": "Deployment request created successfully.",
            "deployment_request": DeploymentRequestService.serialize(
                deployment_request,
                user=user,
            ),
        }
    )
    response.status_code = status_code
    return response


@main_bp.route("/api/current-deployments", methods=["GET"])
@login_required
def api_list_current_deployments():
    query = CurrentDeploymentState.query.order_by(CurrentDeploymentState.updated_at.desc())
    env_scope_type = (request.args.get("env_scope_type") or "").strip().upper()
    env_id = (request.args.get("env_id") or "").strip()
    env_type = (request.args.get("env_type") or "").strip().upper()
    target_key = (request.args.get("target_key") or "").strip().upper()

    if env_scope_type:
        query = query.filter(CurrentDeploymentState.env_scope_type == env_scope_type)
    if env_id:
        query = query.filter(CurrentDeploymentState.env_id == env_id)
    if env_type:
        query = query.filter(CurrentDeploymentState.env_type == env_type)
    if target_key:
        query = query.filter(CurrentDeploymentState.target_key == target_key)

    return jsonify({
        "current_deployments": [item.to_dict() for item in query.all()]
    })


@main_bp.route("/api/deployment-requests/<deployment_request_id>/actions", methods=["POST"])
@login_required
def api_apply_deployment_request_action(deployment_request_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    deployment_request, error, status_code = DeploymentRequestService.apply_action(
        deployment_request_id,
        data.get("action"),
        user,
        payload=data,
    )
    if error:
        return json_error(error, status_code)
    return jsonify(
        {
            "message": "Deployment request updated successfully.",
            "deployment_request": DeploymentRequestService.serialize(
                deployment_request,
                user=user,
            ),
        }
    )


@main_bp.route("/api/deployment-requests/<deployment_request_id>/logs", methods=["GET"])
@login_required
def api_deployment_request_logs(deployment_request_id):
    user = current_user()
    requests_data, error, status_code = DeploymentRequestService.list_requests(
        user,
        scope="env" if can_access_env_team_screen(user) else "mine",
    )
    if error:
        return json_error(error, status_code)
    deployment_request = next(
        (
            item for item in requests_data
            if item["deployment_request_id"] == str(deployment_request_id)
        ),
        None,
    )
    if deployment_request is None:
        return json_error("Deployment request not found.", 404)
    return jsonify({"deployments": deployment_request.get("resolved_targets", [])})

@main_bp.route("/screen/admin")
@screen_required("admin_screen")
def admin_screen():
    return render_template("screen.html", title="Admin Screen")

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

@main_bp.route('/receive-bam-stream-message', methods=['POST'])
@login_required
def receive_stream_message():
    """
    Receive booking activity messages from BAM stream.
    Updates booking state based on incoming messages.
    """
    try:
        data = request.get_json()
        bookings = data.get('bookings', [])
        # TODO: Process booking activity messages
        # This could update booking statuses, notify users, etc.
        return jsonify({'status': 'success', 'message': 'Stream message received'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@main_bp.route('/dashboard-preview')
def dashboard_preview():
    """
    Test route to preview dashboard with dummy data.
    Useful for UI/UX testing without needing live environment data.
    """
    grouped_statuses = {
            'DEV': [
                {
                    'env_id': 'DEV01', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'alpha',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'DEV02', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'alpha',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'DEV03', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'beta',
                    'status': 'warning', 'message': 'Running: 5, Not running: 0, Unknown: 0',
                    'server_types': ['Getway']
                },
                {
                    'env_id': 'DEV04', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'support',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'DEV05', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'alpha',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'DEV06', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'beta',
                    'status': 'warning', 'message': 'Running: 3, Not running: 2, Unknown: 0',
                    'server_types': ['Getway']
                },
                {
                    'env_id': 'DEV07', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'support',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'DEV08', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'alpha',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'DEV09', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'beta',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Getway']
                },
                {
                    'env_id': 'DEV10', 'env_type': 'DEV', 'host': 'host1.local', 'owner_team': 'alpha',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                }
            ],
            'QA': [
                {
                    'env_id': 'QA01', 'env_type': 'QA', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'QA02', 'env_type': 'QA', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'warning', 'message': 'Running: 3, Not running: 1, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'QA03', 'env_type': 'QA', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Getway']
                }
            ],
            'ST': [
                {
                    'env_id': 'ST01', 'env_type': 'ST', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'ST02', 'env_type': 'ST', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'ST03', 'env_type': 'ST', 'host': 'host2.local', 'owner_team': 'qa',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Getway']
                }
            ],
            'PROD': [
                {
                    'env_id': 'PROD01', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'healthy', 'message': 'Running: 8, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'PROD02', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'PROD03', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'critical', 'message': 'Running: 2, Not running: 4, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                },
                {
                    'env_id': 'PROD04', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'healthy', 'message': 'Running: 4, Not running: 0, Unknown: 0',
                    'server_types': ['Getway']
                },
                {
                    'env_id': 'PROD05', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'critical', 'message': 'Running: 1, Not running: 3, Unknown: 0',
                    'server_types': ['Core']
                },
                {
                    'env_id': 'PROD06', 'env_type': 'PROD', 'host': 'host2.local', 'owner_team': 'support',
                    'status': 'maintenance', 'message': 'Running: 0, Not running: 0, Unknown: 0',
                    'server_types': ['Core', 'Getway']
                }
            ]
        }
    test_data = {
        'id': 'preview.admin',
        'role': 'admin',
        'summary': {
            'total': 33,
            'healthy': 26,
            'warning': 4,
            'critical': 2,
            'maintenance': 1,
            'last_updated': datetime.now(timezone.utc).isoformat()
        },
        'refresh_seconds': 30,
        'grouped_statuses': grouped_statuses,
        'statuses': [item for items in grouped_statuses.values() for item in items],
        'active_envs': ['DEV01', 'PROD01']
    }
    return render_template('env_health_dashboard.html', **test_data)
