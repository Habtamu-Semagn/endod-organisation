"""Two-step verification once a company is approved (docs/company-onboarding.md).

While its application is not approved, a company's applicant signs in with
the password only: an ``applicant`` session, which reaches the application
(its routes, the Under review status, the application's own documents), the
sign-in steps and sign-out, and nothing else. Approval revokes every session
of the organisation's admins, in the same transaction, audited; the next
sign-in is the password, then the forced enrolment, then the portal. An
applicant who did enrol still gives a code. Admins made by the CLI and
organisations already approved are unchanged."""

import json
import re
from datetime import timedelta

from conftest import (
    COMPANY, PASSWORD, Applicant, applicant_sign_in, approve_application, bearer, code, events, from_ip, make_admin,
    make_org, password_step, sign_in,
)
from sqlalchemy import select, update

from app.db import platform_session, utcnow
from app.models import AdminSession, OrgAdmin

ID = "a1" * 16


def _routes():
    from app.main import create_app

    return [(method.upper(), template, re.sub(r"\{[a-z_]+\}", ID, template))
            for template, operations in create_app().openapi()["paths"].items() for method in operations]


ROUTES = _routes()
#: Public: no session involved.
PUBLIC = {("POST", "/auth/login"), ("POST", "/auth/setup/check"), ("POST", "/auth/setup"), ("GET", "/health"),
          ("POST", "/application/start")}
#: The steps of a sign-in: each checks the session's stage itself.
CODE_STEPS = {("POST", "/auth/totp"), ("POST", "/auth/enroll/start"), ("POST", "/auth/enroll/confirm")}
SESSION_ONLY = {("GET", "/auth/me"), ("POST", "/auth/logout")}


def _kind(method, template):
    if (method, template) in PUBLIC:
        return "public"
    if template.startswith("/platform/"):
        return "platform"
    if (method, template) in CODE_STEPS:
        return "code_step"
    if (method, template) in SESSION_ONLY:
        return "session"
    if template == "/application" or template.startswith("/application/"):
        return "application"
    return "portal"


def test_the_route_list_is_complete():
    kinds = {}
    for method, template, _ in ROUTES:
        kinds.setdefault(_kind(method, template), set()).add(template)
    assert {"/application", "/application/company", "/application/contact", "/application/submit",
            "/application/documents/{kind}"} == kinds["application"]
    assert {"/overview", "/employees", "/claims", "/batches", "/reports", "/policy", "/receipts", "/auth/reauth",
            "/organisation"} <= kinds["portal"]
    assert len(kinds["portal"]) >= 25


def _admin(email):
    with platform_session() as session:
        admin = session.scalar(select(OrgAdmin).where(OrgAdmin.email == email))
        session.expunge(admin)
        return admin


# --- applying: the password only, the application only -----------------------------------------

def test_an_applicant_session_reaches_nothing_but_the_application(client, clock, platform_key):
    a = Applicant(client, clock)
    a.upload("trade_license")
    reached = []
    for method, template, path in ROUTES:
        kind = _kind(method, template)
        if kind == "public" or (method, template) == ("POST", "/auth/logout"):
            continue
        if template == "/application/documents/{kind}":
            path = "/application/documents/trade_license"
        resp = client.request(method, path, json={"code": "123456"}, headers=a.headers)
        if kind == "platform":
            assert resp.status_code == 401, (method, path, resp.text)  # the platform key, never a session
        elif kind == "code_step":
            assert resp.status_code == 409 and resp.json()["error_code"] == "WRONG_STAGE", (method, path, resp.text)
        elif kind == "portal":
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json()["error_code"] == "APPLICATION_NOT_APPROVED", (method, path)
        else:
            assert resp.status_code not in (401, 403), (method, path, resp.text)
            reached.append((method, template))
    assert sorted(reached) == sorted([
        ("GET", "/auth/me"), ("GET", "/application"), ("PUT", "/application/contact"),
        ("PUT", "/application/company"), ("POST", "/application/documents/{kind}"),
        ("GET", "/application/documents/{kind}"), ("POST", "/application/submit")])
    # Asking for the enrolment while applying never even made a secret.
    assert _admin(a.email).totp_pending_secret is None and _admin(a.email).totp_secret is None
    assert a.get("/application").status_code == 200
    assert a.post("/auth/logout").status_code == 200
    assert a.get("/application").status_code == 401


def test_an_applicant_session_lives_as_long_as_a_full_one(client, clock):
    a = Applicant(client, clock)
    with platform_session() as session:
        row = session.scalar(select(AdminSession).where(AdminSession.stage == "applicant"))
        assert row.expires_at - row.created_at == timedelta(hours=12)
        # The idle timeout applies as to every session.
        session.execute(update(AdminSession).values(last_seen_at=utcnow() - timedelta(minutes=31)))
    assert a.get("/application").status_code == 401


def test_an_applicant_session_of_an_approved_organisation_reaches_nothing(client, clock, platform_key):
    """Approval revokes them all; one opened at the very moment of approval still gets nothing."""
    a = Applicant(client, clock)
    a.complete()
    assert approve_application(client, platform_key, a.org_id).status_code == 200
    with platform_session() as session:
        session.execute(update(AdminSession).values(revoked_at=None))
    for method, template, path in ROUTES:
        kind = _kind(method, template)
        if kind in ("public", "platform", "session"):
            continue
        resp = client.request(method, path, json={"code": "123456"}, headers=a.headers)
        if kind == "code_step":
            assert resp.status_code == 409, (method, path, resp.text)
        else:
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json()["error_code"] == "SESSION_INCOMPLETE", (method, path)


# --- approval -----------------------------------------------------------------------------------

def test_approval_revokes_every_session_of_the_organisations_admins_and_audits_it(client, clock, platform_key,
                                                                                 portal):
    a = Applicant(client, clock)
    second = applicant_sign_in(client, a.email, ip="203.0.113.5")
    other_id, other_secret = make_admin(email="other@applicant.example", organisation_id=a.org_id)
    other = sign_in(client, clock, other_secret, email="other@applicant.example")
    pending = bearer(password_step(client, email="other@applicant.example")["session_token"])
    elsewhere = Applicant(client, clock)
    a.complete()

    # Approving a version the reviewer did not see changes nothing, sessions included.
    stale = client.post(f"/platform/applications/{a.org_id}/approve", headers=platform_key,
                        json={"reviewer": "reviewer@endod.example", "expected_updated_at": "2026-01-01T00:00:00Z"})
    assert stale.status_code == 409
    assert a.get("/application").status_code == 200 and not events("sessions_revoked")

    assert approve_application(client, platform_key, a.org_id).status_code == 200
    for headers in (a.headers, second, other, pending):
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401 and resp.json()["error_code"] == "SESSION_ENDED"
    # Other organisations' sessions are untouched.
    assert elsewhere.get("/application").status_code == 200
    assert portal.get("/overview").status_code == 200

    revoked = events("sessions_revoked")
    assert len(revoked) == 1
    action, result, email, target, detail = revoked[0]
    assert (result, email, target) == ("success", "reviewer@endod.example", a.org_id)
    assert json.loads(detail) == {"via": "platform", "reason": "application_approved", "admins": 2, "sessions": 4}
    # The enrolled admin signs in as before: password and code, no new enrolment.
    assert client.get("/overview", headers=sign_in(client, clock, other_secret,
                                                   email="other@applicant.example")).status_code == 200


def test_after_approval_a_sign_in_without_enrolment_reaches_only_the_enrolment(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    old = a.headers
    assert approve_application(client, platform_key, a.org_id).status_code == 200
    assert client.get("/application", headers=old).status_code == 401

    # A wrong password is refused and counted, as for anyone.
    wrong = client.post("/auth/login", json={"email": a.email, "password": "wrong-password-1"})
    assert wrong.status_code == 401 and "wrong_password" in events("sign_in")[-1][4]

    opened = password_step(client, email=a.email)
    assert opened["stage"] == "enroll" and opened["session_max_age"] == 15 * 60
    headers = bearer(opened["session_token"])
    for method, template, path in ROUTES:
        kind = _kind(method, template)
        if kind in ("public", "platform", "session") or template.startswith("/auth/enroll/"):
            continue
        resp = client.request(method, path, json={"code": "123456"}, headers=headers)
        if kind == "code_step":  # /auth/totp
            assert resp.status_code == 409, (method, path, resp.text)
        else:
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json()["error_code"] == "SESSION_INCOMPLETE", (method, path)
    assert client.get("/auth/me", headers=headers).json()["stage"] == "enroll"

    started = client.post("/auth/enroll/start", headers=headers).json()
    assert started["otpauth_uri"].startswith("otpauth://totp/") and started["account"] == a.email
    done = client.post("/auth/enroll/confirm", json={"code": code(started["secret"], clock)}, headers=headers)
    assert done.status_code == 200 and len(done.json()["recovery_codes"]) == 10
    clock.advance()
    full = bearer(done.json()["session_token"])
    assert client.get("/overview", headers=full).status_code == 200
    assert client.get("/auth/me", headers=full).json()["stage"] == "full"
    assert client.get("/auth/me", headers=headers).status_code == 401  # the enrolment session ended

    # From now on: password, then a code.
    assert password_step(client, email=a.email)["stage"] == "totp"
    assert client.get("/overview", headers=sign_in(client, clock, started["secret"], email=a.email)
                      ).status_code == 200


def test_an_enrolled_applicant_still_needs_the_code(client, clock, platform_key):
    a = Applicant(client, clock, enrolled=True)
    pending = password_step(client, email=a.email)
    assert pending["stage"] == "totp"
    headers = bearer(pending["session_token"])
    denied = client.get("/application", headers=headers)
    assert denied.status_code == 403 and denied.json()["error_code"] == "SESSION_INCOMPLETE"
    assert client.post("/auth/totp", json={"code": "000000"}, headers=headers).status_code == 400
    done = client.post("/auth/totp", json={"code": code(a.secret, clock)}, headers=headers)
    assert done.status_code == 200
    clock.advance()
    full = bearer(done.json()["session_token"])
    assert client.get("/application", headers=full).status_code == 200
    assert client.get("/overview", headers=full).json()["error_code"] == "APPLICATION_NOT_APPROVED"

    a.headers = full
    a.complete()
    assert approve_application(client, platform_key, a.org_id).status_code == 200
    assert client.get("/overview", headers=full).status_code == 401
    # No second enrolment: the code they have.
    assert client.get("/overview", headers=sign_in(client, clock, a.secret, email=a.email)).status_code == 200


# --- throttles ----------------------------------------------------------------------------------

def test_the_account_backoff_applies_to_applicant_sign_in(client, clock):
    a = Applicant(client, clock)
    for _ in range(3):
        assert client.post("/auth/login", json={"email": a.email, "password": "wrong-password-1"}).status_code == 401
    assert json.loads(events("account_backoff")[-1][4])["seconds"] == 30
    # In backoff the right password is refused too (there is no code step to move on to), and not counted.
    refused = client.post("/auth/login", json={"email": a.email, "password": PASSWORD})
    assert refused.status_code == 401 and refused.json()["error"] == "Incorrect email or password."
    assert "backoff_without_second_factor" in events("sign_in")[-1][4]
    assert _admin(a.email).failed_attempts == 3

    with platform_session() as session:
        session.execute(update(OrgAdmin).values(backoff_until=utcnow() - timedelta(seconds=1)))
    assert applicant_sign_in(client, a.email)
    admin = _admin(a.email)
    assert admin.failed_attempts == 0 and admin.backoff_until is None


def test_five_failures_lock_the_address_for_the_applicants_account(client, clock):
    a = Applicant(client, clock)
    for _ in range(5):
        client.post("/auth/login", json={"email": a.email, "password": "wrong-password-1"}, headers=from_ip("203.0.113.7"))
    assert events("account_locked")
    with platform_session() as session:
        session.execute(update(OrgAdmin).values(backoff_until=None))
    refused = client.post("/auth/login", json={"email": a.email, "password": PASSWORD}, headers=from_ip("203.0.113.7"))
    assert refused.status_code == 401
    assert "address_locked_for_account" in events("sign_in")[-1][4]
    # From another address, the applicant signs in.
    assert applicant_sign_in(client, a.email, ip="203.0.113.8")
    # Their open session was never ended by any of it.
    assert a.get("/application").status_code == 200


def test_the_address_limit_applies_to_applicant_sign_in(client, clock, monkeypatch):
    a = Applicant(client, clock)
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    for n in range(3):
        client.post("/auth/login", json={"email": f"nobody{n}@x.example", "password": "wrong-password-1"},
                    headers=from_ip("203.0.113.9"))
    blocked = client.post("/auth/login", json={"email": a.email, "password": PASSWORD}, headers=from_ip("203.0.113.9"))
    assert blocked.status_code == 429
    assert applicant_sign_in(client, a.email, ip="203.0.113.10")


# --- unchanged ----------------------------------------------------------------------------------

def test_cli_admins_and_approved_organisations_still_need_two_step_verification(client, clock, platform_key, portal):
    # A CLI organisation's admin: password, then a code.
    assert password_step(client, email=portal.email)["stage"] == "totp"
    # An admin made by the CLI without an authenticator signs in only through a setup link,
    # in a CLI organisation and in an approved company alike.
    make_admin(email="cli@tena.example", enrolled=False)
    a = Applicant(client, clock)
    a.complete()
    assert approve_application(client, platform_key, a.org_id).status_code == 200
    make_admin(email="added@applicant.example", enrolled=False, organisation_id=a.org_id)
    for email in ("cli@tena.example", "added@applicant.example"):
        resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert resp.status_code == 401
        assert "not_enrolled" in events("sign_in")[-1][4]
    # An organisation made by the CLI has no application: nobody there gets an applicant session.
    org_id = make_org("Another CLI PLC")
    make_admin(email="nosecret@cli.example", enrolled=False, organisation_id=org_id)
    assert client.post("/auth/login", json={"email": "nosecret@cli.example", "password": PASSWORD}).status_code == 401
    # And the approved company's applicant, once enrolled, is like everyone else.
    a.enrol_after_approval()
    assert password_step(client, email=a.email)["stage"] == "totp"
    assert a.put("/application/company", json=COMPANY).json()["error_code"] == "ALREADY_APPROVED"
