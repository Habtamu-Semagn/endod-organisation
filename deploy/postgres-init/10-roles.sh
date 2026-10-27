#!/bin/sh
# Runs once, when the postgres volume is first created (docker-entrypoint-initdb.d).
# Run by hand against an existing database the same way:
#   POSTGRES_USER=... POSTGRES_DB=... ORG_OWNER_PASSWORD=... ORG_APP_PASSWORD=... sh 10-roles.sh
#
# Two roles besides the superuser:
#   org_owner  owns the database and its schema; only the one-shot `migrate`
#              service connects as it (Alembic creates and alters the tables).
#   org_app    what the API connects as: read and write on the app tables,
#              but only SELECT and INSERT on audit_events (no UPDATE, DELETE
#              or TRUNCATE: the API cannot rewrite or erase the audit log),
#              and no DDL at all. Neither role bypasses row-level security
#              (migration 0004): org_app sees one organisation per transaction.
# Tables created later by org_owner get the app grants by default (below);
# migrations/env.py then sets them exactly after every upgrade.
set -eu

: "${ORG_OWNER_PASSWORD:?set ORG_OWNER_PASSWORD}"
: "${ORG_APP_PASSWORD:?set ORG_APP_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v owner_pw="$ORG_OWNER_PASSWORD" -v app_pw="$ORG_APP_PASSWORD" -v db="$POSTGRES_DB" <<'EOSQL'
CREATE ROLE org_owner LOGIN PASSWORD :'owner_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE org_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

ALTER DATABASE :"db" OWNER TO org_owner;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO org_owner, org_app;

ALTER SCHEMA public OWNER TO org_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO org_app;

ALTER DEFAULT PRIVILEGES FOR ROLE org_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO org_app;
ALTER DEFAULT PRIVILEGES FOR ROLE org_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO org_app;
EOSQL
