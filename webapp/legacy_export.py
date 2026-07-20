"""Export legacy SQLite data into the JSON shape expected by the importer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


LEGACY_EXPORT_TABLES = (
    ("role", "role"),
    ("team", "team"),
    ("environment_type", "environment_type"),
    ("testing_mode", "testing_mode"),
    ("oprational_mode", "oprational_mode"),
    ("operational_mode", "operational_mode"),
    ("tcs_service", "tcs_service"),
    ("default_pwd", "default_pwd"),
    ("tcs_service_combo", "tcs_service_combo"),
    ("orbit", "orbit"),
    ("vm", "vm"),
    ("pay_vm", "pay_vm"),
    ("pay_ui", "pay_ui"),
    ("event", "event"),
    ("email_domain", "email_domain"),
    ("tuser", "tuser"),
    ("tcs_version", "tcs_version"),
    ("environment", "environment"),
)


def _table_exists(connection, table_name):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _read_table_rows(connection, table_name):
    cursor = connection.execute('SELECT * FROM "{}"'.format(table_name))
    column_names = [description[0] for description in cursor.description or []]
    rows = []
    for record in cursor.fetchall():
        rows.append(
            {
                column_name: record[index]
                for index, column_name in enumerate(column_names)
            }
        )
    return rows


def export_legacy_sqlite_to_payload(db_path):
    """Return a structured payload from a legacy SQLite database file."""
    database_path = Path(db_path)
    if not database_path.exists():
        raise FileNotFoundError("Legacy database file not found: {}".format(database_path))

    connection = sqlite3.connect(str(database_path))
    try:
        payload = {}
        for output_key, table_name in LEGACY_EXPORT_TABLES:
            payload[output_key] = (
                _read_table_rows(connection, table_name)
                if _table_exists(connection, table_name)
                else []
            )
        return payload
    finally:
        connection.close()


def write_legacy_payload_json(payload, output_path):
    """Persist the structured legacy payload to a JSON file."""
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
