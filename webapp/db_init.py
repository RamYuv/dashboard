"""
Database initialization and seeding functions.
"""

from sqlalchemy import inspect, text
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


def init_db():
    """Initialize database tables and seed default data."""
    migrate_schema()
    seed_all_default_data()


def seed_all_default_data():
    """Seed all default application data."""
    seed_default_environments()
    seed_default_teams()
    seed_default_users()
    seed_default_team_memberships()
    seed_default_hosts()
    seed_default_server_roles()
    seed_default_environment_host_mappings()


def reset_all_table_data():
    """Delete all application data and rebuild the default seed set."""
    delete_order = [
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

    for model in delete_order:
        db.session.query(model).delete()

    db.session.commit()
    seed_all_default_data()


def _rename_table_if_needed(existing_tables, old_name, new_name):
    if old_name in existing_tables and new_name not in existing_tables:
        db.session.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
        db.session.commit()


def _rename_column_if_needed(inspector, table_name, old_name, new_name):
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if old_name in existing_columns and new_name not in existing_columns:
        db.session.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name}"))
        db.session.commit()


def migrate_schema():
    """Apply lightweight schema changes for SQLite-backed local environments."""
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    _rename_table_if_needed(existing_tables, "logical_servers", "server_roles")
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    _rename_table_if_needed(existing_tables, "environment_logical_servers", "environment_host_mappings")
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    if "server_roles" in existing_tables:
        _rename_column_if_needed(inspector, "server_roles", "logical_server_id", "server_role_id")
        inspector = inspect(db.engine)
        _rename_column_if_needed(inspector, "server_roles", "logical_name", "role_key")
        inspector = inspect(db.engine)
        _rename_column_if_needed(inspector, "server_roles", "component_type", "role_type")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

    if "environment_host_mappings" in existing_tables:
        _rename_column_if_needed(inspector, "environment_host_mappings", "id", "environment_host_mapping_id")
        inspector = inspect(db.engine)
        _rename_column_if_needed(inspector, "environment_host_mappings", "logical_server_id", "server_role_id")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

    if "deployments" in existing_tables:
        _rename_column_if_needed(inspector, "deployments", "environment_logical_server_id", "environment_host_mapping_id")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

    if "current_deployment_state" in existing_tables:
        _rename_column_if_needed(inspector, "current_deployment_state", "environment_logical_server_id", "environment_host_mapping_id")
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

    _migrate_environment_bookings_table(inspector, existing_tables)
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    _migrate_deployment_requests_table(inspector, existing_tables)
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    table_column_updates = {
        "users": {
            "is_active": "ALTER TABLE users ADD COLUMN is_active BOOLEAN",
        },
        "environments": {
            "is_active": "ALTER TABLE environments ADD COLUMN is_active BOOLEAN",
            "created_at": "ALTER TABLE environments ADD COLUMN created_at DATETIME",
        },
        "hosts": {
            "domain": "ALTER TABLE hosts ADD COLUMN domain VARCHAR(50)",
            "is_active": "ALTER TABLE hosts ADD COLUMN is_active BOOLEAN",
        },
        "server_roles": {
            "description": "ALTER TABLE server_roles ADD COLUMN description TEXT",
        },
        "environment_host_mappings": {
            "env_type": "ALTER TABLE environment_host_mappings ADD COLUMN env_type VARCHAR(50)",
            "is_shared": "ALTER TABLE environment_host_mappings ADD COLUMN is_shared BOOLEAN DEFAULT 0",
        },
        "deployment_requests": {
            "env_id": "ALTER TABLE deployment_requests ADD COLUMN env_id VARCHAR(50)",
            "requested_env_type": "ALTER TABLE deployment_requests ADD COLUMN requested_env_type VARCHAR(50)",
            "env_scope_type": "ALTER TABLE deployment_requests ADD COLUMN env_scope_type VARCHAR(20) DEFAULT 'ENV'",
            "requested_by": "ALTER TABLE deployment_requests ADD COLUMN requested_by VARCHAR(50)",
            "planned_start_time": "ALTER TABLE deployment_requests ADD COLUMN planned_start_time DATETIME",
            "target_key": "ALTER TABLE deployment_requests ADD COLUMN target_key VARCHAR(50)",
            "component_name": "ALTER TABLE deployment_requests ADD COLUMN component_name VARCHAR(100)",
            "selected_packages": "ALTER TABLE deployment_requests ADD COLUMN selected_packages TEXT",
            "jira_id": "ALTER TABLE deployment_requests ADD COLUMN jira_id VARCHAR(50)",
            "description": "ALTER TABLE deployment_requests ADD COLUMN description TEXT",
            "remarks": "ALTER TABLE deployment_requests ADD COLUMN remarks TEXT",
            "status": "ALTER TABLE deployment_requests ADD COLUMN status VARCHAR(50)",
            "execution_mode": "ALTER TABLE deployment_requests ADD COLUMN execution_mode VARCHAR(20)",
            "approved_by": "ALTER TABLE deployment_requests ADD COLUMN approved_by VARCHAR(50)",
            "approved_at": "ALTER TABLE deployment_requests ADD COLUMN approved_at DATETIME",
            "completed_at": "ALTER TABLE deployment_requests ADD COLUMN completed_at DATETIME",
            "failure_reason": "ALTER TABLE deployment_requests ADD COLUMN failure_reason TEXT",
            "last_notified_at": "ALTER TABLE deployment_requests ADD COLUMN last_notified_at DATETIME",
            "service_types": "ALTER TABLE deployment_requests ADD COLUMN service_types TEXT DEFAULT '[]'",
            "updated_at": "ALTER TABLE deployment_requests ADD COLUMN updated_at DATETIME",
        },
        "deployments": {
            "package_key": "ALTER TABLE deployments ADD COLUMN package_key VARCHAR(100)",
            "package_name": "ALTER TABLE deployments ADD COLUMN package_name VARCHAR(150)",
            "started_at": "ALTER TABLE deployments ADD COLUMN started_at DATETIME",
            "completed_at": "ALTER TABLE deployments ADD COLUMN completed_at DATETIME",
            "created_at": "ALTER TABLE deployments ADD COLUMN created_at DATETIME",
            "log_excerpt": "ALTER TABLE deployments ADD COLUMN log_excerpt TEXT",
        },
    }

    for table_name, column_updates in table_column_updates.items():
        if table_name not in existing_tables:
            continue

        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name, statement in column_updates.items():
            if column_name not in existing_columns:
                db.session.execute(text(statement))

    db.create_all()
    seed_default_teams()
    _backfill_user_team_memberships(inspector)
    db.session.execute(text(
        """
        UPDATE environment_bookings
        SET status = CASE
            WHEN status IS NULL OR status = '' OR status = 'inactive' THEN 'scheduled'
            WHEN status = 'expired' THEN 'completed'
            ELSE status
        END
        WHERE status IS NULL OR status = '' OR status IN ('inactive', 'expired')
        """
    ))
    db.session.execute(text("UPDATE deployment_requests SET status = 'OPEN' WHERE status IS NULL OR status = ''"))
    db.session.execute(text("UPDATE deployment_requests SET env_scope_type = 'ENV' WHERE env_scope_type IS NULL OR env_scope_type = ''"))
    db.session.execute(text("UPDATE deployment_requests SET service_types = '[]' WHERE service_types IS NULL OR service_types = ''"))
    db.session.execute(text(
        """
        UPDATE environment_host_mappings
        SET env_type = (
            SELECT environments.env_type
            FROM environments
            WHERE environments.env_id = environment_host_mappings.env_id
        )
        WHERE env_type IS NULL OR env_type = ''
        """
    ))
    db.session.execute(text("UPDATE environment_host_mappings SET is_shared = 0 WHERE is_shared IS NULL"))
    db.session.commit()


def _migrate_environment_bookings_table(inspector, existing_tables):
    if "environment_bookings" not in existing_tables:
        return

    create_sql = db.session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'environment_bookings'"
    )).scalar() or ""
    normalized_sql = create_sql.lower()

    needs_booking_status_fix = "booking_status" in normalized_sql and "scheduled" not in normalized_sql
    needs_booking_type_fix = "deployment" in normalized_sql

    if not needs_booking_status_fix and not needs_booking_type_fix:
        return

    db.session.execute(text("PRAGMA foreign_keys=OFF"))
    db.session.execute(text(
        """
        CREATE TABLE environment_bookings__new (
            booking_id VARCHAR(50) NOT NULL PRIMARY KEY,
            env_id VARCHAR(50) NOT NULL,
            requested_by VARCHAR(50) NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            booking_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            description TEXT,
            user_timezone VARCHAR(80),
            created_at DATETIME,
            updated_at DATETIME NOT NULL,
            FOREIGN KEY(env_id) REFERENCES environments (env_id),
            FOREIGN KEY(requested_by) REFERENCES users (user_id),
            CONSTRAINT ck_booking_time_order CHECK (start_time < end_time),
            CONSTRAINT booking_type CHECK (booking_type IN ('RESERVATION')),
            CONSTRAINT booking_status CHECK (status IN ('inactive', 'scheduled', 'active', 'expired', 'completed', 'cancelled'))
        )
        """
    ))
    db.session.execute(text(
        """
        INSERT INTO environment_bookings__new (
            booking_id,
            env_id,
            requested_by,
            start_time,
            end_time,
            booking_type,
            status,
            description,
            user_timezone,
            created_at,
            updated_at
        )
        SELECT
            booking_id,
            env_id,
            requested_by,
            start_time,
            end_time,
            CASE
                WHEN booking_type = 'DEPLOYMENT' THEN 'RESERVATION'
                ELSE booking_type
            END,
            CASE
                WHEN status IS NULL OR status = '' OR status = 'inactive' THEN 'scheduled'
                WHEN status = 'expired' THEN 'completed'
                ELSE status
            END,
            description,
            user_timezone,
            created_at,
            COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        FROM environment_bookings
        """
    ))
    db.session.execute(text("DROP TABLE environment_bookings"))
    db.session.execute(text("ALTER TABLE environment_bookings__new RENAME TO environment_bookings"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_booking_env_time ON environment_bookings (env_id, start_time, end_time)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_booking_user_status ON environment_bookings (requested_by, status)"))
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    db.session.commit()


def _migrate_deployment_requests_table(inspector, existing_tables):
    if "deployment_requests" not in existing_tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("deployment_requests")}
    create_sql = db.session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'deployment_requests'"
    )).scalar() or ""
    normalized_sql = create_sql.lower()
    legacy_booking_link = "booking_id" in existing_columns
    legacy_required_component_fields = (
        "component_type varchar(50) not null" in normalized_sql or
        "component_name varchar(100) not null" in normalized_sql
    )
    if not legacy_booking_link and not legacy_required_component_fields:
        return

    env_id_expression = "dr.env_id"
    requested_by_expression = "dr.requested_by"
    planned_start_expression = "dr.planned_start_time"
    service_types_expression = "COALESCE(dr.service_types, '[]')" if "service_types" in existing_columns else "'[]'"
    booking_join = ""
    if legacy_booking_link:
        env_id_expression = "COALESCE(eb.env_id, dr.env_id)"
        requested_by_expression = "COALESCE(eb.requested_by, dr.requested_by)"
        planned_start_expression = "COALESCE(eb.start_time, dr.planned_start_time)"
        booking_join = "LEFT JOIN environment_bookings eb ON eb.booking_id = dr.booking_id"

    db.session.execute(text("PRAGMA foreign_keys=OFF"))
    db.session.execute(text(
        """
        CREATE TABLE deployment_requests__new (
            deployment_request_id VARCHAR(50) NOT NULL PRIMARY KEY,
            env_id VARCHAR(50) NOT NULL,
            requested_by VARCHAR(50) NOT NULL,
            planned_start_time DATETIME NOT NULL,
            build_id INTEGER,
            target_key VARCHAR(50) NOT NULL,
            component_type VARCHAR(50),
            component_name VARCHAR(100),
            requested_version VARCHAR(50) NOT NULL,
            selected_packages TEXT NOT NULL,
            testing_mode VARCHAR(50) NOT NULL DEFAULT '',
            service_types TEXT NOT NULL DEFAULT '[]',
            jira_id VARCHAR(50),
            description TEXT,
            remarks TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
            execution_mode VARCHAR(20),
            approved_by VARCHAR(50),
            approved_at DATETIME,
            completed_at DATETIME,
            failure_reason TEXT,
            last_notified_at DATETIME,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(env_id) REFERENCES environments (env_id),
            FOREIGN KEY(requested_by) REFERENCES users (user_id),
            FOREIGN KEY(approved_by) REFERENCES users (user_id),
            FOREIGN KEY(build_id) REFERENCES component_builds (build_id)
        )
        """
    ))
    db.session.execute(text(
        """
        INSERT INTO deployment_requests__new (
            deployment_request_id,
            env_id,
            requested_by,
            planned_start_time,
            build_id,
            target_key,
            component_type,
            component_name,
            requested_version,
            selected_packages,
            testing_mode,
            service_types,
            jira_id,
            description,
            remarks,
            status,
            execution_mode,
            approved_by,
            approved_at,
            completed_at,
            failure_reason,
            last_notified_at,
            created_at,
            updated_at
        )
        SELECT
            dr.deployment_request_id,
            COALESCE(""" + env_id_expression + """, 'UNKNOWN'),
            COALESCE(""" + requested_by_expression + """, 'admin'),
            COALESCE(""" + planned_start_expression + """, dr.created_at, CURRENT_TIMESTAMP),
            dr.build_id,
            COALESCE(dr.target_key, dr.component_type, 'TCS_APP'),
            dr.component_type,
            dr.component_name,
            COALESCE(dr.requested_version, ''),
            COALESCE(dr.selected_packages, '[]'),
            COALESCE(dr.testing_mode, ''),
            """ + service_types_expression + """,
            dr.jira_id,
            dr.description,
            dr.remarks,
            COALESCE(dr.status, 'OPEN'),
            dr.execution_mode,
            dr.approved_by,
            dr.approved_at,
            dr.completed_at,
            dr.failure_reason,
            dr.last_notified_at,
            dr.created_at,
            COALESCE(dr.updated_at, dr.created_at, CURRENT_TIMESTAMP)
        FROM deployment_requests dr
        """ + booking_join + """
        """
    ))
    db.session.execute(text("DROP TABLE deployment_requests"))
    db.session.execute(text("ALTER TABLE deployment_requests__new RENAME TO deployment_requests"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_dreq_status_created ON deployment_requests (status, created_at)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_dreq_env_status ON deployment_requests (env_id, status)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_dreq_component ON deployment_requests (component_type, component_name, requested_version)"))
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    db.session.commit()


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


def _backfill_user_team_memberships(inspector):
    """Populate team_members from legacy users.team/users.team_id columns when present."""
    if "users" not in inspector.get_table_names() or "team_members" not in inspector.get_table_names():
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "team_id" in user_columns:
        db.session.execute(text(
            """
            INSERT INTO team_members (user_id, team_id, role, created_at)
            SELECT
                users.user_id,
                users.team_id,
                COALESCE(users.role, 'user'),
                COALESCE(users.created_at, CURRENT_TIMESTAMP)
            FROM users
            WHERE users.team_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM team_members
                  WHERE team_members.user_id = users.user_id
                    AND team_members.team_id = users.team_id
              )
            """
        ))

    if "team" in user_columns:
        db.session.execute(text(
            """
            INSERT INTO team_members (user_id, team_id, role, created_at)
            SELECT
                users.user_id,
                teams.team_id,
                COALESCE(users.role, 'user'),
                COALESCE(users.created_at, CURRENT_TIMESTAMP)
            FROM users
            JOIN teams
              ON lower(teams.team_name) = lower(users.team)
            WHERE users.team IS NOT NULL
              AND users.team != ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM team_members
                  WHERE team_members.user_id = users.user_id
                    AND team_members.team_id = teams.team_id
              )
            """
        ))


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
