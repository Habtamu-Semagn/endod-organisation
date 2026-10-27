"""`/claims`: medication claims entered by HR from a receipt, reviewed
(approve or reject, each with a fresh TOTP) against the benefit policy.

Approving pays back the organisation's share (the total minus the employee's
co-pay), capped at what is left of the employee's annual limit. Rules that
block approval are in app.policy; refusals are audited like approvals.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app import audit, money, validation
from app.api.common import bad, checked, claim_items, claim_payload, like, today
from app.auth import Principal, current_admin, fresh_admin
from app.claims_intake import MAX_ITEMS, MAX_QUANTITY, NewClaim, NewItem, create_claim
from app.db import tenant_session, utcnow
from app.errors import ApiError
from app.models import AuditResult, Claim, ClaimItem, ClaimStatus, Dependant, Employee, PaymentBatch
from app.policy import assess, claim_code
from app.tenancy import owned

router = APIRouter(tags=["claims"])

MAX_PAGE_SIZE = 100


class ItemIn(BaseModel):
    medicine: str = Field(max_length=200)
    quantity: StrictInt = Field(ge=1, le=MAX_QUANTITY)
    #: Santim (an integer): ETB 12.50 is 1250.
    unit_price_santim: StrictInt = Field(ge=1, le=money.MAX_SANTIM)


class ClaimIn(BaseModel):
    employee_id: str = Field(max_length=32)
    dependant_id: Optional[str] = Field(default=None, max_length=32)
    pharmacy_name: str = Field(max_length=200)
    pharmacy_tin: str = Field(max_length=20)
    receipt_number: str = Field(max_length=60)
    receipt_date: date
    items: List[ItemIn] = Field(min_length=1, max_length=MAX_ITEMS)
    receipt_file_id: str = Field(max_length=32)


class RejectIn(BaseModel):
    reason: str = Field(max_length=1000)


def _load(session, claim: Claim) -> Dict[str, Any]:
    org = claim.organisation_id
    employee = session.scalar(select(Employee).where(Employee.id == claim.employee_id, Employee.organisation_id == org))
    dependant = session.scalar(select(Dependant).where(Dependant.id == claim.dependant_id,
                                                       Dependant.organisation_id == org)) if claim.dependant_id else None
    batch = session.scalar(select(PaymentBatch).where(PaymentBatch.id == claim.batch_id,
                                                      PaymentBatch.organisation_id == org)) if claim.batch_id else None
    data = claim_payload(claim, employee, dependant, claim_items(session, claim.id), batch)
    if claim.status == ClaimStatus.PENDING:
        data["assessment"] = assess(session, claim, today()).payload()
    return data


@router.get("/claims")
def list_claims(
    status: Optional[str] = Query(default=None, max_length=16),
    q: Optional[str] = Query(default=None, max_length=100),
    department: Optional[str] = Query(default=None, max_length=80),
    pharmacy: Optional[str] = Query(default=None, max_length=160),
    employee_id: Optional[str] = Query(default=None, max_length=32),
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
    principal: Principal = Depends(current_admin),
) -> Dict[str, Any]:
    org = principal.organisation_id
    if status is not None and status not in ClaimStatus.ALL:
        raise bad(f"status must be one of {', '.join(ClaimStatus.ALL)}.")
    base = [Claim.organisation_id == org]
    if department:
        base.append(Employee.department == department)
    if pharmacy:
        base.append(Claim.pharmacy_name == pharmacy)
    if employee_id:
        base.append(Claim.employee_id == employee_id)
    if date_from:
        base.append(Claim.receipt_date >= date_from)
    if date_to:
        base.append(Claim.receipt_date <= date_to)
    if q and q.strip():
        pattern = like(q)
        digits = "".join(ch for ch in q if ch.isdigit())
        conditions = [func.lower(Employee.name).like(pattern), func.lower(Employee.employee_number).like(pattern),
                      func.lower(Claim.pharmacy_name).like(pattern), func.lower(Claim.receipt_number).like(pattern)]
        if digits and len(digits) <= 9:
            conditions.append(Claim.number == int(digits))
        base.append(or_(*conditions))
    filtered = base + ([Claim.status == status] if status else [])
    joined = select(Claim).join(Employee, Employee.id == Claim.employee_id)
    with tenant_session(principal.organisation_id) as session:
        total = session.scalar(select(func.count()).select_from(Claim).join(Employee, Employee.id == Claim.employee_id)
                               .where(*filtered)) or 0
        claims = session.scalars(joined.where(*filtered).order_by(Claim.created_at.desc(), Claim.number.desc())
                                 .offset((page - 1) * page_size).limit(page_size)).all()
        counts = dict(session.execute(select(Claim.status, func.count()).select_from(Claim)
                                      .join(Employee, Employee.id == Claim.employee_id)
                                      .where(*base).group_by(Claim.status)).all())
        pending_total = session.scalar(select(func.coalesce(func.sum(Claim.total_santim), 0)).where(
            Claim.organisation_id == org, Claim.status == ClaimStatus.PENDING)) or 0
        employees = {e.id: e for e in session.scalars(select(Employee).where(
            Employee.organisation_id == org, Employee.id.in_({c.employee_id for c in claims})))}
        first_items: Dict[str, List[str]] = {}
        for item in session.scalars(select(ClaimItem).where(ClaimItem.claim_id.in_([c.id for c in claims]))
                                    .order_by(ClaimItem.position)):
            first_items.setdefault(item.claim_id, []).append(item.medicine)
        pharmacies = sorted(set(session.scalars(select(Claim.pharmacy_name).where(Claim.organisation_id == org))))
        departments = sorted(set(session.scalars(select(Employee.department).where(Employee.organisation_id == org))))
        return {
            "items": [{**claim_payload(c, employees.get(c.employee_id)), "medicines": first_items.get(c.id, [])}
                      for c in claims],
            "total": total, "page": page, "page_size": page_size,
            "counts": {s: counts.get(s, 0) for s in ClaimStatus.ALL} | {"all": sum(counts.values())},
            "pending_total_santim": int(pending_total), "pharmacies": pharmacies, "departments": departments,
        }


@router.post("/claims", status_code=201)
def create(body: ClaimIn, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    pharmacy_name = checked(validation.text, body.pharmacy_name, "Pharmacy name", min_len=2, max_len=160)
    pharmacy_tin = checked(validation.tin, body.pharmacy_tin, "Pharmacy TIN")
    receipt_number = checked(validation.receipt_number, body.receipt_number)
    items = [NewItem(medicine=checked(validation.text, i.medicine, "Medicine", min_len=2, max_len=160),
                     quantity=i.quantity, unit_price_santim=i.unit_price_santim) for i in body.items]
    new = NewClaim(organisation_id=principal.organisation_id, employee_id=body.employee_id,
                   dependant_id=body.dependant_id or None, pharmacy_name=pharmacy_name, pharmacy_tin=pharmacy_tin,
                   receipt_number=receipt_number, receipt_date=body.receipt_date, items=items,
                   receipt_file_id=body.receipt_file_id, created_by=principal.admin_id)
    try:
        with tenant_session(principal.organisation_id) as session:
            claim = create_claim(session, new, today())
            audit.by(session, principal, audit.CLAIM_CREATED, target_type="claim", target_id=claim.id,
                     target_name=claim_code(claim.number),
                     detail={"employee_id": claim.employee_id, "total_santim": claim.total_santim,
                             "pharmacy_tin": claim.pharmacy_tin, "receipt_number": claim.receipt_number})
            return _load(session, claim)
    except IntegrityError as exc:
        raise ApiError(409, "This claim conflicts with another one saved at the same time; try again.",
                       "CONFLICT") from exc


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        return _load(session, owned(session, Claim, claim_id, principal.organisation_id))


def _refuse(session, principal: Principal, action: str, claim: Claim, message: str, code: str,
            status: int = 409, **detail: Any) -> ApiError:
    audit.by(session, principal, action, AuditResult.FAILURE, target_type="claim", target_id=claim.id,
             target_name=claim_code(claim.number), detail={"reason": code, **detail})
    return ApiError(status, message, code)


@router.post("/claims/{claim_id}/approve")
def approve(claim_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    failure: Optional[ApiError] = None
    try:
        with tenant_session(principal.organisation_id) as session:
            claim = owned(session, Claim, claim_id, org, lock=True)
            # One approval at a time per employee: the annual limit cannot be overrun.
            session.scalar(select(Employee.id).where(Employee.id == claim.employee_id).with_for_update())
            if claim.status != ClaimStatus.PENDING:
                failure = _refuse(session, principal, audit.CLAIM_APPROVED, claim,
                                  f"Only a pending claim can be approved; this one is {claim.status}.", "NOT_PENDING")
            else:
                result = assess(session, claim, today())
                if not result.approvable:
                    code = result.problems[0][0]
                    failure = _refuse(session, principal, audit.CLAIM_APPROVED, claim,
                                      " ".join(m for _, m in result.problems), code,
                                      problems=[c for c, _ in result.problems])
                else:
                    claim.status = ClaimStatus.APPROVED
                    claim.copay_santim = result.copay_santim
                    claim.approved_santim = result.payable_santim
                    claim.reviewed_by = principal.admin_id
                    claim.reviewer_name = principal.name
                    claim.reviewed_at = utcnow()
                    claim.rejection_reason = None
                    session.flush()
                    audit.by(session, principal, audit.CLAIM_APPROVED, target_type="claim", target_id=claim.id,
                             target_name=claim_code(claim.number),
                             detail={"total_santim": claim.total_santim, "copay_santim": result.copay_santim,
                                     "approved_santim": result.payable_santim, "capped": result.capped})
                    data = _load(session, claim)
                    data["notes"] = list(result.notes)
                    return data
    except IntegrityError as exc:  # the same receipt approved at the same moment (uq_claims_receipt_once)
        raise ApiError(409, "This receipt was just approved on another claim.", "DUPLICATE_RECEIPT") from exc
    raise failure


@router.post("/claims/{claim_id}/reject")
def reject(claim_id: str, body: RejectIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    reason = checked(validation.text, body.reason, "A reason", min_len=3, max_len=1000)
    failure: Optional[ApiError] = None
    with tenant_session(principal.organisation_id) as session:
        claim = owned(session, Claim, claim_id, principal.organisation_id, lock=True)
        if claim.status != ClaimStatus.PENDING:
            failure = _refuse(session, principal, audit.CLAIM_REJECTED, claim,
                              f"Only a pending claim can be rejected; this one is {claim.status}.", "NOT_PENDING")
        else:
            claim.status = ClaimStatus.REJECTED
            claim.rejection_reason = reason
            claim.reviewed_by = principal.admin_id
            claim.reviewer_name = principal.name
            claim.reviewed_at = utcnow()
            audit.by(session, principal, audit.CLAIM_REJECTED, target_type="claim", target_id=claim.id,
                     target_name=claim_code(claim.number), detail={"reason": reason})
            return _load(session, claim)
    raise failure
