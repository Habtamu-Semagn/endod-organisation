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

- **Organisations** are made by Endod with the CLI (approved at once), or by a company
  applying itself (**Apply as a company** on the sign-in page; see below). Each admin
  belongs to exactly one organisation.
- **Company applications** (`docs/company-onboarding.md`, the contract with the super
  admin): the first step creates the organisation (a draft application) and its first
  admin, who signs in with the password only and reaches nothing but the application;
  then the company's details, three documents (trade licence, TIN certificate,
  authorization letter; checked like receipts), review and submit. Each step is saved, and
  the wizard resumes after sign-in. Applications are limited per address (5 an hour by
  default, `ORG_APPLICATIONS_PER_IP`), and refused from an address the sign-in limit has
  blocked. Only an approved, active organisation holds a TIN: an applicant is refused it
  with one generic message (probing TINs counts against the address), while other
  applications with the same TIN are allowed (no squatting) and flagged to Endod as
  `duplicate_tin`. Emails are not verified (`email_verified: false`), so drafts not
  submitted within 14 days are deleted with their admins, sessions and documents (audited
  as `application_expired`); with no worker in this deployment, the sweep runs when an
  application is started, when Endod lists applications and at sign-in. **Until
  Endod approves it, the organisation is locked**: its admins reach only the application,
  the Under review page and sign-out; every other API route answers 403
  (`APPLICATION_NOT_APPROVED`, `backend/app/auth.py` `current_admin`). A rejected
  application shows Endod's reason and can be fixed and resubmitted; a *closed* one
  (rejected with `close: true`) is final: its admins see only that and sign-out.
- **Platform API** (`/platform/*`, `backend/app/api/platform.py`): Endod's super admin lists,
  reads, approves and rejects applications, downloads their documents, and lists, suspends
  and reactivates organisations. It is reached only over the `endod-bus` network
  (`endod-organisation-api:8000`) with `X-Platform-Key` equal to `ORG_PLATFORM_KEY`
  (compared in constant time; unset or shorter than 32 characters: 503). It does not take
  the BFF secret, the BFF secret does not open it, and the web app's BFF never passes
  `platform/` paths on. Approval names the version the reviewer saw
  (`expected_updated_at`, compared exactly under the lock; every applicant edit moves
  `updated_at`), else 409. Every changing path locks the organisation, then the
  application (`onboarding.lock_for_change`), so they cannot deadlock. Approving,
  rejecting, closing, suspending and reactivating are audited with the reviewer's email. Suspending signs the organisation's admins out and refuses
  their sign-in with the usual generic message.
- **Tenant isolation**: every query of the portal API filters on the signed-in admin's
  organisation (`app/tenancy.py`). An id from another organisation answers `404 Not found.`,
  exactly like an id that does not exist. `backend/tests/test_tenancy.py` tries every
  route that takes an id with another organisation's ids.
- **Row-level security** (PostgreSQL, migrations 0004 and 0005): a second wall in the
  database. Every organisation-scoped table has ENABLE and FORCE ROW LEVEL SECURITY and a
  policy that shows and accepts only the rows of the organisation the transaction acts
  for (`app.organisation_id`, set at the start of every transaction by `app/db.py`). With
  none set, a table shows nothing and takes nothing. Only the NOLOGIN role `org_platform`
  has a policy over every row: `platform_session()` (the `/platform` routes, the
  expired-draft sweep, the CLI) runs `SET LOCAL ROLE org_platform`; `org_app` is its
  member WITH INHERIT FALSE, so nothing else it runs gets those rows, and no setting
  (`app.scope` or any other) opens them. Sign-in, session tokens and setup links learn
  their organisation from one SECURITY DEFINER function each, which answers only for a
  live key (an active admin, a session neither revoked nor expired, an unused unexpired
  link); whether an email or a TIN is taken is a yes or no (`app/rls.py`). A tenant
  appends only its own organisation's audit events; one of no organisation goes through
  one more such function. Composite foreign keys on `(organisation_id, id)` make a claim,
  dependant, policy override or application contact point only at rows of its own
  organisation. Migrations stop unless `org_app` and `org_platform` exist and neither is a
  superuser or BYPASSRLS; the API refuses to start if its role is a superuser, BYPASSRLS,
  owns the tables or inherits `org_platform`. `backend/tests/test_rls.py` and
  `test_same_org_keys.py` check every policy table and key.

  **What remains**: the wall is against a query that forgets its filter, not against SQL
  injection. Any SQL the API runs as `org_app` can still `SET ROLE org_platform`, or set
  `app.organisation_id` to another organisation's id, so injection is as serious as
  before and every query stays parameterised. A secret checked by a SECURITY DEFINER
  function before the platform scope opens was considered and not done: injected SQL
  could still switch to any organisation whose id it learns through the tenant setting,
  so closing the gap properly means signing the tenant context too (an HMAC of the
  organisation id with a key only the API holds, verified in every policy), with that key
  shared by the API and the migrations. That is a larger change, left for later.
- **Sign-in**: argon2id passwords and mandatory TOTP (Google Authenticator) with replay
  protection. Admins enrol through one-time setup links; there are 10 recovery codes.
  A company's applicant uses the password only until Endod approves the company; approval
  signs out every admin of the organisation (audited), and the applicant's next sign-in
  enrols an authenticator before anything else.
  Failed sign-in steps lock out one account at one address (5 failures for 15 minutes),
  with per-account exponential backoff that never signs anyone out, and a per-address limit.
- **Sessions** are server-side, in an httpOnly, Secure, SameSite=Strict `__Host-` cookie,
  with a 30-minute idle timeout and a 12-hour absolute limit.
- **Re-authentication**: approving or rejecting a claim, creating, cancelling or marking
  paid a payout batch, changing payout accounts, importing employees, and changing the
  policy (or an employee's own policy) or the payout settings each need a TOTP code given
  within the last 10 minutes.
- **BFF**: the browser talks only to the web app; the web app calls the API with
  `X-BFF-Secret` (the API refuses everything except `/health` without it) and passes
  the visitor's address from nginx's `X-Endod-Client-IP` (in production a request
  without it gets 503). Changes must come from this site (Origin, Sec-Fetch-Site, JSON).
- **Only our nginx reaches the web app**: nginx adds `X-Endod-Edge-Key` (the value of
  `EDGE_SHARED_SECRET`) to every request; the web app (`proxy.ts`) answers 403 to anything
  without it, so another container on the shared edge network cannot call it directly and
  choose `X-Endod-Client-IP`. Only the container's own health check (`/api/health` asked of
  127.0.0.1) needs no key. In production (an https `SITE_ORIGIN`) a missing or short
  secret makes every request a 503. nginx: `proxy_set_header X-Endod-Edge-Key "<secret>";`
  next to `proxy_set_header X-Endod-Client-IP ...;`.
- **Throttling of codes**: wrong TOTP or recovery codes count per account across all
  addresses too; from 5 within 15 minutes, code attempts for that account wait 30 s,
  60 s, ... up to 15 minutes (audited as `account_code_backoff`; nobody is signed out).
  Per-address limits count an IPv6 address by its /64.
- **Payout accounts**: adding or changing an employee's payout method or account (by hand or
  by CSV import), and creating or cancelling a payout batch, need a fresh code. The audit
  log records each payout change with the old and new accounts masked to their last 4
  digits. Once a batch's file has been downloaded it can no longer be cancelled (only
  marked paid), so its claims can never be batched and paid twice; the file uses the
  accounts recorded when the batch was made. A claim with nothing to reimburse (a 100%
  co-pay) is approved but never goes into a batch.
- **Audit log**: every sign-in step and every change (with the organisation, admin, address,
  target and result) goes to `audit_events`, which the API's database role can only read
  and append to.
- **Database roles** (`deploy/postgres-init`): `org_owner` runs the migrations (in its own
  maintenance scope, since the policies are forced on the owner too); the API connects
  as `org_app` (no DDL; `audit_events` is SELECT/INSERT only; held to the row-level
  security policies); `org_platform` (NOLOGIN) is what the platform scope runs as.
- **Expired drafts** are swept by a background task of the API and when Endod lists
  applications, at most once per `ORG_SWEEP_INTERVAL_SECONDS` and one sweep at a time
  (an advisory lock), or by `python -m app.cli sweep-drafts`; never on a public request.
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

The API container also joins the external `endod-bus` network (`docker network create
endod-bus` once per host) as `endod-organisation-api`, keeping its default network for
Postgres. Set `ORG_PLATFORM_KEY` (at least 32 random characters) in `deploy/.env` and give
the super admin the same value as its `ORGANISATION_PLATFORM_KEY`, with
`ORGANISATION_API_URL=http://endod-organisation-api:8000`.

**Upgrading an existing database to row-level security** (0004 and 0005): the platform
role must exist first; the init scripts only run on a new volume. As the superuser, once:

```sh
cd deploy && git pull
docker compose exec -T postgres sh -s < postgres-init/20-platform-role.sh
docker compose --env-file .env up -d --build   # `migrate` runs 0004 and 0005 as org_owner, then the API starts
```

**Rolling back row-level security** (to 0003) needs the 0003-era *code* as well as the
schema: the current code calls the 0004 look-up functions (sign-in fails without them),
while the 0003-era image cannot downgrade (it has no 0004 or 0005 scripts). So stop the
API, downgrade with the current image, then roll the image back:

```sh
cd deploy
docker compose stop web api
docker compose --env-file .env run --rm migrate alembic downgrade 0003   # current image: knows 0004/0005
git checkout <the last commit before row-level security>                  # e.g. cff4790
docker compose --env-file .env up -d --build   # 0003-era images; `migrate` finds head (0003) already there
```

**Rolling back below migration 0003** (`alembic downgrade 0002`) is refused while any
company application is not approved: without its application such an organisation would
count as approved. Approve, close or delete those applications first.

## Notes on `organisation-frontend/INTEGRATION_GUIDE.md`

It is background for the later integrations, and partly out of date: the Endod patient
platform does have authentication, and pharmacies do not record prices yet (so claims
cannot come from dispensing records today).
