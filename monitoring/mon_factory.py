"""Backward-compatible wrapper for the monitoring app factory.

Prefer importing ``create_monitoring_app`` from ``monitoring.factory``.
This module remains only so older imports do not break immediately.
"""

import logging

from monitoring.factory import create_monitoring_app as _create_monitoring_app


logger = logging.getLogger(__name__)


def create_monitoring_app():
    """Return the monitoring-only Flask app and log deprecation guidance."""
    logger.warning(
        "monitoring.mon_factory is deprecated; import create_monitoring_app "
        "from monitoring.factory instead."
    )
    return _create_monitoring_app()
