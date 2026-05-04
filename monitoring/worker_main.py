"""Dedicated monitoring worker and embeddable background service.

This module supports two operating modes:
1. Standalone worker process via ``python monitoring/worker_main.py``
2. Embedded background thread started by ``run.py`` for local/dev usage

Both modes call the same monitoring refresh logic so behavior stays consistent.
"""

import logging
import os
import signal
import sys
import threading
import time


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from webapp import create_app


logger = logging.getLogger(__name__)


class BackgroundMonitoringService(object):
    """Run monitoring refresh in one background thread.

    The service is intentionally process-local. For local ``run.py`` usage this
    keeps lifecycle simple: when the Flask process stops, the monitoring thread
    is asked to stop and joined cleanly. For production, prefer the standalone
    worker entrypoint below so monitoring is isolated from web serving.
    """

    def __init__(self, app, interval_seconds):
        self.app = app
        self.interval_seconds = max(5, int(interval_seconds or 30))
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background thread if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("Background monitoring service is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="env-monitor-background"
        )
        self._thread.daemon = True
        self._thread.start()
        logger.info(
            "Started background monitoring service with %s second interval.",
            self.interval_seconds
        )

    def stop(self):
        """Request thread shutdown."""
        logger.info("Stopping background monitoring service.")
        self._stop_event.set()

    def join(self, timeout=None):
        """Wait for the background thread to exit."""
        if self._thread is not None:
            self._thread.join(timeout)
            logger.info("Background monitoring service stopped.")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    snapshot = self.app.container.env_worker.refresh()
                    logger.info(
                        "Monitoring refresh completed. Snapshot count=%s",
                        len(snapshot or {})
                    )
            except Exception:
                logger.exception("Monitoring refresh failed in background service.")
            if self._stop_event.wait(self.interval_seconds):
                break


def run_worker():
    """Run monitoring as a standalone dedicated worker process."""
    app = create_app()
    service = BackgroundMonitoringService(
        app,
        app.config.get("MONITOR_REFRESH_SECONDS", 30),
    )
    stop_requested = {"value": False}

    def handle_stop(signum, frame):
        stop_requested["value"] = True
        logger.info("Received stop signal %s for monitoring worker.", signum)
        service.stop()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    logger.info("Starting standalone monitoring worker process.")
    service.start()
    try:
        while not stop_requested["value"]:
            time.sleep(0.5)
    finally:
        service.stop()
        service.join(5)
        logger.info("Standalone monitoring worker process exited.")


if __name__ == "__main__":
    run_worker()
