"""`/platform`: Endod's super admin reviews company applications and manages
organisations (docs/company-onboarding.md, the binding contract).

Only the super admin's API calls these, over the ``endod-bus`` network (alias
``endod-organisation-api``), with ``X-Platform-Key`` equal to ORG_PLATFORM_KEY
(compared in constant time; 503 while it is unset). They do not take the
BFF's secret, and the web app's BFF never passes them on (its allowlist has no
``platform`` path). Errors carry ``detail`` as the contract says.

Approving, rejecting, suspending and reactivating are audited with the Endod
admin's email (``reviewer``); so is every view of a document.

Amendment 1: approval names the version the reviewer saw
(``expected_updated_at``, compared exactly under the lock: every applicant
edit moves ``updated_at``); ``reject`` with ``close`` ends an application for
good (``closed``); list and detail carry ``duplicate_tin`` and
``email_verified``.

Approval also revokes every session of the organisation's admins, in the same
transaction, and audits it (``sessions_revoked``): the applicant's
password-only session ends, and their next sign-in enrols two-step
verification before anything else (app.auth).

Lock order: approve, reject and suspend lock the organisation row first, then
the application (app.onboarding.lock_for_change), exactly as the applicant's
own paths do, so an applicant's save and Endod's decision never deadlock.
"""

from __future__ import annotations

import hmac
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import audit, auth, onboarding
from app.api.application import document_of, send_document
from app.config import get_settings
from app.db import ensure_aware, iso, session_scope, utcnow
from app.errors import ApiError
from app.models import (
    ApplicationStatus, AuditResult, Employee, OrgAdmin, Organisation, OrganisationApplication, OrgStatus,
)

PLATFORM_KEY_REQUIRED = "Authentication required."
NOT_CONFIGURED = "The platform API is not configured."


def check_platform_key(given: Optional[str]) -> Optional[ApiError]:
    """None when ``given`` is the platform key; else the error to answer."""
    key = get_settings().platform_key()
    if key is None:
        return ApiError(503, NOT_CONFIGURED, "NOT_CONFIGURED")
    if not hmac.compare_digest((given or "").encode("utf-8", "surrogateescape"), key.encode()):
        return ApiError(401, PLATFORM_KEY_REQUIRED, "PLATFORM_KEY_REQUIRED")
    return None


def platform_caller(x_platform_key: Optional[str] = Header(default=None)) -> None:
    """Every route here depends on this (app.main checks the same before routing)."""
    error = check_platform_key(x_platform_key)
    if error is not None:
        raise error


router = APIRouter(prefix="/platform", tags=["platform"], dependencies=[Depends(platform_caller)])

_HEX_ID = re.compile(r"^[0-9a-f]{32}$")


def _not_found(what: str = "Application") -> ApiError:
    return ApiError(404, f"{what} not found.", "NOT_FOUND")


class Review(BaseModel):
    #: The Endod admin's email (recorded in the audit log).
    reviewer: str = Field(min_length=3, max_length=254)

    @field_validator("reviewer")
    @classmethod
    def _email_like(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or any(not ch.isprintable() or ch.isspace() for ch in value):
            raise ValueError("give the reviewing admin's email")
        return value


class Approval(Review):
    #: ``updated_at`` of the detail the reviewer saw: approval is refused if it changed since.
    expected_updated_at: AwareDatetime


class Rejection(Review):
    #: Shown to the applicant on their Under review page.
    reason: str = Field(min_length=3, max_length=1000)
    #: True: the application is closed for good (``closed``), never edited or resubmitted.
    close: bool = False

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("give a reason the company can act on")
        return value


def _caller_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


CHANGED = "The application changed since you opened it. Reload it."


def _application(session, application_id: str) -> OrganisationApplication:
    if not _HEX_ID.match(application_id or ""):
        raise _not_found()
    app = onboarding.application_of(session, application_id)
    if app is None:
        raise _not_found()
    return app


def _locked(session, application_id: str):
    """The organisation and its application, locked in the applicant's order."""
    if not _HEX_ID.match(application_id or ""):
        raise _not_found()
    org, app = onboarding.lock_for_change(session, application_id)
    if org is None or app is None:
        raise _not_found()
    return org, app


# --- applications ------------------------------------------------------------------------

@router.get("/applications")
def list_applications(status: Optional[str] = Query(default=None)) -> Dict[str, List[Dict[str, Any]]]:
    if status is not None and status not in ApplicationStatus.ALL:
        raise ApiError(400, f"status must be one of {', '.join(ApplicationStatus.ALL)}.", "VALIDATION_ERROR")
    with session_scope() as session:
        # No worker runs here: expired drafts go when Endod looks (and on applying or signing in).
        onboarding.sweep_expired_drafts(session)
    with session_scope() as session:
        query = select(OrganisationApplication).order_by(
            func.coalesce(OrganisationApplication.submitted_at, OrganisationApplication.created_at).desc(),
            OrganisationApplication.organisation_id)
        if status:
            query = query.where(OrganisationApplication.status == status)
        return {"items": [onboarding.review_item(session, app) for app in session.scalars(query)]}


@router.get("/applications/{application_id}")
def read_application(application_id: str) -> Dict[str, Any]:
    with session_scope() as session:
        return onboarding.review_detail(session, _application(session, application_id))


@router.get("/applications/{application_id}/documents/{kind}")
def read_document(application_id: str, kind: str, request: Request):
    with session_scope() as session:
        app = _application(session, application_id)
        try:
            doc = document_of(session, app.organisation_id, kind)
        except ApiError as exc:
            raise _not_found("Document") from exc
        audit.record(session, audit.APPLICATION_DOCUMENT_VIEWED, AuditResult.SUCCESS,
                     organisation_id=app.organisation_id, ip=_caller_ip(request), target_type="application_document",
                     target_id=doc.id, target_name=doc.filename, detail={"via": "platform", "kind": kind})
    return send_document(doc, inline=False)


@router.post("/applications/{application_id}/approve")
def approve(application_id: str, body: Approval, request: Request) -> Dict[str, str]:
    try:
        with session_scope() as session:
            org, app = _locked(session, application_id)
            # Exactly the version the reviewer saw, checked under the lock.
            if app.status != ApplicationStatus.SUBMITTED or ensure_aware(app.updated_at) != body.expected_updated_at:
                raise ApiError(409, CHANGED, "APPLICATION_CHANGED")
            if session.scalar(select(Organisation.id).where(Organisation.tin == app.tin,
                                                            Organisation.id != org.id)) is not None:
                raise ApiError(409, "Another organisation already has this TIN.", "TIN_TAKEN")
            contact = onboarding.contact_of(session, app)
            now = utcnow()
            org.name, org.tin = app.legal_name, app.tin
            if contact is not None:
                org.contact_name, org.contact_email = contact.name, contact.email
            org.contact_phone = app.contact_phone
            app.status = ApplicationStatus.APPROVED
            app.reviewed_at = app.updated_at = now
            app.reviewed_by = body.reviewer
            app.rejection_reason = None
            audit.record(session, audit.APPLICATION_APPROVED, AuditResult.SUCCESS, organisation_id=org.id,
                         admin_email=body.reviewer, ip=_caller_ip(request), target_type="organisation",
                         target_id=org.id, target_name=org.name,
                         detail={"via": "platform", "reviewer": body.reviewer, "tin": app.tin})
            # Every session of its admins ends now (the applicant's password-only one
            # included): two-step verification is mandatory from here on.
            admin_ids = list(session.scalars(select(OrgAdmin.id).where(OrgAdmin.organisation_id == org.id)))
            revoked = sum(auth.revoke_all(session, admin_id, now) for admin_id in admin_ids)
            audit.record(session, audit.SESSIONS_REVOKED, AuditResult.SUCCESS, organisation_id=org.id,
                         admin_email=body.reviewer, ip=_caller_ip(request), target_type="organisation",
                         target_id=org.id, target_name=org.name,
                         detail={"via": "platform", "reason": "application_approved", "admins": len(admin_ids),
                                 "sessions": revoked})
            session.flush()
    except IntegrityError as exc:
        raise ApiError(409, "Another organisation already has this TIN.", "TIN_TAKEN") from exc
    return {"status": ApplicationStatus.APPROVED}


@router.post("/applications/{application_id}/reject")
def reject(application_id: str, body: Rejection, request: Request) -> Dict[str, str]:
    new_status = ApplicationStatus.CLOSED if body.close else ApplicationStatus.REJECTED
    with session_scope() as session:
        _org, app = _locked(session, application_id)
        if app.status != ApplicationStatus.SUBMITTED:
            raise ApiError(409, f"Only a submitted application can be rejected (this one is {app.status}).",
                           "WRONG_STATUS")
        now = utcnow()
        app.status = new_status
        app.rejection_reason = body.reason
        app.reviewed_at = app.updated_at = now
        app.reviewed_by = body.reviewer
        audit.record(session, audit.APPLICATION_CLOSED if body.close else audit.APPLICATION_REJECTED,
                     AuditResult.SUCCESS, organisation_id=app.organisation_id,
                     admin_email=body.reviewer, ip=_caller_ip(request), target_type="organisation",
                     target_id=app.organisation_id, target_name=app.legal_name,
                     detail={"via": "platform", "reviewer": body.reviewer, "reason": body.reason,
                             "close": body.close})
    return {"status": new_status}


# --- organisations -------------------------------------------------------------------------

def _approved():
    """Organisations that are in business: no application (CLI-made) or an approved one."""
    return (select(Organisation)
            .outerjoin(OrganisationApplication, OrganisationApplication.organisation_id == Organisation.id)
            .where((OrganisationApplication.organisation_id.is_(None))
                   | (OrganisationApplication.status == ApplicationStatus.APPROVED)))


@router.get("/organisations")
def list_organisations() -> Dict[str, List[Dict[str, Any]]]:
    with session_scope() as session:
        orgs = list(session.scalars(_approved().order_by(Organisation.created_at.desc(), Organisation.id)))
        employees = dict(session.execute(select(Employee.organisation_id, func.count())
                                         .where(Employee.active.is_(True)).group_by(Employee.organisation_id)).all())
        admins = dict(session.execute(select(OrgAdmin.organisation_id, func.count())
                                      .where(OrgAdmin.active.is_(True)).group_by(OrgAdmin.organisation_id)).all())
        return {"items": [{
            "id": o.id, "name": o.name, "tin": o.tin, "status": o.status, "created_at": iso(o.created_at),
            "employees": int(employees.get(o.id, 0)), "admins": int(admins.get(o.id, 0)),
        } for o in orgs]}


def _set_status(organisation_id: str, body: Review, request: Request, new_status: str) -> Dict[str, str]:
    if not _HEX_ID.match(organisation_id or ""):
        raise _not_found("Organisation")
    with session_scope() as session:
        if session.scalar(_approved().where(Organisation.id == organisation_id)) is None:
            raise _not_found("Organisation")
        # The organisation row is the first (and here the only) lock, as everywhere.
        org, _app = onboarding.lock_for_change(session, organisation_id)
        changed = org.status != new_status
        org.status = new_status
        now = utcnow()
        if new_status == OrgStatus.SUSPENDED:
            # Signed out now; sign-in is refused with the usual generic message.
            for admin_id in session.scalars(select(OrgAdmin.id).where(OrgAdmin.organisation_id == org.id)):
                auth.revoke_all(session, admin_id, now)
        audit.record(session, audit.ORG_SUSPENDED if new_status == OrgStatus.SUSPENDED else audit.ORG_REACTIVATED,
                     AuditResult.SUCCESS, organisation_id=org.id, admin_email=body.reviewer, ip=_caller_ip(request),
                     target_type="organisation", target_id=org.id, target_name=org.name,
                     detail={"via": "platform", "reviewer": body.reviewer, "changed": changed})
    return {"status": new_status}


@router.post("/organisations/{organisation_id}/suspend")
def suspend(organisation_id: str, body: Review, request: Request) -> Dict[str, str]:
    return _set_status(organisation_id, body, request, OrgStatus.SUSPENDED)


@router.post("/organisations/{organisation_id}/reactivate")
def reactivate(organisation_id: str, body: Review, request: Request) -> Dict[str, str]:
    return _set_status(organisation_id, body, request, OrgStatus.ACTIVE)
