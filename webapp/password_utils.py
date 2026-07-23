"""Password hashing and verification helpers with legacy compatibility."""

import hashlib
import hmac
import secrets

from werkzeug.security import check_password_hash, generate_password_hash as generate_hzn_hash

from .models import DefaultPassword


def hash_password(password):
    """Hash a password using the Phase 1 legacy-compatible salted SHA-256 format."""
    salt = secrets.token_hex(16)
    password_value = "" if password is None else str(password)
    hashed = hashlib.sha256((salt + password_value).encode("utf-8")).hexdigest()
    return "{}${}".format(salt, hashed)


def verify_password(stored_password, provided_password):
    """Verify a password against current or legacy storage formats."""
    stored_value = str(stored_password or "").strip()
    provided_value = "" if provided_password is None else str(provided_password)
    if not stored_value:
        return False

    try:
        if check_password_hash(stored_value, provided_value):
            return True
    except (TypeError, ValueError):
        pass

    if "$" in stored_value:
        salt, expected_hash = stored_value.split("$", 1)
        computed_hash = hashlib.sha256((salt + provided_value).encode("utf-8")).hexdigest()
        if hmac.compare_digest(computed_hash, expected_hash):
            return True

    return hmac.compare_digest(stored_value, provided_value)


def password_matches_default_value(entered_password):
    """Return whether the entered password matches any configured default password."""
    for default_password in DefaultPassword.ordered().all():
        if verify_password(default_password.password_value, entered_password):
            return True
    return False


def user_is_using_default_password(user, entered_password):
    """Return whether a user's valid password entry is still one of the configured defaults."""
    if user is None or not verify_password(getattr(user, "hzn_hash", None), entered_password):
        return False
    return password_matches_default_value(entered_password)


def should_force_password_change(user, entered_password):
    """Return whether the user must be redirected into the password-change flow."""
    if user is None:
        return False
    return bool(getattr(user, "must_change_password", False)) or user_is_using_default_password(
        user,
        entered_password,
    )


def sync_password_change_requirement(user, entered_password):
    """Persist the password-change flag when a user logs in with a default password."""
    if user is None:
        return False
    if getattr(user, "must_change_password", False):
        return True
    if not user_is_using_default_password(user, entered_password):
        return False
    user.must_change_password = True
    return True
