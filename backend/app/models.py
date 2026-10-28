"""Tables of the organisation (employer) portal.

Every business row carries ``organisation_id``, and every query the API
makes filters on the signed-in admin's organisation (app.tenancy): an admin
never reads or changes another organisation's rows. Within an organisation, a
row refers to another (a claim to its employee, ...) by a composite foreign
key on (organisation_id, id), so the database itself refuses a reference to
another organisation's row (``same_org``).

Money is always an integer number of santim (1 ETB = 100 santim); there are
no floats anywhere.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String,
    Text, UniqueConstraint, text, true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, new_id, utcnow


class SessionStage:
    """How far a sign-in has got. Only FULL sessions reach the portal API."""

    #: Password checked; a TOTP (or recovery) code is next.
    TOTP = "totp"
    #: Password checked (or set through a setup link); the admin must enrol
    #: an authenticator before anything else.
    ENROLL = "enroll"
    #: Signed in.
    FULL = "full"
    #: A company's applicant signed in with the password only, while the
    #: organisation is not approved: reaches the application routes (and the
    #: sign-in steps and sign-out), nothing else. Approval revokes it; two-step
    #: verification is enrolled at the next sign-in.
    APPLICANT = "applicant"
    ALL = (TOTP, ENROLL, FULL, APPLICANT)


class OrgStatus:
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ALL = (ACTIVE, SUSPENDED)


class ApplicationStatus:
    """A company's own application (docs/company-onboarding.md). An organisation
    without an application (made by the CLI, or before applications existed)
    counts as approved."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    #: Endod refused it for good: never edited or resubmitted (reject with ``close``).
    CLOSED = "closed"
    ALL = (DRAFT, SUBMITTED, APPROVED, REJECTED, CLOSED)
    #: The applicant may change the application (a rejected one is fixed and resubmitted).
    EDITABLE = (DRAFT, REJECTED)


class Sector:
    ALL = ("government", "ngo", "manufacturing", "services", "finance", "telecom", "health", "education",
           "retail", "transport", "agriculture", "other")


class DocumentKind:
    TRADE_LICENSE = "trade_license"
    TIN_CERTIFICATE = "tin_certificate"
    AUTHORIZATION_LETTER = "authorization_letter"
    ALL = (TRADE_LICENSE, TIN_CERTIFICATE, AUTHORIZATION_LETTER)
    LABELS = {TRADE_LICENSE: "Trade license", TIN_CERTIFICATE: "TIN certificate",
              AUTHORIZATION_LETTER: "Authorization letter"}


class PayoutMethod:
    """How an employee is paid back. TenaCare moves no money: it records the
    batch and exports the file the organisation uploads to its bank or Telebirr."""

    CBE = "cbe"
    AWASH = "awash"
    DASHEN = "dashen"
    TELEBIRR = "telebirr"
    ALL = (CBE, AWASH, DASHEN, TELEBIRR)
    LABELS = {CBE: "Commercial Bank of Ethiopia", AWASH: "Awash Bank", DASHEN: "Dashen Bank", TELEBIRR: "Telebirr"}


class ClaimStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    ALL = (PENDING, APPROVED, REJECTED, PAID)


class ClaimSource:
    #: Entered by HR from a receipt the employee brought in.
    MANUAL = "manual"
    #: Reserved: claims created from Endod pharmacy dispensing (app.claims_intake).
    PHARMACY = "pharmacy"
    ALL = (MANUAL, PHARMACY)


class BatchStatus:
    OPEN = "open"
    PAID = "paid"
    ALL = (OPEN, PAID)


class Relationship:
    ALL = ("spouse", "child", "parent", "other")


def same_org(column: str, parent: str, name: str, **kw) -> ForeignKeyConstraint:
    """(organisation_id, ``column``) -> ``parent``(organisation_id, id): the
    parent row is of the same organisation (migration 0005)."""
    return ForeignKeyConstraint(["organisation_id", column], [f"{parent}.organisation_id", f"{parent}.id"],
                                name=name, **kw)


def org_and_id(table: str) -> UniqueConstraint:
    """What ``same_org`` references: (organisation_id, id) of ``table``."""
    return UniqueConstraint("organisation_id", "id", name=f"uq_{table}_org_id")


# --- organisations and their admins ----------------------------------------------------------

class Organisation(Base):
    """An employer. Created by Endod with ``python -m app.cli create-org``, or
    by a company applying itself (then with an OrganisationApplication, and
    locked until Endod approves it; until then ``tin`` is a placeholder and the
    TIN applied for is on the application)."""

    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    #: Ethiopian taxpayer identification number (10 digits).
    tin: Mapped[str] = mapped_column(String(10), unique=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=OrgStatus.ACTIVE)
    #: Payout settings: the account the organisation pays from (shown in the
    #: exported files) and the methods it pays by (comma-separated).
    payout_debit_account: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    payout_methods: Mapped[str] = mapped_column(String(64), default=",".join(PayoutMethod.ALL))
    #: Per-organisation running numbers (CLM-000001, BATCH-0001).
    next_claim_number: Mapped[int] = mapped_column(Integer, default=1)
    next_batch_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (CheckConstraint("status IN ('active', 'suspended')", name="status"),)


class OrgAdmin(Base):
    """An HR / benefits admin of exactly one organisation."""

    __tablename__ = "org_admins"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    #: argon2id; None until the admin sets one through a setup link.
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: The TOTP secret, encrypted (app.security.seal); None until enrolled.
    totp_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: A secret shown during enrolment, kept until the admin confirms a code.
    totp_pending_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: The last TOTP time step accepted: each code works once.
    totp_last_step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    totp_enrolled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Failed sign-in steps against this account from any address (app.auth backoff).
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Until then, the password step never says whether a password is right.
    backoff_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Wrong TOTP / recovery codes against this account from any address
    #: (the account-wide code limit in app.auth), and until when code attempts wait.
    code_failures: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    code_last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    code_backoff_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (org_and_id("org_admins"),)


class OrganisationApplication(Base):
    """A company's application to use TenaCare, filled in by its first admin
    (the contact) and reviewed by Endod through the platform API. One per
    organisation; organisations without one are approved."""

    __tablename__ = "organisation_applications"

    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default=ApplicationStatus.DRAFT)
    legal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    trade_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    #: The TIN applied for (10 digits); copied to the organisation on approval. Not
    #: unique: only an approved organisation holds a TIN (organisations.tin); other
    #: applications with it are allowed and flagged to Endod (``duplicate_tin``).
    tin: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    business_license_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    #: The company's number (E.164; a landline or a mobile).
    phone: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    #: The contact (the first admin): their title and mobile; name and email are on the admin.
    contact_admin_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    contact_title: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The Endod admin's email (also in the audit log).
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    #: Why Endod sent it back (shown to the applicant).
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'closed')", name="status"),
        CheckConstraint("employee_count IS NULL OR employee_count >= 1", name="employee_count_positive"),
        same_org("contact_admin_id", "org_admins", "fk_organisation_applications_contact_same_org"),
    )


class ApplicationDocument(Base):
    """A document of an application, on the files volume at
    ``<ORG_RECEIPTS_DIR>/<organisation_id>/<id>`` (app.files), one per kind."""

    __tablename__ = "application_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("organisation_id", "kind", name="uq_application_documents_org_kind"),)


class LoginThrottle(Base):
    """Failed sign-in steps against one account from one address; enough of
    them lock that pair (only that address, only that account) for a while."""

    __tablename__ = "login_throttles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    admin_id: Mapped[str] = mapped_column(ForeignKey("org_admins.id", ondelete="CASCADE"))
    ip: Mapped[str] = mapped_column(String(64))
    failures: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("admin_id", "ip", name="uq_login_throttles_admin_ip"),)


class SetupToken(Base):
    """A one-time link to set a password and enrol TOTP (from the CLI)."""

    __tablename__ = "setup_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    admin_id: Mapped[str] = mapped_column(ForeignKey("org_admins.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminSession(Base):
    """A server-side session; the browser holds only its random token (in an
    httpOnly cookie set by the web app), stored here as a keyed hash."""

    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    admin_id: Mapped[str] = mapped_column(ForeignKey("org_admins.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    stage: Mapped[str] = mapped_column(String(16))
    #: False for a stand-in session opened during backoff for a wrong
    #: password: it looks the same, and no code ever completes it.
    password_ok: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    #: The absolute end (12 hours after sign-in; minutes for a half-finished one).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    #: The last fresh TOTP given for a sensitive action.
    reauth_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    admin_id: Mapped[str] = mapped_column(ForeignKey("org_admins.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthFailure(Base):
    """A failed sign-in step, by address (the per-address rate limit)."""

    __tablename__ = "auth_failures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    ip: Mapped[str] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_auth_failures_ip_at", "ip", "at"),)


class AuditResult:
    SUCCESS = "success"
    FAILURE = "failure"
    ALL = (SUCCESS, FAILURE)


class AuditEvent(Base):
    """Append-only: who did what, when, from where, to what, and how it went.
    The API's database role may only read and insert here."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    #: Plain ids (no foreign keys): the log outlives what it describes.
    organisation_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    admin_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    #: The email as given (kept for failed sign-ins and after an admin is gone).
    admin_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    result: Mapped[str] = mapped_column(String(16))
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    #: JSON (a reason, amounts in santim, ...).
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# --- employees and policies ------------------------------------------------------------------

class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    employee_number: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    #: E.164, Ethiopian mobile: +2519XXXXXXXX or +2517XXXXXXXX.
    phone: Mapped[str] = mapped_column(String(13))
    department: Mapped[str] = mapped_column(String(80))
    #: The Endod health card id (DE + 6 digits), when the employee has one.
    endod_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Where reimbursements go (app.models.PayoutMethod), and the account
    #: number (or, for Telebirr, the phone number).
    payout_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    payout_account: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organisation_id", "employee_number", name="uq_employees_org_number"),
        UniqueConstraint("organisation_id", "endod_id", name="uq_employees_org_endod_id"),
        org_and_id("employees"),
    )


class Dependant(Base):
    __tablename__ = "dependants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    employee_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    relationship: Mapped[str] = mapped_column(String(16))
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        same_org("employee_id", "employees", "fk_dependants_employee_same_org", ondelete="CASCADE"),
        org_and_id("dependants"),
    )


class BenefitPolicy(Base):
    """The organisation's policy (``employee_id`` NULL; exactly one), or an
    override for one employee (replaces the limit, co-pay, dependant cover
    and exclusions; the policy year always comes from the organisation's)."""

    __tablename__ = "benefit_policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    annual_limit_santim: Mapped[int] = mapped_column(BigInteger)
    #: Whole percent (0-100) of each claim the employee bears.
    copay_percent: Mapped[int] = mapped_column(Integer, default=0)
    dependants_covered: Mapped[bool] = mapped_column(Boolean, default=True)
    #: JSON array of medicine names (matched as whole words, any case).
    excluded_medicines: Mapped[str] = mapped_column(Text, default="[]")
    #: The policy year starts on this day every year (e.g. 8 July for the
    #: Ethiopian fiscal year).
    year_start_month: Mapped[int] = mapped_column(Integer, default=1)
    year_start_day: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("organisation_id", "employee_id", name="uq_benefit_policies_org_employee"),
        # One organisation-wide policy (employee_id NULL) per organisation.
        Index("uq_benefit_policies_org_default", "organisation_id", unique=True,
              postgresql_where=text("employee_id IS NULL"), sqlite_where=text("employee_id IS NULL")),
        CheckConstraint("annual_limit_santim >= 0", name="limit_not_negative"),
        CheckConstraint("copay_percent >= 0 AND copay_percent <= 100", name="copay_range"),
        CheckConstraint("year_start_month >= 1 AND year_start_month <= 12", name="year_start_month"),
        CheckConstraint("year_start_day >= 1 AND year_start_day <= 31", name="year_start_day"),
        same_org("employee_id", "employees", "fk_benefit_policies_employee_same_org", ondelete="CASCADE"),
    )


# --- claims and payouts ----------------------------------------------------------------------

class ReceiptFile(Base):
    """A receipt photo or scan, on the receipts volume at
    ``<ORG_RECEIPTS_DIR>/<organisation_id>/<id>`` (app.files)."""

    __tablename__ = "receipt_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (org_and_id("receipt_files"),)


class PaymentBatch(Base):
    """Approved claims grouped for one payout method. TenaCare exports the
    file; the organisation pays through its bank; an admin then marks the
    batch paid with the bank's reference. A paid batch never changes."""

    __tablename__ = "payment_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=BatchStatus.OPEN)
    total_santim: Mapped[int] = mapped_column(BigInteger, default=0)
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    #: When the payout file was first downloaded, and by whom: from then on the
    #: batch may have been paid at the bank, so it can no longer be cancelled.
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_payment_batches_org_number"),
        CheckConstraint("status IN ('open', 'paid')", name="status"),
        CheckConstraint("total_santim >= 0", name="total_not_negative"),
        org_and_id("payment_batches"),
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    #: Shown as CLM-000123; per organisation.
    number: Mapped[int] = mapped_column(Integer)
    employee_id: Mapped[str] = mapped_column(String(32), index=True)
    #: Set when the medicine was for a dependant of the employee.
    dependant_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    #: app.models.ClaimSource; ``external_ref`` is the dispensing record's id
    #: for claims that will come from Endod pharmacies.
    source: Mapped[str] = mapped_column(String(16), default=ClaimSource.MANUAL)
    external_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pharmacy_name: Mapped[str] = mapped_column(String(160))
    #: Digits only (10).
    pharmacy_tin: Mapped[str] = mapped_column(String(10))
    #: Normalised (upper case, no spaces): with the TIN, what makes a receipt unique.
    receipt_number: Mapped[str] = mapped_column(String(40))
    receipt_date: Mapped[date] = mapped_column(Date)
    total_santim: Mapped[int] = mapped_column(BigInteger)
    #: Set on approval: what the employee bears, and what the organisation pays back.
    copay_santim: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    approved_santim: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ClaimStatus.PENDING, index=True)
    #: Why it was rejected (shown to HR; told to the employee).
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    receipt_file_id: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    #: The employee's account when the claim was batched (the exported file
    #: and a paid batch keep it, whatever changes on the employee later).
    payout_account: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_claims_org_number"),
        # A receipt is paid back at most once: never two approved or paid
        # claims for the same pharmacy TIN and receipt number.
        Index("uq_claims_receipt_once", "organisation_id", "pharmacy_tin", "receipt_number", unique=True,
              postgresql_where=text("status IN ('approved', 'paid')"),
              sqlite_where=text("status IN ('approved', 'paid')")),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'paid')", name="status"),
        CheckConstraint("total_santim > 0", name="total_positive"),
        CheckConstraint("approved_santim IS NULL OR approved_santim >= 0", name="approved_not_negative"),
        CheckConstraint("copay_santim IS NULL OR copay_santim >= 0", name="copay_not_negative"),
        same_org("employee_id", "employees", "fk_claims_employee_same_org"),
        same_org("dependant_id", "dependants", "fk_claims_dependant_same_org"),
        same_org("receipt_file_id", "receipt_files", "fk_claims_receipt_file_same_org"),
        same_org("batch_id", "payment_batches", "fk_claims_batch_same_org"),
    )


class ClaimItem(Base):
    __tablename__ = "claim_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    medicine: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_santim: Mapped[int] = mapped_column(BigInteger)
    line_total_santim: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_santim > 0", name="price_positive"),
        CheckConstraint("line_total_santim = quantity * unit_price_santim", name="line_total"),
    )


# --- the integration API for companies' own systems (app/integrations, docs/integrations.md) ----

class IntegrationMode:
    #: Changes real data.
    LIVE = "live"
    #: Checks everything and answers what would happen; stores nothing.
    TEST = "test"
    ALL = (LIVE, TEST)


class IntegrationAuth:
    #: A random secret (only its argon2id hash is kept).
    SECRET = "client_secret"
    #: A signed client assertion, checked against the client's public keys.
    PRIVATE_KEY_JWT = "private_key_jwt"
    ALL = (SECRET, PRIVATE_KEY_JWT)


class DeliveryStatus:
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    ALL = (PENDING, DELIVERED, FAILED)


class IntegrationClient(Base):
    """A company system connected to the integration API (OAuth 2.0 client
    credentials). Never deleted: disconnecting sets ``revoked_at``."""

    __tablename__ = "integration_clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    #: Public (the OAuth client_id): endod_live_... or endod_test_...
    client_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    #: Granted scopes, space-separated (app/integrations/scopes.py).
    scopes: Mapped[str] = mapped_column(String(400))
    mode: Mapped[str] = mapped_column(String(4), default=IntegrationMode.LIVE)
    auth_method: Mapped[str] = mapped_column(String(20), default=IntegrationAuth.SECRET)
    #: argon2id hash of the client secret (client_secret only).
    secret_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: The client's public keys (a JWKS; private_key_jwt only). Public: not encrypted.
    jwks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Addresses it may call from (comma-separated CIDRs; empty: anywhere).
    allowed_cidrs: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    #: Where events go (https only), and their signing secret (app.security.seal, "webhook").
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Plain id of the admin who connected it (kept for the record, like the other *_by columns).
    created_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When the credentials last changed (secret rotated, keys set): older tokens are refused.
    credentials_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("mode IN ('live', 'test')", name="mode"),
        CheckConstraint("auth_method IN ('client_secret', 'private_key_jwt')", name="auth_method"),
        org_and_id("integration_clients"),
    )


class IntegrationAssertion(Base):
    """A client assertion's ``jti``, kept until the assertion expires: each is used once."""

    __tablename__ = "integration_assertions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    client_pk: Mapped[str] = mapped_column(String(32))
    jti: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("client_pk", "jti", name="uq_integration_assertions_client_jti"),
        same_org("client_pk", "integration_clients", "fk_integration_assertions_client_same_org", ondelete="CASCADE"),
    )


class IntegrationRequest(Base):
    """One call to the integration API: never a body or a query string. Kept 30 days."""

    __tablename__ = "integration_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    client_pk: Mapped[str] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(8))
    #: The path only.
    path: Mapped[str] = mapped_column(String(300))
    status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_integration_requests_client_at", "client_pk", "at"),
        same_org("client_pk", "integration_clients", "fk_integration_requests_client_same_org", ondelete="CASCADE"),
    )


class IntegrationIdempotency(Base):
    """The answer to a request sent with an Idempotency-Key, replayed when the
    same key comes again (for 24 hours)."""

    __tablename__ = "integration_idempotency"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    client_pk: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(255))
    #: sha256 of the method, path and body: the same key with another request is refused.
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("client_pk", "key", name="uq_integration_idempotency_client_key"),
        same_org("client_pk", "integration_clients", "fk_integration_idempotency_client_same_org",
                 ondelete="CASCADE"),
    )


class IntegrationPayoutChange(Base):
    """A payout method or account set by a connected system
    (employees.payout.write). The employee's claims are kept out of payout
    batches until ``hold_until`` (24 hours), unless an admin confirms the change
    in the portal first (app.payout_holds). Accounts are kept masked only (the
    employee row holds the real one)."""

    __tablename__ = "integration_payout_changes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    employee_id: Mapped[str] = mapped_column(String(32))
    client_pk: Mapped[str] = mapped_column(String(32))
    before_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    before_account: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    after_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    after_account: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    hold_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Plain id of the admin who confirmed it (in the portal).
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_integration_payout_changes_employee", "employee_id", "hold_until"),
        same_org("employee_id", "employees", "fk_integration_payout_changes_employee_same_org", ondelete="CASCADE"),
        same_org("client_pk", "integration_clients", "fk_integration_payout_changes_client_same_org",
                 ondelete="CASCADE"),
    )


class WebhookDelivery(Base):
    """An event for a client's webhook, sent by the worker with retries. The
    body (sealed at rest) is deleted once delivered or given up."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    client_pk: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(40))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=DeliveryStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webhook_deliveries_due", "status", "next_attempt_at"),
        Index("ix_webhook_deliveries_client", "client_pk", "created_at"),
        CheckConstraint("status IN ('pending', 'delivered', 'failed')", name="status"),
        same_org("client_pk", "integration_clients", "fk_webhook_deliveries_client_same_org", ondelete="CASCADE"),
    )
