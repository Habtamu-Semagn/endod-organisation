"""Row-level security (migration 0004, app.db): the database itself refuses
another organisation's rows, even to a query that forgets its filter.

PostgreSQL only (SQLite has no row-level security), as the app role CI
connects with (org_app: neither a superuser nor BYPASSRLS). Two
organisations, A and B, each with a row in every policy table; then, for
every table, acting for A: none of B's rows is visible, updated or deleted,
and a row for B is refused. With no tenant nothing is visible; the platform
scope sees both.
"""

import os
import secrets
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from conftest import PLATFORM_KEY

pytestmark = pytest.mark.skipif(not os.environ.get("ORG_TEST_DATABASE_URL", "").startswith("postgresql"),
                                reason="row-level security needs PostgreSQL (ORG_TEST_DATABASE_URL)")

#: Every policy table, and how to pick one organisation's rows of it in SQL.
OWNED_BY = {
    "organisations": "id = :organisation",
    "org_admins": "organisation_id = :organisation",
    "organisation_applications": "organisation_id = :organisation",
    "application_documents": "organisation_id = :organisation",
    "employees": "organisation_id = :organisation",
    "dependants": "organisation_id = :organisation",
    "benefit_policies": "organisation_id = :organisation",
    "receipt_files": "organisation_id = :organisation",
    "payment_batches": "organisation_id = :organisation",
    "claims": "organisation_id = :organisation",
    "claim_items": "claim_id = :claim",
    "admin_sessions": "admin_id = :admin",
    "recovery_codes": "admin_id = :admin",
    "setup_tokens": "admin_id = :admin",
    "login_throttles": "admin_id = :admin",
    "audit_events": "organisation_id = :organisation",
}
#: Tables without row-level security, and why: per-address sign-in counters
#: (no organisation's data, needed before any organisation is known).
UNCOVERED = {"auth_failures"}
#: The app role may only read and append here (no UPDATE or DELETE grant at all).
APPEND_ONLY = {"audit_events"}

_tins = iter(range(1700000001, 1799999999))


def _hex(n=64):
    return secrets.token_hex(n // 2)


def _seed(name):
    """An organisation with one row in every policy table; returns its keys."""
    from app import audit
    from app.db import platform_session, utcnow
    from app.models import (
        AdminSession, ApplicationDocument, AuditResult, BenefitPolicy, Claim, ClaimItem, Dependant, Employee,
        LoginThrottle, Organisation, OrganisationApplication, OrgAdmin, PaymentBatch, ReceiptFile, RecoveryCode,
        SetupToken,
    )

    now = utcnow()
    with platform_session() as s:
        org = Organisation(name=f"{name} PLC", tin=str(next(_tins)))
        s.add(org)
        s.flush()
        admin = OrgAdmin(organisation_id=org.id, email=f"{name.lower()}@rls.example", name=f"{name} Admin")
        employee = Employee(organisation_id=org.id, employee_number="E-1", name="Employee", phone="+251911000001",
                            department="Ops")
        receipt = ReceiptFile(organisation_id=org.id, filename="r.png", content_type="image/png", size=1,
                              sha256="0" * 64)
        batch = PaymentBatch(organisation_id=org.id, number=1, method="cbe")
        s.add_all([admin, employee, receipt, batch])
        s.flush()
        claim = Claim(organisation_id=org.id, number=1, employee_id=employee.id, pharmacy_name="Pharmacy",
                      pharmacy_tin="0012345678", receipt_number="R-1", receipt_date=date(2026, 10, 1),
                      total_santim=100, receipt_file_id=receipt.id, batch_id=batch.id)
        s.add_all([
            claim,
            AdminSession(admin_id=admin.id, token_hash=_hex(), stage="full", expires_at=now + timedelta(hours=1)),
            RecoveryCode(admin_id=admin.id, code_hash=_hex()),
            SetupToken(admin_id=admin.id, token_hash=_hex(), expires_at=now + timedelta(hours=1)),
            LoginThrottle(admin_id=admin.id, ip="203.0.113.9", failures=1),
            OrganisationApplication(organisation_id=org.id, status="draft", contact_admin_id=admin.id,
                                    created_at=now, updated_at=now),
            ApplicationDocument(organisation_id=org.id, kind="trade_license", filename="t.pdf",
                                content_type="application/pdf", size=1, sha256="0" * 64),
            Dependant(organisation_id=org.id, employee_id=employee.id, name="Dependant", relationship="child"),
            BenefitPolicy(organisation_id=org.id, employee_id=None, annual_limit_santim=100),
        ])
        s.flush()
        s.add(ClaimItem(claim_id=claim.id, position=1, medicine="Medicine", quantity=1, unit_price_santim=100,
                        line_total_santim=100))
        audit.record(s, audit.ORG_CREATED, AuditResult.SUCCESS, organisation_id=org.id)
        return {"organisation": org.id, "admin": admin.id, "employee": employee.id, "claim": claim.id}


def _foreign_row(table, b):
    """A new, otherwise valid row of ``table`` that belongs to B."""
    from app.db import utcnow
    from app.models import (
        AdminSession, ApplicationDocument, AuditEvent, BenefitPolicy, Claim, ClaimItem, Dependant, Employee,
        LoginThrottle, Organisation, OrganisationApplication, OrgAdmin, PaymentBatch, ReceiptFile, RecoveryCode,
        SetupToken,
    )

    org, later = b["organisation"], utcnow() + timedelta(hours=1)
    return {
        # Any organisation but A's own: a new one.
        "organisations": lambda: Organisation(name="Sneaky PLC", tin=str(next(_tins))),
        "org_admins": lambda: OrgAdmin(organisation_id=org, email="sneaky@rls.example", name="Sneaky"),
        "organisation_applications": lambda: OrganisationApplication(organisation_id=org, status="draft"),
        "application_documents": lambda: ApplicationDocument(
            organisation_id=org, kind="tin_certificate", filename="s.pdf", content_type="application/pdf", size=1,
            sha256="0" * 64),
        "employees": lambda: Employee(organisation_id=org, employee_number="E-9", name="Sneaky",
                                      phone="+251911000009", department="Ops"),
        "dependants": lambda: Dependant(organisation_id=org, employee_id=b["employee"], name="Sneaky",
                                        relationship="child"),
        "benefit_policies": lambda: BenefitPolicy(organisation_id=org, employee_id=b["employee"],
                                                  annual_limit_santim=1),
        "receipt_files": lambda: ReceiptFile(organisation_id=org, filename="s.png", content_type="image/png", size=1,
                                             sha256="0" * 64),
        "payment_batches": lambda: PaymentBatch(organisation_id=org, number=2, method="cbe"),
        "claims": lambda: Claim(organisation_id=org, number=2, employee_id=b["employee"], pharmacy_name="P",
                                pharmacy_tin="0012345678", receipt_number="R-9", receipt_date=date(2026, 10, 1),
                                total_santim=100),
        "claim_items": lambda: ClaimItem(claim_id=b["claim"], position=2, medicine="M", quantity=1,
                                         unit_price_santim=1, line_total_santim=1),
        "admin_sessions": lambda: AdminSession(admin_id=b["admin"], token_hash=_hex(), stage="full",
                                               expires_at=later),
        "recovery_codes": lambda: RecoveryCode(admin_id=b["admin"], code_hash=_hex()),
        "setup_tokens": lambda: SetupToken(admin_id=b["admin"], token_hash=_hex(), expires_at=later),
        "login_throttles": lambda: LoginThrottle(admin_id=b["admin"], ip="203.0.113.10", failures=1),
        "audit_events": lambda: AuditEvent(action="sign_in", result="success", organisation_id=org),
    }[table]()


@pytest.fixture
def orgs(db):
    return _seed("Alpha"), _seed("Beta")


def _count(session, table, where="TRUE", keys=None):
    return session.scalar(text(f'SELECT count(*) FROM "{table}" WHERE {where}'), keys or {})


def test_every_organisation_table_has_a_forced_policy(db):
    """Also catches a table added later without one."""
    from app.db import Base, get_engine

    scoped = {name for name, table in Base.metadata.tables.items()
              if {"organisation_id", "admin_id", "claim_id"} & set(table.columns.keys())}
    assert scoped | {"organisations"} == set(OWNED_BY)
    # Every table is either covered or listed (with its reason) as uncovered.
    assert set(Base.metadata.tables) == set(OWNED_BY) | UNCOVERED
    with get_engine().connect() as connection:
        rows = connection.execute(text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, count(p.polname) FROM pg_class c "
            "LEFT JOIN pg_policy p ON p.polrelid = c.oid WHERE c.relnamespace = 'public'::regnamespace "
            "AND c.relkind = 'r' GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity")).all()
    state = {name: (enabled, forced, policies) for name, enabled, forced, policies in rows}
    for table in OWNED_BY:
        assert state[table][:2] == (True, True), table
        assert state[table][2] >= 1, table
    assert state["auth_failures"] == (False, False, 0)


def test_the_app_role_is_held_to_the_policies(db):
    from app.db import get_engine

    with get_engine().connect() as connection:
        row = connection.execute(text(
            "SELECT r.rolsuper, r.rolbypassrls, c.relowner = r.oid FROM pg_roles r, pg_class c "
            "WHERE r.rolname = current_user AND c.oid = 'claims'::regclass")).one()
    assert tuple(row) == (False, False, False), "tests must connect as the app role, not the owner or a superuser"


@pytest.mark.parametrize("table", sorted(OWNED_BY))
def test_acting_for_one_organisation_shows_none_of_the_other(orgs, table):
    from app.db import tenant_session

    a, b = orgs
    with tenant_session(a["organisation"]) as session:
        mine = _count(session, table, OWNED_BY[table], a)
        assert mine >= 1, "A sees its own rows"
        # No filter at all, as a forgetful query: still only A's.
        assert _count(session, table) == mine
        assert _count(session, table, OWNED_BY[table], b) == 0


@pytest.mark.parametrize("table", sorted(OWNED_BY))
def test_a_row_for_the_other_organisation_is_refused(orgs, table):
    from app.db import tenant_session

    a, b = orgs
    with pytest.raises(DBAPIError) as caught:
        with tenant_session(a["organisation"]) as session:
            session.add(_foreign_row(table, b))
            session.flush()
    assert "row-level security" in str(caught.value.orig), caught.value


@pytest.mark.parametrize("table", sorted(set(OWNED_BY) - APPEND_ONLY))
def test_the_other_organisations_rows_cannot_be_changed_or_deleted(orgs, table):
    from app.db import platform_session, tenant_session

    a, b = orgs
    with tenant_session(a["organisation"]) as session:
        # A no-op update, so that nothing would fail but the policy.
        column = "id" if table != "organisation_applications" else "organisation_id"
        changed = session.execute(text(f'UPDATE "{table}" SET {column} = {column} WHERE {OWNED_BY[table]}'), b)
        assert changed.rowcount == 0
        deleted = session.execute(text(f'DELETE FROM "{table}" WHERE {OWNED_BY[table]}'), b)
        assert deleted.rowcount == 0
    with platform_session() as session:
        assert _count(session, table, OWNED_BY[table], b) >= 1


@pytest.mark.parametrize("table", sorted(OWNED_BY))
def test_with_no_tenant_nothing_is_visible(orgs, table):
    from app.db import get_engine, session_scope

    with session_scope() as session:
        assert _count(session, table) == 0
    # A bare connection that never set anything (not even through app.db).
    with get_engine().connect() as connection:
        assert connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar() == 0


def test_with_no_tenant_nothing_can_be_written(orgs):
    from app.db import session_scope
    from app.models import Employee

    with pytest.raises(DBAPIError) as caught:
        with session_scope() as session:
            session.add(Employee(organisation_id=orgs[0]["organisation"], employee_number="E-7", name="Nobody's",
                                 phone="+251911000007", department="Ops"))
            session.flush()
    assert "row-level security" in str(caught.value.orig)


@pytest.mark.parametrize("table", sorted(OWNED_BY))
def test_the_platform_scope_sees_every_organisation(orgs, table):
    from app.db import platform_session

    a, b = orgs
    with platform_session() as session:
        assert _count(session, table, OWNED_BY[table], a) >= 1
        assert _count(session, table, OWNED_BY[table], b) >= 1


def test_the_tenant_context_does_not_outlive_its_transaction(orgs):
    """set_config(..., true): a pooled connection never carries a tenant over."""
    from app.db import get_engine, tenant_session

    with tenant_session(orgs[0]["organisation"]) as session:
        assert _count(session, "organisations") == 1
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM organisations")).scalar() == 0
        assert connection.execute(text("SELECT coalesce(current_setting('app.organisation_id', true), '')")).scalar() \
            == ""


def test_a_session_binds_one_organisation_only(orgs):
    from app.db import bind_tenant, platform_session, tenant_session

    a, b = orgs
    with tenant_session(a["organisation"]) as session:
        with pytest.raises(RuntimeError):
            bind_tenant(session, b["organisation"])
    with platform_session() as session:
        with pytest.raises(RuntimeError):
            bind_tenant(session, a["organisation"])


def test_the_look_up_functions_answer_one_thing_and_leave_no_scope_behind(orgs):
    """Sign-in, session tokens and setup links learn their organisation from
    SECURITY DEFINER functions: one id for one live key (or a yes/no), and
    afterwards the caller still sees nothing."""
    from app import rls
    from app.db import platform_session, session_scope, utcnow
    from app.models import AdminSession, Organisation, OrgAdmin, SetupToken

    a, b = orgs
    with platform_session() as session:
        session_hash = session.scalar(select(AdminSession.token_hash).where(AdminSession.admin_id == b["admin"]))
        link_hash = session.scalar(select(SetupToken.token_hash).where(SetupToken.admin_id == b["admin"]))
        b_tin = session.get(Organisation, b["organisation"]).tin
    with session_scope() as session:
        assert rls.admin_organisation(session, "beta@rls.example") == b["organisation"]
        assert rls.admin_organisation(session, "nobody@rls.example") is None
        assert rls.session_organisation(session, session_hash) == b["organisation"]
        assert rls.session_organisation(session, _hex()) is None
        assert rls.setup_link_organisation(session, link_hash) == b["organisation"]
        assert rls.email_taken(session, "beta@rls.example") is True
        assert rls.email_taken(session, "nobody@rls.example") is False
        assert rls.tin_taken(session, b_tin, a["organisation"]) is True
        assert rls.tin_taken(session, b_tin, b["organisation"]) is False
        assert rls.tin_taken(session, "0000000000", a["organisation"]) is False
        assert session.scalar(text("SELECT coalesce(current_setting('app.scope', true), '')")) == ""
        assert session.scalar(select(func.count()).select_from(AdminSession)) == 0

    # Only live keys: a revoked or expired session, a used or expired link answer nothing.
    past = utcnow() - timedelta(minutes=1)
    for model, column, lookup, key in (
        (AdminSession, "revoked_at", rls.session_organisation, session_hash),
        (AdminSession, "expires_at", rls.session_organisation, session_hash),
        (SetupToken, "used_at", rls.setup_link_organisation, link_hash),
        (SetupToken, "expires_at", rls.setup_link_organisation, link_hash),
    ):
        with platform_session() as session:
            row = session.scalar(select(model).where(model.token_hash == key))
            saved = getattr(row, column)
            setattr(row, column, past)
        with session_scope() as session:
            assert lookup(session, key) is None, (model.__name__, column)
        with platform_session() as session:
            setattr(session.scalar(select(model).where(model.token_hash == key)), column, saved)
    # A disabled admin is not looked up (the email stays taken).
    with platform_session() as session:
        session.get(OrgAdmin, b["admin"]).active = False
    with session_scope() as session:
        assert rls.admin_organisation(session, "beta@rls.example") is None
        assert rls.email_taken(session, "beta@rls.example") is True


def test_the_app_role_cannot_call_anything_else_as_the_owner(db):
    """Only these functions are SECURITY DEFINER, and PUBLIC cannot execute them."""
    from app.db import get_engine

    with get_engine().connect() as connection:
        rows = connection.execute(text(
            "SELECT p.proname, has_function_privilege('public', p.oid, 'EXECUTE') FROM pg_proc p "
            "WHERE p.prosecdef AND p.pronamespace = 'public'::regnamespace ORDER BY 1")).all()
    assert [tuple(r) for r in rows] == [
        ("rls_admin_organisation", False), ("rls_email_taken", False), ("rls_record_orgless_event", False),
        ("rls_session_organisation", False), ("rls_setup_link_organisation", False), ("rls_tin_taken", False)]


@pytest.mark.parametrize("scope", ["platform", "maintenance"])
def test_no_setting_opens_the_platform_scope(orgs, scope):
    """Only the org_platform role (SET ROLE) sees every organisation; setting
    app.scope as the app role, with or without a tenant, gives nothing more."""
    from app.db import get_engine, session_scope, tenant_session

    a, b = orgs
    with get_engine().connect() as connection:
        connection.execute(text("SELECT set_config('app.scope', :s, false)"), {"s": scope})
        for table in OWNED_BY:
            assert connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar() == 0, table
        connection.execute(text("RESET app.scope"))
        connection.commit()
    with session_scope() as session:
        session.execute(text("SELECT set_config('app.scope', :s, true)"), {"s": scope})
        assert _count(session, "organisations") == 0
    with tenant_session(a["organisation"]) as session:
        session.execute(text("SELECT set_config('app.scope', :s, true)"), {"s": scope})
        for table in OWNED_BY:
            assert _count(session, table, OWNED_BY[table], b) == 0, table


def test_the_platform_scope_is_the_platform_role_and_only_when_set(orgs):
    from app.db import get_engine, platform_session, tenant_session

    with platform_session() as session:
        assert session.scalar(text("SELECT current_user")) == "org_platform"
    with tenant_session(orgs[0]["organisation"]) as session:
        assert session.scalar(text("SELECT current_user")) == "org_app"
        # A member WITH INHERIT FALSE: none of org_platform's rights without SET ROLE.
        assert session.scalar(text("SELECT pg_has_role(current_user, 'org_platform', 'USAGE')")) is False
        assert session.scalar(text("SELECT pg_has_role(current_user, 'org_platform', 'MEMBER')")) is True
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT current_user")).scalar() == "org_app"


def test_a_tenant_appends_only_its_own_organisations_events(orgs):
    from app import audit
    from app.db import platform_session, session_scope, tenant_session
    from app.models import AuditEvent

    a, b = orgs
    for organisation_id in (None, b["organisation"]):
        with pytest.raises(DBAPIError) as caught:
            with tenant_session(a["organisation"]) as session:
                session.add(AuditEvent(action="sign_in", result="success", organisation_id=organisation_id))
                session.flush()
        assert "row-level security" in str(caught.value.orig)
    with pytest.raises(DBAPIError):
        with session_scope() as session:
            session.add(AuditEvent(action="sign_in", result="failure", organisation_id=None))
            session.flush()
    with tenant_session(a["organisation"]) as session:
        session.add(AuditEvent(action="sign_in", result="success", organisation_id=a["organisation"]))
    # An event of no organisation goes through the one function, which always leaves it org-less.
    with session_scope() as session:
        audit.record(session, audit.SIGN_IN, "failure", admin_email="hash", ip="203.0.113.1",
                     detail={"reason": "unknown_email"})
    with platform_session() as session:
        orgless = session.scalars(select(AuditEvent).where(AuditEvent.organisation_id.is_(None))).all()
        assert [(e.action, e.admin_id, e.ip) for e in orgless] == [("sign_in", None, "203.0.113.1")]
        session.add(AuditEvent(action="sign_in", result="success", organisation_id=None))  # the platform may


def test_the_api_refuses_to_start_as_a_role_rls_does_not_hold(orgs, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine

    from app import db as dbmod
    from app.main import create_app

    with dbmod.get_engine().connect() as connection:
        assert dbmod.connection_role_problem(connection) is None
    dbmod.check_connection_role()  # the app role: fine
    owner_url = os.environ.get("ORG_TEST_OWNER_DATABASE_URL")
    if not owner_url:
        pytest.skip("needs ORG_TEST_OWNER_DATABASE_URL")
    engine = create_engine(owner_url)
    with engine.connect() as connection:
        assert dbmod.connection_role_problem(connection) == "owns the tables"
    engine.dispose()
    monkeypatch.setenv("ORG_DATABASE_URL", owner_url)
    dbmod.reset_engine()
    with pytest.raises(RuntimeError, match="owns the tables"):
        with TestClient(create_app()):
            pass
    dbmod.reset_engine()


def test_migrations_stop_without_the_roles(orgs, monkeypatch):
    from alembic import command

    from app import db as dbmod
    from test_migrations import _config

    owner_url = os.environ.get("ORG_TEST_OWNER_DATABASE_URL")
    if not owner_url:
        pytest.skip("needs ORG_TEST_OWNER_DATABASE_URL")
    monkeypatch.setenv("ORG_DATABASE_URL", owner_url)
    monkeypatch.setenv("ORG_APP_ROLE", "no_such_role")
    dbmod.reset_engine()
    with pytest.raises(RuntimeError, match="does not exist"):
        command.upgrade(_config(), "head")
    dbmod.reset_engine()


def test_the_platform_routes_see_every_organisation(client, orgs, monkeypatch):
    from app.db import platform_session
    from app.models import OrganisationApplication

    monkeypatch.setenv("ORG_PLATFORM_KEY", PLATFORM_KEY)
    headers = {"X-Platform-Key": PLATFORM_KEY}
    a, b = orgs
    listed = client.get("/platform/applications", headers=headers)
    assert listed.status_code == 200, listed.text
    assert {a["organisation"], b["organisation"]} <= {item["id"] for item in listed.json()["items"]}
    detail = client.get(f"/platform/applications/{b['organisation']}", headers=headers)
    assert detail.status_code == 200 and detail.json()["contact"]["email"] == "beta@rls.example"
    # Organisations in business (approved ones) too.
    with platform_session() as session:
        session.get(OrganisationApplication, a["organisation"]).status = "approved"
        session.get(OrganisationApplication, b["organisation"]).status = "approved"
    organisations = client.get("/platform/organisations", headers=headers).json()["items"]
    assert {a["organisation"], b["organisation"]} <= {o["id"] for o in organisations}
    suspended = client.post(f"/platform/organisations/{b['organisation']}/suspend", headers=headers,
                            json={"reviewer": "reviewer@endod.example"})
    assert suspended.status_code == 200, suspended.text


def test_a_portal_request_reads_only_its_own_organisation(client, clock, orgs):
    """End to end through the API as the app role: A's admin signs in (the
    sign-in look-up binds A) and lists employees; B's never appear."""
    from conftest import Portal

    portal = Portal(client, clock, email="hr@alpha-portal.example", org_name="Alpha Portal PLC")
    mine = portal.employee()
    listed = portal.get("/employees")
    assert listed.status_code == 200
    ids = {e["id"] for e in listed.json()["items"]}
    assert ids == {mine["id"]}
    assert portal.get(f"/employees/{orgs[1]['employee']}").status_code == 404
