"""`/employees`: the organisation's roster, dependants, per-employee policy
overrides, and CSV import (preview, then commit) and export.

Every query is limited to the signed-in admin's organisation; an id from
another organisation answers 404 like one that does not exist.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app import audit, csvutil, validation
from app.api.common import (
    bad, checked, claim_payload, csv_response, dependant_payload, employee_payload, like, today,
)
from app.api.settings import PolicyRules, clean_exclusions, rules_payload
from app.auth import Principal, current_admin, fresh_admin, require_fresh
from app.db import tenant_session, utcnow
from app.errors import ApiError
from app.integrations import webhooks
from app.models import (
    BenefitPolicy, Claim, ClaimStatus, Dependant, Employee, Relationship,
)
from app.policy import default_policy, effective, employee_override, policy_year, used_in_year
from app.tenancy import owned

router = APIRouter(tags=["employees"])

MAX_PAGE_SIZE = 100
IMPORT_COLUMNS = ("employee_number", "name", "phone", "department", "endod_id", "payout_method", "payout_account")
REQUIRED_COLUMNS = ("employee_number", "name", "phone", "department")
PAYOUT_FIELDS = ("payout_method", "payout_account")


def mask(account: Optional[str]) -> Optional[str]:
    """An account for the audit log: only its last 4 characters."""
    if not account:
        return None
    return "****" + account[-4:]


def payout_detail(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    return {"before": {"method": before.get("payout_method"), "account": mask(before.get("payout_account"))},
            "after": {"method": after.get("payout_method"), "account": mask(after.get("payout_account"))}}


def payout_changes(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    return any(before.get(k) != after.get(k) for k in PAYOUT_FIELDS)


def _audit_payout(session, principal: Principal, employee: Employee, before: Dict[str, Any],
                  after: Dict[str, Any], via: str) -> None:
    audit.by(session, principal, audit.EMPLOYEE_PAYOUT_CHANGED, target_type="employee", target_id=employee.id,
             target_name=employee.name, detail={**payout_detail(before, after), "via": via})


class EmployeeIn(BaseModel):
    employee_number: str = Field(max_length=60)
    name: str = Field(max_length=200)
    phone: str = Field(max_length=40)
    department: str = Field(max_length=120)
    endod_id: Optional[str] = Field(default=None, max_length=20)
    payout_method: Optional[str] = Field(default=None, max_length=20)
    payout_account: Optional[str] = Field(default=None, max_length=40)


class EmployeePatch(BaseModel):
    employee_number: Optional[str] = Field(default=None, max_length=60)
    name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    department: Optional[str] = Field(default=None, max_length=120)
    endod_id: Optional[str] = Field(default=None, max_length=20)
    payout_method: Optional[str] = Field(default=None, max_length=20)
    payout_account: Optional[str] = Field(default=None, max_length=40)


class DependantIn(BaseModel):
    name: str = Field(max_length=200)
    relationship: str = Field(max_length=20)
    birth_date: Optional[date] = None


def clean_employee(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validated and normalised fields (raises validation.Invalid)."""
    method, account = validation.payout(data.get("payout_method"), data.get("payout_account"))
    return {
        "employee_number": validation.employee_number(data.get("employee_number")),
        "name": validation.text(data.get("name"), "Name", min_len=2, max_len=120),
        "phone": validation.phone(data.get("phone")),
        "department": validation.text(data.get("department"), "Department", max_len=80),
        "endod_id": validation.endod_id(data.get("endod_id")),
        "payout_method": method, "payout_account": account,
    }


def _unique_or_400(session, org: str, fields: Dict[str, Any], employee_id: Optional[str]) -> None:
    clash = session.scalar(select(Employee.id).where(
        Employee.organisation_id == org, Employee.employee_number == fields["employee_number"],
        Employee.id != (employee_id or "")))
    if clash:
        raise ApiError(409, f"Employee number {fields['employee_number']} is already in use.", "DUPLICATE_EMPLOYEE")
    if fields["endod_id"]:
        clash = session.scalar(select(Employee.id).where(
            Employee.organisation_id == org, Employee.endod_id == fields["endod_id"],
            Employee.id != (employee_id or "")))
        if clash:
            raise ApiError(409, f"Endod ID {fields['endod_id']} belongs to another employee.", "DUPLICATE_ENDOD_ID")


def _usage(session, org: str, employee_ids: List[str], start: date, end: date) -> Dict[str, Dict[str, int]]:
    """Claims this policy year and what was approved, per employee."""
    if not employee_ids:
        return {}
    rows = session.execute(
        select(Claim.employee_id, func.count(Claim.id),
               func.coalesce(func.sum(Claim.approved_santim), 0))
        .where(Claim.organisation_id == org, Claim.employee_id.in_(employee_ids),
               Claim.receipt_date >= start, Claim.receipt_date <= end, Claim.status != ClaimStatus.REJECTED)
        .group_by(Claim.employee_id)).all()
    return {eid: {"claims": int(n), "spend_santim": int(s or 0)} for eid, n, s in rows}


def _year(session, org: str):
    base = default_policy(session, org)
    return policy_year(today(), base.year_start_month, base.year_start_day)


@router.get("/employees")
def list_employees(
    q: Optional[str] = Query(default=None, max_length=100),
    department: Optional[str] = Query(default=None, max_length=80),
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=25, ge=1, le=MAX_PAGE_SIZE),
    principal: Principal = Depends(current_admin),
) -> Dict[str, Any]:
    org = principal.organisation_id
    filters = [Employee.organisation_id == org]
    if status != "all":
        filters.append(Employee.active.is_(status == "active"))
    if department:
        filters.append(Employee.department == department)
    if q and q.strip():
        pattern = like(q)
        filters.append(or_(func.lower(Employee.name).like(pattern), func.lower(Employee.employee_number).like(pattern),
                           func.lower(Employee.department).like(pattern), func.lower(Employee.endod_id).like(pattern),
                           Employee.phone.like(pattern)))
    with tenant_session(principal.organisation_id) as session:
        total = session.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
        rows = session.scalars(select(Employee).where(*filters).order_by(Employee.name, Employee.employee_number)
                               .offset((page - 1) * page_size).limit(page_size)).all()
        start, end = _year(session, org)
        usage = _usage(session, org, [e.id for e in rows], start, end)
        dependants: Dict[str, List[Dependant]] = {}
        for d in session.scalars(select(Dependant).where(
                Dependant.organisation_id == org, Dependant.employee_id.in_([e.id for e in rows]),
                Dependant.active.is_(True))):
            dependants.setdefault(d.employee_id, []).append(d)
        overrides = set(session.scalars(select(BenefitPolicy.employee_id).where(
            BenefitPolicy.organisation_id == org, BenefitPolicy.employee_id.in_([e.id for e in rows]))))
        departments = sorted(set(session.scalars(select(Employee.department).where(Employee.organisation_id == org))))
        counts = dict(session.execute(select(Employee.active, func.count()).where(Employee.organisation_id == org)
                                      .group_by(Employee.active)).all())
        linked = session.scalar(select(func.count()).select_from(Employee).where(
            Employee.organisation_id == org, Employee.active.is_(True), Employee.endod_id.is_not(None))) or 0
        claimants = session.scalar(select(func.count(func.distinct(Claim.employee_id))).where(
            Claim.organisation_id == org, Claim.receipt_date >= start, Claim.receipt_date <= end,
            Claim.status != ClaimStatus.REJECTED)) or 0
        dependant_count = session.scalar(select(func.count()).select_from(Dependant).join(
            Employee, Employee.id == Dependant.employee_id).where(
            Dependant.organisation_id == org, Dependant.active.is_(True), Employee.active.is_(True))) or 0
        return {
            "items": [employee_payload(
                e, claims_count=usage.get(e.id, {}).get("claims", 0),
                spend_santim=usage.get(e.id, {}).get("spend_santim", 0),
                dependants=[dependant_payload(d) for d in dependants.get(e.id, [])],
                has_policy_override=e.id in overrides) for e in rows],
            "total": total, "page": page, "page_size": page_size, "departments": departments,
            "counts": {"active": counts.get(True, 0), "inactive": counts.get(False, 0), "linked": linked,
                       "claimants": claimants, "dependants": dependant_count},
            "policy_year": {"start": start.isoformat(), "end": end.isoformat()},
        }


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeIn, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    fields = checked(clean_employee, body.model_dump())
    if payout_changes({}, fields):
        # Where reimbursements go: a fresh code, like any payout change.
        require_fresh(principal)
    org = principal.organisation_id
    try:
        with tenant_session(principal.organisation_id) as session:
            _unique_or_400(session, org, fields, None)
            employee = Employee(organisation_id=org, **fields)
            session.add(employee)
            session.flush()
            audit.by(session, principal, audit.EMPLOYEE_CREATED, target_type="employee", target_id=employee.id,
                     target_name=employee.name, detail={"employee_number": employee.employee_number})
            if payout_changes({}, fields):
                _audit_payout(session, principal, employee, {}, fields, "create")
            webhooks.employee_event(session, employee, "created")
            return employee_payload(employee, dependants=[], claims_count=0, spend_santim=0,
                                    has_policy_override=False)
    except IntegrityError as exc:  # a simultaneous insert of the same number
        raise ApiError(409, "That employee number or Endod ID is already in use.", "DUPLICATE_EMPLOYEE") from exc


@router.get("/employees/export")
def export_employees(principal: Principal = Depends(current_admin)):
    org = principal.organisation_id
    with tenant_session(principal.organisation_id) as session:
        rows = session.scalars(select(Employee).where(Employee.organisation_id == org)
                               .order_by(Employee.employee_number)).all()
        text = csvutil.to_csv(
            (*IMPORT_COLUMNS, "active"),
            [(e.employee_number, e.name, e.phone, e.department, e.endod_id or "", e.payout_method or "",
              e.payout_account or "", "yes" if e.active else "no") for e in rows])
        audit.by(session, principal, audit.EMPLOYEES_EXPORTED, target_type="organisation", target_id=org,
                 detail={"rows": len(rows)})
    return csv_response(text, f"employees-{today().isoformat()}.csv")


# --- CSV import ---------------------------------------------------------------------------------

class ImportIn(BaseModel):
    csv: str = Field(min_length=1, max_length=csvutil.MAX_IMPORT_CHARS)


def _plan_import(session, org: str, text: str) -> Dict[str, Any]:
    """What importing ``text`` would do, row by row, with every error."""
    try:
        rows = csvutil.parse(text)
    except ValueError as exc:
        raise bad(str(exc)) from exc
    if not rows:
        raise bad("The file has a header but no employees.")
    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0][1]]
    if missing:
        raise bad(f"The header must include: {', '.join(REQUIRED_COLUMNS)} (missing {', '.join(missing)}). "
                  f"Optional: endod_id, payout_method, payout_account.")
    existing = {e.employee_number: e for e in session.scalars(select(Employee).where(Employee.organisation_id == org))}
    endod_owner = {e.endod_id: e.employee_number for e in existing.values() if e.endod_id}
    seen_numbers: Dict[str, int] = {}
    seen_endod: Dict[str, int] = {}
    planned = []
    for index, raw in rows:
        errors: List[str] = []
        fields: Optional[Dict[str, Any]] = None
        try:
            fields = clean_employee(raw)
        except validation.Invalid as exc:
            errors.append(str(exc))
            # Find every problem in the row, not only the first.
            for check, key in ((validation.employee_number, "employee_number"), (validation.phone, "phone"),
                               (validation.endod_id, "endod_id")):
                try:
                    check(raw.get(key))
                except validation.Invalid as more:
                    if str(more) not in errors:
                        errors.append(str(more))
        number = (fields or {}).get("employee_number") or (raw.get("employee_number") or "").strip()
        if number:
            if number in seen_numbers:
                errors.append(f"Employee number {number} is also on line {seen_numbers[number]}.")
            else:
                seen_numbers[number] = index
        endod = (fields or {}).get("endod_id")
        if endod:
            if endod in seen_endod:
                errors.append(f"Endod ID {endod} is also on line {seen_endod[endod]}.")
            else:
                seen_endod[endod] = index
            owner = endod_owner.get(endod)
            if owner and owner != number:
                errors.append(f"Endod ID {endod} belongs to employee {owner}.")
        action = "error"
        if not errors and fields is not None:
            current = existing.get(number)
            if current is None:
                action = "create"
            elif any(getattr(current, k) != v for k, v in fields.items()):
                action = "update"
            else:
                action = "unchanged"
        planned.append({"line": index, "employee_number": number, "name": (fields or raw).get("name") or "",
                        "action": action, "errors": errors, "fields": fields})
    summary = {key: sum(1 for p in planned if p["action"] == key) for key in ("create", "update", "unchanged", "error")}
    return {"rows": planned, "summary": summary, "valid": summary["error"] == 0}


def _public_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    return {**plan, "rows": [{k: v for k, v in row.items() if k != "fields"} for row in plan["rows"]]}


@router.post("/employees/import/preview")
def import_preview(body: ImportIn, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        return _public_plan(_plan_import(session, principal.organisation_id, body.csv))


@router.post("/employees/import/commit")
def import_commit(body: ImportIn, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    """All or nothing: with any error in the file, nothing is imported. Needs a
    fresh code (an import can change where reimbursements are paid)."""
    org = principal.organisation_id
    failure: Optional[ApiError] = None
    try:
        with tenant_session(principal.organisation_id) as session:
            plan = _plan_import(session, org, body.csv)
            if not plan["valid"]:
                failure = ApiError(422, f"{plan['summary']['error']} row(s) have errors; fix them and try again. "
                                        "Nothing was imported.", "IMPORT_INVALID")
                audit.by(session, principal, audit.EMPLOYEES_IMPORTED, audit.AuditResult.FAILURE,
                         target_type="organisation", target_id=org, detail={"summary": plan["summary"]})
            else:
                existing = {e.employee_number: e for e in session.scalars(
                    select(Employee).where(Employee.organisation_id == org))}
                now = utcnow()
                for row in plan["rows"]:
                    if row["action"] == "create":
                        employee = Employee(organisation_id=org, **row["fields"])
                        session.add(employee)
                        session.flush()
                        if payout_changes({}, row["fields"]):
                            _audit_payout(session, principal, employee, {}, row["fields"], "import")
                        webhooks.employee_event(session, employee, "created")
                    elif row["action"] == "update":
                        employee = existing[row["employee_number"]]
                        before = {k: getattr(employee, k) for k in PAYOUT_FIELDS}
                        for key, value in row["fields"].items():
                            setattr(employee, key, value)
                        employee.updated_at = now
                        if payout_changes(before, row["fields"]):
                            _audit_payout(session, principal, employee, before, row["fields"], "import")
                        webhooks.employee_event(session, employee, "updated")
                audit.by(session, principal, audit.EMPLOYEES_IMPORTED, target_type="organisation", target_id=org,
                         detail={"summary": plan["summary"]})
                return _public_plan(plan)
    except IntegrityError as exc:
        raise ApiError(409, "Another change to the roster happened at the same time; preview again.",
                       "IMPORT_CONFLICT") from exc
    raise failure


# --- one employee ----------------------------------------------------------------------------------

def _detail(session, principal: Principal, employee: Employee) -> Dict[str, Any]:
    org = principal.organisation_id
    rules = effective(session, org, employee.id)
    start, end = policy_year(today(), rules.year_start_month, rules.year_start_day)
    used = used_in_year(session, org, employee.id, start, end)
    override = employee_override(session, org, employee.id)
    dependants = session.scalars(select(Dependant).where(
        Dependant.organisation_id == org, Dependant.employee_id == employee.id).order_by(Dependant.created_at)).all()
    claims = session.scalars(select(Claim).where(Claim.organisation_id == org, Claim.employee_id == employee.id)
                             .order_by(Claim.receipt_date.desc(), Claim.number.desc()).limit(20)).all()
    usage = _usage(session, org, [employee.id], start, end).get(employee.id, {})
    return employee_payload(
        employee, dependants=[dependant_payload(d) for d in dependants],
        claims_count=usage.get("claims", 0), spend_santim=usage.get("spend_santim", 0),
        has_policy_override=override is not None,
        policy={"annual_limit_santim": rules.annual_limit_santim, "copay_percent": rules.copay_percent,
                "dependants_covered": rules.dependants_covered, "excluded_medicines": list(rules.excluded_medicines),
                "override": rules_payload(override) if override else None},
        usage={"policy_year": {"start": start.isoformat(), "end": end.isoformat()}, "used_santim": used,
               "remaining_santim": max(0, rules.annual_limit_santim - used)},
        recent_claims=[claim_payload(c) for c in claims])


@router.get("/employees/{employee_id}")
def get_employee(employee_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        return _detail(session, principal, owned(session, Employee, employee_id, principal.organisation_id))


@router.patch("/employees/{employee_id}")
def update_employee(employee_id: str, body: EmployeePatch,
                    principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    changes = body.model_dump(exclude_unset=True)
    try:
        with tenant_session(principal.organisation_id) as session:
            employee = owned(session, Employee, employee_id, org, lock=True)
            current = {k: getattr(employee, k) for k in IMPORT_COLUMNS}
            fields = checked(clean_employee, {**current, **changes})
            _unique_or_400(session, org, fields, employee.id)
            changed = {k: v for k, v in fields.items() if getattr(employee, k) != v}
            if payout_changes(current, fields):
                # Where reimbursements go: a fresh code (refused before anything changes).
                require_fresh(principal)
            for key, value in changed.items():
                setattr(employee, key, value)
            if changed:
                employee.updated_at = utcnow()
                audit.by(session, principal, audit.EMPLOYEE_UPDATED, target_type="employee", target_id=employee.id,
                         target_name=employee.name, detail={"fields": sorted(changed)})
            if payout_changes(current, fields):
                _audit_payout(session, principal, employee, current, fields, "edit")
            if changed:
                webhooks.employee_event(session, employee, "updated")
            return _detail(session, principal, employee)
    except IntegrityError as exc:
        raise ApiError(409, "That employee number or Endod ID is already in use.", "DUPLICATE_EMPLOYEE") from exc


def _set_active(employee_id: str, principal: Principal, active: bool) -> Dict[str, Any]:
    with tenant_session(principal.organisation_id) as session:
        employee = owned(session, Employee, employee_id, principal.organisation_id, lock=True)
        if employee.active != active:
            employee.active = active
            employee.deactivated_at = None if active else utcnow()
            employee.updated_at = utcnow()
            audit.by(session, principal, audit.EMPLOYEE_ACTIVATED if active else audit.EMPLOYEE_DEACTIVATED,
                     target_type="employee", target_id=employee.id, target_name=employee.name)
            webhooks.employee_event(session, employee, "activated" if active else "deactivated")
        return _detail(session, principal, employee)


@router.post("/employees/{employee_id}/deactivate")
def deactivate_employee(employee_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    return _set_active(employee_id, principal, False)


@router.post("/employees/{employee_id}/activate")
def activate_employee(employee_id: str, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    return _set_active(employee_id, principal, True)


@router.post("/employees/{employee_id}/dependants", status_code=201)
def add_dependant(employee_id: str, body: DependantIn, principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    name = checked(validation.text, body.name, "Name", min_len=2, max_len=120)
    relationship = body.relationship.strip().lower()
    if relationship not in Relationship.ALL:
        raise bad(f"Relationship must be one of {', '.join(Relationship.ALL)}.")
    if body.birth_date and body.birth_date > today():
        raise bad("The birth date cannot be in the future.")
    with tenant_session(principal.organisation_id) as session:
        employee = owned(session, Employee, employee_id, principal.organisation_id)
        dependant = Dependant(organisation_id=principal.organisation_id, employee_id=employee.id, name=name,
                              relationship=relationship, birth_date=body.birth_date)
        session.add(dependant)
        session.flush()
        audit.by(session, principal, audit.DEPENDANT_ADDED, target_type="employee", target_id=employee.id,
                 target_name=employee.name, detail={"dependant_id": dependant.id, "relationship": relationship})
        webhooks.employee_event(session, employee, "updated")
        return _detail(session, principal, employee)


@router.post("/employees/{employee_id}/dependants/{dependant_id}/remove")
def remove_dependant(employee_id: str, dependant_id: str,
                     principal: Principal = Depends(current_admin)) -> Dict[str, Any]:
    """Ends a dependant's cover (kept for the claims made for them)."""
    with tenant_session(principal.organisation_id) as session:
        employee = owned(session, Employee, employee_id, principal.organisation_id)
        dependant = owned(session, Dependant, dependant_id, principal.organisation_id, lock=True)
        if dependant.employee_id != employee.id:
            raise ApiError(404, "Not found.", "NOT_FOUND")
        if dependant.active:
            dependant.active = False
            audit.by(session, principal, audit.DEPENDANT_REMOVED, target_type="employee", target_id=employee.id,
                     target_name=employee.name, detail={"dependant_id": dependant.id})
            webhooks.employee_event(session, employee, "updated")
        return _detail(session, principal, employee)


# --- per-employee policy ------------------------------------------------------------------------

@router.put("/employees/{employee_id}/policy")
def put_employee_policy(employee_id: str, body: PolicyRules,
                        principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    excluded = clean_exclusions(body.excluded_medicines)
    org = principal.organisation_id
    with tenant_session(principal.organisation_id) as session:
        employee = owned(session, Employee, employee_id, org)
        row = employee_override(session, org, employee.id)
        before = rules_payload(row) if row else None
        if row is None:
            row = BenefitPolicy(organisation_id=org, employee_id=employee.id)
            session.add(row)
        row.annual_limit_santim = body.annual_limit_santim
        row.copay_percent = body.copay_percent
        row.dependants_covered = body.dependants_covered
        row.excluded_medicines = json.dumps(excluded, ensure_ascii=False)
        base = default_policy(session, org)
        row.year_start_month, row.year_start_day = base.year_start_month, base.year_start_day
        row.updated_at = utcnow()
        row.updated_by = principal.admin_id
        session.flush()
        after = rules_payload(row)
        audit.by(session, principal, audit.EMPLOYEE_POLICY_UPDATED, target_type="employee", target_id=employee.id,
                 target_name=employee.name,
                 detail={"before": before and {k: v for k, v in before.items() if k != "updated_at"},
                         "after": {k: v for k, v in after.items() if k != "updated_at"}})
        return _detail(session, principal, employee)


@router.delete("/employees/{employee_id}/policy")
def delete_employee_policy(employee_id: str, principal: Principal = Depends(fresh_admin)) -> Dict[str, Any]:
    org = principal.organisation_id
    with tenant_session(principal.organisation_id) as session:
        employee = owned(session, Employee, employee_id, org)
        row = employee_override(session, org, employee.id)
        if row is not None:
            session.delete(row)
            session.flush()
            audit.by(session, principal, audit.EMPLOYEE_POLICY_REMOVED, target_type="employee",
                     target_id=employee.id, target_name=employee.name)
        return _detail(session, principal, employee)
