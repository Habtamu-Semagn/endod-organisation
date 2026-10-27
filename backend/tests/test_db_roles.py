"""The app database role (deploy/postgres-init/10-roles.sh + migrations/env.py).

Runs only against a PostgreSQL database set up like production: the init
script run, then `alembic upgrade head` as org_owner. CI does that; set
ORG_ROLES_APP_URL (the org_app connection) to run it by hand.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

APP_URL = os.environ.get("ORG_ROLES_APP_URL")

pytestmark = pytest.mark.skipif(not APP_URL, reason="needs ORG_ROLES_APP_URL (a PostgreSQL org_app role)")


@pytest.fixture
def app_conn():
    engine = create_engine(APP_URL)
    with engine.connect() as connection:
        yield connection
    engine.dispose()


def _refused(connection, sql, params=None):
    """Refused for lack of privilege ("permission denied" or "must be owner")."""
    with pytest.raises(ProgrammingError) as caught:
        with connection.begin():
            connection.execute(text(sql), params or {})
    assert type(caught.value.orig).__name__ == "InsufficientPrivilege", caught.value


def test_the_app_role_reads_and_writes_the_app_tables(app_conn):
    row_id = uuid.uuid4().hex
    with app_conn.begin():
        # Row-level security (migration 0004): acting for that organisation.
        app_conn.execute(text("SELECT set_config('app.organisation_id', :id, true)"), {"id": row_id})
        app_conn.execute(text("INSERT INTO organisations (id, name, tin, status, payout_methods, next_claim_number, next_batch_number, created_at) "
                              "VALUES (:id, 'Role Test', :tin, 'active', 'cbe', 1, 1, now())"),
                         {"id": row_id, "tin": row_id[:10]})
        app_conn.execute(text("UPDATE organisations SET name = 'Renamed' WHERE id = :id"), {"id": row_id})
        app_conn.execute(text("DELETE FROM organisations WHERE id = :id"), {"id": row_id})


def test_the_app_role_can_only_append_to_the_audit_log(app_conn):
    with app_conn.begin():
        app_conn.execute(text("INSERT INTO audit_events (id, at, action, result) VALUES (:id, now(), 'sign_in', 'success')"),
                         {"id": uuid.uuid4().hex})
        # An event without an organisation is read only in the platform scope (migration 0004).
        assert app_conn.execute(text("SELECT count(*) FROM audit_events")).scalar() == 0
        app_conn.execute(text("SELECT set_config('app.scope', 'platform', true)"))
        assert app_conn.execute(text("SELECT count(*) FROM audit_events")).scalar() >= 1
    _refused(app_conn, "UPDATE audit_events SET result = 'failure'")
    _refused(app_conn, "DELETE FROM audit_events")
    _refused(app_conn, "TRUNCATE audit_events")


def test_the_app_role_cannot_bypass_row_level_security(app_conn):
    with app_conn.begin():
        flags = app_conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    assert tuple(flags) == (False, False)
    _refused(app_conn, "ALTER TABLE claims DISABLE ROW LEVEL SECURITY")
    _refused(app_conn, "ALTER TABLE claims NO FORCE ROW LEVEL SECURITY")
    _refused(app_conn, "DROP POLICY tenant_isolation ON claims")


def test_the_app_role_cannot_change_the_schema(app_conn):
    _refused(app_conn, "CREATE TABLE sneaky (id int)")
    _refused(app_conn, "ALTER TABLE claims ADD COLUMN sneaky int")
    _refused(app_conn, "DROP TABLE recovery_codes")
    _refused(app_conn, "UPDATE alembic_version SET version_num = 'x'")
