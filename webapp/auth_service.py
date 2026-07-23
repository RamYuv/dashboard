"""Authentication and access control service."""

import logging
from functools import wraps
from flask import session, redirect, url_for, flash, request

from .models import User
from .access_policy import (
    can_access_env_team_screen,
    can_access_screen,
    get_allowed_screens,
    get_screen_by_endpoint,
)

logger = logging.getLogger(__name__)
PASSWORD_CHANGE_ALLOWED_ENDPOINTS = {
    "main.change_hzn",
    "main.verify_hzn_change",
    "main.logout",
    "static",
}


def current_user():
    """Get the currently logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def password_change_required(user=None):
    """Return whether the current user must change their password before proceeding."""
    target_user = user if user is not None else current_user()
    return bool(getattr(target_user, "must_change_password", False))


def should_redirect_to_password_change():
    """Return whether the current request should be limited to password-change pages."""
    user = current_user()
    endpoint = request.endpoint or ""
    if user is None or not password_change_required(user):
        return False
    return endpoint not in PASSWORD_CHANGE_ALLOWED_ENDPOINTS


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
