"""Database initialization and seeding functions."""

import json
from pathlib import Path

from flask import current_app, has_app_context
from werkzeug.security import generate_password_hash

from .constants import (
    DEFAULT_ENVIRONMENTS,
    DEFAULT_SERVER_TYPES,
    DEFAULT_USERS,
    VALID_TEAMS,
)
from .models import (
    ComponentBuild,
    CurrentDeploymentState,
    Deployment,
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

RESET_DELETE_ORDER = [
    CurrentDeploymentState,
    Deployment,
    DeploymentRequest,
    EnvironmentBooking,
    ComponentBuild,
    EnvironmentHostMapping,
    ServerType,
    Host,
    TeamMember,
    User,
    Role,
    Team,
    Environment,
]

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


def load_host_seed_data():
    """Load seed-only host data from JSON to keep it separate from runtime constants."""
    if not SEED_HOSTS_CONFIG_PATH.exists():
        return {"hosts": [], "environment_host_mappings": []}

    with SEED_HOSTS_CONFIG_PATH.open("r", encoding="utf-8") as seed_file:
        data = json.load(seed_file)

    for index, mapping in enumerate(data.get("environment_host_mappings") or [], start=1):
        if not (mapping.get("ip_address") or "").strip():
            raise ValueError(
                "Seed mapping #{} for hostname '{}' must include ip_address.".format(
                    index,
                    mapping.get("hostname") or "",
                )
            )

    return {
        "hosts": data.get("hosts") or [],
        "environment_host_mappings": data.get("environment_host_mappings") or [],
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
    """Create the current schema and load default seed data."""
    db.create_all()
    if should_reset_seed_data():
        reset_all_table_data()
        return
    seed_all_default_data()


def should_reset_seed_data():
    """Return whether startup should rebuild a fresh default dataset."""
    if not has_app_context():
        return False
    return bool(current_app.config.get("RESET_DB_ON_INIT", False))


def seed_all_default_data():
    """Seed all default application data."""
    for seeder in _seeders():
        seeder()


def reset_all_table_data():
    """Delete all application data and rebuild the default seed set."""
    for model in RESET_DELETE_ORDER:
        db.session.query(model).delete()
    db.session.commit()
    seed_all_default_data()


def seed_default_environments():
    """Seed default environment configurations."""
    for env_id, env_type in DEFAULT_ENVIRONMENTS:
        _create_if_missing(
            Environment,
            env_id=env_id,
            defaults={"env_type": env_type},
        )
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
    for team_name in VALID_TEAMS:
        _create_if_missing(Team, team_name=team_name)
    db.session.commit()


def seed_default_users():
    """Seed default user accounts."""
    for user_data in DEFAULT_USERS:
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
    for user_data in DEFAULT_USERS:
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
    for server_data in DEFAULT_SERVER_TYPES:
        _create_if_missing(
            ServerType,
            server_type_key=server_data["server_type_key"],
            target_type=server_data["target_type"],
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
        if server_type is None or host is None:
            continue

        env_type = mapping_data.get("env_type") or (env.env_type if env is not None else None)
        is_shared = bool(mapping_data.get("is_shared", False))
        if not is_shared and env is None:
            continue

        lookup = {
            "env_type": env_type,
            "is_shared": is_shared,
            "server_type_id": server_type.server_type_id,
        }
        if is_shared:
            lookup["env_id"] = None
        else:
            lookup["env_id"] = env.env_id

        existing = _first(EnvironmentHostMapping, **lookup)
        if existing is None:
            db.session.add(
                EnvironmentHostMapping(
                    env_id=lookup["env_id"],
                    env_type=env_type,
                    server_type_id=server_type.server_type_id,
                    host_id=host.host_id,
                    is_shared=is_shared,
                    deployment_user=mapping_data["deployment_user"],
                    deployment_password=mapping_data["deployment_password"],
                )
            )
    db.session.commit()
