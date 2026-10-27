"""`/batches`: payout batches. TenaCare moves no money.

Approved claims are grouped into a batch for one payout method (CBE, Awash,
Dashen or Telebirr); the batch's file is exported for the organisation to
upload to its bank or Telebirr; after paying, an admin marks the batch paid
with the bank's reference (with a fresh TOTP), and its claims become paid.
Only approved claims can be batched, and a paid batch never changes.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import audit, csvutil, money, validation
from app.api.common import ADDIS_ABABA, batch_payload, checked, claim_payload, csv_response, today
from app.auth import Principal, current_admin, fresh_admin
from app.db import tenant_session, utcnow
from app.errors import ApiError
from app.models import (
    AuditResult, BatchStatus, Claim, ClaimStatus, Employee, Organisation, PaymentBatch, PayoutMethod,
)
from app.policy import batch_code, claim_code
from app.tenancy import owned

router = APIRouter(tags=["batches"])

PAID_IS_FINAL = "This batch is paid and can no longer change."


class BatchIn(BaseModel):
    method: str = Field(max_length=16)
    #: Which approved claims; all that are ready for the method when left out.
    claim_ids: Optional[List[str]] = Field(default=None, max_length=1000)


class PaidIn(BaseModel):
    reference: str = Field(max_length=120)


def _enabled_methods(session, org: str) -> List[str]:
    methods = session.scalar(select(Organisation.payout_methods).where(Organisation.id == org)) or ""
    return [m for m in methods.split(",") if m in PayoutMethod.ALL]


def _ready(session, org: str):
    """Approved claims not in a batch, with their employee."""
    return session.execute(
        select(Claim, Employee).join(Employee, Employee.id == Claim.employee_id)
        .where(Claim.organisation_id == org, Employee.organisation_id == org,
               Claim.status == ClaimStatus.APPROVED, Claim.batch_id.is_(None),
               # Nothing to pay back (e.g. a 100% co-pay): never batched.
               Claim.approved_santim > 0)
        .order_by(Claim.reviewed_at, Claim.number)).all()


@router.get("/batches")
def list_batches(status: Optional[str] = Query(default=None, max_length=16),
                 principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    if status is not None and status not in BatchStatus.ALL:
        raise ApiError(400, f"status must be one of {', '.join(BatchStatus.ALL)}.", "VALIDATION_ERROR")
    with tenant_session(principal.organisation_id) as session:
        query = select(PaymentBatch).where(PaymentBatch.organisation_id == org)
        if status:
            query = query.where(PaymentBatch.status == status)
        batches = session.scalars(query.order_by(PaymentBatch.number.desc()).limit(200)).all()
        ready = _ready(session, org)
        by_method: Dict[str, Dict[str, int]] = {m: {"claims": 0, "total_santim": 0} for m in PayoutMethod.ALL}
        missing = {"claims": 0, "total_santim": 0}
        for claim, employee in ready:
            bucket = by_method.get(employee.payout_method) if employee.payout_account else None
            bucket = bucket if bucket is not None else missing
            bucket["claims"] += 1
            bucket["total_santim"] += claim.approved_santim or 0
        month_start = datetime.combine(today().replace(day=1), time(), tzinfo=ADDIS_ABABA).astimezone(timezone.utc)
        paid_this_month = session.scalar(select(func.coalesce(func.sum(PaymentBatch.total_santim), 0)).where(
            PaymentBatch.organisation_id == org, PaymentBatch.status == BatchStatus.PAID,
            PaymentBatch.paid_at >= month_start)) or 0
        open_total = session.scalar(select(func.coalesce(func.sum(PaymentBatch.total_santim), 0)).where(
            PaymentBatch.organisation_id == org, PaymentBatch.status == BatchStatus.OPEN)) or 0
        return {
            "items": [batch_payload(b) for b in batches],
            "ready": {
                "claims": [{**claim_payload(c, e), "payout_account": e.payout_account,
                            "payout_ready": bool(e.payout_method and e.payout_account)} for c, e in ready],
                "by_method": by_method, "missing_payout_details": missing,
                "total_santim": sum(c.approved_santim or 0 for c, _ in ready),
            },
            "enabled_methods": _enabled_methods(session, org),
            "paid_this_month_santim": int(paid_this_month), "open_total_santim": int(open_total),
        }


@router.post("/batches", status_code=201)
def create_batch(body: BatchIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    method = body.method.strip().lower()
    failure: Optional[ApiError] = None
    with tenant_session(principal.organisation_id) as session:
        if method not in _enabled_methods(session, org):
            raise ApiError(400, "That payout method is not enabled for your organisation.", "VALIDATION_ERROR")
        organisation = session.scalar(select(Organisation).where(Organisation.id == org).with_for_update())
        ready = [(c, e) for c, e in _ready(session, org)]
        eligible = {c.id: (c, e) for c, e in ready if e.payout_method == method and e.payout_account}
        if body.claim_ids is not None:
            wanted = list(dict.fromkeys(body.claim_ids))
            refused = [cid for cid in wanted if cid not in eligible]
            if refused or not wanted:
                failure = ApiError(409, "Only approved claims that are not in a batch, of employees paid by "
                                        f"{PayoutMethod.LABELS[method]}, can go in this batch.", "NOT_BATCHABLE")
            chosen = [eligible[cid] for cid in wanted if cid in eligible]
        else:
            chosen = list(eligible.values())
            if not chosen:
                failure = ApiError(409, f"No approved claims are ready to pay by {PayoutMethod.LABELS[method]}.",
                                   "NOTHING_TO_BATCH")
        if failure is None:
            number = organisation.next_batch_number
            organisation.next_batch_number = number + 1
            batch = PaymentBatch(organisation_id=org, number=number, method=method, status=BatchStatus.OPEN,
                                 created_by=principal.admin_id, claim_count=len(chosen),
                                 total_santim=sum(c.approved_santim or 0 for c, _ in chosen))
            session.add(batch)
            session.flush()
            for claim, employee in chosen:
                # Re-read under lock: the claim must still be approved and unbatched.
                locked = owned(session, Claim, claim.id, org, lock=True)
                if locked.status != ClaimStatus.APPROVED or locked.batch_id is not None:
                    raise ApiError(409, "A claim changed while the batch was made; try again.", "CONFLICT")
                locked.batch_id = batch.id
                locked.payout_account = employee.payout_account
            audit.by(session, principal, audit.BATCH_CREATED, target_type="batch", target_id=batch.id,
                     target_name=batch_code(number),
                     detail={"method": method, "claims": len(chosen), "total_santim": batch.total_santim})
            return _detail(session, batch)
        audit.by(session, principal, audit.BATCH_CREATED, AuditResult.FAILURE, target_type="batch",
                 detail={"method": method, "reason": failure.code})
    raise failure


def _batch_rows(session, batch: PaymentBatch):
    return session.execute(
        select(Claim, Employee).join(Employee, Employee.id == Claim.employee_id)
        .where(Claim.organisation_id == batch.organisation_id, Claim.batch_id == batch.id)
        .order_by(Claim.number)).all()


def _detail(session, batch: PaymentBatch) -> Dict[str, Any]:
    rows = _batch_rows(session, batch)
    return {**batch_payload(batch),
            "claims": [{**claim_payload(c, e), "payout_account": c.payout_account} for c, e in rows]}


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        return _detail(session, owned(session, PaymentBatch, batch_id, principal.organisation_id))


def _payout_file(session, batch: PaymentBatch) -> str:
    """The upload file for the batch's method. Banks: one credit per employee
    account; Telebirr: one transfer per wallet (MSISDN without the +).
    Amounts are plain birr with two decimals ("1234.50"). Accounts are the
    ones recorded on each claim when it was batched, never the employee's
    current one; a line is never written for nothing."""
    organisation = session.get(Organisation, batch.organisation_id)
    rows = [(c, e) for c, e in _batch_rows(session, batch) if (c.approved_santim or 0) > 0 and c.payout_account]
    code = batch_code(batch.number)
    if batch.method == PayoutMethod.TELEBIRR:
        header = ("msisdn", "beneficiary_name", "amount_etb", "reference", "remark")
        lines = [((c.payout_account or "").lstrip("+"), e.name, money.plain_etb(c.approved_santim or 0),
                  f"{code}/{claim_code(c.number)}", f"Medication reimbursement {claim_code(c.number)}")
                 for c, e in rows]
    else:
        header = ("debit_account", "beneficiary_account", "beneficiary_name", "amount_etb", "reference", "narration")
        lines = [(organisation.payout_debit_account or "", c.payout_account or "", e.name,
                  money.plain_etb(c.approved_santim or 0), f"{code}/{claim_code(c.number)}",
                  f"Medication reimbursement {claim_code(c.number)}") for c, e in rows]
    return csvutil.to_csv(header, lines)


@router.get("/batches/{batch_id}/export")
def export_batch(batch_id: str, principal: Principal = Depends(current_admin)):
    with tenant_session(principal.organisation_id) as session:
        batch = owned(session, PaymentBatch, batch_id, principal.organisation_id, lock=True)
        text = _payout_file(session, batch)
        first = batch.exported_at is None
        if first:
            # From now on the batch may be paid at the bank: it can no longer be cancelled.
            batch.exported_at = utcnow()
            batch.exported_by = principal.admin_id
        audit.by(session, principal, audit.BATCH_EXPORTED, target_type="batch", target_id=batch.id,
                 target_name=batch_code(batch.number),
                 detail={"method": batch.method, "status": batch.status, "first_export": first})
        name = f"{batch_code(batch.number)}-{batch.method}.csv"
    return csv_response(text, name)


@router.post("/batches/{batch_id}/mark-paid")
def mark_paid(batch_id: str, body: PaidIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    reference = checked(validation.text, body.reference, "The payment reference", min_len=3, max_len=80)
    failure: Optional[ApiError] = None
    with tenant_session(principal.organisation_id) as session:
        batch = owned(session, PaymentBatch, batch_id, principal.organisation_id, lock=True)
        if batch.status == BatchStatus.PAID:
            failure = ApiError(409, PAID_IS_FINAL, "BATCH_PAID")
            audit.by(session, principal, audit.BATCH_PAID, AuditResult.FAILURE, target_type="batch",
                     target_id=batch.id, target_name=batch_code(batch.number), detail={"reason": "already_paid"})
        else:
            now = utcnow()
            batch.status = BatchStatus.PAID
            batch.paid_at = now
            batch.paid_by = principal.admin_id
            batch.reference = reference
            for claim, _ in _batch_rows(session, batch):
                claim.status = ClaimStatus.PAID
                claim.paid_at = now
            audit.by(session, principal, audit.BATCH_PAID, target_type="batch", target_id=batch.id,
                     target_name=batch_code(batch.number),
                     detail={"reference": reference, "claims": batch.claim_count, "total_santim": batch.total_santim})
            return _detail(session, batch)
    raise failure


EXPORTED_IS_FINAL = ("This batch's payout file was already downloaded, so it may have been paid: mark it paid, "
                     "or contact Endod support.")


@router.post("/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """An open batch whose file was never downloaded is taken apart (its claims
    are ready to batch again). A downloaded or paid one never is: its claims
    could otherwise be paid twice."""
    failure: Optional[ApiError] = None
    with tenant_session(principal.organisation_id) as session:
        batch = owned(session, PaymentBatch, batch_id, principal.organisation_id, lock=True)
        if batch.status == BatchStatus.PAID:
            failure = ApiError(409, PAID_IS_FINAL, "BATCH_PAID")
            audit.by(session, principal, audit.BATCH_CANCELLED, AuditResult.FAILURE, target_type="batch",
                     target_id=batch.id, target_name=batch_code(batch.number), detail={"reason": "already_paid"})
        elif batch.exported_at is not None:
            failure = ApiError(409, EXPORTED_IS_FINAL, "BATCH_EXPORTED")
            audit.by(session, principal, audit.BATCH_CANCELLED, AuditResult.FAILURE, target_type="batch",
                     target_id=batch.id, target_name=batch_code(batch.number), detail={"reason": "already_exported"})
        else:
            for claim, _ in _batch_rows(session, batch):
                claim.batch_id = None
                claim.payout_account = None
            audit.by(session, principal, audit.BATCH_CANCELLED, target_type="batch", target_id=batch.id,
                     target_name=batch_code(batch.number),
                     detail={"claims": batch.claim_count, "total_santim": batch.total_santim})
            session.flush()
            session.delete(batch)
            return {"ok": True}
    raise failure
