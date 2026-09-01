"""Database initialization and seeding functions."""

import json
from functools import lru_cache
from pathlib import Path

from flask import current_app, has_app_context

from .component_build_catalog import (
    build_package_entries,
    canonical_build_name,
)
from .domain.deployment_targets import get_target_definition
from .password_utils import hash_password
from .models import (
    ComponentBuild,
    Environment,
    EnvironmentHostMapping,
    Host,
    PayUi,
    Role,
    ServerType,
    Team,
    TeamMember,
    TCSDeploymentMode,
    TcsService,
    User,
    db,
)

SEED_GUARD_MODELS = (
    Team,
    User,
    TCSDeploymentMode,
    TcsService,
    ComponentBuild,
)

DEFAULT_ROLES = [
    {"role_name": "user", "description": "Standard user access"},
    {"role_name": "admin", "description": "Administrator access"},
]

SEED_CONFIG_FALLBACK_PATH = (
    Path(__file__).resolve().parent.parent / "configs" / "default_seed_data.json"
)
ACCESS_ADMIN_TEAM_NAME = "access_admin"

EMPTY_SEED_DATA = {
    "roles": [],
    "teams": [],
    "environments": [],
    "users": [],
    "deployment_modes": [],
    "tcs_services": [],
    "server_types": [],
    "hosts": [],
    "environment_host_mappings": [],
    "pay_ui": [],
    "component_builds": [],
}


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


def _normalize_seed_hosts(hosts, mappings):
    """Validate seeded hosts and mappings for the current JSON structure."""
    normalized_hosts = []
    hosts_by_id = {}

    for index, host in enumerate(hosts, start=1):
        normalized_host = dict(host)
        host_id = (normalized_host.get("host_id") or "").strip() or None
        if not host_id:
            raise ValueError("Seed host #{} must include host_id.".format(index))
        if host_id in hosts_by_id:
            raise ValueError(
                "Seed host #{} uses duplicate host_id '{}'.".format(
                    index,
                    host_id,
                )
            )
        normalized_host["host_id"] = host_id
        hosts_by_id[host_id] = normalized_host
        normalized_hosts.append(normalized_host)

    normalized_mappings = []
    for index, mapping in enumerate(mappings, start=1):
        normalized_mapping = dict(mapping)
        host_id = (normalized_mapping.get("host_id") or "").strip() or None
        if not host_id:
            raise ValueError("Seed mapping #{} must include host_id.".format(index))
        host = hosts_by_id.get(host_id)
        if host is None:
            raise ValueError(
                "Seed mapping #{} references unknown host_id '{}'.".format(
                    index,
                    host_id,
                )
            )
        normalized_mapping["host_id"] = host_id
        normalized_mapping["hostname"] = host.get("hostname")
        normalized_mapping["ip_address"] = host.get("ip_address")
        normalized_mappings.append(normalized_mapping)

    return normalized_hosts, normalized_mappings


def _seed_config_path():
    configured_path = None
    if has_app_context():
        configured_path = current_app.config.get("SEED_DATA_PATH")
    resolved_path = configured_path or str(SEED_CONFIG_FALLBACK_PATH)
    return Path(resolved_path)


@lru_cache(maxsize=4)
def _load_seed_data_from_path(seed_path_value):
    seed_path = Path(seed_path_value)
    if not seed_path.exists():
        return dict(EMPTY_SEED_DATA)

    with seed_path.open("r", encoding="utf-8-sig") as seed_file:
        data = json.load(seed_file)

    normalized_hosts, normalized_mappings = _normalize_seed_hosts(
        data.get("hosts") or [],
        data.get("environment_host_mappings") or [],
    )

    for index, mapping in enumerate(normalized_mappings, start=1):
        if not (mapping.get("ip_address") or "").strip():
            raise ValueError(
                "Seed mapping #{} for hostname '{}' must include ip_address.".format(
                    index,
                    mapping.get("hostname") or "",
                )
            )

    return {
        "roles": data.get("roles") or [],
        "teams": data.get("teams") or [],
        "environments": data.get("environments") or [],
        "users": data.get("users") or [],
        "deployment_modes": data.get("deployment_modes") or [],
        "tcs_services": data.get("tcs_services") or [],
        "server_types": data.get("server_types") or [],
        "hosts": normalized_hosts,
        "environment_host_mappings": normalized_mappings,
        "pay_ui": data.get("pay_ui") or [],
        "component_builds": data.get("component_builds") or [],
    }


def load_seed_data():
    """Load the single default seed data source used by startup seeding."""
    return _load_seed_data_from_path(str(_seed_config_path().resolve()))


def load_host_seed_data():
    """Backward-compatible alias for the unified seed data loader."""
    return load_seed_data()


def _seeders():
    """Return the ordered set of seeder callables."""
    return (
        seed_default_roles,
        seed_default_teams,
        seed_default_users,
        seed_default_team_memberships,
        seed_default_deployment_modes,
        seed_default_tcs_services,
        seed_default_environments,
        seed_default_hosts,
        seed_default_server_types,
        seed_default_environment_host_mappings,
        seed_default_pay_ui,
        seed_default_component_builds,
    )


def _resolve_seed_host(host_data):
    """Resolve a seeded host record by host_id."""
    host_id = (host_data.get("host_id") or "").strip()
    return _first(Host, host_id=host_id) if host_id else None


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


def upgrade_existing_schema():
    """Create the current schema for clean deployments."""
    db.create_all()


def seed_initial_data():
    """Seed first-time deployment data when the database is still bootstrap-empty."""
    if should_seed_default_data():
        seed_all_default_data()
        return
    seed_default_roles()


def init_db():
    """Ensure schema exists and apply first-start seed data."""
    upgrade_existing_schema()
    seed_initial_data()


def has_bootstrap_seed_data():
    """Return whether bootstrap-managed operational records already exist."""
    return any(model.query.first() is not None for model in SEED_GUARD_MODELS)


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
        "config_path": str(_seed_config_path()),
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
    seed_data = load_seed_data()
    for environment_data in seed_data["environments"]:
        env_id = environment_data["env_id"]
        env_type = environment_data["env_type"]
        team = (environment_data.get("team") or "").strip().lower() or None
        _create_if_missing(
            Environment,
            env_id=env_id,
            defaults={"env_type": env_type, "team": team},
        )
        environment = _first(Environment, env_id=env_id)
        if environment is not None:
            environment.env_type = env_type
            environment.team = team
    db.session.commit()


def seed_default_roles():
    """Seed default application roles."""
    seed_data = load_seed_data()
    role_entries = seed_data["roles"] or DEFAULT_ROLES
    for role_data in role_entries:
        role_name = (
            role_data.get("role_name")
            or role_data.get("id")
            or role_data.get("name")
            or ""
        ).strip().lower()
        if not role_name:
            continue
        _create_if_missing(
            Role,
            role_name=role_name,
            defaults={
                "description": role_data.get("description"),
                "is_active": role_data.get("is_active", True),
            },
        )
    db.session.commit()


def seed_default_teams():
    """Seed default teams used by access control and registration."""
    seed_data = load_seed_data()
    for team_data in seed_data["teams"]:
        if isinstance(team_data, str):
            team_name = team_data
            description = None
        else:
            team_name = team_data.get("team_name") or team_data.get("id") or team_data.get("name")
            description = team_data.get("description")
        team_name = (team_name or "").strip().lower()
        if not team_name:
            continue
        _create_if_missing(Team, team_name=team_name, defaults={"description": description})
    db.session.commit()


def seed_default_users():
    """Seed default user accounts."""
    seed_data = load_seed_data()
    for user_data in seed_data["users"]:
        _create_if_missing(
            User,
            user_id=user_data["user_id"],
            defaults={
                "email_id": user_data["email_id"],
                "name": user_data["name"],
                "hzn_hash": hash_password(user_data["password"]),
                "role": user_data["role"],
            },
        )
    db.session.commit()


def seed_default_team_memberships():
    """Ensure seeded users have at least one team membership."""
    seed_data = load_seed_data()
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


def seed_default_deployment_modes():
    """Seed default TCS deployment modes."""
    seed_data = load_seed_data()
    for mode_data in seed_data["deployment_modes"]:
        mode_id = (
            mode_data.get("tcs_deployment_mode_id")
            or mode_data.get("id")
            or ""
        ).strip()
        mode_name = (
            mode_data.get("mode_name")
            or mode_data.get("name")
            or mode_id
        ).strip()
        if not mode_id:
            continue
        _create_if_missing(
            TCSDeploymentMode,
            tcs_deployment_mode_id=mode_id,
            defaults={
                "mode_name": mode_name,
                "description": mode_data.get("description"),
                "is_active": mode_data.get("is_active", True),
            },
        )
    db.session.commit()


def seed_default_tcs_services():
    """Seed default TCS services."""
    seed_data = load_seed_data()
    logical_service_entries = [
        {
            "tcs_service_id": service_id,
            "service_name": service_id,
            "bit_id": bit_id,
            "is_active": True,
        }
        for service_id, bit_id in TcsService.LOGICAL_BIT_ID_MAP.items()
    ]
    for service_data in seed_data["tcs_services"]:
        logical_service_entries.append(service_data)
    for service_data in logical_service_entries:
        service_id = (
            service_data.get("tcs_service_id")
            or service_data.get("id")
            or ""
        ).strip()
        service_name = (
            service_data.get("service_name")
            or service_data.get("name")
            or service_id
        ).strip()
        if not service_id:
            continue
        _create_if_missing(
            TcsService,
            tcs_service_id=service_id,
            defaults={
                "service_name": service_name,
                "bit_id": TcsService.normalize_bit_id(service_data.get("bit_id")),
                "description": service_data.get("description"),
                "is_active": service_data.get("is_active", True),
            },
        )
    db.session.commit()


def seed_default_hosts():
    """Seed default host configurations."""
    seed_data = load_seed_data()
    for host_data in seed_data["hosts"]:
        _create_if_missing(
            Host,
            host_id=host_data["host_id"],
            defaults={
                "hostname": host_data["hostname"],
                "ip_address": host_data.get("ip_address"),
                "domain": host_data.get("domain"),
                "description": host_data["description"],
            },
        )
    db.session.commit()


def seed_default_server_types():
    """Seed default server type configurations."""
    seed_data = load_seed_data()
    for server_data in seed_data["server_types"]:
        _create_if_missing(
            ServerType,
            server_type_key=server_data["server_type_key"],
            target_key=server_data["target_key"],
        )
    db.session.commit()


def seed_default_environment_host_mappings():
    """Seed default environment-to-host mappings."""
    seed_data = load_seed_data()
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
                    deploy_user_hzn=mapping_data["deploy_user_hzn"],
                )
            )
    db.session.commit()


def seed_default_pay_ui():
    """Seed default Pay UI access links."""
    seed_data = load_seed_data()
    for pay_ui_data in seed_data["pay_ui"]:
        env_id = (pay_ui_data.get("env_id") or "").strip()
        if not env_id:
            continue

        environment = _first(Environment, env_id=env_id)
        if environment is None:
            continue

        record = _create_if_missing(PayUi, env_id=env_id)
        record.pay_url = (pay_ui_data.get("pay_url") or "").strip() or None
        record.pay_adm_url = (pay_ui_data.get("pay_adm_url") or "").strip() or None
    db.session.commit()


def seed_default_component_builds():
    """Seed default component build catalog entries."""
    seed_data = load_seed_data()
    for build_data in seed_data["component_builds"]:
        target_key = (build_data.get("target_key") or "").strip().upper()
        version = (build_data.get("version") or "").strip()
        if not target_key or not version:
            continue

        raw_build_name = (build_data.get("build_name") or "").strip()
        if raw_build_name:
            _create_if_missing(
                ComponentBuild,
                target_key=target_key,
                build_name=raw_build_name,
                version=version,
            )
            continue

        target_definition = get_target_definition(target_key) or {}
        packages = target_definition.get("packages") or {}
        if not packages:
            _create_if_missing(
                ComponentBuild,
                target_key=target_key,
                build_name=(target_key or "").strip().lower(),
                version=version,
            )
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
