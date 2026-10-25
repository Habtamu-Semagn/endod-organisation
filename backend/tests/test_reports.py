"""Reports: spend by month, department and medicine, the overview, and CSV exports."""

import csv
import io
from datetime import date


def approve(portal, claim_id):
    resp = portal.approve(claim_id)
    if resp.status_code == 403:
        portal.reauth()
        resp = portal.approve(claim_id)
    assert resp.status_code == 200, resp.text


def rows(text):
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


def seed(portal):
    eng = portal.employee(department="Engineering")
    ops = portal.employee(department="Operations")
    a = portal.claim(eng["id"], receipt_date=date(2026, 3, 10), items=[
        {"medicine": "Metformin 500mg", "quantity": 2, "unit_price_santim": 10_000},
        {"medicine": "Insulin", "quantity": 1, "unit_price_santim": 50_000}])
    b = portal.claim(ops["id"], receipt_date=date(2026, 3, 20), items=[
        {"medicine": "metformin  500MG", "quantity": 1, "unit_price_santim": 10_000}])
    c = portal.claim(ops["id"], receipt_date=date(2026, 9, 1), items=[
        {"medicine": "Amoxicillin", "quantity": 3, "unit_price_santim": 5_000}])
    portal.claim(eng["id"])  # pending: not spend
    for claim in (a, b, c):
        approve(portal, claim["id"])
    rejected = portal.claim(eng["id"])
    portal.post(f"/claims/{rejected['id']}/reject", json={"reason": "Not covered."})


def test_spend_by_month_department_and_medicine(portal):
    seed(portal)
    data = portal.get("/reports").json()
    assert data["period"] == {"from": "2026-01-01", "to": "2026-12-31"}
    assert data["totals"] == {"claims": 3, "approved_santim": 95_000, "total_santim": 95_000, "employees": 2,
                              "average_claim_santim": 31_666}
    months = {m["month"]: m for m in data["by_month"]}
    assert len(months) == 12
    assert months["2026-03"] == {"month": "2026-03", "claims": 2, "approved_santim": 80_000, "total_santim": 80_000}
    assert months["2026-09"]["approved_santim"] == 15_000 and months["2026-10"]["claims"] == 0
    assert data["by_department"] == [
        {"department": "Engineering", "claims": 1, "approved_santim": 70_000, "total_santim": 70_000, "employees": 1},
        {"department": "Operations", "claims": 2, "approved_santim": 25_000, "total_santim": 25_000, "employees": 1},
    ]
    # Medicines are grouped whatever their case and spacing.
    assert [(m["medicine"], m["quantity"], m["total_santim"], m["claims"]) for m in data["by_medicine"]] == [
        ("Insulin", 1, 50_000, 1), ("Metformin 500mg", 3, 30_000, 2), ("Amoxicillin", 3, 15_000, 1)]


def test_a_chosen_period(portal):
    seed(portal)
    data = portal.get("/reports?from=2026-03-15&to=2026-09-30").json()
    assert data["totals"]["claims"] == 2 and [m["month"] for m in data["by_month"]] == [
        "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert portal.get("/reports?from=2026-05-01&to=2026-04-01").status_code == 400
    assert portal.get("/reports?from=2020-01-01&to=2026-04-01").status_code == 400


def test_csv_exports(portal):
    seed(portal)
    month = portal.get("/reports/export?kind=month")
    assert month.status_code == 200 and month.headers["content-type"].startswith("text/csv")
    assert month.headers["content-disposition"] == 'attachment; filename="spend-by-month-2026-01-01-2026-12-31.csv"'
    table = rows(month.text)
    assert table[0] == ["month", "claims", "approved_etb", "receipts_total_etb"]
    assert ["2026-03", "2", "800.00", "800.00"] in table
    assert rows(portal.get("/reports/export?kind=department").text)[1] == [
        "Engineering", "1", "1", "700.00", "700.00"]
    assert rows(portal.get("/reports/export?kind=medicine").text)[1] == ["Insulin", "1", "1", "500.00"]
    assert len(rows(portal.get("/reports/export?kind=employee").text)) == 3
    assert portal.get("/reports/export?kind=passwords").status_code == 400


def test_report_exports_are_formula_safe(portal):
    emp = portal.employee(department="=cmd|' /C calc'!A0")
    claim = portal.claim(emp["id"], items=[{"medicine": "@SUM(1+1)", "quantity": 1, "unit_price_santim": 100}])
    approve(portal, claim["id"])
    assert rows(portal.get("/reports/export?kind=department").text)[1][0] == "'=cmd|' /C calc'!A0"
    assert rows(portal.get("/reports/export?kind=medicine").text)[1][0] == "'@SUM(1+1)"


def test_overview(portal):
    seed(portal)
    data = portal.get("/overview").json()
    assert data["spend_santim"] == 95_000 and data["reimbursed_santim"] == 0
    assert data["claims_submitted"] == 5 and data["pending_claims"] == 1
    assert data["by_status"]["approved"]["claims"] == 3 and data["by_status"]["rejected"]["claims"] == 1
    assert data["employees"] == {"active": 2, "linked_endod": 0, "claimants": 2}
    assert data["policy_year"] == {"start": "2026-01-01", "end": "2026-12-31"}


def test_a_medicine_is_shown_by_its_most_common_spelling():
    from app.api.reports import label

    # Most common wins.
    assert label({"aspirin": [1, (1, "a")], "Aspirin": [2, (2, "b")]}) == "Aspirin"
    # A tie goes to the spelling used first: earliest claim, then lowest item id.
    assert label({"ASPIRIN": [1, (3, "a")], "Aspirin": [1, (2, "z")]}) == "Aspirin"
    assert label({"ASPIRIN": [1, (2, "a")], "Aspirin": [1, (2, "b")]}) == "ASPIRIN"


def test_the_medicine_label_does_not_depend_on_the_database_order(portal):
    emp = portal.employee()
    for spelling in ("ibuprofen 400MG", "Ibuprofen 400mg", "Ibuprofen 400mg", "IBUPROFEN 400MG"):
        claim = portal.claim(emp["id"], items=[{"medicine": spelling, "quantity": 1, "unit_price_santim": 100}])
        approve(portal, claim["id"])
    rows = portal.get("/reports").json()["by_medicine"]
    assert [(r["medicine"], r["quantity"], r["claims"]) for r in rows] == [("Ibuprofen 400mg", 4, 4)]
