#!/bin/sh
# The platform role (row-level security, migrations 0004+). Runs after
# 10-roles.sh when the postgres volume is first created; on an existing
# database run it by hand, as the superuser, BEFORE `alembic upgrade head`:
#   docker compose exec -T postgres sh -s < postgres-init/20-platform-role.sh
# (POSTGRES_USER and POSTGRES_DB are set in the container). Idempotent.
#
#   org_platform  NOLOGIN. The row-level security policies let it see and
#                 write every organisation's rows; no other role has such a
#                 policy. org_app is a member WITH INHERIT FALSE: it gets none
#                 of org_platform's rights by default, only after an explicit
#                 `SET LOCAL ROLE org_platform` (app.db.platform_session: the
#                 /platform routes, the expired-draft sweep and the CLI).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'org_platform') THEN
    CREATE ROLE org_platform NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
END
$$;
ALTER ROLE org_platform NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO org_platform;
-- Revoke first: an earlier grant with other options is replaced, not kept.
REVOKE org_platform FROM org_app;
GRANT org_platform TO org_app WITH INHERIT FALSE, SET TRUE;
ALTER DEFAULT PRIVILEGES FOR ROLE org_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO org_platform;
EOSQL
