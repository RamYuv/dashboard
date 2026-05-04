"""
Application-wide constants and configuration values.
"""

# Role and Team Definitions
VALID_ROLES = ["user", "qa", "manager", "admin"]
VALID_TEAMS = ["alpha", "beta", "support", "qa", "env"]
VALID_BOOKING_TYPES = ["RESERVATION"]

BOOKING_STATUS = {
    "SCHEDULED": "scheduled",
    "CANCELLED": "cancelled",
}

BOOKING_LIFECYCLE_STATUS = {
    "SCHEDULED": "scheduled",
    "ACTIVE": "active",
    "COMPLETED": "completed",
    "CANCELLED": "cancelled",
}

BOOKING_STATUS_ALIASES = {
    # Legacy persisted values kept for backward compatibility.
    "INACTIVE": "inactive",
    "EXPIRED": "expired",
}

BOOKING_MUTABLE_LIFECYCLE_STATUSES = {
    BOOKING_LIFECYCLE_STATUS["SCHEDULED"],
}

# Screen Configuration
SCREENS = [
    {
        "endpoint": "admin_screen",
        "title": "Admin Screen",
        "description": "Only users with the admin role can open this page.",
        "roles": ["admin"],
        "teams": [],
    },
    {
        "endpoint": "manager_screen",
        "title": "Manager Screen",
        "description": "Managers and admins can open this page.",
        "roles": ["manager", "admin"],
        "teams": [],
    },
    {
        "endpoint": "alpha_screen",
        "title": "Alpha Team Screen",
        "description": "Only members of the Alpha team can open this page.",
        "roles": ["admin"],
        "teams": ["alpha"],
    },
    {
        "endpoint": "general_screen",
        "title": "General Screen",
        "description": "Every logged-in user can open this page.",
        "roles": VALID_ROLES,
        "teams": VALID_TEAMS,
    },
    {
        "endpoint": "booking_screen",
        "title": "Environment Booking",
        "description": "Book environments and manage your own reservations.",
        "roles": VALID_ROLES,
        "teams": VALID_TEAMS,
    },
    {
        "endpoint": "environment_health",
        "title": "Environment Health Dashboard",
        "description": "View live environment health and activity for the ENV team.",
        "roles": ["admin"],
        "teams": ["env"],
    },
]

# Default Seed Data
DEFAULT_ENVIRONMENTS = [
    ("DEV-01", "DEV"),
    ("DEV-02", "DEV"),
    ("ST-01", "ST"),
    ("QA-01", "QA"),
    ("QA-02", "QA"),
    ("UAT-01", "UAT"),
    ("PERF-01", "PERF"),
]

DEFAULT_USERS = [
    {
        "user_id": "admin",
        "email_id": "admin@example.com",
        "name": "Admin User",
        "password": "adminpass",
        "team": "env",
        "role": "admin",
    },
    {
        "user_id": "qa1",
        "email_id": "qa1@example.com",
        "name": "QA User",
        "password": "qapass",
        "team": "qa",
        "role": "qa",
    },
    {
        "user_id": "user1",
        "email_id": "user1@example.com",
        "name": "Normal User",
        "password": "userpass",
        "team": "alpha",
        "role": "user",
    },
]

DEFAULT_HOSTS = [
    {
        "hostname": "Core",
        "ip_address": "10.0.0.10",
        "domain": "APP",
        "description": "Shared host for Core deployments",
    },
    {
        "hostname": "Gateway",
        "ip_address": "10.0.0.11",
        "domain": "APP",
        "description": "Shared host for Gateway deployments",
    },
    {
        "hostname": "PayGet",
        "ip_address": "10.0.0.12",
        "domain": "PAYGET",
        "description": "Shared host for PayGet deployments",
    },
    {
        "hostname": "CoreDB",
        "ip_address": "10.0.0.13",
        "domain": "DB",
        "description": "Reserved host entry for CoreDB",
    },
    {
        "hostname": "DB",
        "ip_address": "10.0.0.14",
        "domain": "DB",
        "description": "Shared host for DB deployments",
    },
    {
        "hostname": "Dev",
        "ip_address": "10.0.0.15",
        "domain": "TOOLS",
        "description": "Reserved host entry for Dev",
    },
    {
        "hostname": "Dev-Tool01",
        "ip_address": "10.0.0.16",
        "domain": "TOOLS",
        "description": "Shared host for Tools package tool1",
    },
    {
        "hostname": "Dev-Tool02",
        "ip_address": "10.0.0.17",
        "domain": "TOOLS",
        "description": "Shared host for Tools package tool2",
    },
]

DEFAULT_SERVER_ROLES = [
    {"role_key": "Core", "role_type": "TCS_APP"},
    {"role_key": "Gateway", "role_type": "TCS_APP"},
    {"role_key": "PayGet", "role_type": "PAYGET"},
    {"role_key": "CoreDB", "role_type": "DB"},
    {"role_key": "DB", "role_type": "DB"},
    {"role_key": "Dev", "role_type": "TOOLS"},
    {"role_key": "Dev-Tool01", "role_type": "TOOLS"},
    {"role_key": "Dev-Tool02", "role_type": "TOOLS"},
]

_DEFAULT_HOST_ROLE_MATRIX = [
    ("Core", "Core"),
    ("Gateway", "Gateway"),
    ("PayGet", "PayGet"),
    ("DB", "DB"),
    ("Dev-Tool01", "Dev-Tool01"),
    ("Dev-Tool02", "Dev-Tool02"),
]

DEFAULT_ENVIRONMENT_HOST_MAPPINGS = [
    {
        "env_id": env_id,
        "env_type": env_type,
        "is_shared": False,
        "server_role_key": role_key,
        "hostname": hostname,
        "deployment_user": "user1",
        "deployment_password": "pass1",
    }
    for env_id, env_type in DEFAULT_ENVIRONMENTS
    for role_key, hostname in _DEFAULT_HOST_ROLE_MATRIX
    if env_type == "DEV" or role_key not in {"Dev-Tool01", "Dev-Tool02"}
]

DEFAULT_ENVIRONMENT_HOST_MAPPINGS.extend([
    {
        "env_id": None,
        "env_type": "DEV",
        "is_shared": True,
        "server_role_key": "Dev-Tool01",
        "hostname": "Dev-Tool01",
        "deployment_user": "user1",
        "deployment_password": "pass1",
    },
    {
        "env_id": None,
        "env_type": "DEV",
        "is_shared": True,
        "server_role_key": "Dev-Tool02",
        "hostname": "Dev-Tool02",
        "deployment_user": "user1",
        "deployment_password": "pass1",
    },
])

# Component Version Definitions
COMPONENT_VERSIONS = {
    "TCS": ["1.0.0", "1.1.0", "2.0.0"],
    "TCS_APP": ["1.0.0", "1.1.0", "2.0.0"],
    "PAYGET": ["1.0.0", "1.1.0", "2.0.0"],
    "DB": ["schema-2026.01", "schema-2026.02"],
    "TCS_DB": ["schema-2026.01", "schema-2026.02"],
    "PAYUI": ["1.0.0", "1.1.0", "2.0.0"],
    "TCS_PAYUI": ["1.0.0", "1.1.0", "2.0.0"],
    "PAM": ["pam-4.5", "pam-4.6"],
    "TOOLS": ["latest", "stable", "lts"],
    "MQ": ["mq-9.3", "mq-9.4"],
}

PACKAGE_VERSIONS = {
    "tool1": ["1.0.0", "1.1.0", "1.2.0"],
    "tool2": ["2.0.0", "2.1.0", "2.2.0"],
    "tool3": ["3.0.0", "3.1.0", "3.2.0"],
}
