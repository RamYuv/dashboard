import json
import uuid
from datetime import datetime
from enum import Enum
from flask_sqlalchemy import SQLAlchemy

from .component_build_catalog import build_package_entries
from .constants import (
    BOOKING_LIFECYCLE_STATUS,
    BOOKING_MUTABLE_LIFECYCLE_STATUSES,
    BOOKING_STATUS,
    BOOKING_STATUS_ALIASES,
)

db = SQLAlchemy()


class ServerTypeKey(str, Enum):
    CORE = "core"
    GATEWAY = "gateway"
    COREDB = "coredb"
    LGDB = "lgdb"
    PAYAPP = "payapp"

    @classmethod
    def from_value(cls, value):
        normalized = (value or "").strip().lower()
        if not normalized:
            return None
        for item in cls:
            if item.value == normalized:
                return item
        return None


class PayUiAccessType(str, Enum):
    PAY_URL = "pay_url"
    PAY_ADMIN = "pay_admin"

    @classmethod
    def from_value(cls, value):
        normalized = (value or "").strip().lower()
        if not normalized:
            return None
        for item in cls:
            if item.value == normalized:
                return item
        return None

def generate_id(prefix):
    return "{}-{}".format(prefix, uuid.uuid4().hex[:12])


def format_datetime(value):
    if value is None:
        return None
    return value.isoformat() + "Z"


def parse_json_list(value):
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def json_dumps(value):
    return json.dumps(value or [])


def build_requester_display(user, fallback_user_id):
    """Return a consistent requester label for UI rendering."""
    user_id = (fallback_user_id or "").strip()
    if user is None:
        return user_id or None

    display_name = (user.user_id or "").strip() or (user.name or "").strip() or user_id
    team_label = user.team_names_display.strip() if user.team_names_display else ""
    if team_label:
        return "{} ({})".format(display_name, team_label)
    return display_name or user_id or None


# ==========================================================
# ROLE
# ==========================================================
class Role(db.Model):
    __tablename__ = "roles"

    role_name = db.Column(db.String(20), primary_key=True)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==========================================================
# USER
# ==========================================================
class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.String(50), primary_key=True)
    email_id = db.Column(db.String(100), unique=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    name = db.Column(db.String(100))
    hzn_hash = db.Column(db.String(255), nullable=False)

    # Self-registered accounts start as "user"; admins can promote them later.
    role = db.Column(db.String(20), nullable=False, default="user")
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    username = db.synonym("user_id")
    id = db.synonym("user_id")

    @classmethod
    def find_by_user_id(cls, user_id):
        normalized_user_id = (user_id or "").strip().lower()
        if not normalized_user_id:
            return None
        return cls.query.filter_by(user_id=normalized_user_id).first()

    @classmethod
    def find_by_username(cls, username):
        return cls.find_by_user_id(username)

    @classmethod
    def find_by_email(cls, email_id):
        normalized_email_id = (email_id or "").strip().lower()
        if not normalized_email_id:
            return None
        return cls.query.filter_by(email_id=normalized_email_id).first()

    @classmethod
    def ordered(cls):
        return cls.query.order_by(cls.user_id)

    @classmethod
    def active(cls):
        return cls.query.filter_by(is_active=True).order_by(cls.user_id)

    @classmethod
    def by_role(cls, role_name):
        normalized_role_name = (role_name or "").strip().lower()
        if not normalized_role_name:
            return cls.query.filter(db.text("1 = 0"))
        return cls.query.filter_by(role=normalized_role_name).order_by(cls.user_id)

    @classmethod
    def requiring_password_change(cls):
        return cls.query.filter_by(must_change_password=True).order_by(cls.user_id)

    @property
    def full_name(self):
        parts = [
            (self.first_name or "").strip(),
            (self.last_name or "").strip(),
        ]
        full_name = " ".join(part for part in parts if part)
        return full_name or (self.name or "").strip() or self.user_id

    @property
    def display_name(self):
        """Backward-compatible alias used by templates and serializers."""
        return self.full_name

    @property
    def normalized_role(self):
        return (self.role or "").strip().lower()

    @property
    def is_admin(self):
        return self.normalized_role == "admin"

    @property
    def team_names(self):
        names = []
        for membership in getattr(self, "team_memberships", []) or []:
            if membership.team and membership.team.team_name:
                names.append(membership.team.team_name)
        return names

    @property
    def normalized_team_names(self):
        return [
            (team_name or "").strip().lower()
            for team_name in self.team_names
            if (team_name or "").strip()
        ]

    @property
    def team_name(self):
        names = self.team_names
        return names[0] if names else None

    @property
    def team_names_display(self):
        return ", ".join(self.team_names)

    @property
    def is_team_lead(self):
        return any(
            bool(getattr(membership, "team_lead", False))
            for membership in getattr(self, "team_memberships", []) or []
        )

    def has_team(self, team_name):
        normalized_team_name = (team_name or "").strip().lower()
        return any(
            (name or "").strip().lower() == normalized_team_name
            for name in self.team_names
        )


class PasswordChangeRequest(db.Model):
    __tablename__ = "password_change_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    new_hzn_hash = db.Column(db.String(255), nullable=False)
    verification_code = db.Column(db.String(12), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="password_change_requests")

    @classmethod
    def find_by_id(cls, request_id):
        if request_id in (None, ""):
            return None
        return cls.query.get(request_id)

    @classmethod
    def for_user(cls, user_id):
        normalized_user_id = (user_id or "").strip().lower()
        if not normalized_user_id:
            return cls.query.filter(db.text("1 = 0"))
        return cls.query.filter_by(user_id=normalized_user_id).order_by(cls.created_at.desc())

    @classmethod
    def latest_for_user(cls, user_id):
        return cls.for_user(user_id).first()

    @classmethod
    def delete_for_user(cls, user_id):
        normalized_user_id = (user_id or "").strip().lower()
        if not normalized_user_id:
            return 0
        return cls.query.filter_by(user_id=normalized_user_id).delete()


# ==========================================================
# TEAM
# ==========================================================
class Team(db.Model):
    __tablename__ = "teams"

    team_id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def find_by_id(cls, team_id):
        if team_id in (None, ""):
            return None
        return cls.query.get(team_id)

    @classmethod
    def find_by_name(cls, team_name):
        normalized_team_name = (team_name or "").strip().lower()
        if not normalized_team_name:
            return None
        return cls.query.filter_by(team_name=normalized_team_name).first()

    @classmethod
    def ordered(cls):
        return cls.query.order_by(cls.team_name)


# ==========================================================
# USER ↔ TEAM
# ==========================================================
class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    team_id = db.Column(
        db.Integer,
        db.ForeignKey("teams.team_id"),
        nullable=False
    )

    role = db.Column(db.String(20), nullable=False, default="user")
    team_lead = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="team_memberships")
    team = db.relationship("Team", backref="members")

    __table_args__ = (
        db.UniqueConstraint("user_id", "team_id", name="uq_user_team"),
    )


# ==========================================================
# EMAIL DOMAIN
# ==========================================================
class EmailDomain(db.Model):
    __tablename__ = "email_domains"

    email_domain_id = db.Column(db.String(50), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ==========================================================
# DEFAULT PASSWORD
# ==========================================================
class DefaultPassword(db.Model):
    __tablename__ = "default_passwords"

    default_password_id = db.Column(db.String(20), primary_key=True)
    password_value = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @classmethod
    def find_by_id(cls, default_password_id):
        normalized_id = (default_password_id or "").strip()
        if not normalized_id:
            return None
        return cls.query.get(normalized_id)

    @classmethod
    def ordered(cls):
        return cls.query.order_by(cls.default_password_id)

    @classmethod
    def values(cls):
        return [record.password_value for record in cls.ordered().all()]


# ==========================================================
# ORBIT
# ==========================================================
class Orbit(db.Model):
    __tablename__ = "orbits"

    orbit_id = db.Column(db.String(20), primary_key=True)
    orb_value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @classmethod
    def find_by_id(cls, orbit_id):
        normalized_id = (orbit_id or "").strip()
        if not normalized_id:
            return None
        return cls.query.get(normalized_id)

    @classmethod
    def primary(cls):
        return cls.find_by_id("orb")


# ==========================================================
# ENVIRONMENT
# ==========================================================
class Environment(db.Model):
    __tablename__ = "environments"

    env_id = db.Column(db.String(16), primary_key=True)  # DEV01, ST01
    env_type = db.Column(db.String(16), nullable=False)  # DEV / ST / QA / PROD
    team = db.Column("domain", db.String(24))
    description = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)
    monitoring_enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    domain = db.synonym("team")


class PayUi(db.Model):
    __tablename__ = "pay_ui"

    env_id = db.Column(
        db.String(16),
        db.ForeignKey("environments.env_id"),
        primary_key=True,
    )
    pay_url = db.Column(db.Text)
    pay_adm_url = db.Column(db.Text)

    environment = db.relationship("Environment", backref="pay_ui_link", uselist=False)

    def get_url(self, access_type):
        if access_type == PayUiAccessType.PAY_URL.value:
            return (self.pay_url or "").strip()
        if access_type == PayUiAccessType.PAY_ADMIN.value:
            return (self.pay_adm_url or "").strip()
        return ""


# ==========================================================
# HOST
# ==========================================================
class Host(db.Model):
    __tablename__ = "hosts"
    host_id = db.Column(db.String(50), primary_key=True)
    # Real server hostname/address, e.g. core-host or serveraddress.
    hostname = db.Column(db.String(40), nullable=False)
    ip_address = db.Column(db.String(25))
    domain = db.Column(db.String(10))  # DEV / ST / PROD / TOOLS
    description = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint("hostname", "ip_address", "domain", name="uq_host_identity"),
    )


# ==========================================================
# SERVER TYPE
# ==========================================================
class ServerType(db.Model):
    __tablename__ = "server_types"

    server_type_id = db.Column(db.Integer, primary_key=True)

    server_type_key = db.Column(db.String(100), nullable=False)
    # Server type, e.g. core, gateway, lgdb, coredb, payapp.

    target_type = db.Column(db.String(50), nullable=False)
    # TCS_APP / DB / PAYAPP / TOOLS
    target_key = db.synonym("target_type")

    description = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "server_type_key",
            "target_type",
            name="uq_server_type_key_target_type"
        ),
    )


# ==========================================================
# ENVIRONMENT -> SERVER TYPE -> HOST
# ==========================================================
class EnvironmentHostMapping(db.Model):
    __tablename__ = "environment_host_mappings"

    environment_host_mapping_id = db.Column(db.Integer, primary_key=True)

    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=False,
    )

    env_type = db.Column(db.String(16))

    server_type_id = db.Column(
        db.Integer,
        db.ForeignKey("server_types.server_type_id"),
        nullable=False
    )

    host_id = db.Column(
        db.String(48),
        db.ForeignKey("hosts.host_id"),
        nullable=False
    )
    # Maps a server type such as core to the actual target host machine.

    deployment_user = db.Column(db.String(100))
    deploy_user_hzn = db.Column(db.String(255))

    environment = db.relationship("Environment", backref="host_mappings")
    server_type = db.relationship("ServerType", backref="environment_mappings")
    host = db.relationship("Host", backref="environment_mappings")

    __table_args__ = (
        db.UniqueConstraint(
            "env_id",
            "server_type_id",
            name="uq_environment_host_mapping"
        ),
    )

    @property
    def server_type_key(self):
        return self.server_type.server_type_key if self.server_type else None

    def _apply_temporary_deployment_user_override(self, deployment_user):
        """Temporary runtime override for DB access users without changing stored data."""
        normalized_server_type = (self.server_type_key or "").strip().lower()
        normalized_deployment_user = (deployment_user or "").strip()

        # Temporary fix for DB access until the source data is corrected.
        if (
            normalized_server_type in {"coredb", "lgdb"} and
            normalized_deployment_user.lower().endswith("dbm")
        ):
            return normalized_deployment_user[:-3] + "ktm"

        return deployment_user

    def __getattribute__(self, name):
        if name == "deployment_user":
            raw_value = object.__getattribute__(self, name)
            return object.__getattribute__(
                self,
                "_apply_temporary_deployment_user_override",
            )(raw_value)
        return object.__getattribute__(self, name)

    def matches_access_server_type(self, server_type_key):
        enum_value = ServerTypeKey.from_value(server_type_key)
        expected_value = enum_value.value if enum_value is not None else (server_type_key or "").strip().lower()
        return ((self.server_type_key or "").strip().lower() == expected_value)

    def terminal_access_payload(self):
        host = self.host
        return {
            "env_id": self.env_id,
            "server_type_key": self.server_type_key,
            "host_id": host.host_id if host else None,
            "hostname": host.hostname if host else None,
            "ip_address": host.ip_address if host else None,
            "deployment_user": self.deployment_user,
            "deploy_user_hzn": self.deploy_user_hzn,
        }

    def get_decrypted_deployment_password(self):
        from .orbit_crypto import decrypt_server_password

        return decrypt_server_password(self.deploy_user_hzn)

    @classmethod
    def get_core_vm(cls, env_id):
        return cls.find_terminal_access_mapping(env_id, ServerTypeKey.CORE)

    @classmethod
    def get_gateway_vm(cls, env_id):
        return cls.find_terminal_access_mapping(env_id, ServerTypeKey.GATEWAY)

    @classmethod
    def get_core_db_vm(cls, env_id):
        return cls.find_terminal_access_mapping(env_id, ServerTypeKey.COREDB)

    @classmethod
    def get_lg_db_vm(cls, env_id):
        return cls.find_terminal_access_mapping(env_id, ServerTypeKey.LGDB)

    @classmethod
    def get_core_vm_payload(cls, env_id):
        mapping = cls.get_core_vm(env_id)
        return mapping.terminal_access_payload() if mapping is not None else None

    @classmethod
    def get_gateway_vm_payload(cls, env_id):
        mapping = cls.get_gateway_vm(env_id)
        return mapping.terminal_access_payload() if mapping is not None else None

    @classmethod
    def get_core_db_vm_payload(cls, env_id):
        mapping = cls.get_core_db_vm(env_id)
        return mapping.terminal_access_payload() if mapping is not None else None

    @classmethod
    def get_lg_db_vm_payload(cls, env_id):
        mapping = cls.get_lg_db_vm(env_id)
        return mapping.terminal_access_payload() if mapping is not None else None

    @classmethod
    def find_terminal_access_mapping(cls, env_id, server_type_key):
        normalized_env_id = (env_id or "").strip()
        enum_value = ServerTypeKey.from_value(server_type_key)
        normalized_server_type = (
            enum_value.value if enum_value is not None else (server_type_key or "").strip().lower()
        )
        if not normalized_env_id or not normalized_server_type:
            return None

        mappings = cls.query.filter_by(env_id=normalized_env_id).all()
        for mapping in mappings:
            if mapping.matches_access_server_type(normalized_server_type):
                return mapping
        return None

    def to_dict(self):
        return {
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "env_id": self.env_id,
            "env_type": self.env_type,
            "server_type_id": self.server_type_id,
            "server_type_key": self.server_type.server_type_key if self.server_type else None,
            "target_key": self.server_type.target_key if self.server_type else None,
            "host_id": self.host_id,
            "hostname": self.host.hostname if self.host else None,
            "ip_address": self.host.ip_address if self.host else None,
            "deployment_user": self.deployment_user,
        }


# ==========================================================
# COMPONENT BUILD
# ==========================================================
class ComponentBuild(db.Model):
    __tablename__ = "component_builds"

    build_id = db.Column(db.Integer, primary_key=True)

    target_key = db.Column(db.String(50), nullable=False)
    # TCS_APP / DB / PAYAPP / TOOLS

    build_name = db.Column(db.String(100), nullable=False)
    # Stable service/app identity such as tcs_service, tcs_db, payapp, or tool1.

    version = db.Column(db.String(50), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "target_key",
            "build_name",
            "version",
            name="uq_component_build"
        ),
        db.Index("idx_component_build_lookup", "target_key", "build_name", "version"),
        db.Index("idx_component_build_target", "target_key"),
        db.Index("idx_component_build_version", "version"),
    )

    def to_dict(self):
        return {
            "build_id": self.build_id,
            "target_key": self.target_key,
            "app_name": self.build_name,
            "build_name": self.build_name,
            "version": self.version,
            "package_entries": self.package_entries(),
            "created_at": format_datetime(self.created_at),
        }

    def package_entries(self):
        from .domain.deployment_targets import get_target_definition

        target_definition = get_target_definition(self.target_key) or {}
        if self.target_key == "TOOLS":
            selected_package_keys = [self.build_name]
        else:
            selected_package_keys = list((target_definition.get("packages") or {}).keys())
        return build_package_entries(
            self.target_key,
            target_definition=target_definition,
            selected_package_keys=selected_package_keys,
            build_name=self.build_name,
        )

    def get_package_entry(self, package_key):
        normalized_key = (package_key or "").strip().lower()
        for package_data in self.package_entries():
            if (package_data.get("package_key") or "").strip().lower() == normalized_key:
                return package_data
        return None

    def package_summary(self):
        package_keys = [
            (package_data.get("package_key") or "").strip().lower()
            for package_data in self.package_entries()
            if (package_data.get("package_key") or "").strip()
        ]
        return ", ".join(package_keys) if package_keys else "-"


# ==========================================================
# TCS SERVICE
# ==========================================================
class TcsService(db.Model):
    __tablename__ = "tcs_services"

    LOGICAL_BIT_ID_MAP = {
        "DOM": "21",
        "MON": "22",
        "CPM": "2,3",
        "DOM_MON": "21,22",
    }

    tcs_service_id = db.Column(db.String(16), primary_key=True)
    service_name = db.Column(db.String(128), nullable=False)
    bit_id = db.Column(db.String(32))
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @classmethod
    def normalize_service_id(cls, value):
        normalized = (value or "").strip().upper()
        return normalized or None

    @classmethod
    def normalize_bit_id(cls, value):
        if value is None:
            raw_value = ""
        else:
            raw_value = str(value).strip()
        if not raw_value:
            return None
        tokens = []
        for token in raw_value.replace(":", ",").split(","):
            normalized_token = token.strip()
            if normalized_token and normalized_token not in tokens:
                tokens.append(normalized_token)
        if not tokens:
            return None
        if len(tokens) == 1:
            return tokens[0]
        try:
            tokens = sorted(tokens, key=lambda item: int(item))
        except ValueError:
            tokens = sorted(tokens)
        return ",".join(tokens)

    @classmethod
    def default_bit_id_for_service_id(cls, service_id):
        normalized_service_id = cls.normalize_service_id(service_id)
        if not normalized_service_id:
            return None
        return cls.LOGICAL_BIT_ID_MAP.get(normalized_service_id)

    @classmethod
    def default_service_id_for_bit_id(cls, bit_id):
        normalized_bit_id = cls.normalize_bit_id(bit_id)
        if not normalized_bit_id:
            return None
        for service_id, candidate_bit_id in cls.LOGICAL_BIT_ID_MAP.items():
            if cls.normalize_bit_id(candidate_bit_id) == normalized_bit_id:
                return service_id
        return None

    @classmethod
    def resolve_logical_service_ids(cls, values):
        resolved_ids = []
        for value in values or []:
            normalized_service_id = cls.normalize_service_id(value)
            if normalized_service_id:
                service = cls.query.get(normalized_service_id)
                if service is not None:
                    if service.tcs_service_id not in resolved_ids:
                        resolved_ids.append(service.tcs_service_id)
                    continue

            normalized_bit_id = cls.normalize_bit_id(value)
            if normalized_bit_id:
                default_service_id = cls.default_service_id_for_bit_id(normalized_bit_id)
                if default_service_id and default_service_id not in resolved_ids:
                    resolved_ids.append(default_service_id)
                    continue

                service = cls.query.filter_by(bit_id=normalized_bit_id).first()
                if service is not None:
                    if service.tcs_service_id not in resolved_ids:
                        resolved_ids.append(service.tcs_service_id)
                    continue

                bit_id_tokens = normalized_bit_id.split(",")
                if len(bit_id_tokens) > 1:
                    for token in bit_id_tokens:
                        fallback_service = cls.query.filter_by(bit_id=token).first()
                        if fallback_service is not None and fallback_service.tcs_service_id not in resolved_ids:
                            resolved_ids.append(fallback_service.tcs_service_id)
                    continue

            if normalized_service_id and normalized_service_id not in resolved_ids:
                resolved_ids.append(normalized_service_id)
        return resolved_ids


# ==========================================================
# TCS DEPLOYMENT MODE
# ==========================================================
class TCSDeploymentMode(db.Model):
    __tablename__ = "tcs_deployment_modes"

    tcs_deployment_mode_id = db.Column(db.String(16), primary_key=True)
    mode_name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


# ==========================================================
# ENVIRONMENT BOOKING
# ==========================================================
class EnvironmentBooking(db.Model):
    __tablename__ = "environment_bookings"

    booking_id = db.Column(
        db.String(50),
        primary_key=True,
        default=lambda: generate_id("BOOK")
    )

    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=False
    )

    requested_by = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    booking_type = db.Column(
        db.Enum("RESERVATION", name="booking_type"),
        nullable=False
    )

    status = db.Column(
        db.Enum(
            "inactive",
            "scheduled",
            "active",
            "expired",
            "completed",
            "cancelled",
            name="booking_status"
        ),
        default="scheduled",
        nullable=False
    )
    # New writes should persist only scheduled/cancelled.
    # Legacy time-derived values remain allowed for compatibility with old rows.

    description = db.Column(db.Text)
    user_timezone = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    environment = db.relationship("Environment", backref="bookings")
    requester = db.relationship("User", backref="bookings")

    __table_args__ = (
        db.CheckConstraint("start_time < end_time", name="ck_booking_time_order"),
        db.Index("idx_booking_env_time", "env_id", "start_time", "end_time"),
        db.Index("idx_booking_user_status", "requested_by", "status"),
    )

    @property
    def normalized_status(self):
        raw_status = (self.status or "").strip().lower()
        aliases = {
            BOOKING_STATUS_ALIASES["INACTIVE"]: BOOKING_STATUS["SCHEDULED"],
            BOOKING_STATUS_ALIASES["EXPIRED"]: BOOKING_LIFECYCLE_STATUS["COMPLETED"],
        }
        return aliases.get(raw_status, raw_status)

    def lifecycle_status(self, now=None):
        if now is None:
            now = datetime.utcnow()

        stored_status = self.normalized_status
        if stored_status == BOOKING_STATUS["CANCELLED"]:
            return BOOKING_STATUS["CANCELLED"]
        if self.start_time is not None and now < self.start_time:
            return BOOKING_LIFECYCLE_STATUS["SCHEDULED"]
        if (
            self.start_time is not None and
            self.end_time is not None and
            self.start_time <= now <= self.end_time
        ):
            return BOOKING_LIFECYCLE_STATUS["ACTIVE"]
        return BOOKING_LIFECYCLE_STATUS["COMPLETED"]

    def is_cancelled(self):
        return self.normalized_status == BOOKING_STATUS["CANCELLED"]

    def is_mutable(self, now=None):
        return self.lifecycle_status(now=now) in BOOKING_MUTABLE_LIFECYCLE_STATUSES

    def to_dict(self):
        requester = self.requester
        requested_by_name = (
            ((requester.user_id or "").strip() or (requester.name or "").strip())
            if requester else
            self.requested_by
        )
        requested_by_team = requester.team_names_display if requester else None
        data = {
            "booking_id": self.booking_id,
            "env_id": self.env_id,
            "env_type": self.environment.env_type if self.environment else None,
            "requested_by": self.requested_by,
            "requested_by_name": requested_by_name,
            "requested_by_team": requested_by_team,
            "requested_by_display": build_requester_display(requester, self.requested_by),
            "start_time": format_datetime(self.start_time),
            "end_time": format_datetime(self.end_time),
            "booking_type": self.booking_type,
            "status": self.status,
            "description": self.description,
            "user_timezone": self.user_timezone,
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }

        if hasattr(self, "deployment_request") and self.deployment_request:
            data["deployment_request"] = self.deployment_request.to_dict()

        return data


# ==========================================================
# ENV BOOKING SYSTEM SNAPSHOT
# ==========================================================
class EnvBookingSystemSnapshot(db.Model):
    __tablename__ = "env_booking_system_snapshots"

    env_booking_system_snapshot_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.String(50),
        db.ForeignKey("environment_bookings.booking_id"),
        nullable=False,
        index=True,
    )
    environment_host_mapping_id = db.Column(
        db.Integer,
        db.ForeignKey("environment_host_mappings.environment_host_mapping_id"),
        nullable=False,
    )
    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=False,
    )
    host_id = db.Column(
        db.String(50),
        db.ForeignKey("hosts.host_id"),
        nullable=False,
    )
    server_type_id = db.Column(
        db.Integer,
        db.ForeignKey("server_types.server_type_id"),
        nullable=False,
    )
    target_key = db.Column(db.String(50), nullable=False, default="TCS_APP")
    package_key = db.Column(db.String(100))
    tcs_service_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_services.tcs_service_id"),
        nullable=True,
    )
    tcs_deployment_mode_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_deployment_modes.tcs_deployment_mode_id"),
    )
    package_name = db.Column(db.String(150))
    current_version = db.Column(db.String(50))
    source = db.Column(db.String(30), nullable=False, default="CURRENT_DEPLOYMENT_STATE")
    status = db.Column(db.String(30), nullable=False, default="CURRENT")
    captured_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text)

    booking = db.relationship("EnvironmentBooking", backref="system_snapshots")
    environment = db.relationship("Environment")
    host = db.relationship("Host")
    server_type = db.relationship("ServerType")
    environment_host_mapping = db.relationship("EnvironmentHostMapping")
    tcs_service = db.relationship("TcsService")
    tcs_deployment_mode = db.relationship("TCSDeploymentMode")

    __table_args__ = (
        db.Index(
            "idx_booking_snapshot_lookup",
            "booking_id",
            "environment_host_mapping_id",
            "server_type_id",
            "tcs_service_id",
        ),
        db.UniqueConstraint(
            "booking_id",
            "environment_host_mapping_id",
            "target_key",
            "package_key",
            "tcs_service_id",
            name="uq_booking_snapshot_server_service",
        ),
    )


# ==========================================================
# DEPLOYMENT REQUEST
# ==========================================================
class DeploymentRequest(db.Model):
    __tablename__ = "deployment_requests"

    deployment_request_id = db.Column(
        db.String(50),
        primary_key=True,
        default=lambda: generate_id("DREQ")
    )

    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=False,
    )

    requested_env_type = db.Column(db.String(50))
    env_scope_type = db.Column(db.String(20), nullable=False, default="ENV")

    requested_by = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=False
    )

    planned_start_time = db.Column(db.DateTime, nullable=False)

    build_id = db.Column(
        db.Integer,
        db.ForeignKey("component_builds.build_id"),
        nullable=True
    )

    target_key = db.Column(db.String(50), nullable=False)

    requested_version = db.Column(db.String(50), nullable=False)

    package_keys_raw = db.Column("package_keys", db.Text, nullable=False)
    # JSON list used only for tool deployments, for example ["tool1"].
    selected_server_mapping_ids_raw = db.Column("selected_server_mapping_ids", db.Text, nullable=False, default="[]")
    # JSON list of selected EnvironmentHostMapping ids for deployment execution.

    tcs_deployment_mode_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_deployment_modes.tcs_deployment_mode_id"),
    )
    jira_id = db.Column(db.String(50))
    description = db.Column(db.Text)
    remarks = db.Column(db.Text)
    status = db.Column(
        db.Enum(
            "OPEN",
            "READY_FOR_DEPLOYMENT",
            "AUTO_DEPLOYMENT_RUNNING",
            "MANUAL_DEPLOYMENT_IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "REJECTED",
            name="deployment_request_status",
        ),
        default="OPEN",
        nullable=False,
    )
    execution_mode = db.Column(
        db.Enum("AUTO", "MANUAL", name="deployment_execution_mode"),
        nullable=True,
    )
    approved_by = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=True,
    )
    approved_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    failure_reason = db.Column(db.Text)
    last_notified_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    environment = db.relationship("Environment", backref="deployment_requests")
    requester = db.relationship("User", foreign_keys=[requested_by], backref="deployment_requests")
    approver = db.relationship("User", foreign_keys=[approved_by], backref="approved_deployment_requests")
    build = db.relationship("ComponentBuild", backref="deployment_requests")
    tcs_deployment_mode = db.relationship("TCSDeploymentMode")

    __table_args__ = (
        db.Index("idx_dreq_status_created", "status", "created_at"),
        db.Index("idx_dreq_env_status", "env_id", "status"),
        db.Index("idx_dreq_target_version", "target_key", "requested_version"),
    )

    @property
    def package_keys(self):
        return parse_json_list(self.package_keys_raw)

    @package_keys.setter
    def package_keys(self, packages):
        self.package_keys_raw = json_dumps(packages)

    @property
    def selected_server_mapping_ids(self):
        values = parse_json_list(self.selected_server_mapping_ids_raw)
        normalized = []
        for value in values:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                continue
        return normalized

    @selected_server_mapping_ids.setter
    def selected_server_mapping_ids(self, mapping_ids):
        normalized = []
        for value in mapping_ids or []:
            try:
                normalized.append(int(value))
            except (TypeError, ValueError):
                continue
        self.selected_server_mapping_ids_raw = json_dumps(normalized)

    def get_service_ids(self):
        service_ids = []
        for item in self.request_services or []:
            if item.tcs_service_id and item.tcs_service_id not in service_ids:
                service_ids.append(item.tcs_service_id)
        return service_ids

    def get_service_names(self):
        service_names = []
        for item in self.request_services or []:
            service = item.tcs_service
            service_name = (
                service.service_name if service is not None else item.tcs_service_id
            )
            if service_name and service_name not in service_names:
                service_names.append(service_name)
        return service_names

    def set_service_ids(self, service_ids):
        normalized_ids = []
        for value in service_ids or []:
            normalized_value = (value or "").strip()
            if normalized_value and normalized_value not in normalized_ids:
                normalized_ids.append(normalized_value)

        existing_by_service_id = {
            item.tcs_service_id: item
            for item in self.request_services or []
            if item.tcs_service_id
        }
        updated_items = []
        for service_id in normalized_ids:
            existing = existing_by_service_id.get(service_id)
            if existing is not None:
                updated_items.append(existing)
            else:
                updated_items.append(
                    DeploymentRequestService(
                        tcs_service_id=service_id,
                    )
                )
        self.request_services = updated_items

    @property
    def target_definition(self):
        from .domain.deployment_targets import get_target_definition

        return get_target_definition(self.target_key) or {}

    @property
    def target_display_name(self):
        return self.target_definition.get("display_name") or self.target_key

    @property
    def environment_scope(self):
        return (self.env_scope_type or "ENV").strip().upper()

    @property
    def environment_scope_value(self):
        return self.env_id

    def get_package_entry(self, package_key):
        normalized_key = (package_key or "").strip().lower()
        package_entries = build_package_entries(
            self.target_key,
            target_definition=self.target_definition,
            selected_package_keys=list((self.target_definition.get("packages") or {}).keys()),
        )
        for package in package_entries:
            package_aliases = {
                (package.get("package_key") or "").strip().lower(),
                (package.get("server_type_key") or "").strip().lower(),
                (package.get("package_name") or "").strip().lower(),
            }
            if normalized_key in package_aliases:
                return package
        return None

    @property
    def build_name(self):
        return (
            self.build.build_name if self.build else None
        ) or self.target_key

    @property
    def build_version(self):
        return self.requested_version

    @property
    def selected_server_mappings(self):
        mappings = []
        seen_ids = set()
        for deployment in self.deployments or []:
            mapping = deployment.environment_host_mapping
            if mapping is None or mapping.environment_host_mapping_id in seen_ids:
                continue
            seen_ids.add(mapping.environment_host_mapping_id)
            mappings.append(mapping)
        if mappings:
            return mappings

        selected_ids = self.selected_server_mapping_ids
        if not selected_ids:
            return []

        mapping_by_id = {
            mapping.environment_host_mapping_id: mapping
            for mapping in EnvironmentHostMapping.query.filter(
                EnvironmentHostMapping.environment_host_mapping_id.in_(selected_ids)
            ).all()
        }
        return [
            mapping_by_id[mapping_id]
            for mapping_id in selected_ids
            if mapping_id in mapping_by_id
        ]

    @property
    def selected_servers(self):
        servers = []
        for mapping in self.selected_server_mappings:
            host = mapping.host
            server_type = mapping.server_type
            hostname = host.hostname if host is not None else None
            server_type_key = server_type.server_type_key if server_type is not None else None
            label_parts = [part for part in [server_type_key, hostname] if part]
            servers.append(
                {
                    "environment_host_mapping_id": mapping.environment_host_mapping_id,
                    "server_type_key": server_type_key,
                    "host_id": host.host_id if host is not None else None,
                    "hostname": hostname,
                    "ip_address": host.ip_address if host is not None else None,
                    "label": " / ".join(label_parts) if label_parts else str(mapping.environment_host_mapping_id),
                }
            )
        return servers

    @property
    def selected_servers_summary(self):
        labels = [server.get("label") for server in self.selected_servers if server.get("label")]
        return ", ".join(labels)

    def environment_display_label(self):
        return self.env_id or "-"

    def resolved_hostnames(self):
        hostnames = []
        for deployment in self.deployments or []:
            mapping = deployment.environment_host_mapping
            host = mapping.host if mapping else None
            hostname = host.hostname if host else None
            if hostname and hostname not in hostnames:
                hostnames.append(hostname)
        return hostnames

    def to_dict(self):
        resolved_hostnames = self.resolved_hostnames()
        requester = self.requester
        requested_by_name = (
            ((requester.user_id or "").strip() or (requester.name or "").strip())
            if requester else
            self.requested_by
        )
        requested_by_team = requester.team_names_display if requester else None
        return {
            "deployment_request_id": self.deployment_request_id,
            "env_id": self.env_id,
            "environment_display": self.environment_display_label(),
            "requested_env_type": self.requested_env_type,
            "env_scope_type": self.environment_scope,
            "environment_scope": self.environment_scope,
            "environment_scope_value": self.environment_scope_value,
            "requested_by": self.requested_by,
            "requested_by_name": requested_by_name,
            "requested_by_team": requested_by_team,
            "requested_by_display": build_requester_display(requester, self.requested_by),
            "planned_start_time": format_datetime(self.planned_start_time),
            "build_id": self.build_id,
            "target_key": self.target_key,
            "target_display_name": self.target_display_name,
            "app_name": self.build_name,
            "build_name": self.build_name,
            "build_version": self.build_version,
            "requested_version": self.requested_version,
            "package_keys": self.package_keys,
            "selected_server_mapping_ids": self.selected_server_mapping_ids,
            "selected_servers": self.selected_servers,
            "selected_servers_summary": self.selected_servers_summary,
            "tcs_deployment_mode_id": self.tcs_deployment_mode_id,
            "tcs_deployment_mode": (
                self.tcs_deployment_mode.mode_name
                if self.tcs_deployment_mode else
                None
            ),
            "tcs_service_ids": self.get_service_ids(),
            "tcs_service_names": self.get_service_names(),
            "jira_id": self.jira_id,
            "description": self.description,
            "remarks": self.remarks,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "approved_by": self.approved_by,
            "approved_by_name": self.approver.name if self.approver else self.approved_by,
            "approved_at": format_datetime(self.approved_at),
            "completed_at": format_datetime(self.completed_at),
            "failure_reason": self.failure_reason,
            "last_notified_at": format_datetime(self.last_notified_at),
            "resolved_hostnames": resolved_hostnames,
            "resolved_hosts_summary": ", ".join(resolved_hostnames),
            "deployments": [deployment.to_dict() for deployment in self.deployments],
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


# ==========================================================
# DEPLOYMENT REQUEST -> TCS SERVICE
# ==========================================================
class DeploymentRequestService(db.Model):
    __tablename__ = "deployment_request_services"

    deployment_request_service_id = db.Column(db.Integer, primary_key=True)
    deployment_request_id = db.Column(
        db.String(50),
        db.ForeignKey("deployment_requests.deployment_request_id"),
        nullable=False,
        index=True,
    )
    tcs_service_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_services.tcs_service_id"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    deployment_request = db.relationship("DeploymentRequest", backref="request_services")
    tcs_service = db.relationship("TcsService")

    __table_args__ = (
        db.UniqueConstraint(
            "deployment_request_id",
            "tcs_service_id",
            name="uq_deployment_request_service",
        ),
    )


# ==========================================================
# DEPLOYMENT EXECUTION RECORD
# ==========================================================
class Deployment(db.Model):
    __tablename__ = "deployments"

    deployment_id = db.Column(db.Integer, primary_key=True)

    deployment_request_id = db.Column(
        db.String(50),
        db.ForeignKey("deployment_requests.deployment_request_id"),
        nullable=False
    )

    environment_host_mapping_id = db.Column(
        db.Integer,
        db.ForeignKey("environment_host_mappings.environment_host_mapping_id"),
        nullable=False
    )

    package_key = db.Column(db.String(100), nullable=False)
    # cor / gateway / cordb / paydb / lg / tool1

    package_name = db.Column(db.String(150), nullable=False)
    # display/package label snapshot for this execution line

    deployed_version = db.Column(db.String(50), nullable=False)

    deployment_status = db.Column(
        db.Enum(
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "CANCELLED",
            name="deployment_status"
        ),
        default="PENDING",
        nullable=False
    )

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    log_excerpt = db.Column(db.Text)

    deployment_request = db.relationship("DeploymentRequest", backref="deployments")
    environment_host_mapping = db.relationship(
        "EnvironmentHostMapping",
        backref="deployments"
    )

    @property
    def env_id(self):
        mapping = self.environment_host_mapping
        return mapping.env_id if mapping else None

    @property
    def server_type_key(self):
        mapping = self.environment_host_mapping
        if mapping is None or mapping.server_type is None:
            return None
        return mapping.server_type.server_type_key

    @property
    def host_id(self):
        mapping = self.environment_host_mapping
        return mapping.host_id if mapping else None

    @property
    def target_key(self):
        request = self.deployment_request
        return request.target_key if request else None

    @property
    def package_metadata(self):
        request = self.deployment_request
        if request is None:
            return None
        return request.get_package_entry(self.package_key)

    def to_dict(self):
        return {
            "deployment_id": self.deployment_id,
            "deployment_request_id": self.deployment_request_id,
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "env_id": self.env_id,
            "server_type_key": self.server_type_key,
            "host_id": self.host_id,
            "hostname": (
                self.environment_host_mapping.host.hostname
                if self.environment_host_mapping and self.environment_host_mapping.host
                else None
            ),
            "target_key": self.target_key,
            "package_key": self.package_key,
            "app_name": self.package_name,
            "package_name": self.package_name,
            "package_metadata": self.package_metadata,
            "deployed_version": self.deployed_version,
            "server_label": " / ".join([
                part for part in [
                    self.server_type_key,
                    (
                        self.environment_host_mapping.host.hostname
                        if self.environment_host_mapping and self.environment_host_mapping.host
                        else None
                    ),
                ] if part
            ]),
            "deployment_status": self.deployment_status,
            "log_excerpt": self.log_excerpt,
            "started_at": format_datetime(self.started_at),
            "completed_at": format_datetime(self.completed_at),
            "created_at": format_datetime(self.created_at),
        }


class CurrentDeploymentState(db.Model):
    __tablename__ = "current_deployment_state"

    current_deployment_state_id = db.Column(db.Integer, primary_key=True)

    env_scope_type = db.Column(db.String(20), nullable=False, default="ENV")
    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=False,
    )
    env_type = db.Column(db.String(50))

    environment_host_mapping_id = db.Column(
        db.Integer,
        db.ForeignKey("environment_host_mappings.environment_host_mapping_id"),
        nullable=False,
    )

    target_key = db.Column(db.String(50), nullable=False)
    package_key = db.Column(db.String(100), nullable=False)
    package_name = db.Column(db.String(150), nullable=False)
    current_version = db.Column(db.String(50))
    tcs_service_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_services.tcs_service_id"),
        nullable=False,
    )
    tcs_deployment_mode_id = db.Column(
        db.String(16),
        db.ForeignKey("tcs_deployment_modes.tcs_deployment_mode_id"),
    )
    source = db.Column(db.String(30), nullable=False, default="DEPLOYMENT")
    status = db.Column(db.String(30), nullable=False, default="CURRENT")
    updated_by = db.Column(
        db.String(50),
        db.ForeignKey("users.user_id"),
        nullable=True,
    )
    deployment_request_id = db.Column(
        db.String(50),
        db.ForeignKey("deployment_requests.deployment_request_id"),
        nullable=True,
    )
    deployment_id = db.Column(
        db.Integer,
        db.ForeignKey("deployments.deployment_id"),
        nullable=True,
    )
    notes = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    environment = db.relationship("Environment", backref="current_deployment_states")
    environment_host_mapping = db.relationship("EnvironmentHostMapping", backref="current_states")
    deployment_request = db.relationship("DeploymentRequest", backref="current_state_updates")
    deployment = db.relationship("Deployment", backref="current_state_updates")
    updated_by_user = db.relationship("User")
    tcs_service = db.relationship("TcsService")
    tcs_deployment_mode = db.relationship("TCSDeploymentMode")

    __table_args__ = (
        db.UniqueConstraint(
            "env_scope_type",
            "env_id",
            "env_type",
            "environment_host_mapping_id",
            "package_key",
            "tcs_service_id",
            name="uq_current_deployment_state",
        ),
        db.Index(
            "idx_current_deployment_lookup",
            "env_scope_type",
            "env_id",
            "env_type",
            "target_key",
            "package_key",
            "tcs_service_id",
        ),
    )

    def to_dict(self):
        mapping = self.environment_host_mapping
        host = mapping.host if mapping else None
        deployment_request = self.deployment_request
        return {
            "current_deployment_state_id": self.current_deployment_state_id,
            "env_scope_type": self.env_scope_type,
            "env_id": self.env_id,
            "env_type": self.env_type,
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "target_key": self.target_key,
            "target_display_name": (
                deployment_request.target_display_name
                if deployment_request is not None
                else self.target_key
            ),
            "package_key": self.package_key,
            "app_name": self.package_name,
            "package_name": self.package_name,
            "current_version": self.current_version,
            "tcs_service_id": self.tcs_service_id,
            "tcs_service_name": self.tcs_service.service_name if self.tcs_service else None,
            "tcs_deployment_mode_id": self.tcs_deployment_mode_id,
            "tcs_deployment_mode": (
                self.tcs_deployment_mode.mode_name
                if self.tcs_deployment_mode else
                None
            ),
            "source": self.source,
            "status": self.status,
            "updated_by": self.updated_by,
            "deployment_request_id": self.deployment_request_id,
            "deployment_id": self.deployment_id,
            "package_metadata": (
                deployment_request.get_package_entry(self.package_key)
                if deployment_request is not None else
                None
            ),
            "server_type_key": mapping.server_type.server_type_key if mapping and mapping.server_type else None,
            "hostname": host.hostname if host else None,
            "host_id": host.host_id if host else None,
            "updated_at": format_datetime(self.updated_at),
            "notes": self.notes,
        }
