"""Shared by the portal routers: today's date, error helpers and the JSON
shapes of employees, claims and batches. Amounts are integers in santim."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi.responses import Response
from sqlalchemy import select

from app import validation
from app.db import iso
from app.errors import ApiError
from app.models import Claim, ClaimItem, Dependant, Employee, PaymentBatch, PayoutMethod
from app.policy import batch_code, claim_code

ADDIS_ABABA = ZoneInfo("Africa/Addis_Ababa")


def _today() -> date:
    return datetime.now(ADDIS_ABABA).date()


def today() -> date:
    """The date in Addis Ababa (tests replace ``_today``)."""
    return _today()


def bad(message: str, code: str = "VALIDATION_ERROR") -> ApiError:
    return ApiError(400, message, code)


def checked(fn, *args, **kwargs):
    """Run a app.validation check; its message becomes a 400."""
    try:
        return fn(*args, **kwargs)
    except validation.Invalid as exc:
        raise bad(str(exc)) from exc


def like(q: str) -> str:
    """A LIKE pattern for a search box: the user's %, _ and \\ match nothing special."""
    return "%" + re.sub(r"[\\%_]", "", q.strip().lower()) + "%"


def csv_response(text: str, filename: str) -> Response:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:80] or "export.csv"
    return Response(content=text.encode("utf-8"), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{safe}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
    })


def dependant_payload(d: Dependant) -> Dict[str, Any]:
    return {"id": d.id, "name": d.name, "relationship": d.relationship,
            "birth_date": d.birth_date.isoformat() if d.birth_date else None, "active": d.active}


def employee_payload(e: Employee, **extra: Any) -> Dict[str, Any]:
    return {
        "id": e.id, "employee_number": e.employee_number, "name": e.name, "phone": e.phone,
        "department": e.department, "endod_id": e.endod_id, "active": e.active,
        "payout_method": e.payout_method, "payout_account": e.payout_account,
        "created_at": iso(e.created_at), "deactivated_at": iso(e.deactivated_at), **extra,
    }


def claim_payload(c: Claim, employee: Optional[Employee] = None, dependant: Optional[Dependant] = None,
                  items: Optional[list] = None, batch: Optional[PaymentBatch] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": c.id, "code": claim_code(c.number), "number": c.number, "status": c.status, "source": c.source,
        "employee_id": c.employee_id, "dependant_id": c.dependant_id,
        "pharmacy_name": c.pharmacy_name, "pharmacy_tin": c.pharmacy_tin, "receipt_number": c.receipt_number,
        "receipt_date": c.receipt_date.isoformat(), "total_santim": c.total_santim,
        "copay_santim": c.copay_santim, "approved_santim": c.approved_santim,
        "rejection_reason": c.rejection_reason, "has_receipt": c.receipt_file_id is not None,
        "receipt_file_id": c.receipt_file_id, "created_at": iso(c.created_at),
        "reviewer_name": c.reviewer_name, "reviewed_at": iso(c.reviewed_at),
        "batch_id": c.batch_id, "paid_at": iso(c.paid_at),
    }
    if employee is not None:
        data["employee"] = {"id": employee.id, "name": employee.name, "employee_number": employee.employee_number,
                            "department": employee.department, "endod_id": employee.endod_id,
                            "active": employee.active, "payout_method": employee.payout_method}
    if dependant is not None:
        data["dependant"] = dependant_payload(dependant)
    if items is not None:
        data["items"] = [{"medicine": i.medicine, "quantity": i.quantity, "unit_price_santim": i.unit_price_santim,
                          "line_total_santim": i.line_total_santim} for i in items]
    if batch is not None:
        data["batch"] = {"id": batch.id, "code": batch_code(batch.number), "status": batch.status,
                         "reference": batch.reference}
    return data


def claim_items(session, claim_id: str):
    return session.scalars(select(ClaimItem).where(ClaimItem.claim_id == claim_id).order_by(ClaimItem.position)).all()


def batch_payload(b: PaymentBatch) -> Dict[str, Any]:
    return {
        "id": b.id, "code": batch_code(b.number), "number": b.number, "method": b.method,
        "method_label": PayoutMethod.LABELS.get(b.method, b.method), "status": b.status,
        "total_santim": b.total_santim, "claim_count": b.claim_count, "created_at": iso(b.created_at),
        "paid_at": iso(b.paid_at), "reference": b.reference,
    }
