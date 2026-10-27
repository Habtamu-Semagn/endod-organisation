"""The few look-ups that must cross the tenant wall before the organisation is known.

On PostgreSQL every organisation-scoped table has row-level security
(migration 0004, app.db): a session acting for nobody sees no rows. Signing
in, opening a setup link and resolving a session token must find *which*
organisation they belong to first. Each of those is one SECURITY DEFINER
function that answers a single organisation id for a single key, and only
for a live key (an active admin; a session neither revoked nor expired; a
setup link neither used nor expired); the request then binds that
organisation (app.db.bind_tenant) and reads everything else under the
policies as usual. Whether an email or a TIN is taken is a yes or no. An
audit event that concerns no organisation (a failed sign-in for an unknown
email) is appended through one more function: a tenant may append only its
own organisation's events.

SQLite has no row-level security: the same questions are plain queries.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, text

from app.db import utcnow
from app.models import AdminSession, Organisation, OrgAdmin, OrgStatus, SetupToken

#: The SECURITY DEFINER functions migration 0004 creates (the app role may execute only these).
FUNCTIONS = (
    "rls_admin_organisation(text)",
    "rls_session_organisation(text)",
    "rls_setup_link_organisation(text)",
    "rls_email_taken(text)",
    "rls_tin_taken(text, text)",
    "rls_record_orgless_event(text, timestamptz, text, text, text, text, text, text, text, text)",
)


def postgres(session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def admin_organisation(session, email: str) -> Optional[str]:
    """The organisation of the active admin with this (normalised) email, or None."""
    if postgres(session):
        return session.scalar(text("SELECT rls_admin_organisation(:email)"), {"email": email})
    return session.scalar(select(OrgAdmin.organisation_id).join(Organisation, Organisation.id == OrgAdmin.organisation_id)
                          .where(OrgAdmin.email == email, OrgAdmin.active.is_(True)))


def session_organisation(session, token_hash: str) -> Optional[str]:
    """The organisation of the admin whose live (not revoked, not expired)
    session has this token hash, or None."""
    if postgres(session):
        return session.scalar(text("SELECT rls_session_organisation(:h)"), {"h": token_hash})
    return session.scalar(select(OrgAdmin.organisation_id).join(AdminSession, AdminSession.admin_id == OrgAdmin.id)
                          .where(AdminSession.token_hash == token_hash, AdminSession.revoked_at.is_(None),
                                 AdminSession.expires_at > utcnow()))


def setup_link_organisation(session, token_hash: str) -> Optional[str]:
    """The organisation of the admin whose unused, unexpired setup link has this token hash, or None."""
    if postgres(session):
        return session.scalar(text("SELECT rls_setup_link_organisation(:h)"), {"h": token_hash})
    return session.scalar(select(OrgAdmin.organisation_id).join(SetupToken, SetupToken.admin_id == OrgAdmin.id)
                          .where(SetupToken.token_hash == token_hash, SetupToken.used_at.is_(None),
                                 SetupToken.expires_at > utcnow()))


def email_taken(session, email: str) -> bool:
    """Some admin (of any organisation, active or not) has this email."""
    if postgres(session):
        return bool(session.scalar(text("SELECT rls_email_taken(:email)"), {"email": email}))
    return session.scalar(select(OrgAdmin.id).where(OrgAdmin.email == email)) is not None


def tin_taken(session, tin: str, organisation_id: str) -> bool:
    """``tin`` is held by another active organisation (app.onboarding.tin_taken)."""
    if postgres(session):
        return bool(session.scalar(text("SELECT rls_tin_taken(:tin, :org)"), {"tin": tin, "org": organisation_id}))
    return session.scalar(select(Organisation.id).where(
        Organisation.tin == tin, Organisation.id != organisation_id, Organisation.status == OrgStatus.ACTIVE,
    )) is not None


def record_orgless_event(session, event) -> None:
    """Append ``event`` (an app.models.AuditEvent with no organisation and no
    admin) from a session that acts for no organisation."""
    session.execute(text(
        "SELECT rls_record_orgless_event(:id, :at, :action, :result, :admin_email, :ip, :target_type, :target_id, "
        ":target_name, :detail)"), {
        "id": event.id, "at": event.at, "action": event.action, "result": event.result, "admin_email": event.admin_email,
        "ip": event.ip, "target_type": event.target_type, "target_id": event.target_id,
        "target_name": event.target_name, "detail": event.detail})
