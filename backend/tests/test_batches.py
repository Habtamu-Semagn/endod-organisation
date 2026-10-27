"""Payout batches: only approved claims, one method per batch, the exported
file, mark paid with a reference (fresh code), and a paid batch never changes."""

import csv
import io

import pytest
from sqlalchemy import update

from app.db import platform_session
from app.models import AdminSession


def approve(portal, claim_id):
    resp = portal.approve(claim_id)
    if resp.status_code == 403:
        portal.reauth()
        resp = portal.approve(claim_id)
    assert resp.status_code == 200, resp.text
    return resp.json()


def approved_claim(portal, employee, santim=100_000):
    claim = portal.claim(employee["id"], items=[{"medicine": "Amoxicillin", "quantity": 1,
                                                 "unit_price_santim": santim}])
    return approve(portal, claim["id"])


def rows(text):
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


@pytest.fixture
def ready(portal):
    """Two CBE employees and one Telebirr employee, each with an approved claim, plus a pending one."""
    cbe1 = portal.employee(name="Bethlehem Haile", payout_method="cbe", payout_account="1000123456789")
    cbe2 = portal.employee(name="Dawit Bekele", payout_method="cbe", payout_account="1000987654321")
    tele = portal.employee(name="Rahel Assefa", payout_method="telebirr", payout_account="0912345678")
    claims = {"cbe1": approved_claim(portal, cbe1, 120_050), "cbe2": approved_claim(portal, cbe2, 80_000),
              "tele": approved_claim(portal, tele, 82_000)}
    claims["pending"] = portal.claim(cbe1["id"])
    return {"cbe1": cbe1, "cbe2": cbe2, "tele": tele, "claims": claims}


def test_the_payments_screen_shows_what_is_ready(portal, ready):
    data = portal.get("/batches").json()
    assert data["ready"]["by_method"]["cbe"] == {"claims": 2, "total_santim": 200_050}
    assert data["ready"]["by_method"]["telebirr"] == {"claims": 1, "total_santim": 82_000}
    assert data["ready"]["total_santim"] == 282_050
    assert data["enabled_methods"] == ["cbe", "awash", "dashen", "telebirr"]
    assert data["items"] == []


def test_a_batch_takes_the_approved_claims_of_one_method(portal, ready):
    resp = portal.post("/batches", json={"method": "cbe"})
    assert resp.status_code == 201, resp.text
    batch = resp.json()
    assert (batch["code"], batch["status"], batch["claim_count"], batch["total_santim"]) == (
        "BATCH-0001", "open", 2, 200_050)
    assert {c["id"] for c in batch["claims"]} == {ready["claims"]["cbe1"]["id"], ready["claims"]["cbe2"]["id"]}
    assert all(c["status"] == "approved" and c["batch_id"] == batch["id"] for c in batch["claims"])
    # Nothing left for CBE; the Telebirr claim is still ready.
    again = portal.post("/batches", json={"method": "cbe"})
    assert again.status_code == 409 and again.json()["error_code"] == "NOTHING_TO_BATCH"
    assert portal.get("/batches").json()["ready"]["by_method"]["telebirr"]["claims"] == 1


def test_only_approved_unbatched_claims_of_that_method_can_be_chosen(portal, ready):
    c = ready["claims"]
    for wrong in ([c["pending"]["id"]], [c["tele"]["id"]], ["a1" * 16], []):
        resp = portal.post("/batches", json={"method": "cbe", "claim_ids": wrong})
        assert resp.status_code == 409 and resp.json()["error_code"] == "NOT_BATCHABLE", wrong
    resp = portal.post("/batches", json={"method": "cbe", "claim_ids": [c["cbe1"]["id"]]})
    assert resp.status_code == 201 and resp.json()["claim_count"] == 1
    resp = portal.post("/batches", json={"method": "cbe", "claim_ids": [c["cbe1"]["id"]]})
    assert resp.status_code == 409  # already in a batch


def test_employees_without_payout_details_are_held_back(portal):
    emp = portal.employee(payout_method=None, payout_account=None)
    approved_claim(portal, emp)
    data = portal.get("/batches").json()
    assert data["ready"]["missing_payout_details"] == {"claims": 1, "total_santim": 100_000}
    assert data["ready"]["claims"][0]["payout_ready"] is False
    for method in ("cbe", "telebirr"):
        assert portal.post("/batches", json={"method": method}).status_code == 409


def test_bank_export(portal, ready):
    portal.reauth()
    assert portal.put("/organisation/payout", json={"debit_account": "1000-555-444-333", "methods": ["cbe", "telebirr"]}
                      ).status_code == 200
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    resp = portal.get(f"/batches/{batch['id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="BATCH-0001-cbe.csv"'
    assert resp.headers["x-content-type-options"] == "nosniff"
    table = rows(resp.text)
    assert table[0] == ["debit_account", "beneficiary_account", "beneficiary_name", "amount_etb", "reference",
                        "narration"]
    assert table[1:] == [
        ["1000555444333", "1000123456789", "Bethlehem Haile", "1200.50", "BATCH-0001/CLM-000001",
         "Medication reimbursement CLM-000001"],
        ["1000555444333", "1000987654321", "Dawit Bekele", "800.00", "BATCH-0001/CLM-000002",
         "Medication reimbursement CLM-000002"],
    ]


def test_telebirr_export(portal, ready):
    batch = portal.post("/batches", json={"method": "telebirr"}).json()
    table = rows(portal.get(f"/batches/{batch['id']}/export").text)
    assert table[0] == ["msisdn", "beneficiary_name", "amount_etb", "reference", "remark"]
    assert table[1][:3] == ["251912345678", "Rahel Assefa", "820.00"]


def test_the_export_is_safe_to_open_in_a_spreadsheet(portal):
    emp = portal.employee(name='=HYPERLINK("http://evil.example","Click")', payout_method="cbe",
                          payout_account="1000123456789")
    approved_claim(portal, emp)
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    table = rows(portal.get(f"/batches/{batch['id']}/export").text)
    assert table[1][2] == '\'=HYPERLINK("http://evil.example","Click")'


def test_the_batch_keeps_the_account_it_was_made_with(portal, ready):
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    portal.patch(f"/employees/{ready['cbe1']['id']}", json={"payout_account": "2000111122223"})
    table = rows(portal.get(f"/batches/{batch['id']}/export").text)
    assert table[1][1] == "1000123456789"


def test_mark_paid_needs_a_fresh_code_and_a_reference(portal, ready):
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    with platform_session() as session:
        session.execute(update(AdminSession).values(reauth_at=None))
    resp = portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": "FT26293ABCDE"})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    portal.reauth()
    assert portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": " "}).status_code == 400
    resp = portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": "FT26293ABCDE"})
    assert resp.status_code == 200, resp.text
    paid = resp.json()
    assert paid["status"] == "paid" and paid["reference"] == "FT26293ABCDE" and paid["paid_at"]
    assert {c["status"] for c in paid["claims"]} == {"paid"}
    claim = portal.get(f"/claims/{ready['claims']['cbe1']['id']}").json()
    assert claim["status"] == "paid" and claim["batch"]["reference"] == "FT26293ABCDE"
    overview = portal.get("/overview").json()
    assert overview["reimbursed_santim"] == 200_050 and overview["awaiting_payout_santim"] == 82_000


def test_a_paid_batch_never_changes(portal, ready):
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    portal.reauth()
    portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": "FT-1"})
    again = portal.post(f"/batches/{batch['id']}/mark-paid", json={"reference": "FT-2"})
    assert again.status_code == 409 and again.json()["error_code"] == "BATCH_PAID"
    cancel = portal.post(f"/batches/{batch['id']}/cancel")
    assert cancel.status_code == 409 and cancel.json()["error"] == "This batch is paid and can no longer change."
    detail = portal.get(f"/batches/{batch['id']}").json()
    assert detail["reference"] == "FT-1" and detail["claim_count"] == 2 and detail["total_santim"] == 200_050
    # Its claims cannot be batched, approved or rejected again.
    claim_id = ready["claims"]["cbe1"]["id"]
    assert portal.post("/batches", json={"method": "cbe", "claim_ids": [claim_id]}).status_code == 409
    assert portal.approve(claim_id).status_code == 409
    assert portal.post(f"/claims/{claim_id}/reject", json={"reason": "Too late"}).status_code == 409


def test_an_open_batch_can_be_cancelled(portal, ready):
    batch = portal.post("/batches", json={"method": "cbe"}).json()
    assert portal.post(f"/batches/{batch['id']}/cancel").json() == {"ok": True}
    assert portal.get(f"/batches/{batch['id']}").status_code == 404
    claim = portal.get(f"/claims/{ready['claims']['cbe1']['id']}").json()
    assert claim["status"] == "approved" and claim["batch_id"] is None
    assert portal.post("/batches", json={"method": "cbe"}).json()["code"] == "BATCH-0002"


def test_only_enabled_methods(portal, ready):
    portal.reauth()
    assert portal.put("/organisation/payout", json={"methods": ["telebirr"]}).json()["payout"]["methods"] == [
        "telebirr"]
    resp = portal.post("/batches", json={"method": "cbe"})
    assert resp.status_code == 400
    assert portal.put("/organisation/payout", json={"methods": ["paypal"]}).status_code == 400
    assert portal.put("/organisation/payout", json={"methods": ["cbe"], "debit_account": "12"}).status_code == 400


def test_payout_settings_need_a_fresh_code(portal):
    resp = portal.put("/organisation/payout", json={"methods": ["cbe"]})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
