"""Flask CLI entrypoint for migration and app commands."""

import os
import sys

if "db" in sys.argv:
    os.environ["SKIP_APP_INIT_DB"] = "true"

from webapp import create_app


app = create_app()
