"""`/policy` and `/organisation`: the organisation's benefit policy and its
payout settings. Changing either needs a fresh TOTP (app.auth.fresh_admin)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool, StrictInt
from sqlalchemy import select

from app import audit, money
from app.api.common import checked, today
from app.auth import Principal, current_admin, fresh_admin
from app.db import iso, tenant_session, utcnow
from app.errors import ApiError
from app.models import BenefitPolicy, Organisation, PayoutMethod
from app.policy import MAX_EXCLUSIONS, check_year_start, default_policy, exclusions, policy_year
from app import validation

router = APIRouter(tags=["settings"])


class PolicyRules(BaseModel):
    """What an employee override holds (and the organisation's policy, plus the year)."""

    annual_limit_santim: StrictInt = Field(ge=0, le=money.MAX_SANTIM)
    copay_percent: StrictInt = Field(ge=0, le=100)
    dependants_covered: StrictBool
    excluded_medicines: List[str] = Field(default_factory=list, max_length=MAX_EXCLUSIONS)


class PolicyIn(PolicyRules):
    year_start_month: StrictInt = Field(ge=1, le=12)
    year_start_day: StrictInt = Field(ge=1, le=31)


def clean_exclusions(values: List[str]) -> List[str]:
    """Trimmed, de-duplicated (any case), each 2-80 characters."""
    seen, cleaned = set(), []
    for value in values:
        term = checked(validation.text, value, "An excluded medicine", min_len=2, max_len=80)
        if term.casefold() not in seen:
            seen.add(term.casefold())
            cleaned.append(term)
    return cleaned


def rules_payload(p: BenefitPolicy) -> Dict[str, Any]:
    return {"annual_limit_santim": p.annual_limit_santim, "copay_percent": p.copay_percent,
            "dependants_covered": p.dependants_covered, "excluded_medicines": exclusions(p),
            "updated_at": iso(p.updated_at)}


def _rules_snapshot(p: BenefitPolicy) -> Dict[str, Any]:
    return {"annual_limit_santim": p.annual_limit_santim, "copay_percent": p.copay_percent,
            "dependants_covered": p.dependants_covered, "excluded_medicines": exclusions(p),
            "year_start_month": p.year_start_month, "year_start_day": p.year_start_day}


def _organisation_payload(o: Organisation) -> Dict[str, Any]:
    return {"id": o.id, "name": o.name, "tin": o.tin, "contact_name": o.contact_name,
            "contact_email": o.contact_email, "contact_phone": o.contact_phone, "status": o.status,
            "payout": {"debit_account": o.payout_debit_account,
                       "methods": [m for m in (o.payout_methods or "").split(",") if m in PayoutMethod.ALL]}}


@router.get("/policy")
def get_policy(principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        p = default_policy(session, principal.organisation_id)
        start, end = policy_year(today(), p.year_start_month, p.year_start_day)
        return {**rules_payload(p), "year_start_month": p.year_start_month, "year_start_day": p.year_start_day,
                "current_year": {"start": start.isoformat(), "end": end.isoformat()}}


@router.put("/policy")
def put_policy(body: PolicyIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    try:
        check_year_start(body.year_start_month, body.year_start_day)
    except ValueError as exc:
        raise ApiError(400, str(exc), "VALIDATION_ERROR") from exc
    excluded = clean_exclusions(body.excluded_medicines)
    with tenant_session(principal.organisation_id) as session:
        p = default_policy(session, principal.organisation_id)
        before = _rules_snapshot(p)
        p.annual_limit_santim = body.annual_limit_santim
        p.copay_percent = body.copay_percent
        p.dependants_covered = body.dependants_covered
        p.excluded_medicines = json.dumps(excluded, ensure_ascii=False)
        p.year_start_month = body.year_start_month
        p.year_start_day = body.year_start_day
        p.updated_at = utcnow()
        p.updated_by = principal.admin_id
        audit.by(session, principal, audit.POLICY_UPDATED, target_type="policy", target_id=p.id,
                 detail={"before": before, "after": _rules_snapshot(p)})
    return get_policy(principal)


@router.get("/organisation")
def get_organisation(principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        return _organisation_payload(session.get(Organisation, principal.organisation_id))


class PayoutIn(BaseModel):
    debit_account: Optional[str] = Field(default=None, max_length=40)
    methods: List[str] = Field(min_length=1, max_length=len(PayoutMethod.ALL))


@router.put("/organisation/payout")
def put_payout(body: PayoutIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    methods = []
    for method in body.methods:
        if method not in PayoutMethod.ALL:
            raise ApiError(400, f"Payout methods must be among {', '.join(PayoutMethod.ALL)}.", "VALIDATION_ERROR")
        if method not in methods:
            methods.append(method)
    debit = (body.debit_account or "").replace(" ", "").replace("-", "") or None
    if debit is not None and not re.fullmatch(r"[0-9]{8,20}", debit):
        raise ApiError(400, "The debit account must be 8-20 digits.", "VALIDATION_ERROR")
    with tenant_session(principal.organisation_id) as session:
        org = session.scalar(select(Organisation).where(Organisation.id == principal.organisation_id))
        before = {"debit_account": org.payout_debit_account, "methods": org.payout_methods}
        org.payout_debit_account = debit
        org.payout_methods = ",".join(m for m in PayoutMethod.ALL if m in methods)
        audit.by(session, principal, audit.PAYOUT_SETTINGS_UPDATED, target_type="organisation", target_id=org.id,
                 target_name=org.name,
                 detail={"before": before, "after": {"debit_account": debit, "methods": org.payout_methods}})
        return _organisation_payload(org)
