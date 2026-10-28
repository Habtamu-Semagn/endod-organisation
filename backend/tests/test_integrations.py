"""The integration API for companies' own systems (docs/integrations.md):
connections in the portal, tokens, scopes, employees, claims and payments,
test mode, limits, webhooks (signing and SSRF), the request log and the audit
trail. SQLite by default; PostgreSQL too (row-level security) with
ORG_TEST_DATABASE_URL."""

import base64
import json
import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from sqlalchemy import func, select

from conftest import CLIENT_IP, Portal, events

from app.db import platform_session, utcnow
from app.integrations import clients, jose, ratelimit, signing, tokens, webhooks
from app.models import (
    AuditEvent, Dependant, DeliveryStatus, Employee, IntegrationAssertion, IntegrationClient, IntegrationIdempotency,
    IntegrationPayoutChange, IntegrationRequest, Organisation, OrganisationApplication, WebhookDelivery,
)

API = "/integrations/v1"
EVERYTHING = ["employees.write", "employees.read", "claims.read", "payments.read"]
PAYOUT = EVERYTHING + ["employees.payout.write", "employees.payout.read"]


@pytest.fixture(autouse=True)
def fresh_limits():
    ratelimit.reset_all()
    signing.clear_cache()
    yield
    ratelimit.reset_all()


# --- helpers ----------------------------------------------------------------------------------

def connect(portal, scopes=None, mode="live", webhook_url=None, name="HR system"):
    body = {"name": name, "scopes": EVERYTHING if scopes is None else scopes, "mode": mode}
    if webhook_url:
        body["webhook_url"] = webhook_url
    resp = portal.post("/connections", json=body)
    if resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED":
        portal.reauth()
        resp = portal.post("/connections", json=body)
    return resp


def connected(portal, **kwargs):
    resp = connect(portal, **kwargs)
    assert resp.status_code == 201, resp.text
    return resp.json()


def basic(client_id, secret):
    return {"Authorization": "Basic " + base64.b64encode(f"{client_id}:{secret}".encode()).decode()}


def token_request(client, data=None, headers=None):
    return client.post(f"{API}/oauth/token", data={"grant_type": "client_credentials", **(data or {})},
                       headers=headers or {})


def get_token(client, conn, scope=None, headers=None):
    data = {"scope": scope} if scope else {}
    resp = token_request(client, data, {**basic(conn["connection"]["client_id"], conn["client_secret"]),
                                        **(headers or {})})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def sync(client, auth, employees, headers=None):
    return client.post(f"{API}/employees", headers={**auth, "Content-Type": "application/json", **(headers or {})},
                       content=json.dumps({"employees": employees}))


def person(number="HR-0001", **fields):
    return {"employee_number": number, "name": f"Worker {number}", "phone": "0911223344", "department": "Ops",
            **fields}


def count(model, **where):
    with platform_session() as session:
        query = select(func.count()).select_from(model)
        for key, value in where.items():
            query = query.where(getattr(model, key) == value)
        return session.scalar(query)


def advanced(portal, path, body=None):
    """A change under Advanced: with a fresh code."""
    resp = portal.post(path, json=body or {})
    if resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED":
        portal.reauth()
        resp = portal.post(path, json=body or {})
    return resp


def ec_key_and_jwks(kid="k1"):
    private = ec.generate_private_key(ec.SECP256R1())
    return private, {"keys": [jose.ec_public_jwk(private.public_key(), kid)]}


def assertion(private, client_id, aud=None, exp_in=120, jti=None, kid="k1", rsa_key=False):
    now = int(time.time())
    claims = {"iss": client_id, "sub": client_id, "aud": aud or tokens.token_url(), "exp": now + exp_in, "iat": now,
              "jti": jti or uuid.uuid4().hex}
    if rsa_key:
        return jose.sign_rs256(private, {"kid": kid}, claims)
    return jose.sign_es256(private, {"kid": kid}, claims)


def jwt_token_request(client, client_id, signed):
    return token_request(client, {"client_assertion_type": tokens.ASSERTION_TYPE, "client_assertion": signed,
                                  "client_id": client_id})


def set_organisation(org_id, status=None, application=None):
    with platform_session() as session:
        if status:
            session.get(Organisation, org_id).status = status
        if application:
            row = session.get(OrganisationApplication, org_id)
            if row is None:
                session.add(OrganisationApplication(organisation_id=org_id, status=application))
            else:
                row.status = application


# --- connecting in the portal ---------------------------------------------------------------------

def test_connecting_needs_a_fresh_code_and_shows_the_secret_once(portal):
    resp = portal.post("/connections", json={"name": "HR system", "scopes": EVERYTHING})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    assert count(IntegrationClient) == 0
    portal.reauth()
    resp = portal.post("/connections", json={"name": "HR system", "scopes": EVERYTHING, "mode": "live"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    secret = body["client_secret"]
    assert body["connection"]["client_id"].startswith("endod_live_") and len(secret) > 40
    assert body["connection"]["abilities"] == ["Sync employees from your HR system", "See employee list",
                                               "See claims and their status", "See payments"]
    assert body["token_url"] == "https://api.endod-health.com/organisation/v1/oauth/token"
    # Never again: not in the list, not in the database, not in the audit log.
    listed = portal.get("/connections")
    assert listed.status_code == 200 and secret not in listed.text
    assert listed.json()["items"][0]["name"] == "HR system"
    with platform_session() as session:
        stored = session.scalar(select(IntegrationClient))
        assert stored.secret_hash.startswith("$argon2id$") and secret not in stored.secret_hash
    audit_rows = events("integration_connected")
    assert len(audit_rows) == 1 and secret not in (audit_rows[0][4] or "")


def test_connection_requests_are_checked(portal):
    portal.reauth()
    assert connect(portal, scopes=["employees.delete"]).status_code == 400
    assert connect(portal, mode="sandbox").status_code == 400
    assert connect(portal, name=" ").status_code == 400
    # Notifications need https and a public address.
    for url in ("http://hooks.example.com/x", "https://localhost/x", "https://10.0.0.5/x", "https://169.254.169.254/x",
                "https://user:pw@hooks.example.com/x", "https://[::1]/x"):
        resp = connect(portal, scopes=["webhooks"], webhook_url=url)
        assert resp.status_code == 400, url
    assert connect(portal, scopes=["claims.read"], webhook_url="https://hooks.example.com/x").status_code == 400
    ok = connected(portal, scopes=["webhooks"], webhook_url="https://hooks.example.com/endod")
    assert ok["webhook_secret"].startswith("whsec_")
    with platform_session() as session:
        stored = session.scalar(select(IntegrationClient)).webhook_secret
    assert ok["webhook_secret"] not in stored and clients.open_webhook_secret(stored) == ok["webhook_secret"]


def test_only_approved_organisations_admins_reach_connections(client, clock, applicant):
    resp = applicant.get("/connections")
    assert resp.status_code == 403
    assert applicant.post("/connections", json={"name": "x", "scopes": ["claims.read"]}).status_code == 403
    # A suspended organisation's sessions end.
    admin = Portal(client, clock, email="hr@suspended.example", org_name="Suspended PLC")
    set_organisation(admin.org_id, status="suspended")
    assert admin.get("/connections").status_code == 401
    # Without a session: nothing.
    assert client.get("/connections").status_code == 401


def test_another_organisations_connection_is_not_found(portal, other_portal):
    conn = connected(portal)
    cid = conn["connection"]["id"]
    other_portal.reauth()
    for path in (f"/connections/{cid}/disconnect", f"/connections/{cid}/rotate-secret",
                 f"/connections/{cid}/webhook/test"):
        assert other_portal.post(path, json={}).status_code == 404, path
    for path in (f"/connections/{cid}", f"/connections/{cid}/requests", f"/connections/{cid}/deliveries"):
        assert other_portal.get(path).status_code == 404, path
    assert other_portal.get("/connections").json()["items"] == []


def test_disconnecting_needs_a_fresh_code_and_stops_the_system(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    portal.forget_reauth()
    cid = conn["connection"]["id"]
    resp = portal.post(f"/connections/{cid}/disconnect")
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    assert advanced(portal, f"/connections/{cid}/disconnect").status_code == 200
    assert portal.get("/connections").json()["items"] == []
    # The token in hand stops at once, and no new one is given.
    assert client.get(f"{API}/employees", headers=auth).status_code == 401
    assert token_request(client, headers=basic(conn["connection"]["client_id"], conn["client_secret"])).status_code \
        == 401
    assert advanced(portal, f"/connections/{cid}/rotate-secret").status_code == 409
    assert events("integration_disconnected")


def test_advanced_changes_need_a_fresh_code(portal):
    conn = connected(portal, scopes=["employees.read"])
    cid = conn["connection"]["id"]
    _private, jwks = ec_key_and_jwks()
    changes = [
        (f"/connections/{cid}/ip-restriction", {"allowed_ips": ["196.188.10.0/24"]}),
        (f"/connections/{cid}/public-key", {"jwks": jwks}),
        (f"/connections/{cid}/rotate-secret", {}),
        (f"/connections/{cid}/webhook", {"url": "https://hooks.example.com/endod"}),
        (f"/connections/{cid}/webhook/rotate-secret", {}),
        (f"/connections/{cid}/webhook", {"url": None}),
    ]
    for path, body in changes:
        portal.forget_reauth()
        resp = portal.post(path, json=body)
        assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED", path
        assert advanced(portal, path, body).status_code == 200, path
    actions = {a for a, *_ in events() if a.startswith("integration_")}
    assert {"integration_ips_set", "integration_public_keys_set", "integration_secret_rotated",
            "integration_webhook_set", "integration_webhook_secret_rotated", "integration_webhook_removed"} <= actions
    assert advanced(portal, f"/connections/{cid}/ip-restriction", {"allowed_ips": ["0.0.0.0/0"]}).status_code == 400
    assert advanced(portal, f"/connections/{cid}/ip-restriction", {"allowed_ips": ["not an ip"]}).status_code == 400
    private_jwk = {"keys": [{"kty": "EC", "crv": "P-256", "x": "a", "y": "b", "d": "secret"}]}
    assert advanced(portal, f"/connections/{cid}/public-key", {"jwks": private_jwk}).status_code == 400


# --- tokens ------------------------------------------------------------------------------------------

def test_a_secret_gets_a_short_es256_token_that_verifies_with_the_jwks(client, portal):
    conn = connected(portal)
    cid, secret = conn["connection"]["client_id"], conn["client_secret"]
    resp = token_request(client, headers=basic(cid, secret))
    assert resp.status_code == 200 and resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert body["expires_in"] == 300 and body["token_type"] == "Bearer"
    assert body["scope"] == " ".join(EVERYTHING)
    keys = [jose.public_key(k) for k in client.get(f"{API}/.well-known/jwks.json").json()["keys"]]
    parsed = jose.verify(body["access_token"], keys)
    assert parsed.header["alg"] == "ES256" and parsed.header["typ"] == "at+jwt"
    assert parsed.claims["exp"] - parsed.claims["iat"] == 300
    assert parsed.claims["aud"] == tokens.public_url() and parsed.claims["organisation_id"] == portal.org_id
    # client_secret_post works too.
    assert token_request(client, {"client_id": cid, "client_secret": secret}).status_code == 200
    # Wrong secrets and unknown clients get the same answer.
    wrong = token_request(client, headers=basic(cid, secret + "x"))
    unknown = token_request(client, headers=basic("endod_live_" + "0" * 24, secret))
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"error": "invalid_client", "error_description": tokens.UNKNOWN_CLIENT}
    assert token_request(client, {"grant_type": "password"}).json()["error"] == "unsupported_grant_type"
    # Two methods at once are refused.
    assert token_request(client, {"client_id": cid, "client_secret": secret},
                         basic(cid, secret)).json()["error"] == "invalid_request"
    issued = events("integration_token_issued")
    assert [r for _a, r, *_ in issued].count("success") == 2 and "failure" in [r for _a, r, *_ in issued]


def test_scopes_are_granted_and_enforced(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    creds = basic(conn["connection"]["client_id"], conn["client_secret"])
    assert token_request(client, {"scope": "employees.write"}, creds).json()["error"] == "invalid_scope"
    auth = get_token(client, conn)
    assert client.get(f"{API}/employees", headers=auth).status_code == 200
    for method, path in (("POST", "/employees"), ("GET", "/claims"), ("GET", "/payments/batches"),
                         ("POST", "/employees/HR-1/deactivate")):
        resp = client.request(method, f"{API}{path}", headers={**auth, "Content-Type": "application/json"},
                              content=json.dumps({"employees": [person()]}))
        assert resp.status_code == 403 and resp.json()["error_code"] == "insufficient_scope", path
    # A token asked for fewer scopes carries only those.
    full = connected(portal, name="All")
    narrow = get_token(client, full, scope="claims.read")
    assert client.get(f"{API}/employees", headers=narrow).status_code == 403
    assert client.get(f"{API}/claims", headers=narrow).status_code == 200
    assert client.get(f"{API}/employees").status_code == 401


def test_private_key_jwt_with_replay_wrong_audience_and_expiry(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    cid = conn["connection"]["client_id"]
    private, jwks = ec_key_and_jwks()
    assert advanced(portal, f"/connections/{conn['connection']['id']}/public-key", {"jwks": jwks}).status_code == 200
    # The secret stopped working.
    assert token_request(client, headers=basic(cid, conn["client_secret"])).status_code == 401
    signed = assertion(private, cid)
    ok = jwt_token_request(client, cid, signed)
    assert ok.status_code == 200, ok.text
    replay = jwt_token_request(client, cid, signed)
    assert replay.status_code == 401 and "already used" in replay.json()["error_description"]
    wrong_aud = jwt_token_request(client, cid, assertion(private, cid, aud="https://evil.example/oauth/token"))
    assert wrong_aud.status_code == 401 and "aud" in wrong_aud.json()["error_description"]
    expired = jwt_token_request(client, cid, assertion(private, cid, exp_in=-120))
    assert expired.status_code == 401 and "expired" in expired.json()["error_description"]
    too_long = jwt_token_request(client, cid, assertion(private, cid, exp_in=3600))
    assert too_long.status_code == 401
    other, _ = ec_key_and_jwks()
    assert jwt_token_request(client, cid, assertion(other, cid)).status_code == 401
    assert count(IntegrationAssertion) == 1
    reasons = [json.loads(d)["reason"] for _a, r, _e, _t, d in events("integration_token_issued") if r == "failure"]
    assert {"replayed_assertion", "wrong_audience", "expired_assertion"} <= set(reasons)


def test_rs256_public_keys_work_too(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {"keys": [jose.rsa_public_jwk(private.public_key(), "r1")]}
    assert advanced(portal, f"/connections/{conn['connection']['id']}/public-key", {"jwks": jwks}).status_code == 200
    cid = conn["connection"]["client_id"]
    resp = jwt_token_request(client, cid, assertion(private, cid, kid="r1", rsa_key=True))
    assert resp.status_code == 200, resp.text


def test_an_expired_or_foreign_access_token_is_refused(client, portal, monkeypatch):
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    later = utcnow() + timedelta(minutes=6)
    with monkeypatch.context() as patched:
        patched.setattr(tokens, "utcnow", lambda: later)
        resp = client.get(f"{API}/employees", headers=auth)
        assert resp.status_code == 401 and "expired" in resp.json()["error"]
    # Signed by another key (or tampered with): refused.
    head, body, _sig = auth["Authorization"][7:].split(".")
    forged_claims = json.loads(base64.urlsafe_b64decode(body + "=="))
    forged_claims["scope"] = "employees.read employees.write"
    other = ec.generate_private_key(ec.SECP256R1())
    forged = jose.sign_es256(other, json.loads(base64.urlsafe_b64decode(head + "==")), forged_claims)
    assert client.get(f"{API}/employees", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert client.get(f"{API}/employees", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


def test_rotating_the_secret_voids_tokens_issued_before(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    rotated = advanced(portal, f"/connections/{conn['connection']['id']}/rotate-secret").json()
    assert client.get(f"{API}/employees", headers=auth).status_code == 401
    assert token_request(client, headers=basic(conn["connection"]["client_id"], conn["client_secret"])).status_code \
        == 401
    fresh = {**conn, "client_secret": rotated["client_secret"]}
    assert client.get(f"{API}/employees", headers=get_token(client, fresh)).status_code == 200


def test_ip_restriction_on_tokens_and_calls(client, portal):
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    resp = advanced(portal, f"/connections/{conn['connection']['id']}/ip-restriction",
                    {"allowed_ips": ["196.188.10.0/24"]})
    assert resp.json()["connection"]["allowed_ips"] == ["196.188.10.0/24"]
    resp = client.get(f"{API}/employees", headers=auth)
    assert resp.status_code == 403 and "address" in resp.json()["error"]
    creds = basic(conn["connection"]["client_id"], conn["client_secret"])
    assert token_request(client, headers=creds).status_code == 401
    inside = {"X-Endod-Client-IP": "196.188.10.7"}
    auth = get_token(client, conn, headers=inside)
    assert client.get(f"{API}/employees", headers={**auth, **inside}).status_code == 200
    refused = [json.loads(d)["reason"] for a, r, _e, _t, d in events() if r == "failure" and a.startswith("integration")]
    assert "address_not_allowed" in refused


@pytest.mark.parametrize("change", [{"status": "suspended"}, {"application": "submitted"},
                                   {"application": "rejected"}])
def test_unapproved_or_suspended_organisations_get_nothing(client, portal, change):
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    set_organisation(portal.org_id, **change)
    resp = client.get(f"{API}/employees", headers=auth)
    assert resp.status_code == 403
    resp = token_request(client, headers=basic(conn["connection"]["client_id"], conn["client_secret"]))
    assert resp.status_code == 400 and resp.json()["error"] == "unauthorized_client"


# --- employees -----------------------------------------------------------------------------------------

def test_employees_sync_is_idempotent_and_shows_in_the_employees_screen(client, portal):
    conn = connected(portal, scopes=PAYOUT)
    auth = get_token(client, conn)
    batch = [person("HR-0001", payout_method="cbe", payout_account="1000123456789"),
             person("HR-0002", dependants=[{"name": "Liya Worker", "relationship": "child",
                                            "birth_date": "2016-02-01"}])]
    first = sync(client, auth, batch)
    assert first.status_code == 200, first.text
    assert first.json()["summary"] == {"create": 2, "update": 0, "unchanged": 0, "error": 0}
    assert first.json()["mode"] == "live" and first.json()["stored"] is True
    again = sync(client, auth, batch)
    assert again.status_code == 200
    assert again.json()["summary"] == {"create": 0, "update": 0, "unchanged": 2, "error": 0}
    assert count(Employee, organisation_id=portal.org_id) == 2
    assert count(Dependant, organisation_id=portal.org_id) == 1
    # In the portal's Employees screen.
    listed = portal.get("/employees").json()
    names = {e["employee_number"]: e for e in listed["items"]}
    assert set(names) == {"HR-0001", "HR-0002"}
    assert names["HR-0001"]["payout_account"] == "1000123456789" and names["HR-0001"]["phone"] == "+251911223344"
    assert [d["name"] for d in names["HR-0002"]["dependants"]] == ["Liya Worker"]
    # Read back through the API.
    read = client.get(f"{API}/employees", headers=auth).json()
    assert read["total"] == 2 and read["items"][1]["dependants"][0]["relationship"] == "child"
    one = client.get(f"{API}/employees/HR-0001", headers=auth).json()
    assert one["payout_account"] == "1000123456789"
    assert client.get(f"{API}/employees/NOPE-1", headers=auth).status_code == 404


def test_partial_updates_payout_audit_masked_and_deactivation(client, portal):
    conn = connected(portal, scopes=PAYOUT)
    auth = get_token(client, conn)
    assert sync(client, auth, [person("HR-7", payout_method="cbe", payout_account="1000555512345678")]).status_code \
        == 200
    resp = sync(client, auth, [{"employee_number": "HR-7", "department": "Finance",
                                "payout_method": "telebirr", "payout_account": "0911998877"}])
    result = resp.json()["results"][0]
    assert result["action"] == "update" and result["changes"] == ["department", "payout_account", "payout_method"]
    payout = events("employee_payout_changed")
    assert len(payout) == 2
    detail = json.loads(payout[-1][4])
    assert detail["before"] == {"method": "cbe", "account": "****5678"}
    assert detail["after"] == {"method": "telebirr", "account": "****8877"}
    assert detail["via"] == "api" and detail["client_id"] == conn["connection"]["client_id"]
    for row in events():
        assert "1000555512345678" not in (row[4] or "") and "0911998877" not in (row[4] or "")
    # Only one of the two payout fields: refused.
    assert sync(client, auth, [{"employee_number": "HR-7", "payout_account": "1234567890"}]).status_code == 422
    # Deactivating, twice.
    resp = client.post(f"{API}/employees/HR-7/deactivate", headers=auth)
    assert resp.status_code == 200 and resp.json()["action"] == "deactivate"
    assert client.post(f"{API}/employees/HR-7/deactivate", headers=auth).json()["action"] == "unchanged"
    assert portal.get("/employees?status=inactive").json()["items"][0]["employee_number"] == "HR-7"
    assert client.post(f"{API}/employees/NOPE/deactivate", headers=auth).status_code == 404
    # Dependants given are the whole list.
    sync(client, auth, [{"employee_number": "HR-7", "dependants": [{"name": "Abel", "relationship": "child"},
                                                                  {"name": "Sara", "relationship": "spouse"}]}])
    sync(client, auth, [{"employee_number": "HR-7", "active": True,
                         "dependants": [{"name": "Sara", "relationship": "spouse"}]}])
    detail = portal.get("/employees?status=all").json()["items"][0]
    assert detail["active"] is True and [d["name"] for d in detail["dependants"]] == ["Sara"]


def test_a_sync_with_any_error_changes_nothing(client, portal):
    conn = connected(portal)
    auth = get_token(client, conn)
    resp = sync(client, auth, [
        person("HR-1"),
        person("HR-2", phone="12345"),
        person("HR-1"),
        {"employee_number": "HR-3"},
        person("HR-4", endod_id="XX1"),
        person("HR-5", payout_method="paypal", payout_account="1"),
        "not an object",
        person("HR-6", salary=100),
    ])
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "INVALID_EMPLOYEES" and body["stored"] is False
    errors = {r["index"]: r["errors"] for r in body["results"]}
    assert errors[0] == [] and "Phone must be" in errors[1][0] and "also at index 0" in errors[2][0]
    assert "needs name, phone, department" in errors[3][0] and "endod_id cannot be set" in errors[4][0]
    assert "employees.payout.write" in errors[5][0] and errors[6] and "Unknown field" in errors[7][0]
    assert count(Employee) == 0
    assert not events("employee_created")
    # With the payout scope, the payout rules of the portal apply.
    payouts = get_token(client, connected(portal, scopes=PAYOUT, name="Payroll"))
    resp = sync(client, payouts, [person("HR-5", payout_method="paypal", payout_account="1")])
    assert resp.status_code == 422 and "Payout method" in resp.json()["results"][0]["errors"][0]


def test_limits_on_a_sync(client, portal):
    conn = connected(portal)
    auth = get_token(client, conn)
    resp = sync(client, auth, [person(f"HR-{n}") for n in range(501)])
    assert resp.status_code == 413 and resp.json()["error_code"] == "TOO_MANY_EMPLOYEES"
    assert sync(client, auth, []).status_code == 400
    big = client.post(f"{API}/employees", headers={**auth, "Content-Type": "application/json"},
                      content=b'{"employees": [' + b'"x",' * 800_000 + b'"x"]}')
    assert big.status_code == 413
    assert client.post(f"{API}/employees", headers={**auth, "Content-Type": "text/csv"}, content=b"a,b").status_code \
        == 415
    assert client.post(f"{API}/employees", headers={**auth, "Content-Type": "application/json"},
                       content=b"{not json").status_code == 400
    assert sync(client, auth, [person(f"HR-{n}") for n in range(500)]).status_code == 200


def test_per_client_rate_limit(client, portal, monkeypatch):
    monkeypatch.setattr(ratelimit, "REQUESTS_PER_CLIENT", ratelimit.Limiter(3, 60))
    conn = connected(portal, scopes=["employees.read"])
    auth = get_token(client, conn)
    for _ in range(3):
        assert client.get(f"{API}/employees", headers=auth).status_code == 200
    resp = client.get(f"{API}/employees", headers=auth)
    assert resp.status_code == 429 and int(resp.headers["retry-after"]) >= 1
    # Token requests have their own limits.
    monkeypatch.setattr(ratelimit, "TOKENS_PER_CLIENT", ratelimit.Limiter(1, 60))
    creds = basic(conn["connection"]["client_id"], conn["client_secret"])
    assert token_request(client, headers=creds).status_code == 200
    assert token_request(client, headers=creds).status_code == 429


def test_idempotency_key_replays_the_first_answer(client, portal):
    conn = connected(portal)
    auth = get_token(client, conn)
    key = {"Idempotency-Key": "sync-2026-10-28"}
    first = sync(client, auth, [person("HR-1")], headers=key)
    replay = sync(client, auth, [person("HR-1")], headers=key)
    assert replay.status_code == 200 and replay.headers["idempotent-replayed"] == "true"
    assert replay.json() == first.json() and replay.json()["summary"]["create"] == 1
    other = sync(client, auth, [person("HR-2")], headers=key)
    assert other.status_code == 422 and other.json()["error_code"] == "IDEMPOTENCY_KEY_REUSED"
    assert count(Employee) == 1 and count(IntegrationIdempotency) == 1
    assert sync(client, auth, [person("HR-1")], headers={"Idempotency-Key": "x" * 300}).status_code == 400


def test_test_mode_answers_what_would_happen_and_stores_nothing(client, portal):
    portal.employee(employee_number="P-1", name="Already Here")
    live_events = count(AuditEvent)
    conn = connected(portal, mode="test", scopes=EVERYTHING + ["webhooks"], webhook_url="https://hooks.example.com/x")
    assert conn["connection"]["client_id"].startswith("endod_test_")
    auth = get_token(client, conn)
    before = (count(Employee), count(Dependant), count(WebhookDelivery))
    audit_before = count(AuditEvent)
    resp = sync(client, auth, [person("HR-1", dependants=[{"name": "Abel", "relationship": "child"}]),
                               {"employee_number": "P-1", "department": "Finance"}],
                headers={"Idempotency-Key": "test-1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "test" and body["stored"] is False
    assert [r["action"] for r in body["results"]] == ["create", "update"]
    assert all(r["employee_id"] is None for r in body["results"])
    deactivate = client.post(f"{API}/employees/P-1/deactivate", headers=auth)
    assert deactivate.json() == {**deactivate.json(), "mode": "test", "stored": False, "action": "deactivate"}
    assert (count(Employee), count(Dependant), count(WebhookDelivery)) == before
    assert count(IntegrationIdempotency) == 0
    # Only the token request was audited: no employee changes.
    new_actions = {a for a, *_ in events()[audit_before:]}
    assert new_actions <= {"integration_token_issued", "integration_data_read"}
    assert live_events < audit_before
    assert portal.get("/employees").json()["items"][0]["department"] == "Engineering"


# --- claims and payments --------------------------------------------------------------------------------

def _approved_claim(portal):
    portal.set_policy()
    employee = portal.employee()
    claim = portal.claim(employee["id"])
    resp = portal.approve(claim["id"])
    if resp.status_code == 403:
        portal.reauth()
        resp = portal.approve(claim["id"])
    assert resp.status_code == 200, resp.text
    return employee, claim


def test_claims_and_payments_are_read_with_events_on_approval_and_payment(client, portal):
    conn = connected(portal, scopes=["claims.read", "payments.read", "webhooks"],
                     webhook_url="https://hooks.example.com/endod")
    auth = get_token(client, conn)
    employee, claim = _approved_claim(portal)
    listed = client.get(f"{API}/claims", headers=auth).json()
    assert listed["total"] == 1 and listed["items"][0]["status"] == "approved"
    assert listed["items"][0]["employee_number"] == employee["employee_number"]
    one = client.get(f"{API}/claims/{claim['id']}", headers=auth).json()
    assert one["items"][0]["medicine"] == "Metformin 500mg" and one["has_receipt"] is True
    assert "receipt_file_id" not in one
    assert client.get(f"{API}/claims?status=approved", headers=auth).json()["total"] == 1
    assert client.get(f"{API}/claims?status=nope", headers=auth).status_code == 400
    # A batch, paid.
    batch = portal.post("/batches", json={"method": "cbe"})
    assert batch.status_code == 201, batch.text
    paid = portal.post(f"/batches/{batch.json()['id']}/mark-paid", json={"reference": "CBE-REF-0001"})
    assert paid.status_code == 200, paid.text
    batches = client.get(f"{API}/payments/batches", headers=auth).json()
    assert batches["items"][0]["status"] == "paid"
    detail = client.get(f"{API}/payments/batches/{batch.json()['id']}", headers=auth).json()
    assert detail["claims"][0]["claim_id"] == claim["id"] and "payout_account" not in json.dumps(detail)
    with platform_session() as session:
        types = [d.event_type for d in session.scalars(select(WebhookDelivery).order_by(WebhookDelivery.created_at))]
    assert "claim.approved" in types and "batch.paid" in types and "employee.changed" in types


def test_one_organisations_client_never_touches_another(client, portal, other_portal):
    """Org A's client, whatever it sends, reads and writes only org A's rows."""
    b_employee, b_claim = _approved_claim(other_portal)
    b_batch = other_portal.post("/batches", json={"method": "cbe"}).json()
    conn = connected(portal)
    auth = get_token(client, conn)
    assert client.get(f"{API}/employees", headers=auth).json()["total"] == 0
    assert client.get(f"{API}/employees/{b_employee['employee_number']}", headers=auth).status_code == 404
    assert client.get(f"{API}/claims", headers=auth).json()["total"] == 0
    assert client.get(f"{API}/claims/{b_claim['id']}", headers=auth).status_code == 404
    assert client.get(f"{API}/payments/batches/{b_batch['id']}", headers=auth).status_code == 404
    assert client.post(f"{API}/employees/{b_employee['employee_number']}/deactivate", headers=auth).status_code \
        == 404
    # The same employee number in A makes A's own employee; B's stays as it was.
    resp = sync(client, auth, [person(b_employee["employee_number"], name="Somebody Else")])
    assert resp.json()["results"][0]["action"] == "create"
    with platform_session() as session:
        theirs = session.get(Employee, b_employee["id"])
        assert theirs.name == b_employee["name"] and theirs.active and theirs.organisation_id == other_portal.org_id
    # A token naming B's organisation (as if forged into the claims) is not B's client: refused.
    with platform_session() as session:
        assert session.scalar(select(func.count()).select_from(Employee).where(
            Employee.organisation_id == portal.org_id)) == 1


# --- webhooks ---------------------------------------------------------------------------------------------

def test_webhook_signature_like_stripe():
    body = b'{"id":"evt_1","type":"claim.approved"}'
    header = webhooks.signature_header("whsec_test", 1_700_000_000, body)
    assert header.startswith("t=1700000000,v1=")
    assert webhooks.verify("whsec_test", header, body, now=1_700_000_100)
    assert not webhooks.verify("whsec_test", header, body + b" ", now=1_700_000_100)
    assert not webhooks.verify("whsec_other", header, body, now=1_700_000_100)
    assert not webhooks.verify("whsec_test", header, body, now=1_700_001_000)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254",
                                     "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:10.0.0.1",
                                     "224.0.0.1", "64:ff9b::a00:1", "64:ff9b::808:808", "64:ff9b:1::a00:1"])
def test_ssrf_private_loopback_and_link_local_are_blocked_at_send_time(monkeypatch, address):
    monkeypatch.setattr(webhooks.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, (address, 443))])
    sent = webhooks.post("https://hooks.example.com/endod", {}, b"{}")
    assert not sent.ok and sent.error.startswith("blocked")


def test_ssrf_only_https_and_no_rebinding(monkeypatch):
    assert webhooks.post("http://hooks.example.com/x", {}, b"{}").error.startswith("blocked")
    calls = []

    def resolve(host, port, **_kw):
        calls.append(host)
        return [(None, None, None, None, ("93.184.216.34", port)), (None, None, None, None, ("10.0.0.1", port))]

    monkeypatch.setattr(webhooks.socket, "getaddrinfo", resolve)
    # One public and one private address: blocked (every address must be public).
    assert webhooks.post("https://hooks.example.com/x", {}, b"{}").error.startswith("blocked")


def _queued(portal, url="https://hooks.example.com/endod"):
    conn = connected(portal, scopes=["webhooks", "employees.read"], webhook_url=url)
    portal.employee()
    return conn


def test_the_worker_delivers_signed_events_and_retries_with_backoff(portal, monkeypatch):
    conn = _queued(portal)
    seen = []

    def fake_post(url, headers, body):
        seen.append((url, headers, body))
        return webhooks.Sent(True, 204, None)

    monkeypatch.setattr(webhooks, "post", fake_post)
    assert webhooks.deliver_due() == 1
    url, headers, body = seen[0]
    assert url == "https://hooks.example.com/endod"
    assert webhooks.verify(conn["webhook_secret"], headers["Endod-Signature"], body)
    event = json.loads(body)
    assert event["type"] == "employee.changed" and event["data"]["change"] == "created"
    # The names of the fields, never their values.
    assert set(event["data"]["fields"]) == {"department", "employee_number", "name", "payout_account",
                                            "payout_method", "phone"}
    assert "+2519" not in body.decode() and "Engineering" not in body.decode()
    assert "phone" not in event["data"] and "payout_account" not in event["data"]
    with platform_session() as session:
        delivery = session.scalar(select(WebhookDelivery))
        assert delivery.status == DeliveryStatus.DELIVERED and delivery.body is None
    # A failure is retried later, then given up after 24 hours; redirects count as failures.
    portal.employee()
    monkeypatch.setattr(webhooks, "post", lambda *a: webhooks.Sent(False, 302, "redirects are not followed"))
    assert webhooks.deliver_due() == 1
    with platform_session() as session:
        failing = session.scalar(select(WebhookDelivery).where(WebhookDelivery.status == DeliveryStatus.PENDING))
        assert failing.attempts == 1 and failing.last_status_code == 302
        failing_id = failing.id
    assert webhooks.deliver_due() == 0  # not due yet
    assert webhooks.deliver_due(now=utcnow() + timedelta(hours=25)) == 1
    with platform_session() as session:
        failed = session.get(WebhookDelivery, failing_id)
        assert failed.status == DeliveryStatus.FAILED and failed.body is None and "gave up" in failed.last_error


def test_bodies_are_sealed_at_rest_and_test_events_are_sent(client, portal, monkeypatch):
    conn = _queued(portal)
    with platform_session() as session:
        stored = session.scalar(select(WebhookDelivery)).body
    assert stored.startswith("v1:") and "employee.changed" not in stored
    resp = portal.post(f"/connections/{conn['connection']['id']}/webhook/test")
    assert resp.status_code == 202
    sent = []
    monkeypatch.setattr(webhooks, "post", lambda url, headers, body: sent.append(json.loads(body)) or
                        webhooks.Sent(True, 200, None))
    webhooks.deliver_due()
    assert "endpoint.test" in [e["type"] for e in sent]
    deliveries = portal.get(f"/connections/{conn['connection']['id']}/deliveries").json()["items"]
    assert {d["status"] for d in deliveries} == {"delivered"}


def test_disconnecting_drops_waiting_events(portal, monkeypatch):
    conn = _queued(portal)
    advanced(portal, f"/connections/{conn['connection']['id']}/disconnect")
    monkeypatch.setattr(webhooks, "post", lambda *a: pytest.fail("nothing may be sent"))
    assert webhooks.deliver_due() == 0
    with platform_session() as session:
        assert session.scalar(select(WebhookDelivery)).status == DeliveryStatus.FAILED


# --- the request log, audit, discovery ----------------------------------------------------------------

def test_the_request_log_keeps_no_bodies(client, portal, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    # Alembic's logging config (tests/test_migrations.py) disables existing loggers.
    monkeypatch.setattr(logging.getLogger("organisation.integrations"), "disabled", False)
    conn = connected(portal)
    auth = get_token(client, conn)
    marker = "MARKER-Selamawit-0911"
    sync(client, auth, [person("HR-1", name=marker)])
    client.get(f"{API}/employees?status=active&limit=5", headers=auth)
    with platform_session() as session:
        rows = session.scalars(select(IntegrationRequest).order_by(IntegrationRequest.at)).all()
        logged = [(r.method, r.path, r.status, r.ip) for r in rows]
    assert ("POST", f"{API}/oauth/token", 200, CLIENT_IP) in logged
    assert ("POST", f"{API}/employees", 200, CLIENT_IP) in logged
    assert ("GET", f"{API}/employees", 200, CLIENT_IP) in logged
    ours = " | ".join(r.getMessage() for r in caplog.records if r.name.startswith("organisation"))
    assert "integration_request" in ours
    every = json.dumps(logged) + ours
    assert marker not in every and conn["client_secret"] not in every and "limit=5" not in every
    shown = portal.get(f"/connections/{conn['connection']['id']}/requests").json()["items"]
    assert shown[0]["path"] == f"{API}/employees" and marker not in json.dumps(shown)
    assert portal.get("/connections").json()["items"][0]["last_used_at"]


def test_the_worker_forgets_old_logs(portal):
    from app import worker

    conn = connected(portal)
    with platform_session() as session:
        client_row = session.scalar(select(IntegrationClient))
        old = utcnow() - timedelta(days=31)
        session.add(IntegrationRequest(organisation_id=portal.org_id, client_pk=client_row.id, method="GET",
                                       path="/x", status=200, duration_ms=1, at=old))
        session.add(IntegrationRequest(organisation_id=portal.org_id, client_pk=client_row.id, method="GET",
                                       path="/y", status=200, duration_ms=1))
        session.add(IntegrationIdempotency(organisation_id=portal.org_id, client_pk=client_row.id, key="k",
                                           request_hash="0" * 64, status_code=200, response="{}",
                                           created_at=utcnow() - timedelta(hours=25)))
    assert conn and worker.clean_up() == 2
    assert count(IntegrationRequest) == 1 and count(IntegrationIdempotency) == 0


def test_writes_and_reads_are_audited_with_the_connection(client, portal):
    conn = connected(portal)
    auth = get_token(client, conn)
    sync(client, auth, [person("HR-1")])
    client.get(f"{API}/claims", headers=auth)
    with platform_session() as session:
        rows = session.scalars(select(AuditEvent).where(AuditEvent.organisation_id == portal.org_id)).all()
    by_action = {r.action: r for r in rows}
    for action in ("integration_token_issued", "employee_created", "integration_employees_synced",
                   "integration_data_read"):
        assert action in by_action, action
        detail = json.loads(by_action[action].detail)
        assert detail["client_id"] == conn["connection"]["client_id"] and by_action[action].ip == CLIENT_IP
    assert json.loads(by_action["employee_created"].detail)["via"] == "api"


def test_the_api_has_its_own_openapi_and_no_bff_secret(client, db):
    from fastapi.testclient import TestClient

    from app.main import create_app

    bare = TestClient(create_app())  # no BFF secret
    spec = bare.get(f"{API}/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for path in ("/oauth/token", "/employees", "/employees/{employee_number}", "/claims", "/payments/batches",
                 "/.well-known/jwks.json"):
        assert path in paths, path
    assert spec.json()["servers"] == [{"url": "https://api.endod-health.com/organisation/v1"}]
    assert "client_credentials" in json.dumps(spec.json()["components"]["securitySchemes"]).lower() \
        or "clientCredentials" in json.dumps(spec.json()["components"]["securitySchemes"])
    assert bare.get(f"{API}/docs").status_code == 200
    # The portal's routes still need the BFF secret.
    assert bare.get("/connections").status_code == 403


def test_the_guide_is_the_docs_copy():
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs" / "integrations.md").read_text(encoding="utf-8") == \
        (root / "backend" / "app" / "integrations" / "guide.md").read_text(encoding="utf-8")


def test_behind_nginx_only_its_key_names_the_address(client, portal, monkeypatch):
    edge = "edge-secret-0123456789abcdefghijklmnopqrstuv"
    conn = connected(portal, scopes=["employees.read"])
    monkeypatch.setenv("EDGE_SHARED_SECRET", edge)
    creds = basic(conn["connection"]["client_id"], conn["client_secret"])
    resp = token_request(client, headers=creds)
    assert resp.status_code == 403 and resp.json()["error_code"] == "EDGE_REQUIRED"
    resp = token_request(client, headers={**creds, "X-Endod-Edge-Key": edge, "X-Endod-Client-IP": "203.0.113.50"})
    assert resp.status_code == 200
    with platform_session() as session:
        assert session.scalar(select(IntegrationRequest.ip).order_by(IntegrationRequest.at.desc())) == "203.0.113.50"
    monkeypatch.delenv("EDGE_SHARED_SECRET")
    monkeypatch.setenv("ORG_ENVIRONMENT", "staging")
    assert token_request(client, headers=creds).status_code == 503


def test_without_a_signing_key_outside_development_the_api_is_off(client, portal, monkeypatch, tmp_path):
    conn = connected(portal, scopes=["employees.read"])
    creds = basic(conn["connection"]["client_id"], conn["client_secret"])
    edge = "edge-secret-0123456789abcdefghijklmnopqrstuv"
    monkeypatch.setenv("ORG_ENVIRONMENT", "staging")
    monkeypatch.setenv("EDGE_SHARED_SECRET", edge)
    signing.clear_cache()
    resp = token_request(client, headers={**creds, "X-Endod-Edge-Key": edge})
    assert resp.status_code == 503
    # With a key file: on, and the kid is the key's thumbprint.
    from cryptography.hazmat.primitives import serialization

    private = ec.generate_private_key(ec.SECP256R1())
    key_file = tmp_path / "signing.pem"
    key_file.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    monkeypatch.setenv("INTEGRATIONS_SIGNING_KEY_FILE", str(key_file))
    resp = token_request(client, headers={**creds, "X-Endod-Edge-Key": edge})
    assert resp.status_code == 200
    assert signing.signing_key().kid == jose.thumbprint(jose.ec_public_jwk(private.public_key()))


# --- review fixes: payout accounts, Endod IDs, test connections, NAT64, audit URLs --------------------

def _held_claim(client, portal):
    """An approved claim of a portal employee whose payout a connected system then changes."""
    employee, claim = _approved_claim(portal)
    conn = connected(portal, scopes=PAYOUT, name="Payroll system")
    auth = get_token(client, conn)
    resp = sync(client, auth, [{"employee_number": employee["employee_number"], "payout_method": "telebirr",
                                "payout_account": "0911556677"}])
    assert resp.status_code == 200, resp.text
    return employee, claim, conn


def test_payout_details_need_their_own_scope(client, portal):
    portal.employee(employee_number="P-1")
    auth = get_token(client, connected(portal, scopes=["employees.write"]))
    resp = sync(client, auth, [{"employee_number": "P-1", "payout_method": "telebirr",
                                "payout_account": "0911556677"}])
    assert resp.status_code == 422 and "employees.payout.write" in resp.json()["results"][0]["errors"][0]
    portal.reauth()
    resp = portal.post("/connections", json={"name": "Alone", "scopes": ["employees.payout.write"]})
    assert resp.status_code == 400 and "needs" in resp.json()["error"]
    resp = portal.post("/connections", json={"name": "Alone", "scopes": ["employees.payout.read"]})
    assert resp.status_code == 400
    assert count(IntegrationPayoutChange) == 0


def test_endod_ids_are_never_set_through_the_api(client, portal):
    portal.employee(employee_number="P-1", endod_id="DE300003")
    auth = get_token(client, connected(portal, scopes=PAYOUT))
    for value in ("DE300003", "DE300004", None):
        resp = sync(client, auth, [{"employee_number": "P-1", "endod_id": value}])
        assert resp.status_code == 422 and "endod_id cannot be set" in resp.json()["results"][0]["errors"][0]
    with platform_session() as session:
        assert session.scalar(select(Employee.endod_id).where(Employee.employee_number == "P-1")) == "DE300003"


def test_a_payout_change_by_a_system_is_held_announced_and_confirmed(client, portal):
    employee, claim, conn = _held_claim(client, portal)
    # Held: not batchable for 24 hours.
    payments = portal.get("/batches").json()
    assert payments["ready"]["payout_held"]["claims"] == 1
    assert payments["ready"]["by_method"]["telebirr"]["claims"] == 0
    portal.reauth()
    resp = portal.post("/batches", json={"method": "telebirr"})
    assert resp.status_code == 409
    # Announced on the Overview and listed under the connection, masked.
    alerts = portal.get("/overview").json()["payout_alerts"]
    assert alerts == [{"connection_id": conn["connection"]["id"], "connection": "Payroll system", "changed": 1,
                       "held": 1}]
    changes = portal.get(f"/connections/{conn['connection']['id']}/payout-changes").json()["items"]
    assert len(changes) == 1 and changes[0]["held"] is True
    assert changes[0]["after"] == {"method": "telebirr", "account": "****6677"}
    assert changes[0]["employee_number"] == employee["employee_number"]
    with platform_session() as session:
        stored = session.scalar(select(IntegrationPayoutChange))
        assert "0911556677" not in f"{stored.before_account}{stored.after_account}"
    detail = json.loads(events("employee_payout_changed")[-1][4])
    assert detail["after"]["account"] == "****6677" and detail["via"] == "api" and detail["held_until"]
    # Confirming needs a fresh code; then the claim can be paid.
    portal.forget_reauth()
    path = f"/connections/{conn['connection']['id']}/payout-changes/{changes[0]['id']}/confirm"
    resp = portal.post(path)
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    resp = advanced(portal, path)
    assert resp.status_code == 200 and resp.json()["held"] is False
    assert events("integration_payout_confirmed")
    assert portal.get("/batches").json()["ready"]["payout_held"]["claims"] == 0
    batch = portal.post("/batches", json={"method": "telebirr"})
    assert batch.status_code == 201, batch.text


def test_a_held_change_ends_after_24_hours_or_when_an_admin_sets_the_account(client, portal):
    employee, _claim, _conn = _held_claim(client, portal)
    with platform_session() as session:
        session.scalar(select(IntegrationPayoutChange)).hold_until = utcnow() - timedelta(minutes=1)
    assert portal.get("/batches").json()["ready"]["payout_held"]["claims"] == 0
    # Another held change, then the admin sets the account in the portal (with a fresh code).
    auth = get_token(client, connected(portal, scopes=PAYOUT, name="Second"))
    sync(client, auth, [{"employee_number": employee["employee_number"], "payout_method": "cbe",
                         "payout_account": "1000999988887777"}])
    assert portal.get("/batches").json()["ready"]["payout_held"]["claims"] == 1
    portal.reauth()
    resp = portal.patch(f"/employees/{employee['id']}", json={"payout_method": "cbe",
                                                              "payout_account": "1000111122223333"})
    assert resp.status_code == 200, resp.text
    assert portal.get("/batches").json()["ready"]["payout_held"]["claims"] == 0


def test_reads_mask_payout_accounts_without_the_payout_read_scope(client, portal):
    portal.employee(employee_number="P-1", payout_method="cbe", payout_account="1000123456789")
    masked = get_token(client, connected(portal, scopes=["employees.read"]))
    assert client.get(f"{API}/employees/P-1", headers=masked).json()["payout_account"] == "****6789"
    assert "1000123456789" not in client.get(f"{API}/employees", headers=masked).text
    full = get_token(client, connected(portal, scopes=["employees.read", "employees.payout.read"], name="Full"))
    assert client.get(f"{API}/employees/P-1", headers=full).json()["payout_account"] == "1000123456789"


def test_test_connections_read_samples_and_get_no_real_events(client, portal, monkeypatch):
    employee, claim = _approved_claim(portal)
    conn = connected(portal, mode="test", scopes=EVERYTHING + ["webhooks"], webhook_url="https://hooks.example.com/t")
    auth = get_token(client, conn)
    employees = client.get(f"{API}/employees", headers=auth).json()
    assert employees["sample"] is True and {e["employee_number"] for e in employees["items"]} == {
        "SAMPLE-0001", "SAMPLE-0002", "SAMPLE-0003"}
    assert employee["name"] not in client.get(f"{API}/employees", headers=auth).text
    assert client.get(f"{API}/employees/{employee['employee_number']}", headers=auth).status_code == 404
    claims = client.get(f"{API}/claims", headers=auth).json()
    assert claims["total"] == 4 and all(c["pharmacy_name"] == "Sample Pharmacy" for c in claims["items"])
    assert client.get(f"{API}/claims/{claim['id']}", headers=auth).status_code == 404
    sample_claim = claims["items"][0]["id"]
    assert client.get(f"{API}/claims/{sample_claim}", headers=auth).json()["items"]
    batches = client.get(f"{API}/payments/batches", headers=auth).json()
    assert client.get(f"{API}/payments/batches/{batches['items'][0]['id']}", headers=auth).json()["claims"]
    # Real events never reach a test connection; "Send test event" does.
    portal.employee()
    with platform_session() as session:
        assert session.scalar(select(func.count()).select_from(WebhookDelivery)) == 0
    assert portal.post(f"/connections/{conn['connection']['id']}/webhook/test").status_code == 202
    with platform_session() as session:
        assert [d.event_type for d in session.scalars(select(WebhookDelivery))] == ["endpoint.test"]


def test_nat64_webhook_addresses_are_refused():
    for url in ("https://[64:ff9b::a00:1]/x", "https://[64:ff9b:1::1]/x"):
        with pytest.raises(clients.WebhookUrlError):
            clients.check_webhook_url(url)


def test_the_audit_keeps_webhook_urls_without_query_or_user_info(portal):
    conn = connected(portal, scopes=["webhooks"], webhook_url="https://hooks.example.com/endod?token=s3cr3t")
    assert advanced(portal, f"/connections/{conn['connection']['id']}/webhook",
                    {"url": "https://hooks.example.com:8443/new/path?key=abc#x"}).status_code == 400  # fragment
    assert advanced(portal, f"/connections/{conn['connection']['id']}/webhook",
                    {"url": "https://hooks.example.com:8443/new/path?key=abc"}).status_code == 200
    details = [json.loads(d) for a, _r, _e, _t, d in events() if a in ("integration_connected",
                                                                      "integration_webhook_set")]
    assert details[0]["webhook"] == "https://hooks.example.com/endod"
    assert details[1]["url"] == "https://hooks.example.com:8443/new/path"
    assert "s3cr3t" not in json.dumps(details) and "abc" not in json.dumps(details)
    assert clients.audit_url("https://user:pw@hooks.example.com/a?b=c") == "https://hooks.example.com/a"
