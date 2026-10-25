"""Benefit policies and the approval rules.

A claim may be approved only when:

* the employee is active, and, for a dependant's medicine, the dependant is
  active and the policy covers dependants;
* the receipt date is within the current policy year (and not in the future);
* no medicine on it is excluded by the policy;
* no other approved or paid claim has the same pharmacy TIN and receipt number;
* something is left of the employee's annual limit.

The organisation pays back its share (the total minus the employee's co-pay),
capped at what is left of the annual limit; the cap is reported clearly.
Usage counts the approved and paid claims whose receipt date is in the same
policy year, for the employee and their dependants together.
"""

from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select

from app import money
from app.models import BenefitPolicy, Claim, ClaimItem, ClaimStatus, Dependant, Employee

#: What a new organisation starts with (create-org); admins change it in Settings.
DEFAULT_ANNUAL_LIMIT_SANTIM = 1_000_000  # ETB 10,000.00
MAX_EXCLUSIONS = 200


@dataclass(frozen=True)
class Effective:
    """The policy that applies to one employee."""

    annual_limit_santim: int
    copay_percent: int
    dependants_covered: bool
    excluded_medicines: Tuple[str, ...]
    year_start_month: int
    year_start_day: int
    #: True when the employee has their own override.
    override: bool


def exclusions(policy: BenefitPolicy) -> List[str]:
    try:
        value = json.loads(policy.excluded_medicines or "[]")
    except ValueError:
        return []
    return [str(v) for v in value if isinstance(v, str)]


def default_policy(session, organisation_id: str) -> BenefitPolicy:
    row = session.scalar(select(BenefitPolicy).where(
        BenefitPolicy.organisation_id == organisation_id, BenefitPolicy.employee_id.is_(None)))
    if row is None:  # every organisation gets one at create-org; never expected
        raise RuntimeError("organisation has no benefit policy")
    return row


def employee_override(session, organisation_id: str, employee_id: str) -> Optional[BenefitPolicy]:
    return session.scalar(select(BenefitPolicy).where(
        BenefitPolicy.organisation_id == organisation_id, BenefitPolicy.employee_id == employee_id))


def effective(session, organisation_id: str, employee_id: str) -> Effective:
    base = default_policy(session, organisation_id)
    own = employee_override(session, organisation_id, employee_id)
    source = own or base
    return Effective(
        annual_limit_santim=source.annual_limit_santim, copay_percent=source.copay_percent,
        dependants_covered=source.dependants_covered, excluded_medicines=tuple(exclusions(source)),
        year_start_month=base.year_start_month, year_start_day=base.year_start_day, override=own is not None)


# --- the policy year ---------------------------------------------------------------------------

def _start_in(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def policy_year(on: date, month: int, day: int) -> Tuple[date, date]:
    """The policy year containing ``on``: (first day, last day), inclusive."""
    start = _start_in(on.year, month, day)
    if on < start:
        start = _start_in(on.year - 1, month, day)
    end = _start_in(start.year + 1, month, day) - timedelta(days=1)
    return start, end


def check_year_start(month: int, day: int) -> None:
    if not 1 <= month <= 12:
        raise ValueError("The policy year must start in a month from 1 to 12.")
    if not 1 <= day <= calendar.monthrange(2001, month)[1]:
        raise ValueError("That day does not exist in that month.")


# --- exclusions --------------------------------------------------------------------------------

def normalise_medicine(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def excluded_by(medicine: str, excluded: Sequence[str]) -> Optional[str]:
    """The exclusion that ``medicine`` falls under (whole words, any case), or None.
    "Sildenafil" excludes "Sildenafil 50mg tablets", not "Sildenafilx"."""
    name = normalise_medicine(medicine)
    for term in excluded:
        wanted = normalise_medicine(term)
        if wanted and re.search(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)", name):
            return term
    return None


# --- usage and assessment ----------------------------------------------------------------------

def used_in_year(session, organisation_id: str, employee_id: str, start: date, end: date,
                 exclude_claim_id: Optional[str] = None) -> int:
    """What the organisation has approved for this employee (and dependants) in the year."""
    query = select(func.coalesce(func.sum(Claim.approved_santim), 0)).where(
        Claim.organisation_id == organisation_id, Claim.employee_id == employee_id,
        Claim.status.in_((ClaimStatus.APPROVED, ClaimStatus.PAID)),
        Claim.receipt_date >= start, Claim.receipt_date <= end)
    if exclude_claim_id:
        query = query.where(Claim.id != exclude_claim_id)
    return int(session.scalar(query) or 0)


@dataclass
class Assessment:
    total_santim: int
    copay_percent: int
    copay_santim: int
    share_santim: int
    payable_santim: int
    annual_limit_santim: int
    used_santim: int
    remaining_santim: int
    capped: bool
    year_start: date
    year_end: date
    #: (code, message) pairs; any of them blocks approval.
    problems: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def approvable(self) -> bool:
        return not self.problems

    def payload(self) -> Dict:
        return {
            "total_santim": self.total_santim, "copay_percent": self.copay_percent,
            "copay_santim": self.copay_santim, "share_santim": self.share_santim,
            "payable_santim": self.payable_santim, "annual_limit_santim": self.annual_limit_santim,
            "used_santim": self.used_santim, "remaining_santim": self.remaining_santim, "capped": self.capped,
            "policy_year": {"start": self.year_start.isoformat(), "end": self.year_end.isoformat()},
            "problems": [{"code": c, "message": m} for c, m in self.problems],
            "notes": list(self.notes), "approvable": self.approvable,
        }


def assess(session, claim: Claim, today: date) -> Assessment:
    """Whether ``claim`` may be approved today, and for how much."""
    org = claim.organisation_id
    employee = session.scalar(select(Employee).where(Employee.id == claim.employee_id,
                                                     Employee.organisation_id == org))
    rules = effective(session, org, claim.employee_id)
    start, end = policy_year(today, rules.year_start_month, rules.year_start_day)
    used = used_in_year(session, org, claim.employee_id, start, end, exclude_claim_id=claim.id)
    remaining = max(0, rules.annual_limit_santim - used)
    copay, share, payable = money.split_claim(claim.total_santim, rules.copay_percent, remaining)
    result = Assessment(
        total_santim=claim.total_santim, copay_percent=rules.copay_percent, copay_santim=copay,
        share_santim=share, payable_santim=payable, annual_limit_santim=rules.annual_limit_santim,
        used_santim=used, remaining_santim=remaining, capped=payable < share,
        year_start=start, year_end=end)
    problems = result.problems

    if employee is None or not employee.active:
        problems.append(("EMPLOYEE_INACTIVE", "The employee is not active, so the claim cannot be approved."))
    if claim.dependant_id:
        dependant = session.scalar(select(Dependant).where(
            Dependant.id == claim.dependant_id, Dependant.organisation_id == org,
            Dependant.employee_id == claim.employee_id))
        if not rules.dependants_covered:
            problems.append(("DEPENDANT_NOT_COVERED", "The policy does not cover dependants."))
        elif dependant is None or not dependant.active:
            problems.append(("DEPENDANT_INACTIVE", "The dependant is no longer covered."))
    if claim.receipt_date > today:
        problems.append(("FUTURE_DATE", "The receipt date is in the future."))
    elif not start <= claim.receipt_date <= end:
        problems.append(("OUTSIDE_POLICY_YEAR",
                         f"The receipt date {claim.receipt_date.isoformat()} is outside the current policy year "
                         f"({start.isoformat()} to {end.isoformat()})."))
    items = session.scalars(select(ClaimItem).where(ClaimItem.claim_id == claim.id)
                            .order_by(ClaimItem.position)).all()
    for item in items:
        term = excluded_by(item.medicine, rules.excluded_medicines)
        if term:
            problems.append(("EXCLUDED_MEDICINE", f"{item.medicine} is excluded by the policy ({term})."))
    duplicate = session.scalar(select(Claim.number).where(
        Claim.organisation_id == org, Claim.id != claim.id, Claim.pharmacy_tin == claim.pharmacy_tin,
        Claim.receipt_number == claim.receipt_number,
        Claim.status.in_((ClaimStatus.APPROVED, ClaimStatus.PAID))))
    if duplicate is not None:
        problems.append(("DUPLICATE_RECEIPT",
                         f"This receipt (TIN {claim.pharmacy_tin}, number {claim.receipt_number}) was already "
                         f"approved on claim {claim_code(duplicate)}."))
    if remaining == 0:
        problems.append(("LIMIT_REACHED",
                         f"The annual limit of {money.format_etb(rules.annual_limit_santim, True)} is used up "
                         f"for this policy year; nothing is left to pay back."))
    elif payable == 0:
        result.notes.append(
            f"Nothing is reimbursed: the employee's co-pay of {money.format_etb(copay, True)} covers the whole "
            f"receipt. Approving records the claim; it never goes into a payout batch.")
    elif result.capped:
        result.notes.append(
            f"The organisation's share of {money.format_etb(share, True)} is capped at the remaining annual "
            f"limit: {money.format_etb(payable, True)} is paid back; the employee bears the other "
            f"{money.format_etb(claim.total_santim - payable, True)}.")
    return result


def claim_code(number: int) -> str:
    return f"CLM-{number:06d}"


def batch_code(number: int) -> str:
    return f"BATCH-{number:04d}"
