"""
Email delivery helpers backed by the local sendmail binary.
"""

import os
import subprocess
from email.message import EmailMessage
from email.utils import formatdate

from flask import current_app


class EmailDeliveryError(RuntimeError):
    """Raised when an email cannot be delivered."""


class SendmailEmailService:
    """Send outbound email through a local sendmail-compatible binary."""

    @staticmethod
    def _resolve_sendmail_path():
        """Return the configured sendmail path without changing fallback behavior."""
        configured_path = current_app.config.get("SENDMAIL_PATH") or "/usr/sbin/sendmail"
        if os.path.exists(configured_path):
            return configured_path
        return configured_path

    @staticmethod
    def send_message(subject, recipients, body, reply_to=None):
        """Send one plaintext message through the configured sendmail binary."""
        normalized_recipients = [item.strip() for item in (recipients or []) if item and item.strip()]
        if not normalized_recipients:
            raise EmailDeliveryError("No recipients were provided.")

        if not current_app.config.get("SENDMAIL_ENABLED", True):
            raise EmailDeliveryError("Sendmail delivery is disabled by configuration.")

        sender = (current_app.config.get("MAIL_SENDER") or "envbooking@localhost").strip()
        sendmail_path = SendmailEmailService._resolve_sendmail_path()
        if not os.path.exists(sendmail_path):
            raise EmailDeliveryError("Sendmail binary not found at '{}'.".format(sendmail_path))

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(normalized_recipients)
        message["Date"] = formatdate(localtime=True)
        if reply_to:
            message["Reply-To"] = reply_to
        message.set_content(body)

        result = subprocess.run(
            [sendmail_path, "-t", "-i"],
            input=message.as_bytes(),
            capture_output=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise EmailDeliveryError(
                "Sendmail exited with code {}. {}".format(result.returncode, stderr or "No stderr output.")
            )
