"""Runs the organisation portal API for the browser tests.

Started by playwright.config.ts with backend/ as the working directory and
ORG_DATABASE_URL pointing at a throwaway SQLite file: applies the Alembic
migrations (as the container does on start), then serves the API.

    python ../e2e/api_server.py <port>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.getcwd())

import uvicorn  # noqa: E402
from alembic.config import main as alembic  # noqa: E402


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8140
    if not os.environ.get("ORG_DATABASE_URL", "").startswith("sqlite:///"):
        raise SystemExit("The browser tests need a throwaway SQLite ORG_DATABASE_URL.")
    alembic(argv=["upgrade", "head"])
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
