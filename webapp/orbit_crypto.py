"""Orbit-based encryption helpers for server access passwords."""

import base64

from cryptography.fernet import Fernet, InvalidToken

from .models import Orbit


class OrbitCryptoError(Exception):
    """Raised when Orbit-managed encryption or decryption cannot be completed."""


def get_primary_orbit_key():
    """Return the configured primary orbit key value."""
    record = Orbit.primary()
    return (record.orb_value or "").strip() if record is not None else ""


def is_valid_orbit_key(orbit_value):
    """Return whether the provided orbit value is a valid Fernet key."""
    normalized_value = (orbit_value or "").strip()
    if not normalized_value:
        return False
    try:
        decoded_value = base64.urlsafe_b64decode(normalized_value)
        if len(decoded_value) != 32:
            return False
        Fernet(normalized_value.encode("utf-8"))
        return True
    except (TypeError, ValueError):
        return False


def looks_like_encrypted_server_password(password_value):
    """Return whether the value resembles a Fernet token from the legacy system."""
    normalized_value = (password_value or "").strip()
    return normalized_value.startswith("gAAAAA")


def encrypt_server_password(password_value, orbit_value=None):
    """Encrypt a server password when an orbit key is available."""
    normalized_password = "" if password_value is None else str(password_value)
    if not normalized_password:
        return normalized_password

    orbit_key = (orbit_value or get_primary_orbit_key() or "").strip()
    if not orbit_key:
        return normalized_password
    if not is_valid_orbit_key(orbit_key):
        raise OrbitCryptoError("Configured orbit key is invalid.")

    # Avoid double-encrypting existing stored secrets.
    if looks_like_encrypted_server_password(normalized_password):
        try:
            decrypt_server_password(normalized_password, orbit_key)
            return normalized_password
        except OrbitCryptoError:
            pass

    token = Fernet(orbit_key.encode("utf-8")).encrypt(normalized_password.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_server_password(password_value, orbit_value=None):
    """Decrypt a stored server password, while still allowing plaintext compatibility."""
    normalized_password = "" if password_value is None else str(password_value).strip()
    if not normalized_password:
        return normalized_password

    orbit_key = (orbit_value or get_primary_orbit_key() or "").strip()
    if not orbit_key:
        if looks_like_encrypted_server_password(normalized_password):
            raise OrbitCryptoError("No orbit key is configured for encrypted server passwords.")
        return normalized_password
    if not is_valid_orbit_key(orbit_key):
        raise OrbitCryptoError("Configured orbit key is invalid.")

    try:
        decrypted_value = Fernet(orbit_key.encode("utf-8")).decrypt(normalized_password.encode("utf-8"))
        return decrypted_value.decode("utf-8")
    except InvalidToken:
        if looks_like_encrypted_server_password(normalized_password):
            raise OrbitCryptoError("Encrypted server password could not be decrypted with the current orbit key.")
        return normalized_password
