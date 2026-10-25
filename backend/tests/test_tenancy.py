"""Tenant isolation: an admin of organisation A never sees or changes
organisation B's data. Every route with an id answers A's admin 404 for B's
ids, exactly as for an id that does not exist; lists, reports and exports
never include B's rows; and nothing of B's can be referenced from A's claims
or batches."""

import re

import pytest
from conftest import events
from sqlalchemy import select

from app.db import session_scope
from app.models import AuditEvent, BatchStatus, Claim, Employee, PaymentBatch

NOT_FOUND = {"error": "Not found.", "error_code": "NOT_FOUND"}


def _approve(portal, claim_id):
    resp = portal.approve(claim_id)
    if resp.status_code == 403:
        portal.reauth()
        resp = portal.approve(claim_id)
    assert resp.status_code == 200, resp.text


@pytest.fixture
def two_orgs(portal, other_portal):
    """Organisation B (other_portal) with one of everything; organisation A (portal) with its own."""
    b = other_portal
    emp = b.employee(name="Secret Bekele", department="B-Only Department", endod_id="DE999999")
    dependant = b.post(f"/employees/{emp['id']}/dependants", json={"name": "B Child", "relationship": "child"}
                       ).json()["dependants"][0]
    claim = b.claim(emp["id"], items=[{"medicine": "B-Only-Medicine", "quantity": 1, "unit_price_santim": 777_700}])
    _approve(b, claim["id"])
    batch = b.post("/batches", json={"method": "cbe"}).json()
    pending = b.claim(emp["id"], receipt_number="B-PENDING")
    receipt = b.receipt()
    ids = {"employee_id": emp["id"], "dependant_id": dependant["id"], "claim_id": claim["id"],
           "pending_claim_id": pending["id"], "batch_id": batch["id"], "receipt_id": receipt,
           "claim_receipt_id": claim["receipt_file_id"]}
    a_emp = portal.employee(name="Own Employee")
    return {"a": portal, "b": b, "ids": ids, "a_employee": a_emp}


def _routes_with_ids():
    from app.main import create_app

    found = []
    for template, operations in create_app().openapi()["paths"].items():
        if "{" in template:
            for method in operations:
                found.append((method.upper(), template))
    return found


#: Every route that takes an id, and the B id to try for each parameter.
PARAMS = {"employee_id": "employee_id", "dependant_id": "dependant_id", "claim_id": "claim_id",
          "batch_id": "batch_id", "receipt_id": "receipt_id"}
BODIES = {
    ("PATCH", "/employees/{employee_id}"): {"name": "Hijacked"},
    ("POST", "/employees/{employee_id}/dependants"): {"name": "Intruder", "relationship": "child"},
    ("PUT", "/employees/{employee_id}/policy"): {"annual_limit_santim": 1, "copay_percent": 0,
                                               "dependants_covered": True, "excluded_medicines": []},
    ("POST", "/claims/{claim_id}/reject"): {"reason": "Not yours."},
    ("POST", "/batches/{batch_id}/mark-paid"): {"reference": "STOLEN-1"},
}


def test_the_route_list_is_covered():
    params = {p for _, t in _routes_with_ids() for p in re.findall(r"\{([a-z_]+)\}", t)}
    assert params == set(PARAMS), params
    assert len(_routes_with_ids()) >= 16


@pytest.mark.parametrize("method, template", _routes_with_ids())
def test_every_route_with_an_id_answers_404_for_another_organisations_id(two_orgs, method, template):
    a, ids = two_orgs["a"], two_orgs["ids"]
    a.reauth()  # so routes that need a fresh code get as far as the lookup
    path = template
    for param in re.findall(r"\{([a-z_]+)\}", template):
        value = ids[PARAMS[param]]
        if param == "claim_id" and method == "POST":
            value = ids["pending_claim_id"]  # a claim that could still be approved or rejected
        path = path.replace("{" + param + "}", value)
    resp = a.client.request(method, path, headers=a.headers, json=BODIES.get((method, template), {}))
    assert resp.status_code == 404, (method, path, resp.text)
    assert resp.json() == NOT_FOUND
    # The same answer as for an id that does not exist at all.
    unknown = re.sub(r"[0-9a-f]{32}", "a1" * 16, path)
    resp2 = a.client.request(method, unknown, headers=a.headers, json=BODIES.get((method, template), {}))
    assert (resp2.status_code, resp2.json()) == (404, NOT_FOUND)


def test_a_dependant_route_with_own_employee_and_foreign_dependant(two_orgs):
    a, ids = two_orgs["a"], two_orgs["ids"]
    resp = a.post(f"/employees/{two_orgs['a_employee']['id']}/dependants/{ids['dependant_id']}/remove")
    assert (resp.status_code, resp.json()) == (404, NOT_FOUND)


def test_nothing_of_b_was_changed(two_orgs):
    b, ids = two_orgs["b"], two_orgs["ids"]
    a = two_orgs["a"]
    a.reauth()
    a.patch(f"/employees/{ids['employee_id']}", json={"name": "Hijacked"})
    a.post(f"/claims/{ids['pending_claim_id']}/approve")
    a.post(f"/claims/{ids['pending_claim_id']}/reject", json={"reason": "Not yours."})
    a.post(f"/batches/{ids['batch_id']}/mark-paid", json={"reference": "STOLEN-1"})
    a.post(f"/batches/{ids['batch_id']}/cancel")
    a.post(f"/employees/{ids['employee_id']}/deactivate")
    with session_scope() as session:
        assert session.get(Employee, ids["employee_id"]).name == "Secret Bekele"
        assert session.get(Employee, ids["employee_id"]).active is True
        assert session.get(Claim, ids["pending_claim_id"]).status == "pending"
        assert session.get(PaymentBatch, ids["batch_id"]).status == BatchStatus.OPEN
    assert b.get(f"/batches/{ids['batch_id']}").json()["reference"] is None


def test_lists_reports_and_exports_never_include_another_organisation(two_orgs):
    a, b = two_orgs["a"], two_orgs["b"]
    own_claim = a.claim(two_orgs["a_employee"]["id"])
    _approve(a, own_claim["id"])

    employees = a.get("/employees?status=all").json()
    assert [e["name"] for e in employees["items"]] == ["Own Employee"]
    assert "B-Only Department" not in employees["departments"]
    assert a.get("/employees?q=Secret").json()["total"] == 0

    claims = a.get("/claims").json()
    assert [c["id"] for c in claims["items"]] == [own_claim["id"]]
    assert claims["counts"]["all"] == 1
    assert a.get(f"/claims?employee_id={two_orgs['ids']['employee_id']}").json()["total"] == 0

    batches = a.get("/batches").json()
    assert batches["items"] == [] and batches["open_total_santim"] == 0

    report = a.get("/reports").json()
    assert report["totals"]["claims"] == 1
    assert all(r["medicine"] != "B-Only-Medicine" for r in report["by_medicine"])
    assert all(r["department"] != "B-Only Department" for r in report["by_department"])

    overview = a.get("/overview").json()
    assert overview["claims_submitted"] == 1 and overview["employees"]["linked_endod"] == 0

    for path in ("/employees/export", "/reports/export?kind=medicine", "/reports/export?kind=department",
                 "/reports/export?kind=employee", "/reports/export?kind=month"):
        text = a.get(path).text
        assert "Secret" not in text and "B-Only" not in text and "7777.00" not in text, path

    # B's own view is unaffected.
    assert b.get("/claims").json()["counts"]["all"] == 2


def test_a_claim_cannot_reference_another_organisations_rows(two_orgs):
    a, ids = two_orgs["a"], two_orgs["ids"]
    own = two_orgs["a_employee"]["id"]
    for field, value in (("employee_id", ids["employee_id"]), ("dependant_id", ids["dependant_id"]),
                         ("receipt_file_id", ids["receipt_id"])):
        body = a.claim_body(own)
        body[field] = value
        resp = a.post("/claims", json=body)
        assert (resp.status_code, resp.json()) == (404, NOT_FOUND), field


def test_a_batch_cannot_take_another_organisations_claims(two_orgs):
    a, b, ids = two_orgs["a"], two_orgs["b"], two_orgs["ids"]
    other = b.claim(b.employee()["id"])
    _approve(b, other["id"])
    resp = a.post("/batches", json={"method": "cbe", "claim_ids": [other["id"]]})
    assert resp.status_code == 409 and resp.json()["error_code"] == "NOT_BATCHABLE"
    with session_scope() as session:
        assert session.get(Claim, other["id"]).batch_id is None


def test_duplicate_receipt_detection_does_not_leak_across_organisations(two_orgs):
    """B's receipt numbers are B's business: A may enter the same TIN and number."""
    a = two_orgs["a"]
    resp = a.post("/claims", json=a.claim_body(two_orgs["a_employee"]["id"], receipt_number="B-PENDING"))
    assert resp.status_code == 201


def test_receipt_files_of_another_organisation_are_not_served(two_orgs):
    a, ids = two_orgs["a"], two_orgs["ids"]
    for receipt in (ids["receipt_id"], ids["claim_receipt_id"]):
        assert a.get(f"/receipts/{receipt}").status_code == 404
    assert not any(e[0] == "receipt_viewed" and e[1] == "success" and e[2] == a.email for e in events())


def test_audit_entries_carry_the_organisation(two_orgs):
    a, b = two_orgs["a"], two_orgs["b"]
    with session_scope() as session:
        rows = list(session.scalars(select(AuditEvent)))
    by_admin = {}
    for row in rows:
        if row.admin_email in (a.email, b.email):
            by_admin.setdefault(row.admin_email, set()).add(row.organisation_id)
    assert by_admin[a.email] == {a.org_id} and by_admin[b.email] == {b.org_id}
