"""integration API: connected systems, used assertions, request log, idempotency, webhook deliveries

The tables of the integration API for companies' own systems
(app/integrations, docs/integrations.md). New tables only; nothing else is
touched:

* ``integration_clients``: connected systems (OAuth 2.0 client credentials:
  an argon2id hash of the secret, or public keys; the webhook URL and its
  sealed signing secret);
* ``integration_assertions``: the ``jti`` of each client assertion used,
  until it expires (each is used once);
* ``integration_requests``: the request log (never a body; kept 30 days);
* ``integration_idempotency``: answers replayed for an Idempotency-Key;
* ``webhook_deliveries``: events waiting for, or sent to, a client's webhook;
* ``integration_payout_changes``: payout accounts a client changed (masked),
  held out of payout batches for 24 hours unless an admin confirms them.

Every table has ``organisation_id``. The ones that belong to a client point
at it with a same-organisation composite key, (organisation_id, client_pk)
-> integration_clients (organisation_id, id), like migration 0005; a payout
change points at its employee the same way.

On PostgreSQL each gets row-level security exactly like migration 0004
(ENABLE, FORCE, ``tenant_isolation``, ``platform_access`` for
``org_platform``, ``owner_maintenance``), and the token endpoint gets one
SECURITY DEFINER look-up, ``rls_integration_client_organisation``: the
organisation id of a client by its public client_id, and only for a live
client (not disconnected) of an organisation that is active and approved (no
application, or an approved one); NULL for anything else, and nothing but
that id. Like 0004's: ``search_path`` pinned to ``public, pg_temp``, run in
the owner's maintenance scope for its one query (the caller's scope put
back), EXECUTE revoked from PUBLIC (migrations/env.py grants it to the app
role only). The definitions are frozen copies of 0004's helpers.

Downgrading drops the function, the policies and the tables (every connected
system stops working).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-28 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

PLATFORM_ROLE = "org_platform"
TENANT = "NULLIF(current_setting('app.organisation_id', true), '')"
MAINTENANCE = "current_setting('app.scope', true) = 'maintenance'"
TABLES = ("integration_clients", "integration_assertions", "integration_requests", "integration_idempotency",
          "webhook_deliveries", "integration_payout_changes")
LOOKUP = "rls_integration_client_organisation(p_client_id text)"
LOOKUP_QUERY = ("SELECT c.organisation_id FROM integration_clients c "
                "JOIN organisations o ON o.id = c.organisation_id "
                "LEFT JOIN organisation_applications a ON a.organisation_id = c.organisation_id "
                "WHERE c.client_id = p_client_id AND c.revoked_at IS NULL AND o.status = 'active' "
                "AND (a.organisation_id IS NULL OR a.status = 'approved')")


def _signature(name: str) -> str:
    fn, _, args = name.partition("(")
    types = [arg.split()[-1] for arg in args.rstrip(")").split(",") if arg.strip()]
    return f"{fn}({', '.join(types)})"


def _definer(name: str, returns: str, query: str) -> None:
    """As migration 0004: runs as the owner, in the maintenance scope for this one query."""
    op.execute(f"""CREATE FUNCTION {name} RETURNS {returns} LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = public, pg_temp AS $fn$
DECLARE
  caller_scope text := current_setting('app.scope', true);
  answer {returns};
BEGIN
  PERFORM set_config('app.scope', 'maintenance', true);
  {query} INTO answer;
  PERFORM set_config('app.scope', coalesce(caller_scope, ''), true);
  RETURN answer;
END
$fn$""")
    op.execute(f"REVOKE ALL ON FUNCTION {_signature(name)} FROM PUBLIC")


def _organisation(table):
    return (sa.Column('organisation_id', sa.String(length=32), nullable=False),
            sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'],
                                    name=op.f(f'fk_{table}_organisation_id_organisations')))


def _client(table, name):
    return (sa.Column('client_pk', sa.String(length=32), nullable=False),
            sa.ForeignKeyConstraint(['organisation_id', 'client_pk'],
                                    ['integration_clients.organisation_id', 'integration_clients.id'],
                                    name=name, ondelete='CASCADE'))


def _when(name, nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _index(table):
    op.create_index(op.f(f'ix_{table}_organisation_id'), table, ['organisation_id'], unique=False)


def upgrade() -> None:
    org, org_fk = _organisation('integration_clients')
    op.create_table(
        'integration_clients',
        sa.Column('id', sa.String(length=32), nullable=False), org,
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('scopes', sa.String(length=400), nullable=False),
        sa.Column('mode', sa.String(length=4), nullable=False),
        sa.Column('auth_method', sa.String(length=20), nullable=False),
        sa.Column('secret_hash', sa.String(length=255), nullable=True),
        sa.Column('jwks', sa.Text(), nullable=True),
        sa.Column('allowed_cidrs', sa.String(length=2000), nullable=True),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('webhook_secret', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=True),
        _when('created_at'), _when('last_used_at', True), _when('credentials_changed_at', True),
        _when('revoked_at', True),
        sa.CheckConstraint("mode IN ('live', 'test')", name=op.f('ck_integration_clients_mode')),
        sa.CheckConstraint("auth_method IN ('client_secret', 'private_key_jwt')",
                           name=op.f('ck_integration_clients_auth_method')),
        org_fk,
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_clients')),
        sa.UniqueConstraint('client_id', name=op.f('uq_integration_clients_client_id')),
        sa.UniqueConstraint('organisation_id', 'id', name='uq_integration_clients_org_id'),
    )
    _index('integration_clients')

    org, org_fk = _organisation('integration_assertions')
    client, client_fk = _client('integration_assertions', 'fk_integration_assertions_client_same_org')
    op.create_table(
        'integration_assertions',
        sa.Column('id', sa.String(length=32), nullable=False), org, client,
        sa.Column('jti', sa.String(length=255), nullable=False),
        _when('expires_at'),
        org_fk, client_fk,
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_assertions')),
        sa.UniqueConstraint('client_pk', 'jti', name='uq_integration_assertions_client_jti'),
    )
    _index('integration_assertions')

    org, org_fk = _organisation('integration_requests')
    client, client_fk = _client('integration_requests', 'fk_integration_requests_client_same_org')
    op.create_table(
        'integration_requests',
        sa.Column('id', sa.String(length=32), nullable=False), org, client,
        sa.Column('method', sa.String(length=8), nullable=False),
        sa.Column('path', sa.String(length=300), nullable=False),
        sa.Column('status', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('ip', sa.String(length=64), nullable=True),
        _when('at'),
        org_fk, client_fk,
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_requests')),
    )
    _index('integration_requests')
    op.create_index('ix_integration_requests_client_at', 'integration_requests', ['client_pk', 'at'], unique=False)

    org, org_fk = _organisation('integration_idempotency')
    client, client_fk = _client('integration_idempotency', 'fk_integration_idempotency_client_same_org')
    op.create_table(
        'integration_idempotency',
        sa.Column('id', sa.String(length=32), nullable=False), org, client,
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        _when('created_at'),
        org_fk, client_fk,
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_idempotency')),
        sa.UniqueConstraint('client_pk', 'key', name='uq_integration_idempotency_client_key'),
    )
    _index('integration_idempotency')

    org, org_fk = _organisation('webhook_deliveries')
    client, client_fk = _client('webhook_deliveries', 'fk_webhook_deliveries_client_same_org')
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.String(length=32), nullable=False), org, client,
        sa.Column('event_id', sa.String(length=40), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        _when('next_attempt_at', True), _when('last_attempt_at', True),
        sa.Column('last_status_code', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.String(length=200), nullable=True),
        _when('created_at'), _when('delivered_at', True),
        sa.CheckConstraint("status IN ('pending', 'delivered', 'failed')", name=op.f('ck_webhook_deliveries_status')),
        org_fk, client_fk,
        sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_deliveries')),
    )
    _index('webhook_deliveries')
    op.create_index('ix_webhook_deliveries_due', 'webhook_deliveries', ['status', 'next_attempt_at'], unique=False)
    op.create_index('ix_webhook_deliveries_client', 'webhook_deliveries', ['client_pk', 'created_at'], unique=False)

    org, org_fk = _organisation('integration_payout_changes')
    client, client_fk = _client('integration_payout_changes', 'fk_integration_payout_changes_client_same_org')
    op.create_table(
        'integration_payout_changes',
        sa.Column('id', sa.String(length=32), nullable=False), org,
        sa.Column('employee_id', sa.String(length=32), nullable=False), client,
        sa.Column('before_method', sa.String(length=16), nullable=True),
        sa.Column('before_account', sa.String(length=12), nullable=True),
        sa.Column('after_method', sa.String(length=16), nullable=True),
        sa.Column('after_account', sa.String(length=12), nullable=True),
        _when('created_at'), _when('hold_until'), _when('confirmed_at', True),
        sa.Column('confirmed_by', sa.String(length=32), nullable=True),
        org_fk, client_fk,
        sa.ForeignKeyConstraint(['organisation_id', 'employee_id'], ['employees.organisation_id', 'employees.id'],
                                name='fk_integration_payout_changes_employee_same_org', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_integration_payout_changes')),
    )
    _index('integration_payout_changes')
    op.create_index('ix_integration_payout_changes_employee', 'integration_payout_changes',
                    ['employee_id', 'hold_until'], unique=False)

    if op.get_bind().dialect.name != "postgresql":
        return
    _definer(LOOKUP, "varchar", LOOKUP_QUERY)
    condition = f"organisation_id = {TENANT}"
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY tenant_isolation ON "{table}" FOR ALL TO PUBLIC '
                   f'USING ({condition}) WITH CHECK ({condition})')
        op.execute(f'CREATE POLICY platform_access ON "{table}" FOR ALL TO {PLATFORM_ROLE} '
                   f'USING (true) WITH CHECK (true)')
        op.execute(f'CREATE POLICY owner_maintenance ON "{table}" FOR ALL TO CURRENT_USER '
                   f'USING ({MAINTENANCE}) WITH CHECK ({MAINTENANCE})')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP FUNCTION IF EXISTS {_signature(LOOKUP)}")
        for table in reversed(TABLES):
            for policy in ("owner_maintenance", "platform_access", "tenant_isolation"):
                op.execute(f'DROP POLICY IF EXISTS {policy} ON "{table}"')
    for table in ('integration_payout_changes', 'webhook_deliveries', 'integration_idempotency', 'integration_requests', 'integration_assertions',
                  'integration_clients'):
        op.drop_table(table)  # its indexes and keys go with it
