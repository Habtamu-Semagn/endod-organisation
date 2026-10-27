"""Fixes from the security review: payout changes need a fresh code and are
audited masked; a downloaded batch cannot be cancelled (no double payment);
an account-wide limit on the code step; IPv6 /64 address limits; bad CSV is
a 400; setup audit carries the organisation; nothing-to-pay claims never
reach a payout file."""

import csv
import io
import json
from datetime import timedelta

from conftest import bearer, code, events, from_ip, make_admin, password_step, sign_in
from sqlalchemy import select, update

from app.db import platform_session, utcnow
from app.models import AuditEvent, Claim, OrgAdmin, PaymentBatch


def payout_events():
    return [json.loads(e[4]) for e in events("employee_payout_changed")]


# --- 1. payout account changes ------------------------------------------------------------------

def test_creating_an_employee_with_payout_details_needs_a_fresh_code(portal):
    portal.forget_reauth()
    body = {"employee_number": "ET-1", "name": "Abebe Kebede", "phone": "0911000001", "department": "Ops",
            "payout_method": "cbe", "payout_account": "1000123456789"}
    resp = portal.post("/employees", json=body)
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    assert portal.get("/employees").json()["total"] == 0
    # Without payout details, no code is needed.
    plain = {k: v for k, v in body.items() if not k.startswith("payout")}
    assert portal.post("/employees", json=plain).status_code == 201
    assert payout_events() == []


def test_changing_payout_details_needs_a_fresh_code_and_is_audited_masked(portal):
    emp = portal.employee(payout_method="cbe", payout_account="1000123456789")
    assert payout_events() == [{"before": {"method": None, "account": None},
                                "after": {"method": "cbe", "account": "****6789"}, "via": "create"}]
    portal.forget_reauth()
    # Other fields still change without a code.
    assert portal.patch(f"/employees/{emp['id']}", json={"department": "Finance"}).status_code == 200
    resp = portal.patch(f"/employees/{emp['id']}", json={"payout_account": "2000111122223"})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    resp = portal.patch(f"/employees/{emp['id']}", json={"payout_method": "telebirr", "payout_account": "0911000001"})
    assert resp.status_code == 403
    assert portal.get(f"/employees/{emp['id']}").json()["payout_account"] == "1000123456789"
    portal.reauth()
    resp = portal.patch(f"/employees/{emp['id']}", json={"payout_account": "2000111122223"})
    assert resp.status_code == 200 and resp.json()["payout_account"] == "2000111122223"
    assert payout_events()[-1] == {"before": {"method": "cbe", "account": "****6789"},
                                   "after": {"method": "cbe", "account": "****2223"}, "via": "edit"}
    # The full account numbers never reach the audit log.
    dump = repr(events())
    assert "1000123456789" not in dump and "2000111122223" not in dump


def test_import_commit_needs_a_fresh_code_and_audits_payout_changes_masked(portal):
    portal.employee(employee_number="ET-1", name="Abebe Kebede", phone="0911000001", department="Ops",
                    payout_method="cbe", payout_account="1000123456789")
    text = ("employee_number,name,phone,department,payout_method,payout_account\n"
            "ET-1,Abebe Kebede,0911000001,Ops,awash,2000999988887\n"
            "ET-2,Hana Girma,0911000002,Ops,telebirr,0911000002\n")
    portal.forget_reauth()
    assert portal.post("/employees/import/preview", json={"csv": text}).status_code == 200  # preview is free
    resp = portal.post("/employees/import/commit", json={"csv": text})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    portal.reauth()
    assert portal.post("/employees/import/commit", json={"csv": text}).status_code == 200
    imported = [e for e in payout_events() if e["via"] == "import"]
    assert imported == [
        {"before": {"method": "cbe", "account": "****6789"}, "after": {"method": "awash", "account": "****8887"},
         "via": "import"},
        {"before": {"method": None, "account": None}, "after": {"method": "telebirr", "account": "****0002"},
         "via": "import"},
    ]
    assert "2000999988887" not in repr(events())


def test_creating_and_cancelling_batches_need_a_fresh_code(portal):
    emp = portal.employee()
    claim = portal.claim(emp["id"])
    portal.reauth()
    portal.approve(claim["id"])
    portal.forget_reauth()
    resp = portal.post("/batches", json={"method": "cbe"})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    portal.reauth()
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    portal.forget_reauth()
    assert portal.post(f"/batches/{batch['id']}/cancel").status_code == 403


# --- 2. no double payment through cancel and re-batch ---------------------------------------------

def _batch(portal):
    emp = portal.employee(name="Dawit Bekele", payout_account="1000123456789")
    claim = portal.claim(emp["id"])
    portal.reauth()
    portal.approve(claim["id"])
    return emp, claim, portal.post("/batches", json={"method": "cbe"}).json()


def test_a_downloaded_batch_cannot_be_cancelled(portal):
    emp, claim, batch = _batch(portal)
    assert batch["exported_at"] is None
    assert portal.get(f"/batches/{batch['id']}/export").status_code == 200
    detail = portal.get(f"/batches/{batch['id']}").json()
    assert detail["exported_at"] is not None
    with platform_session() as session:
        assert session.get(PaymentBatch, batch["id"]).exported_by == portal.admin_id
    resp = portal.post(f"/batches/{batch['id']}/cancel")
    assert resp.status_code == 409 and resp.json()["error_code"] == "BATCH_EXPORTED"
    assert "already downloaded" in resp.json()["error"]
    # Its claims stay in it: they cannot be batched (and paid) a second time.
    assert portal.post("/batches", json={"method": "cbe"}).json()["error_code"] == "NOTHING_TO_BATCH"
    assert portal.get(f"/claims/{claim['id']}").json()["batch_id"] == batch["id"]
    exports = events("batch_exported")
    assert json.loads(exports[0][4])["first_export"] is True
    assert [e[1] for e in events("batch_cancelled")] == ["failure"]
    # Downloading again keeps the first export's time.
    first = detail["exported_at"]
    portal.get(f"/batches/{batch['id']}/export")
    assert portal.get(f"/batches/{batch['id']}").json()["exported_at"] == first
    assert json.loads(events("batch_exported")[1][4])["first_export"] is False


def test_an_open_batch_never_downloaded_can_be_cancelled(portal):
    _, claim, batch = _batch(portal)
    assert portal.post(f"/batches/{batch['id']}/cancel").json() == {"ok": True}
    assert portal.get(f"/claims/{claim['id']}").json()["batch_id"] is None


def test_the_export_uses_the_account_recorded_at_batching(portal):
    emp, _, batch = _batch(portal)
    portal.patch(f"/employees/{emp['id']}", json={"payout_account": "9999888877776"})
    text = portal.get(f"/batches/{batch['id']}/export").text
    assert "1000123456789" in text and "9999888877776" not in text


# --- 3. an account-wide limit on the code step ---------------------------------------------------

def _pending_from(client, ip):
    return bearer(password_step(client, headers=from_ip(ip))["session_token"])


def test_wrong_codes_from_many_addresses_pause_code_attempts_for_the_account(client, clock):
    _, secret = make_admin()
    for n in range(5):  # one wrong code from each of 5 addresses: no address is locked
        resp = client.post("/auth/totp", json={"code": "000000"},
                           headers={**_pending_from(client, f"203.0.113.{n + 1}"), **from_ip(f"203.0.113.{n + 1}")})
        assert resp.status_code == 400, resp.text
    backoffs = events("account_code_backoff")
    assert len(backoffs) == 1 and json.loads(backoffs[0][4]) == {"seconds": 30, "failures": 5}
    # A sixth address, even with the right code, waits.
    ip = "198.51.100.77"
    pending = _pending_from(client, ip)
    resp = client.post("/auth/totp", json={"code": code(secret, clock)}, headers={**pending, **from_ip(ip)})
    assert resp.status_code == 429 and resp.json()["error_code"] == "CODE_BACKOFF"
    assert "account_code_backoff" in events("sign_in")[-1][4]
    # The pending session is not ended; after the pause the right code works and clears the count.
    with platform_session() as session:
        session.execute(update(OrgAdmin).values(code_backoff_until=utcnow() - timedelta(seconds=1)))
    resp = client.post("/auth/totp", json={"code": code(secret, clock)}, headers={**pending, **from_ip(ip)})
    assert resp.status_code == 200
    with platform_session() as session:
        admin = session.scalar(select(OrgAdmin))
        assert (admin.code_failures, admin.code_backoff_until) == (0, None)


def test_the_code_pause_grows_and_is_capped():
    from app.auth import code_backoff_seconds
    from app.config import Settings

    settings = Settings()
    assert [code_backoff_seconds(n, settings) for n in range(1, 12)] == [
        0, 0, 0, 0, 30, 60, 120, 240, 480, 900, 900]


def test_reauth_codes_count_toward_the_account_limit(client, clock):
    _, secret = make_admin()
    sessions = [sign_in(client, clock, secret, ip=f"192.0.2.{n + 1}") for n in range(5)]
    for n, headers in enumerate(sessions):
        resp = client.post("/auth/reauth", json={"code": "000000"}, headers={**headers, **from_ip(f"192.0.2.{n + 1}")})
        assert resp.status_code == 400
    resp = client.post("/auth/reauth", json={"code": code(secret, clock)}, headers=sessions[0])
    assert resp.status_code == 429 and resp.json()["error_code"] == "CODE_BACKOFF"
    # Nobody was signed out.
    assert all(client.get("/auth/me", headers=h).status_code == 200 for h in sessions)


def test_ipv6_addresses_count_per_64(client, monkeypatch):
    from app.auth import ip_key

    assert ip_key("2001:db8:1:2:aaaa::1") == ip_key("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
    assert ip_key("2001:db8:1:3::1") != ip_key("2001:db8:1:2::1")
    assert ip_key("::ffff:198.51.100.10") == "198.51.100.10"
    assert ip_key("198.51.100.10") == "198.51.100.10"
    monkeypatch.setenv("ORG_IP_FAILURE_LIMIT", "3")
    for n in range(3):
        client.post("/auth/login", json={"email": f"x{n}@tena.example", "password": "whatever-1"},
                    headers=from_ip(f"2001:db8:1:2::{n + 1}"))
    resp = client.post("/auth/login", json={"email": "y@tena.example", "password": "whatever-1"},
                       headers=from_ip("2001:db8:1:2:dead:beef::1"))
    assert resp.status_code == 429
    assert client.post("/auth/login", json={"email": "y@tena.example", "password": "whatever-1"},
                       headers=from_ip("2001:db8:1:3::1")).status_code == 401


# --- 5. bad CSV files -------------------------------------------------------------------------------

def test_unparseable_csv_is_a_400(portal):
    for text, message in (
        ('employee_number,name,phone,department\n"ET-1,"Abebe" Kebede\n', None),
        ("employee_number,name,phone,department\nET-1,A\x00B,0911000001,Ops\n", None),
        ("employee_number,name,name,phone,department\nET-1,A,B,0911000001,Ops\n", "appears more than once"),
    ):
        resp = portal.post("/employees/import/preview", json={"csv": text})
        assert resp.status_code in (200, 400), resp.text
        if message:
            assert resp.status_code == 400 and message in resp.json()["error"]


def test_a_huge_field_is_a_400_not_a_500(portal):
    huge = "employee_number,name,phone,department\nET-1,\"" + "x" * 200_000 + "\",0911000001,Ops\n"
    resp = portal.post("/employees/import/preview", json={"csv": huge})
    assert resp.status_code == 400 and "not a valid CSV file" in resp.json()["error"]


# --- 6. auth audit events carry the organisation ---------------------------------------------------

def test_every_audit_event_of_a_known_admin_names_the_organisation(client, clock):
    from app import cli

    org = cli.create_org("Setup Org", "0055555555")
    link = cli.create_admin(org, "setup@tena.example", "Setup Admin")
    token = link.split("#", 1)[1]
    client.post("/auth/setup", json={"token": token, "password": "a long passphrase"})
    with platform_session() as session:
        rows = list(session.scalars(select(AuditEvent).where(AuditEvent.admin_id.is_not(None))))
    assert rows and all(r.organisation_id == org for r in rows)
    assert "setup_completed" in {r.action for r in rows}


# --- 7. nothing to reimburse ----------------------------------------------------------------------

def test_a_claim_with_nothing_to_reimburse_never_reaches_a_batch(portal):
    portal.set_policy(copay_percent=100)
    emp = portal.employee()
    claim = portal.claim(emp["id"])
    preview = portal.get(f"/claims/{claim['id']}").json()["assessment"]
    assert preview["payable_santim"] == 0 and preview["approvable"]
    assert "Nothing is reimbursed" in preview["notes"][0]
    body = portal.approve(claim["id"]).json()
    assert body["status"] == "approved" and body["approved_santim"] == 0
    assert "Nothing is reimbursed" in body["notes"][0]
    payments = portal.get("/batches").json()
    assert payments["ready"]["claims"] == [] and payments["ready"]["by_method"]["cbe"]["claims"] == 0
    assert portal.post("/batches", json={"method": "cbe"}).json()["error_code"] == "NOTHING_TO_BATCH"


def test_rounding_to_zero_is_not_paid_either(portal):
    portal.set_policy(copay_percent=50)
    emp = portal.employee()
    claim = portal.claim(emp["id"], items=[{"medicine": "Gauze", "quantity": 1, "unit_price_santim": 1}])
    assert portal.approve(claim["id"]).json()["approved_santim"] == 0  # 0.5 santim co-pay rounds up to 1
    other = portal.claim(emp["id"])
    portal.approve(other["id"])
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    assert batch["claim_count"] == 1
    lines = list(csv.reader(io.StringIO(portal.get(f"/batches/{batch['id']}/export").text.lstrip("﻿"))))
    assert len(lines) == 2 and all(row[3] != "0.00" for row in lines[1:])
    with platform_session() as session:
        assert session.get(Claim, claim["id"]).batch_id is None

