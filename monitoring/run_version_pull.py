"""Standalone runner for the version-pull worker.

This script can be invoked from cron or another scheduler and will perform one
version-pull pass and exit with status code 0 on success. It mirrors the
structure of the existing `monitoring/monitoring_process_service.py` entrypoint but executes
only a single run.
"""

import logging
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from monitoring.factory import create_monitoring_app
from monitoring.version_pull_worker import VersionPullWorker

logger = logging.getLogger(__name__)


def run_once():
    """Create the monitoring app, run one version pull, and return the summary."""
    app = create_monitoring_app()
    with app.app_context():
        worker = getattr(app.container, "version_worker", None) or VersionPullWorker(app)
        summary = worker.refresh()
        logger.info("Version pull completed: %s", summary)
        return summary


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        run_once()
        sys.exit(0)
    except Exception:
        logger.exception("Version pull runner failed.")
        sys.exit(2)


if __name__ == "__main__":
    main()
