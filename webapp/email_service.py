"""Backward-compatible import wrapper for email service."""

from .services.email_service import EmailDeliveryError, SendmailEmailService

__all__ = ["EmailDeliveryError", "SendmailEmailService"]
