"""The audit log: what is written for each change, with organisation, admin,
address, target and result; secrets never."""

import json

from conftest import CLIENT_IP, PASSWORD, events, make_admin, sign_in
from sqlalchemy import select

from app.db import platform_session
from app.models import AuditEvent


def test_a_claims_life_is_audited(portal):
    portal.set_policy(copay_percent=10)  # policy_updated (after a reauth)
    emp = portal.employee(name="Dawit Bekele")
    claim = portal.claim(emp["id"])
    portal.reauth()
    assert portal.approve(claim["id"]).status_code == 200
    assert portal.approve(claim["id"]).status_code == 409  # a refusal is audited too
    other = portal.claim(emp["id"])
    portal.post(f"/claims/{other['id']}/reject", json={"reason": "Missing stamp."})
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    portal.get(f"/batches/{batch['id']}/export")
    portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": "FT123"})
    portal.get(f"/receipts/{claim['receipt_file_id']}")
    portal.get("/reports/export?kind=month")
    portal.get("/employees/export")

    logged = [(a, r) for a, r, *_ in events() if a not in ("sign_in", "sign_in_password", "reauth",
                                                          "organisation_created")]
    assert logged == [
        ("policy_updated", "success"), ("employee_created", "success"), ("employee_payout_changed", "success"),
        ("receipt_uploaded", "success"),
        ("claim_created", "success"), ("claim_approved", "success"), ("claim_approved", "failure"),
        ("receipt_uploaded", "success"), ("claim_created", "success"), ("claim_rejected", "success"),
        ("batch_created", "success"), ("batch_exported", "success"), ("batch_paid", "success"),
        ("receipt_viewed", "success"), ("report_exported", "success"), ("employees_exported", "success"),
    ]
    with platform_session() as session:
        rows = list(session.scalars(select(AuditEvent).where(AuditEvent.admin_email == portal.email)))
    assert all(r.organisation_id == portal.org_id and r.ip == CLIENT_IP and r.admin_id == portal.admin_id
               for r in rows)
    approve = next(r for r in rows if r.action == "claim_approved" and r.result == "success")
    assert (approve.target_type, approve.target_id, approve.target_name) == ("claim", claim["id"], "CLM-000001")
    assert json.loads(approve.detail) == {"total_santim": 100_000, "copay_santim": 10_000,
                                          "approved_santim": 90_000, "capped": False}
    refused = next(r for r in rows if r.action == "claim_approved" and r.result == "failure")
    assert json.loads(refused.detail)["reason"] == "NOT_PENDING"
    policy = next(r for r in rows if r.action == "policy_updated")
    assert json.loads(policy.detail)["before"]["copay_percent"] == 0
    assert json.loads(policy.detail)["after"]["copay_percent"] == 10
    paid = next(r for r in rows if r.action == "batch_paid")
    assert json.loads(paid.detail)["reference"] == "FT123"


def test_refused_approvals_name_the_rule(portal):
    portal.set_policy(annual_limit_santim=0)
    claim = portal.claim(portal.employee()["id"])
    portal.reauth()
    portal.approve(claim["id"])
    failure = [e for e in events("claim_approved") if e[1] == "failure"][-1]
    assert json.loads(failure[4]) == {"reason": "LIMIT_REACHED", "problems": ["LIMIT_REACHED"]}


def test_employee_changes_are_audited(portal):
    emp = portal.employee()
    portal.patch(f"/employees/{emp['id']}", json={"department": "Finance"})
    portal.patch(f"/employees/{emp['id']}", json={"department": "Finance"})  # no change, no entry
    portal.post(f"/employees/{emp['id']}/deactivate")
    portal.post(f"/employees/{emp['id']}/activate")
    detail = portal.post(f"/employees/{emp['id']}/dependants", json={"name": "Abel", "relationship": "child"}).json()
    portal.post(f"/employees/{emp['id']}/dependants/{detail['dependants'][0]['id']}/remove")
    portal.post("/employees/import/commit", json={"csv": "employee_number,name,phone,department\nX-1,Abebe Kebede,"
                                                         "0911000099,Ops\n"})
    actions = [a for a, *_ in events() if a.startswith(("employee", "dependant"))]
    assert actions == ["employee_created", "employee_payout_changed", "employee_updated", "employee_deactivated", "employee_activated",
                       "dependant_added", "dependant_removed", "employees_imported"]
    updated = events("employee_updated")[0]
    assert json.loads(updated[4]) == {"fields": ["department"]}


def test_passwords_codes_and_tokens_are_never_logged(client, clock):
    _, secret = make_admin()
    client.post("/auth/login", json={"email": "hr@tena.example", "password": "Wrong-password-1"})
    sign_in(client, clock, secret)
    dump = repr(events())
    assert PASSWORD not in dump and "Wrong-password-1" not in dump and secret not in dump
