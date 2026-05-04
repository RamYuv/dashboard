import json
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

from .constants import (
    BOOKING_LIFECYCLE_STATUS,
    BOOKING_MUTABLE_LIFECYCLE_STATUSES,
    BOOKING_STATUS,
    BOOKING_STATUS_ALIASES,
)

db = SQLAlchemy()

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


# ==========================================================
# USER
# ==========================================================
class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.String(50), primary_key=True)
    email_id = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)

    # Optional global role
    role = db.Column(db.String(20), nullable=False, default="User")

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    username = db.synonym("user_id")
    id = db.synonym("user_id")

    @property
    def team_names(self):
        names = []
        for membership in getattr(self, "team_memberships", []) or []:
            if membership.team and membership.team.team_name:
                names.append(membership.team.team_name)
        return names

    @property
    def team_name(self):
        names = self.team_names
        return names[0] if names else None

    @property
    def team_names_display(self):
        return ", ".join(self.team_names)

    def has_team(self, team_name):
        normalized_team_name = (team_name or "").strip().lower()
        return any(
            (name or "").strip().lower() == normalized_team_name
            for name in self.team_names
        )


# ==========================================================
# TEAM
# ==========================================================
class Team(db.Model):
    __tablename__ = "teams"

    team_id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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

    role = db.Column(db.String(20), nullable=False)  # Admin / QA / User

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="team_memberships")
    team = db.relationship("Team", backref="members")

    __table_args__ = (
        db.UniqueConstraint("user_id", "team_id", name="uq_user_team"),
    )


# ==========================================================
# ENVIRONMENT
# ==========================================================
class Environment(db.Model):
    __tablename__ = "environments"

    env_id = db.Column(db.String(50), primary_key=True)  # DEV01, ST01
    env_type = db.Column(db.String(50), nullable=False)  # DEV / ST / QA / PROD
    description = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==========================================================
# HOST
# ==========================================================
class Host(db.Model):
    __tablename__ = "hosts"

    host_id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100), unique=True, nullable=False)
    ip_address = db.Column(db.String(100))
    domain = db.Column(db.String(50))  # DEV / ST / PROD / TOOLS
    description = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)


# ==========================================================
# SERVER ROLE
# ==========================================================
class ServerRole(db.Model):
    __tablename__ = "server_roles"

    server_role_id = db.Column(db.Integer, primary_key=True)

    role_key = db.Column(db.String(100), nullable=False)
    # Canonical role key, e.g. cor-tcs, gateway-tcs, pay-ui, cordb, tools-server.

    role_type = db.Column(db.String(50), nullable=False)
    # TCS / DB / PAYUI / TOOLS

    description = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "role_key",
            "role_type",
            name="uq_server_role_key_type"
        ),
    )


# ==========================================================
# ENVIRONMENT ↔ LOGICAL SERVER ↔ HOST
# ==========================================================
class EnvironmentHostMapping(db.Model):
    __tablename__ = "environment_host_mappings"

    environment_host_mapping_id = db.Column(db.Integer, primary_key=True)

    env_id = db.Column(
        db.String(50),
        db.ForeignKey("environments.env_id"),
        nullable=True
    )

    env_type = db.Column(db.String(50))
    is_shared = db.Column(db.Boolean, default=False, nullable=False)

    server_role_id = db.Column(
        db.Integer,
        db.ForeignKey("server_roles.server_role_id"),
        nullable=False
    )

    host_id = db.Column(
        db.Integer,
        db.ForeignKey("hosts.host_id"),
        nullable=False
    )

    deployment_user = db.Column(db.String(100))
    deployment_password = db.Column(db.String(255))

    environment = db.relationship("Environment", backref="host_mappings")
    server_role = db.relationship("ServerRole", backref="environment_mappings")
    host = db.relationship("Host", backref="environment_mappings")

    __table_args__ = (
        db.UniqueConstraint(
            "env_id",
            "server_role_id",
            name="uq_environment_host_mapping"
        ),
    )

    @property
    def role_key(self):
        return self.server_role.role_key if self.server_role else None

    def to_dict(self):
        return {
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "env_id": self.env_id,
            "env_type": self.env_type,
            "is_shared": self.is_shared,
            "server_role_id": self.server_role_id,
            "server_role_key": self.server_role.role_key if self.server_role else None,
            "role_type": self.server_role.role_type if self.server_role else None,
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

    component_type = db.Column(db.String(50), nullable=False)
    # TCS_APP / TCS_PAYUI / TCS_DB / TOOLS

    component_name = db.Column(db.String(100), nullable=False)
    # tcs_service / payui / tcs_db / tools

    version = db.Column(db.String(50), nullable=False)

    artifact_name = db.Column(db.String(255))
    artifact_path = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "component_type",
            "component_name",
            "version",
            name="uq_component_build"
        ),
        db.Index("idx_component_build_lookup", "component_type", "component_name", "version"),
    )

    def to_dict(self):
        return {
            "build_id": self.build_id,
            "component_type": self.component_type,
            "component_name": self.component_name,
            "version": self.version,
            "artifact_name": self.artifact_name,
            "artifact_path": self.artifact_path,
            "created_at": format_datetime(self.created_at),
        }


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
        data = {
            "booking_id": self.booking_id,
            "env_id": self.env_id,
            "requested_by": self.requested_by,
            "requested_by_name": self.requester.name if self.requester else None,
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
        nullable=True
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

    component_type = db.Column(db.String(50), nullable=True)
    # Legacy denormalized field retained for migration compatibility.

    component_name = db.Column(db.String(100), nullable=True)
    # Legacy denormalized field retained for migration compatibility.

    requested_version = db.Column(db.String(50), nullable=False)

    selected_packages = db.Column(db.Text, nullable=False)
    # JSON list: ["all"] or ["gateway"] or ["cordb", "paydb"]

    testing_mode = db.Column(db.String(50), nullable=False, default="")
    service_types = db.Column(db.Text, nullable=False, default="[]")
    # JSON list of selected service types for TCS_APP requests.
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

    __table_args__ = (
        db.Index("idx_dreq_status_created", "status", "created_at"),
        db.Index("idx_dreq_env_status", "env_id", "status"),
        db.Index("idx_dreq_component", "component_type", "component_name", "requested_version"),
    )

    def get_selected_packages(self):
        return parse_json_list(self.selected_packages)

    def set_selected_packages(self, packages):
        self.selected_packages = json_dumps(packages)

    def get_service_types(self):
        return parse_json_list(self.service_types)

    def set_service_types(self, service_types):
        self.service_types = json_dumps(service_types)

    def resolved_component_type(self):
        from .deployment_targets import derive_component_type

        return (
            self.build.component_type if self.build else None
        ) or derive_component_type(self.target_key, self.component_type)

    def resolved_component_name(self):
        from .deployment_targets import get_target_definition

        target_definition = get_target_definition(self.target_key) or {}
        return (
            self.build.component_name if self.build else None
        ) or self.component_name or target_definition.get("component_name")

    def environment_display_label(self):
        if self.env_scope_type == "ENV" and self.env_id:
            return self.env_id
        if self.requested_env_type:
            return "{} (shared)".format(self.requested_env_type)
        if self.env_id:
            return self.env_id
        return "Shared"

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
        return {
            "deployment_request_id": self.deployment_request_id,
            "env_id": self.env_id,
            "environment_display": self.environment_display_label(),
            "requested_env_type": self.requested_env_type,
            "env_scope_type": self.env_scope_type,
            "requested_by": self.requested_by,
            "requested_by_name": self.requester.name if self.requester else self.requested_by,
            "planned_start_time": format_datetime(self.planned_start_time),
            "build_id": self.build_id,
            "target_key": self.target_key,
            "component_type": self.resolved_component_type(),
            "component_name": self.resolved_component_name(),
            "artifact_name": self.build.artifact_name if self.build else None,
            "requested_version": self.requested_version,
            "component_names": self.get_selected_packages(),
            "selected_packages": self.get_selected_packages(),
            "testing_mode": self.testing_mode,
            "service_types": self.get_service_types(),
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
            "resolved_targets": [deployment.to_dict() for deployment in self.deployments],
            "created_at": format_datetime(self.created_at),
            "updated_at": format_datetime(self.updated_at),
        }


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
    # tcs_service_cor / tcs_service_gateway / cordb / tool1

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
    def server_role_key(self):
        mapping = self.environment_host_mapping
        if mapping is None or mapping.server_role is None:
            return None
        return mapping.server_role.role_key

    @property
    def host_id(self):
        mapping = self.environment_host_mapping
        return mapping.host_id if mapping else None

    def to_dict(self):
        return {
            "deployment_id": self.deployment_id,
            "deployment_request_id": self.deployment_request_id,
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "env_id": self.env_id,
            "server_role_key": self.server_role_key,
            "host_id": self.host_id,
            "package_key": self.package_key,
            "package_name": self.package_name,
            "deployed_version": self.deployed_version,
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
        nullable=True,
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
    updated_by_user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint(
            "env_scope_type",
            "env_id",
            "env_type",
            "environment_host_mapping_id",
            "package_key",
            name="uq_current_deployment_state",
        ),
        db.Index(
            "idx_current_deployment_lookup",
            "env_scope_type",
            "env_id",
            "env_type",
            "target_key",
            "package_key",
        ),
    )

    def to_dict(self):
        mapping = self.environment_host_mapping
        host = mapping.host if mapping else None
        return {
            "current_deployment_state_id": self.current_deployment_state_id,
            "env_scope_type": self.env_scope_type,
            "env_id": self.env_id,
            "env_type": self.env_type,
            "environment_host_mapping_id": self.environment_host_mapping_id,
            "target_key": self.target_key,
            "package_key": self.package_key,
            "package_name": self.package_name,
            "current_version": self.current_version,
            "source": self.source,
            "status": self.status,
            "updated_by": self.updated_by,
            "deployment_request_id": self.deployment_request_id,
            "server_role_key": mapping.server_role.role_key if mapping and mapping.server_role else None,
            "hostname": host.hostname if host else None,
            "host_id": host.host_id if host else None,
            "updated_at": format_datetime(self.updated_at),
            "notes": self.notes,
        }
