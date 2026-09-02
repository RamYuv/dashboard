"""Deployment-time database initializer for the dashboard application."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from webapp import create_app
from webapp.db_init import get_seed_runtime_summary


def main():
    app = create_app()
    with app.app_context():
        summary = get_seed_runtime_summary()

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
