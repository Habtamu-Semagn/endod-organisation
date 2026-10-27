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


def test_0003_only_adds_tables_and_existing_organisations_stay_approved(migrated_url):
    """Company applications: new tables only; an organisation made before
    them has no application, so it is approved and its admins are not locked."""
    from sqlalchemy import text

    from app.db import reset_engine

    command.upgrade(_config(), "0002")
    reset_engine()
    engine = create_engine(migrated_url)
    before = {t: [c["name"] for c in inspect(engine).get_columns(t)] for t in inspect(engine).get_table_names()}
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO organisations (id, name, tin, status, payout_methods, next_claim_number, next_batch_number,"
            " created_at) VALUES (:id, 'Old Org', '0012345678', 'active', 'cbe', 1, 1, CURRENT_TIMESTAMP)"),
            {"id": "c3" * 16})
    engine.dispose()

    command.upgrade(_config(), "0003")
    reset_engine()
    engine = create_engine(migrated_url)
    after = {t: [c["name"] for c in inspect(engine).get_columns(t)]
             for t in inspect(engine).get_table_names()}
    assert {t: cols for t, cols in after.items() if t in before} == before
    assert set(after) - set(before) == {"organisation_applications", "application_documents"}
    engine.dispose()

    from app import onboarding
    from app.db import platform_session
    from app.models import ApplicationStatus

    with platform_session() as session:
        assert onboarding.status_of(onboarding.application_of(session, "c3" * 16)) == ApplicationStatus.APPROVED
    reset_engine()

    command.downgrade(_config(), "0002")
    reset_engine()
    engine = create_engine(migrated_url)
    assert set(inspect(engine).get_table_names()) == set(before)
    engine.dispose()
