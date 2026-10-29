"""`/overview`: the Overview screen's numbers, from the organisation's claims."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app import payout_holds
from app.api.common import today
from app.auth import Principal, current_admin
from app.db import tenant_session
from app.models import Claim, ClaimStatus, Employee
from app.policy import default_policy, policy_year

router = APIRouter(tags=["overview"])


@router.get("/overview")
def overview(principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    with tenant_session(principal.organisation_id) as session:
        base = default_policy(session, org)
        start, end = policy_year(today(), base.year_start_month, base.year_start_day)
        in_year = [Claim.organisation_id == org, Claim.receipt_date >= start, Claim.receipt_date <= end]
        by_status = {s: {"claims": 0, "total_santim": 0, "approved_santim": 0} for s in ClaimStatus.ALL}
        for status, count, total, approved in session.execute(
                select(Claim.status, func.count(), func.coalesce(func.sum(Claim.total_santim), 0),
                       func.coalesce(func.sum(Claim.approved_santim), 0))
                .where(*in_year).group_by(Claim.status)).all():
            by_status[status] = {"claims": int(count), "total_santim": int(total), "approved_santim": int(approved)}
        pending = session.execute(select(func.count(), func.coalesce(func.sum(Claim.total_santim), 0)).where(
            Claim.organisation_id == org, Claim.status == ClaimStatus.PENDING)).one()
        active = session.scalar(select(func.count()).select_from(Employee).where(
            Employee.organisation_id == org, Employee.active.is_(True))) or 0
        linked = session.scalar(select(func.count()).select_from(Employee).where(
            Employee.organisation_id == org, Employee.active.is_(True), Employee.endod_id.is_not(None))) or 0
        claimants = session.scalar(select(func.count(func.distinct(Claim.employee_id))).where(
            *in_year, Claim.status.in_((ClaimStatus.APPROVED, ClaimStatus.PAID)))) or 0
        return {
            "policy_year": {"start": start.isoformat(), "end": end.isoformat()},
            "spend_santim": by_status[ClaimStatus.APPROVED]["approved_santim"]
            + by_status[ClaimStatus.PAID]["approved_santim"],
            "reimbursed_santim": by_status[ClaimStatus.PAID]["approved_santim"],
            "awaiting_payout_santim": by_status[ClaimStatus.APPROVED]["approved_santim"],
            "claims_submitted": sum(v["claims"] for v in by_status.values()),
            "by_status": by_status,
            "pending_claims": int(pending[0]), "pending_total_santim": int(pending[1]),
            "employees": {"active": int(active), "linked_endod": int(linked), "claimants": int(claimants)},
            "policy": {"annual_limit_santim": base.annual_limit_santim, "copay_percent": base.copay_percent,
                       "dependants_covered": base.dependants_covered},
            # Payout accounts changed by connected systems in the last 24 hours (app.payout_holds).
            "payout_alerts": payout_holds.recent_by_connection(session, org),
        }
