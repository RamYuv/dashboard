"""Legacy in-process monitoring scheduler.

This module provides a small background-thread scheduler that repeatedly calls
``worker.refresh()`` inside the current process.

Current project direction:
- Local/dev execution now uses ``BackgroundMonitoringService`` from
  ``monitoring.worker_main`` via ``run.py``.
- Production-style execution should use the standalone monitoring worker
  entrypoint in ``monitoring.worker_main``.

This class remains useful as a simple reusable scheduler primitive and as
reference for the older embedded-thread approach, but it is no longer the
primary runtime path for monitoring refresh.
"""

import logging
import threading
import time


logger = logging.getLogger(__name__)


class MonitoringScheduler(object):
    """Run ``worker.refresh()`` repeatedly on one daemon thread.

    The scheduler owns only timing/thread lifecycle. It does not know how
    monitoring works internally; it just triggers the supplied worker object
    at a fixed interval until ``stop()`` is called.
    """

    def __init__(self, app, worker, interval_seconds):
        """Create a scheduler bound to one app/worker pair."""
        self.app = app
        self.worker = worker
        self.interval_seconds = max(5, int(interval_seconds or 30))
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the daemon thread if it is not already running."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="env-monitor-scheduler"
        )
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """Request clean shutdown of the scheduler loop."""
        self._stop_event.set()

    def _run(self):
        """Scheduler loop: refresh, then sleep until next interval or stop."""
        while not self._stop_event.is_set():
            try:
                self.worker.refresh()
            except Exception:
                logger.exception("Background monitoring refresh failed.")

            if self._stop_event.wait(self.interval_seconds):
                break
