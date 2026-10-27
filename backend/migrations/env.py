"""Alembic environment: migrates the organisation portal's own database.

In production migrations run as the *owner* role (the one-shot ``migrate``
service), and the API runs as the *app* role (deploy/postgres-init). On
PostgreSQL both roles of row-level security (migration 0004) must exist
before anything runs, or the migration stops:

* the app role (ORG_APP_ROLE, default ``org_app``): neither a superuser nor
  BYPASSRLS;
* the platform role (``org_platform``): NOLOGIN, neither a superuser nor
  BYPASSRLS, and granted to the app role WITH INHERIT FALSE and SET TRUE (the
  app role reaches it only through an explicit SET ROLE).

After every upgrade each is given exactly what it needs: read and write on
the app tables, but only SELECT and INSERT on audit_events (the log is
append-only); the app role also SELECT on alembic_version and EXECUTE on the
look-up functions (app.rls). The owner's default privileges (set by the init
scripts) cover tables created later too; this step makes it exact and
idempotent.

Migrations run in the owner's maintenance scope (``app.scope =
'maintenance'``, for this transaction only): the tables FORCE row-level
security, so even the owner sees no rows without it, and only the owner has a
policy for that scope.
"""

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app import models  # noqa: F401  (registers the tables)
from app import rls
from app.db import PLATFORM_ROLE, Base, get_engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata

#: Tables the API may only read and append to.
APPEND_ONLY = ("audit_events",)


def _app_role() -> str:
    role = os.environ.get("ORG_APP_ROLE", "org_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("ORG_APP_ROLE must be a plain lower-case role name.")
    return role


def check_roles(connection) -> None:
    """Stop unless both roles exist and cannot get around row-level security."""
    if connection.dialect.name != "postgresql":
        return
    role = _app_role()
    setup = "Create the roles first: deploy/postgres-init/10-roles.sh and 20-platform-role.sh."
    app = connection.execute(text("SELECT oid, rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = :r"),
                             {"r": role}).first()
    if app is None:
        raise RuntimeError(f"The app role {role} (ORG_APP_ROLE) does not exist. {setup}")
    if app[1]:
        raise RuntimeError(f"The app role {role} must be neither a superuser nor BYPASSRLS: "
                           "row-level security would not apply to it.")
    platform = connection.execute(text(
        "SELECT oid, rolsuper OR rolbypassrls OR rolcanlogin FROM pg_roles WHERE rolname = :r"),
        {"r": PLATFORM_ROLE}).first()
    if platform is None:
        raise RuntimeError(f"The platform role {PLATFORM_ROLE} does not exist. {setup}")
    if platform[1]:
        raise RuntimeError(f"The platform role {PLATFORM_ROLE} must be NOLOGIN, neither a superuser nor BYPASSRLS.")
    membership = connection.execute(text(
        "SELECT inherit_option, set_option FROM pg_auth_members WHERE roleid = :p AND member = :a"),
        {"p": platform[0], "a": app[0]}).first()
    if membership is None or membership[0] or not membership[1]:
        raise RuntimeError(f"Grant {PLATFORM_ROLE} to {role} WITH INHERIT FALSE, SET TRUE "
                           "(deploy/postgres-init/20-platform-role.sh).")


def _grant_tables(connection, role: str) -> None:
    for table in sorted(target_metadata.tables):
        if connection.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar() is None:
            continue  # not there (yet, or any more after a downgrade)
        connection.execute(text(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"'))
        privileges = "SELECT, INSERT" if table in APPEND_ONLY else "SELECT, INSERT, UPDATE, DELETE"
        connection.execute(text(f'GRANT {privileges} ON TABLE "{table}" TO "{role}"'))


def grant_roles(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    role = _app_role()
    for grantee in (role, PLATFORM_ROLE):
        connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{grantee}"'))
        _grant_tables(connection, grantee)
    connection.execute(text(f'REVOKE ALL ON TABLE alembic_version FROM "{role}"'))
    connection.execute(text(f'GRANT SELECT ON TABLE alembic_version TO "{role}"'))
    for function in rls.FUNCTIONS:
        if connection.execute(text("SELECT to_regprocedure(:f)"), {"f": function}).scalar() is not None:
            connection.execute(text(f'GRANT EXECUTE ON FUNCTION {function} TO "{role}"'))


def run_migrations_offline() -> None:
    context.configure(url=str(get_engine().url), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                check_roles(connection)
                # Row-level security is FORCEd on the owner too: its maintenance scope, this transaction only.
                connection.execute(text("SELECT set_config('app.scope', 'maintenance', true)"))
            context.run_migrations()
            grant_roles(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
