"""Service layer for admin configuration and user-management flows."""

import json

from werkzeug.security import generate_password_hash

from ..auth_service import get_allowed_screens
from ..helpers import DEFAULT_ROLE_NAMES, get_valid_roles, normalize_role
from ..models import (
    ComponentBuild,
    CurrentDeploymentState,
    DeploymentRequest,
    Environment,
    EnvironmentBooking,
    EnvironmentHostMapping,
    Host,
    Role,
    ServerType,
    Team,
    TeamMember,
    User,
    db,
)


ADMIN_TABS = [
    "roles",
    "teams",
    "environments",
    "hosts",
    "server_types",
    "environment_host_mappings",
    "component_builds",
]


def normalize_checkbox(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def build_admin_page_context(active_tab=None):
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


def create_team(form):
    team_name = (form.get("team_name") or "").strip().lower()
    description = (form.get("description") or "").strip() or None
    if not team_name:
        return "Team name is required."
    if Team.query.filter_by(team_name=team_name).first() is not None:
        return "Team already exists."
    db.session.add(Team(team_name=team_name, description=description))
    return None


def create_role(form):
    role_name = (form.get("role_name") or "").strip().lower()
    description = (form.get("description") or "").strip() or None
    is_active = normalize_checkbox(form.get("is_active"))
    supported_roles = set(DEFAULT_ROLE_NAMES)
    if not role_name:
        return "Role name is required."
    if role_name not in supported_roles:
        return "Supported roles are admin and user only."
    if Role.query.filter_by(role_name=role_name).first() is not None:
        return "Role already exists."
    db.session.add(Role(role_name=role_name, description=description, is_active=is_active))
    return None


def create_environment(form):
    env_id = (form.get("env_id") or "").strip().upper()
    env_type = (form.get("env_type") or "").strip().upper()
    domain = (form.get("domain") or "").strip().lower() or None
    description = (form.get("description") or "").strip() or None
    is_active = normalize_checkbox(form.get("is_active"))
    if not env_id or not env_type:
        return "Environment ID and type are required."
    if Environment.query.filter_by(env_id=env_id).first() is not None:
        return "Environment already exists."
    db.session.add(
        Environment(
            env_id=env_id,
            env_type=env_type,
            domain=domain,
            description=description,
            is_active=is_active,
        )
    )
    return None


def create_host(form):
    hostname = (form.get("hostname") or "").strip()
    ip_address = (form.get("ip_address") or "").strip() or None
    domain = (form.get("domain") or "").strip().upper() or None
    description = (form.get("description") or "").strip() or None
    is_active = normalize_checkbox(form.get("is_active"))
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


def create_server_type(form):
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


def create_environment_host_mapping(form):
    env_id = (form.get("env_id") or "").strip().upper()
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

    if not env_id:
        return "Environment is required."
    environment = Environment.query.filter_by(env_id=env_id).first()
    if environment is None:
        return "Selected environment was not found."
    env_type = environment.env_type

    existing = EnvironmentHostMapping.query.filter_by(
        env_id=env_id,
        env_type=env_type,
        server_type_id=server_type_id,
    ).first()
    if existing is not None:
        return "Environment host mapping already exists."

    db.session.add(
        EnvironmentHostMapping(
            env_id=env_id,
            env_type=env_type,
            server_type_id=server_type_id,
            host_id=host_id,
            deployment_user=deployment_user,
            deployment_password=deployment_password,
        )
    )
    return None


def create_component_build(form):
    target_key = (form.get("target_key") or "").strip().upper()
    build_name = (form.get("build_name") or "").strip()
    version = (form.get("version") or "").strip()
    artifact_name = (form.get("artifact_name") or "").strip() or None
    artifact_path = (form.get("artifact_path") or "").strip() or None
    artifact_size_bytes = None
    checksum = (form.get("checksum") or "").strip() or None
    build_metadata = None
    build_metadata_raw = (form.get("build_metadata") or "").strip()

    if build_metadata_raw:
        try:
            build_metadata = json.loads(build_metadata_raw)
        except ValueError:
            return "Build metadata must be valid JSON."

    if not target_key or not build_name or not version:
        return "Target key, build name, and version are required."

    if form.get("artifact_size_bytes"):
        try:
            artifact_size_bytes = int(form.get("artifact_size_bytes"))
        except (TypeError, ValueError):
            return "Artifact size must be a number."

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
            artifact_size_bytes=artifact_size_bytes,
            checksum=checksum,
            build_metadata=build_metadata,
        )
    )
    return None


def create_user(form):
    user_id = (form.get("user_id") or "").strip().lower()
    email_id = (form.get("email_id") or "").strip().lower()
    first_name = (form.get("first_name") or "").strip()
    last_name = (form.get("last_name") or "").strip()
    password = form.get("password") or ""
    requested_role = (form.get("role") or "user").strip().lower()
    valid_roles = get_valid_roles()

    if not user_id:
        return "User ID is required."
    if not email_id:
        return "Email is required."
    if not password:
        return "Password is required."
    if requested_role not in valid_roles:
        return "Please select a valid role."
    if User.query.filter_by(user_id=user_id).first() is not None:
        return "That user ID already exists."
    if User.query.filter_by(email_id=email_id).first() is not None:
        return "That email is already registered."

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

    submitted_team_lead_ids = set()
    for value in form.getlist("team_lead_ids"):
        raw_value = (value or "").strip()
        if not raw_value:
            continue
        try:
            submitted_team_lead_ids.add(int(raw_value))
        except ValueError:
            return "One or more selected team lead values are invalid."

    invalid_team_lead_ids = submitted_team_lead_ids - set(team_ids)
    if invalid_team_lead_ids:
        return "Team lead can only be enabled for assigned teams."

    role = normalize_role(requested_role)
    user = User(
        user_id=user_id,
        email_id=email_id,
        first_name=first_name or None,
        last_name=last_name or None,
        name="{} {}".format(first_name, last_name).strip() or user_id,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(user)
    db.session.flush()

    for team in selected_teams:
        db.session.add(
            TeamMember(
                user_id=user.user_id,
                team_id=team.team_id,
                role=role,
                team_lead=team.team_id in submitted_team_lead_ids,
            )
        )

    return None


def update_user_role(form):
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


def update_user_teams(form):
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

    submitted_team_lead_ids = set()
    for value in form.getlist("team_lead_ids"):
        raw_value = (value or "").strip()
        if not raw_value:
            continue
        try:
            submitted_team_lead_ids.add(int(raw_value))
        except ValueError:
            return "One or more selected team lead values are invalid."

    invalid_team_lead_ids = submitted_team_lead_ids - set(team_ids)
    if invalid_team_lead_ids:
        return "Team lead can only be enabled for assigned teams."

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
                    team_lead=team.team_id in submitted_team_lead_ids,
                )
            )
        else:
            membership.role = user.role
            membership.team_lead = team.team_id in submitted_team_lead_ids

    return None


def delete_user(form):
    user_id = (form.get("user_id") or "").strip().lower()
    if not user_id:
        return "User ID is required."

    user = User.query.filter_by(user_id=user_id).first()
    if user is None:
        return "Selected user was not found."

    if EnvironmentBooking.query.filter_by(requested_by=user.user_id).first() is not None:
        return "Cannot delete a user who has booking history."
    if DeploymentRequest.query.filter(
        (DeploymentRequest.requested_by == user.user_id) |
        (DeploymentRequest.approved_by == user.user_id)
    ).first() is not None:
        return "Cannot delete a user who has deployment request history."
    if CurrentDeploymentState.query.filter_by(updated_by=user.user_id).first() is not None:
        return "Cannot delete a user who has deployment state history."

    for membership in list(user.team_memberships or []):
        db.session.delete(membership)
    db.session.delete(user)
    return None


def handle_admin_form(form):
    action = (form.get("action") or "create").strip().lower()
    entity = (form.get("entity") or "").strip()
    if action == "create_user":
        return create_user(form)
    if action == "delete_user":
        return delete_user(form)
    if action == "update_role":
        return update_user_role(form)
    if action == "update_teams":
        return update_user_teams(form)

    handlers = {
        "roles": create_role,
        "teams": create_team,
        "environments": create_environment,
        "hosts": create_host,
        "server_types": create_server_type,
        "environment_host_mappings": create_environment_host_mapping,
        "component_builds": create_component_build,
    }
    handler = handlers.get(entity)
    if handler is None:
        return "Unknown admin action."
    return handler(form)
