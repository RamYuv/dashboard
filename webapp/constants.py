"""
Application-wide constants and configuration values.
"""

# Team Definitions
VALID_TEAMS = ["alpha", "beta", "support", "qa", "env", "dev", "access_admin"]
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
