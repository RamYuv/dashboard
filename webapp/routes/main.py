import logging
from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from monitoring.api import _build_environment_health_payload, _get_active_booking_env_ids

from ..models import (
    ComponentBuild,
    CurrentDeploymentState,
    Environment,
    EnvironmentHostMapping,
    Host,
    Role,
    ServerType,
    Team,
    TeamMember,
    User,
    db,
)
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
    get_valid_roles,
)
from ..constants import VALID_TEAMS

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

ADMIN_TABS = [
    "roles",
    "teams",
    "environments",
    "hosts",
    "server_types",
    "environment_host_mappings",
    "component_builds",
]


def _normalize_checkbox(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _admin_redirect(tab_name):
    return redirect(url_for("main.admin_screen", tab=tab_name))


def _user_management_redirect():
    return redirect(url_for("main.user_management_screen"))


def _registration_team_choices():
    teams = Team.query.order_by(Team.team_name).all()
    if teams:
        return teams
    return [Team(team_name=team_name) for team_name in VALID_TEAMS]


def _admin_page_context(active_tab=None):
    selected_tab = active_tab if active_tab in ADMIN_TABS else ADMIN_TABS[0]
    environments = Environment.query.order_by(Environment.env_type, Environment.env_id).all()
    hosts = Host.query.order_by(Host.hostname).all()
    server_types = ServerType.query.order_by(ServerType.target_type, ServerType.server_type_key).all()
    valid_roles = get_valid_roles()
    users = User.query.order_by(User.user_id).all()
    return {
        "active_tab": selected_tab,
        "admin_tabs": ADMIN_TABS,
        "users": users,
        "multi_team_user_count": sum(1 for user in users if len(user.team_names) > 1),
        "user_access_map": {
            user.user_id: [screen.get("title") or screen.get("endpoint") for screen in get_allowed_screens(user)]
            for user in users
        },
        "roles": Role.query.order_by(Role.role_name).all(),
        "valid_roles": valid_roles,
        "teams": Team.query.order_by(Team.team_name).all(),
        "environments": environments,
        "hosts": hosts,
        "server_types": server_types,
        "environment_host_mappings": EnvironmentHostMapping.query.order_by(
            EnvironmentHostMapping.env_type,
            EnvironmentHostMapping.env_id,
            EnvironmentHostMapping.environment_host_mapping_id,
        ).all(),
        "component_builds": ComponentBuild.query.order_by(
            ComponentBuild.target_key,
            ComponentBuild.build_name,
            ComponentBuild.version,
        ).all(),
        "mapping_environment_options": environments,
        "mapping_host_options": hosts,
        "mapping_server_type_options": server_types,
    }


def _create_team_from_admin(form):
    team_name = (form.get("team_name") or "").strip().lower()
    description = (form.get("description") or "").strip() or None
    if not team_name:
        return "Team name is required."
    if Team.query.filter_by(team_name=team_name).first() is not None:
        return "Team already exists."
    db.session.add(Team(team_name=team_name, description=description))
    return None


def _create_role_from_admin(form):
    role_name = (form.get("role_name") or "").strip().lower()
    description = (form.get("description") or "").strip() or None
    is_active = _normalize_checkbox(form.get("is_active"))
    if not role_name:
        return "Role name is required."
    if Role.query.filter_by(role_name=role_name).first() is not None:
        return "Role already exists."
    db.session.add(Role(role_name=role_name, description=description, is_active=is_active))
    return None


def _create_environment_from_admin(form):
    env_id = (form.get("env_id") or "").strip().upper()
    env_type = (form.get("env_type") or "").strip().upper()
    description = (form.get("description") or "").strip() or None
    is_active = _normalize_checkbox(form.get("is_active"))
    if not env_id or not env_type:
        return "Environment ID and type are required."
    if Environment.query.filter_by(env_id=env_id).first() is not None:
        return "Environment already exists."
    db.session.add(
        Environment(
            env_id=env_id,
            env_type=env_type,
            description=description,
            is_active=is_active,
        )
    )
    return None


def _create_host_from_admin(form):
    hostname = (form.get("hostname") or "").strip()
    ip_address = (form.get("ip_address") or "").strip() or None
    domain = (form.get("domain") or "").strip().upper() or None
    description = (form.get("description") or "").strip() or None
    is_active = _normalize_checkbox(form.get("is_active"))
    if not hostname:
        return "Host name is required."
    if Host.query.filter_by(hostname=hostname, ip_address=ip_address).first() is not None:
        return "Host already exists for that host name and IP address."
    db.session.add(
        Host(
            hostname=hostname,
            ip_address=ip_address,
            domain=domain,
            description=description,
            is_active=is_active,
        )
    )
    return None


def _create_server_type_from_admin(form):
    server_type_key = (form.get("server_type_key") or "").strip()
    target_type = (form.get("target_type") or "").strip().upper()
    description = (form.get("description") or "").strip() or None
    if not server_type_key or not target_type:
        return "Server type key and target type are required."
    if ServerType.query.filter_by(
        server_type_key=server_type_key,
        target_type=target_type,
    ).first() is not None:
        return "Server type already exists for that target."
    db.session.add(
        ServerType(
            server_type_key=server_type_key,
            target_type=target_type,
            description=description,
        )
    )
    return None


def _create_environment_host_mapping_from_admin(form):
    env_id = (form.get("env_id") or "").strip().upper() or None
    env_type = (form.get("env_type") or "").strip().upper() or None
    is_shared = _normalize_checkbox(form.get("is_shared"))
    deployment_user = (form.get("deployment_user") or "").strip() or None
    deployment_password = (form.get("deployment_password") or "").strip() or None

    try:
        server_type_id = int(form.get("server_type_id") or "")
        host_id = int(form.get("host_id") or "")
    except ValueError:
        return "Host and server type selections are required."

    server_type = ServerType.query.get(server_type_id)
    host = Host.query.get(host_id)
    if server_type is None or host is None:
        return "Selected host or server type was not found."

    environment = None
    if not is_shared:
        if not env_id:
            return "Environment is required for non-shared mappings."
        environment = Environment.query.filter_by(env_id=env_id).first()
        if environment is None:
            return "Selected environment was not found."
        env_type = environment.env_type
    elif not env_type:
        return "Environment type is required for shared mappings."

    existing = EnvironmentHostMapping.query.filter_by(
        env_id=None if is_shared else env_id,
        env_type=env_type,
        is_shared=is_shared,
        server_type_id=server_type_id,
    ).first()
    if existing is not None:
        return "Environment host mapping already exists."

    db.session.add(
        EnvironmentHostMapping(
            env_id=None if is_shared else env_id,
            env_type=env_type,
            is_shared=is_shared,
            server_type_id=server_type_id,
            host_id=host_id,
            deployment_user=deployment_user,
            deployment_password=deployment_password,
        )
    )
    return None


def _create_component_build_from_admin(form):
    target_key = (form.get("target_key") or "").strip().upper()
    build_name = (form.get("build_name") or "").strip()
    version = (form.get("version") or "").strip()
    artifact_name = (form.get("artifact_name") or "").strip() or None
    artifact_path = (form.get("artifact_path") or "").strip() or None
    if not target_key or not build_name or not version:
        return "Target key, build name, and version are required."
    if ComponentBuild.query.filter_by(
        target_key=target_key,
        build_name=build_name,
        version=version,
    ).first() is not None:
        return "Component build already exists."
    db.session.add(
        ComponentBuild(
            target_key=target_key,
            build_name=build_name,
            version=version,
            artifact_name=artifact_name,
            artifact_path=artifact_path,
        )
    )
    return None


def _update_user_role_from_admin(form):
    user_id = (form.get("user_id") or "").strip().lower()
    requested_role = (form.get("role") or "").strip().lower()
    valid_roles = get_valid_roles()
    if requested_role not in valid_roles:
        return "Please select a valid role."

    role = normalize_role(requested_role)

    if not user_id:
        return "User ID is required."

    user = User.query.filter_by(user_id=user_id).first()
    if user is None:
        return "Selected user was not found."

    user.role = role
    for membership in user.team_memberships or []:
        membership.role = role
    return None


def _update_user_teams_from_admin(form):
    user_id = (form.get("user_id") or "").strip().lower()
    if not user_id:
        return "User ID is required."

    user = User.query.filter_by(user_id=user_id).first()
    if user is None:
        return "Selected user was not found."

    submitted_team_ids = []
    for value in form.getlist("team_ids"):
        raw_value = (value or "").strip()
        if not raw_value:
            continue
        try:
            submitted_team_ids.append(int(raw_value))
        except ValueError:
            return "One or more selected teams are invalid."

    team_ids = sorted(set(submitted_team_ids))
    if not team_ids:
        return "Please assign at least one team to the user."

    selected_teams = Team.query.filter(Team.team_id.in_(team_ids)).all()
    if len(selected_teams) != len(team_ids):
        return "One or more selected teams were not found."

    existing_memberships = {
        membership.team_id: membership
        for membership in (user.team_memberships or [])
    }

    for membership in list(user.team_memberships or []):
        if membership.team_id not in team_ids:
            db.session.delete(membership)

    for team in selected_teams:
        membership = existing_memberships.get(team.team_id)
        if membership is None:
            db.session.add(
                TeamMember(
                    user_id=user.user_id,
                    team_id=team.team_id,
                    role=user.role,
                )
            )
        else:
            membership.role = user.role

    return None


def _handle_admin_create(form):
    action = (form.get("action") or "create").strip().lower()
    entity = (form.get("entity") or "").strip()
    if action == "update_role":
        return _update_user_role_from_admin(form)
    if action == "update_teams":
        return _update_user_teams_from_admin(form)
    handlers = {
        "roles": _create_role_from_admin,
        "teams": _create_team_from_admin,
        "environments": _create_environment_from_admin,
        "hosts": _create_host_from_admin,
        "server_types": _create_server_type_from_admin,
        "environment_host_mappings": _create_environment_host_mapping_from_admin,
        "component_builds": _create_component_build_from_admin,
    }
    handler = handlers.get(entity)
    if handler is None:
        return "Unknown admin action."
    return handler(form)


# Registration and Authentication Routes
@main_bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("main.environment_health"))
    return redirect(url_for("main.login"))


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    team_choices = _registration_team_choices()
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("user_id", "").strip().lower()
        email_id = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        team = normalize_team(request.form.get("team", "support"))
        role = normalize_role("user")

        if not first_name or not last_name or not username or not email_id or not password:
            flash("First name, last name, user ID, email, and password are required.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if User.query.filter_by(user_id=username).first() is not None:
            flash("That user ID is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        if User.query.filter_by(email_id=email_id).first() is not None:
            flash("That email is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        team_record = Team.query.filter_by(team_name=team).first()
        if team_record is None:
            team_record = Team(team_name=team)
            db.session.add(team_record)
            db.session.flush()

        user = User(
            username=username,
            email_id=email_id,
            first_name=first_name,
            last_name=last_name,
            name="{} {}".format(first_name, last_name).strip(),
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
            logger.warning("Registration failed because user %s already exists.", username)
            flash("That user ID or email is already registered.", "danger")
            return render_template("register.html", team_choices=team_choices)

        logger.info("User %s registered with role=%s team=%s", username, role, team)
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", team_choices=team_choices)

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

@main_bp.route("/screen/admin", methods=["GET", "POST"])
@screen_required("admin_screen")
def admin_screen():
    active_tab = (request.values.get("tab") or request.values.get("entity") or ADMIN_TABS[0]).strip()
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        error = _handle_admin_create(request.form)
        if error:
            db.session.rollback()
            flash(error, "danger")
        else:
            try:
                db.session.commit()
                flash(
                    "User role updated successfully." if action == "update_role" else
                    "User teams updated successfully." if action == "update_teams" else
                    "Record created successfully.",
                    "success",
                )
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("Admin create failed for tab %s: %s", active_tab, exc)
                flash("Unable to save the record because it conflicts with existing data.", "danger")
        return _admin_redirect(active_tab)

    return render_template(
        "admin_screen.html",
        title="Admin Screen",
        **_admin_page_context(active_tab=active_tab),
    )


@main_bp.route("/screen/admin/users", methods=["GET", "POST"])
@screen_required("user_management_screen")
def user_management_screen():
    if request.method == "POST":
        action = (request.form.get("action") or "create").strip().lower()
        error = _handle_admin_create(request.form)
        if error:
            db.session.rollback()
            flash(error, "danger")
        else:
            try:
                db.session.commit()
                flash(
                    "User role updated successfully." if action == "update_role" else
                    "User teams updated successfully." if action == "update_teams" else
                    "User management updated successfully.",
                    "success",
                )
            except IntegrityError as exc:
                db.session.rollback()
                logger.warning("User management update failed: %s", exc)
                flash("Unable to save the user update because it conflicts with existing data.", "danger")
        return _user_management_redirect()

    return render_template(
        "user_management_workspace.html",
        title="User Management",
        **_admin_page_context(active_tab="users"),
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
