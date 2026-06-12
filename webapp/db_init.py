"""Database initialization and seeding functions."""

import json
from pathlib import Path

from flask import current_app, has_app_context
from werkzeug.security import generate_password_hash

from .component_build_catalog import (
    build_package_entries,
    canonical_build_name,
)
from .domain.deployment_targets import get_target_definition
from .models import (
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

BOOTSTRAP_SEED_MODELS = (
    Team,
    User,
    Environment,
    Host,
    ServerType,
    EnvironmentHostMapping,
    ComponentBuild,
)

DEFAULT_ROLES = [
    {"role_name": "user", "description": "Standard user access"},
    {"role_name": "admin", "description": "Administrator access"},
]

SEED_HOSTS_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "configs" / "default_seed_hosts.json"
)
ACCESS_ADMIN_TEAM_NAME = "access_admin"


def _first(model, **filters):
    """Return the first matching record for the provided filters."""
    return model.query.filter_by(**filters).first()


def _create_if_missing(model, defaults=None, **filters):
    """Create a record only when it does not already exist."""
    existing = _first(model, **filters)
    if existing is not None:
        return existing

    payload = dict(filters)
    if defaults:
        payload.update(defaults)
    record = model(**payload)
    db.session.add(record)
    return record


def _normalize_environment_host_inventory(data):
    """Expand grouped environment-host inventory into flat hosts and mappings."""
    inventory_groups = data.get("environment_host_inventory") or []
    if not inventory_groups:
        return (
            data.get("hosts") or [],
            data.get("environment_host_mappings") or [],
        )

    hosts = list(data.get("hosts") or [])
    mappings = []
    seen_hosts = {
        (
            (host.get("hostname") or "").strip(),
            (host.get("ip_address") or "").strip(),
        )
        for host in hosts
    }

    for group_index, group in enumerate(inventory_groups, start=1):
        raw_environments = group.get("environments") or []
        environment_entries = []
        for env in raw_environments:
            env_id = (env.get("env_id") or "").strip()
            if not env_id:
                raise ValueError(
                    "Inventory group #{} has an environment entry without env_id.".format(
                        group_index
                    )
                )
            environment_entries.append(
                {
                    "env_id": env_id,
                    "deployment_user": (env.get("deployment_user") or "").strip() or None,
                    "deployment_password": (env.get("deployment_password") or "").strip() or None,
                }
            )

        env_ids = group.get("env_ids") or []
        single_env_id = (group.get("env_id") or "").strip()
        if single_env_id:
            env_ids = env_ids + [single_env_id]
        env_ids = [env_id for env_id in env_ids if (env_id or "").strip()]
        env_type = (group.get("env_type") or "").strip().upper()
        default_user = (group.get("deployment_user") or "").strip() or None
        default_password = (group.get("deployment_password") or "").strip() or None
        group_mappings = group.get("mappings") or []

        if not environment_entries:
            environment_entries = [
                {
                    "env_id": env_id,
                    "deployment_user": default_user,
                    "deployment_password": default_password,
                }
                for env_id in env_ids
            ]

        if not environment_entries:
            raise ValueError(
                "Inventory group #{} must include environments, env_id, or env_ids.".format(group_index)
            )
        if not env_type:
            raise ValueError(
                "Inventory group #{} must include env_type.".format(group_index)
            )

        for mapping_index, mapping in enumerate(group_mappings, start=1):
            hostname = (mapping.get("hostname") or "").strip()
            ip_address = (mapping.get("ip_address") or "").strip()
            server_type_key = (mapping.get("server_type_key") or "").strip()
            host_domain = (mapping.get("domain") or "").strip() or None
            host_description = (mapping.get("description") or "").strip() or None

            if not hostname or not ip_address or not server_type_key:
                raise ValueError(
                    "Inventory group #{} mapping #{} must include server_type_key, hostname, and ip_address.".format(
                        group_index,
                        mapping_index,
                    )
                )

            host_key = (hostname, ip_address)
            if host_key not in seen_hosts:
                hosts.append(
                    {
                        "hostname": hostname,
                        "ip_address": ip_address,
                        "domain": host_domain,
                        "description": host_description,
                    }
                )
                seen_hosts.add(host_key)

            mapping_user = (mapping.get("deployment_user") or "").strip() or None
            mapping_password = (mapping.get("deployment_password") or "").strip() or None

            for environment_entry in environment_entries:
                mappings.append(
                    {
                        "env_id": environment_entry["env_id"],
                        "env_type": env_type,
                        "server_type_key": server_type_key,
                        "hostname": hostname,
                        "ip_address": ip_address,
                        "deployment_user": mapping_user or environment_entry["deployment_user"],
                        "deployment_password": mapping_password or environment_entry["deployment_password"],
                    }
                )

    return hosts, mappings


def load_host_seed_data():
    """Load default seed data from JSON config."""
    if not SEED_HOSTS_CONFIG_PATH.exists():
        return {
            "teams": [],
            "environments": [],
            "users": [],
            "server_types": [],
            "hosts": [],
            "environment_host_mappings": [],
            "component_builds": [],
        }

    with SEED_HOSTS_CONFIG_PATH.open("r", encoding="utf-8-sig") as seed_file:
        data = json.load(seed_file)

    normalized_hosts, normalized_mappings = _normalize_environment_host_inventory(data)

    for index, mapping in enumerate(normalized_mappings, start=1):
        if not (mapping.get("ip_address") or "").strip():
            raise ValueError(
                "Seed mapping #{} for hostname '{}' must include ip_address.".format(
                    index,
                    mapping.get("hostname") or "",
                )
            )

    return {
        "teams": data.get("teams") or [],
        "environments": data.get("environments") or [],
        "users": data.get("users") or [],
        "server_types": data.get("server_types") or [],
        "hosts": normalized_hosts,
        "environment_host_mappings": normalized_mappings,
        "component_builds": data.get("component_builds") or [],
    }


def _seeders():
    """Return the ordered set of seeder callables."""
    return (
        seed_default_roles,
        seed_default_environments,
        seed_default_teams,
        seed_default_users,
        seed_default_team_memberships,
        seed_default_hosts,
        seed_default_server_types,
        seed_default_environment_host_mappings,
        seed_default_component_builds,
    )


def _resolve_seed_host(host_data):
    """Resolve a seeded host record by hostname and IP address."""
    hostname = host_data["hostname"]
    ip_address = host_data.get("ip_address")
    return _first(Host, hostname=hostname, ip_address=ip_address)


def _seed_team_membership(user, team, role, team_lead=False):
    """Ensure a single user-to-team membership exists with the expected role."""
    if user is None or team is None:
        return
    membership = _create_if_missing(
        TeamMember,
        user_id=user.user_id,
        team_id=team.team_id,
        defaults={"role": role, "team_lead": team_lead},
    )
    membership.role = role
    membership.team_lead = bool(team_lead)


def _seed_access_admin_memberships():
    """Ensure admin users belong to the dedicated access-admin team."""
    access_admin_team = _first(Team, team_name=ACCESS_ADMIN_TEAM_NAME)
    if access_admin_team is None:
        return

    for admin_user in User.query.filter_by(role="admin").all():
        _seed_team_membership(admin_user, access_admin_team, admin_user.role)


def init_db():
    """Create the schema and seed bootstrap data for a fresh initial version."""
    db.create_all()
    if should_seed_default_data():
        seed_all_default_data()
        return
    seed_default_roles()


def has_bootstrap_seed_data():
    """Return whether bootstrap-managed operational records already exist."""
    return any(model.query.first() is not None for model in BOOTSTRAP_SEED_MODELS)


def should_seed_default_data():
    """Return whether JSON seed data should be applied during startup."""
    if not has_app_context():
        return False
    if not current_app.config.get("SEED_BOOTSTRAP_ONLY", True):
        return True
    return not has_bootstrap_seed_data()


def get_seed_runtime_summary():
    """Describe how bootstrap seed data is being treated at runtime."""
    bootstrap_only = bool(
        current_app.config.get("SEED_BOOTSTRAP_ONLY", True)
    ) if has_app_context() else True
    has_data = has_bootstrap_seed_data() if has_app_context() else False
    return {
        "config_path": str(SEED_HOSTS_CONFIG_PATH),
        "bootstrap_only": bootstrap_only,
        "has_operational_data": has_data,
        "seed_applied_on_startup": (not bootstrap_only or not has_data),
    }


def seed_all_default_data():
    """Seed all default application data."""
    for seeder in _seeders():
        seeder()


def seed_default_environments():
    """Seed default environment configurations."""
    seed_data = load_host_seed_data()
    for environment_data in seed_data["environments"]:
        env_id = environment_data["env_id"]
        env_type = environment_data["env_type"]
        domain = (environment_data.get("domain") or "").strip().lower() or None
        _create_if_missing(
            Environment,
            env_id=env_id,
            defaults={"env_type": env_type, "domain": domain},
        )
        environment = _first(Environment, env_id=env_id)
        if environment is not None:
            environment.env_type = env_type
            environment.domain = domain
    db.session.commit()


def seed_default_roles():
    """Seed default application roles."""
    for role_data in DEFAULT_ROLES:
        _create_if_missing(
            Role,
            role_name=role_data["role_name"],
            defaults={
                "description": role_data["description"],
                "is_active": True,
            },
        )
    db.session.commit()


def seed_default_teams():
    """Seed default teams used by access control and registration."""
    seed_data = load_host_seed_data()
    for team_name in seed_data["teams"]:
        _create_if_missing(Team, team_name=team_name)
    db.session.commit()


def seed_default_users():
    """Seed default user accounts."""
    seed_data = load_host_seed_data()
    for user_data in seed_data["users"]:
        _create_if_missing(
            User,
            user_id=user_data["user_id"],
            defaults={
                "email_id": user_data["email_id"],
                "name": user_data["name"],
                "password_hash": generate_password_hash(user_data["password"]),
                "role": user_data["role"],
            },
        )
    db.session.commit()


def seed_default_team_memberships():
    """Ensure seeded users have at least one team membership."""
    seed_data = load_host_seed_data()
    for user_data in seed_data["users"]:
        user = _first(User, user_id=user_data["user_id"])
        team = _first(Team, team_name=user_data["team"])
        _seed_team_membership(
            user,
            team,
            user_data["role"],
            team_lead=bool(user_data.get("team_lead", 0)),
        )

    _seed_access_admin_memberships()
    db.session.commit()


def seed_default_hosts():
    """Seed default host configurations."""
    seed_data = load_host_seed_data()
    for host_data in seed_data["hosts"]:
        _create_if_missing(
            Host,
            hostname=host_data["hostname"],
            ip_address=host_data.get("ip_address"),
            defaults={
                "domain": host_data.get("domain"),
                "description": host_data["description"],
            },
        )
    db.session.commit()


def seed_default_server_types():
    """Seed default server type configurations."""
    seed_data = load_host_seed_data()
    for server_data in seed_data["server_types"]:
        _create_if_missing(
            ServerType,
            server_type_key=server_data["server_type_key"],
            target_key=server_data["target_key"],
        )
    db.session.commit()


def seed_default_environment_host_mappings():
    """Seed default environment-to-host mappings."""
    seed_data = load_host_seed_data()
    for mapping_data in seed_data["environment_host_mappings"]:
        env_id = mapping_data.get("env_id")
        env = _first(Environment, env_id=env_id) if env_id else None
        server_type = _first(ServerType, server_type_key=mapping_data["server_type_key"])
        host = _resolve_seed_host(mapping_data)
        if env is None or server_type is None or host is None:
            continue

        lookup = {
            "env_id": env.env_id,
            "env_type": mapping_data.get("env_type") or env.env_type,
            "server_type_id": server_type.server_type_id,
        }

        existing = _first(EnvironmentHostMapping, **lookup)
        if existing is None:
            db.session.add(
                EnvironmentHostMapping(
                    env_id=lookup["env_id"],
                    env_type=lookup["env_type"],
                    server_type_id=server_type.server_type_id,
                    host_id=host.host_id,
                    deployment_user=mapping_data["deployment_user"],
                    deployment_password=mapping_data["deployment_password"],
                )
            )
    db.session.commit()


def seed_default_component_builds():
    """Seed default component build catalog entries."""
    seed_data = load_host_seed_data()
    for build_data in seed_data["component_builds"]:
        target_key = (build_data.get("target_key") or "").strip().upper()
        version = (build_data.get("version") or "").strip()
        if not target_key or not version:
            continue

        raw_build_name = (build_data.get("build_name") or "").strip()
        target_definition = get_target_definition(target_key) or {}
        packages = target_definition.get("packages") or {}
        if not packages:
            continue

        if target_key == "TOOLS":
            selected_package_sets = (
                [[raw_build_name]]
                if raw_build_name else
                [[package_key] for package_key in packages.keys()]
            )
        else:
            selected_package_sets = [list(packages.keys())]

        for selected_package_keys in selected_package_sets:
            package_entries = build_package_entries(
                target_key,
                target_definition=target_definition,
                selected_package_keys=selected_package_keys,
                build_name=raw_build_name,
                build_metadata=build_data.get("build_metadata"),
            )
            build_name = canonical_build_name(
                target_key,
                selected_package_keys=[entry.get("package_key") for entry in package_entries],
                explicit_name=raw_build_name,
                target_definition=target_definition,
            )

            _create_if_missing(
                ComponentBuild,
                target_key=target_key,
                build_name=build_name,
                version=version,
            )
    db.session.commit()

