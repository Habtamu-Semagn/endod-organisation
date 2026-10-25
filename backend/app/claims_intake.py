"""Where claims come from.

Today every claim is entered by HR (``ClaimSource.MANUAL``): the employee
paid at the pharmacy and brings the receipt; an admin types it in with a
photo or scan of it (app.api.claims).

THE SEAM FOR AUTOMATIC CLAIMS. Endod pharmacies will later report what they
dispense to an employee (matched by Endod ID, ``Employee.endod_id``). That
needs prices, which pharmacies do not record yet, so it is not built. When it
is, it should:

* receive the dispensing record from the pharmacy service over the private
  bus (endod-bus), authenticated service to service, never through the BFF;
* find the employee by ``endod_id`` within the organisations that cover them;
* build a :class:`NewClaim` with ``source=ClaimSource.PHARMACY``,
  ``external_ref`` set to the dispensing record's id (unique per source, so a
  record re-sent is not claimed twice), and the receipt the pharmacy issued;
* call :func:`create_claim` exactly like the manual path, so every check
  (tenant, duplicate receipts, amounts in santim) and the audit entry are the
  same, and HR still approves or rejects it on the Claims screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlalchemy import select

from app import money
from app.errors import ApiError
from app.models import Claim, ClaimItem, ClaimSource, ClaimStatus, Dependant, Employee, Organisation, ReceiptFile
from app.policy import claim_code
from app.tenancy import owned

MAX_ITEMS = 50
MAX_QUANTITY = 100_000


@dataclass(frozen=True)
class NewItem:
    medicine: str
    quantity: int
    unit_price_santim: int


@dataclass(frozen=True)
class NewClaim:
    organisation_id: str
    employee_id: str
    dependant_id: Optional[str]
    pharmacy_name: str
    pharmacy_tin: str
    receipt_number: str
    receipt_date: date
    items: List[NewItem]
    receipt_file_id: Optional[str]
    source: str = ClaimSource.MANUAL
    external_ref: Optional[str] = None
    created_by: Optional[str] = None


def _conflict(message: str, code: str) -> ApiError:
    return ApiError(409, message, code)


def create_claim(session, new: NewClaim, today: date) -> Claim:
    """Check and store a claim (status pending). Raises ApiError; the caller audits."""
    org = new.organisation_id
    employee = owned(session, Employee, new.employee_id, org)
    if new.dependant_id:
        dependant = owned(session, Dependant, new.dependant_id, org)
        if dependant.employee_id != employee.id:
            raise ApiError(400, "That dependant does not belong to this employee.", "VALIDATION_ERROR")
    if new.source not in ClaimSource.ALL:
        raise ApiError(400, "Unknown claim source.", "VALIDATION_ERROR")
    if new.receipt_date > today:
        raise ApiError(400, "The receipt date cannot be in the future.", "VALIDATION_ERROR")
    if not 1 <= len(new.items) <= MAX_ITEMS:
        raise ApiError(400, f"A claim has 1 to {MAX_ITEMS} medicines.", "VALIDATION_ERROR")
    total = 0
    for item in new.items:
        if not (isinstance(item.quantity, int) and 1 <= item.quantity <= MAX_QUANTITY):
            raise ApiError(400, f"Quantity must be a whole number from 1 to {MAX_QUANTITY}.", "VALIDATION_ERROR")
        if not (isinstance(item.unit_price_santim, int) and 1 <= item.unit_price_santim <= money.MAX_SANTIM):
            raise ApiError(400, "Each unit price must be more than zero.", "VALIDATION_ERROR")
        total += money.line_total(item.quantity, item.unit_price_santim)
    if total > money.MAX_SANTIM:
        raise ApiError(400, "The claim total is too large.", "VALIDATION_ERROR")

    receipt = None
    if new.source == ClaimSource.MANUAL or new.receipt_file_id:
        if not new.receipt_file_id:
            raise ApiError(400, "Attach the receipt (a photo or a PDF).", "RECEIPT_REQUIRED")
        receipt = owned(session, ReceiptFile, new.receipt_file_id, org)
        if session.scalar(select(Claim.id).where(Claim.receipt_file_id == receipt.id)) is not None:
            raise _conflict("That receipt file is already attached to another claim; upload it again.",
                            "RECEIPT_IN_USE")

    duplicate = session.scalar(select(Claim.number).where(
        Claim.organisation_id == org, Claim.pharmacy_tin == new.pharmacy_tin,
        Claim.receipt_number == new.receipt_number, Claim.status != ClaimStatus.REJECTED))
    if duplicate is not None:
        raise _conflict(f"This receipt (pharmacy TIN {new.pharmacy_tin}, number {new.receipt_number}) is already "
                        f"claimed on {claim_code(duplicate)}.", "DUPLICATE_RECEIPT")

    organisation = session.scalar(select(Organisation).where(Organisation.id == org).with_for_update())
    number = organisation.next_claim_number
    organisation.next_claim_number = number + 1
    claim = Claim(
        organisation_id=org, number=number, employee_id=employee.id, dependant_id=new.dependant_id,
        source=new.source, external_ref=new.external_ref, pharmacy_name=new.pharmacy_name,
        pharmacy_tin=new.pharmacy_tin, receipt_number=new.receipt_number, receipt_date=new.receipt_date,
        total_santim=total, status=ClaimStatus.PENDING, receipt_file_id=receipt.id if receipt else None,
        created_by=new.created_by)
    session.add(claim)
    session.flush()
    for position, item in enumerate(new.items):
        session.add(ClaimItem(claim_id=claim.id, position=position, medicine=item.medicine,
                              quantity=item.quantity, unit_price_santim=item.unit_price_santim,
                              line_total_santim=money.line_total(item.quantity, item.unit_price_santim)))
    session.flush()
    return claim
