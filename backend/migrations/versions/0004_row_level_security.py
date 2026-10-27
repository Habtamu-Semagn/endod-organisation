"""row-level security: the database refuses another organisation's rows

A second tenant wall behind the application's own ``organisation_id``
filters (app.tenancy): on PostgreSQL every organisation-scoped table gets
ENABLE and FORCE ROW LEVEL SECURITY (FORCE: the owner role is held to the
policies too) and three kinds of policy:

* ``tenant_isolation`` (every role): only the rows of the organisation the
  transaction acts for, ``current_setting('app.organisation_id', true)``,
  which app.db sets at the start of every transaction. With none set, no
  rows, and every write is refused: it fails closed.
* ``platform_access`` (only the NOLOGIN role ``org_platform``): every row.
  The app role reaches it only through ``SET LOCAL ROLE org_platform``
  (app.db.platform_session: the /platform routes, the expired-draft sweep, the
  CLI); it is a member WITH INHERIT FALSE (deploy/postgres-init/20-platform-role.sh),
  so nothing else it runs gets these rows. No setting gives them: setting
  ``app.scope`` as the app role changes nothing.
* ``owner_maintenance`` (only the owner role that runs this migration): every
  row, but only while ``app.scope = 'maintenance'``, which migrations/env.py
  sets for migrations and the look-up functions below set for their one
  query. The API never connects as the owner (app.db.check_connection_role).

Tables:

* with ``organisation_id``: organisations (by ``id``), org_admins,
  organisation_applications, application_documents, employees, dependants,
  benefit_policies, receipt_files, payment_batches, claims;
* keyed by ``admin_id`` (admin_sessions, recovery_codes, setup_tokens,
  login_throttles): through their admin's organisation (an EXISTS on
  org_admins, itself under its policy). No column is added: an admin never
  moves between organisations, so there is nothing to backfill or to drift;
* claim_items: through its claim's organisation, the same way;
* audit_events: SELECT and INSERT policies only (the app role has only those
  grants; with FORCE not even the owner can UPDATE or DELETE a row through
  SQL). A tenant appends only its own organisation's events; an event with no
  organisation (a failed sign-in for an unknown email) is appended through
  ``rls_record_orgless_event`` or by the platform role, and read only by it;
* not covered: auth_failures (per-address counters, no organisation's data,
  needed before any organisation is known) and alembic_version.

Before the organisation is known, SECURITY DEFINER functions answer one narrow
question each (EXECUTE revoked from PUBLIC; migrations/env.py grants it to the
app role): the organisation of an active admin by email (sign-in), the
organisation of a live session or of an unused, unexpired setup link by its
token hash, whether an email is taken and whether a TIN is held by another
active organisation (booleans), plus appending an event with no organisation.

Works on an existing database: nothing is added to or changed in any row. It
needs the roles of deploy/postgres-init (org_platform included). The downgrade
drops the policies and functions and disables row-level security again.

SQLite (development) has no row-level security: nothing happens there.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27 09:00:00.000000
"""
from alembic import op


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

PLATFORM_ROLE = "org_platform"
TENANT = "NULLIF(current_setting('app.organisation_id', true), '')"
MAINTENANCE = "current_setting('app.scope', true) = 'maintenance'"

#: Each policy table and the condition a tenant's rows meet.
POLICIES = {
    "organisations": f"id = {TENANT}",
    "org_admins": f"organisation_id = {TENANT}",
    "organisation_applications": f"organisation_id = {TENANT}",
    "application_documents": f"organisation_id = {TENANT}",
    "employees": f"organisation_id = {TENANT}",
    "dependants": f"organisation_id = {TENANT}",
    "benefit_policies": f"organisation_id = {TENANT}",
    "receipt_files": f"organisation_id = {TENANT}",
    "payment_batches": f"organisation_id = {TENANT}",
    "claims": f"organisation_id = {TENANT}",
    "claim_items": f"EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_items.claim_id AND c.organisation_id = {TENANT})",
}
for _table in ("admin_sessions", "recovery_codes", "setup_tokens", "login_throttles"):
    POLICIES[_table] = (f"EXISTS (SELECT 1 FROM org_admins a WHERE a.id = {_table}.admin_id "
                        f"AND a.organisation_id = {TENANT})")

AUDIT = "audit_events"
#: (name, command, role, USING, WITH CHECK) of the audit log's policies.
AUDIT_POLICIES = (
    ("tenant_read", "SELECT", "PUBLIC", f"organisation_id = {TENANT}", None),
    ("tenant_append", "INSERT", "PUBLIC", None, f"organisation_id = {TENANT}"),
    ("platform_read", "SELECT", PLATFORM_ROLE, "true", None),
    ("platform_append", "INSERT", PLATFORM_ROLE, None, "true"),
    ("owner_read", "SELECT", "CURRENT_USER", MAINTENANCE, None),
    ("owner_append", "INSERT", "CURRENT_USER", None, MAINTENANCE),
)

#: name(arguments) -> (return type, query). Each runs as the owner, in the
#: maintenance scope for that one query; the caller's scope is put back.
FUNCTIONS = {
    "rls_admin_organisation(p_email text)": (
        "varchar", "SELECT a.organisation_id FROM org_admins a JOIN organisations o ON o.id = a.organisation_id "
                   "WHERE a.email = p_email AND a.active"),
    "rls_session_organisation(p_token_hash text)": (
        "varchar", "SELECT a.organisation_id FROM admin_sessions s JOIN org_admins a ON a.id = s.admin_id "
                   "WHERE s.token_hash = p_token_hash AND s.revoked_at IS NULL AND s.expires_at > now()"),
    "rls_setup_link_organisation(p_token_hash text)": (
        "varchar", "SELECT a.organisation_id FROM setup_tokens t JOIN org_admins a ON a.id = t.admin_id "
                   "WHERE t.token_hash = p_token_hash AND t.used_at IS NULL AND t.expires_at > now()"),
    "rls_email_taken(p_email text)": (
        "boolean", "SELECT EXISTS (SELECT 1 FROM org_admins WHERE email = p_email)"),
    "rls_tin_taken(p_tin text, p_organisation_id text)": (
        "boolean", "SELECT EXISTS (SELECT 1 FROM organisations WHERE tin = p_tin AND id <> p_organisation_id "
                   "AND status = 'active')"),
}
#: Appends an audit event that concerns no organisation (and no admin).
ORGLESS_EVENT = ("rls_record_orgless_event(p_id text, p_at timestamptz, p_action text, p_result text, "
                 "p_admin_email text, "
                 "p_ip text, p_target_type text, p_target_id text, p_target_name text, p_detail text)")


def _signature(name: str) -> str:
    """``f(p_a text, p_b text)`` -> ``f(text, text)``."""
    fn, _, args = name.partition("(")
    types = [arg.split()[-1] for arg in args.rstrip(")").split(",") if arg.strip()]
    return f"{fn}({', '.join(types)})"


def _definer(name: str, returns: str, body: str) -> None:
    op.execute(f"""CREATE FUNCTION {name} RETURNS {returns} LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = public, pg_temp AS $fn$
DECLARE
  caller_scope text := current_setting('app.scope', true);
  {'answer ' + returns + ';' if returns != 'void' else ''}
BEGIN
  PERFORM set_config('app.scope', 'maintenance', true);
  {body};
  PERFORM set_config('app.scope', coalesce(caller_scope, ''), true);
  {'RETURN answer;' if returns != 'void' else 'RETURN;'}
END
$fn$""")
    op.execute(f"REVOKE ALL ON FUNCTION {_signature(name)} FROM PUBLIC")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, (returns, query) in FUNCTIONS.items():
        _definer(name, returns, f"{query} INTO answer")
    _definer(ORGLESS_EVENT, "void",
             "INSERT INTO audit_events (id, at, organisation_id, admin_id, admin_email, action, result, ip, "
             "target_type, target_id, target_name, detail) VALUES (p_id, p_at, NULL, NULL, p_admin_email, "
             "p_action, p_result, p_ip, p_target_type, p_target_id, p_target_name, p_detail)")
    for table, condition in POLICIES.items():
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO PUBLIC '
                   f'USING ({condition}) WITH CHECK ({condition})')
        op.execute(f'CREATE POLICY platform_access ON "{table}" FOR ALL TO {PLATFORM_ROLE} '
                   f'USING (true) WITH CHECK (true)')
        op.execute(f'CREATE POLICY owner_maintenance ON "{table}" FOR ALL TO CURRENT_USER '
                   f'USING ({MAINTENANCE}) WITH CHECK ({MAINTENANCE})')
    op.execute(f'ALTER TABLE "{AUDIT}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{AUDIT}" FORCE ROW LEVEL SECURITY')
    for name, command, role, using, check in AUDIT_POLICIES:
        clause = f"USING ({using})" if using else f"WITH CHECK ({check})"
        op.execute(f'CREATE POLICY {name} ON "{AUDIT}" FOR {command} TO {role} {clause}')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, *_ in AUDIT_POLICIES:
        op.execute(f'DROP POLICY IF EXISTS {name} ON "{AUDIT}"')
    op.execute(f'ALTER TABLE "{AUDIT}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{AUDIT}" DISABLE ROW LEVEL SECURITY')
    for table in reversed(list(POLICIES)):
        for policy in ("owner_maintenance", "platform_access", "tenant_isolation"):
            op.execute(f'DROP POLICY IF EXISTS {policy} ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    for name in (*FUNCTIONS, ORGLESS_EVENT):
        op.execute(f"DROP FUNCTION IF EXISTS {_signature(name)}")
