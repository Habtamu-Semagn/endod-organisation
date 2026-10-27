"""Database engine and sessions.

This service has its own database: organisations, their admins, employees,
policies, claims, payout batches and the audit log.

Tenant context (PostgreSQL row-level security, migration 0004). Every
organisation-scoped table refuses rows of any organisation but the one the
transaction acts for, even if a query forgets its ``organisation_id`` filter.
Each session says who it acts for, and every transaction it begins sets it
again with ``set_config(..., true)`` (transaction-local: a pooled connection
never carries it over to the next user):

* ``tenant_session(organisation_id)``: a signed-in admin's request
  (``app.organisation_id``); the portal routes use only this;
* ``platform_session()``: Endod acting across organisations (``app.scope =
  'platform'``): the /platform routes, the expired-draft sweep and the CLI.
  It is the only way the application sets that scope;
* ``session_scope()``: nobody yet (sign-in, setup links, a new application):
  every tenant table answers no rows and refuses every write until
  ``bind_tenant`` names the organisation, which sign-in learns from one narrow
  SECURITY DEFINER function (app.auth).

SQLite (development and the default tests) has no row-level security; the
application's own ``organisation_id`` filters (app.tenancy) are the wall there.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

DEV_DATABASE_URL = "sqlite:///./organisation.db"


class Base(DeclarativeBase):
    # Explicit constraint names: the same on SQLite and PostgreSQL.
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


def ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; everything here is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def iso(value: Optional[datetime]) -> Optional[str]:
    return ensure_aware(value).isoformat() if value is not None else None


_engine: Optional[Engine] = None
_engine_url: Optional[str] = None
_sessions: Optional[sessionmaker] = None


def database_url() -> str:
    settings = get_settings()
    url = settings.ORG_DATABASE_URL or ""
    if settings.is_production and (not url or url.startswith("sqlite")):
        raise RuntimeError("ORG_DATABASE_URL must point at PostgreSQL in production.")
    if not url and settings.ORG_ENVIRONMENT != "development":
        # A container that lost its URL must not quietly use a throwaway SQLite file.
        raise RuntimeError("ORG_DATABASE_URL is not set.")
    return url or DEV_DATABASE_URL


def get_engine() -> Engine:
    global _engine, _engine_url, _sessions
    url = database_url()
    if _engine is None or url != _engine_url:
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _sqlite_foreign_keys)
        _engine_url = url
        _sessions = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def _sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def reset_engine() -> None:
    global _engine, _engine_url, _sessions
    if _engine is not None:
        _engine.dispose()
    _engine = _engine_url = _sessions = None


#: Keys of ``Session.info``: the organisation a session acts for, or the platform scope.
TENANT_KEY = "rls_organisation_id"
PLATFORM_KEY = "rls_platform"
PLATFORM_SCOPE = "platform"

_SET_CONTEXT = text("SELECT set_config('app.organisation_id', :org, true), set_config('app.scope', :scope, true)")


def _apply_context(session: Session, connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(_SET_CONTEXT, {
        "org": session.info.get(TENANT_KEY) or "",
        "scope": PLATFORM_SCOPE if session.info.get(PLATFORM_KEY) else "",
    })


@event.listens_for(Session, "after_begin")
def _context_on_begin(session: Session, _transaction, connection) -> None:
    """Every transaction a session begins acts for its tenant (or for nobody)."""
    _apply_context(session, connection)


def bind_tenant(session: Session, organisation_id: str) -> None:
    """From now on (this transaction and the next) ``session`` acts for
    ``organisation_id``: once the organisation is known (sign-in, a new
    application). Never switches a session from one organisation to another."""
    if not organisation_id or not isinstance(organisation_id, str):
        raise ValueError("bind_tenant needs an organisation id.")
    if session.info.get(PLATFORM_KEY):
        raise RuntimeError("A platform session is not bound to one organisation.")
    current = session.info.get(TENANT_KEY)
    if current and current != organisation_id:
        raise RuntimeError("This session already acts for another organisation.")
    session.info[TENANT_KEY] = organisation_id
    if session.in_transaction():
        _apply_context(session, session.connection())


@contextmanager
def tenant_session(organisation_id: str) -> Iterator[Session]:
    """A session acting for one organisation: a signed-in admin's request."""
    if not organisation_id or not isinstance(organisation_id, str):
        raise ValueError("tenant_session needs an organisation id.")
    with session_scope() as session:
        session.info[TENANT_KEY] = organisation_id
        yield session


@contextmanager
def platform_session() -> Iterator[Session]:
    """A session acting for Endod across every organisation. Only the
    /platform routes (behind the platform key), the expired-draft sweep and
    the operator CLI use it."""
    with session_scope() as session:
        session.info[PLATFORM_KEY] = True
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session acting for nobody: on PostgreSQL the tenant tables show no
    rows and take no writes until ``bind_tenant``."""
    get_engine()
    session = _sessions()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all() -> None:
    """Create tables directly (tests and local development).

    Deployments use the Alembic migrations in ``migrations/`` instead.
    """
    from app import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(get_engine())
