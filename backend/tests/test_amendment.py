"""Amendment 1 of docs/company-onboarding.md (after the security review):
closed applications, no TIN squatting (tests/test_application.py), expired
drafts, the approval version check, one lock order, and the guarded downgrade."""

import json
import re
import time
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import (
    COMPANY, PASSWORD, PDF, Applicant, approve_application, events, start_application,
)
from sqlalchemy import select, update

from app import onboarding
from app.db import platform_session, utcnow
from app.models import (
    AdminSession, ApplicationDocument, BenefitPolicy, OrgAdmin, Organisation, OrganisationApplication, RecoveryCode,
)

REVIEWER = {"reviewer": "reviewer@endod.example"}
CHANGED = "The application changed since you opened it. Reload it."


# --- closed ----------------------------------------------------------------------------------

def test_closing_ends_an_application_for_good(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    resp = client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                       json={"reason": "Not an employer we can serve.", "close": True, **REVIEWER})
    assert resp.status_code == 200 and resp.json() == {"status": "closed"}

    closed = events("application_closed")
    assert len(closed) == 1 and closed[0][2] == "reviewer@endod.example"
    assert json.loads(closed[0][4])["close"] is True
    assert events("application_rejected") == []

    app = a.get("/application").json()
    assert app["status"] == "closed" and app["editable"] is False
    assert app["rejection_reason"] == "Not an employer we can serve."
    for resp in (a.put("/application/company", json=COMPANY),
                 a.put("/application/contact", json={"full_name": "X Y", "title": "HR", "phone": "0911000000"}),
                 a.upload("trade_license", PDF), a.submit()):
        assert resp.status_code == 409 and resp.json() == {"error": "This application was closed.",
                                                           "error_code": "APPLICATION_CLOSED"}, resp.text
    # Still locked out of the portal; signing in and out still work.
    assert a.get("/overview").json()["error_code"] == "APPLICATION_NOT_APPROVED"
    assert a.post("/auth/logout").status_code == 200
    a.sign_in_again()
    assert a.get("/application").json()["status"] == "closed"

    # Endod cannot reopen it either.
    assert approve_application(client, platform_key, a.org_id).json()["detail"] == CHANGED
    assert client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                       json={"reason": "Again.", **REVIEWER}).status_code == 409
    listed = client.get("/platform/applications", params={"status": "closed"}, headers=platform_key).json()
    assert [i["id"] for i in listed["items"]] == [a.org_id]
    assert client.get(f"/platform/applications/{a.org_id}", headers=platform_key).json()["status"] == "closed"


def test_rejecting_without_close_still_allows_a_resubmission(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    resp = client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                       json={"reason": "Fix the letter.", "close": False, **REVIEWER})
    assert resp.json() == {"status": "rejected"}
    assert a.submit().status_code == 200


# --- the approval version check --------------------------------------------------------------

def _seen(client, headers, org_id):
    return client.get(f"/platform/applications/{org_id}", headers=headers).json()["updated_at"]


def test_every_applicant_edit_moves_updated_at(client, clock, platform_key):
    a = Applicant(client, clock)
    versions = [_seen(client, platform_key, a.org_id)]
    for change in (lambda: a.company(),
                   lambda: a.put("/application/contact", json={"full_name": "Meron A", "title": "HR", "phone": "0911223344"}),
                   lambda: a.upload("trade_license", PDF),
                   lambda: a.upload("trade_license", PDF),  # a replacement too
                   lambda: (a.upload("tin_certificate", PDF), a.upload("authorization_letter", PDF)),
                   lambda: a.submit()):
        time.sleep(0.002)
        change()
        versions.append(_seen(client, platform_key, a.org_id))
    assert len(set(versions)) == len(versions), versions
    assert versions == sorted(versions)


def test_approval_needs_the_version_the_reviewer_saw(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    stale = _seen(client, platform_key, a.org_id)
    # Sent back, fixed and resubmitted after the reviewer opened it.
    client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                json={"reason": "Fix the TIN certificate.", **REVIEWER})
    time.sleep(0.002)
    a.upload("tin_certificate", PDF, "new-tin.pdf")
    a.submit()

    old = client.post(f"/platform/applications/{a.org_id}/approve", headers=platform_key,
                      json={**REVIEWER, "expected_updated_at": stale})
    assert old.status_code == 409 and old.json()["detail"] == CHANGED
    fresh = _seen(client, platform_key, a.org_id)
    # The same instant in another timezone is the same version.
    from datetime import datetime, timezone
    as_addis = datetime.fromisoformat(fresh).astimezone(timezone(timedelta(hours=3))).isoformat()
    ok = client.post(f"/platform/applications/{a.org_id}/approve", headers=platform_key,
                     json={**REVIEWER, "expected_updated_at": as_addis})
    assert ok.status_code == 200
    assert events("application_approved")


def test_a_version_one_microsecond_off_is_refused(client, clock, platform_key):
    from datetime import datetime
    a = Applicant(client, clock)
    a.complete()
    seen = datetime.fromisoformat(_seen(client, platform_key, a.org_id))
    for off in (timedelta(microseconds=1), -timedelta(microseconds=1), timedelta(seconds=1)):
        resp = client.post(f"/platform/applications/{a.org_id}/approve", headers=platform_key,
                           json={**REVIEWER, "expected_updated_at": (seen + off).isoformat()})
        assert resp.status_code == 409 and resp.json()["detail"] == CHANGED


# --- expired drafts --------------------------------------------------------------------------

def _age(org_id, days):
    with platform_session() as session:
        session.execute(update(OrganisationApplication).where(OrganisationApplication.organisation_id == org_id)
                        .values(created_at=utcnow() - timedelta(days=days)))


def test_drafts_not_submitted_within_14_days_are_deleted_with_everything(client, clock, platform_key, tmp_path):
    old = Applicant(client, clock, email="old@company.example")
    old.company()
    old.upload("trade_license", PDF)
    young = Applicant(client, clock)
    submitted = Applicant(client, clock)
    submitted.complete(tin="0045670009")
    for applicant in (old, submitted):
        _age(applicant.org_id, 15)
    _age(young.org_id, 13)
    assert (tmp_path / "receipts" / old.org_id).is_dir()

    # The periodic sweep (the API's background task, the platform list, the CLI).
    assert onboarding.sweep_now(force=True) == 1

    with platform_session() as session:
        assert session.get(Organisation, old.org_id) is None
        assert session.get(OrganisationApplication, old.org_id) is None
        assert session.scalar(select(OrgAdmin).where(OrgAdmin.organisation_id == old.org_id)) is None
        assert session.scalar(select(ApplicationDocument).where(ApplicationDocument.organisation_id == old.org_id)) is None
        assert session.scalar(select(BenefitPolicy).where(BenefitPolicy.organisation_id == old.org_id)) is None
        for model in (AdminSession, RecoveryCode):
            assert session.scalar(select(model).join(OrgAdmin, OrgAdmin.id == model.admin_id, isouter=True)
                                  .where(OrgAdmin.id.is_(None))) is None
        # A young draft and anything submitted stay.
        assert session.get(Organisation, young.org_id) is not None
        assert session.get(Organisation, submitted.org_id) is not None
    assert not any((tmp_path / "receipts" / old.org_id).glob("*"))
    assert old.get("/application").status_code == 401

    expired = events("application_expired")
    assert len(expired) == 1 and expired[0][3] == old.org_id
    assert json.loads(expired[0][4]) == {"reason": "draft_not_submitted_within_14_days",
                                         "admins": ["old@company.example"]}
    # The email is free again.
    assert start_application(client, email="old@company.example").status_code == 200


def test_listing_applications_sweeps_and_signing_in_is_refused_without_sweeping(client, clock, platform_key):
    listed = Applicant(client, clock)
    _age(listed.org_id, 15)
    items = client.get("/platform/applications", headers=platform_key).json()["items"]
    assert listed.org_id not in [i["id"] for i in items]

    signing_in = Applicant(client, clock, email="late@company.example")
    _age(signing_in.org_id, 15)
    resp = client.post("/auth/login", json={"email": "late@company.example", "password": PASSWORD})
    assert resp.status_code == 401 and resp.json()["error"] == "Incorrect email or password."
    assert json.loads(events("sign_in")[-1][4])["reason"] == "application_expired"
    # A public request never sweeps (anyone could make it lock rows on demand).
    assert len(events("application_expired")) == 1
    with platform_session() as session:
        assert session.get(Organisation, signing_in.org_id) is not None
    assert onboarding.sweep_now(force=True) == 1
    assert len(events("application_expired")) == 2


def test_starting_an_application_sweeps_only_the_expired_draft_of_its_email(client, clock):
    mine = Applicant(client, clock, email="again@company.example")
    other = Applicant(client, clock)
    for applicant in (mine, other):
        _age(applicant.org_id, 15)
    assert start_application(client, email="again@company.example").status_code == 200
    with platform_session() as session:
        assert session.get(Organisation, mine.org_id) is None
        assert session.get(Organisation, other.org_id) is not None


def test_the_sweep_runs_at_most_once_per_interval_and_one_at_a_time(db, monkeypatch):
    monkeypatch.setenv("ORG_SWEEP_INTERVAL_SECONDS", "600")
    monkeypatch.setattr(onboarding, "_last_sweep", None)
    assert onboarding.sweep_now() == 0
    assert onboarding.sweep_now() is None  # within the interval
    assert onboarding.sweep_now(force=True) == 0


def test_a_rate_limited_application_never_sweeps(client, clock, monkeypatch):
    late = Applicant(client, clock, email="limited@company.example")
    _age(late.org_id, 15)
    monkeypatch.setenv("ORG_APPLICATIONS_PER_IP", "1")
    resp = start_application(client, email="limited@company.example")
    assert resp.status_code == 429
    with platform_session() as session:
        assert session.get(Organisation, late.org_id) is not None


def test_a_rejected_application_is_not_swept(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                json={"reason": "Fix it.", **REVIEWER})
    _age(a.org_id, 60)
    client.get("/platform/applications", headers=platform_key)
    assert a.get("/application").json()["status"] == "rejected"


def test_a_taken_email_is_still_refused_and_rate_limited(client, monkeypatch):
    monkeypatch.setenv("ORG_APPLICATIONS_PER_IP", "2")
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    assert start_application(client, email="taken@company.example", ip="203.0.113.50").status_code == 200
    resp = start_application(client, email="taken@company.example", ip="203.0.113.50")
    assert resp.status_code == 409 and resp.json()["error_code"] == "APPLICATION_REFUSED"
    # Each refusal counts as an attempt: the address is soon refused outright.
    assert start_application(client, email="taken@company.example", ip="203.0.113.50").status_code == 429
    assert start_application(client, ip="203.0.113.50").status_code == 429
    assert start_application(client, email="taken@company.example", ip="203.0.113.51").status_code == 409


# --- one lock order --------------------------------------------------------------------------

def test_every_changing_path_locks_through_lock_for_change(client, clock, platform_key, portal, monkeypatch):
    """Applicant steps, approve, reject and suspend all take their locks through
    onboarding.lock_for_change (organisation, then application): one order, no
    deadlock between an applicant's save and Endod's decision."""
    calls = []
    real = onboarding.lock_for_change

    def spy(session, organisation_id):
        calls.append(organisation_id)
        return real(session, organisation_id)

    monkeypatch.setattr(onboarding, "lock_for_change", spy)
    a = Applicant(client, clock)
    steps = [
        lambda: a.company(),
        lambda: a.put("/application/contact", json={"full_name": "Meron A", "title": "HR", "phone": "0911223344"}),
        lambda: (a.upload("trade_license", PDF), a.upload("tin_certificate", PDF), a.upload("authorization_letter", PDF)),
        lambda: a.submit(),
        lambda: client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                            json={"reason": "Fix it.", **REVIEWER}),
        lambda: a.submit(),
        lambda: approve_application(client, platform_key, a.org_id),
        lambda: client.post(f"/platform/organisations/{portal.org_id}/suspend", headers=platform_key, json=REVIEWER),
    ]
    for step in steps:
        before = len(calls)
        step()
        assert len(calls) > before, step


def test_lock_for_change_locks_the_organisation_first(db):
    from sqlalchemy import event

    from app.db import get_engine

    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", record)
    try:
        with platform_session() as session:
            from conftest import make_org
            real = make_org("Lock Order PLC")
            statements.clear()
            onboarding.lock_for_change(session, real)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    # (The tenant context each transaction sets first, app.db, reads no table.)
    tables = [re.search(r"FROM (\w+)", s).group(1) for s in statements
              if s.lstrip().upper().startswith("SELECT") and "set_config" not in s]
    assert tables[:2] == ["organisations", "organisation_applications"], tables


def test_no_other_code_locks_an_application_row():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "application_of(" in line and "lock=True" in line and "def lock_for_change" not in line:
                offenders.append(f"{path.name}:{number}")
    # The one place: inside lock_for_change itself.
    assert offenders == ["onboarding.py:" + str(_line_in_lock_for_change(app_dir / "onboarding.py"))], offenders


def _line_in_lock_for_change(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("def lock_for_change"))
    return next(i for i in range(start, len(lines)) if "application_of(" in lines[i]) + 1


# --- rollback safety -------------------------------------------------------------------------

def test_downgrading_below_0003_refuses_while_applications_are_pending(tmp_path, monkeypatch):
    from alembic import command
    from sqlalchemy import create_engine, inspect, text

    from app.db import reset_engine
    from test_migrations import _config

    url = f"sqlite:///{(tmp_path / 'downgrade.db').as_posix()}"
    monkeypatch.setenv("ORG_DATABASE_URL", url)
    monkeypatch.setenv("ORG_ENVIRONMENT", "development")
    reset_engine()
    command.upgrade(_config(), "head")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO organisations (id, name, tin, status, payout_methods, next_claim_number, next_batch_number,"
            " created_at) VALUES (:id, 'Applying PLC', '~abc', 'active', 'cbe', 1, 1, CURRENT_TIMESTAMP)"),
            {"id": "d4" * 16})
        connection.execute(text(
            "INSERT INTO organisation_applications (organisation_id, status, created_at, updated_at)"
            " VALUES (:id, 'submitted', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": "d4" * 16})
    engine.dispose()
    reset_engine()
    with pytest.raises(RuntimeError, match="1 company application\\(s\\) are not approved"):
        command.downgrade(_config(), "0002")
    reset_engine()
    engine = create_engine(url)
    assert "organisation_applications" in inspect(engine).get_table_names()
    with engine.begin() as connection:
        connection.execute(text("UPDATE organisation_applications SET status = 'approved'"))
    engine.dispose()
    command.downgrade(_config(), "0002")
    reset_engine()
    engine = create_engine(url)
    assert "organisation_applications" not in inspect(engine).get_table_names()
    engine.dispose()
    reset_engine()
