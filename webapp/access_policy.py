"""Centralized authorization policy rules."""

from .constants import VALID_TEAMS


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


def _normalized_team_names(user):
    return {
        (team_name or "").strip().lower()
        for team_name in getattr(user, "team_names", []) or []
    }


def can_access_screen(user, screen):
    """Check if user has permission to access a screen."""
    if user is None:
        return False

    user_team_names = _normalized_team_names(user)
    screen_team_names = {
        (team_name or "").strip().lower()
        for team_name in screen["teams"]
    }
    required_roles = {
        (role or "").strip().lower()
        for role in screen.get("roles", [])
    }

    if user.role == "admin":
        if screen.get("endpoint") == "user_management_screen":
            return "access_admin" in user_team_names
        return True

    return user.role in required_roles or bool(user_team_names & screen_team_names)


def get_allowed_screens(user):
    """Get all screens accessible by the user."""
    if user is None:
        return []
    return [screen for screen in SCREENS if can_access_screen(user, screen)]


def can_access_env_team_screen(user):
    """Return whether the user can access ENV-team deployment operations."""
    if user is None:
        return False
    if user.role == "admin":
        return True
    return "env" in _normalized_team_names(user)


def get_screen_by_endpoint(endpoint):
    """Get screen configuration by endpoint."""
    return next((item for item in SCREENS if item["endpoint"] == endpoint), None)
