"""A company applies to use TenaCare (docs/company-onboarding.md), after the
hospital service's onboarding (Hospital-service backend-hospital/app/onboarding.py).

The steps, in the order the web app shows them:

1. ``contact``: the account. ``POST /application/start`` (public) creates the
   organisation (with a *draft* application, so it is locked), its first
   admin (the contact) and signs them in with an applicant session (password
   only, app.auth): it reaches the application alone. Two-step verification
   becomes mandatory on approval, which ends every session of the
   organisation's admins: the next sign-in enrols an authenticator (QR code,
   recovery codes) before anything else;
2. ``company``: the company's details (legal name, TIN, licence, sector, ...);
3. ``documents``: trade licence, TIN certificate and authorization letter;
4. ``review``: submit. Endod approves or rejects it through the platform
   API (app.api.platform); a rejected application is fixed and resubmitted.

Each step is saved as it is completed, so the applicant can sign out and
carry on later. Until the application is approved, the organisation's admins
reach only these routes (app.auth.current_admin answers 403 everywhere else).

The TIN applied for stays on the application until approval (only then is it
the organisation's). Only an approved, active organisation holds a TIN: the
applicant is refused it with one generic message. Other applications with
the same TIN are allowed (nobody can squat a TIN by applying first) and Endod
sees ``duplicate_tin`` on each of them (Amendment 1 of the contract).

Nobody verifies the applicant's email yet (``email_verified`` is always false
for Endod), so drafts not submitted within DRAFT_DAYS are deleted with
everything they made (``sweep_expired_drafts``): by the API's background task
and when Endod lists applications (``sweep_now``, at most once per
ORG_SWEEP_INTERVAL_SECONDS, one sweep at a time). Until then an expired draft's
admin cannot sign in (app.auth), and an application with its email deletes
that one draft first (app.api.application).

Locks: every path that changes an application locks the organisation row
first, then the application row (``lock_for_change``): the applicant's steps,
Endod's approve and reject, and suspend (the organisation only). One order
everywhere, so two of them never wait on each other in a cycle.
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select, text

from app import audit, files, rls
from app.config import get_settings
from app.db import PLATFORM_KEY, ensure_aware, iso, platform_session, utcnow
from app.errors import ApiError
from app.models import (
    AdminSession, ApplicationDocument, ApplicationStatus, AuditResult, BenefitPolicy, DocumentKind, LoginThrottle,
    OrgAdmin, Organisation, OrganisationApplication, RecoveryCode, SetupToken,
)

#: A draft not submitted within this many days is deleted (its email was never verified).
DRAFT_DAYS = 14

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
CLOSED = "This application was closed."
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
    """``tin`` is held by another approved, active organisation (the only
    holder of a TIN; applications never block one another). Asked by the
    applicant's own session, which sees no other organisation: on PostgreSQL
    through one SECURITY DEFINER function that answers yes or no (app.rls)."""
    return rls.tin_taken(session, tin, organisation_id)


def duplicate_tin(session, app: OrganisationApplication) -> bool:
    """Another application or organisation has this application's TIN (for Endod's review)."""
    if not app.tin:
        return False
    other_org = session.scalar(select(Organisation.id).where(
        Organisation.tin == app.tin, Organisation.id != app.organisation_id))
    if other_org is not None:
        return True
    return session.scalar(select(OrganisationApplication.organisation_id).where(
        OrganisationApplication.tin == app.tin,
        OrganisationApplication.organisation_id != app.organisation_id)) is not None


def require_editable(app: Optional[OrganisationApplication]) -> OrganisationApplication:
    if app is None or app.status == ApplicationStatus.APPROVED:
        raise ApiError(409, ALREADY_APPROVED, "ALREADY_APPROVED")
    if app.status == ApplicationStatus.CLOSED:
        raise ApiError(409, CLOSED, "APPLICATION_CLOSED")
    if app.status not in ApplicationStatus.EDITABLE:
        raise ApiError(409, LOCKED_FOR_REVIEW, "UNDER_REVIEW")
    return app


def lock_for_change(session, organisation_id: str) -> Tuple[Optional[Organisation], Optional[OrganisationApplication]]:
    """The organisation and its application, locked in the one order every
    changing path uses: the organisation, then the application."""
    org = session.scalar(select(Organisation).where(Organisation.id == organisation_id).with_for_update())
    if org is None:
        return None, None
    return org, application_of(session, organisation_id, lock=True)


# --- expired drafts -------------------------------------------------------------------------

def expired(app: Optional[OrganisationApplication], now: Optional[datetime] = None) -> bool:
    return (app is not None and app.status == ApplicationStatus.DRAFT
            and ensure_aware(app.created_at) < (now or utcnow()) - timedelta(days=DRAFT_DAYS))


def delete_organisation(session, organisation_id: str) -> None:
    """Everything an application made: its documents (rows and files), the
    application, the admins with their sessions, codes, links and throttles,
    the default policy and the organisation. The audit log keeps its entries."""
    admin_ids = list(session.scalars(select(OrgAdmin.id).where(OrgAdmin.organisation_id == organisation_id)))
    doc_ids = list(session.scalars(select(ApplicationDocument.id)
                                   .where(ApplicationDocument.organisation_id == organisation_id)))
    session.execute(delete(ApplicationDocument).where(ApplicationDocument.organisation_id == organisation_id))
    session.execute(delete(OrganisationApplication).where(OrganisationApplication.organisation_id == organisation_id))
    if admin_ids:
        for model in (AdminSession, RecoveryCode, SetupToken, LoginThrottle):
            session.execute(delete(model).where(model.admin_id.in_(admin_ids)))
        session.execute(delete(OrgAdmin).where(OrgAdmin.id.in_(admin_ids)))
    session.execute(delete(BenefitPolicy).where(BenefitPolicy.organisation_id == organisation_id))
    session.execute(delete(Organisation).where(Organisation.id == organisation_id))
    session.flush()
    for doc_id in doc_ids:
        files.delete(organisation_id, doc_id)


def sweep_expired_drafts(session, now: Optional[datetime] = None, email: Optional[str] = None) -> int:
    """Delete drafts not submitted within DRAFT_DAYS, each audited. Returns how
    many. Acts across organisations: ``session`` is an app.db.platform_session.
    With ``email``: only the expired draft (if any) whose admin has that email."""
    if not session.info.get(PLATFORM_KEY):
        raise RuntimeError("The expired-draft sweep runs in a platform session (app.db.platform_session).")
    now = now or utcnow()
    cutoff = now - timedelta(days=DRAFT_DAYS)
    query = select(OrganisationApplication.organisation_id).where(
        OrganisationApplication.status == ApplicationStatus.DRAFT, OrganisationApplication.created_at < cutoff)
    if email is not None:
        query = query.where(OrganisationApplication.organisation_id.in_(
            select(OrgAdmin.organisation_id).where(OrgAdmin.email == email)))
    stale = list(session.scalars(query))
    swept = 0
    for organisation_id in stale:
        # Same lock order as every other path; checked again under the lock.
        org, app = lock_for_change(session, organisation_id)
        if org is None or not expired(app, now):
            continue
        emails = list(session.scalars(select(OrgAdmin.email).where(OrgAdmin.organisation_id == organisation_id)))
        legal_name = app.legal_name
        delete_organisation(session, organisation_id)
        audit.record(session, audit.APPLICATION_EXPIRED, AuditResult.SUCCESS, organisation_id=organisation_id,
                     target_type="organisation", target_id=organisation_id, target_name=legal_name,
                     detail={"reason": f"draft_not_submitted_within_{DRAFT_DAYS}_days", "admins": emails})
        swept += 1
    return swept


#: Any two sweeps of the whole table, in any process, take turns on this
#: transaction-level advisory lock; one that finds it taken skips.
SWEEP_LOCK = 0x54656E61  # "Tena"
_last_sweep: Optional[float] = None


def sweep_now(force: bool = False) -> Optional[int]:
    """The periodic sweep: at most once per ORG_SWEEP_INTERVAL_SECONDS in this
    process (unless ``force``), and skipped when another sweep is running
    (pg_try_advisory_xact_lock). Returns how many drafts went, or None if skipped.

    Never on a sign-in or an application: those are public, so a sweep there
    would let anyone make the database take row locks over every expired draft
    on demand. The API runs it in the background (app.main), the platform
    list runs it, and ``python -m app.cli sweep-drafts`` does from cron."""
    global _last_sweep
    interval = get_settings().ORG_SWEEP_INTERVAL_SECONDS
    started = time.monotonic()
    if not force and interval > 0 and _last_sweep is not None and started - _last_sweep < interval:
        return None
    _last_sweep = started
    with platform_session() as session:
        if rls.postgres(session) and not session.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"),
                                                        {"k": SWEEP_LOCK}):
            return None
        return sweep_expired_drafts(session)


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
        "rejection_reason": app.rejection_reason if app.status in (ApplicationStatus.REJECTED,
                                                                   ApplicationStatus.CLOSED) else None,
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
        "duplicate_tin": duplicate_tin(session, app),
        # Nobody verifies the applicant's email yet (contract, Amendment 1).
        "email_verified": False,
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
