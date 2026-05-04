"""Factory helpers for monitoring-only app usage.

This module can build a minimal Flask app that exposes only monitoring routes
and monitoring dependencies. It is useful for focused monitoring experiments or
future service separation.
"""

from flask import Flask

from monitoring.container import AppContainer
from monitoring.api import monitoring_bp


def create_monitoring_app():
    """Create a minimal Flask app containing only monitoring pieces."""
    app = Flask(__name__)
    app.container = AppContainer(app, None)
    app.register_blueprint(monitoring_bp)
    return app
