"""Local application runner."""

import atexit
import logging
import signal

from webapp import create_app
from monitoring.worker_main import MonitoringProcessService

logger = logging.getLogger(__name__)

app = create_app()
monitor_service = MonitoringProcessService()


def stop_monitoring_service():
    """Stop the child monitoring process cleanly."""
    logger.info("Stopping monitoring process from run.py.")
    monitor_service.stop()


def _handle_signal(signum, frame):
    logger.info("Received stop signal %s for envbooking application.", signum)
    stop_monitoring_service()
    raise SystemExit(0)

if __name__ == '__main__':
    atexit.register(stop_monitoring_service)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    logger.info(
        "Starting envbooking web app on %s:%s with child monitoring process.",
        app.config.get('APP_HOST', '127.0.0.1'),
        app.config.get('APP_PORT', 5000)
    )
    monitor_service.start()
    try:
        app.run(
            host=app.config.get('APP_HOST', '127.0.0.1'),
            port=app.config.get('APP_PORT', 5000),
            debug=True,
            use_reloader=False
        )
    finally:
        stop_monitoring_service()
