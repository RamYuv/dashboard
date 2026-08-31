"""Export seed-data sections from the application database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SKIP_APP_INIT_DB", "true")

from sqlalchemy.orm import joinedload

from webapp import create_app
from webapp.config import Config
from webapp.models import Environment, EnvironmentHostMapping, Host, PayUi


SECTION_EXPORTERS = ("environments", "hosts", "environment_host_mappings", "pay_ui")


def export_environments():
    """Return seed-ready environment rows."""
    environments = (
        Environment.query.order_by(Environment.env_id.asc()).all()
    )
    payload = []
    for environment in environments:
        payload.append(
            {
                "env_id": environment.env_id,
                "env_type": environment.env_type,
                "team": (environment.team or "").strip().lower(),
            }
        )
    return payload


def export_hosts():
    """Return seed-ready host rows."""
    hosts = Host.query.order_by(Host.host_id.asc()).all()
    payload = []
    for host in hosts:
        payload.append(
            {
                "host_id": host.host_id,
                "hostname": host.hostname,
                "ip_address": host.ip_address or "",
                "domain": host.domain or "",
                "description": host.description or "",
            }
        )
    return payload


def export_environment_host_mappings():
    """Return seed-ready environment host mapping rows."""
    mappings = (
        EnvironmentHostMapping.query.options(
            joinedload(EnvironmentHostMapping.server_type),
            joinedload(EnvironmentHostMapping.environment),
            joinedload(EnvironmentHostMapping.host),
        )
        .order_by(
            EnvironmentHostMapping.env_id.asc(),
            EnvironmentHostMapping.environment_host_mapping_id.asc(),
        )
        .all()
    )

    payload = []
    for mapping in mappings:
        server_type_key = mapping.server_type_key
        env_type = mapping.env_type or (
            mapping.environment.env_type if mapping.environment else None
        )
        host_id = mapping.host_id or (mapping.host.host_id if mapping.host else None)

        if not mapping.env_id or not env_type or not server_type_key or not host_id:
            continue

        payload.append(
            {
                "env_id": mapping.env_id,
                "env_type": env_type,
                "server_type_key": server_type_key,
                "host_id": host_id,
                "deployment_user": mapping.deployment_user or "",
                "deploy_user_hzn": mapping.deploy_user_hzn or "",
            }
        )

    return payload


def export_pay_ui():
    """Return seed-ready pay_ui rows."""
    pay_ui_rows = PayUi.query.order_by(PayUi.env_id.asc()).all()
    payload = []
    for pay_ui in pay_ui_rows:
        payload.append(
            {
                "env_id": pay_ui.env_id,
                "pay_url": (pay_ui.pay_url or "").strip(),
                "pay_adm_url": (pay_ui.pay_adm_url or "").strip(),
            }
        )
    return payload


def export_section(section_name):
    """Dispatch export by seed section name."""
    if section_name == "environments":
        return export_environments()
    if section_name == "hosts":
        return export_hosts()
    if section_name == "environment_host_mappings":
        return export_environment_host_mappings()
    if section_name == "pay_ui":
        return export_pay_ui()
    raise ValueError("Unsupported section: {}".format(section_name))


def _render_seed_block(section_name, records, array_only=False):
    if array_only:
        return json.dumps(records, indent=2) + "\n"

    return json.dumps(
        {section_name: records},
        indent=2,
    )[1:-1].strip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "section",
        choices=SECTION_EXPORTERS,
        help="Seed-data section to export.",
    )
    parser.add_argument(
        "--db-path",
        help=(
            "Optional SQLite database file path. "
            "Sets DATABASE_URL to sqlite:///<path> for this run."
        ),
    )
    parser.add_argument(
        "--database-url",
        help="Optional SQLAlchemy DATABASE_URL override for this run.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the rendered JSON block.",
    )
    parser.add_argument(
        "--array-only",
        action="store_true",
        help="Emit only the JSON array instead of the full seed-data property block.",
    )
    args = parser.parse_args()

    if args.db_path and args.database_url:
        parser.error("Use either --db-path or --database-url, not both.")

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    elif args.db_path:
        db_path = Path(args.db_path).expanduser().resolve()
        os.environ["DATABASE_URL"] = "sqlite:///{}".format(db_path.as_posix())
    else:
        os.environ.setdefault(
            "DATABASE_URL",
            "sqlite:///{}".format(Path(Config.DEFAULT_DB_PATH).resolve().as_posix()),
        )

    app = create_app()
    with app.app_context():
        rendered = _render_seed_block(
            args.section,
            export_section(args.section),
            array_only=args.array_only,
        )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print("{} export completed: {}".format(args.section, output_path))
        return

    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
