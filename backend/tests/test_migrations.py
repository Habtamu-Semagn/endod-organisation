"""The Alembic migrations build exactly the schema of the models, and go
down and up again cleanly (on SQLite here; CI also runs them on PostgreSQL)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_url(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    monkeypatch.setenv("ORG_DATABASE_URL", url)
    monkeypatch.setenv("ORG_ENVIRONMENT", "development")
    from app import db as dbmod

    dbmod.reset_engine()
    yield url
    dbmod.reset_engine()


def _config():
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    return config


def test_upgrade_matches_the_models_and_downgrades_cleanly(migrated_url):
    from app import models  # noqa: F401
    from app.db import Base, reset_engine

    command.upgrade(_config(), "head")
    reset_engine()
    engine = create_engine(migrated_url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection, opts={"render_as_batch": True}), Base.metadata)
    assert diff == []
    tables = set(inspect(engine).get_table_names())
    assert {"organisations", "org_admins", "employees", "dependants", "benefit_policies", "claims", "claim_items",
            "receipt_files", "payment_batches", "audit_events"} <= tables
    engine.dispose()

    command.downgrade(_config(), "base")
    reset_engine()
    engine = create_engine(migrated_url)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
    command.upgrade(_config(), "head")
    reset_engine()


def test_there_is_one_head():
    from alembic.script import ScriptDirectory

    assert len(ScriptDirectory.from_config(_config()).get_heads()) == 1
