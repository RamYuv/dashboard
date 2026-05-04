"""Backward-compatible import wrapper for deployment request service."""

from .services.deployment_request_service import (
    DEPLOYMENT_REQUEST_STATUSES,
    DeploymentRequestService,
)

__all__ = ["DEPLOYMENT_REQUEST_STATUSES", "DeploymentRequestService"]
