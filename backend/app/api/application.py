"""`/application`: a company's own application (app.onboarding).

* ``POST /application/start`` (public): the organisation, its first admin
  (the contact) and an enrolment session: TOTP comes before anything else.
  Limited per address (ORG_APPLICATIONS_PER_IP per window), and refused from
  an address the sign-in limit has blocked.
* ``GET /application``: the application, what is missing, where to resume;
  also the Under review page (status, Endod's reason after a rejection).
* ``PUT /application/contact | company``: save a step (while a draft, or
  after Endod sent it back).
* ``POST /application/documents/{kind}``: upload or replace a document (the
  file is the body, its name in X-Filename); ``GET`` the same path views it.
* ``POST /application/submit``: send it to Endod.

These are the only routes (with sign-in and sign-out) that the admins of an
organisation that is not approved can use (app.auth.current_admin).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import unquote

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app import audit, auth, files, onboarding, security, validation
from app.api.common import checked
from app.auth import Principal, signed_in_admin
from app.config import get_settings
from app.db import new_id, session_scope, utcnow
from app.errors import ApiError
from app.models import (
    ApplicationDocument, ApplicationStatus, AuditResult, BenefitPolicy, DocumentKind, OrgAdmin, Organisation,
    OrganisationApplication, Sector,
)
from app.policy import DEFAULT_ANNUAL_LIMIT_SANTIM
from app.tenancy import not_found

router = APIRouter(prefix="/application", tags=["application"])

EMAIL_REFUSED = "This email cannot be used for a new application. If it is yours, sign in instead."
TOO_MANY_APPLICATIONS = "Too many applications from this address. Try again later."


def _email(value: str, field: str = "Email") -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ApiError(400, f"{field} is not a valid email address.", "VALIDATION_ERROR") from exc


def _ua(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


# --- step 1: the account -----------------------------------------------------------------

class StartRequest(BaseModel):
    legal_name: str = Field(max_length=200)
    full_name: str = Field(max_length=120)
    title: str = Field(max_length=80)
    phone: str = Field(max_length=32)
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.post("/start")
def start(body: StartRequest, request: Request, ip: str = Depends(auth.client_ip)) -> Dict[str, Any]:
    legal_name = checked(validation.text, body.legal_name, "Company legal name", min_len=2, max_len=200)
    full_name = checked(validation.text, body.full_name, "Full name", min_len=2, max_len=120)
    title = checked(validation.text, body.title, "Title", min_len=2, max_len=80)
    phone = checked(validation.phone, body.phone)
    email = _email(body.email)
    problem = security.password_problem(body.password, email)
    if problem:
        raise ApiError(400, problem, "WEAK_PASSWORD")
    # Hashed before anything is looked up: a taken email costs the same.
    password_hash = security.hash_password(body.password)
    settings = get_settings()
    now = utcnow()
    failure: Optional[ApiError] = None
    try:
        with session_scope() as session:
            if auth.ip_blocked(session, ip, now, settings) or auth.application_limited(session, ip, now, settings):
                audit.record(session, audit.APPLICATION_STARTED, AuditResult.FAILURE, ip=ip,
                             admin_email=security.email_fingerprint(email), detail={"reason": "address_rate_limited"})
                failure = ApiError(429, TOO_MANY_APPLICATIONS, "RATE_LIMITED")
            elif session.scalar(select(OrgAdmin.id).where(OrgAdmin.email == email)) is not None:
                auth.note_ip_failure(session, ip, now)
                audit.record(session, audit.APPLICATION_STARTED, AuditResult.FAILURE, ip=ip,
                             admin_email=security.email_fingerprint(email), detail={"reason": "email_taken"})
                failure = ApiError(409, EMAIL_REFUSED, "APPLICATION_REFUSED")
            else:
                org = Organisation(name=legal_name, tin=onboarding.placeholder_tin(), contact_name=full_name,
                                   contact_email=email, contact_phone=phone)
                session.add(org)
                session.flush()
                admin = OrgAdmin(organisation_id=org.id, email=email, name=full_name, password_hash=password_hash)
                session.add(admin)
                session.flush()
                session.add(OrganisationApplication(
                    organisation_id=org.id, status=ApplicationStatus.DRAFT, legal_name=legal_name,
                    contact_admin_id=admin.id, contact_title=title, contact_phone=phone, created_at=now,
                    updated_at=now))
                # The policy every organisation starts with (as app.cli create-org).
                session.add(BenefitPolicy(organisation_id=org.id, employee_id=None,
                                          annual_limit_santim=DEFAULT_ANNUAL_LIMIT_SANTIM, copay_percent=0,
                                          dependants_covered=True, excluded_medicines="[]",
                                          year_start_month=1, year_start_day=1))
                auth.note_application(session, ip, now)
                audit.record(session, audit.APPLICATION_STARTED, AuditResult.SUCCESS, organisation_id=org.id,
                             admin_id=admin.id, admin_email=email, ip=ip, target_type="organisation",
                             target_id=org.id, target_name=legal_name)
                opened = auth.open_enrolment(session, admin, now, ip, _ua(request))
                return auth.opened_payload(opened)
    except IntegrityError as exc:
        # The same email, taken at the same moment.
        raise ApiError(409, EMAIL_REFUSED, "APPLICATION_REFUSED") from exc
    raise failure


# --- reading -------------------------------------------------------------------------------

def _organisation(session, principal: Principal, lock: bool = False) -> Organisation:
    query = select(Organisation).where(Organisation.id == principal.organisation_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


@router.get("")
def read(principal: Principal = Depends(signed_in_admin)) -> Dict[str, Any]:
    with session_scope() as session:
        return onboarding.application_payload(session, _organisation(session, principal))


# --- the steps -----------------------------------------------------------------------------

class ContactStep(BaseModel):
    full_name: str = Field(max_length=120)
    title: str = Field(max_length=80)
    phone: str = Field(max_length=32)


class CompanyStep(BaseModel):
    legal_name: str = Field(max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    tin: str = Field(max_length=20)
    business_license_number: str = Field(max_length=60)
    sector: str = Field(max_length=32)
    employee_count: int = Field(ge=1, le=10_000_000)
    city: str = Field(max_length=100)
    address: str = Field(max_length=200)
    phone: str = Field(max_length=32)
    email: str = Field(max_length=254)


def _save(principal: Principal, step: str, apply) -> Dict[str, Any]:
    with session_scope() as session:
        org = _organisation(session, principal, lock=True)
        app = onboarding.require_editable(onboarding.application_of(session, org.id, lock=True))
        apply(session, org, app)
        app.updated_at = utcnow()
        audit.by(session, principal, audit.APPLICATION_SAVED, target_type="organisation", target_id=org.id,
                 detail={"step": step})
        session.flush()
        return onboarding.application_payload(session, org)


@router.put("/contact")
def save_contact(body: ContactStep, principal: Principal = Depends(signed_in_admin)) -> Dict[str, Any]:
    full_name = checked(validation.text, body.full_name, "Full name", min_len=2, max_len=120)
    title = checked(validation.text, body.title, "Title", min_len=2, max_len=80)
    phone = checked(validation.phone, body.phone)

    def apply(session, org: Organisation, app: OrganisationApplication) -> None:
        contact = onboarding.contact_of(session, app)
        if contact is not None:
            contact.name = full_name
        app.contact_title, app.contact_phone = title, phone
        org.contact_name, org.contact_phone = full_name, phone

    return _save(principal, "contact", apply)


@router.put("/company")
def save_company(body: CompanyStep, principal: Principal = Depends(signed_in_admin)) -> Dict[str, Any]:
    legal_name = checked(validation.text, body.legal_name, "Legal name", min_len=2, max_len=200)
    trade_name = checked(validation.optional_text, body.trade_name, "Trade name", max_len=200)
    tin = checked(validation.tin, body.tin)
    licence = checked(validation.text, body.business_license_number, "Business license number", min_len=2, max_len=60)
    if body.sector not in Sector.ALL:
        raise ApiError(400, f"Sector must be one of {', '.join(Sector.ALL)}.", "VALIDATION_ERROR")
    city = checked(validation.text, body.city, "City", min_len=2, max_len=100)
    address = checked(validation.text, body.address, "Address", min_len=3, max_len=200)
    phone = checked(validation.ethiopian_number, body.phone)
    email = _email(body.email, "Company email")
    settings = get_settings()
    now = utcnow()
    with session_scope() as session:
        # Probing TINs costs like guessing passwords: the per-address limit applies.
        if auth.ip_blocked(session, principal.ip, now, settings):
            raise ApiError(429, auth.TOO_MANY, "RATE_LIMITED")
        if onboarding.tin_taken(session, tin, principal.organisation_id):
            auth.note_ip_failure(session, principal.ip, now)
            audit.by(session, principal, audit.APPLICATION_SAVED, AuditResult.FAILURE, target_type="organisation",
                     target_id=principal.organisation_id, detail={"step": "company", "reason": "tin_taken"})
            refused = True
        else:
            refused = False
    if refused:
        raise ApiError(409, onboarding.REFUSED, "APPLICATION_REFUSED")

    def apply(_session, org: Organisation, app: OrganisationApplication) -> None:
        app.legal_name, app.trade_name, app.tin = legal_name, trade_name, tin
        app.business_license_number, app.sector, app.employee_count = licence, body.sector, body.employee_count
        app.city, app.address, app.phone, app.email = city, address, phone, email
        org.name = legal_name

    return _save(principal, "company", apply)


# --- documents -----------------------------------------------------------------------------

@router.post("/documents/{kind}", status_code=201)
async def upload_document(kind: str, request: Request,
                          x_filename: Optional[str] = Header(default=None, max_length=600),
                          content_length: Optional[int] = Header(default=None),
                          principal: Principal = Depends(signed_in_admin)) -> Dict[str, Any]:
    """One document, as the request body. Uploading a kind again replaces it."""
    if kind not in DocumentKind.ALL:
        raise not_found()
    if content_length is not None and content_length > onboarding.MAX_DOCUMENT_BYTES:
        raise ApiError(413, "A document can be at most 10 MB.", "FILE_TOO_LARGE")
    org_id = principal.organisation_id

    def check() -> None:
        with session_scope() as session:
            onboarding.require_editable(onboarding.application_of(session, org_id))

    await run_in_threadpool(check)
    file_id = new_id()
    try:
        size, sha256, content_type = await files.store_stream(
            request.stream(), org_id, file_id, max_bytes=onboarding.MAX_DOCUMENT_BYTES, what="A document")
        filename = files.safe_filename(unquote(x_filename or ""), content_type)
    except files.FileRejected as exc:
        files.delete(org_id, file_id)
        code = {413: "FILE_TOO_LARGE", 415: "FILE_TYPE"}.get(exc.status_code, "FILE_REJECTED")
        raise ApiError(exc.status_code, str(exc), code) from exc

    def save() -> tuple:
        with session_scope() as session:
            org = _organisation(session, principal, lock=True)
            # Again under the lock: the application may have been submitted meanwhile.
            app = onboarding.require_editable(onboarding.application_of(session, org.id, lock=True))
            old = session.scalar(select(ApplicationDocument).where(
                ApplicationDocument.organisation_id == org.id, ApplicationDocument.kind == kind))
            replaced = old.id if old is not None else None
            if old is not None:
                session.delete(old)
                session.flush()  # the old row goes before the new one takes its kind
            session.add(ApplicationDocument(id=file_id, organisation_id=org.id, kind=kind, filename=filename,
                                            content_type=content_type, size=size, sha256=sha256,
                                            uploaded_by=principal.admin_id))
            app.updated_at = utcnow()
            audit.by(session, principal, audit.APPLICATION_DOCUMENT_UPLOADED, target_type="application_document",
                     target_id=file_id, target_name=filename,
                     detail={"kind": kind, "size": size, "sha256": sha256, "replaced": bool(replaced)})
            session.flush()
            return onboarding.application_payload(session, org), replaced

    try:
        payload, replaced = await run_in_threadpool(save)
    except IntegrityError as exc:
        files.delete(org_id, file_id)
        raise ApiError(409, "The document changed meanwhile; upload it again.", "CONFLICT") from exc
    except BaseException:
        files.delete(org_id, file_id)
        raise
    if replaced:
        files.delete(org_id, replaced)
    return payload


def send_document(doc: ApplicationDocument, inline: bool) -> FileResponse:
    """A stored document, streamed: its stored type, a safe disposition, never sniffed or cached."""
    try:
        path = files.path_for(doc.organisation_id, doc.id)
    except files.FileRejected as exc:
        raise not_found() from exc
    if not path.is_file():
        raise not_found()
    return FileResponse(path, media_type=doc.content_type, headers={
        "Content-Disposition": files.content_disposition(doc.filename, inline=inline),
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "X-Sha256": doc.sha256,
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
                                   "frame-ancestors 'self'" if doc.content_type != "application/pdf"
                                   else "frame-ancestors 'self'",
    })


def document_of(session, organisation_id: str, kind: str) -> ApplicationDocument:
    if kind not in DocumentKind.ALL:
        raise not_found()
    doc = session.scalar(select(ApplicationDocument).where(
        ApplicationDocument.organisation_id == organisation_id, ApplicationDocument.kind == kind))
    if doc is None:
        raise not_found()
    return doc


@router.get("/documents/{kind}")
def read_document(kind: str, principal: Principal = Depends(signed_in_admin)):
    """The organisation's own document (the organisation comes from the session)."""
    with session_scope() as session:
        doc = document_of(session, principal.organisation_id, kind)
        session.expunge(doc)
    return send_document(doc, inline=True)


# --- submitting ----------------------------------------------------------------------------

@router.post("/submit")
def submit(principal: Principal = Depends(signed_in_admin)) -> Dict[str, Any]:
    refused = False
    try:
        with session_scope() as session:
            org = _organisation(session, principal, lock=True)
            app = onboarding.require_editable(onboarding.application_of(session, org.id, lock=True))
            gaps = onboarding.missing(session, app)
            unfinished = [onboarding.STEP_NAMES[step] for step in onboarding.STEPS if gaps[step]]
            if unfinished:
                raise ApiError(400, f"Finish these steps first: {', '.join(unfinished)}.", "INCOMPLETE")
            if onboarding.tin_taken(session, app.tin, org.id):
                audit.by(session, principal, audit.APPLICATION_SUBMITTED, AuditResult.FAILURE,
                         target_type="organisation", target_id=org.id, detail={"reason": "tin_taken"})
                refused = True
            else:
                now = utcnow()
                resubmitted = app.status == ApplicationStatus.REJECTED
                app.status = ApplicationStatus.SUBMITTED
                app.submitted_at = app.updated_at = now
                app.rejection_reason = None
                app.reviewed_at = app.reviewed_by = None
                audit.by(session, principal, audit.APPLICATION_SUBMITTED, target_type="organisation",
                         target_id=org.id, target_name=app.legal_name, detail={"resubmitted": resubmitted})
                # The partial unique index settles two submissions of one TIN at once.
                session.flush()
                return onboarding.application_payload(session, org)
    except IntegrityError as exc:
        raise ApiError(409, onboarding.REFUSED, "APPLICATION_REFUSED") from exc
    if refused:
        raise ApiError(409, onboarding.REFUSED, "APPLICATION_REFUSED")
    raise AssertionError("unreachable")
