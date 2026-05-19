"""
Application-wide constants and configuration values.
"""

# Team Definitions
VALID_TEAMS = ["alpha", "beta", "support", "qa", "env", "access_admin"]
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
        "endpoint": "user_management_screen",
        "title": "User Management",
        "description": "Manage user permissions and team membership.",
        "roles": ["admin"],
        "teams": ["access_admin"],
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
        "roles": [],
        "teams": VALID_TEAMS,
    },
    {
        "endpoint": "booking_screen",
        "title": "Environment Booking",
        "description": "Book environments and manage your own reservations.",
        "roles": [],
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
        "role": "manager",
    },
    {
        "user_id": "user1",
        "email_id": "user1@example.com",
        "name": "user1",
        "password": "userpass",
        "team": "alpha",
        "role": "user",
    },
]

DEFAULT_SERVER_TYPES = [
    {"server_type_key": "Core", "target_type": "TCS_APP"},
    {"server_type_key": "Getway", "target_type": "TCS_APP"},
    {"server_type_key": "PAYApp", "target_type": "PAYAPP"},
    {"server_type_key": "CoreDb", "target_type": "DB"},
    {"server_type_key": "LGDB", "target_type": "DB"},
    {"server_type_key": "Tool_server", "target_type": "TOOLS"},
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
