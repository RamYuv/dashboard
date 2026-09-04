import os
import re
from pathlib import Path


def _read_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() == 'true'


def _read_app_version(project_root, default="1.0"):
    version_from_env = os.environ.get("APP_VERSION")
    if version_from_env:
        return version_from_env

    version_file = Path(project_root, "version.txt")
    if version_file.exists():
        lines = version_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            value = line.strip()
            match = re.match(r"^Version\s*:\s*(.+)$", value, re.IGNORECASE)
            if match:
                parsed_version = match.group(1).strip()
                if parsed_version:
                    return parsed_version
        for line in lines:
            value = line.strip()
            if value:
                return value
    return default


class Config:
    """Application configuration loaded from environment variables."""

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    DEFAULT_DB_PATH = Path(PROJECT_ROOT, "dashboard.db").as_posix()
    DEFAULT_SEED_DATA_PATH = Path(
        PROJECT_ROOT,
        "configs",
        "default_seed_data.json",
    ).as_posix()

    # Flask session signing key. Must be replaced with a real secret outside development.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
    # Full SQLAlchemy connection string. Defaults to the local SQLite project database.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{DEFAULT_DB_PATH}")
    # SQLAlchemy event tracking is disabled to reduce memory overhead.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Give SQLite more time to wait for short-lived writers before raising "database is locked".
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": int(os.environ.get("SQLITE_BUSY_TIMEOUT_SECONDS", "10")),
        }
    }
    # High-level environment mode used by app-specific defaults such as seed handling.
    APP_ENV = (os.environ.get('APP_ENV', 'development') or 'development').strip().lower()

    # Host/IP address the Flask server binds to when started via the local runner.
    APP_HOST = os.environ.get('APP_HOST', '127.0.0.1')
    # TCP port the Flask server listens on when started via the local runner.
    APP_PORT = int(os.environ.get('APP_PORT', 5000))

    # Display/processing timezone used by server-side time formatting defaults.
    SERVER_TIMEZONE = os.environ.get('SERVER_TIMEZONE', 'UTC')
    # App version label shown in the UI; can come from env or fall back to version.txt.
    APP_VERSION = _read_app_version(PROJECT_ROOT, default='1.0')

    # Seconds between monitoring refresh cycles for background environment health updates.
    MONITOR_REFRESH_SECONDS = int(os.environ.get('MONITOR_REFRESH_SECONDS', 15 * 60))
    # Number of worker threads used for parallel monitoring fetches.
    MONITOR_FETCH_THREADS = max(1, int(os.environ.get('MONITOR_FETCH_THREADS', 4)))
    # Enables background version collection from monitored targets.
    MONITOR_VERSION_PULL_ENABLED = _read_bool(
        os.environ.get('MONITOR_VERSION_PULL_ENABLED', 'true'),
        default=True,
    )
    # Seconds between version pull cycles when version monitoring is enabled.
    MONITOR_VERSION_PULL_SECONDS = max(
        60,
        int(os.environ.get('MONITOR_VERSION_PULL_SECONDS', 15 * 60))
    )
    # Turns the monitoring scheduler on or off at runtime.
    MONITOR_SCHEDULER_ENABLED = _read_bool(os.environ.get('MONITOR_SCHEDULER_ENABLED', 'false'))
    # Comma-separated server types included in monitoring operations.
    MONITOR_INCLUDED_SERVER_TYPES = os.environ.get(
        'MONITOR_INCLUDED_SERVER_TYPES',
        os.environ.get('MONITOR_INCLUDED_SERVER_ROLES', 'Core,Getway')
    )
    # Includes shared environment-host mappings in monitoring scans when true.
    MONITOR_INCLUDE_SHARED_MAPPINGS = _read_bool(
        os.environ.get('MONITOR_INCLUDE_SHARED_MAPPINGS', 'false')
    )
    # File path used to persist monitoring cache/state between runs.
    MONITOR_CACHE_FILE = os.environ.get(
        'MONITOR_CACHE_FILE',
        os.path.join(BASE_DIR, 'monitoring_cache.json')
    )

    # Directory where app and monitoring log files are written.
    LOG_DIR = os.environ.get('LOG_DIR', os.path.join(PROJECT_ROOT, 'logs'))
    # Root log verbosity for the application logging setup.
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    # Maximum size in bytes for a single log file before rotation.
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))
    # Number of rotated log files retained on disk.
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    # File name for the main web application log inside LOG_DIR.
    APP_LOG_FILE = os.environ.get('APP_LOG_FILE', 'app.log')
    # File name for the monitoring-specific log inside LOG_DIR.
    MONITORING_LOG_FILE = os.environ.get('MONITORING_LOG_FILE', 'monitoring.log')

    # Comma-separated email recipients for ENV-team deployment notifications.
    ENV_TEAM_EMAILS = os.environ.get('ENV_TEAM_EMAILS', '')
    # Enables or disables outbound email delivery through the configured sendmail binary.
    SENDMAIL_ENABLED = _read_bool(os.environ.get('SENDMAIL_ENABLED', 'true'), default=True)
    # Absolute path to the sendmail-compatible executable used for email sending.
    SENDMAIL_PATH = os.environ.get('SENDMAIL_PATH', '/usr/sbin/sendmail')
    # From-address used for system-generated emails.
    MAIL_SENDER = os.environ.get('MAIL_SENDER', 'envbooking@localhost')

    # Master switch for automated deployment execution after approval/trigger.
    AUTO_DEPLOY_ENABLED = _read_bool(os.environ.get('AUTO_DEPLOY_ENABLED', 'false'))
    # Legacy/default deployment script path when using script-driven auto deployment.
    AUTO_DEPLOY_SCRIPT = os.environ.get('AUTO_DEPLOY_SCRIPT', '')
    # Working directory used when launching the legacy auto-deploy script.
    AUTO_DEPLOY_WORKDIR = os.environ.get('AUTO_DEPLOY_WORKDIR', '')
    # Directory where deployment payload files are stored for auto-deploy processing.
    AUTO_DEPLOY_PAYLOAD_DIR = os.environ.get(
        'AUTO_DEPLOY_PAYLOAD_DIR',
        os.path.join(LOG_DIR, 'deployments')
    )
    # Deployment execution mode, for example SCRIPT, used by deployment services.
    DEPLOYMENT_ENGINE = (os.environ.get('DEPLOYMENT_ENGINE', 'SCRIPT') or 'SCRIPT').strip().upper()
    # Command or script path used to launch deployment work for the selected engine.
    DEPLOYMENT_LAUNCHER = os.environ.get('DEPLOYMENT_LAUNCHER', AUTO_DEPLOY_SCRIPT)
    # Working directory for DEPLOYMENT_LAUNCHER.
    DEPLOYMENT_LAUNCHER_WORKDIR = os.environ.get('DEPLOYMENT_LAUNCHER_WORKDIR', AUTO_DEPLOY_WORKDIR)
    # Final resolved deployment payload directory used by the deployment runtime.
    DEPLOYMENT_PAYLOAD_DIR = os.environ.get('DEPLOYMENT_PAYLOAD_DIR', AUTO_DEPLOY_PAYLOAD_DIR)

    # Optional explicit path to the ttyd binary used for browser-based terminal sessions.
    TTYD_BINARY = os.environ.get('TTYD_BINARY', '')
    # Optional explicit path to sshpass used for password-based SSH terminal launches.
    SSHPASS_BINARY = os.environ.get('SSHPASS_BINARY', '')
    # Public hostname exposed to users for ttyd terminal session URLs.
    TTYD_PUBLIC_HOST = os.environ.get('TTYD_PUBLIC_HOST', '')
    # URL scheme used when building ttyd public links.
    TTYD_PUBLIC_SCHEME = os.environ.get('TTYD_PUBLIC_SCHEME', 'http')
    # First port in the allowed ttyd port allocation range.
    TTYD_PORT_START = int(os.environ.get('TTYD_PORT_START', 46000))
    # Last port in the allowed ttyd port allocation range.
    TTYD_PORT_END = int(os.environ.get('TTYD_PORT_END', 49000))
    # Maximum concurrent ttyd sessions/connections the service should allow.
    TTYD_MAX_CONNECTIONS = int(os.environ.get('TTYD_MAX_CONNECTIONS', 100))
    # Directory where temporary password files for ttyd/sshpass sessions are written.
    TTYD_PASS_FILE_DIR = os.environ.get(
        'TTYD_PASS_FILE_DIR',
        os.path.join(PROJECT_ROOT, 'pass_files')
    )

    # When true, reinitializes the database on startup. Use with extreme caution.
    RESET_DB_ON_INIT = _read_bool(os.environ.get('RESET_DB_ON_INIT', 'false'))
    # Controls whether JSON seed data is only used for first-time/bootstrap creation.
    SEED_BOOTSTRAP_ONLY = _read_bool(os.environ.get('SEED_BOOTSTRAP_ONLY', 'true'), default=True)
    # Path to the JSON seed data file used during startup seeding.
    SEED_DATA_PATH = os.environ.get(
        'SEED_DATA_PATH',
        DEFAULT_SEED_DATA_PATH,
    )
    # Allows plaintext `hzn_secret` values in seed users; should be false in production.
    SEED_ALLOW_HZN_SECRET = _read_bool(
        os.environ.get(
            'SEED_ALLOW_HZN_SECRET',
            'false' if APP_ENV == 'production' else 'true',
        ),
        default=APP_ENV != 'production',
    )
    # Enables validation that prevents overlapping reservation windows across environments.
    MUTUAL_ENV_RESERVATION_ENABLED = _read_bool(
        os.environ.get('MUTUAL_ENV_RESERVATION_ENABLED', 'false')
    )
    # Reservation window length, in minutes, used for deployment booking conflict checks.
    DEPLOYMENT_RESERVATION_WINDOW_MINUTES = max(
        1,
        int(os.environ.get('DEPLOYMENT_RESERVATION_WINDOW_MINUTES', 60))
    )
