"""CLI wrapper for importing legacy production data into the current schema."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webapp import create_app
from webapp.legacy_import import (
    import_legacy_payload,
    import_legacy_sensitive_values_from_sqlite,
    load_legacy_payload_from_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", help="Path to the structured legacy JSON export.")
    parser.add_argument(
        "--event-mode",
        choices=["booking", "deployment", "both"],
        default="booking",
        help="How legacy event rows should be represented in the new model.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and stage the import without committing it.",
    )
    parser.add_argument(
        "--legacy-db",
        help="Optional legacy SQLite DB path used to import sensitive values directly.",
    )
    args = parser.parse_args()

    app = create_app()
    payload = load_legacy_payload_from_json(args.payload)

    with app.app_context():
        summary = import_legacy_payload(
            payload,
            event_mode=args.event_mode,
            commit=False,
        )
        if args.legacy_db:
            sensitive_summary = import_legacy_sensitive_values_from_sqlite(
                args.legacy_db,
                commit=False,
            )
            summary["sensitive_import"] = sensitive_summary
        if args.dry_run:
            from webapp.models import db

            db.session.rollback()
        else:
            from webapp.models import db

            db.session.commit()
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
