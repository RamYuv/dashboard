"""CLI helper to export a legacy SQLite database into importer-ready JSON."""

import argparse

from webapp.legacy_export import export_legacy_sqlite_to_payload, write_legacy_payload_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_db", help="Path to the legacy SQLite database file.")
    parser.add_argument(
        "output",
        help="Path to write the exported JSON payload.",
    )
    args = parser.parse_args()

    payload = export_legacy_sqlite_to_payload(args.legacy_db)
    write_legacy_payload_json(payload, args.output)

    exported_sections = {
        key: len(value)
        for key, value in payload.items()
        if isinstance(value, list) and value
    }
    print("Legacy export completed: {}".format(args.output))
    print(exported_sections)


if __name__ == "__main__":
    main()

