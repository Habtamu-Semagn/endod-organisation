"""Synthetic sample data for test connections.

A test connection checks a system's integration without touching (or
seeing) the organisation's real data: every read answers these made-up
employees, claims and batches instead, in exactly the live shapes. Their ids
are fixed (``0000...``) so a system can read one, then fetch it again.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.api.employees import mask
from app.models import PayoutMethod
from app.policy import batch_code, claim_code

CREATED = "2026-01-05T06:00:00+00:00"


def _id(n: int) -> str:
    return f"{n:032x}"


_EMPLOYEES: List[Dict[str, Any]] = [
    {"id": _id(1), "employee_number": "SAMPLE-0001", "name": "Sample Employee One", "phone": "+251911000001",
     "department": "Sample Department", "endod_id": None, "active": True, "payout_method": "cbe",
     "payout_account": "1000000000001",
     "dependants": [{"id": _id(101), "name": "Sample Child", "relationship": "child", "birth_date": "2018-01-01"}],
     "created_at": CREATED, "updated_at": CREATED, "deactivated_at": None},
    {"id": _id(2), "employee_number": "SAMPLE-0002", "name": "Sample Employee Two", "phone": "+251911000002",
     "department": "Sample Department", "endod_id": None, "active": True, "payout_method": "telebirr",
     "payout_account": "+251911000002", "dependants": [], "created_at": CREATED, "updated_at": CREATED,
     "deactivated_at": None},
    {"id": _id(3), "employee_number": "SAMPLE-0003", "name": "Sample Employee Three", "phone": "+251911000003",
     "department": "Sample Department", "endod_id": None, "active": False, "payout_method": None,
     "payout_account": None, "dependants": [], "created_at": CREATED, "updated_at": CREATED,
     "deactivated_at": CREATED},
]


def _claim(n: int, employee: Dict[str, Any], status: str, total: int, approved: Optional[int],
           batch: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": _id(200 + n), "code": claim_code(n), "status": status, "source": "manual",
        "employee_id": employee["id"], "employee_number": employee["employee_number"], "dependant_id": None,
        "pharmacy_name": "Sample Pharmacy", "pharmacy_tin": "0000000000", "receipt_number": f"SAMPLE-{n:03d}",
        "receipt_date": "2026-01-10", "total_santim": total,
        "copay_santim": None if approved is None else total - approved, "approved_santim": approved,
        "rejection_reason": "A sample rejection." if status == "rejected" else None, "has_receipt": True,
        "created_at": CREATED, "reviewed_at": None if status == "pending" else CREATED, "batch_id": batch,
        "paid_at": CREATED if status == "paid" else None,
        "items": [{"medicine": "Sample Medicine 500mg", "quantity": 1, "unit_price_santim": total,
                   "line_total_santim": total}],
    }


_CLAIMS = [
    _claim(1, _EMPLOYEES[0], "pending", 50_000, None),
    _claim(2, _EMPLOYEES[0], "approved", 80_000, 72_000),
    _claim(3, _EMPLOYEES[1], "rejected", 30_000, None),
    _claim(4, _EMPLOYEES[1], "paid", 60_000, 54_000, batch=_id(301)),
]
_BATCHES = [{
    "id": _id(301), "code": batch_code(1), "status": "paid", "method": "telebirr",
    "method_label": PayoutMethod.LABELS["telebirr"], "claim_count": 1, "total_santim": 54_000,
    "created_at": CREATED, "exported_at": CREATED, "paid_at": CREATED, "reference": "SAMPLE-REF-0001",
}]


def _page(items: List[Dict[str, Any]], limit: int, offset: int) -> Dict[str, Any]:
    rows = items[offset:offset + limit]
    return {"items": rows, "total": len(items), "limit": limit, "offset": offset,
            "has_more": offset + len(rows) < len(items), "sample": True}


def _employee(e: Dict[str, Any], full_payout: bool) -> Dict[str, Any]:
    return {**e, "payout_account": e["payout_account"] if full_payout else mask(e["payout_account"])}


def employees(status: str, limit: int, offset: int, full_payout: bool) -> Dict[str, Any]:
    rows = [e for e in _EMPLOYEES if status == "all" or e["active"] == (status == "active")]
    return _page([_employee(e, full_payout) for e in rows], limit, offset)


def employee(number: str, full_payout: bool) -> Optional[Dict[str, Any]]:
    found = next((e for e in _EMPLOYEES if e["employee_number"] == number), None)
    return {**_employee(found, full_payout), "sample": True} if found else None


def claims(status: Optional[str], employee_number: Optional[str], limit: int, offset: int) -> Dict[str, Any]:
    rows = [{k: v for k, v in c.items() if k != "items"} for c in _CLAIMS
            if (not status or c["status"] == status)
            and (not employee_number or c["employee_number"] == employee_number)]
    return _page(sorted(rows, key=lambda c: c["code"], reverse=True), limit, offset)


def claim(claim_id: str) -> Optional[Dict[str, Any]]:
    found = next((c for c in _CLAIMS if c["id"] == claim_id), None)
    return {**found, "sample": True} if found else None


def batches(status: Optional[str], limit: int, offset: int) -> Dict[str, Any]:
    return _page([b for b in _BATCHES if not status or b["status"] == status], limit, offset)


def batch(batch_id: str) -> Optional[Dict[str, Any]]:
    found = next((b for b in _BATCHES if b["id"] == batch_id), None)
    if found is None:
        return None
    rows = [c for c in _CLAIMS if c["batch_id"] == batch_id]
    return {**found, "sample": True,
            "claims": [{"claim_id": c["id"], "code": c["code"], "employee_id": c["employee_id"],
                        "employee_number": c["employee_number"], "approved_santim": c["approved_santim"],
                        "status": c["status"]} for c in rows]}
