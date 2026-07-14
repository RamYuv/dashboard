import os
from pathlib import Path


def _read_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() == 'true'


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    DEFAULT_DB_PATH = Path(PROJECT_ROOT, "envbooking_app.db").as_posix()

    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Web app host/port
    APP_HOST = os.environ.get('APP_HOST', '127.0.0.1')
    APP_PORT = int(os.environ.get('APP_PORT', 5000))

    # Other settings
    SERVER_TIMEZONE = os.environ.get('SERVER_TIMEZONE', 'UTC')
    APP_VERSION = os.environ.get('APP_VERSION', '1.0')

    # Monitoring scheduler/cache
    MONITOR_REFRESH_SECONDS = int(os.environ.get('MONITOR_REFRESH_SECONDS', 60))
    MONITOR_FETCH_THREADS = max(1, int(os.environ.get('MONITOR_FETCH_THREADS', 4)))
    MONITOR_VERSION_PULL_ENABLED = _read_bool(
        os.environ.get('MONITOR_VERSION_PULL_ENABLED', 'true'),
        default=True,
    )
    MONITOR_VERSION_PULL_SECONDS = max(
        60,
        int(os.environ.get('MONITOR_VERSION_PULL_SECONDS', 15 * 60))
    )
    MONITOR_SCHEDULER_ENABLED = _read_bool(os.environ.get('MONITOR_SCHEDULER_ENABLED', 'false'))
    MONITOR_INCLUDED_SERVER_TYPES = os.environ.get(
        'MONITOR_INCLUDED_SERVER_TYPES',
        os.environ.get('MONITOR_INCLUDED_SERVER_ROLES', 'Core,Getway')
    )
    MONITOR_INCLUDE_SHARED_MAPPINGS = _read_bool(
        os.environ.get('MONITOR_INCLUDE_SHARED_MAPPINGS', 'false')
    )
    MONITOR_CACHE_FILE = os.environ.get(
        'MONITOR_CACHE_FILE',
        os.path.join(BASE_DIR, 'monitoring_cache.json')
    )

    LOG_DIR = os.environ.get('LOG_DIR', os.path.join(PROJECT_ROOT, 'logs'))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    APP_LOG_FILE = os.environ.get('APP_LOG_FILE', 'app.log')
    MONITORING_LOG_FILE = os.environ.get('MONITORING_LOG_FILE', 'monitoring.log')

    ENV_TEAM_EMAILS = os.environ.get('ENV_TEAM_EMAILS', '')
    SENDMAIL_ENABLED = _read_bool(os.environ.get('SENDMAIL_ENABLED', 'true'), default=True)
    SENDMAIL_PATH = os.environ.get('SENDMAIL_PATH', '/usr/sbin/sendmail')
    MAIL_SENDER = os.environ.get('MAIL_SENDER', 'envbooking@localhost')

    AUTO_DEPLOY_ENABLED = _read_bool(os.environ.get('AUTO_DEPLOY_ENABLED', 'false'))
    AUTO_DEPLOY_SCRIPT = os.environ.get('AUTO_DEPLOY_SCRIPT', '')
    AUTO_DEPLOY_WORKDIR = os.environ.get('AUTO_DEPLOY_WORKDIR', '')
    AUTO_DEPLOY_PAYLOAD_DIR = os.environ.get(
        'AUTO_DEPLOY_PAYLOAD_DIR',
        os.path.join(LOG_DIR, 'deployments')
    )
    DEPLOYMENT_ENGINE = (os.environ.get('DEPLOYMENT_ENGINE', 'SCRIPT') or 'SCRIPT').strip().upper()
    DEPLOYMENT_LAUNCHER = os.environ.get('DEPLOYMENT_LAUNCHER', AUTO_DEPLOY_SCRIPT)
    DEPLOYMENT_LAUNCHER_WORKDIR = os.environ.get('DEPLOYMENT_LAUNCHER_WORKDIR', AUTO_DEPLOY_WORKDIR)
    DEPLOYMENT_PAYLOAD_DIR = os.environ.get('DEPLOYMENT_PAYLOAD_DIR', AUTO_DEPLOY_PAYLOAD_DIR)

    TTYD_BINARY = os.environ.get('TTYD_BINARY', '')
    SSHPASS_BINARY = os.environ.get('SSHPASS_BINARY', '')
    TTYD_PUBLIC_HOST = os.environ.get('TTYD_PUBLIC_HOST', '')
    TTYD_PUBLIC_SCHEME = os.environ.get('TTYD_PUBLIC_SCHEME', 'http')
    TTYD_PORT_START = int(os.environ.get('TTYD_PORT_START', 46000))
    TTYD_PORT_END = int(os.environ.get('TTYD_PORT_END', 49000))
    TTYD_MAX_CONNECTIONS = int(os.environ.get('TTYD_MAX_CONNECTIONS', 100))
    TTYD_PASS_FILE_DIR = os.environ.get(
        'TTYD_PASS_FILE_DIR',
        os.path.join(PROJECT_ROOT, 'pass_files')
    )

    RESET_DB_ON_INIT = _read_bool(os.environ.get('RESET_DB_ON_INIT', 'false'))
    SEED_BOOTSTRAP_ONLY = _read_bool(os.environ.get('SEED_BOOTSTRAP_ONLY', 'true'), default=True)
    MUTUAL_ENV_RESERVATION_ENABLED = _read_bool(
        os.environ.get('MUTUAL_ENV_RESERVATION_ENABLED', 'false')
    )
    DEPLOYMENT_RESERVATION_WINDOW_MINUTES = max(
        1,
        int(os.environ.get('DEPLOYMENT_RESERVATION_WINDOW_MINUTES', 60))
    )
