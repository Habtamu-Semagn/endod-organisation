"""A company applies to use TenaCare (docs/company-onboarding.md), after the
hospital service's onboarding (Hospital-service backend-hospital/app/onboarding.py).

The steps, in the order the web app shows them:

1. ``contact``: the account. ``POST /application/start`` (public) creates the
   organisation (with a *draft* application, so it is locked), its first
   admin (the contact) and opens an enrolment session: the applicant enrols
   an authenticator (QR code, recovery codes) before anything else;
2. ``company``: the company's details (legal name, TIN, licence, sector, ...);
3. ``documents``: trade licence, TIN certificate and authorization letter;
4. ``review``: submit. Endod approves or rejects it through the platform
   API (app.api.platform); a rejected application is fixed and resubmitted.

Each step is saved as it is completed, so the applicant can sign out and
carry on later. Until the application is approved, the organisation's admins
reach only these routes (app.auth.current_admin answers 403 everywhere else).

The TIN applied for stays on the application until approval (only then is it
the organisation's): a TIN already used by an approved organisation, or by
another submitted application, is refused with one generic message.
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.db import iso
from app.errors import ApiError
from app.models import (
    ApplicationDocument, ApplicationStatus, DocumentKind, OrgAdmin, Organisation, OrganisationApplication,
)

#: Each document at most this big.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

STEPS = ("contact", "company", "documents")
STEP_NAMES = {"contact": "contact person", "company": "company details", "documents": "documents"}
COMPANY_FIELDS = ("legal_name", "tin", "business_license_number", "sector", "employee_count", "city", "address",
                  "phone", "email")

#: Said for a TIN that is taken, whatever the reason (an approved organisation
#: or another submitted application): nothing more is told about who has it.
REFUSED = "This application cannot be accepted with these details. Contact Endod if you think this is a mistake."
LOCKED_FOR_REVIEW = "Your application is with Endod for review; it cannot be changed now."
ALREADY_APPROVED = "Your organisation is already approved."


def placeholder_tin() -> str:
    """What an applying organisation's ``tin`` holds until approval: never 10
    digits (so never a real TIN), unique, and shown nowhere."""
    return "~" + secrets.token_hex(5)[:9]


def application_of(session, organisation_id: str, lock: bool = False) -> Optional[OrganisationApplication]:
    query = select(OrganisationApplication).where(OrganisationApplication.organisation_id == organisation_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def status_of(app: Optional[OrganisationApplication]) -> str:
    """No application: made by the CLI (or before applications existed), so approved."""
    return app.status if app is not None else ApplicationStatus.APPROVED


def contact_of(session, app: OrganisationApplication) -> Optional[OrgAdmin]:
    if app.contact_admin_id:
        admin = session.get(OrgAdmin, app.contact_admin_id)
        if admin is not None:
            return admin
    return session.scalar(select(OrgAdmin).where(OrgAdmin.organisation_id == app.organisation_id)
                          .order_by(OrgAdmin.created_at, OrgAdmin.id).limit(1))


def documents_of(session, organisation_id: str) -> Dict[str, ApplicationDocument]:
    return {d.kind: d for d in session.scalars(
        select(ApplicationDocument).where(ApplicationDocument.organisation_id == organisation_id))}


def missing(session, app: OrganisationApplication) -> Dict[str, List[str]]:
    """What each step still needs (an empty list: the step is complete)."""
    contact = contact_of(session, app)
    result: Dict[str, List[str]] = {step: [] for step in STEPS}
    if contact is None or not contact.name:
        result["contact"].append("full_name")
    if not app.contact_title:
        result["contact"].append("title")
    if not app.contact_phone:
        result["contact"].append("phone")
    result["company"] = [field for field in COMPANY_FIELDS if getattr(app, field) in (None, "")]
    docs = documents_of(session, app.organisation_id)
    result["documents"] = [kind for kind in DocumentKind.ALL if kind not in docs]
    return result


def tin_taken(session, tin: str, organisation_id: str) -> bool:
    """``tin`` belongs to another approved organisation (active or suspended)
    or to another organisation's submitted application."""
    approved = session.scalar(select(Organisation.id).where(Organisation.tin == tin,
                                                            Organisation.id != organisation_id))
    if approved is not None:
        return True
    return session.scalar(select(OrganisationApplication.organisation_id).where(
        OrganisationApplication.tin == tin, OrganisationApplication.status == ApplicationStatus.SUBMITTED,
        OrganisationApplication.organisation_id != organisation_id)) is not None


def require_editable(app: Optional[OrganisationApplication]) -> OrganisationApplication:
    if app is None or app.status == ApplicationStatus.APPROVED:
        raise ApiError(409, ALREADY_APPROVED, "ALREADY_APPROVED")
    if app.status not in ApplicationStatus.EDITABLE:
        raise ApiError(409, LOCKED_FOR_REVIEW, "UNDER_REVIEW")
    return app


def document_payload(doc: ApplicationDocument) -> Dict[str, Any]:
    return {"kind": doc.kind, "filename": doc.filename, "content_type": doc.content_type, "size": doc.size,
            "uploaded_at": iso(doc.uploaded_at)}


def application_payload(session, organisation: Organisation) -> Dict[str, Any]:
    """What the wizard and the Under review page show the organisation's admins."""
    app = application_of(session, organisation.id)
    if app is None:
        return {"status": ApplicationStatus.APPROVED, "organisation_name": organisation.name}
    contact = contact_of(session, app)
    docs = documents_of(session, organisation.id)
    gaps = missing(session, app)
    next_step = next((step for step in STEPS if gaps[step]), "review")
    return {
        "status": app.status,
        "organisation_name": organisation.name,
        "editable": app.status in ApplicationStatus.EDITABLE,
        "next_step": next_step,
        "complete": next_step == "review",
        "missing": gaps,
        "submitted_at": iso(app.submitted_at),
        "reviewed_at": iso(app.reviewed_at),
        "rejection_reason": app.rejection_reason if app.status == ApplicationStatus.REJECTED else None,
        "contact": {
            "full_name": contact.name if contact else None,
            "title": app.contact_title,
            "phone": app.contact_phone,
            "email": contact.email if contact else None,
        },
        "company": {field: getattr(app, field) for field in ("legal_name", "trade_name", *COMPANY_FIELDS[1:])},
        "documents": [
            {"kind": kind, "label": DocumentKind.LABELS[kind], "uploaded": kind in docs,
             **(document_payload(docs[kind]) if kind in docs else {})}
            for kind in DocumentKind.ALL
        ],
    }


# --- for Endod (the platform API) ----------------------------------------------------------

def review_item(session, app: OrganisationApplication) -> Dict[str, Any]:
    """One application as GET /platform/applications lists it."""
    contact = contact_of(session, app)
    return {
        "id": app.organisation_id,
        "legal_name": app.legal_name,
        "trade_name": app.trade_name,
        "tin": app.tin,
        "sector": app.sector,
        "employee_count": app.employee_count,
        "city": app.city,
        "status": app.status,
        "submitted_at": iso(app.submitted_at),
        "updated_at": iso(app.updated_at),
        "contact": {
            "full_name": contact.name if contact else None,
            "title": app.contact_title,
            "phone": app.contact_phone,
            "email": contact.email if contact else None,
        },
    }


def review_detail(session, app: OrganisationApplication) -> Dict[str, Any]:
    docs = documents_of(session, app.organisation_id)
    return {
        **review_item(session, app),
        "business_license_number": app.business_license_number,
        "address": app.address,
        "phone": app.phone,
        "email": app.email,
        "rejection_reason": app.rejection_reason,
        "reviewed_at": iso(app.reviewed_at),
        "documents": [document_payload(docs[kind]) for kind in DocumentKind.ALL if kind in docs],
    }
