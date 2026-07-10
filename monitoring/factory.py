"""Factory helpers for monitoring-only app usage.

This module builds a lightweight Flask app with monitoring dependencies and
database access, without bootstrapping the full web application startup flow.
It is suitable for cron-friendly jobs such as version reconciliation.
"""

try:
    from flask.logging import default_handler
except ImportError:
    default_handler = None

from flask import Flask

from logging_setup import configure_application_logging
from monitoring.container import AppContainer
from monitoring.api import monitoring_bp
from webapp.config import Config
from webapp.db_init import init_db
from webapp.monitor_state import MonitorState
from webapp.models import db


def create_monitoring_app(config_class=Config):
    """Create a monitoring-focused app with DB wiring but no web startup side effects."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    configure_application_logging(app.config)
    if default_handler is not None and default_handler in app.logger.handlers:
        app.logger.removeHandler(default_handler)
    app.logger.propagate = True

    db.init_app(app)
    app.monitor_state = MonitorState()
    app.container = AppContainer(app, app.monitor_state)
    app.register_blueprint(monitoring_bp)

    with app.app_context():
        init_db()
        app.monitor_state.load_persisted()

    return app
