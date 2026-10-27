"""`/reports`: medication spend by month, department and medicine, for a
period (the current policy year unless given), and their CSV exports.

Spend is what the organisation approved (approved and paid claims, by
receipt date); the receipts' totals are shown beside it. Only the signed-in
admin's organisation is ever counted.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app import audit, csvutil, money
from app.api.common import bad, csv_response, today
from app.auth import Principal, current_admin
from app.db import tenant_session
from app.models import Claim, ClaimItem, ClaimStatus, Employee
from app.policy import default_policy, normalise_medicine, policy_year

router = APIRouter(tags=["reports"])

KINDS = ("month", "department", "medicine", "employee")
MAX_DAYS = 3 * 366


def _period(session, org: str, date_from: Optional[date], date_to: Optional[date]) -> Tuple[date, date]:
    if date_from is None or date_to is None:
        base = default_policy(session, org)
        start, end = policy_year(today(), base.year_start_month, base.year_start_day)
        date_from, date_to = date_from or start, date_to or end
    if date_to < date_from:
        raise bad("The end of the period is before its start.")
    if (date_to - date_from).days > MAX_DAYS:
        raise bad("A report covers at most three years.")
    return date_from, date_to


def label(spellings: Dict[str, list]) -> str:
    """The name shown for a group of spellings of one medicine, the same on
    every database: the most common spelling; on a tie, the one used first
    (the earliest claim, then the lowest item id)."""
    return min(spellings.items(), key=lambda kv: (-kv[1][0], kv[1][1]))[0]


def build(session, org: str, start: date, end: date) -> Dict[str, Any]:
    rows = session.execute(
        select(Claim, Employee).join(Employee, Employee.id == Claim.employee_id)
        .where(Claim.organisation_id == org, Employee.organisation_id == org,
               Claim.status.in_((ClaimStatus.APPROVED, ClaimStatus.PAID)),
               Claim.receipt_date >= start, Claim.receipt_date <= end)
        .order_by(Claim.receipt_date)).all()
    claim_ids = [c.id for c, _ in rows]
    # Each item with its claim's number (claims are numbered in the order they were entered).
    items = session.execute(
        select(ClaimItem, Claim.number).join(Claim, Claim.id == ClaimItem.claim_id)
        .where(ClaimItem.claim_id.in_(claim_ids))
        .order_by(Claim.number, ClaimItem.id)).all() if claim_ids else []

    months: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        months[cursor.strftime("%Y-%m")] = {"claims": 0, "approved_santim": 0, "total_santim": 0}
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    departments: Dict[str, Dict[str, Any]] = {}
    employees: Dict[str, Dict[str, Any]] = {}
    for claim, employee in rows:
        approved = claim.approved_santim or 0
        bucket = months[claim.receipt_date.strftime("%Y-%m")]
        bucket["claims"] += 1
        bucket["approved_santim"] += approved
        bucket["total_santim"] += claim.total_santim
        dept = departments.setdefault(employee.department, {"claims": 0, "approved_santim": 0, "total_santim": 0,
                                                            "employees": set()})
        dept["claims"] += 1
        dept["approved_santim"] += approved
        dept["total_santim"] += claim.total_santim
        dept["employees"].add(employee.id)
        person = employees.setdefault(employee.id, {"employee_number": employee.employee_number,
                                                    "name": employee.name, "department": employee.department,
                                                    "claims": 0, "approved_santim": 0})
        person["claims"] += 1
        person["approved_santim"] += approved
    medicines: Dict[str, Dict[str, Any]] = {}
    for item, claim_number in items:
        key = normalise_medicine(item.medicine)
        entry = medicines.setdefault(key, {"quantity": 0, "total_santim": 0, "claims": set(), "spellings": {}})
        entry["quantity"] += item.quantity
        entry["total_santim"] += item.line_total_santim
        entry["claims"].add(item.claim_id)
        # Per spelling: how often it was used, and where it was first used.
        seen = entry["spellings"].setdefault(item.medicine, [0, (claim_number, item.id)])
        seen[0] += 1
        seen[1] = min(seen[1], (claim_number, item.id))
    for entry in medicines.values():
        entry["medicine"] = label(entry.pop("spellings"))

    approved_total = sum(c.approved_santim or 0 for c, _ in rows)
    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "totals": {"claims": len(rows), "approved_santim": approved_total,
                   "total_santim": sum(c.total_santim for c, _ in rows),
                   "employees": len(employees),
                   "average_claim_santim": approved_total // len(rows) if rows else 0},
        "by_month": [{"month": m, **v} for m, v in months.items()],
        "by_department": sorted(
            ({"department": d, "claims": v["claims"], "approved_santim": v["approved_santim"],
              "total_santim": v["total_santim"], "employees": len(v["employees"])} for d, v in departments.items()),
            key=lambda r: (-r["approved_santim"], r["department"])),
        "by_medicine": sorted(
            ({"medicine": v["medicine"], "quantity": v["quantity"], "total_santim": v["total_santim"],
              "claims": len(v["claims"])} for v in medicines.values()),
            key=lambda r: (-r["total_santim"], r["medicine"].casefold()))[:200],
        "by_employee": sorted(employees.values(), key=lambda r: (-r["approved_santim"], r["name"]))[:200],
    }


@router.get("/reports")
def report(date_from: Optional[date] = Query(default=None, alias="from"),
           date_to: Optional[date] = Query(default=None, alias="to"),
           principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        start, end = _period(session, principal.organisation_id, date_from, date_to)
        return build(session, principal.organisation_id, start, end)


def _csv(kind: str, data: Dict[str, Any]) -> str:
    etb = money.plain_etb
    if kind == "month":
        return csvutil.to_csv(("month", "claims", "approved_etb", "receipts_total_etb"),
                              [(r["month"], r["claims"], etb(r["approved_santim"]), etb(r["total_santim"]))
                               for r in data["by_month"]])
    if kind == "department":
        return csvutil.to_csv(("department", "employees", "claims", "approved_etb", "receipts_total_etb"),
                              [(r["department"], r["employees"], r["claims"], etb(r["approved_santim"]),
                                etb(r["total_santim"])) for r in data["by_department"]])
    if kind == "medicine":
        return csvutil.to_csv(("medicine", "quantity", "claims", "receipts_total_etb"),
                              [(r["medicine"], r["quantity"], r["claims"], etb(r["total_santim"]))
                               for r in data["by_medicine"]])
    return csvutil.to_csv(("employee_number", "name", "department", "claims", "approved_etb"),
                          [(r["employee_number"], r["name"], r["department"], r["claims"], etb(r["approved_santim"]))
                           for r in data["by_employee"]])


@router.get("/reports/export")
def export(kind: str = Query(max_length=16),
           date_from: Optional[date] = Query(default=None, alias="from"),
           date_to: Optional[date] = Query(default=None, alias="to"),
           principal: Principal = Depends(current_admin)):
    if kind not in KINDS:
        raise bad(f"kind must be one of {', '.join(KINDS)}.")
    with tenant_session(principal.organisation_id) as session:
        start, end = _period(session, principal.organisation_id, date_from, date_to)
        text = _csv(kind, build(session, principal.organisation_id, start, end))
        audit.by(session, principal, audit.REPORT_EXPORTED, target_type="report", target_id=kind,
                 detail={"from": start.isoformat(), "to": end.isoformat()})
    return csv_response(text, f"spend-by-{kind}-{start.isoformat()}-{end.isoformat()}.csv")

