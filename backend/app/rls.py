"""The few look-ups that must cross the tenant wall before the organisation is known.

On PostgreSQL every organisation-scoped table has row-level security
(migration 0004, app.db): a session acting for nobody sees no rows. Signing
in, opening a setup link and resolving a session token must find *which*
organisation they belong to first. Each of those is one SECURITY DEFINER
function that answers a single organisation id (or a yes/no) for a single
secret or key, and nothing else; the request then binds that organisation
(app.db.bind_tenant) and reads everything else under the policies as usual.
Starting an application asks whether an email is taken, and saving one
whether a TIN is held by another organisation, the same way.

SQLite has no row-level security: the same questions are plain queries.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, text

from app.models import AdminSession, Organisation, OrgAdmin, OrgStatus, SetupToken

#: The SECURITY DEFINER functions migration 0004 creates (the app role may execute only these).
FUNCTIONS = (
    "rls_admin_organisation(text)",
    "rls_session_organisation(text)",
    "rls_setup_link_organisation(text)",
    "rls_tin_taken(text, text)",
)


def _postgres(session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def admin_organisation(session, email: str) -> Optional[str]:
    """The organisation of the admin with this (normalised) email, or None."""
    if _postgres(session):
        return session.scalar(text("SELECT rls_admin_organisation(:email)"), {"email": email})
    return session.scalar(select(OrgAdmin.organisation_id).where(OrgAdmin.email == email))


def session_organisation(session, token_hash: str) -> Optional[str]:
    """The organisation of the admin whose session has this token hash, or None."""
    if _postgres(session):
        return session.scalar(text("SELECT rls_session_organisation(:h)"), {"h": token_hash})
    return session.scalar(select(OrgAdmin.organisation_id).join(AdminSession, AdminSession.admin_id == OrgAdmin.id)
                          .where(AdminSession.token_hash == token_hash))


def setup_link_organisation(session, token_hash: str) -> Optional[str]:
    """The organisation of the admin whose setup link has this token hash, or None."""
    if _postgres(session):
        return session.scalar(text("SELECT rls_setup_link_organisation(:h)"), {"h": token_hash})
    return session.scalar(select(OrgAdmin.organisation_id).join(SetupToken, SetupToken.admin_id == OrgAdmin.id)
                          .where(SetupToken.token_hash == token_hash))


def tin_taken(session, tin: str, organisation_id: str) -> bool:
    """``tin`` is held by another active organisation (app.onboarding.tin_taken)."""
    if _postgres(session):
        return bool(session.scalar(text("SELECT rls_tin_taken(:tin, :org)"), {"tin": tin, "org": organisation_id}))
    return session.scalar(select(Organisation.id).where(
        Organisation.tin == tin, Organisation.id != organisation_id, Organisation.status == OrgStatus.ACTIVE,
    )) is not None
