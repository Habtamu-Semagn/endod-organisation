"""Claims: entry, the approval rules (cover, policy year, limit, exclusions,
duplicate receipts) and rejection with a reason."""

from datetime import date

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db import platform_session
from app.models import AdminSession, Claim, ClaimItem, ClaimStatus


def approved(portal, claim_id):
    resp = portal.approve(claim_id)
    if resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED":
        portal.reauth()
        resp = portal.approve(claim_id)
    return resp


def one_item(santim, medicine="Metformin 500mg", quantity=1):
    return [{"medicine": medicine, "quantity": quantity, "unit_price_santim": santim}]


# --- entry -----------------------------------------------------------------------------------

def test_a_claim_is_entered_pending_with_its_total_computed(portal):
    emp = portal.employee(name="Dawit Bekele")
    claim = portal.claim(emp["id"], items=[
        {"medicine": "Insulin Glargine", "quantity": 2, "unit_price_santim": 185_050},
        {"medicine": "Test strips", "quantity": 3, "unit_price_santim": 12_999}])
    assert claim["status"] == "pending" and claim["code"] == "CLM-000001"
    assert claim["total_santim"] == 2 * 185_050 + 3 * 12_999
    assert [i["line_total_santim"] for i in claim["items"]] == [370_100, 38_997]
    assert claim["employee"]["name"] == "Dawit Bekele" and claim["has_receipt"]
    assessment = claim["assessment"]
    assert assessment["approvable"] and assessment["payable_santim"] == claim["total_santim"]
    assert portal.claim(emp["id"])["code"] == "CLM-000002"


def test_claim_numbers_are_per_organisation(portal, other_portal):
    portal.claim(portal.employee()["id"])
    assert other_portal.claim(other_portal.employee()["id"])["code"] == "CLM-000001"


@pytest.mark.parametrize("change, status", [
    ({"items": [{"medicine": "X ray", "quantity": 1, "unit_price_santim": 12.5}]}, 422),  # no floats
    ({"items": [{"medicine": "Aspirin", "quantity": 1, "unit_price_santim": "1250"}]}, 422),
    ({"items": [{"medicine": "Aspirin", "quantity": 0, "unit_price_santim": 100}]}, 422),
    ({"items": [{"medicine": "Aspirin", "quantity": 1, "unit_price_santim": -100}]}, 422),
    ({"items": [{"medicine": "Aspirin", "quantity": 1.0, "unit_price_santim": 100}]}, 422),
    ({"items": []}, 422),
    ({"pharmacy_tin": "12345"}, 400),
    ({"receipt_number": "no spaces? ok but !"}, 400),
    ({"receipt_date": "2026-10-21"}, 400),  # tomorrow
    ({"pharmacy_name": "x"}, 400),
])
def test_bad_claims_are_refused(portal, change, status):
    emp = portal.employee()
    body = {**portal.claim_body(emp["id"]), **change}
    resp = portal.post("/claims", json=body)
    assert resp.status_code == status, resp.text
    with platform_session() as session:
        assert session.scalar(select(Claim.id)) is None


def test_a_receipt_file_is_required_and_used_once(portal):
    emp = portal.employee()
    body = portal.claim_body(emp["id"])
    empty = portal.post("/claims", json={**body, "receipt_file_id": ""})
    assert empty.status_code == 400 and empty.json()["error_code"] == "RECEIPT_REQUIRED"
    assert portal.post("/claims", json={**body, "receipt_file_id": "a1" * 16}).status_code == 404
    body.pop("receipt_file_id")
    assert portal.post("/claims", json=body).status_code == 422
    first = portal.claim_body(emp["id"])
    assert portal.post("/claims", json=first).status_code == 201
    again = portal.claim_body(emp["id"])
    again["receipt_file_id"] = first["receipt_file_id"]
    resp = portal.post("/claims", json=again)
    assert resp.status_code == 409 and resp.json()["error_code"] == "RECEIPT_IN_USE"


# --- approval -------------------------------------------------------------------------------------

def test_approval_needs_a_fresh_code_and_pays_the_share(portal):
    portal.set_policy(copay_percent=10)
    claim = portal.claim(portal.employee()["id"], items=one_item(100_000))
    with platform_session() as session:
        session.execute(update(AdminSession).values(reauth_at=None))
    resp = portal.approve(claim["id"])
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"
    resp = approved(portal, claim["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert (body["copay_santim"], body["approved_santim"]) == (10_000, 90_000)
    assert body["reviewer_name"] == "Selam Tesfaye" and body["reviewed_at"]


def test_copay_rounds_to_the_santim(portal):
    portal.set_policy(copay_percent=15)
    claim = portal.claim(portal.employee()["id"], items=one_item(333))  # 15% = 49.95 -> 50
    body = approved(portal, claim["id"]).json()
    assert (body["copay_santim"], body["approved_santim"]) == (50, 283)


def test_the_share_is_capped_at_the_remaining_limit(portal):
    portal.set_policy(annual_limit_santim=100_000)  # ETB 1,000.00
    emp = portal.employee()
    first = portal.claim(emp["id"], items=one_item(60_000))
    assert approved(portal, first["id"]).json()["approved_santim"] == 60_000
    second = portal.claim(emp["id"], items=one_item(60_000))
    preview = portal.get(f"/claims/{second['id']}").json()["assessment"]
    assert (preview["used_santim"], preview["remaining_santim"], preview["payable_santim"], preview["capped"]) == (
        60_000, 40_000, 40_000, True)
    resp = approved(portal, second["id"])
    assert resp.status_code == 200
    assert resp.json()["approved_santim"] == 40_000
    assert "capped at the remaining annual limit" in resp.json()["notes"][0]
    assert "ETB 400.00 is paid back" in resp.json()["notes"][0]
    third = portal.claim(emp["id"], items=one_item(1))
    resp = approved(portal, third["id"])
    assert resp.status_code == 409 and resp.json()["error_code"] == "LIMIT_REACHED"
    assert "annual limit of ETB 1,000.00 is used up" in resp.json()["error"]
    assert portal.get(f"/claims/{third['id']}").json()["status"] == "pending"


def test_a_claim_exactly_at_the_limit_is_paid_in_full(portal):
    portal.set_policy(annual_limit_santim=100_000)
    emp = portal.employee()
    claim = portal.claim(emp["id"], items=one_item(100_000))
    body = approved(portal, claim["id"]).json()
    assert body["approved_santim"] == 100_000 and "notes" in body and body["notes"] == []
    nxt = portal.claim(emp["id"], items=one_item(100))
    assert approved(portal, nxt["id"]).json()["error_code"] == "LIMIT_REACHED"


def test_one_santim_over_the_limit_is_capped(portal):
    portal.set_policy(annual_limit_santim=100_000)
    claim = portal.claim(portal.employee()["id"], items=one_item(100_001))
    assert approved(portal, claim["id"]).json()["approved_santim"] == 100_000


def test_a_zero_limit_pays_nothing(portal):
    portal.set_policy(annual_limit_santim=0)
    claim = portal.claim(portal.employee()["id"], items=one_item(500))
    assert approved(portal, claim["id"]).json()["error_code"] == "LIMIT_REACHED"


def test_the_limit_is_per_employee_and_counts_dependants(portal):
    portal.set_policy(annual_limit_santim=100_000)
    one, two = portal.employee(), portal.employee()
    child = portal.post(f"/employees/{one['id']}/dependants", json={"name": "Robel", "relationship": "child"}
                        ).json()["dependants"][0]
    approved(portal, portal.claim(one["id"], items=one_item(70_000))["id"])
    for_child = portal.claim(one["id"], dependant_id=child["id"], items=one_item(70_000))
    assert approved(portal, for_child["id"]).json()["approved_santim"] == 30_000
    assert approved(portal, portal.claim(two["id"], items=one_item(70_000))["id"]).json()["approved_santim"] == 70_000


def test_co_pay_comes_off_before_the_limit(portal):
    portal.set_policy(annual_limit_santim=100_000, copay_percent=20)
    claim = portal.claim(portal.employee()["id"], items=one_item(150_000))  # share 120,000 -> capped 100,000
    body = approved(portal, claim["id"]).json()
    assert (body["copay_santim"], body["approved_santim"]) == (30_000, 100_000)


def test_only_this_policy_years_claims_count(portal):
    portal.set_policy(annual_limit_santim=100_000)
    emp = portal.employee()
    old = portal.claim(emp["id"], items=one_item(100_000), receipt_date=date(2026, 1, 5))
    approved(portal, old["id"])
    # Moved into last year (as if approved then): it no longer counts.
    with platform_session() as session:
        session.execute(update(Claim).where(Claim.id == old["id"]).values(receipt_date=date(2025, 12, 20)))
    claim = portal.claim(emp["id"], items=one_item(100_000))
    assert approved(portal, claim["id"]).json()["approved_santim"] == 100_000


def test_the_receipt_date_must_be_in_the_current_policy_year(portal):
    portal.set_policy(year_start_month=7, year_start_day=8)  # Ethiopian fiscal year: 8 July 2026 - 7 July 2027
    emp = portal.employee()
    inside = portal.claim(emp["id"], receipt_date=date(2026, 7, 8))
    outside = portal.claim(emp["id"], receipt_date=date(2026, 7, 7))
    assert approved(portal, inside["id"]).status_code == 200
    resp = approved(portal, outside["id"])
    assert resp.status_code == 409 and resp.json()["error_code"] == "OUTSIDE_POLICY_YEAR"
    assert "2026-07-08 to 2027-07-07" in resp.json()["error"]


def test_the_policy_year_handles_the_29th_of_february():
    from app.policy import check_year_start, policy_year

    assert policy_year(date(2026, 10, 20), 1, 1) == (date(2026, 1, 1), date(2026, 12, 31))
    assert policy_year(date(2026, 3, 1), 7, 8) == (date(2025, 7, 8), date(2026, 7, 7))
    assert policy_year(date(2028, 2, 29), 2, 29) == (date(2028, 2, 29), date(2029, 2, 27))
    with pytest.raises(ValueError):
        check_year_start(2, 30)


def test_excluded_medicines_are_refused(portal):
    portal.set_policy(excluded_medicines=["Sildenafil", "  cosmetic  cream "])
    emp = portal.employee()
    bad = portal.claim(emp["id"], items=[*one_item(1000), *one_item(2000, "SILDENAFIL 50mg tablets")])
    assessment = portal.get(f"/claims/{bad['id']}").json()["assessment"]
    assert [p["code"] for p in assessment["problems"]] == ["EXCLUDED_MEDICINE"]
    resp = approved(portal, bad["id"])
    assert resp.status_code == 409 and "SILDENAFIL 50mg tablets is excluded" in resp.json()["error"]
    # Whole words only.
    fine = portal.claim(emp["id"], items=one_item(1000, "Sildenafilx"))
    assert approved(portal, fine["id"]).status_code == 200
    cream = portal.claim(emp["id"], items=one_item(1000, "Cosmetic Cream 30g"))
    assert approved(portal, cream["id"]).json()["error_code"] == "EXCLUDED_MEDICINE"


def test_duplicate_receipts_are_refused(portal):
    emp = portal.employee()
    first = portal.claim(emp["id"], receipt_number="fs 0042", tin="0012345678")
    assert first["receipt_number"] == "FS0042"
    again = portal.post("/claims", json=portal.claim_body(emp["id"], receipt_number="FS0042", tin="001-234-5678"))
    assert again.status_code == 409 and again.json()["error_code"] == "DUPLICATE_RECEIPT"
    assert "already claimed on CLM-000001" in again.json()["error"]
    # Another pharmacy may use the same receipt number.
    assert portal.post("/claims", json=portal.claim_body(emp["id"], receipt_number="FS0042", tin="0099999999")
                       ).status_code == 201
    # Once the first is rejected, the receipt may be entered again (e.g. a clearer photo)...
    portal.reauth()
    assert portal.post(f"/claims/{first['id']}/reject", json={"reason": "Photo unreadable."}).status_code == 200
    second = portal.claim(emp["id"], receipt_number="FS0042", tin="0012345678")
    assert approved(portal, second["id"]).status_code == 200
    # ...but never paid back twice.
    third = portal.post("/claims", json=portal.claim_body(emp["id"], receipt_number="FS0042", tin="0012345678"))
    assert third.status_code == 409


def test_a_duplicate_slipped_in_is_refused_at_approval_and_by_the_database(portal):
    emp = portal.employee()
    first = portal.claim(emp["id"], receipt_number="R-1")
    other = portal.claim(emp["id"], receipt_number="R-2")
    approved(portal, first["id"])
    # As if two entries raced: the second has the same receipt.
    with platform_session() as session:
        session.execute(update(Claim).where(Claim.id == other["id"]).values(receipt_number="R-1"))
    resp = approved(portal, other["id"])
    assert resp.status_code == 409 and resp.json()["error_code"] == "DUPLICATE_RECEIPT"
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.execute(update(Claim).where(Claim.id == other["id"]).values(status="approved", approved_santim=1))


def test_inactive_employees_and_dependants_are_not_covered(portal):
    emp = portal.employee()
    detail = portal.post(f"/employees/{emp['id']}/dependants", json={"name": "Hana", "relationship": "spouse"}).json()
    spouse = detail["dependants"][0]
    for_spouse = portal.claim(emp["id"], dependant_id=spouse["id"])
    portal.post(f"/employees/{emp['id']}/dependants/{spouse['id']}/remove")
    assert approved(portal, for_spouse["id"]).json()["error_code"] == "DEPENDANT_INACTIVE"

    claim = portal.claim(emp["id"])
    portal.post(f"/employees/{emp['id']}/deactivate")
    resp = approved(portal, claim["id"])
    assert resp.status_code == 409 and resp.json()["error_code"] == "EMPLOYEE_INACTIVE"


def test_dependants_must_be_covered_by_the_policy(portal):
    portal.set_policy(dependants_covered=False)
    emp = portal.employee()
    child = portal.post(f"/employees/{emp['id']}/dependants", json={"name": "Robel", "relationship": "child"}
                        ).json()["dependants"][0]
    claim = portal.claim(emp["id"], dependant_id=child["id"])
    assert approved(portal, claim["id"]).json()["error_code"] == "DEPENDANT_NOT_COVERED"
    # The employee's own claims are fine.
    assert approved(portal, portal.claim(emp["id"])["id"]).status_code == 200


def test_a_dependant_must_be_the_employees(portal):
    one, two = portal.employee(), portal.employee()
    child = portal.post(f"/employees/{two['id']}/dependants", json={"name": "Robel", "relationship": "child"}
                        ).json()["dependants"][0]
    resp = portal.post("/claims", json=portal.claim_body(one["id"], dependant_id=child["id"]))
    assert resp.status_code == 400


def test_an_employee_override_replaces_the_limit(portal):
    portal.set_policy(annual_limit_santim=1_000_000)
    emp = portal.employee()
    rules = {"annual_limit_santim": 20_000, "copay_percent": 0, "dependants_covered": True, "excluded_medicines": []}
    resp = portal.put(f"/employees/{emp['id']}/policy", json=rules)
    if resp.status_code == 403:
        portal.reauth()
        resp = portal.put(f"/employees/{emp['id']}/policy", json=rules)
    assert resp.status_code == 200 and resp.json()["policy"]["annual_limit_santim"] == 20_000
    claim = portal.claim(emp["id"], items=one_item(50_000))
    assert approved(portal, claim["id"]).json()["approved_santim"] == 20_000
    assert portal.delete(f"/employees/{emp['id']}/policy").json()["policy"]["annual_limit_santim"] == 1_000_000


def test_reject_needs_a_reason_and_is_final(portal):
    claim = portal.claim(portal.employee()["id"])
    portal.reauth()
    assert portal.post(f"/claims/{claim['id']}/reject", json={"reason": "  "}).status_code == 400
    resp = portal.post(f"/claims/{claim['id']}/reject", json={"reason": "Missing pharmacy stamp."})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected" and resp.json()["rejection_reason"] == "Missing pharmacy stamp."
    again = portal.post(f"/claims/{claim['id']}/reject", json={"reason": "Again."})
    assert again.status_code == 409 and again.json()["error_code"] == "NOT_PENDING"
    assert approved(portal, claim["id"]).json()["error_code"] == "NOT_PENDING"


def test_an_approved_claim_cannot_be_rejected_or_approved_again(portal):
    claim = portal.claim(portal.employee()["id"])
    approved(portal, claim["id"])
    assert approved(portal, claim["id"]).status_code == 409
    resp = portal.post(f"/claims/{claim['id']}/reject", json={"reason": "Changed my mind."})
    assert resp.status_code == 409


def test_reject_needs_a_fresh_code(portal):
    claim = portal.claim(portal.employee()["id"])
    portal.forget_reauth()
    resp = portal.post(f"/claims/{claim['id']}/reject", json={"reason": "No stamp."})
    assert resp.status_code == 403 and resp.json()["error_code"] == "REAUTH_REQUIRED"


def test_the_list_filters_and_counts(portal):
    eng = portal.employee(name="Abel Engineer", department="Engineering")
    ops = portal.employee(name="Meron Ops", department="Operations")
    a = portal.claim(eng["id"], pharmacy="Kenema Pharmacy Bole")
    portal.claim(ops["id"], pharmacy="Lion Pharmacy")
    approved(portal, a["id"])
    listed = portal.get("/claims").json()
    assert listed["total"] == 2 and listed["counts"] == {"pending": 1, "approved": 1, "rejected": 0, "paid": 0,
                                                         "all": 2}
    assert listed["pending_total_santim"] == 100_000
    assert listed["pharmacies"] == ["Kenema Pharmacy Bole", "Lion Pharmacy"]
    assert [c["code"] for c in portal.get("/claims?status=pending").json()["items"]] == ["CLM-000002"]
    assert portal.get("/claims?department=Operations").json()["total"] == 1
    assert portal.get("/claims?pharmacy=Lion%20Pharmacy").json()["total"] == 1
    assert portal.get("/claims?q=abel").json()["items"][0]["employee"]["name"] == "Abel Engineer"
    assert portal.get("/claims?q=CLM-000002").json()["items"][0]["code"] == "CLM-000002"
    assert portal.get("/claims?q=%25").json()["total"] == 2
    assert portal.get("/claims?from=2026-10-16").json()["total"] == 0
    assert portal.get("/claims?status=nope").status_code == 400
    assert portal.get("/claims").json()["items"][0]["medicines"] == ["Metformin 500mg"]


def test_line_totals_are_checked_by_the_database(portal):
    claim = portal.claim(portal.employee()["id"])
    with pytest.raises(IntegrityError):
        with platform_session() as session:
            session.execute(update(ClaimItem).where(ClaimItem.claim_id == claim["id"]).values(line_total_santim=1))
    with platform_session() as session:
        assert session.scalar(select(Claim.status).where(Claim.id == claim["id"])) == ClaimStatus.PENDING
