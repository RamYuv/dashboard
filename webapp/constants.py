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
        "hostname": "Gatway",
        "ip_address": "10.0.0.11",
        "domain": "APP",
        "description": "Shared host for Gatway deployments",
    },
    {
        "hostname": "PAYAPP",
        "ip_address": "10.0.0.12",
        "domain": "PAYAPP",
        "description": "Shared host for PayApp deployments",
    },
    {
        "hostname": "CoreDB",
        "ip_address": "10.0.0.13",
        "domain": "DB",
        "description": "Shared host for CoreDB deployments",
    },
    {
        "hostname": "CosDB",
        "ip_address": "10.0.0.14",
        "domain": "DB",
        "description": "Shared host for CosDB deployments",
    },
    {
        "hostname": "TOOL_SERVER",
        "ip_address": "10.0.0.15",
        "domain": "TOOLS",
        "description": "Shared host for tool server workloads",
    },
]

DEFAULT_SERVER_ROLES = [
    {"role_key": "Core", "role_type": "TCS_APP"},
    {"role_key": "Gatway", "role_type": "TCS_APP"},
    {"role_key": "PAYAPP", "role_type": "PAYAPP"},
    {"role_key": "CoreDB", "role_type": "DB"},
    {"role_key": "CosDB", "role_type": "DB"},
    {"role_key": "TOOL_SERVER", "role_type": "TOOLS"},
]

_DEFAULT_HOST_ROLE_MATRIX = [
    ("Core", "Core"),
    ("Gatway", "Gatway"),
    ("PAYAPP", "PAYAPP"),
    ("CoreDB", "CoreDB"),
    ("CosDB", "CosDB"),
    ("TOOL_SERVER", "TOOL_SERVER"),
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
]

# Component Version Definitions
COMPONENT_VERSIONS = {
    "TCS_APP": ["1.0.0", "1.1.0", "2.0.0"],
    "PAYAPP": ["1.0.0", "1.1.0", "2.0.0"],
    "DB": ["schema-2026.01", "schema-2026.02"],
    "TOOLS": ["latest", "stable", "lts"],
}

PACKAGE_VERSIONS = {
    "tool1": ["1.0.0", "1.1.0", "1.2.0"],
    "tool2": ["2.0.0", "2.1.0", "2.2.0"],
    "tool3": ["3.0.0", "3.1.0", "3.2.0"],
    "tool5": ["5.0.0", "5.1.0", "5.2.0"],
}
