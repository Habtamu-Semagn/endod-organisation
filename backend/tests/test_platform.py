"""The platform API (app.api.platform) exactly as docs/company-onboarding.md
says: X-Platform-Key (constant time; 503 while unset), no BFF secret, 404 for
unknown ids, 409 for the wrong status, audited approve, reject, suspend and
reactivate with the reviewer's email."""

import json

import pytest
from conftest import (
    BFF_SECRET, CLIENT_IP, COMPANY, PDF, PLATFORM_KEY, PNG, Applicant, approve_application, events, make_admin,
    make_org, password_step, sign_in,
)
from fastapi.testclient import TestClient

REVIEWER = {"reviewer": "reviewer@endod.example"}
SEEN = "2026-10-20T08:00:00+00:00"
CHANGED = "The application changed since you opened it. Reload it."
UNKNOWN = "b2" * 16


@pytest.fixture
def endod(db, platform_key):
    """The super admin's API: on endod-bus, with the platform key and nothing else (no BFF secret)."""
    from app.main import create_app

    return TestClient(create_app(), headers=platform_key)


def _routes():
    from app.main import create_app

    return [(m.upper(), t.replace("{application_id}", UNKNOWN).replace("{organisation_id}", UNKNOWN)
             .replace("{kind}", "trade_license"))
            for t, ops in create_app().openapi()["paths"].items() if t.startswith("/platform/") for m in ops]


PLATFORM_ROUTES = _routes()


def test_the_contract_routes_exist():
    assert sorted(PLATFORM_ROUTES) == sorted([
        ("GET", "/platform/applications"),
        ("GET", f"/platform/applications/{UNKNOWN}"),
        ("GET", f"/platform/applications/{UNKNOWN}/documents/trade_license"),
        ("POST", f"/platform/applications/{UNKNOWN}/approve"),
        ("POST", f"/platform/applications/{UNKNOWN}/reject"),
        ("GET", "/platform/organisations"),
        ("POST", f"/platform/organisations/{UNKNOWN}/suspend"),
        ("POST", f"/platform/organisations/{UNKNOWN}/reactivate"),
    ])


# --- the key -------------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", PLATFORM_ROUTES + [("GET", "/platform/nothing")])
def test_unset_or_short_key_switches_the_platform_api_off(db, monkeypatch, method, path):
    from app.main import create_app

    bare = TestClient(create_app())
    for value in (None, "", "short-key"):
        if value is None:
            monkeypatch.delenv("ORG_PLATFORM_KEY", raising=False)
        else:
            monkeypatch.setenv("ORG_PLATFORM_KEY", value)
        for headers in ({}, {"X-Platform-Key": value or ""}, {"X-Platform-Key": PLATFORM_KEY}):
            resp = bare.request(method, path, json=REVIEWER, headers={k: v for k, v in headers.items() if v})
            assert resp.status_code == 503, (method, path, value)
            assert resp.json()["detail"] == "The platform API is not configured."


@pytest.mark.parametrize("method, path", PLATFORM_ROUTES)
def test_every_route_needs_the_key_and_not_the_bff_secret(db, platform_key, method, path):
    from app.main import create_app

    bare = TestClient(create_app())
    for headers in ({}, {"X-Platform-Key": PLATFORM_KEY[:-1]}, {"X-Platform-Key": PLATFORM_KEY + "x"},
                    {"X-Platform-Key": PLATFORM_KEY.upper()}, {"X-BFF-Secret": BFF_SECRET},
                    {"Authorization": f"Bearer {PLATFORM_KEY}"}):
        resp = bare.request(method, path, json=REVIEWER, headers=headers)
        assert resp.status_code == 401, (method, path, headers)
        assert resp.json()["detail"] == "Authentication required."
    # The right key alone (no BFF secret): past the key, to the unknown id.
    resp = bare.request(method, path, json={"reason": "A fine reason.", "expected_updated_at": SEEN, **REVIEWER},
                        headers=platform_key)
    assert resp.status_code in (200, 404), (method, path, resp.text)


def test_the_key_does_not_open_the_portal_api(db, platform_key):
    from app.main import create_app

    bare = TestClient(create_app())
    for path in ("/overview", "/employees", "/application", "/auth/me"):
        resp = bare.get(path, headers=platform_key)
        assert resp.status_code == 403 and resp.json()["error_code"] == "BFF_REQUIRED"


# --- applications --------------------------------------------------------------------------

def test_listing_applications_newest_first_with_the_contract_fields(client, clock, endod):
    draft = Applicant(client, clock, legal_name="Draft Co")
    first = Applicant(client, clock)
    first.complete(tin="0045670001", legal_name="First Submitted PLC")
    clock.advance()
    second = Applicant(client, clock)
    second.complete(tin="0045670002", legal_name="Second Submitted PLC")
    make_org("CLI Org")  # not an application

    everything = endod.get("/platform/applications")
    assert everything.status_code == 200
    items = everything.json()["items"]
    assert {i["id"] for i in items} == {draft.org_id, first.org_id, second.org_id}

    submitted = endod.get("/platform/applications", params={"status": "submitted"}).json()["items"]
    assert [i["id"] for i in submitted] == [second.org_id, first.org_id]
    item = submitted[0]
    assert set(item) == {"id", "legal_name", "trade_name", "tin", "sector", "employee_count", "city", "status",
                         "submitted_at", "updated_at", "duplicate_tin", "email_verified", "contact"}
    assert item["duplicate_tin"] is False and item["email_verified"] is False
    assert item["legal_name"] == "Second Submitted PLC" and item["tin"] == "0045670002"
    assert item["trade_name"] == COMPANY["trade_name"] and item["sector"] == "manufacturing"
    assert item["employee_count"] == 240 and item["city"] == "Addis Ababa" and item["status"] == "submitted"
    assert item["contact"] == {"full_name": "Meron Alemu", "title": "HR Manager", "phone": "+251911223344",
                               "email": second.email}
    assert [i["id"] for i in endod.get("/platform/applications", params={"status": "draft"}).json()["items"]] == [
        draft.org_id]
    assert endod.get("/platform/applications", params={"status": "approved"}).json() == {"items": []}
    bad = endod.get("/platform/applications", params={"status": "pending"})
    assert bad.status_code == 400 and "status must be one of" in bad.json()["detail"]


def test_one_application_with_its_documents(client, clock, endod):
    a = Applicant(client, clock)
    a.complete()
    detail = endod.get(f"/platform/applications/{a.org_id}").json()
    assert detail["business_license_number"] == COMPANY["business_license_number"]
    assert detail["address"] == COMPANY["address"] and detail["phone"] == "+251115512345"
    assert detail["email"] == COMPANY["email"]
    assert detail["rejection_reason"] is None and detail["reviewed_at"] is None
    assert [d["kind"] for d in detail["documents"]] == ["trade_license", "tin_certificate", "authorization_letter"]
    assert set(detail["documents"][0]) == {"kind", "filename", "content_type", "size", "uploaded_at"}
    assert detail["documents"][0]["content_type"] == "application/pdf" and detail["documents"][0]["size"] == len(PDF)

    for path in (f"/platform/applications/{UNKNOWN}", "/platform/applications/not-an-id",
                 f"/platform/applications/{UNKNOWN.upper()}"):
        resp = endod.get(path)
        assert resp.status_code == 404 and resp.json()["detail"]


def test_documents_download_as_attachments_and_views_are_audited(client, clock, endod):
    a = Applicant(client, clock)
    a.upload("tin_certificate", PNG, "tin <cert>.png")
    resp = endod.get(f"/platform/applications/{a.org_id}/documents/tin_certificate")
    assert resp.status_code == 200 and resp.content == PNG
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["content-disposition"].startswith("attachment; ")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in resp.headers["cache-control"]
    viewed = events("application_document_viewed")
    assert len(viewed) == 1 and json.loads(viewed[0][4]) == {"via": "platform", "kind": "tin_certificate"}

    assert endod.get(f"/platform/applications/{a.org_id}/documents/trade_license").status_code == 404
    assert endod.get(f"/platform/applications/{a.org_id}/documents/passport").status_code == 404
    assert endod.get(f"/platform/applications/{UNKNOWN}/documents/tin_certificate").status_code == 404


def test_approving_needs_a_submitted_application_and_is_audited(client, clock, endod):
    a = Applicant(client, clock)
    a.company()
    a.upload_all()
    draft = approve_application(endod, {}, a.org_id)
    assert draft.status_code == 409 and draft.json()["detail"] == CHANGED
    a.submit()
    seen = endod.get(f"/platform/applications/{a.org_id}").json()["updated_at"]

    for body in ({}, {"reviewer": "no-at-sign", "expected_updated_at": seen},
                 {"reviewer": "a @b.example", "expected_updated_at": seen}, REVIEWER,
                 {**REVIEWER, "expected_updated_at": "yesterday"},
                 {**REVIEWER, "expected_updated_at": "2026-10-20T08:00:00"}):  # no timezone
        assert endod.post(f"/platform/applications/{a.org_id}/approve", json=body).status_code == 422, body
    assert endod.post(f"/platform/applications/{UNKNOWN}/approve",
                      json={**REVIEWER, "expected_updated_at": seen}).status_code == 404

    ok = endod.post(f"/platform/applications/{a.org_id}/approve",
                    json={"reviewer": " Reviewer@Endod.example ", "expected_updated_at": seen})
    assert ok.status_code == 200 and ok.json() == {"status": "approved"}
    again = endod.post(f"/platform/applications/{a.org_id}/approve", json={**REVIEWER, "expected_updated_at": seen})
    assert again.status_code == 409 and again.json()["detail"] == CHANGED
    assert endod.post(f"/platform/applications/{a.org_id}/reject",
                      json={"reason": "Too late.", **REVIEWER}).status_code == 409

    approved = events("application_approved")
    assert len(approved) == 1
    action, result, email, target, detail = approved[0]
    assert (result, email, target) == ("success", "reviewer@endod.example", a.org_id)
    assert json.loads(detail) == {"via": "platform", "reviewer": "reviewer@endod.example", "tin": COMPANY["tin"]}
    detail = endod.get(f"/platform/applications/{a.org_id}").json()
    assert detail["status"] == "approved" and detail["reviewed_at"]
    orgs = endod.get("/platform/organisations").json()["items"]
    assert [(o["id"], o["name"], o["tin"], o["status"]) for o in orgs] == [
        (a.org_id, COMPANY["legal_name"], COMPANY["tin"], "active")]


def test_rejecting_needs_a_reason_and_a_submitted_application(client, clock, endod):
    a = Applicant(client, clock)
    assert endod.post(f"/platform/applications/{a.org_id}/reject",
                      json={"reason": "Not yet.", **REVIEWER}).status_code == 409
    a.complete()
    for reason in ("", "  x ", "no", "x" * 1001):
        resp = endod.post(f"/platform/applications/{a.org_id}/reject", json={"reason": reason, **REVIEWER})
        assert resp.status_code == 422 and resp.json()["detail"], reason
    assert endod.post(f"/platform/applications/{a.org_id}/reject", json={"reason": "Fine reason."}).status_code == 422
    assert endod.post(f"/platform/applications/{UNKNOWN}/reject",
                      json={"reason": "Fine reason.", **REVIEWER}).status_code == 404

    resp = endod.post(f"/platform/applications/{a.org_id}/reject",
                      json={"reason": "The authorization letter is not signed.", **REVIEWER})
    assert resp.status_code == 200 and resp.json() == {"status": "rejected"}
    assert endod.post(f"/platform/applications/{a.org_id}/reject",
                      json={"reason": "Twice.", **REVIEWER}).status_code == 409
    assert approve_application(endod, {}, a.org_id).status_code == 409

    rejected = events("application_rejected")
    assert len(rejected) == 1 and rejected[0][2] == "reviewer@endod.example"
    assert json.loads(rejected[0][4])["reason"] == "The authorization letter is not signed."
    detail = endod.get(f"/platform/applications/{a.org_id}").json()
    assert detail["status"] == "rejected" and detail["rejection_reason"] == "The authorization letter is not signed."
    assert a.get("/application").json()["rejection_reason"] == "The authorization letter is not signed."


def test_approval_refuses_a_tin_another_organisation_took_meanwhile(client, clock, endod):
    a = Applicant(client, clock)
    a.complete()
    make_org("Came Later PLC", tin=COMPANY["tin"])  # by the CLI, after the submission
    resp = approve_application(endod, {}, a.org_id)
    assert resp.status_code == 409 and "TIN" in resp.json()["detail"]
    assert endod.get(f"/platform/applications/{a.org_id}").json()["status"] == "submitted"
    assert a.get("/overview").status_code == 403


# --- organisations -------------------------------------------------------------------------

def test_listing_organisations_counts_employees_and_admins(client, clock, endod, portal):
    portal.employee()
    portal.employee()
    gone = portal.employee()
    portal.post(f"/employees/{gone['id']}/deactivate")
    make_admin(email="second@tena.example", organisation_id=portal.org_id)
    make_admin(email="off@tena.example", organisation_id=portal.org_id, active=False)
    Applicant(client, clock)  # still applying: not listed

    items = endod.get("/platform/organisations").json()["items"]
    assert len(items) == 1
    org = items[0]
    assert set(org) == {"id", "name", "tin", "status", "created_at", "employees", "admins"}
    assert (org["id"], org["name"], org["status"], org["employees"], org["admins"]) == (
        portal.org_id, "Tena Logistics PLC", "active", 2, 2)


def test_suspending_signs_the_admins_out_and_refuses_them_until_reactivated(client, clock, endod, portal):
    second_id, second_secret = make_admin(email="second@tena.example", organisation_id=portal.org_id)
    second = sign_in(client, clock, second_secret, email="second@tena.example")
    pending = password_step(client, email="hr@tena.example")
    assert portal.get("/overview").status_code == 200

    resp = endod.post(f"/platform/organisations/{portal.org_id}/suspend", json=REVIEWER)
    assert resp.status_code == 200 and resp.json() == {"status": "suspended"}
    for headers in (portal.headers, second, {"Authorization": f"Bearer {pending['session_token']}"}):
        assert client.get("/auth/me", headers=headers).status_code == 401
    refused = client.post("/auth/login", json={"email": "hr@tena.example", "password": "Correct-Horse-42"})
    assert refused.status_code == 401 and refused.json()["error"] == "Incorrect email or password."
    assert endod.get("/platform/organisations").json()["items"][0]["status"] == "suspended"
    # Suspending again changes nothing (and says so in the log).
    assert endod.post(f"/platform/organisations/{portal.org_id}/suspend", json=REVIEWER).status_code == 200

    back = endod.post(f"/platform/organisations/{portal.org_id}/reactivate", json=REVIEWER)
    assert back.status_code == 200 and back.json() == {"status": "active"}
    headers = sign_in(client, clock, portal.secret, email="hr@tena.example")
    assert client.get("/overview", headers=headers).status_code == 200

    suspended = events("organisation_suspended")
    assert [json.loads(e[4])["changed"] for e in suspended] == [True, False]
    assert all(e[2] == "reviewer@endod.example" and e[3] == portal.org_id for e in suspended)
    assert events("organisation_reactivated")[0][2] == "reviewer@endod.example"


def test_suspend_and_reactivate_answer_404_for_unknown_or_unapproved_organisations(client, clock, endod):
    a = Applicant(client, clock)
    a.complete()
    for org_id in (UNKNOWN, "nope", a.org_id):
        for action in ("suspend", "reactivate"):
            resp = endod.post(f"/platform/organisations/{org_id}/{action}", json=REVIEWER)
            assert resp.status_code == 404 and resp.json()["detail"], (org_id, action)
    assert endod.post(f"/platform/organisations/{UNKNOWN}/suspend", json={}).status_code == 422


def test_a_suspended_approved_company_keeps_its_approval(client, clock, endod):
    a = Applicant(client, clock)
    a.complete()
    approve_application(endod, {}, a.org_id)
    endod.post(f"/platform/organisations/{a.org_id}/suspend", json=REVIEWER)
    assert a.get("/application").status_code == 401
    endod.post(f"/platform/organisations/{a.org_id}/reactivate", json=REVIEWER)
    a.sign_in_again()
    assert a.get("/overview").status_code == 200


def test_the_bff_client_cannot_reach_the_platform_api_with_a_session(client, portal, platform_key):
    """The BFF never passes /platform on; even if something did, a session is not the key."""
    resp = client.get("/platform/applications", headers={**portal.headers, "X-Endod-Client-IP": CLIENT_IP})
    assert resp.status_code == 401
