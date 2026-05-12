"""
Database initialization and seeding functions.
"""

from flask import current_app, has_app_context
from werkzeug.security import generate_password_hash

from .models import (
    ComponentBuild,
    CurrentDeploymentState,
    DeploymentRequest,
    Deployment,
    Environment,
    EnvironmentBooking,
    EnvironmentHostMapping,
    Host,
    ServerRole,
    Team,
    TeamMember,
    User,
    db,
)
from .constants import (
    DEFAULT_ENVIRONMENTS,
    DEFAULT_HOSTS,
    DEFAULT_SERVER_ROLES,
    DEFAULT_ENVIRONMENT_HOST_MAPPINGS,
    DEFAULT_USERS,
    VALID_TEAMS,
)

DEFAULT_SEEDERS = (
    "seed_default_environments",
    "seed_default_teams",
    "seed_default_users",
    "seed_default_team_memberships",
    "seed_default_hosts",
    "seed_default_server_roles",
    "seed_default_environment_host_mappings",
)

RESET_DELETE_ORDER = [
    CurrentDeploymentState,
    Deployment,
    DeploymentRequest,
    EnvironmentBooking,
    ComponentBuild,
    EnvironmentHostMapping,
    ServerRole,
    Host,
    TeamMember,
    User,
    Team,
    Environment,
]


def init_db():
    """Create tables for the current model and seed default data."""
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
    for seeder_name in DEFAULT_SEEDERS:
        globals()[seeder_name]()


def reset_all_table_data():
    """Delete all application data and rebuild the default seed set."""
    for model in RESET_DELETE_ORDER:
        db.session.query(model).delete()

    db.session.commit()
    seed_all_default_data()


def seed_default_environments():
    """Seed default environment configurations."""
    for env_id, env_type in DEFAULT_ENVIRONMENTS:
        existing = Environment.query.filter_by(env_id=env_id).first()
        if existing is None:
            db.session.add(Environment(env_id=env_id, env_type=env_type))
    db.session.commit()


def seed_default_teams():
    """Seed default teams used by access control and registration."""
    for team_name in VALID_TEAMS:
        existing = Team.query.filter_by(team_name=team_name).first()
        if existing is None:
            db.session.add(Team(team_name=team_name))
    db.session.commit()


def seed_default_users():
    """Seed default user accounts."""
    for user_data in DEFAULT_USERS:
        existing = User.query.filter_by(user_id=user_data["user_id"]).first()
        if existing is None:
            user_kwargs = {
                "user_id": user_data["user_id"],
                "email_id": user_data["email_id"],
                "name": user_data["name"],
                "password_hash": generate_password_hash(user_data["password"]),
                "role": user_data["role"],
            }
            user = User(**user_kwargs)
            db.session.add(user)
    db.session.commit()


def seed_default_team_memberships():
    """Ensure seeded users have at least one team membership."""
    for user_data in DEFAULT_USERS:
        user = User.query.filter_by(user_id=user_data["user_id"]).first()
        team = Team.query.filter_by(team_name=user_data["team"]).first()
        if user is None or team is None:
            continue

        existing_membership = TeamMember.query.filter_by(
            user_id=user.user_id,
            team_id=team.team_id,
        ).first()
        if existing_membership is None:
            db.session.add(
                TeamMember(
                    user_id=user.user_id,
                    team_id=team.team_id,
                    role=user_data["role"],
                )
            )
    db.session.commit()


def seed_default_hosts():
    """Seed default host configurations."""
    for host_data in DEFAULT_HOSTS:
        existing = Host.query.filter_by(hostname=host_data["hostname"]).first()
        if existing is None:
            host_kwargs = {
                "hostname": host_data["hostname"],
                "ip_address": host_data["ip_address"],
                "description": host_data["description"],
            }
            if hasattr(Host, "domain"):
                host_kwargs["domain"] = host_data.get("domain")
            host = Host(**host_kwargs)
            db.session.add(host)
    db.session.commit()


def seed_default_server_roles():
    """Seed default server role configurations."""
    for server_data in DEFAULT_SERVER_ROLES:
        existing = ServerRole.query.filter_by(
            role_key=server_data["role_key"]
        ).first()
        if existing is None:
            server = ServerRole(
                role_key=server_data["role_key"],
                role_type=server_data["role_type"],
            )
            db.session.add(server)
    db.session.commit()


def seed_default_environment_host_mappings():
    """Seed default environment-to-host mappings."""
    for mapping_data in DEFAULT_ENVIRONMENT_HOST_MAPPINGS:
        env_id = mapping_data.get("env_id")
        env = Environment.query.filter_by(env_id=env_id).first() if env_id else None
        server_role = ServerRole.query.filter_by(
            role_key=mapping_data["server_role_key"]
        ).first()
        host = Host.query.filter_by(hostname=mapping_data["hostname"]).first()

        if server_role is None or host is None:
            continue

        is_shared = bool(mapping_data.get("is_shared", False))
        env_type = mapping_data.get("env_type") or (env.env_type if env is not None else None)

        if not is_shared and env is None:
            continue

        if is_shared:
            existing = EnvironmentHostMapping.query.filter_by(
                env_id=None,
                env_type=env_type,
                is_shared=True,
                server_role_id=server_role.server_role_id,
            ).first()
        else:
            existing = EnvironmentHostMapping.query.filter_by(
                env_id=env.env_id,
                server_role_id=server_role.server_role_id,
            ).first()
        if existing is None:
            mapping = EnvironmentHostMapping(
                env_id=env.env_id if env is not None else None,
                env_type=env_type,
                server_role_id=server_role.server_role_id,
                host_id=host.host_id,
                is_shared=is_shared,
                deployment_user=mapping_data["deployment_user"],
                deployment_password=mapping_data["deployment_password"],
            )
            db.session.add(mapping)
    db.session.commit()
