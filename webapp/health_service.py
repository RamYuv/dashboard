"""Backward-compatible import wrapper for monitoring health helpers."""

from monitoring.services.health_service import (
    ENVIRONMENT_HEALTH_TARGETS,
    POLL_INTERVAL_SECONDS,
    EnvironmentHealthMonitor,
    build_dummy_environment_snapshot,
    health_monitor,
)

__all__ = [
    "ENVIRONMENT_HEALTH_TARGETS",
    "POLL_INTERVAL_SECONDS",
    "EnvironmentHealthMonitor",
    "build_dummy_environment_snapshot",
    "health_monitor",
]
