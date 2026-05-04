"""Local application runner.

This script starts the Flask web app and one embedded background monitoring
thread for local/dev usage. Stopping this process stops both the web server and
the monitoring thread, so there is no separate orphan worker to clean up.
"""

import atexit
import logging
import signal

from webapp import create_app
from monitoring.worker_main import BackgroundMonitoringService

logger = logging.getLogger(__name__)

app = create_app()
monitor_service = BackgroundMonitoringService(
    app,
    app.config.get("MONITOR_REFRESH_SECONDS", 30),
)


def stop_monitoring_service():
    """Stop the embedded monitoring thread cleanly."""
    logger.info("Stopping embedded monitoring service from run.py.")
    monitor_service.stop()
    monitor_service.join(5)


def _handle_signal(signum, frame):
    logger.info("Received stop signal %s for envbooking application.", signum)
    stop_monitoring_service()
    raise SystemExit(0)

if __name__ == '__main__':
    atexit.register(stop_monitoring_service)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    logger.info(
        "Starting envbooking web app on %s:%s with embedded monitoring thread.",
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
