"""Deployment-time database initializer for the dashboard application."""

import json
import os
import sys
import tempfile
import sqlite3
import subprocess
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask import Flask
from flask_migrate import Migrate, stamp, upgrade
from sqlalchemy import MetaData, inspect

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webapp import create_app
from flask_sqlalchemy import SQLAlchemy
from webapp.db_init import get_seed_runtime_summary
from webapp.db_init import seed_initial_data
from webapp.models import db


def copy_sqlite_database(source, destination):
    """Copy a consistent SQLite snapshot, including committed WAL contents."""
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination:
        return
    if destination.exists():
        raise RuntimeError("Refusing to overwrite existing database: " + str(destination))
    connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    try:
        if not hasattr(connection, "backup"):
            # Python 3.6 lacks Connection.backup; use SQLite's WAL-aware CLI.
            destination_arg = destination.as_posix().replace('"', '\\"')
            try:
                subprocess.check_call([
                    "sqlite3", "-batch", "-bail", str(source),
                    '.backup "{}"'.format(destination_arg),
                ])
            except OSError as exc:
                raise RuntimeError("Database copy requires the sqlite3 command on PATH.") from exc
            return
        target = sqlite3.connect(str(destination))
        try:
            connection.backup(target)
        finally:
            target.close()
    finally:
        connection.close()


def apply_schema_migrations(app, directory=None):
    """Upgrade tracked databases, or adopt an exactly matching legacy baseline."""
    directory = str(directory or PROJECT_ROOT / "migrations")
    if not Path(directory, "env.py").is_file():
        raise RuntimeError("Release is missing migrations/env.py; ship the migration folder.")
    scripts = ScriptDirectory(directory)
    bases = scripts.get_bases()
    if len(bases) != 1 or len(scripts.get_heads()) != 1:
        raise RuntimeError("Release must include one initial migration and one migration head.")
    with app.app_context():
        with db.engine.connect() as connection:
            revisions = MigrationContext.configure(connection).get_current_heads()
            tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if revisions:
            for revision in revisions:
                if scripts.get_revision(revision) is None:
                    raise RuntimeError("Database references an unknown migration: " + revision)
        elif tables:
            # Compare against the frozen initial revision, not today's models.
            with tempfile.TemporaryDirectory(prefix="dashboard_baseline_") as folder:
                reference = Flask("migration_baseline")
                reference.config.update(
                    SQLALCHEMY_DATABASE_URI="sqlite:///" + Path(folder, "baseline.db").as_posix(),
                    SQLALCHEMY_TRACK_MODIFICATIONS=False,
                )
                reference_db = SQLAlchemy(reference)
                Migrate(reference, reference_db)
                with reference.app_context():
                    try:
                        upgrade(directory=directory, revision=bases[0])
                        baseline = MetaData()
                        baseline.reflect(bind=reference_db.engine)
                        baseline.remove(baseline.tables["alembic_version"])
                    finally:
                        reference_db.session.remove()
                        reference_db.engine.dispose()
            with db.engine.connect() as connection:
                differences = compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_type": True,
                                                                  "compare_server_default": True}),
                    baseline,
                )
            if differences:
                raise RuntimeError(
                    "Existing database differs from the initial schema. No version was stamped. "
                    "Create a baseline from the existing schema and a reviewed follow-up migration, "
                    "or reconcile the database before deployment. Differences: " + repr(differences)
                )
            stamp(directory=directory, revision=bases[0])
        upgrade(directory=directory)


def main():
    # deploy_dashboard.sh has already copied the previous release database.
    # Skip normal startup initialization so migrations run before model queries.
    previous_skip_init = os.environ.get("SKIP_APP_INIT_DB")
    os.environ["SKIP_APP_INIT_DB"] = "true"
    try:
        app = create_app()
    finally:
        if previous_skip_init is None:
            os.environ.pop("SKIP_APP_INIT_DB", None)
        else:
            os.environ["SKIP_APP_INIT_DB"] = previous_skip_init
    with app.app_context():
        try:
            apply_schema_migrations(app)
            summary = get_seed_runtime_summary()
            seed_initial_data()
        except Exception:
            db.session.rollback()
            raise
        finally:
            db.session.remove()
            db.engine.dispose()

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--copy-sqlite":
        copy_sqlite_database(sys.argv[2], sys.argv[3])
        raise SystemExit(0)
    raise SystemExit(main())
