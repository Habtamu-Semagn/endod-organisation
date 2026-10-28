"""What connected systems read and change: employees (sync by employee number,
deactivate), claims and payout batches. JSON, not FHIR: this is HR data.

* **Employees** are matched by ``employee_number`` within the organisation.
  A sync (``POST /employees``, at most 500) is all or nothing: every row is
  checked first (the same rules as the Employees screen and its CSV import,
  app.api.employees), and with any error nothing changes (422, every row's
  errors). Sending the same employees again changes nothing ("unchanged"):
  the sync is idempotent by content, and an Idempotency-Key replays the first
  answer as well. A field left out of a row is left as it is; ``dependants``,
  when given, is the employee's whole list of covered dependants. Payout
  changes are audited with the accounts masked, exactly like the portal's.
* **Test mode** (a test connection) runs every check and answers what would
  happen (``"mode": "test"``), and stores nothing: no employee, no audit
  event, no Idempotency-Key, no webhook.
* **Claims and batches** are read only; receipt files never leave (v1).

Every function runs in a session acting for the caller's organisation (row-level
security) and filters on it as well (app.tenancy's rule).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import audit, validation
from app.api.common import today
from app.api.employees import IMPORT_COLUMNS, PAYOUT_FIELDS, clean_employee, payout_changes, payout_detail
from app.db import iso, tenant_session, utcnow
from app.errors import ApiError
from app.integrations import webhooks
from app.integrations.tokens import Caller, record
from app.models import (
    BatchStatus, Claim, ClaimItem, ClaimStatus, Dependant, Employee, IntegrationIdempotency, PaymentBatch,
    PayoutMethod, Relationship,
)
from app.policy import batch_code, claim_code

#: Employees in one sync.
MAX_EMPLOYEES = 500
#: Dependants of one employee in a sync.
MAX_DEPENDANTS = 20
#: The largest request body read (a sync of 500 employees is far smaller).
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_PAGE = 500
MAX_IDEMPOTENCY_KEY = 255
#: The fields of an employee a sync may send.
SYNC_FIELDS = (*IMPORT_COLUMNS, "active", "dependants")
_HEX_ID = re.compile(r"^[0-9a-f]{32}$")


# --- payloads ------------------------------------------------------------------------------------

def dependant_payload(d: Dependant) -> Dict[str, Any]:
    return {"id": d.id, "name": d.name, "relationship": d.relationship,
            "birth_date": d.birth_date.isoformat() if d.birth_date else None}


def employee_payload(e: Employee, dependants: List[Dependant]) -> Dict[str, Any]:
    return {
        "id": e.id, "employee_number": e.employee_number, "name": e.name, "phone": e.phone,
        "department": e.department, "endod_id": e.endod_id, "active": e.active,
        "payout_method": e.payout_method, "payout_account": e.payout_account,
        "dependants": [dependant_payload(d) for d in dependants],
        "created_at": iso(e.created_at), "updated_at": iso(e.updated_at), "deactivated_at": iso(e.deactivated_at),
    }


def claim_payload(c: Claim, employee_number: Optional[str]) -> Dict[str, Any]:
    return {
        "id": c.id, "code": claim_code(c.number), "status": c.status, "source": c.source,
        "employee_id": c.employee_id, "employee_number": employee_number, "dependant_id": c.dependant_id,
        "pharmacy_name": c.pharmacy_name, "pharmacy_tin": c.pharmacy_tin, "receipt_number": c.receipt_number,
        "receipt_date": c.receipt_date.isoformat(), "total_santim": c.total_santim,
        "copay_santim": c.copay_santim, "approved_santim": c.approved_santim,
        "rejection_reason": c.rejection_reason, "has_receipt": c.receipt_file_id is not None,
        "created_at": iso(c.created_at), "reviewed_at": iso(c.reviewed_at), "batch_id": c.batch_id,
        "paid_at": iso(c.paid_at),
    }


def batch_payload(b: PaymentBatch) -> Dict[str, Any]:
    return {
        "id": b.id, "code": batch_code(b.number), "status": b.status, "method": b.method,
        "method_label": PayoutMethod.LABELS.get(b.method, b.method), "claim_count": b.claim_count,
        "total_santim": b.total_santim, "created_at": iso(b.created_at), "exported_at": iso(b.exported_at),
        "paid_at": iso(b.paid_at), "reference": b.reference,
    }


def not_found(what: str = "Not found.") -> ApiError:
    return ApiError(404, what, "NOT_FOUND")


def _read(session, caller: Caller, resource: str, count: int, target_id: Optional[str] = None) -> None:
    record(session, caller, audit.INTEGRATION_DATA_READ, target_type=resource, target_id=target_id,
           detail={"resource": resource, "count": count})


def _dependants(session, organisation_id: str, employee_ids: List[str]) -> Dict[str, List[Dependant]]:
    out: Dict[str, List[Dependant]] = {}
    if not employee_ids:
        return out
    for d in session.scalars(select(Dependant).where(
            Dependant.organisation_id == organisation_id, Dependant.employee_id.in_(employee_ids),
            Dependant.active.is_(True)).order_by(Dependant.created_at, Dependant.id)):
        out.setdefault(d.employee_id, []).append(d)
    return out


# --- reading -------------------------------------------------------------------------------------

def list_employees(caller: Caller, status: str, updated_since, limit: int, offset: int) -> Dict[str, Any]:
    org = caller.organisation_id
    filters = [Employee.organisation_id == org]
    if status != "all":
        filters.append(Employee.active.is_(status == "active"))
    if updated_since is not None:
        filters.append(Employee.updated_at >= updated_since)
    with tenant_session(org) as session:
        total = session.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
        rows = session.scalars(select(Employee).where(*filters).order_by(Employee.employee_number)
                               .offset(offset).limit(limit)).all()
        dependants = _dependants(session, org, [e.id for e in rows])
        _read(session, caller, "employees", len(rows))
        return {"items": [employee_payload(e, dependants.get(e.id, [])) for e in rows], "total": total,
                "limit": limit, "offset": offset, "has_more": offset + len(rows) < total}


def get_employee(caller: Caller, employee_number: str) -> Dict[str, Any]:
    number = _number_or_404(employee_number)
    org = caller.organisation_id
    with tenant_session(org) as session:
        employee = session.scalar(select(Employee).where(Employee.organisation_id == org,
                                                         Employee.employee_number == number))
        if employee is None:
            raise not_found("No employee has this employee number.")
        _read(session, caller, "employee", 1, employee.id)
        return employee_payload(employee, _dependants(session, org, [employee.id]).get(employee.id, []))


def list_claims(caller: Caller, status: Optional[str], employee_number: Optional[str], date_from: Optional[date],
                date_to: Optional[date], limit: int, offset: int) -> Dict[str, Any]:
    org = caller.organisation_id
    if status is not None and status not in ClaimStatus.ALL:
        raise ApiError(400, f"status must be one of {', '.join(ClaimStatus.ALL)}.", "VALIDATION_ERROR")
    filters = [Claim.organisation_id == org, Employee.organisation_id == org]
    if status:
        filters.append(Claim.status == status)
    if employee_number:
        filters.append(Employee.employee_number == employee_number)
    if date_from:
        filters.append(Claim.receipt_date >= date_from)
    if date_to:
        filters.append(Claim.receipt_date <= date_to)
    joined = select(Claim, Employee.employee_number).join(Employee, Employee.id == Claim.employee_id)
    with tenant_session(org) as session:
        total = session.scalar(select(func.count()).select_from(Claim).join(Employee, Employee.id == Claim.employee_id)
                               .where(*filters)) or 0
        rows = session.execute(joined.where(*filters).order_by(Claim.number.desc()).offset(offset).limit(limit)).all()
        _read(session, caller, "claims", len(rows))
        return {"items": [claim_payload(c, number) for c, number in rows], "total": total, "limit": limit,
                "offset": offset, "has_more": offset + len(rows) < total}


def get_claim(caller: Caller, claim_id: str) -> Dict[str, Any]:
    org = caller.organisation_id
    if not _HEX_ID.match(claim_id or ""):
        raise not_found()
    with tenant_session(org) as session:
        row = session.execute(select(Claim, Employee.employee_number).join(Employee, Employee.id == Claim.employee_id)
                              .where(Claim.id == claim_id, Claim.organisation_id == org,
                                     Employee.organisation_id == org)).first()
        if row is None:
            raise not_found()
        claim, number = row
        items = session.scalars(select(ClaimItem).where(ClaimItem.claim_id == claim.id).order_by(ClaimItem.position))
        _read(session, caller, "claim", 1, claim.id)
        return {**claim_payload(claim, number),
                "items": [{"medicine": i.medicine, "quantity": i.quantity, "unit_price_santim": i.unit_price_santim,
                           "line_total_santim": i.line_total_santim} for i in items]}


def list_batches(caller: Caller, status: Optional[str], limit: int, offset: int) -> Dict[str, Any]:
    org = caller.organisation_id
    if status is not None and status not in BatchStatus.ALL:
        raise ApiError(400, f"status must be one of {', '.join(BatchStatus.ALL)}.", "VALIDATION_ERROR")
    filters = [PaymentBatch.organisation_id == org] + ([PaymentBatch.status == status] if status else [])
    with tenant_session(org) as session:
        total = session.scalar(select(func.count()).select_from(PaymentBatch).where(*filters)) or 0
        rows = session.scalars(select(PaymentBatch).where(*filters).order_by(PaymentBatch.number.desc())
                               .offset(offset).limit(limit)).all()
        _read(session, caller, "batches", len(rows))
        return {"items": [batch_payload(b) for b in rows], "total": total, "limit": limit, "offset": offset,
                "has_more": offset + len(rows) < total}


def get_batch(caller: Caller, batch_id: str) -> Dict[str, Any]:
    org = caller.organisation_id
    if not _HEX_ID.match(batch_id or ""):
        raise not_found()
    with tenant_session(org) as session:
        batch = session.scalar(select(PaymentBatch).where(PaymentBatch.id == batch_id,
                                                          PaymentBatch.organisation_id == org))
        if batch is None:
            raise not_found()
        rows = session.execute(select(Claim, Employee.employee_number).join(Employee, Employee.id == Claim.employee_id)
                               .where(Claim.organisation_id == org, Employee.organisation_id == org,
                                      Claim.batch_id == batch.id).order_by(Claim.number)).all()
        _read(session, caller, "batch", 1, batch.id)
        # Never the payout accounts: the bank file stays in the portal.
        return {**batch_payload(batch),
                "claims": [{"claim_id": c.id, "code": claim_code(c.number), "employee_id": c.employee_id,
                            "employee_number": number, "approved_santim": c.approved_santim, "status": c.status}
                           for c, number in rows]}


# --- idempotency ----------------------------------------------------------------------------------

def request_hash(method: str, path: str, data: bytes) -> str:
    digest = hashlib.sha256()
    for part in (method.encode(), b"\n", path.encode(), b"\n", data):
        digest.update(part)
    return digest.hexdigest()


def check_idempotency_key(key: Optional[str]) -> Optional[str]:
    if key is None:
        return None
    if not 0 < len(key) <= MAX_IDEMPOTENCY_KEY or any(not 32 < ord(ch) < 127 for ch in key):
        raise ApiError(400, f"The Idempotency-Key must be 1 to {MAX_IDEMPOTENCY_KEY} printable ASCII characters.",
                       "VALIDATION_ERROR")
    return key


Work = Callable[[Any], Tuple[int, Dict[str, Any]]]


def run_write(caller: Caller, key: Optional[str], fingerprint: str, work: Work) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """Run a write in one transaction. With an Idempotency-Key (live mode), the
    first successful answer is kept for 24 hours and replayed for the same
    request; the same key with another request is refused (422)."""
    org = caller.organisation_id
    store = key is not None and not caller.test
    try:
        with tenant_session(org) as session:
            if store:
                row = session.scalar(select(IntegrationIdempotency).where(
                    IntegrationIdempotency.organisation_id == org, IntegrationIdempotency.client_pk == caller.client_pk,
                    IntegrationIdempotency.key == key))
                if row is not None:
                    if row.request_hash != fingerprint:
                        raise ApiError(422, "This Idempotency-Key was already used for a different request.",
                                       "IDEMPOTENCY_KEY_REUSED")
                    return row.status_code, json.loads(row.response), {"Idempotent-Replayed": "true"}
            status, body = work(session)
            if status >= 400:
                session.rollback()
                return status, body, {}
            if store:
                session.add(IntegrationIdempotency(organisation_id=org, client_pk=caller.client_pk, key=key,
                                                   request_hash=fingerprint, status_code=status,
                                                   response=json.dumps(body, separators=(",", ":"))))
                session.flush()
            if caller.test:
                session.rollback()  # stores nothing (the work stored nothing either)
            return status, body, {}
    except IntegrityError:
        raise ApiError(409, "The same employees, or the same Idempotency-Key, were being changed at the same time; "
                            "send the request again.", "CONFLICT") from None


# --- syncing employees ------------------------------------------------------------------------------

@dataclass
class Row:
    index: int
    employee_number: str
    given: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    action: str = "error"
    fields: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    dependants: Optional[List[Dict[str, Any]]] = None
    changes: List[str] = field(default_factory=list)
    employee: Optional[Employee] = None

    def result(self) -> Dict[str, Any]:
        return {"index": self.index, "employee_number": self.employee_number, "action": self.action,
                "employee_id": self.employee.id if self.employee is not None else None,
                "changes": self.changes, "errors": self.errors}


def parse_sync(data: bytes) -> List[Any]:
    try:
        body = json.loads(data.decode("utf-8-sig"))
    except RecursionError:
        raise ApiError(400, "The JSON is nested too deeply.", "INVALID_JSON") from None
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "The body is not valid JSON.", "INVALID_JSON") from None
    if not isinstance(body, dict) or set(body) != {"employees"} or not isinstance(body["employees"], list):
        raise ApiError(400, 'Send {"employees": [ ... ]}.', "VALIDATION_ERROR")
    rows = body["employees"]
    if not rows:
        raise ApiError(400, "Send at least one employee.", "VALIDATION_ERROR")
    if len(rows) > MAX_EMPLOYEES:
        raise ApiError(413, f"At most {MAX_EMPLOYEES} employees per request; send the rest in another request.",
                       "TOO_MANY_EMPLOYEES")
    return rows


def _string_or_none(row: Row, name: str) -> None:
    value = row.given.get(name)
    if value is not None and not isinstance(value, str):
        row.errors.append(f"{name} must be a string.")


def _clean_dependants(row: Row, value: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(value, list):
        row.errors.append("dependants must be a list.")
        return None
    if len(value) > MAX_DEPENDANTS:
        row.errors.append(f"At most {MAX_DEPENDANTS} dependants per employee.")
        return None
    out: List[Dict[str, Any]] = []
    seen = set()
    for n, item in enumerate(value, start=1):
        if not isinstance(item, dict) or not set(item) <= {"name", "relationship", "birth_date"}:
            row.errors.append(f"Dependant {n} must be an object with name, relationship and birth_date.")
            continue
        try:
            name = validation.text(item.get("name") if isinstance(item.get("name"), str) else None,
                                   f"Dependant {n} name", min_len=2, max_len=120)
        except validation.Invalid as exc:
            row.errors.append(str(exc))
            continue
        relationship = item.get("relationship")
        relationship = relationship.strip().lower() if isinstance(relationship, str) else None
        if relationship not in Relationship.ALL:
            row.errors.append(f"Dependant {n} relationship must be one of {', '.join(Relationship.ALL)}.")
            continue
        birth = item.get("birth_date")
        birth_date = None
        if birth is not None:
            try:
                birth_date = date.fromisoformat(birth) if isinstance(birth, str) and len(birth) == 10 else None
            except ValueError:
                birth_date = None
            if birth_date is None:
                row.errors.append(f"Dependant {n} birth_date must be a date like 2015-04-30.")
                continue
            if birth_date > today():
                row.errors.append(f"Dependant {n} birth_date cannot be in the future.")
                continue
        identity = (name.casefold(), relationship)
        if identity in seen:
            row.errors.append(f"Dependant {n} is listed twice.")
            continue
        seen.add(identity)
        out.append({"name": name, "relationship": relationship, "birth_date": birth_date})
    return out


def _plan(session, organisation_id: str, raw_rows: List[Any]) -> List[Row]:
    rows: List[Row] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            row = Row(index, "", {})
            row.errors.append("Each employee must be a JSON object.")
            rows.append(row)
            continue
        unknown = sorted(set(raw) - set(SYNC_FIELDS))
        number_raw = raw.get("employee_number")
        row = Row(index, number_raw.strip() if isinstance(number_raw, str) else "", raw)
        if unknown:
            row.errors.append(f"Unknown field(s): {', '.join(unknown)[:200]}.")
        for name in IMPORT_COLUMNS:
            _string_or_none(row, name)
        try:
            row.employee_number = validation.employee_number(number_raw if isinstance(number_raw, str) else None)
        except validation.Invalid as exc:
            row.errors.append(str(exc))
        if "active" in raw and not isinstance(raw["active"], bool):
            row.errors.append("active must be true or false.")
        if "dependants" in raw:
            row.dependants = _clean_dependants(row, raw["dependants"])
        if ("payout_method" in raw) != ("payout_account" in raw):
            row.errors.append("Send payout_method and payout_account together (both null to remove them).")
        rows.append(row)

    numbers = [r.employee_number for r in rows if r.employee_number]
    existing = {e.employee_number: e for e in session.scalars(select(Employee).where(
        Employee.organisation_id == organisation_id, Employee.employee_number.in_(numbers)))} if numbers else {}
    seen: Dict[str, int] = {}
    for row in rows:
        if row.employee_number:
            if row.employee_number in seen:
                row.errors.append(f"Employee number {row.employee_number} is also at index {seen[row.employee_number]}.")
            else:
                seen[row.employee_number] = row.index
        if row.errors:
            continue
        current = existing.get(row.employee_number)
        row.employee = current
        given = {k: v for k, v in row.given.items() if k in IMPORT_COLUMNS}
        if current is None:
            missing = [k for k in ("name", "phone", "department") if not row.given.get(k)]
            if missing:
                row.errors.append(f"A new employee needs {', '.join(missing)}.")
                continue
            merged = {k: None for k in IMPORT_COLUMNS} | given
        else:
            merged = {k: getattr(current, k) for k in IMPORT_COLUMNS} | given
        try:
            row.fields = clean_employee(merged)
        except validation.Invalid as exc:
            row.errors.append(str(exc))
            # Every problem of the row, not only the first (like the CSV import).
            for check, key in ((validation.phone, "phone"), (validation.endod_id, "endod_id")):
                if key in given:
                    try:
                        check(given.get(key))
                    except validation.Invalid as more:
                        if str(more) not in row.errors:
                            row.errors.append(str(more))
            continue
        row.active = row.given.get("active")
        if current is None:
            row.action = "create"
            row.changes = sorted(k for k, v in row.fields.items() if v is not None)
            if row.active is False:
                row.changes.append("active")
            if row.dependants:
                row.changes.append("dependants")
        else:
            row.changes = sorted(k for k, v in row.fields.items() if getattr(current, k) != v)
            if row.active is not None and row.active != current.active:
                row.changes.append("active")
            if row.dependants is not None and _dependant_changes(session, current, row.dependants):
                row.changes.append("dependants")
            row.action = "update" if row.changes else "unchanged"

    # Endod IDs stay unique within the organisation, after the whole sync.
    planned = {r.employee_number: r.fields["endod_id"] for r in rows if r.fields is not None and not r.errors}
    owners: Dict[str, str] = {}
    for number, endod in session.execute(select(Employee.employee_number, Employee.endod_id).where(
            Employee.organisation_id == organisation_id, Employee.endod_id.is_not(None))):
        if number not in planned:
            owners[endod] = number
    for row in rows:
        endod = row.fields["endod_id"] if row.fields is not None and not row.errors else None
        if not endod:
            continue
        owner = owners.get(endod)
        if owner is not None and owner != row.employee_number:
            row.errors.append(f"Endod ID {endod} belongs to employee {owner}.")
        else:
            owners[endod] = row.employee_number
    for row in rows:
        if row.errors:
            row.action, row.changes = "error", []
    return rows


def _active_dependants(session, employee: Employee) -> List[Dependant]:
    return list(session.scalars(select(Dependant).where(
        Dependant.organisation_id == employee.organisation_id, Dependant.employee_id == employee.id,
        Dependant.active.is_(True)).order_by(Dependant.created_at, Dependant.id)))


def _dependant_changes(session, employee: Employee, wanted: List[Dict[str, Any]]) -> bool:
    current = {(d.name.casefold(), d.relationship): d.birth_date for d in _active_dependants(session, employee)}
    target = {(d["name"].casefold(), d["relationship"]): d["birth_date"] for d in wanted}
    return current != target


def _summary(rows: List[Row]) -> Dict[str, int]:
    return {key: sum(1 for r in rows if r.action == key) for key in ("create", "update", "unchanged", "error")}


def sync_employees(caller: Caller, raw_rows: List[Any]) -> Work:
    """The work of ``POST /employees``, for run_write."""

    def work(session) -> Tuple[int, Dict[str, Any]]:
        rows = _plan(session, caller.organisation_id, raw_rows)
        summary = _summary(rows)
        mode = "test" if caller.test else "live"
        if summary["error"]:
            return 422, {"error": f"{summary['error']} employee(s) have errors; nothing was changed.",
                         "error_code": "INVALID_EMPLOYEES", "mode": mode, "stored": False, "summary": summary,
                         "results": [r.result() for r in rows]}
        if caller.test:
            return 200, {"mode": mode, "stored": False, "summary": summary, "results": [r.result() for r in rows]}
        now = utcnow()
        for row in rows:
            if row.action == "create":
                _create(session, caller, row, now)
            elif row.action == "update":
                _update(session, caller, row, now)
        record(session, caller, audit.INTEGRATION_EMPLOYEES_SYNCED, target_type="organisation",
               target_id=caller.organisation_id, detail={"summary": summary})
        return 200, {"mode": mode, "stored": True, "summary": summary, "results": [r.result() for r in rows]}

    return work


def _audit_employee(session, caller: Caller, action: str, employee: Employee, **detail) -> None:
    record(session, caller, action, target_type="employee", target_id=employee.id, target_name=employee.name,
           detail={**detail, "via": "api"})


def _audit_payout(session, caller: Caller, employee: Employee, before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """The same masked before and after as the portal (app.api.employees)."""
    _audit_employee(session, caller, audit.EMPLOYEE_PAYOUT_CHANGED, employee, **payout_detail(before, after))


def _create(session, caller: Caller, row: Row, now) -> None:
    active = row.active is not False
    employee = Employee(organisation_id=caller.organisation_id, **row.fields, active=active,
                        deactivated_at=None if active else now, created_at=now, updated_at=now)
    session.add(employee)
    session.flush()
    row.employee = employee
    _audit_employee(session, caller, audit.EMPLOYEE_CREATED, employee, employee_number=employee.employee_number)
    if payout_changes({}, row.fields):
        _audit_payout(session, caller, employee, {}, row.fields)
    for d in row.dependants or []:
        _add_dependant(session, caller, employee, d)
    webhooks.employee_event(session, employee, "created")


def _add_dependant(session, caller: Caller, employee: Employee, wanted: Dict[str, Any]) -> None:
    dependant = Dependant(organisation_id=employee.organisation_id, employee_id=employee.id, name=wanted["name"],
                          relationship=wanted["relationship"], birth_date=wanted["birth_date"])
    session.add(dependant)
    session.flush()
    _audit_employee(session, caller, audit.DEPENDANT_ADDED, employee, dependant_id=dependant.id,
                    relationship=dependant.relationship)


def _update(session, caller: Caller, row: Row, now) -> None:
    employee = session.scalar(select(Employee).where(
        Employee.id == row.employee.id, Employee.organisation_id == caller.organisation_id).with_for_update())
    before = {k: getattr(employee, k) for k in PAYOUT_FIELDS}
    changed = [k for k, v in row.fields.items() if getattr(employee, k) != v]
    for key in changed:
        setattr(employee, key, row.fields[key])
    employee.updated_at = now
    if changed:
        _audit_employee(session, caller, audit.EMPLOYEE_UPDATED, employee, fields=sorted(changed))
    if payout_changes(before, row.fields):
        _audit_payout(session, caller, employee, before, row.fields)
    change = "updated"
    if row.active is not None and row.active != employee.active:
        employee.active = row.active
        employee.deactivated_at = None if row.active else now
        _audit_employee(session, caller, audit.EMPLOYEE_ACTIVATED if row.active else audit.EMPLOYEE_DEACTIVATED,
                        employee)
        if not changed and row.dependants is None:
            change = "activated" if row.active else "deactivated"
    if row.dependants is not None:
        current = {(d.name.casefold(), d.relationship): d for d in _active_dependants(session, employee)}
        wanted = {(d["name"].casefold(), d["relationship"]): d for d in row.dependants}
        for identity, dependant in current.items():
            if identity not in wanted:
                dependant.active = False
                _audit_employee(session, caller, audit.DEPENDANT_REMOVED, employee, dependant_id=dependant.id)
            elif dependant.birth_date != wanted[identity]["birth_date"]:
                dependant.birth_date = wanted[identity]["birth_date"]
        for identity, d in wanted.items():
            if identity not in current:
                _add_dependant(session, caller, employee, d)
    webhooks.employee_event(session, employee, change)


def _number_or_404(employee_number: str) -> str:
    try:
        return validation.employee_number(employee_number)
    except validation.Invalid:
        raise not_found("No employee has this employee number.") from None


def deactivate_employee(caller: Caller, employee_number: str) -> Work:
    """The work of ``POST /employees/{employee_number}/deactivate``."""
    number = _number_or_404(employee_number)

    def work(session) -> Tuple[int, Dict[str, Any]]:
        employee = session.scalar(select(Employee).where(
            Employee.organisation_id == caller.organisation_id, Employee.employee_number == number)
            .with_for_update())
        if employee is None:
            raise not_found("No employee has this employee number.")
        mode = "test" if caller.test else "live"
        action = "deactivate" if employee.active else "unchanged"
        answer = {"mode": mode, "stored": not caller.test, "employee_number": employee.employee_number,
                  "employee_id": employee.id, "action": action}
        if caller.test or not employee.active:
            return 200, answer
        employee.active = False
        employee.deactivated_at = employee.updated_at = utcnow()
        _audit_employee(session, caller, audit.EMPLOYEE_DEACTIVATED, employee)
        webhooks.employee_event(session, employee, "deactivated")
        return 200, answer

    return work
