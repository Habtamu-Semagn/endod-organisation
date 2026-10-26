"""A company applies itself (app.api.application, docs/company-onboarding.md):
the account and a mandatory authenticator first, then the company, the
documents and submission; until Endod approves it, its admins reach only the
application (every other route answers 403)."""

import re

import pytest
from conftest import (
    CLIENT_IP, COMPANY, JPEG, PASSWORD, PDF, PNG, WEBP, Applicant, bearer, events, from_ip, make_admin, make_org,
    password_step, sign_in, start_application,
)

from app.db import session_scope
from app.models import ApplicationDocument, Organisation

REFUSED = "This application cannot be accepted with these details. Contact Endod if you think this is a mistake."


# --- step 1: the account and the authenticator ----------------------------------------------

def test_starting_makes_a_locked_draft_organisation_and_requires_an_authenticator(client, clock):
    resp = start_application(client, email="Meron@Abyssinia.example", legal_name="Abyssinia Textiles PLC")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "enroll"
    headers = bearer(resp.json()["session_token"])

    me = client.get("/auth/me", headers=headers).json()
    assert me["stage"] == "enroll"
    assert me["admin"]["email"] == "meron@abyssinia.example"
    assert me["organisation"]["name"] == "Abyssinia Textiles PLC"
    assert me["organisation"]["application_status"] == "draft"
    # Nothing, not even the application, before the authenticator is enrolled.
    for method, path in (("GET", "/application"), ("PUT", "/application/company"), ("POST", "/application/submit"),
                         ("GET", "/overview")):
        denied = client.request(method, path, json=COMPANY, headers=headers)
        assert denied.status_code == 403 and denied.json()["error_code"] == "SESSION_INCOMPLETE", (method, path)

    started = client.post("/auth/enroll/start", headers=headers).json()
    assert started["otpauth_uri"].startswith("otpauth://totp/")
    from conftest import code
    done = client.post("/auth/enroll/confirm", json={"code": code(started["secret"], clock)}, headers=headers)
    assert done.status_code == 200
    assert len(done.json()["recovery_codes"]) == 10
    full = bearer(done.json()["session_token"])

    app = client.get("/application", headers=full).json()
    assert app["status"] == "draft" and app["editable"] is True
    assert app["contact"] == {"full_name": "Meron Alemu", "title": "HR Manager", "phone": "+251911223344",
                              "email": "meron@abyssinia.example"}
    assert app["company"]["legal_name"] == "Abyssinia Textiles PLC"
    assert app["missing"]["contact"] == [] and "tin" in app["missing"]["company"]
    assert app["next_step"] == "company" and app["complete"] is False
    assert [d["kind"] for d in app["documents"]] == ["trade_license", "tin_certificate", "authorization_letter"]

    # The organisation is not usable yet: its TIN is a placeholder, never a real one.
    with session_scope() as session:
        org = session.get(Organisation, me["organisation"]["id"])
        assert not re.fullmatch(r"[0-9]{10}", org.tin)
        assert org.status == "active"
    started_events = events("application_started")
    assert started_events[-1][:2] == ("application_started", "success")


@pytest.mark.parametrize("field, value, message", [
    ("password", "password1", "too common"),
    ("password", "short", "at least 8"),
    ("phone", "12345", "Ethiopian mobile"),
    ("email", "not-an-email", "not a valid email"),
    ("legal_name", "A", "at least 2"),
    ("full_name", "", "at least 2"),
])
def test_the_account_is_checked(client, field, value, message):
    resp = start_application(client, **{field: value})
    assert resp.status_code in (400, 422), resp.text
    assert message in resp.json()["error"]


def test_an_email_already_in_use_is_refused_with_a_generic_message(client):
    make_admin(email="hr@tena.example")
    first = start_application(client, email="new@company.example")
    assert first.status_code == 200
    for email in ("hr@tena.example", "NEW@company.example"):
        resp = start_application(client, email=email)
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "APPLICATION_REFUSED"
        assert "cannot be used" in resp.json()["error"]
    # Logged without the email typed.
    failed = [e for e in events("application_started") if e[1] == "failure"]
    assert len(failed) == 2 and all(e[2].startswith("unknown:") for e in failed)


def test_applications_are_limited_per_address(client, monkeypatch):
    monkeypatch.setenv("ORG_APPLICATIONS_PER_IP", "2")
    assert start_application(client, ip="203.0.113.7").status_code == 200
    assert start_application(client, ip="203.0.113.7").status_code == 200
    third = start_application(client, ip="203.0.113.7")
    assert third.status_code == 429 and third.json()["error_code"] == "RATE_LIMITED"
    # Another address may; an IPv6 /64 counts as one address.
    assert start_application(client, ip="203.0.113.8").status_code == 200
    assert start_application(client, ip="2001:db8:1:2::1").status_code == 200
    assert start_application(client, ip="2001:db8:1:2::99").status_code == 200
    assert start_application(client, ip="2001:db8:1:2:ffff::5").status_code == 429
    # Sign-in from the limited address is not affected by applications.
    make_admin(email="hr@tena.example")
    password_step(client, headers=from_ip("203.0.113.7"))


def test_an_address_blocked_for_failed_sign_ins_cannot_apply(client, monkeypatch):
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    for _ in range(3):
        client.post("/auth/login", json={"email": "nobody@x.example", "password": "wrong-password-1"},
                    headers=from_ip("203.0.113.9"))
    assert start_application(client, ip="203.0.113.9").status_code == 429
    assert start_application(client, ip="203.0.113.10").status_code == 200


def test_an_applicant_who_left_before_enrolling_enrols_after_signing_in(client, clock):
    resp = start_application(client, email="left@company.example")
    assert resp.status_code == 200
    # Wrong password: the generic answer, counted like any other.
    wrong = client.post("/auth/login", json={"email": "left@company.example", "password": "wrong-password-1"})
    assert wrong.status_code == 401 and wrong.json()["error"] == "Incorrect email or password."
    again = password_step(client, email="left@company.example")
    assert again["stage"] == "enroll"
    headers = bearer(again["session_token"])
    from conftest import code
    secret = client.post("/auth/enroll/start", headers=headers).json()["secret"]
    done = client.post("/auth/enroll/confirm", json={"code": code(secret, clock)}, headers=headers)
    assert done.status_code == 200
    assert client.get("/application", headers=bearer(done.json()["session_token"])).json()["status"] == "draft"


def test_an_unenrolled_cli_admin_still_cannot_sign_in_with_a_password(client):
    make_admin(email="cli@tena.example", enrolled=False)
    resp = client.post("/auth/login", json={"email": "cli@tena.example", "password": PASSWORD})
    assert resp.status_code == 401


# --- the steps -----------------------------------------------------------------------------

def test_steps_are_saved_and_the_wizard_resumes_after_signing_in(client, clock):
    a = Applicant(client, clock)
    saved = a.company()
    assert saved["company"] == {**COMPANY, "phone": "+251115512345"}
    assert saved["missing"]["company"] == [] and saved["next_step"] == "documents"
    assert a.upload("trade_license").status_code == 201

    contact = a.put("/application/contact", json={"full_name": "Meron T. Alemu", "title": "Head of HR",
                                                  "phone": "+251 911 000 111"})
    assert contact.status_code == 200
    assert contact.json()["contact"]["full_name"] == "Meron T. Alemu"
    assert contact.json()["contact"]["phone"] == "+251911000111"

    assert a.post("/auth/logout").status_code == 200
    assert a.get("/application").status_code == 401
    a.sign_in_again()
    app = a.get("/application").json()
    assert app["next_step"] == "documents"
    assert app["missing"]["documents"] == ["tin_certificate", "authorization_letter"]
    assert app["company"]["tin"] == COMPANY["tin"]
    assert client.get("/auth/me", headers=a.headers).json()["admin"]["name"] == "Meron T. Alemu"
    assert [e[4] for e in events("application_saved")][-1] == '{"step": "contact"}'


@pytest.mark.parametrize("field, value", [
    ("tin", "12345"), ("tin", "00456712345"), ("sector", "mining"), ("employee_count", 0), ("phone", "12"),
    ("email", "nope"), ("legal_name", " "), ("address", ""), ("business_license_number", ""), ("city", "\u0000x"),
])
def test_company_details_are_checked(applicant, field, value):
    resp = applicant.put("/application/company", json={**COMPANY, field: value})
    assert resp.status_code in (400, 422), (field, resp.text)


def test_company_phone_may_be_a_landline_or_a_mobile(applicant):
    assert applicant.company(phone="0911 223344")["company"]["phone"] == "+251911223344"
    assert applicant.company(phone="+251-11-551-2345")["company"]["phone"] == "+251115512345"
    assert applicant.company(trade_name="")["company"]["trade_name"] is None


# --- documents -----------------------------------------------------------------------------

def test_documents_are_checked_by_content_and_size(applicant, tmp_path):
    for kind, data, name in (("trade_license", PDF, "licence.pdf"), ("tin_certificate", PNG, "tin.png"),
                             ("authorization_letter", JPEG, "letter.jpg")):
        resp = applicant.upload(kind, data, name)
        assert resp.status_code == 201, resp.text
    assert applicant.upload("authorization_letter", WEBP, "letter.webp").status_code == 201

    html = applicant.upload("trade_license", b"<html><script>alert(1)</script></html>", "licence.pdf")
    assert html.status_code == 415 and html.json()["error_code"] == "FILE_TYPE"
    svg = applicant.upload("trade_license", b"<svg xmlns='http://www.w3.org/2000/svg'/>", "x.svg")
    assert svg.status_code == 415
    wrong_name = applicant.upload("trade_license", PNG, "licence.pdf")
    assert wrong_name.status_code == 400
    assert applicant.upload("trade_license", b"", "empty.pdf").status_code == 400
    too_big = applicant.upload("trade_license", b"%PDF-" + b"0" * (10 * 1024 * 1024), "big.pdf")
    assert too_big.status_code == 413 and too_big.json()["error_code"] == "FILE_TOO_LARGE"
    assert applicant.upload("passport", PDF).status_code == 404

    # Refused uploads leave nothing behind; the earlier ones stand.
    files = [p for p in (tmp_path / "receipts" / applicant.org_id).iterdir()]
    assert len(files) == 3 and not any(p.name.endswith(".part") for p in files)
    docs = applicant.get("/application").json()["documents"]
    assert [(d["kind"], d["filename"], d["content_type"]) for d in docs] == [
        ("trade_license", "licence.pdf", "application/pdf"), ("tin_certificate", "tin.png", "image/png"),
        ("authorization_letter", "letter.webp", "image/webp")]


def test_replacing_a_document_keeps_one_and_removes_the_old_file(applicant, tmp_path):
    first = applicant.upload("trade_license", PDF, "one.pdf")
    second = applicant.upload("trade_license", PNG, "two.png")
    assert first.status_code == second.status_code == 201
    with session_scope() as session:
        rows = session.query(ApplicationDocument).filter_by(organisation_id=applicant.org_id).all()
        assert [(r.kind, r.filename) for r in rows] == [("trade_license", "two.png")]
        only = rows[0].id
    assert [p.name for p in (tmp_path / "receipts" / applicant.org_id).iterdir()] == [only]


def test_an_applicant_views_only_its_own_documents(client, clock):
    a = Applicant(client, clock)
    b = Applicant(client, clock)
    a.upload("trade_license", PNG, "a-licence.png")
    view = a.get("/application/documents/trade_license")
    assert view.status_code == 200 and view.content == PNG
    assert view.headers["content-type"] == "image/png"
    assert view.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in view.headers["cache-control"]
    assert "default-src 'none'" in view.headers["content-security-policy"]
    # B has none of its own, and cannot name A's.
    assert b.get("/application/documents/trade_license").status_code == 404
    assert b.get("/application/documents/../trade_license").status_code == 404
    assert a.get("/application/documents/passport").status_code == 404


# --- submitting ----------------------------------------------------------------------------

def test_submitting_needs_every_step_and_then_freezes_the_application(applicant):
    early = applicant.submit()
    assert early.status_code == 400
    assert early.json()["error"] == "Finish these steps first: company details, documents."
    applicant.company()
    assert applicant.submit().json()["error"] == "Finish these steps first: documents."
    applicant.upload_all()
    done = applicant.submit()
    assert done.status_code == 200 and done.json()["status"] == "submitted"
    assert done.json()["submitted_at"] and done.json()["editable"] is False

    for resp in (applicant.put("/application/company", json=COMPANY),
                 applicant.put("/application/contact", json={"full_name": "X Y", "title": "HR", "phone": "0911000000"}),
                 applicant.upload("trade_license"), applicant.submit()):
        assert resp.status_code == 409 and resp.json()["error_code"] == "UNDER_REVIEW", resp.text
    assert events("application_submitted")[-1][:2] == ("application_submitted", "success")


# --- duplicate TINs ------------------------------------------------------------------------

def test_a_tin_of_an_approved_organisation_is_refused_generically(client, clock):
    make_org("Existing PLC", tin="0045671234")
    a = Applicant(client, clock)
    resp = a.put("/application/company", json=COMPANY)
    assert resp.status_code == 409
    assert resp.json() == {"error": REFUSED, "error_code": "APPLICATION_REFUSED"}
    # A different TIN is fine.
    assert a.put("/application/company", json={**COMPANY, "tin": "0045671235"}).status_code == 200


def test_a_tin_of_another_submitted_application_is_refused_and_drafts_do_not_block(client, clock, platform_key):
    first = Applicant(client, clock)
    second = Applicant(client, clock)
    third = Applicant(client, clock)
    # Two drafts may hold the same TIN...
    first.company()
    second.company()
    second.upload_all()
    first.upload_all()
    # ...until one is submitted: then the other cannot submit it, or save it again.
    first.submit()
    resp = second.submit()
    assert resp.status_code == 409 and resp.json()["error"] == REFUSED
    assert third.put("/application/company", json=COMPANY).status_code == 409
    # A rejected application no longer holds it.
    client.post(f"/platform/applications/{first.org_id}/reject", headers=platform_key,
                json={"reason": "Wrong company.", "reviewer": "reviewer@endod.example"})
    assert second.submit().status_code == 200
    # Now the first, fixed, cannot resubmit it.
    assert first.submit().json()["error"] == REFUSED


def test_tin_probing_is_counted_against_the_address(client, clock, monkeypatch):
    make_org("Existing PLC", tin="0045671234")
    a = Applicant(client, clock)
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    for _ in range(3):
        assert a.put("/application/company", json=COMPANY).status_code == 409
    blocked = a.put("/application/company", json={**COMPANY, "tin": "0045671299"})
    assert blocked.status_code == 429


# --- the lockout ---------------------------------------------------------------------------

def _routes():
    from app.main import create_app

    found = []
    for template, operations in create_app().openapi()["paths"].items():
        for method in operations:
            found.append((method.upper(), template, re.sub(r"\{[a-z_]+\}", "a1" * 16, template)))
    return found


#: What an organisation that is not approved can still use.
OPEN_TO_APPLICANTS = {("POST", "/auth/login"), ("POST", "/auth/setup/check"), ("POST", "/auth/setup"),
                      ("GET", "/health"), ("POST", "/auth/totp"), ("POST", "/auth/enroll/start"),
                      ("POST", "/auth/enroll/confirm"), ("POST", "/auth/logout"), ("GET", "/auth/me"),
                      ("POST", "/application/start")}
LOCKED_ROUTES = [r for r in _routes() if (r[0], r[1]) not in OPEN_TO_APPLICANTS
                 and not r[1].startswith(("/application", "/platform/"))]


def test_the_lockout_covers_the_portal():
    templates = {t for _, t, _ in LOCKED_ROUTES}
    assert {"/overview", "/employees", "/claims", "/batches", "/reports", "/policy", "/receipts", "/auth/reauth",
            "/organisation", "/employees/{employee_id}"} <= templates
    assert len(LOCKED_ROUTES) >= 30


@pytest.fixture
def locked_states(client, clock, platform_key):
    """Admins of a draft, a submitted and a rejected application."""
    draft = Applicant(client, clock)
    submitted = Applicant(client, clock)
    submitted.complete(tin="0045670001")
    rejected = Applicant(client, clock)
    rejected.complete(tin="0045670002")
    resp = client.post(f"/platform/applications/{rejected.org_id}/reject", headers=platform_key,
                       json={"reason": "The trade license is expired.", "reviewer": "reviewer@endod.example"})
    assert resp.status_code == 200
    return [draft, submitted, rejected]


@pytest.mark.parametrize("method, template, path", LOCKED_ROUTES)
def test_every_other_route_answers_403_until_approved(client, locked_states, method, template, path):
    for applicant in locked_states:
        resp = client.request(method, path, json={}, headers=applicant.headers)
        assert resp.status_code == 403, (method, path, resp.text)
        assert resp.json()["error_code"] == "APPLICATION_NOT_APPROVED"


def test_the_application_routes_stay_open_while_locked(client, locked_states):
    for applicant in locked_states:
        assert applicant.get("/application").status_code == 200
        assert client.get("/auth/me", headers=applicant.headers).status_code == 200
        assert applicant.post("/auth/logout").status_code == 200


def test_receipt_files_and_exports_are_locked_too(applicant):
    assert applicant.post("/receipts", content=PNG, headers={"Content-Type": "application/octet-stream"}
                          ).status_code == 403
    assert applicant.get("/employees/export").status_code == 403


# --- rejection, resubmission, approval -----------------------------------------------------

def test_a_rejected_application_shows_the_reason_and_can_be_fixed_and_resubmitted(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    client.post(f"/platform/applications/{a.org_id}/reject", headers=platform_key,
                json={"reason": "  The TIN certificate is unreadable.  ", "reviewer": "reviewer@endod.example"})
    app = a.get("/application").json()
    assert app["status"] == "rejected" and app["editable"] is True
    assert app["rejection_reason"] == "The TIN certificate is unreadable."
    assert app["reviewed_at"]
    assert client.get("/auth/me", headers=a.headers).json()["organisation"]["application_status"] == "rejected"

    assert a.upload("tin_certificate", PNG, "tin-better.png").status_code == 201
    a.company(employee_count=250)
    again = a.submit()
    assert again.status_code == 200
    assert again.json()["status"] == "submitted" and again.json()["rejection_reason"] is None
    assert events("application_submitted")[-1][4] == '{"resubmitted": true}'
    detail = client.get(f"/platform/applications/{a.org_id}", headers=platform_key).json()
    assert detail["employee_count"] == 250 and detail["rejection_reason"] is None


def test_approval_opens_the_portal(client, clock, platform_key):
    a = Applicant(client, clock)
    a.complete()
    assert a.get("/overview").status_code == 403
    resp = client.post(f"/platform/applications/{a.org_id}/approve", headers=platform_key,
                       json={"reviewer": "reviewer@endod.example"})
    assert resp.status_code == 200
    # The same session now reaches everything.
    assert a.get("/overview").status_code == 200
    org = a.get("/organisation").json()
    assert org["tin"] == COMPANY["tin"] and org["name"] == COMPANY["legal_name"]
    assert a.get("/policy").status_code == 200
    app = a.get("/application").json()
    assert app["status"] == "approved"
    assert a.put("/application/company", json=COMPANY).json()["error_code"] == "ALREADY_APPROVED"


def test_organisations_made_by_the_cli_count_as_approved(portal):
    assert portal.get("/application").json() == {"status": "approved", "organisation_name": "Tena Logistics PLC"}
    assert portal.put("/application/company", json=COMPANY).status_code == 409
    assert portal.post("/application/documents/trade_license", content=PDF).status_code == 409
    assert portal.get("/overview").status_code == 200


def test_the_applicant_session_cannot_be_used_from_a_pending_sign_in(client, clock):
    a = Applicant(client, clock)
    pending = password_step(client, email=a.email)
    assert pending["stage"] == "totp"
    resp = client.get("/application", headers=bearer(pending["session_token"]))
    assert resp.status_code == 403 and resp.json()["error_code"] == "SESSION_INCOMPLETE"
    # And a signed-in applicant's other sessions are unaffected by sign-out of one.
    other = sign_in(client, clock, a.secret, email=a.email, ip=CLIENT_IP)
    assert client.get("/application", headers=other).status_code == 200
