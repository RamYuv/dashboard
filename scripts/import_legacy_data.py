"""CLI wrapper for importing legacy production data into the current schema."""

import argparse
import json

from webapp import create_app
from webapp.legacy_import import import_legacy_payload, load_legacy_payload_from_json


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
    args = parser.parse_args()

    app = create_app()
    payload = load_legacy_payload_from_json(args.payload)

    with app.app_context():
        summary = import_legacy_payload(
            payload,
            event_mode=args.event_mode,
            commit=not args.dry_run,
        )
        if args.dry_run:
            from webapp.models import db

            db.session.rollback()
        print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
