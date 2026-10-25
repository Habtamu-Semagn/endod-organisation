"""Alembic environment: migrates the organisation portal's own database.

In production migrations run as the *owner* role (the one-shot ``migrate``
service), and the API runs as the *app* role (deploy/postgres-init). After
every upgrade on PostgreSQL, the app role (ORG_APP_ROLE, default
``org_app``, if it exists) is given exactly what it needs: read and write
on the app tables, but only SELECT and INSERT on audit_events (the log is
append-only for the API), and only SELECT on alembic_version. The owner's
default privileges (set by the init script) cover tables created later too;
this step makes it exact and idempotent.
"""

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app import models  # noqa: F401  (registers the tables)
from app.db import Base, get_engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata

#: Tables the API may only read and append to.
APPEND_ONLY = ("audit_events",)


def grant_app_role(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    role = os.environ.get("ORG_APP_ROLE", "org_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("ORG_APP_ROLE must be a plain lower-case role name.")
    if not connection.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar():
        return
    connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
    for table in sorted(target_metadata.tables):
        if connection.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar() is None:
            continue  # not there (yet, or any more after a downgrade)
        connection.execute(text(f'REVOKE ALL ON TABLE "{table}" FROM "{role}"'))
        privileges = "SELECT, INSERT" if table in APPEND_ONLY else "SELECT, INSERT, UPDATE, DELETE"
        connection.execute(text(f'GRANT {privileges} ON TABLE "{table}" TO "{role}"'))
    connection.execute(text(f'REVOKE ALL ON TABLE alembic_version FROM "{role}"'))
    connection.execute(text(f'GRANT SELECT ON TABLE alembic_version TO "{role}"'))


def run_migrations_offline() -> None:
    context.configure(url=str(get_engine().url), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
            grant_app_role(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
