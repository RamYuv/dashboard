"""Service layer for admin configuration and user-management flows."""

from datetime import datetime

from flask import current_app
from werkzeug.security import generate_password_hash as generate_hzn_hash

from ..auth_service import get_allowed_screens
from ..component_build_catalog import (
    build_package_entries,
    canonical_build_name,
)
from ..domain.deployment_targets import get_deployment_target_options, get_target_definition
from ..helpers import DEFAULT_ROLE_NAMES, get_valid_roles, normalize_role
from ..db_init import get_seed_runtime_summary
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


def is_valid_host_id(host_id):
    normalized = (host_id or "").strip()
    return bool(normalized) and "-" not in normalized and normalized.replace("_", "").isalnum()


def build_admin_page_context(active_tab=None):
    selected_tab = active_tab if active_tab in ADMIN_TABS else ADMIN_TABS[0]
    environments = Environment.query.order_by(Environment.env_type, Environment.env_id).all()
    hosts = Host.query.order_by(Host.hostname).all()
    server_types = ServerType.query.order_by(ServerType.target_key, ServerType.server_type_key).all()
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
        "component_builds": build_component_build_rows(
            ComponentBuild.query.order_by(
                ComponentBuild.target_key,
                ComponentBuild.version,
                ComponentBuild.build_name,
            ).all()
        ),
        "mapping_environment_options": environments,
        "mapping_host_options": hosts,
        "mapping_server_type_options": server_types,
        "component_build_target_options": get_deployment_target_options(),
        "seed_runtime": get_seed_runtime_summary(),
        "deployment_runtime": {
            "engine": (current_app.config.get("DEPLOYMENT_ENGINE") or "SCRIPT").strip().upper(),
            "launcher": (
                current_app.config.get("DEPLOYMENT_LAUNCHER")
                or current_app.config.get("AUTO_DEPLOY_SCRIPT")
                or ""
            ).strip() or None,
            "auto_enabled": bool(current_app.config.get("AUTO_DEPLOY_ENABLED", False)),
        },
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


def update_team(form):
    team_id = form.get("team_id") or ""
    try:
        team_id = int(team_id)
    except (TypeError, ValueError):
        return "Team was not found."

    team = Team.query.get(team_id)
    if team is None:
        return "Team was not found."

    team_name = (form.get("team_name") or "").strip().lower()
    description = (form.get("description") or "").strip() or None
    if not team_name:
        return "Team name is required."

    duplicate = Team.query.filter(
        Team.team_name == team_name,
        Team.team_id != team.team_id,
    ).first()
    if duplicate is not None:
        return "Team already exists."

    team.team_name = team_name
    team.description = description
    return None


def delete_team(form):
    team_id = form.get("team_id") or ""
    try:
        team_id = int(team_id)
    except (TypeError, ValueError):
        return "Team was not found."

    team = Team.query.get(team_id)
    if team is None:
        return "Team was not found."
    if TeamMember.query.filter_by(team_id=team.team_id).first() is not None:
        return "Cannot delete a team that still has assigned users."

    db.session.delete(team)
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


def update_role_record(form):
    role_name = (form.get("original_role_name") or form.get("role_name") or "").strip().lower()
    if not role_name:
        return "Role name is required."

    role = Role.query.filter_by(role_name=role_name).first()
    if role is None:
        return "Role was not found."

    role.description = (form.get("description") or "").strip() or None
    role.is_active = normalize_checkbox(form.get("is_active"))
    return None


def delete_role_record(form):
    role_name = (form.get("original_role_name") or form.get("role_name") or "").strip().lower()
    if not role_name:
        return "Role name is required."
    if role_name in set(DEFAULT_ROLE_NAMES):
        return "Default roles cannot be deleted."

    role = Role.query.filter_by(role_name=role_name).first()
    if role is None:
        return "Role was not found."
    if User.query.filter_by(role=role_name).first() is not None:
        return "Cannot delete a role that is assigned to users."

    db.session.delete(role)
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


def update_environment(form):
    env_id = (form.get("original_env_id") or form.get("env_id") or "").strip().upper()
    if not env_id:
        return "Environment ID is required."

    environment = Environment.query.filter_by(env_id=env_id).first()
    if environment is None:
        return "Environment was not found."

    env_type = (form.get("env_type") or "").strip().upper()
    if not env_type:
        return "Environment type is required."

    environment.env_type = env_type
    environment.domain = (form.get("domain") or "").strip().lower() or None
    environment.description = (form.get("description") or "").strip() or None
    environment.is_active = normalize_checkbox(form.get("is_active"))

    for mapping in EnvironmentHostMapping.query.filter_by(env_id=env_id).all():
        mapping.env_type = env_type
    return None


def delete_environment(form):
    env_id = (form.get("original_env_id") or form.get("env_id") or "").strip().upper()
    if not env_id:
        return "Environment ID is required."

    environment = Environment.query.filter_by(env_id=env_id).first()
    if environment is None:
        return "Environment was not found."
    if EnvironmentHostMapping.query.filter_by(env_id=env_id).first() is not None:
        return "Cannot delete an environment that still has host mappings."
    if EnvironmentBooking.query.filter_by(env_id=env_id).first() is not None:
        return "Cannot delete an environment that has booking history."
    if DeploymentRequest.query.filter_by(env_id=env_id).first() is not None:
        return "Cannot delete an environment that has deployment request history."
    if CurrentDeploymentState.query.filter_by(env_id=env_id).first() is not None:
        return "Cannot delete an environment that has current deployment state."

    db.session.delete(environment)
    return None


def create_host(form):
    host_id = (form.get("host_id") or "").strip()
    hostname = (form.get("hostname") or "").strip()
    ip_address = (form.get("ip_address") or "").strip() or None
    domain = (form.get("domain") or "").strip().upper() or None
    description = (form.get("description") or "").strip() or None
    is_active = normalize_checkbox(form.get("is_active"))
    if not host_id:
        return "Host ID is required."
    if not is_valid_host_id(host_id):
        return "Host ID can contain only letters, numbers, and underscores. Hyphens are not allowed."
    if not hostname:
        return "Host name is required."
    if Host.query.filter_by(host_id=host_id).first() is not None:
        return "Host ID already exists."
    if Host.query.filter_by(hostname=hostname, ip_address=ip_address, domain=domain).first() is not None:
        return "Host already exists for that host name, IP address, and domain."
    db.session.add(
        Host(
            host_id=host_id,
            hostname=hostname,
            ip_address=ip_address,
            domain=domain,
            description=description,
            is_active=is_active,
        )
    )
    return None


def update_host(form):
    original_host_id = (form.get("original_host_id") or form.get("host_id") or "").strip()
    host_id = (form.get("host_id") or "").strip()
    if not original_host_id:
        return "Host was not found."
    if not is_valid_host_id(host_id):
        return "Host ID can contain only letters, numbers, and underscores. Hyphens are not allowed."
    if host_id != original_host_id:
        return "Host ID cannot be changed."

    host = Host.query.get(original_host_id)
    if host is None:
        return "Host was not found."

    hostname = (form.get("hostname") or "").strip()
    ip_address = (form.get("ip_address") or "").strip() or None
    domain = (form.get("domain") or "").strip().upper() or None
    if not hostname:
        return "Host name is required."

    duplicate = Host.query.filter(
        Host.hostname == hostname,
        Host.ip_address == ip_address,
        Host.domain == domain,
        Host.host_id != host.host_id,
    ).first()
    if duplicate is not None:
        return "Host already exists for that host name, IP address, and domain."

    host.hostname = hostname
    host.ip_address = ip_address
    host.domain = domain
    host.description = (form.get("description") or "").strip() or None
    host.is_active = normalize_checkbox(form.get("is_active"))
    return None


def delete_host(form):
    host_id = (form.get("host_id") or "").strip()
    if not host_id:
        return "Host was not found."

    host = Host.query.get(host_id)
    if host is None:
        return "Host was not found."
    if EnvironmentHostMapping.query.filter_by(host_id=host.host_id).first() is not None:
        return "Cannot delete a host that is still used by environment mappings."

    db.session.delete(host)
    return None


def create_server_type(form):
    server_type_key = (form.get("server_type_key") or "").strip()
    target_key = (form.get("target_key") or "").strip().upper()
    description = (form.get("description") or "").strip() or None
    if not server_type_key or not target_key:
        return "Server type key and target key are required."
    if ServerType.query.filter_by(
        server_type_key=server_type_key,
        target_key=target_key,
    ).first() is not None:
        return "Server type already exists for that target."
    db.session.add(
        ServerType(
            server_type_key=server_type_key,
            target_key=target_key,
            description=description,
        )
    )
    return None


def update_server_type(form):
    server_type_id = form.get("server_type_id") or ""
    try:
        server_type_id = int(server_type_id)
    except (TypeError, ValueError):
        return "Server type was not found."

    server_type = ServerType.query.get(server_type_id)
    if server_type is None:
        return "Server type was not found."

    server_type_key = (form.get("server_type_key") or "").strip()
    target_key = (form.get("target_key") or "").strip().upper()
    if not server_type_key or not target_key:
        return "Server type key and target key are required."

    duplicate = ServerType.query.filter(
        ServerType.server_type_key == server_type_key,
        ServerType.target_type == target_key,
        ServerType.server_type_id != server_type.server_type_id,
    ).first()
    if duplicate is not None:
        return "Server type already exists for that target."

    server_type.server_type_key = server_type_key
    server_type.target_key = target_key
    server_type.description = (form.get("description") or "").strip() or None
    return None


def delete_server_type(form):
    server_type_id = form.get("server_type_id") or ""
    try:
        server_type_id = int(server_type_id)
    except (TypeError, ValueError):
        return "Server type was not found."

    server_type = ServerType.query.get(server_type_id)
    if server_type is None:
        return "Server type was not found."
    if EnvironmentHostMapping.query.filter_by(server_type_id=server_type.server_type_id).first() is not None:
        return "Cannot delete a server type that is still used by environment mappings."

    db.session.delete(server_type)
    return None


def create_environment_host_mapping(form):
    env_id = (form.get("env_id") or "").strip().upper()
    deployment_user = (form.get("deployment_user") or "").strip() or None
    deploy_user_hzn = (form.get("deploy_user_hzn") or "").strip() or None

    try:
        server_type_id = int(form.get("server_type_id") or "")
    except ValueError:
        return "Host and server type selections are required."
    host_id = (form.get("host_id") or "").strip()
    if not host_id:
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
        existing.host_id = host_id
        existing.deployment_user = deployment_user
        existing.deploy_user_hzn = deploy_user_hzn
        return None

    db.session.add(
        EnvironmentHostMapping(
            env_id=env_id,
            env_type=env_type,
            server_type_id=server_type_id,
            host_id=host_id,
            deployment_user=deployment_user,
            deploy_user_hzn=deploy_user_hzn,
        )
    )
    return None


def update_environment_host_mapping(form):
    mapping_id = form.get("environment_host_mapping_id") or ""
    try:
        mapping_id = int(mapping_id)
    except (TypeError, ValueError):
        return "Mapping was not found."

    mapping = EnvironmentHostMapping.query.get(mapping_id)
    if mapping is None:
        return "Mapping was not found."

    env_id = (form.get("env_id") or "").strip().upper()
    deployment_user = (form.get("deployment_user") or "").strip() or None
    deploy_user_hzn = (form.get("deploy_user_hzn") or "").strip() or None

    try:
        server_type_id = int(form.get("server_type_id") or "")
    except ValueError:
        return "Host and server type selections are required."
    host_id = (form.get("host_id") or "").strip()
    if not host_id:
        return "Host and server type selections are required."

    server_type = ServerType.query.get(server_type_id)
    host = Host.query.get(host_id)
    environment = Environment.query.filter_by(env_id=env_id).first() if env_id else None
    if environment is None or server_type is None or host is None:
        return "Selected environment, host, or server type was not found."

    duplicate = EnvironmentHostMapping.query.filter(
        EnvironmentHostMapping.env_id == env_id,
        EnvironmentHostMapping.server_type_id == server_type_id,
        EnvironmentHostMapping.environment_host_mapping_id != mapping.environment_host_mapping_id,
    ).first()
    if duplicate is not None:
        return "A mapping already exists for that environment and server type."

    mapping.env_id = env_id
    mapping.env_type = environment.env_type
    mapping.server_type_id = server_type_id
    mapping.host_id = host_id
    mapping.deployment_user = deployment_user
    mapping.deploy_user_hzn = deploy_user_hzn
    return None


def delete_environment_host_mapping(form):
    mapping_id = form.get("environment_host_mapping_id") or ""
    try:
        mapping_id = int(mapping_id)
    except (TypeError, ValueError):
        return "Mapping was not found."

    mapping = EnvironmentHostMapping.query.get(mapping_id)
    if mapping is None:
        return "Mapping was not found."
    if DeploymentRequest.query.filter(
        DeploymentRequest.selected_server_mapping_ids_raw.like("%{}%".format(mapping.environment_host_mapping_id))
    ).first() is not None:
        return "Cannot delete a mapping that is referenced by deployment requests."
    if CurrentDeploymentState.query.filter_by(environment_host_mapping_id=mapping.environment_host_mapping_id).first() is not None:
        return "Cannot delete a mapping that is referenced by current deployment state."

    db.session.delete(mapping)
    return None


def _upsert_component_build_row(target_key, version, target_definition, selected_package_keys):
    package_entries = build_package_entries(
        target_key,
        target_definition=target_definition,
        selected_package_keys=selected_package_keys,
    )
    if not package_entries:
        return "No package mapping is configured for target '{}'.".format(target_key)

    build_name = canonical_build_name(
        target_key,
        selected_package_keys=[entry.get("package_key") for entry in package_entries],
        explicit_name=None,
        target_definition=target_definition,
    )
    existing = ComponentBuild.query.filter_by(
        target_key=target_key,
        build_name=build_name,
        version=version,
    ).first()
    if existing is None:
        db.session.add(
            ComponentBuild(
                target_key=target_key,
                build_name=build_name,
                version=version,
            )
        )
        return None

    return None


def _resolve_component_build_values(form):
    target_key = (form.get("target_key") or "").strip().upper()
    version = (form.get("version") or "").strip()
    tool_build_name = (form.get("tool_build_name") or "").strip().lower()

    if not target_key or not version:
        return None, None, None, "Target and version are required."

    target_definition = get_target_definition(target_key) or {}
    packages = target_definition.get("packages") or {}
    if not packages:
        return None, None, None, "Selected target was not found in deployment target configuration."

    all_package_keys = list(packages.keys())
    if target_key == "TOOLS":
        if not tool_build_name:
            return None, None, None, "Tool name is required for TOOLS version entries."
        if tool_build_name not in packages:
            return None, None, None, "Selected tool was not found in deployment target configuration."
        selected_package_keys = [tool_build_name]
    else:
        selected_package_keys = all_package_keys

    build_name = canonical_build_name(
        target_key,
        selected_package_keys=selected_package_keys,
        explicit_name=None,
        target_definition=target_definition,
    )
    return target_key, version, build_name, None


def create_component_build(form):
    target_key, version, build_name, error = _resolve_component_build_values(form)
    if error:
        return error
    if ComponentBuild.query.filter_by(target_key=target_key, build_name=build_name, version=version).first() is not None:
        return None

    db.session.add(
        ComponentBuild(
            target_key=target_key,
            build_name=build_name,
            version=version,
        )
    )
    return None


def update_component_build(form):
    build_id = form.get("build_id") or ""
    try:
        build_id = int(build_id)
    except (TypeError, ValueError):
        return "Version record was not found."

    build = ComponentBuild.query.get(build_id)
    if build is None:
        return "Version record was not found."

    target_key, version, build_name, error = _resolve_component_build_values(form)
    if error:
        return error

    duplicate = ComponentBuild.query.filter(
        ComponentBuild.target_key == target_key,
        ComponentBuild.build_name == build_name,
        ComponentBuild.version == version,
        ComponentBuild.build_id != build.build_id,
    ).first()
    if duplicate is not None:
        return "That requested version already exists."

    build.target_key = target_key
    build.build_name = build_name
    build.version = version
    return None


def delete_component_build(form):
    build_id = form.get("build_id") or ""
    try:
        build_id = int(build_id)
    except (TypeError, ValueError):
        return "Version record was not found."

    build = ComponentBuild.query.get(build_id)
    if build is None:
        return "Version record was not found."
    if DeploymentRequest.query.filter_by(build_id=build.build_id).first() is not None:
        return "Cannot delete a version that is referenced by deployment requests."

    db.session.delete(build)
    return None


def build_component_build_rows(component_builds):
    rows = []
    for build in component_builds:
        row = build.to_dict()
        target_definition = get_target_definition(build.target_key) or {}
        row["target_display_name"] = target_definition.get("display_name") or build.target_key
        row["app_name"] = build.build_name or "-"
        row["coverage_summary"] = "Selected tool" if build.target_key == "TOOLS" else "All configured servers"
        rows.append(row)
    return rows


def create_user(form):
    user_id = (form.get("user_id") or "").strip().lower()
    email_id = (form.get("email_id") or "").strip().lower()
    first_name = (form.get("first_name") or "").strip()
    last_name = (form.get("last_name") or "").strip()
    hzn = form.get("password") or ""
    requested_role = (form.get("role") or "user").strip().lower()
    valid_roles = get_valid_roles()

    if not user_id:
        return "User ID is required."
    if not email_id:
        return "Email is required."
    if not hzn:
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
        hzn_hash=generate_hzn_hash(hzn),
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
    if action == "update_role_record":
        return update_role_record(form)
    if action == "delete_role_record":
        return delete_role_record(form)
    if action == "update_team":
        return update_team(form)
    if action == "delete_team":
        return delete_team(form)
    if action == "update_environment":
        return update_environment(form)
    if action == "delete_environment":
        return delete_environment(form)
    if action == "update_host":
        return update_host(form)
    if action == "delete_host":
        return delete_host(form)
    if action == "update_server_type":
        return update_server_type(form)
    if action == "delete_server_type":
        return delete_server_type(form)
    if action == "update_environment_host_mapping":
        return update_environment_host_mapping(form)
    if action == "delete_environment_host_mapping":
        return delete_environment_host_mapping(form)
    if action == "update_component_build":
        return update_component_build(form)
    if action == "delete_component_build":
        return delete_component_build(form)

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
