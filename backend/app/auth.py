"""Organisation admin sign-in: password, then TOTP; enrolment through a
one-time setup link; server-side sessions; throttling; re-authentication.

Every admin belongs to exactly one organisation; the session carries its id
(Principal.organisation_id) and every query of the portal API filters on it.
A suspended organisation's admins cannot sign in, and their sessions end.
An organisation whose application (app.onboarding) is not approved is
*locked*: its admins reach only the application, the sign-in steps and
sign-out; every other route answers 403 (``current_admin``).

A sign-in goes through stages (app.models.SessionStage). The password opens a
short *pending* session (stage ``totp``); the code revokes it and opens a new
*full* session, so the token changes at every step (no fixation). Only full
sessions reach the portal API. An admin who has not enrolled an authenticator
cannot sign in with a password at all: only their setup link opens an
``enroll`` session (after it checks or sets the password).

Throttling never signs anyone out and never locks an account for everyone:

* per address: too many failed steps from one address, for any account, and
  that address is refused for a while (429);
* per account and address: 5 failed steps against one account from one
  address lock that pair for 15 minutes (logged as ``account_locked``);
* per account, exponential backoff: after 3 recent failures (from anywhere),
  for 30 s, 60 s, ... up to 15 minutes, the password step stops telling
  whether a password is right: right or wrong, it moves on to the code step
  (a wrong one gets a stand-in session no code completes) and is not counted.
  Guessing is pointless then, while the admin, with the right password and a
  code, still signs in from any address.

Every failure is committed before the error is raised.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, Header, Request
from sqlalchemy import delete, func, select, update

from app import audit, security, totp
from app.config import Settings, get_settings
from app.db import ensure_aware, iso, session_scope, utcnow
from app.errors import ApiError
from app.models import (
    AdminSession, ApplicationStatus, AuditResult, AuthFailure, LoginThrottle, OrgAdmin, Organisation,
    OrganisationApplication, OrgStatus, RecoveryCode, SessionStage, SetupToken,
)

INVALID_LOGIN = "Incorrect email or password."
TOO_MANY = "Too many failed attempts from this address. Try again later."
INVALID_CODE = "That code is not valid. Check your authenticator app and try again."
LOCKED = "Too many failed attempts. Sign in again later."
SESSION_REQUIRED = "Authentication required."
SESSION_ENDED = "Your session has ended. Please sign in again."
INCOMPLETE = "Finish signing in first."
REAUTH_REQUIRED = "Confirm it is you: enter a code from your authenticator app."
INVALID_SETUP_LINK = "This setup link is invalid or has expired. Ask for a new one."
WRONG_PASSWORD = "That password is not correct."
CODE_WAIT = "Too many wrong codes for this account. Wait a few minutes, then try again."
NOT_APPROVED = "Your organisation's application is not approved yet."

SUCCESS, FAILURE = AuditResult.SUCCESS, AuditResult.FAILURE


@dataclass(frozen=True)
class Principal:
    """The session behind a request."""

    admin_id: str
    email: str
    name: str
    session_id: str
    stage: str
    reauth_at: Optional[datetime]
    ip: str
    #: The admin's organisation: the only one whose data this request may touch.
    organisation_id: str
    organisation_name: str
    password_ok: bool = True
    #: The organisation's application (app.models.ApplicationStatus); "approved" without one.
    application_status: str = ApplicationStatus.APPROVED

    @property
    def locked(self) -> bool:
        """Only the application, sign-in steps and sign-out until Endod approves it."""
        return self.application_status != ApplicationStatus.APPROVED


@dataclass(frozen=True)
class Opened:
    token: str
    stage: str
    max_age: int


# --- helpers -----------------------------------------------------------------------------

def _normal_email(email: str) -> str:
    return email.strip().lower()


def ip_key(ip: str) -> str:
    """The address the per-address limits count: an IPv4 address, or the /64
    network of an IPv6 address (one subscriber usually holds a whole /64)."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _ip_blocked(session, ip: str, now: datetime, settings: Settings) -> bool:
    ip = ip_key(ip)
    since = now - timedelta(minutes=settings.ORG_IP_WINDOW_MINUTES)
    count = session.scalar(select(func.count()).select_from(AuthFailure)
                           .where(AuthFailure.ip == ip, AuthFailure.at > since))
    return (count or 0) >= settings.ORG_IP_FAILURE_LIMIT


def _note_ip_failure(session, ip: str, now: datetime) -> None:
    ip = ip_key(ip)
    session.add(AuthFailure(ip=ip, at=now))
    # Old rows are of no use; dropped as new ones come in.
    session.execute(delete(AuthFailure).where(AuthFailure.at < now - timedelta(days=1)))


#: The per-address counter of company applications shares the sign-in
#: failures' table under its own key (``apply:<address>``), which the
#: sign-in limit never counts.
_APPLY_PREFIX = "apply:"


def application_limited(session, ip: str, now: datetime, settings: Settings) -> bool:
    """Too many applications started from this address (or its IPv6 /64) lately."""
    key = _APPLY_PREFIX + ip_key(ip)
    since = now - timedelta(minutes=settings.ORG_APPLICATION_WINDOW_MINUTES)
    count = session.scalar(select(func.count()).select_from(AuthFailure)
                           .where(AuthFailure.ip == key, AuthFailure.at > since))
    return (count or 0) >= settings.ORG_APPLICATIONS_PER_IP


def note_application(session, ip: str, now: datetime) -> None:
    session.add(AuthFailure(ip=(_APPLY_PREFIX + ip_key(ip))[:64], at=now))


def ip_blocked(session, ip: str, now: datetime, settings: Settings) -> bool:
    return _ip_blocked(session, ip, now, settings)


def note_ip_failure(session, ip: str, now: datetime) -> None:
    _note_ip_failure(session, ip, now)


def _throttle(session, admin_id: str, ip: str) -> LoginThrottle:
    ip = ip_key(ip)
    row = session.scalar(select(LoginThrottle).where(LoginThrottle.admin_id == admin_id, LoginThrottle.ip == ip)
                         .with_for_update())
    if row is None:
        row = LoginThrottle(admin_id=admin_id, ip=ip, failures=0)
        session.add(row)
    return row


def _pair_locked(session, admin_id: str, ip: str, now: datetime) -> bool:
    ip = ip_key(ip)
    until = session.scalar(select(LoginThrottle.locked_until).where(
        LoginThrottle.admin_id == admin_id, LoginThrottle.ip == ip))
    return until is not None and ensure_aware(until) > now


def _organisation_active(session, organisation_id: str) -> bool:
    return session.scalar(select(Organisation.status).where(Organisation.id == organisation_id)) == OrgStatus.ACTIVE


def _applying(session, organisation_id: str) -> bool:
    """The organisation applied itself and is not approved yet."""
    status = session.scalar(select(OrganisationApplication.status)
                            .where(OrganisationApplication.organisation_id == organisation_id))
    return status is not None and status != ApplicationStatus.APPROVED


def in_backoff(admin: OrgAdmin, now: datetime) -> bool:
    return admin.backoff_until is not None and ensure_aware(admin.backoff_until) > now


def backoff_seconds(failures: int, settings: Settings) -> int:
    """0 below ORG_BACKOFF_AFTER failures, then doubling from the base, capped."""
    if failures < settings.ORG_BACKOFF_AFTER:
        return 0
    exponent = min(failures - settings.ORG_BACKOFF_AFTER, 20)
    return min(settings.ORG_BACKOFF_BASE_SECONDS * 2 ** exponent, settings.ORG_BACKOFF_MAX_SECONDS)


def _record_failure(session, admin: OrgAdmin, now: datetime, settings: Settings, ip: str) -> bool:
    """Count a failed step against ``admin`` from ``ip`` (admin row locked).
    Returns True if this locked the (account, address) pair. Never ends a session."""
    window = timedelta(minutes=settings.ORG_LOCKOUT_MINUTES)
    pair = _throttle(session, admin.id, ip)
    if pair.last_failed_at is None or ensure_aware(pair.last_failed_at) < now - window:
        pair.failures = 0
    pair.failures += 1
    pair.last_failed_at = now
    locked = False
    if pair.failures >= settings.ORG_LOCKOUT_ATTEMPTS:
        pair.locked_until = now + window
        pair.failures = 0
        locked = True
        audit.record(session, audit.LOCKED_OUT, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                     detail={"scope": "account_and_address", "minutes": settings.ORG_LOCKOUT_MINUTES})

    backoff_window = timedelta(minutes=settings.ORG_BACKOFF_WINDOW_MINUTES)
    if admin.last_failed_at is None or ensure_aware(admin.last_failed_at) < now - backoff_window:
        admin.failed_attempts = 0
    admin.failed_attempts += 1
    admin.last_failed_at = now
    seconds = backoff_seconds(admin.failed_attempts, settings)
    if seconds:
        admin.backoff_until = now + timedelta(seconds=seconds)
        audit.record(session, audit.BACKOFF, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                     detail={"seconds": seconds, "failures": admin.failed_attempts})
    return locked


def _clear_failures(session, admin: OrgAdmin, ip: str) -> None:
    admin.failed_attempts = 0
    admin.last_failed_at = None
    admin.backoff_until = None
    session.execute(delete(LoginThrottle).where(LoginThrottle.admin_id == admin.id, LoginThrottle.ip == ip_key(ip)))


def code_backoff_seconds(failures: int, settings: Settings) -> int:
    """0 below ORG_CODE_FAILURE_LIMIT failures, then doubling from the base, capped."""
    if failures < settings.ORG_CODE_FAILURE_LIMIT:
        return 0
    exponent = min(failures - settings.ORG_CODE_FAILURE_LIMIT, 20)
    return min(settings.ORG_CODE_BACKOFF_BASE_SECONDS * 2 ** exponent, settings.ORG_CODE_BACKOFF_MAX_SECONDS)


def _code_blocked(admin: OrgAdmin, now: datetime) -> bool:
    """Code attempts against this account are paused (from any address)."""
    return admin.code_backoff_until is not None and ensure_aware(admin.code_backoff_until) > now


def _record_code_failure(session, admin: OrgAdmin, now: datetime, settings: Settings, ip: str) -> None:
    """Count a wrong TOTP or recovery code against the account, whatever the
    address: from ORG_CODE_FAILURE_LIMIT failures within the window, code
    attempts are refused for a growing while (30 s, 60 s, ... 15 minutes).
    Sessions are never ended by this."""
    window = timedelta(minutes=settings.ORG_CODE_WINDOW_MINUTES)
    if admin.code_last_failed_at is None or ensure_aware(admin.code_last_failed_at) < now - window:
        admin.code_failures = 0
    admin.code_failures = (admin.code_failures or 0) + 1
    admin.code_last_failed_at = now
    seconds = code_backoff_seconds(admin.code_failures, settings)
    if seconds:
        admin.code_backoff_until = now + timedelta(seconds=seconds)
        audit.record(session, audit.CODE_BACKOFF, SUCCESS, organisation_id=admin.organisation_id,
                     admin_id=admin.id, admin_email=admin.email, ip=ip,
                     detail={"seconds": seconds, "failures": admin.code_failures})


def _clear_code_failures(admin: OrgAdmin) -> None:
    admin.code_failures = 0
    admin.code_last_failed_at = None
    admin.code_backoff_until = None


def revoke_all(session, admin_id: str, now: datetime) -> None:
    session.execute(update(AdminSession)
                    .where(AdminSession.admin_id == admin_id, AdminSession.revoked_at.is_(None))
                    .values(revoked_at=now))


def _locked_admin(session, admin_id: str) -> Optional[OrgAdmin]:
    """The admin row, locked for this transaction so parallel attempts cannot
    lose failure counts or reuse a TOTP step (no-op on SQLite, which serialises writers)."""
    return session.scalar(select(OrgAdmin).where(OrgAdmin.id == admin_id).with_for_update())


def _open_session(session, admin: OrgAdmin, stage: str, now: datetime, settings: Settings,
                  ip: str, user_agent: Optional[str], password_ok: bool = True) -> Opened:
    token = security.new_token()
    if stage == SessionStage.FULL:
        lifetime = timedelta(hours=settings.ORG_SESSION_MAX_HOURS)
    else:
        lifetime = timedelta(minutes=settings.ORG_PENDING_SESSION_MINUTES)
    session.add(AdminSession(admin_id=admin.id, token_hash=security.token_hash(token), stage=stage,
                             password_ok=password_ok, created_at=now, last_seen_at=now,
                             expires_at=now + lifetime, ip=ip, user_agent=(user_agent or "")[:200] or None))
    return Opened(token=token, stage=stage, max_age=int(lifetime.total_seconds()))


def _revoke(session, session_id: str, now: datetime) -> None:
    session.execute(update(AdminSession).where(AdminSession.id == session_id).values(revoked_at=now))


def opened_payload(opened: Opened, **extra: Any) -> Dict[str, Any]:
    """What the web app receives: it moves ``session_token`` into the
    httpOnly cookie and never passes it to the page."""
    return {"stage": opened.stage, "session_token": opened.token, "session_max_age": opened.max_age, **extra}


# --- password step -----------------------------------------------------------------------

def login(email: str, password: str, ip: str, user_agent: Optional[str]) -> Opened:
    """Check the password; open a pending session (a TOTP code is next).

    Unknown email, wrong password, disabled account, an address locked for
    this account, and an admin who has not enrolled yet (they use their setup
    link) all answer the same, with the same argon2 work. The email typed for
    an unknown account is logged only as a keyed hash.
    """
    settings = get_settings()
    now = utcnow()
    email = _normal_email(email)
    failure: Optional[ApiError] = None
    with session_scope() as session:
        if _ip_blocked(session, ip, now, settings):
            security.verify_password(password, security.DUMMY_HASH)
            audit.record(session, audit.SIGN_IN, FAILURE, admin_email=security.email_fingerprint(email), ip=ip,
                         detail={"step": "password", "reason": "address_rate_limited"})
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
        else:
            found = session.scalar(select(OrgAdmin.id).where(OrgAdmin.email == email))
            admin = _locked_admin(session, found) if found else None
            reason: Optional[str] = None
            counted = False
            if admin is None:
                security.verify_password(password, security.DUMMY_HASH)
                reason = "unknown_email"
            else:
                correct = security.verify_password(password, admin.password_hash or security.DUMMY_HASH) \
                    and admin.password_hash is not None
                if _pair_locked(session, admin.id, ip, now):
                    reason = "address_locked_for_account"
                elif not admin.active:
                    reason = "account_disabled"
                elif not _organisation_active(session, admin.organisation_id):
                    reason = "organisation_suspended"
                elif not admin.totp_secret:
                    applying = _applying(session, admin.organisation_id)
                    if applying and correct and not in_backoff(admin, now):
                        # A company's applicant who left before enrolling (they chose
                        # the password themselves; there is no setup link): enrol now.
                        _clear_failures(session, admin, ip)
                        opened = _open_session(session, admin, SessionStage.ENROLL, now, settings, ip, user_agent)
                        audit.record(session, audit.SIGN_IN_PASSWORD, SUCCESS, organisation_id=admin.organisation_id,
                                     admin_id=admin.id, admin_email=admin.email, ip=ip,
                                     detail={"next": SessionStage.ENROLL})
                        return opened
                    if applying and not correct:
                        reason = "wrong_password"
                        counted = True
                    else:
                        # Enrolment happens only through the setup link (an applicant in backoff waits).
                        reason = "not_enrolled"
                elif in_backoff(admin, now):
                    # Right or wrong, on to the code step; a wrong password gets
                    # a stand-in session that no code completes. Not counted.
                    if correct and security.needs_rehash(admin.password_hash):
                        admin.password_hash = security.hash_password(password)
                    opened = _open_session(session, admin, SessionStage.TOTP, now, settings, ip, user_agent,
                                           password_ok=correct)
                    audit.record(session, audit.SIGN_IN_PASSWORD, SUCCESS if correct else FAILURE,
                                 organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                                 detail={"next": SessionStage.TOTP, "during_backoff": True})
                    return opened
                elif not correct:
                    reason = "wrong_password"
                    counted = True
            if reason is not None:
                if counted:
                    _record_failure(session, admin, now, settings, ip)
                _note_ip_failure(session, ip, now)
                audit.record(session, audit.SIGN_IN, FAILURE, organisation_id=admin.organisation_id if admin else None, admin_id=admin.id if admin else None,
                             admin_email=admin.email if admin else security.email_fingerprint(email), ip=ip,
                             detail={"step": "password", "reason": reason})
                failure = ApiError(401, INVALID_LOGIN, "INVALID_LOGIN")
            else:
                if security.needs_rehash(admin.password_hash):
                    admin.password_hash = security.hash_password(password)
                opened = _open_session(session, admin, SessionStage.TOTP, now, settings, ip, user_agent)
                audit.record(session, audit.SIGN_IN_PASSWORD, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email,
                             ip=ip, detail={"next": SessionStage.TOTP})
                return opened
    raise failure


# --- sessions ----------------------------------------------------------------------------

def resolve(token: str, ip: str) -> Principal:
    """The session for ``token``, or ApiError(401). Ends sessions idle for
    longer than the idle timeout; refreshes the idle clock otherwise."""
    settings = get_settings()
    now = utcnow()
    with session_scope() as session:
        row = session.execute(
            select(AdminSession, OrgAdmin, Organisation, OrganisationApplication.status)
            .join(OrgAdmin, OrgAdmin.id == AdminSession.admin_id)
            .join(Organisation, Organisation.id == OrgAdmin.organisation_id)
            .outerjoin(OrganisationApplication, OrganisationApplication.organisation_id == Organisation.id)
            .where(AdminSession.token_hash == security.token_hash(token))
        ).first()
        if row is None:
            raise ApiError(401, SESSION_REQUIRED, "AUTH_REQUIRED")
        sess, admin, organisation, application_status = row
        idle = timedelta(minutes=settings.ORG_SESSION_IDLE_MINUTES)
        ended = (sess.revoked_at is not None or ensure_aware(sess.expires_at) <= now
                 or ensure_aware(sess.last_seen_at) + idle <= now or not admin.active
                 or organisation.status != OrgStatus.ACTIVE)
        if ended:
            if sess.revoked_at is None:
                sess.revoked_at = now
                session.commit()
            raise ApiError(401, SESSION_ENDED, "SESSION_ENDED")
        sess.last_seen_at = now
        return Principal(admin_id=admin.id, email=admin.email, name=admin.name, session_id=sess.id,
                         stage=sess.stage, reauth_at=ensure_aware(sess.reauth_at), ip=ip,
                         organisation_id=organisation.id, organisation_name=organisation.name,
                         password_ok=bool(sess.password_ok),
                         application_status=application_status or ApplicationStatus.APPROVED)


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.strip().partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def any_session(request_ip: str, authorization: Optional[str]) -> Principal:
    token = _bearer(authorization)
    if not token:
        raise ApiError(401, SESSION_REQUIRED, "AUTH_REQUIRED")
    return resolve(token, request_ip)


def reauth_valid_until(principal: Principal) -> Optional[datetime]:
    if principal.reauth_at is None:
        return None
    return principal.reauth_at + timedelta(minutes=get_settings().ORG_REAUTH_MINUTES)


def require_fresh(principal: Principal) -> None:
    until = reauth_valid_until(principal)
    if until is None or until <= utcnow():
        raise ApiError(403, REAUTH_REQUIRED, "REAUTH_REQUIRED")


def logout(principal: Principal) -> None:
    now = utcnow()
    with session_scope() as session:
        _revoke(session, principal.session_id, now)
        audit.by(session, principal, audit.SIGN_OUT, SUCCESS)


# --- second step: TOTP or a recovery code ------------------------------------------------

def _check_code(session, admin: OrgAdmin, code: Optional[str], recovery_code: Optional[str],
                now: datetime) -> Optional[str]:
    """The method that worked ("totp" or "recovery_code"), or None. Marks the
    TOTP step or the recovery code as used."""
    if code:
        if not admin.totp_secret:
            return None
        step = totp.verify(security.unseal(admin.totp_secret), code, admin.totp_last_step)
        if step is not None:
            admin.totp_last_step = step
            return "totp"
        return None
    if recovery_code:
        wanted = security.recovery_code_hash(recovery_code)
        row = session.scalar(select(RecoveryCode).where(
            RecoveryCode.admin_id == admin.id, RecoveryCode.code_hash == wanted, RecoveryCode.used_at.is_(None)))
        if row is not None:
            row.used_at = now
            return "recovery_code"
    return None


def complete_sign_in(principal: Principal, code: Optional[str], recovery_code: Optional[str],
                     user_agent: Optional[str]) -> Tuple[Opened, Dict[str, Any]]:
    if principal.stage != SessionStage.TOTP:
        raise ApiError(409, "This sign-in does not need a code now.", "WRONG_STAGE")
    settings = get_settings()
    now = utcnow()
    ip = principal.ip
    failure: Optional[ApiError] = None
    with session_scope() as session:
        admin = _locked_admin(session, principal.admin_id)
        if _ip_blocked(session, ip, now, settings):
            audit.record(session, audit.SIGN_IN, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                         detail={"step": "totp", "reason": "address_rate_limited"})
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
        elif _pair_locked(session, admin.id, ip, now):
            _revoke(session, principal.session_id, now)
            audit.record(session, audit.SIGN_IN, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                         detail={"step": "totp", "reason": "address_locked_for_account"})
            failure = ApiError(401, LOCKED, "LOCKED")
        elif _code_blocked(admin, now):
            audit.record(session, audit.SIGN_IN, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id,
                         admin_email=admin.email, ip=ip, detail={"step": "totp", "reason": "account_code_backoff"})
            failure = ApiError(429, CODE_WAIT, "CODE_BACKOFF")
        else:
            # A stand-in session (wrong password during backoff) never completes,
            # and its code is not even checked (a recovery code stays unused).
            method = _check_code(session, admin, code, recovery_code, now) if principal.password_ok else None
            if method is None:
                _note_ip_failure(session, ip, now)
                locked = _record_failure(session, admin, now, settings, ip)
                _record_code_failure(session, admin, now, settings, ip)
                reason = "invalid_code" if principal.password_ok else "wrong_password_during_backoff"
                audit.record(session, audit.SIGN_IN, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                             detail={"step": "recovery_code" if recovery_code and not code else "totp",
                                     "reason": reason})
                if locked:
                    # Only this half-finished sign-in ends; nobody else is signed out.
                    _revoke(session, principal.session_id, now)
                    failure = ApiError(401, LOCKED, "LOCKED")
                else:
                    failure = ApiError(400, INVALID_CODE, "INVALID_CODE")
            else:
                _revoke(session, principal.session_id, now)
                _clear_failures(session, admin, ip)
                _clear_code_failures(admin)
                admin.last_login_at = now
                opened = _open_session(session, admin, SessionStage.FULL, now, settings, ip, user_agent)
                remaining = session.scalar(select(func.count()).select_from(RecoveryCode).where(
                    RecoveryCode.admin_id == admin.id, RecoveryCode.used_at.is_(None))) or 0
                audit.record(session, audit.SIGN_IN, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                             detail={"method": method, "recovery_codes_left": remaining})
                return opened, {"recovery_codes_left": remaining}
    raise failure


# --- enrolment ---------------------------------------------------------------------------

def enrolment_start(principal: Principal) -> Dict[str, Any]:
    """The secret to add to the authenticator (as a QR code's otpauth URI and as text).
    Asking again shows the same secret until it is confirmed."""
    if principal.stage != SessionStage.ENROLL:
        raise ApiError(409, "Two-factor sign-in is already set up.", "WRONG_STAGE")
    with session_scope() as session:
        admin = _locked_admin(session, principal.admin_id)
        if admin.totp_pending_secret:
            secret = security.unseal(admin.totp_pending_secret)
        else:
            secret = totp.new_secret()
            admin.totp_pending_secret = security.seal(secret)
            audit.record(session, audit.ENROLMENT_STARTED, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email,
                         ip=principal.ip)
        return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, admin.email),
                "issuer": totp.ISSUER, "account": admin.email}


def enrolment_confirm(principal: Principal, code: str, user_agent: Optional[str]) -> Tuple[Opened, List[str]]:
    """Confirm the first code; store the secret; issue 10 recovery codes (shown once)."""
    if principal.stage != SessionStage.ENROLL:
        raise ApiError(409, "Two-factor sign-in is already set up.", "WRONG_STAGE")
    settings = get_settings()
    now = utcnow()
    ip = principal.ip
    failure: Optional[ApiError] = None
    audited = False
    with session_scope() as session:
        admin = _locked_admin(session, principal.admin_id)
        if _ip_blocked(session, ip, now, settings):
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
        elif _pair_locked(session, admin.id, ip, now):
            _revoke(session, principal.session_id, now)
            failure = ApiError(401, LOCKED, "LOCKED")
        elif _code_blocked(admin, now):
            failure = ApiError(429, CODE_WAIT, "CODE_BACKOFF")
        elif not admin.totp_pending_secret:
            failure = ApiError(409, "Start the set-up again: no authenticator is waiting for a code.", "NO_SECRET")
        else:
            secret = security.unseal(admin.totp_pending_secret)
            step = totp.verify(secret, code, None)
            if step is None:
                _note_ip_failure(session, ip, now)
                locked = _record_failure(session, admin, now, settings, ip)
                _record_code_failure(session, admin, now, settings, ip)
                audit.record(session, audit.ENROLLED, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                             detail={"reason": "invalid_code"})
                audited = True
                if locked:
                    _revoke(session, principal.session_id, now)
                    failure = ApiError(401, LOCKED, "LOCKED")
                else:
                    failure = ApiError(400, INVALID_CODE, "INVALID_CODE")
            else:
                admin.totp_secret = admin.totp_pending_secret
                admin.totp_pending_secret = None
                admin.totp_last_step = step
                admin.totp_enrolled_at = now
                admin.last_login_at = now
                _clear_failures(session, admin, ip)
                _clear_code_failures(admin)
                codes = _replace_recovery_codes(session, admin.id, now)
                _revoke(session, principal.session_id, now)
                opened = _open_session(session, admin, SessionStage.FULL, now, settings, ip, user_agent)
                audit.record(session, audit.ENROLLED, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                             detail={"recovery_codes": len(codes)})
                audit.record(session, audit.SIGN_IN, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                             detail={"method": "enrolment"})
                return opened, codes
        if failure.code in ("RATE_LIMITED", "LOCKED", "CODE_BACKOFF") and not audited:
            audit.record(session, audit.ENROLLED, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                         detail={"reason": failure.code.lower()})
    raise failure


def _replace_recovery_codes(session, admin_id: str, now: datetime) -> List[str]:
    session.execute(delete(RecoveryCode).where(RecoveryCode.admin_id == admin_id))
    codes = [security.new_recovery_code() for _ in range(security.RECOVERY_CODE_COUNT)]
    for code in codes:
        session.add(RecoveryCode(admin_id=admin_id, code_hash=security.recovery_code_hash(code), created_at=now))
    return codes


# --- re-authentication -------------------------------------------------------------------

def reauthenticate(principal: Principal, code: str) -> datetime:
    """A fresh TOTP for sensitive actions; returns until when it is good."""
    settings = get_settings()
    now = utcnow()
    ip = principal.ip
    failure: Optional[ApiError] = None
    with session_scope() as session:
        admin = _locked_admin(session, principal.admin_id)
        if _ip_blocked(session, ip, now, settings):
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
            reason = "address_rate_limited"
        elif not admin.totp_secret:
            failure, reason = ApiError(409, "No authenticator is set up.", "NO_SECRET"), "no_secret"
        elif _code_blocked(admin, now):
            failure, reason = ApiError(429, CODE_WAIT, "CODE_BACKOFF"), "account_code_backoff"
        else:
            step = totp.verify(security.unseal(admin.totp_secret), code, admin.totp_last_step)
            if step is not None:
                admin.totp_last_step = step
                session.execute(update(AdminSession).where(AdminSession.id == principal.session_id)
                                .values(reauth_at=now))
                _clear_code_failures(admin)
                audit.record(session, audit.REAUTH, SUCCESS, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip)
                return now + timedelta(minutes=settings.ORG_REAUTH_MINUTES)
            _note_ip_failure(session, ip, now)
            locked = _record_failure(session, admin, now, settings, ip)
            _record_code_failure(session, admin, now, settings, ip)
            if locked:
                # Whoever is guessing with this session loses it (only this one).
                _revoke(session, principal.session_id, now)
                failure = ApiError(401, LOCKED, "LOCKED")
            else:
                failure = ApiError(400, INVALID_CODE, "INVALID_CODE")
            reason = "invalid_code"
        audit.record(session, audit.REAUTH, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email, ip=ip,
                     detail={"reason": reason})
    raise failure


# --- setup links -------------------------------------------------------------------------

def issue_setup_link(session, admin: OrgAdmin, now: Optional[datetime] = None) -> str:
    """A new one-time setup link for ``admin`` (earlier unused ones stop working)."""
    settings = get_settings()
    now = now or utcnow()
    session.execute(update(SetupToken).where(SetupToken.admin_id == admin.id, SetupToken.used_at.is_(None))
                    .values(used_at=now))
    token = security.new_token()
    session.add(SetupToken(admin_id=admin.id, token_hash=security.token_hash(token), created_at=now,
                           expires_at=now + timedelta(hours=settings.ORG_SETUP_LINK_HOURS)))
    # In the fragment: never sent to a server, never in a Referer.
    return f"{settings.SITE_ORIGIN}/setup#{token}"


def _setup_row(session, token: str, now: datetime, lock: bool = False) -> Optional[Tuple[SetupToken, OrgAdmin]]:
    query = select(SetupToken).where(SetupToken.token_hash == security.token_hash(token))
    if lock:
        query = query.with_for_update()
    link = session.scalar(query)
    if link is None or link.used_at is not None or ensure_aware(link.expires_at) <= now:
        return None
    admin = _locked_admin(session, link.admin_id) if lock else session.get(OrgAdmin, link.admin_id)
    if admin is None or not admin.active or not _organisation_active(session, admin.organisation_id):
        return None
    return link, admin


def _setup_mode(admin: OrgAdmin) -> str:
    """``confirm``: the admin has a password (create-admin --password-stdin) and
    proves it here; ``set``: the link sets it."""
    return "confirm" if admin.password_hash else "set"


def setup_check(token: str, ip: str) -> Dict[str, Any]:
    settings = get_settings()
    now = utcnow()
    with session_scope() as session:
        if _ip_blocked(session, ip, now, settings):
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
        else:
            found = _setup_row(session, token, now)
            if found is not None:
                link, admin = found
                return {"email": admin.email, "name": admin.name, "expires_at": iso(link.expires_at),
                        "mode": _setup_mode(admin)}
            _note_ip_failure(session, ip, now)
            audit.record(session, audit.SETUP_LINK, FAILURE, ip=ip, detail={"reason": "invalid_or_expired"})
            failure = ApiError(400, INVALID_SETUP_LINK, "INVALID_SETUP_LINK")
    raise failure


def setup_complete(token: str, password: str, ip: str, user_agent: Optional[str]) -> Opened:
    """Through a setup link: set the password (or, for an admin created with
    one, check it), then the admin enrols TOTP. The link works once: it is
    read FOR UPDATE and claimed with a conditional update in the same
    transaction, so of two simultaneous uses only one gets a session."""
    settings = get_settings()
    now = utcnow()
    failure: Optional[ApiError] = None
    with session_scope() as session:
        if _ip_blocked(session, ip, now, settings):
            failure = ApiError(429, TOO_MANY, "RATE_LIMITED")
        else:
            found = _setup_row(session, token, now, lock=True)
            if found is None:
                _note_ip_failure(session, ip, now)
                audit.record(session, audit.SETUP_LINK, FAILURE, ip=ip, detail={"reason": "invalid_or_expired"})
                failure = ApiError(400, INVALID_SETUP_LINK, "INVALID_SETUP_LINK")
            else:
                link, admin = found
                mode = _setup_mode(admin)
                if mode == "set":
                    problem = security.password_problem(password, admin.email)
                    if problem:
                        raise ApiError(400, problem, "WEAK_PASSWORD")
                    new_hash = security.hash_password(password)
                elif _pair_locked(session, admin.id, ip, now):
                    security.verify_password(password, security.DUMMY_HASH)
                    audit.record(session, audit.SETUP_LINK, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email,
                                 ip=ip, detail={"reason": "address_locked_for_account"})
                    failure = ApiError(401, LOCKED, "LOCKED")
                    new_hash = None
                elif not security.verify_password(password, admin.password_hash):
                    _note_ip_failure(session, ip, now)
                    _record_failure(session, admin, now, settings, ip)
                    audit.record(session, audit.SETUP_LINK, FAILURE, organisation_id=admin.organisation_id, admin_id=admin.id, admin_email=admin.email,
                                 ip=ip, detail={"reason": "wrong_password"})
                    failure = ApiError(400, WRONG_PASSWORD, "WRONG_PASSWORD")
                    new_hash = None
                else:
                    new_hash = admin.password_hash
                if failure is None:
                    claimed = session.execute(
                        update(SetupToken).where(SetupToken.id == link.id, SetupToken.used_at.is_(None))
                        .values(used_at=now)).rowcount
                    if claimed != 1:
                        failure = ApiError(400, INVALID_SETUP_LINK, "INVALID_SETUP_LINK")
                    else:
                        admin.password_hash = new_hash
                        admin.totp_secret = admin.totp_pending_secret = None
                        admin.totp_last_step = admin.totp_enrolled_at = None
                        _clear_failures(session, admin, ip)
                        _clear_code_failures(admin)
                        session.execute(delete(RecoveryCode).where(RecoveryCode.admin_id == admin.id))
                        revoke_all(session, admin.id, now)
                        opened = _open_session(session, admin, SessionStage.ENROLL, now, settings, ip, user_agent)
                        audit.record(session, audit.SETUP_COMPLETED, SUCCESS, organisation_id=admin.organisation_id,
                                     admin_id=admin.id,
                                     admin_email=admin.email, ip=ip, detail={"mode": mode})
                        return opened
    raise failure


# --- FastAPI dependencies ----------------------------------------------------------------

def client_ip(request: Request) -> str:
    return audit.client_address(request)


def signed_in_any_stage(ip: str = Depends(client_ip),
                        authorization: Optional[str] = Header(default=None)) -> Principal:
    """Any live session, even a half-finished sign-in (the sign-in steps use this)."""
    return any_session(ip, authorization)


def signed_in_admin(principal: Principal = Depends(signed_in_any_stage)) -> Principal:
    """A fully signed-in admin, whether or not the organisation is approved:
    only the company application routes (app.api.application) use this."""
    if principal.stage != SessionStage.FULL:
        raise ApiError(403, INCOMPLETE, "SESSION_INCOMPLETE")
    return principal


def current_admin(principal: Principal = Depends(signed_in_admin)) -> Principal:
    """A fully signed-in admin of an approved organisation. Every portal
    route depends on this: an organisation still applying gets 403."""
    if principal.locked:
        raise ApiError(403, NOT_APPROVED, "APPLICATION_NOT_APPROVED")
    return principal


def fresh_admin(principal: Principal = Depends(current_admin)) -> Principal:
    """A fully signed-in admin who gave a fresh TOTP within ORG_REAUTH_MINUTES
    (approve, reject, mark paid, policy and payout changes)."""
    require_fresh(principal)
    return principal


def open_enrolment(session, admin: OrgAdmin, now: datetime, ip: str, user_agent: Optional[str]) -> Opened:
    """An enrolment session for an admin who just chose a password (a
    company's applicant, app.api.application): an authenticator comes first."""
    return _open_session(session, admin, SessionStage.ENROLL, now, get_settings(), ip, user_agent)
