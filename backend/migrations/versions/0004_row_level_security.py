"""row-level security: the database refuses another organisation's rows

A second tenant wall behind the application's own ``organisation_id``
filters (app.tenancy): on PostgreSQL every organisation-scoped table gets
ENABLE and FORCE ROW LEVEL SECURITY (FORCE: the owner role is held to the
policies too) and a policy that lets a transaction see and write only the
rows of the organisation it acts for::

    organisation_id = current_setting('app.organisation_id', true)
    OR current_setting('app.scope', true) = 'platform'

The application sets ``app.organisation_id`` (a signed-in admin) or
``app.scope = 'platform'`` (the /platform routes, the expired-draft sweep, the
CLI) at the start of every transaction (app.db). With neither set, every
policy table answers no rows and refuses every write: it fails closed.

* Tables with ``organisation_id``: organisations (by ``id``), org_admins,
  organisation_applications, application_documents, employees, dependants,
  benefit_policies, receipt_files, payment_batches, claims.
* Tables keyed by ``admin_id`` (admin_sessions, recovery_codes, setup_tokens,
  login_throttles): through their admin's organisation (an EXISTS on
  org_admins, itself under its policy). No column is added: an admin never
  moves between organisations, so there is nothing to backfill or to drift.
* claim_items: through its claim's organisation, the same way.
* audit_events: SELECT and INSERT policies only (the app role has only those
  grants; with FORCE not even the owner can UPDATE or DELETE a row through
  SQL). Events without an organisation (a failed sign-in for an unknown email)
  can be appended by anyone and read only in the platform scope.
* Not covered: auth_failures (per-address sign-in counters, no organisation
  data, needed before any organisation is known) and alembic_version.

Before the organisation is known, four SECURITY DEFINER functions answer one
narrow question each, for one secret or key, in the platform scope for that
one query only (the caller's scope is put back before it returns): an admin's organisation by email (sign
in, and whether an email is taken), a session's organisation by its token
hash, a setup link's organisation by its token hash, and whether a TIN is
held by another active organisation. EXECUTE is revoked from PUBLIC;
migrations/env.py grants it to the app role.

Works on an existing database: nothing is added to or changed in any row.
Migrations run in the platform scope (migrations/env.py). The downgrade drops
the policies and functions and disables row-level security again.

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

TENANT = "NULLIF(current_setting('app.organisation_id', true), '')"
PLATFORM = "current_setting('app.scope', true) = 'platform'"

#: Each policy table and the condition its rows must meet (besides the platform scope).
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
POLICY = "tenant_isolation"
AUDIT_READ = "tenant_read"
AUDIT_APPEND = "tenant_append"

#: name(arguments) -> (return type, body). Each runs as the owner, in the platform scope.
FUNCTIONS = {
    "rls_admin_organisation(p_email text)": (
        "varchar", "SELECT organisation_id FROM org_admins WHERE email = p_email"),
    "rls_session_organisation(p_token_hash text)": (
        "varchar", "SELECT a.organisation_id FROM admin_sessions s JOIN org_admins a ON a.id = s.admin_id "
                   "WHERE s.token_hash = p_token_hash"),
    "rls_setup_link_organisation(p_token_hash text)": (
        "varchar", "SELECT a.organisation_id FROM setup_tokens t JOIN org_admins a ON a.id = t.admin_id "
                   "WHERE t.token_hash = p_token_hash"),
    "rls_tin_taken(p_tin text, p_organisation_id text)": (
        "boolean", "SELECT EXISTS (SELECT 1 FROM organisations WHERE tin = p_tin AND id <> p_organisation_id "
                   "AND status = 'active')"),
}


def _signature(name: str) -> str:
    """``f(p_a text, p_b text)`` -> ``f(text, text)``."""
    fn, _, args = name.partition("(")
    types = [arg.split()[-1] for arg in args.rstrip(")").split(",") if arg.strip()]
    return f"{fn}({', '.join(types)})"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, (returns, body) in FUNCTIONS.items():
        # The platform scope for the one query, then the caller's scope again
        # (a function's SET clause cannot name a custom parameter without a superuser).
        op.execute(f"""CREATE FUNCTION {name} RETURNS {returns} LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = public, pg_temp AS $fn$
DECLARE
  caller_scope text := current_setting('app.scope', true);
  answer {returns};
BEGIN
  PERFORM set_config('app.scope', 'platform', true);
  {body} INTO answer;
  PERFORM set_config('app.scope', coalesce(caller_scope, ''), true);
  RETURN answer;
END
$fn$""")
        op.execute(f"REVOKE ALL ON FUNCTION {_signature(name)} FROM PUBLIC")
    for table, condition in POLICIES.items():
        rule = f"({condition}) OR {PLATFORM}"
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY {POLICY} ON "{table}" FOR ALL USING ({rule}) WITH CHECK ({rule})')
    op.execute(f'ALTER TABLE "{AUDIT}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{AUDIT}" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY {AUDIT_READ} ON "{AUDIT}" FOR SELECT '
               f'USING (organisation_id = {TENANT} OR {PLATFORM})')
    op.execute(f'CREATE POLICY {AUDIT_APPEND} ON "{AUDIT}" FOR INSERT '
               f'WITH CHECK (organisation_id IS NULL OR organisation_id = {TENANT} OR {PLATFORM})')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS {AUDIT_APPEND} ON "{AUDIT}"')
    op.execute(f'DROP POLICY IF EXISTS {AUDIT_READ} ON "{AUDIT}"')
    op.execute(f'ALTER TABLE "{AUDIT}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{AUDIT}" DISABLE ROW LEVEL SECURITY')
    for table in reversed(list(POLICIES)):
        op.execute(f'DROP POLICY IF EXISTS {POLICY} ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    for name in FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {_signature(name)}")
