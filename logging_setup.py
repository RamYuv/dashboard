"""Central logging configuration for envbooking."""

import logging
import os
from logging.handlers import RotatingFileHandler


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
MONITORING_LOGGER_PREFIXES = (
    "monitoring",
)


class PrefixFilter(logging.Filter):
    """Filter records by logger-name prefix."""

    def __init__(self, prefixes, include=True):
        super().__init__()
        self.prefixes = tuple(prefixes or ())
        self.include = include

    def filter(self, record):
        matches = record.name.startswith(self.prefixes)
        return matches if self.include else not matches


def _resolve_level(level_name):
    if isinstance(level_name, int):
        return level_name
    return getattr(logging, str(level_name or "INFO").upper(), logging.INFO)


def _make_handler(path, level, max_bytes, backup_count, include_prefixes=None, exclude_prefixes=None):
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    if include_prefixes:
        handler.addFilter(PrefixFilter(include_prefixes, include=True))
    if exclude_prefixes:
        handler.addFilter(PrefixFilter(exclude_prefixes, include=False))
    handler._envbooking_managed = True
    return handler


def _make_console_handler(level):
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._envbooking_managed = True
    return handler


def _reset_managed_handlers(logger):
    for handler in list(logger.handlers):
        if getattr(handler, "_envbooking_managed", False):
            logger.removeHandler(handler)
            handler.close()


def configure_application_logging(config):
    """Configure rotating file logs for app and monitoring flows."""

    log_dir = config.get("LOG_DIR") or os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level = _resolve_level(config.get("LOG_LEVEL"))
    max_bytes = int(config.get("LOG_MAX_BYTES", 10 * 1024 * 1024))
    backup_count = int(config.get("LOG_BACKUP_COUNT", 5))
    app_log_path = os.path.join(log_dir, config.get("APP_LOG_FILE", "app.log"))
    monitoring_log_path = os.path.join(
        log_dir,
        config.get("MONITORING_LOG_FILE", "monitoring.log"),
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    _reset_managed_handlers(root_logger)

    app_handler = _make_handler(
        app_log_path,
        log_level,
        max_bytes,
        backup_count,
        exclude_prefixes=MONITORING_LOGGER_PREFIXES,
    )
    monitoring_handler = _make_handler(
        monitoring_log_path,
        log_level,
        max_bytes,
        backup_count,
        include_prefixes=MONITORING_LOGGER_PREFIXES,
    )

    console_handler = _make_console_handler(log_level)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(monitoring_handler)
    root_logger.addHandler(console_handler)
