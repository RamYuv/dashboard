from flask import Flask
from flask.logging import default_handler

from logging_setup import configure_application_logging
from .config import Config
from .models import db
from .monitor_state import MonitorState
from monitoring.container import AppContainer
from .auth_service import current_user
from .db_init import init_db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    configure_application_logging(app.config)
    if default_handler in app.logger.handlers:
        app.logger.removeHandler(default_handler)
    app.logger.propagate = True

    db.init_app(app)

    # Initialize shared monitor state
    app.monitor_state = MonitorState()

    # Initialize container with shared monitor state and app context
    app.container = AppContainer(app, app.monitor_state)

    # Register blueprints
    from .routes.main import main_bp
    from booking.routes.booking import booking_bp
    from monitoring.api import monitoring_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(monitoring_bp, url_prefix='/monitoring')

    @app.context_processor
    def inject_current_user():
        return {"current_user": current_user()}

    with app.app_context():
        init_db()
        app.monitor_state.load_persisted()
        snapshot, _ = app.monitor_state.snapshot()
        if not snapshot:
            app.container.env_worker.refresh()

    return app
