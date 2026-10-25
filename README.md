# TenaCare: the Endod employer benefits portal

organisation.endod-health.com. Company HR and benefits admins manage their
employees' medication coverage:

1. An employee pays at the pharmacy and brings the receipt.
2. HR enters the claim on **Claims → New Claim** with a photo or scan of the receipt.
3. HR approves it (or rejects it with a reason). Approval checks the benefit policy and
   pays back the organisation's share: the total minus the employee's co-pay, capped at
   what is left of the employee's annual limit.
4. On **Payments**, approved claims are grouped into a payout batch per method (CBE,
   Awash, Dashen or Telebirr). HR downloads the batch's file and pays it through the
   bank or Telebirr, then marks the batch paid with the bank's reference.
   **TenaCare never moves money.**

Only medication claims are handled. Claims are entered by HR for now. Claims that come
automatically from Endod pharmacy dispensing will follow once pharmacies record prices;
the seam for them is `backend/app/claims_intake.py`.

## Layout

| Path | What |
| --- | --- |
| `backend/` | The API: FastAPI, SQLAlchemy, Alembic, its own Postgres |
| `organisation-frontend/` | The web app: Next.js 16 (Habtamu Semagn's design), with a BFF under `app/api` |
| `deploy/` | `docker-compose.yml` (project `endod-organisation`), the Postgres role script, `.env.example` |
| `.github/workflows/ci.yml` | pytest on SQLite and PostgreSQL (with the role tests), lint, types, build, Playwright, Docker images |

The design follows the Endod super admin service (`endod-superadmin`).

## Security model

- **Organisations and admins exist only through the CLI** (run by Endod; no sign-up).
  Each admin belongs to exactly one organisation.
- **Tenant isolation**: every query of the portal API filters on the signed-in admin's
  organisation (`app/tenancy.py`). An id from another organisation answers `404 Not found.`,
  exactly like an id that does not exist. `backend/tests/test_tenancy.py` tries every
  route that takes an id with another organisation's ids.
- **Sign-in**: argon2id passwords and mandatory TOTP (Google Authenticator) with replay
  protection. Admins enrol through one-time setup links; there are 10 recovery codes.
  Failed sign-in steps lock out one account at one address (5 failures for 15 minutes),
  with per-account exponential backoff that never signs anyone out, and a per-address limit.
- **Sessions** are server-side, in an httpOnly, Secure, SameSite=Strict `__Host-` cookie,
  with a 30-minute idle timeout and a 12-hour absolute limit.
- **Re-authentication**: approving or rejecting a claim, marking a batch paid, and
  changing the policy (or an employee's own policy) or the payout settings each need a
  TOTP code given within the last 10 minutes.
- **BFF**: the browser talks only to the web app; the web app calls the API with
  `X-BFF-Secret` (the API refuses everything except `/health` without it) and passes
  the visitor's address from nginx's `X-Endod-Client-IP` (in production a request
  without it gets 503). Changes must come from this site (Origin, Sec-Fetch-Site, JSON).
- **Audit log**: every sign-in step and every change (with the organisation, admin, address,
  target and result) goes to `audit_events`, which the API's database role can only read
  and append to.
- **Database roles**: `org_owner` runs the migrations; the API connects as `org_app`
  (no DDL; `audit_events` is SELECT/INSERT only).
- **Money** is always an integer number of santim (1 ETB = 100 santim). There are no
  floats, in the API or in the web app.
- **Receipt files**: PDF, JPEG, PNG or WebP, recognised by their first bytes, at most
  10 MB, stored on a volume as `<organisation id>/<file id>`, served streamed with
  `nosniff`, a safe `Content-Disposition`, no caching, and every view audited.
- **CSV**: imports are previewed with per-row errors and are all-or-nothing; every
  exported cell is safe to open in a spreadsheet (formula injection).

## The approval rules

A claim is approved only when the employee (or the dependant) is active and covered,
the receipt date is within the current policy year, no medicine on it is excluded by the
policy, the receipt (pharmacy TIN plus receipt number) has not been approved before, and
something is left of the annual limit. Only approved claims can be batched, and a paid
batch never changes.

## Running it

### The API

```sh
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # Windows: .venv\Scripts\...
.venv/bin/alembic upgrade head          # SQLite at ./organisation.db in development
.venv/bin/python -m app.cli create-org --name "Tena Logistics PLC" --tin 0012345678
.venv/bin/python -m app.cli create-admin --org <the id it printed> --email hr@example.et --name "Selam Tesfaye"
.venv/bin/uvicorn app.main:app --port 8040
.venv/bin/python -m pytest -q
```

The admin opens the printed setup link, sets a password and enrols an authenticator app.
With `--password-stdin` the password is read from standard input instead (never from the
command line) and the setup link asks for it. Other commands: `reset-2fa --email`,
`disable --email`, `list-orgs`, `list-admins [--org]`.

### The web app

```sh
cd organisation-frontend
npm ci
npm run dev            # http://localhost:3000; ORG_API_URL defaults to http://127.0.0.1:8040
npx playwright test    # builds nothing itself: run `npx next build` first; uses the installed Chrome
```

### Production

```sh
cd deploy && cp .env.example .env   # fill it in
docker compose --env-file .env up -d --build
docker compose exec api python -m app.cli create-org --name "..." --tin ...
docker compose exec api python -m app.cli create-admin --org <id> --email ... --name "..."
```

The web container joins the shared nginx edge network (`${SHARED_NGINX_NETWORK:-eyita_edge}`)
as `endod-organisation`. nginx terminates TLS for organisation.endod-health.com, sets
`X-Endod-Client-IP` and proxies to `http://endod-organisation:3000`.

## Notes on `organisation-frontend/INTEGRATION_GUIDE.md`

It is background for the later integrations, and partly out of date: the Endod patient
platform does have authentication, and pharmacies do not record prices yet (so claims
cannot come from dispensing records today).
