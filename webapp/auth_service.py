"""
Authentication and access control service.
"""

import logging
from functools import wraps
from flask import session, redirect, url_for, flash

from .models import User
from .constants import SCREENS

logger = logging.getLogger(__name__)


def current_user():
    """Get the currently logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def can_access_screen(user, screen):
    """Check if user has permission to access a screen."""
    if user is None:
        return False
    user_team_names = {
        (team_name or "").strip().lower()
        for team_name in getattr(user, "team_names", []) or []
    }
    screen_team_names = {
        (team_name or "").strip().lower()
        for team_name in screen["teams"]
    }

    endpoint = (screen.get("endpoint") or "").strip()
    if endpoint == "user_management_screen":
        return user.role == "admin" and "access_admin" in user_team_names

    if user.role == "admin":
        return True

    return user.role in screen["roles"] or bool(user_team_names & screen_team_names)


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
    return "env" in {
        (team_name or "").strip().lower()
        for team_name in getattr(user, "team_names", []) or []
    }


def get_screen_by_endpoint(endpoint):
    """Get screen configuration by endpoint."""
    return next((item for item in SCREENS if item["endpoint"] == endpoint), None)


def login_required(view):
    """Decorator to require login for a route."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if current_user() is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped_view


def screen_required(endpoint):
    """Decorator to require specific screen access."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user()
            screen = get_screen_by_endpoint(endpoint)

            if user is None:
                flash("Please log in first.", "warning")
                return redirect(url_for("main.login"))

            if screen is None or not can_access_screen(user, screen):
                logger.warning(
                    "Screen access denied for user %s on endpoint %s",
                    user.username if user else "anonymous",
                    endpoint,
                )
                flash("You do not have access to that screen.", "danger")
                return redirect(url_for("main.dashboard"))

            return view(*args, **kwargs)

        return wrapped_view

    return decorator
