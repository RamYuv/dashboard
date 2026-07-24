"""Import legacy production data into the normalized application schema."""

from __future__ import annotations

from datetime import datetime
import json
import re
import sqlite3

from .models import (
    ComponentBuild,
    DefaultPassword,
    EnvBookingSystemSnapshot,
    TCSDeploymentMode,
    TcsService,
    DeploymentRequest,
    EmailDomain,
    Environment,
    EnvironmentBooking,
    EnvironmentHostMapping,
    Host,
    Orbit,
    PayUi,
    Role,
    ServerType,
    Team,
    TeamMember,
    User,
    db,
)


LEGACY_BOOKING_STATUS_MAP = {
    "inactive": "inactive",
    "scheduled": "scheduled",
    "active": "active",
    "expired": "expired",
    "completed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}

LEGACY_DEPLOYMENT_STATUS_MAP = {
    "inactive": "OPEN",
    "scheduled": "OPEN",
    "active": "READY_FOR_DEPLOYMENT",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "failed": "FAILED",
    "rejected": "REJECTED",
}

LEGACY_SERVER_TYPE_ALIASES = {
    "core": ("core", "TCS_APP"),
    "gateway": ("gateway", "TCS_APP"),
    "payapp": ("payapp", "PAYAPP"),
    "coredb": ("coredb", "DB"),
    "cordb": ("coredb", "DB"),
    "lgdb": ("lgdb", "DB"),
    "lg": ("lgdb", "DB"),
    "stage": ("stage", "ARTIFACT_REPO"),
    "tool_server": ("tool_server", "TOOLS"),
    "tools": ("tool_server", "TOOLS"),
}

LEGACY_SERVICE_BIT_ID_MAP = {
    "STL": "20",
    "NOW": "21",
}


def _get_first_present(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return []


def _sqlite_table_exists(connection, table_name):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _clean(value):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        try:
            text = bytes(value).decode("utf-8").strip()
        except UnicodeDecodeError:
            text = bytes(value).decode("latin-1").strip()
    else:
        text = str(value).strip()
    if not text:
        return None
    if text.upper() == "NULL":
        return None
    return text


def _lower(value):
    cleaned = _clean(value)
    return cleaned.lower() if cleaned else None


def _upper(value):
    cleaned = _clean(value)
    return cleaned.upper() if cleaned else None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    cleaned = _lower(value)
    return cleaned in {"1", "true", "t", "yes", "y"}


def _parse_datetime(value):
    cleaned = _clean(value)
    if cleaned is None:
        return None
    normalized = cleaned.replace("Z", "+00:00")
    candidates = [normalized, normalized.replace("T", " ")]

    if len(normalized) > 6 and normalized[-6] in ("+", "-") and normalized[-3] == ":":
        compact_offset = normalized[:-3] + normalized[-2:]
        candidates.append(compact_offset)
        candidates.append(compact_offset.replace("T", " "))

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    )

    for candidate in candidates:
        for date_format in formats:
            try:
                parsed = datetime.strptime(candidate, date_format)
                return parsed.replace(tzinfo=None)
            except ValueError:
                continue
    raise ValueError("Unsupported datetime value '{}'".format(cleaned))


def _guess_env_type(env_id):
    normalized = _upper(env_id) or ""
    prefix = re.split(r"[_0-9-]", normalized, maxsplit=1)[0]
    return prefix or "ENV"


def _derive_host_domain_from_env_id(env_id):
    return _guess_env_type(env_id)


def _resolve_or_create_role(role_name, description=None):
    normalized_name = _lower(role_name) or "user"
    role = Role.query.get(normalized_name)
    if role is None:
        role = Role(
            role_name=normalized_name,
            description=_clean(description),
            is_active=True,
        )
        db.session.add(role)
        return role, True

    if description and not role.description:
        role.description = _clean(description)
    return role, False


def _resolve_or_create_team(team_name, description=None):
    normalized_name = _lower(team_name)
    if not normalized_name:
        return None, False

    team = Team.query.filter_by(team_name=normalized_name).first()
    if team is None:
        team = Team(team_name=normalized_name, description=_clean(description))
        db.session.add(team)
        db.session.flush()
        return team, True

    if description and not team.description:
        team.description = _clean(description)
    return team, False


def _resolve_or_create_user(user_data):
    user_id = _clean(user_data.get("id") or user_data.get("user_id"))
    if not user_id:
        return None, False

    role_name = _lower(user_data.get("role")) or "user"
    team_name = _lower(user_data.get("team"))
    full_name = _clean(user_data.get("name"))
    email = _clean(user_data.get("email_id"))
    password_value = _clean(user_data.get("password"))

    user = User.query.get(user_id)
    created = False
    if user is None:
        user = User(
            user_id=user_id,
            email_id=email,
            name=full_name or user_id,
            hzn_hash=password_value or "legacy-imported-secret",
            role=role_name,
            is_active=True,
        )
        db.session.add(user)
        created = True
    else:
        user.email_id = email or user.email_id
        user.name = full_name or user.name
        user.role = role_name or user.role
        if password_value:
            user.hzn_hash = password_value

    team = None
    if team_name:
        team, _ = _resolve_or_create_team(team_name)
    if team is not None:
        membership = TeamMember.query.filter_by(
            user_id=user.user_id,
            team_id=team.team_id,
        ).first()
        if membership is None:
            membership = TeamMember(
                user_id=user.user_id,
                team_id=team.team_id,
                role=role_name,
                team_lead=_parse_bool(user_data.get("team_lead")),
            )
            db.session.add(membership)
        else:
            membership.role = role_name
            membership.team_lead = _parse_bool(user_data.get("team_lead"))
    return user, created


def _resolve_or_create_environment(environment_data):
    env_id = _upper(environment_data.get("id") or environment_data.get("env_id"))
    if not env_id:
        return None, False

    env_type = _upper(
        environment_data.get("environment_type")
        or environment_data.get("env_type")
        or _guess_env_type(env_id)
    )
    team_name = _lower(environment_data.get("domain") or environment_data.get("team"))
    if team_name:
        _resolve_or_create_team(team_name)

    environment = Environment.query.get(env_id)
    created = False
    if environment is None:
        environment = Environment(
            env_id=env_id,
            env_type=env_type,
            team=team_name,
            description=_clean(environment_data.get("name")),
            is_active=True,
        )
        db.session.add(environment)
        created = True
    else:
        environment.env_type = env_type or environment.env_type
        environment.team = team_name or environment.team
        if environment_data.get("name"):
            environment.description = _clean(environment_data.get("name"))
    return environment, created


def _resolve_server_type(usage_value):
    normalized_usage = _lower(usage_value) or "core"
    alias = LEGACY_SERVER_TYPE_ALIASES.get(normalized_usage)
    if alias is None:
        raise ValueError(
            "Unsupported legacy vm.tcs_usage '{}' . Add an explicit mapping before importing.".format(
                normalized_usage
            )
        )
    server_type_key, target_key = alias
    server_type = ServerType.query.filter_by(
        server_type_key=server_type_key,
        target_type=target_key,
    ).first()
    created = False
    if server_type is None:
        server_type = ServerType(
            server_type_key=server_type_key,
            target_type=target_key,
            description="Legacy import mapping for {}".format(normalized_usage),
        )
        db.session.add(server_type)
        db.session.flush()
        created = True
    return server_type, created


def _resolve_or_create_host(host_id, hostname, ip_address, domain, description):
    normalized_host_id = _clean(host_id)
    if not normalized_host_id:
        return None, False

    normalized_hostname = _clean(hostname) or normalized_host_id
    normalized_ip_address = _clean(ip_address)
    normalized_domain = _clean(domain)

    duplicate_host = Host.query.filter_by(
        hostname=normalized_hostname,
        ip_address=normalized_ip_address,
        domain=normalized_domain,
    ).first()

    host = Host.query.get(normalized_host_id)
    created = False
    if host is None and duplicate_host is not None:
        host = duplicate_host
    if host is None:
        host = Host(
            host_id=normalized_host_id,
            hostname=normalized_hostname,
            ip_address=normalized_ip_address,
            domain=normalized_domain,
            description=_clean(description),
            is_active=True,
        )
        db.session.add(host)
        created = True
    else:
        conflicting_host = None
        if host.host_id != normalized_host_id:
            conflicting_host = host
        elif (
            duplicate_host is not None and
            duplicate_host.host_id != host.host_id
        ):
            conflicting_host = duplicate_host

        if conflicting_host is not None:
            host = conflicting_host
        else:
            host.hostname = normalized_hostname or host.hostname
            host.ip_address = normalized_ip_address or host.ip_address
            host.domain = normalized_domain or host.domain
        if description:
            host.description = _clean(description)
    return host, created


def _resolve_or_create_environment_mapping(
    environment,
    server_type,
    host,
    deployment_user,
    deploy_user_hzn,
):
    if environment is None or server_type is None or host is None:
        return None, False

    mapping = EnvironmentHostMapping.query.filter_by(
        env_id=environment.env_id,
        server_type_id=server_type.server_type_id,
    ).first()
    created = False
    if mapping is None:
        mapping = EnvironmentHostMapping(
            env_id=environment.env_id,
            env_type=environment.env_type,
            server_type_id=server_type.server_type_id,
            host_id=host.host_id,
            deployment_user=_clean(deployment_user),
            deploy_user_hzn=_clean(deploy_user_hzn),
        )
        db.session.add(mapping)
        created = True
    else:
        mapping.env_type = environment.env_type
        mapping.host_id = host.host_id
        mapping.deployment_user = _clean(deployment_user) or mapping.deployment_user
        mapping.deploy_user_hzn = _clean(deploy_user_hzn) or mapping.deploy_user_hzn
    return mapping, created


def _resolve_or_create_component_build(version_data):
    version = _clean(version_data.get("id") or version_data.get("version"))
    if not version:
        return None, False

    build_name = _lower(version_data.get("build_name")) or "tcs_app"
    target_key = _upper(version_data.get("target_key")) or "TCS_APP"
    build = ComponentBuild.query.filter_by(
        target_key=target_key,
        build_name=build_name,
        version=version,
    ).first()
    created = False
    if build is None:
        build = ComponentBuild(
            target_key=target_key,
            build_name=build_name,
            version=version,
        )
        db.session.add(build)
        created = True
    return build, created


def _resolve_or_create_tcs_service_from_combo(service_combo):
    normalized_combo = _upper(service_combo)
    if not normalized_combo:
        return None

    normalized_combo = (
        TcsService.default_service_id_for_bit_id(normalized_combo)
        or normalized_combo
    )
    record = TcsService.query.get(normalized_combo)
    bit_id = (
        TcsService.default_bit_id_for_service_id(normalized_combo)
        or LEGACY_SERVICE_BIT_ID_MAP.get(normalized_combo)
        or TcsService.normalize_bit_id(service_combo)
    )
    if record is None:
        record = TcsService(
            tcs_service_id=normalized_combo,
            service_name=normalized_combo,
            bit_id=bit_id,
            is_active=True,
        )
        db.session.add(record)
        db.session.flush()
        return record

    if not record.service_name:
        record.service_name = normalized_combo
    if record.bit_id is None and bit_id is not None:
        record.bit_id = bit_id
    return record


def _resolve_or_create_tcs_deployment_mode_from_event(mode_id):
    normalized_mode_id = _clean(mode_id)
    if not normalized_mode_id:
        return None

    record = TCSDeploymentMode.query.get(normalized_mode_id)
    if record is None:
        record = TCSDeploymentMode(
            tcs_deployment_mode_id=normalized_mode_id,
            mode_name=normalized_mode_id,
            is_active=True,
        )
        db.session.add(record)
        db.session.flush()
    return record


def _resolve_booking_snapshot_service(event_data):
    service_combo = _clean(event_data.get("tcs_service_combo"))
    if service_combo:
        return _resolve_or_create_tcs_service_from_combo(service_combo)
    service_id = _clean(event_data.get("tcs_service_id"))
    if service_id:
        return _resolve_or_create_tcs_service_from_combo(service_id)
    return None


def _sync_booking_system_snapshots(booking, event_data):
    if booking is None:
        return

    service = _resolve_booking_snapshot_service(event_data)
    deployment_mode = _resolve_or_create_tcs_deployment_mode_from_event(
        event_data.get("testing_mode_id")
    )
    current_version = _clean(event_data.get("tcs_version_id"))

    mappings = (
        EnvironmentHostMapping.query.join(ServerType)
        .filter(EnvironmentHostMapping.env_id == booking.env_id)
        .filter(ServerType.target_type == "TCS_APP")
        .filter(ServerType.server_type_key.in_(["core", "gateway"]))
        .order_by(EnvironmentHostMapping.environment_host_mapping_id.asc())
        .all()
    )

    desired_mapping_ids = []
    for mapping in mappings:
        desired_mapping_ids.append(mapping.environment_host_mapping_id)
        snapshot = EnvBookingSystemSnapshot.query.filter_by(
            booking_id=booking.booking_id,
            environment_host_mapping_id=mapping.environment_host_mapping_id,
            target_key="TCS_APP",
            package_key=None,
            tcs_service_id=service.tcs_service_id if service is not None else None,
        ).first()
        if snapshot is None:
            snapshot = EnvBookingSystemSnapshot(
                booking_id=booking.booking_id,
                environment_host_mapping_id=mapping.environment_host_mapping_id,
                env_id=booking.env_id,
                host_id=mapping.host_id,
                server_type_id=mapping.server_type_id,
                target_key="TCS_APP",
                package_key=None,
                tcs_service_id=service.tcs_service_id if service is not None else None,
            )
            db.session.add(snapshot)

        snapshot.env_id = booking.env_id
        snapshot.host_id = mapping.host_id
        snapshot.server_type_id = mapping.server_type_id
        snapshot.tcs_service_id = service.tcs_service_id if service is not None else None
        snapshot.tcs_deployment_mode_id = (
            deployment_mode.tcs_deployment_mode_id if deployment_mode is not None else None
        )
        snapshot.current_version = current_version
        snapshot.package_name = None
        snapshot.source = "LEGACY_EVENT_IMPORT"
        snapshot.status = "CURRENT"
        snapshot.notes = "Migrated from legacy booking event."

    existing_snapshots = EnvBookingSystemSnapshot.query.filter_by(
        booking_id=booking.booking_id
    ).all()
    for snapshot in existing_snapshots:
        if snapshot.environment_host_mapping_id not in desired_mapping_ids:
            db.session.delete(snapshot)


def _resolve_or_create_default_password(default_password_data):
    password_id = _clean(default_password_data.get("id"))
    if not password_id:
        return None, False

    password_value = _clean(
        default_password_data.get("pwd")
        or default_password_data.get("password")
        or default_password_data.get("value")
    )
    if not password_value:
        return None, False

    record = DefaultPassword.query.get(password_id)
    created = False
    if record is None:
        record = DefaultPassword(
            default_password_id=password_id,
            password_value=password_value,
        )
        db.session.add(record)
        created = True
    else:
        record.password_value = password_value
    return record, created


def _resolve_or_create_email_domain(email_domain_data):
    domain_id = _clean(email_domain_data.get("id") or email_domain_data.get("domain"))
    if not domain_id:
        return None, False

    record = EmailDomain.query.get(domain_id)
    created = False
    if record is None:
        record = EmailDomain(email_domain_id=domain_id)
        db.session.add(record)
        created = True
    return record, created


def _resolve_or_create_orbit(orbit_data):
    orbit_id = _clean(orbit_data.get("id"))
    orb_value = _clean(orbit_data.get("orb"))
    if not orbit_id or not orb_value:
        return None, False

    record = Orbit.query.get(orbit_id)
    created = False
    if record is None:
        record = Orbit(
            orbit_id=orbit_id,
            orb_value=orb_value,
        )
        db.session.add(record)
        created = True
    else:
        record.orb_value = orb_value
    return record, created


def _resolve_or_create_pay_ui(pay_ui_data):
    env_id = _upper(pay_ui_data.get("id") or pay_ui_data.get("env_id"))
    if not env_id:
        return None, False

    if Environment.query.get(env_id) is None:
        _resolve_or_create_environment({"id": env_id})

    pay_url = _clean(pay_ui_data.get("pay_url"))
    pay_adm_url = _clean(
        pay_ui_data.get("admin_url") or pay_ui_data.get("pay_adm_url")
    )

    record = PayUi.query.get(env_id)
    created = False
    if record is None:
        record = PayUi(
            env_id=env_id,
            pay_url=pay_url,
            pay_adm_url=pay_adm_url,
        )
        db.session.add(record)
        created = True
    else:
        record.pay_url = pay_url or record.pay_url
        record.pay_adm_url = pay_adm_url or record.pay_adm_url
    return record, created


def _normalize_service_types(event_data):
    combo_value = _clean(event_data.get("tcs_service_combo"))
    if combo_value:
        normalized_combo = _upper(combo_value)
        logical_service_id = TcsService.default_service_id_for_bit_id(normalized_combo)
        if logical_service_id:
            return [logical_service_id]
        return [
            (
                TcsService.default_service_id_for_bit_id(token.strip().upper())
                or token.strip().upper()
            )
            for token in re.split(r"[|,;/]+", combo_value)
            if token.strip()
        ]
    service_value = _clean(event_data.get("tcs_service_id"))
    if not service_value:
        return []
    normalized_service_value = service_value.upper()
    return [TcsService.default_service_id_for_bit_id(normalized_service_value) or normalized_service_value]


def _build_legacy_metadata_description(event_data):
    lines = []
    title = _clean(event_data.get("title"))
    if title:
        lines.append(title)

    operational_mode = _clean(
        event_data.get("operational_mode_id") or event_data.get("oprational_mode_id")
    )

    metadata_pairs = [
        ("Legacy testing mode", _clean(event_data.get("testing_mode_id"))),
        ("Legacy operational mode", operational_mode),
        ("Legacy version", _clean(event_data.get("tcs_version_id"))),
        ("Legacy service", _clean(event_data.get("tcs_service_id"))),
        ("Legacy service combo", _clean(event_data.get("tcs_service_combo"))),
        ("Legacy all-day flag", str(_parse_bool(event_data.get("allDay")))),
    ]
    metadata_lines = [
        "{}: {}".format(label, value)
        for label, value in metadata_pairs
        if value is not None
    ]
    if metadata_lines:
        if lines:
            lines.append("")
        lines.append("Imported legacy metadata:")
        lines.extend(metadata_lines)
    return "\n".join(lines) or None


def _resolve_tcs_app_mapping_ids(env_id):
    mappings = (
        EnvironmentHostMapping.query.join(ServerType)
        .filter(EnvironmentHostMapping.env_id == env_id)
        .filter(ServerType.target_type == "TCS_APP")
        .order_by(EnvironmentHostMapping.environment_host_mapping_id.asc())
        .all()
    )
    return [mapping.environment_host_mapping_id for mapping in mappings]


def _import_booking_event(event_data):
    booking_id = _clean(event_data.get("id"))
    env_id = _upper(event_data.get("environment_id"))
    requested_by = _clean(event_data.get("user_id"))
    if not booking_id or not env_id or not requested_by:
        return False

    if Environment.query.get(env_id) is None:
        _resolve_or_create_environment({"id": env_id})
    if User.query.get(requested_by) is None:
        _resolve_or_create_user({"id": requested_by, "team": "support", "role": "user"})

    booking = EnvironmentBooking.query.get(booking_id)
    created = False
    if booking is None:
        booking = EnvironmentBooking(
            booking_id=booking_id,
            env_id=env_id,
            requested_by=requested_by,
            booking_type="RESERVATION",
        )
        db.session.add(booking)
        created = True

    booking.start_time = _parse_datetime(event_data.get("start"))
    booking.end_time = _parse_datetime(event_data.get("end"))
    booking.status = LEGACY_BOOKING_STATUS_MAP.get(
        _lower(event_data.get("booking_status")),
        "scheduled",
    )
    booking.description = _build_legacy_metadata_description(event_data)
    booking.user_timezone = "UTC"
    _sync_booking_system_snapshots(booking, event_data)
    return created


def _import_deployment_event(event_data):
    request_id = _clean(event_data.get("id"))
    env_id = _upper(event_data.get("environment_id"))
    requested_by = _clean(event_data.get("user_id"))
    if not request_id or not env_id or not requested_by:
        return False

    environment = Environment.query.get(env_id)
    if environment is None:
        environment, _ = _resolve_or_create_environment({"id": env_id})
    if User.query.get(requested_by) is None:
        _resolve_or_create_user({"id": requested_by, "team": "support", "role": "user"})

    version = _clean(event_data.get("tcs_version_id")) or "legacy-unknown"
    build, _ = _resolve_or_create_component_build(
        {"id": version, "build_name": "tcs_app", "target_key": "TCS_APP"}
    )

    deployment_request = DeploymentRequest.query.get(request_id)
    created = False
    if deployment_request is None:
        deployment_request = DeploymentRequest(
            deployment_request_id=request_id,
            env_id=env_id,
            requested_by=requested_by,
            planned_start_time=_parse_datetime(event_data.get("start")),
            target_key="TCS_APP",
            requested_version=version,
            package_keys_raw="[]",
            selected_server_mapping_ids_raw="[]",
        )
        db.session.add(deployment_request)
        created = True

    deployment_request.requested_env_type = environment.env_type if environment else _guess_env_type(env_id)
    deployment_request.env_scope_type = "ENV"
    deployment_request.planned_start_time = _parse_datetime(event_data.get("start"))
    deployment_request.build_id = build.build_id if build is not None else None
    deployment_request.requested_version = version
    deployment_mode_id = _clean(event_data.get("testing_mode_id")) or None
    if deployment_mode_id and TCSDeploymentMode.query.get(deployment_mode_id) is None:
        db.session.add(
            TCSDeploymentMode(
                tcs_deployment_mode_id=deployment_mode_id,
                mode_name=deployment_mode_id,
                is_active=True,
            )
        )
    deployment_request.tcs_deployment_mode_id = deployment_mode_id
    deployment_request.description = _clean(event_data.get("title"))
    deployment_request.remarks = _build_legacy_metadata_description(event_data)
    deployment_request.status = LEGACY_DEPLOYMENT_STATUS_MAP.get(
        _lower(event_data.get("booking_status")),
        "OPEN",
    )
    deployment_request.selected_server_mapping_ids = _resolve_tcs_app_mapping_ids(env_id)
    service_ids = _normalize_service_types(event_data)
    for service_id in service_ids:
        if TcsService.query.get(service_id) is None:
            db.session.add(
                TcsService(
                    tcs_service_id=service_id,
                    service_name=service_id,
                    is_active=True,
                )
            )
    deployment_request.set_service_ids(service_ids)
    return created


def import_legacy_payload(payload, event_mode="booking", commit=True):
    """Import a structured legacy export payload into the current schema."""
    normalized_mode = (_clean(event_mode) or "booking").lower()
    if normalized_mode not in {"booking", "deployment", "both"}:
        raise ValueError("Unsupported event mode '{}'".format(event_mode))

    summary = {
        "roles_created": 0,
        "teams_created": 0,
        "users_created": 0,
        "default_passwords_created": 0,
        "email_domains_created": 0,
        "orbits_created": 0,
        "pay_ui_created": 0,
        "environments_created": 0,
        "hosts_created": 0,
        "server_types_created": 0,
        "environment_mappings_created": 0,
        "component_builds_created": 0,
        "bookings_created": 0,
        "deployment_requests_created": 0,
        "ignored_sections": [],
    }

    for role_data in _get_first_present(payload, "roles", "role"):
        _, created = _resolve_or_create_role(
            role_data.get("name") or role_data.get("id"),
            role_data.get("description"),
        )
        summary["roles_created"] += int(created)

    for team_data in _get_first_present(payload, "teams", "team"):
        _, created = _resolve_or_create_team(
            team_data.get("id") or team_data.get("name"),
            team_data.get("description"),
        )
        summary["teams_created"] += int(created)

    for user_data in _get_first_present(payload, "users", "tuser"):
        _, created = _resolve_or_create_user(user_data)
        summary["users_created"] += int(created)

    for default_password_data in _get_first_present(payload, "default_passwords", "default_pwd"):
        _, created = _resolve_or_create_default_password(default_password_data)
        summary["default_passwords_created"] += int(created)

    for email_domain_data in _get_first_present(payload, "email_domains", "email_domain"):
        _, created = _resolve_or_create_email_domain(email_domain_data)
        summary["email_domains_created"] += int(created)

    for orbit_data in _get_first_present(payload, "orbits", "orbit"):
        _, created = _resolve_or_create_orbit(orbit_data)
        summary["orbits_created"] += int(created)

    for environment_data in _get_first_present(payload, "environments", "environment"):
        _, created = _resolve_or_create_environment(environment_data)
        summary["environments_created"] += int(created)

    for pay_ui_data in _get_first_present(payload, "pay_vm", "pay_ui"):
        _, created = _resolve_or_create_pay_ui(pay_ui_data)
        summary["pay_ui_created"] += int(created)

    for version_data in _get_first_present(payload, "tcs_versions", "tcs_version"):
        _, created = _resolve_or_create_component_build(version_data)
        summary["component_builds_created"] += int(created)

    for vm_data in _get_first_present(payload, "vms", "vm"):
        environment, environment_created = _resolve_or_create_environment(
            {
                "id": vm_data.get("env_id"),
                "environment_type": _guess_env_type(vm_data.get("env_id")),
            }
        )
        summary["environments_created"] += int(environment_created)

        server_type, server_type_created = _resolve_server_type(vm_data.get("tcs_usage"))
        summary["server_types_created"] += int(server_type_created)

        host_domain = _derive_host_domain_from_env_id(vm_data.get("env_id"))

        host, host_created = _resolve_or_create_host(
            vm_data.get("id"),
            vm_data.get("hostname"),
            vm_data.get("ip_address"),
            host_domain,
            "Legacy VM import ({})".format(_clean(vm_data.get("tcs_usage")) or "unknown"),
        )
        summary["hosts_created"] += int(host_created)

        _, mapping_created = _resolve_or_create_environment_mapping(
            environment,
            server_type,
            host,
            vm_data.get("usr"),
            vm_data.get("hzn"),
        )
        summary["environment_mappings_created"] += int(mapping_created)

        db_host_specs = [
            (
                vm_data.get("core_db_hostname") or vm_data.get("db_instance_id"),
                vm_data.get("core_db_hostname") or vm_data.get("db_instance_id"),
                vm_data.get("core_db_ip_address"),
                "coredb",
            ),
            (
                vm_data.get("lg_db_hostname"),
                vm_data.get("lg_db_hostname"),
                vm_data.get("lg_db_ip_address"),
                "lgdb",
            ),
        ]
        for derived_host_id, derived_hostname, derived_ip, derived_usage in db_host_specs:
            if _clean(derived_hostname) is None and _clean(derived_ip) is None:
                continue
            derived_server_type, derived_server_type_created = _resolve_server_type(derived_usage)
            summary["server_types_created"] += int(derived_server_type_created)
            derived_host, derived_host_created = _resolve_or_create_host(
                derived_host_id,
                derived_hostname or derived_host_id,
                derived_ip,
                host_domain,
                "Legacy derived DB host ({})".format(derived_usage),
            )
            summary["hosts_created"] += int(derived_host_created)
            _, derived_mapping_created = _resolve_or_create_environment_mapping(
                environment,
                derived_server_type,
                derived_host,
                vm_data.get("db_instance_id") or vm_data.get("usr"),
                vm_data.get("hzn"),
            )
            summary["environment_mappings_created"] += int(derived_mapping_created)

    for event_data in _get_first_present(payload, "events", "event"):
        if normalized_mode in {"booking", "both"}:
            summary["bookings_created"] += int(_import_booking_event(event_data))
        if normalized_mode in {"deployment", "both"}:
            summary["deployment_requests_created"] += int(_import_deployment_event(event_data))

    ignored_sections = [
        key
        for key in (
            "environment_types",
            "environment_type",
            "testing_modes",
            "testing_mode",
            "operational_modes",
            "operational_mode",
            "oprational_mode",
            "tcs_services",
            "tcs_service",
            "tcs_service_combos",
            "tcs_service_combo",
        )
        if payload.get(key)
    ]
    summary["ignored_sections"] = ignored_sections

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return summary


def import_legacy_sensitive_values_from_sqlite(db_path, commit=True):
    """Import sensitive legacy values directly from SQLite without using JSON."""
    summary = {
        "users_updated": 0,
        "orbits_updated": 0,
        "environment_mappings_updated": 0,
        "missing_users": [],
        "missing_mappings": [],
    }

    connection = sqlite3.connect(str(db_path))
    try:
        if _sqlite_table_exists(connection, "tuser"):
            for user_id, password_value in connection.execute("SELECT id, password FROM tuser").fetchall():
                normalized_user_id = _clean(user_id)
                normalized_password = _clean(password_value)
                if not normalized_user_id or normalized_password is None:
                    continue
                user = User.query.get(normalized_user_id)
                if user is None:
                    summary["missing_users"].append(normalized_user_id)
                    continue
                user.hzn_hash = normalized_password
                summary["users_updated"] += 1

        if _sqlite_table_exists(connection, "orbit"):
            for orbit_id, orbit_value in connection.execute("SELECT id, orb FROM orbit").fetchall():
                normalized_orbit_id = _clean(orbit_id)
                normalized_orbit_value = _clean(orbit_value)
                if not normalized_orbit_id or normalized_orbit_value is None:
                    continue
                orbit = Orbit.query.get(normalized_orbit_id)
                if orbit is None:
                    orbit = Orbit(orbit_id=normalized_orbit_id, orb_value=normalized_orbit_value)
                    db.session.add(orbit)
                else:
                    orbit.orb_value = normalized_orbit_value
                summary["orbits_updated"] += 1

        if _sqlite_table_exists(connection, "vm"):
            def _update_mapping_password(env_id, server_type, hzn_value, deployment_user=None):
                mapping = EnvironmentHostMapping.query.filter_by(
                    env_id=env_id,
                    server_type_id=server_type.server_type_id,
                ).first()
                if mapping is None:
                    summary["missing_mappings"].append(
                        "{}:{}".format(env_id, server_type.server_type_key)
                    )
                    return False

                mapping.deploy_user_hzn = hzn_value
                if _clean(deployment_user):
                    mapping.deployment_user = _clean(deployment_user)
                summary["environment_mappings_updated"] += 1
                return True

            vm_rows = connection.execute(
                "SELECT env_id, tcs_usage, hzn, usr, db_instance_id FROM vm"
            ).fetchall()
            for env_id, tcs_usage, hzn_value, usr_value, db_instance_id in vm_rows:
                normalized_env_id = _upper(env_id)
                normalized_hzn_value = _clean(hzn_value)
                if not normalized_env_id or normalized_hzn_value is None:
                    continue

                try:
                    server_type, _ = _resolve_server_type(tcs_usage)
                except ValueError:
                    summary["missing_mappings"].append(
                        "{}:{}".format(normalized_env_id, _clean(tcs_usage) or "unknown")
                    )
                    continue

                deployment_user = _clean(usr_value)
                if (
                    deployment_user is None and
                    server_type.server_type_key in {"coredb", "lgdb"} and
                    _clean(db_instance_id)
                ):
                    deployment_user = _clean(db_instance_id)

                _update_mapping_password(
                    normalized_env_id,
                    server_type,
                    normalized_hzn_value,
                    deployment_user=deployment_user,
                )

                derived_db_server_type_key = None
                derived_db_deployment_user = _clean(db_instance_id) or deployment_user
                if server_type.server_type_key == "core":
                    derived_db_server_type_key = "coredb"
                elif server_type.server_type_key == "gateway":
                    derived_db_server_type_key = "lgdb"

                if derived_db_server_type_key is not None:
                    derived_db_server_type, _ = _resolve_server_type(derived_db_server_type_key)
                    _update_mapping_password(
                        normalized_env_id,
                        derived_db_server_type,
                        normalized_hzn_value,
                        deployment_user=derived_db_deployment_user,
                    )

        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return summary
    finally:
        connection.close()


def load_legacy_payload_from_json(path):
    """Load a legacy export payload from a JSON file path."""
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)
