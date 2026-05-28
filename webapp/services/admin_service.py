"""Service layer for admin configuration and user-management flows."""

from ..auth_service import get_allowed_screens
from ..helpers import DEFAULT_ROLE_NAMES, get_valid_roles, normalize_role
from ..models import (
    ComponentBuild,
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
    env_id = (form.get("env_id") or "").strip().upper() or None
    env_type = (form.get("env_type") or "").strip().upper() or None
    is_shared = normalize_checkbox(form.get("is_shared"))
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


def create_component_build(form):
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


def handle_admin_form(form):
    action = (form.get("action") or "create").strip().lower()
    entity = (form.get("entity") or "").strip()
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
