"""Release-time wrapper to migrate a legacy dashboard SQLite DB into the new model."""

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webapp import create_app
from webapp.config import Config
from webapp.legacy_export import export_legacy_sqlite_to_payload
from webapp.legacy_import import (
    import_legacy_payload,
    import_legacy_sensitive_values_from_sqlite,
)
from webapp.models import db


def _resolve_target_db_path():
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):]).resolve()
    return Path(Config.DEFAULT_DB_PATH).resolve()


def _prepare_legacy_db_path():
    preferred_legacy_path = (PROJECT_ROOT / "dashboard_pre_migration.db").resolve()
    if preferred_legacy_path.exists():
        return preferred_legacy_path

    current_dashboard_db = (PROJECT_ROOT / "dashboard.db").resolve()
    if current_dashboard_db.exists():
        current_dashboard_db.rename(preferred_legacy_path)
        return preferred_legacy_path

    return None


def _resolve_legacy_db_path():
    return _prepare_legacy_db_path()


def _build_summary_message(summary):
    exported_sections = summary.get("exported_sections") or {}
    imported_summary = summary.get("import_summary") or {}
    sensitive_summary = summary.get("sensitive_summary") or {}
    return {
        "legacy_db_path": summary.get("legacy_db_path"),
        "event_mode": summary.get("event_mode"),
        "exported_sections": exported_sections,
        "imported": imported_summary,
        "sensitive_updates": sensitive_summary,
    }


def main():
    legacy_db_path = _resolve_legacy_db_path()
    if legacy_db_path is None:
        print(
            "dashboard.db was not found under PROJECT_ROOT, and "
            "dashboard_pre_migration.db does not exist. Cannot run migration."
        )
        return 1

    target_db_path = _resolve_target_db_path()
    event_mode = (os.environ.get("LEGACY_EVENT_MODE") or "booking").strip().lower() or "booking"
    if event_mode not in {"booking", "deployment", "both"}:
        print("Unsupported LEGACY_EVENT_MODE '{}'. Use booking, deployment, or both.".format(event_mode))
        return 1

    app = create_app()
    with app.app_context():
        payload = export_legacy_sqlite_to_payload(str(legacy_db_path))
        import_summary = import_legacy_payload(
            payload,
            event_mode=event_mode,
            commit=False,
        )
        sensitive_summary = import_legacy_sensitive_values_from_sqlite(
            str(legacy_db_path),
            commit=False,
        )
        db.session.commit()

    summary = {
        "legacy_db_path": str(legacy_db_path),
        "target_db_path": str(target_db_path),
        "event_mode": event_mode,
        "exported_sections": {
            key: len(value)
            for key, value in payload.items()
            if isinstance(value, list) and value
        },
        "import_summary": import_summary,
        "sensitive_summary": sensitive_summary,
    }
    print(json.dumps(_build_summary_message(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
