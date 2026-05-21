"""Authentication and access control service."""

import logging
from functools import wraps
from flask import session, redirect, url_for, flash

from .models import User
from .access_policy import (
    can_access_env_team_screen,
    can_access_screen,
    get_allowed_screens,
    get_screen_by_endpoint,
)

logger = logging.getLogger(__name__)


def current_user():
    """Get the currently logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


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
