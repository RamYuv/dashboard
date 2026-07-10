import sqlite3
import time
import os
from pathlib import Path
from flask import Flask
from flask_migrate import Migrate

try:
    from flask.logging import default_handler
except ImportError:
    default_handler = None

from logging_setup import configure_application_logging
from .config import Config

if not hasattr(time, "clock"):
    time.clock = time.perf_counter

from .models import db
from .monitor_state import MonitorState
from monitoring.container import AppContainer
from .auth_service import current_user
from .db_init import init_db

migrate = Migrate()


def _project_sqlite_recovery_path(app):
    """Return a recovery SQLite file path inside the project directory."""
    project_root = app.config.get("PROJECT_ROOT")
    if project_root:
        return Path(project_root) / "envbooking_app_recovered.db"
    return Path("envbooking_app_recovered.db").resolve()


def _recover_sqlite_database_uri(app):
    """Switch to a fresh SQLite file when the configured DB is unreadable."""
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    prefix = "sqlite:///"
    if not database_uri.startswith(prefix):
        return

    db_path = Path(database_uri[len(prefix):])
    if not db_path.exists():
        return

    try:
        connection = sqlite3.connect(str(db_path))
        connection.execute("PRAGMA schema_version")
        connection.close()
    except sqlite3.Error as exc:
        recovery_path = _project_sqlite_recovery_path(app)
        app.logger.warning(
            "Configured SQLite database %s is unreadable (%s). Falling back to %s.",
            db_path,
            exc,
            recovery_path,
        )
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///{}".format(
            recovery_path.as_posix()
        )

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    configure_application_logging(app.config)
    if default_handler is not None and default_handler in app.logger.handlers:
        app.logger.removeHandler(default_handler)
    app.logger.propagate = True

    _recover_sqlite_database_uri(app)
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize shared monitor state
    app.monitor_state = MonitorState()

    # Initialize container with shared monitor state and app context
    app.container = AppContainer(app, app.monitor_state)

    # Register blueprints
    from .routes import main_bp
    from booking.routes.booking import booking_bp
    from monitoring.api import monitoring_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(monitoring_bp, url_prefix='/monitoring')

    @app.context_processor
    def inject_current_user():
        return {"current_user": current_user()}

    with app.app_context():
        if os.environ.get("SKIP_APP_INIT_DB", "").strip().lower() != "true":
            init_db()
        app.monitor_state.load_persisted()

    return app
