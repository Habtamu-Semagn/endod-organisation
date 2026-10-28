# Endod Organisation Integration API

Connect your company's own system (HR, payroll, ERP) to TenaCare, the Endod
employer benefits portal: keep the employee list in sync from your HR system, read
claims and their status, read payout batches, and get notified when claims are
approved or rejected, when a batch is paid and when an employee changes.

This is HR data, so the API speaks plain JSON (not FHIR). Amounts are integers in
**santim** (1 ETB = 100 santim).

- **Base URL:** `https://api.endod-health.com/organisation/v1`
- **Token URL:** `https://api.endod-health.com/organisation/v1/oauth/token`
- **Signing keys of access tokens:** `https://api.endod-health.com/organisation/v1/.well-known/jwks.json`
- **OpenAPI:** `https://api.endod-health.com/organisation/v1/openapi.json` (this guide, with every
  endpoint, at `/docs`)

Only organisations approved by Endod can connect a system; a suspended
organisation's connections stop working at once.

## 1. Connect your system (in the portal)

An administrator opens **Connect your system** in the TenaCare portal and clicks
**Connect a system**:

1. a name (e.g. "Payroll system");
2. what it may do (each is a *scope* in this API):

   | In the portal | Scope | Gives |
   |---|---|---|
   | Sync employees from your HR system | `employees.write` | `POST /employees`, `POST /employees/{employee_number}/deactivate` |
   | See employee list | `employees.read` | `GET /employees`, `GET /employees/{employee_number}` |
   | See claims and their status | `claims.read` | `GET /claims`, `GET /claims/{id}` |
   | See payments | `payments.read` | `GET /payments/batches`, `GET /payments/batches/{id}` |
   | Get notified when claims are approved or paid | `webhooks` | events sent to your webhook URL |

   and **Live** (real data) or **Test** (everything is checked, nothing is stored);
3. the **client ID** and **client secret**, shown once. Save the secret in your
   system's secret store now: Endod keeps only a hash of it and cannot show it again
   (an administrator can rotate it). "Download setup guide" prints the connection's
   details (never the secret).

Under **Advanced** an administrator can limit the addresses the system may call
from, switch it to public-key authentication, rotate the secret, set the webhook
URL and its secret, send a test event, and see recent requests and webhook
deliveries. Connecting, rotating, disconnecting and every change under Advanced ask
the administrator for a fresh code from their authenticator app, and are audited.

## 2. Get an access token

OAuth 2.0 client credentials. Tokens are JWTs signed ES256 (the `kid` in their
header names the key at `/.well-known/jwks.json`), valid **5 minutes**: get a new
one when it expires (`expires_in`), not for every request.

### With the client secret (HTTP Basic, preferred)

```bash
curl -s https://api.endod-health.com/organisation/v1/oauth/token \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d grant_type=client_credentials \
  -d "scope=employees.write employees.read"
```

or with the credentials in the form (`client_secret_post`):

```bash
curl -s https://api.endod-health.com/organisation/v1/oauth/token \
  -d grant_type=client_credentials \
  -d client_id="$CLIENT_ID" --data-urlencode client_secret="$CLIENT_SECRET"
```

```json
{"access_token": "eyJhbGciOiJFUzI1NiIs...", "token_type": "Bearer", "expires_in": 300,
 "scope": "employees.write employees.read"}
```

`scope` is optional (space-separated); without it the token carries every scope
granted to the connection. Asking for a scope not granted is refused (`invalid_scope`).

### With a private key (`private_key_jwt`)

Make an EC P-256 (ES256) or RSA 2048+ (RS256) key pair, keep the private key in your
system, and paste the **public** key set (JWKS) under Advanced, "Use a public key
instead". The secret then stops working.

Each token request carries a fresh signed assertion:

- header: `alg` ES256 or RS256, `kid` of your key;
- `iss` and `sub`: your client ID; `aud`: the token URL;
- `exp`: at most 5 minutes ahead; `jti`: unique, never reused (a replay is refused).

```python
import time, uuid, jwt, requests   # PyJWT
TOKEN_URL = "https://api.endod-health.com/organisation/v1/oauth/token"
assertion = jwt.encode({"iss": CLIENT_ID, "sub": CLIENT_ID, "aud": TOKEN_URL,
                        "exp": int(time.time()) + 240, "jti": uuid.uuid4().hex},
                       PRIVATE_KEY_PEM, algorithm="ES256", headers={"kid": "my-key-1"})
token = requests.post(TOKEN_URL, data={
    "grant_type": "client_credentials", "scope": "employees.write",
    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    "client_assertion": assertion}).json()["access_token"]
```

### Refusals

| HTTP | `error` | Why |
|---|---|---|
| 400 | `unsupported_grant_type` | `grant_type` is not `client_credentials` |
| 400 | `invalid_request` | malformed request, or two authentication methods |
| 401 | `invalid_client` | unknown or disconnected client, wrong secret, bad assertion (signature, `aud`, `exp`, reused `jti`), or a call from an address not allowed |
| 400 | `unauthorized_client` | the organisation is not approved by Endod, or is suspended |
| 400 | `invalid_scope` | a scope not granted to the connection |
| 429 | `slow_down` | too many token requests (see Limits); wait `Retry-After` seconds |
| 503 | `temporarily_unavailable` | the API is not available |

## 3. Employees

Employees are identified by their **employee number** (`employee_number`, 1 to 40
letters, digits, `/`, `-`, `_` or `.`), unique within your organisation. The fields
are those of the Employees screen in the portal:

| Field | |
|---|---|
| `employee_number` | required |
| `name` | 2 to 120 characters; required for a new employee |
| `phone` | an Ethiopian mobile number (`0911223344`, `+251911223344`); required for a new employee |
| `department` | required for a new employee |
| `endod_id` | the Endod health card ID (`DE` and 6 digits), optional, unique in the organisation |
| `active` | `true` or `false` (default `true` for a new employee) |
| `payout_method`, `payout_account` | `cbe`, `awash`, `dashen` (an 8 to 20 digit account) or `telebirr` (the wallet's mobile number); send both, or both `null` to remove them |
| `dependants` | the employee's covered dependants: `[{"name", "relationship" (spouse, child, parent, other), "birth_date" (YYYY-MM-DD, optional)}]` |

### Add or update employees (`employees.write`)

```bash
curl -s https://api.endod-health.com/organisation/v1/employees \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "Idempotency-Key: payroll-sync-2026-10-28" \
  -d '{"employees": [
        {"employee_number": "ET-0042", "name": "Abebe Kebede", "phone": "0911223344",
         "department": "Operations", "endod_id": "DE100042",
         "payout_method": "cbe", "payout_account": "1000123456789",
         "dependants": [{"name": "Liya Abebe", "relationship": "child", "birth_date": "2016-02-01"}]},
        {"employee_number": "ET-0043", "department": "Finance"}
      ]}'
```

```json
{"mode": "live", "stored": true,
 "summary": {"create": 1, "update": 1, "unchanged": 0, "error": 0},
 "results": [
   {"index": 0, "employee_number": "ET-0042", "action": "create", "employee_id": "5f0c...",
    "changes": ["department", "employee_number", "endod_id", "name", "payout_account", "payout_method", "phone",
                "dependants"], "errors": []},
   {"index": 1, "employee_number": "ET-0043", "action": "update", "employee_id": "9a1e...",
    "changes": ["department"], "errors": []}]}
```

- **Upsert by employee number:** an unknown number adds the employee; a known one
  updates it. A field you leave out stays as it is; `dependants`, when you send it,
  is the employee's whole list (dependants not in it stop being covered).
- **Idempotent:** sending the same employees again changes nothing (`"unchanged"`),
  so you can send your whole roster every night.
- **All or nothing:** every row is checked first; with any error nothing changes and
  the answer is `422` with each row's `errors` (`error_code: INVALID_EMPLOYEES`).
- At most **500 employees** per request: send larger rosters in several requests.
- Changes of payout details are audited like the portal's (accounts masked to their
  last 4 digits).

### Deactivate an employee (`employees.write`)

```bash
curl -s -X POST https://api.endod-health.com/organisation/v1/employees/ET-0042/deactivate \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"mode": "live", "stored": true, "employee_number": "ET-0042", "employee_id": "5f0c...", "action": "deactivate"}
```

Their claims stay; they can no longer claim. Deactivating an inactive employee
answers `"action": "unchanged"`. Reactivate with `"active": true` in a sync.

### Read employees (`employees.read`)

```bash
curl -s "https://api.endod-health.com/organisation/v1/employees?status=active&limit=100&offset=0" \
  -H "Authorization: Bearer $TOKEN"
curl -s https://api.endod-health.com/organisation/v1/employees/ET-0042 -H "Authorization: Bearer $TOKEN"
```

`status` is `active`, `inactive` or `all` (default); `updated_since` (an ISO 8601 time
with an offset) returns only employees changed since; `limit` is at most 500. Lists
answer `{"items": [...], "total", "limit", "offset", "has_more"}`, in employee number
order.

## 4. Claims (`claims.read`)

```bash
curl -s "https://api.endod-health.com/organisation/v1/claims?status=approved&from=2026-10-01&to=2026-10-31" \
  -H "Authorization: Bearer $TOKEN"
curl -s https://api.endod-health.com/organisation/v1/claims/$CLAIM_ID -H "Authorization: Bearer $TOKEN"
```

Filters: `status` (`pending`, `approved`, `rejected`, `paid`), `employee_number`,
`from` and `to` (receipt dates), `limit`, `offset`; newest first. A claim:

```json
{"id": "3b7d...", "code": "CLM-000123", "status": "approved", "source": "manual",
 "employee_id": "5f0c...", "employee_number": "ET-0042", "dependant_id": null,
 "pharmacy_name": "Kenema Pharmacy Bole", "pharmacy_tin": "0012345678", "receipt_number": "FS-00981",
 "receipt_date": "2026-10-15", "total_santim": 100000, "copay_santim": 10000, "approved_santim": 90000,
 "rejection_reason": null, "has_receipt": true, "created_at": "...", "reviewed_at": "...",
 "batch_id": null, "paid_at": null}
```

`GET /claims/{id}` adds the medicines (`items`). Receipt files are never available
through the API.

## 5. Payments (`payments.read`)

```bash
curl -s "https://api.endod-health.com/organisation/v1/payments/batches?status=paid" -H "Authorization: Bearer $TOKEN"
curl -s https://api.endod-health.com/organisation/v1/payments/batches/$BATCH_ID -H "Authorization: Bearer $TOKEN"
```

A batch: `id`, `code` (`BATCH-0007`), `status` (`open`, `paid`), `method` (`cbe`,
`awash`, `dashen`, `telebirr`), `claim_count`, `total_santim`, `created_at`,
`exported_at`, `paid_at`, `reference` (the bank's, once paid). One batch adds its
`claims` (id, code, employee, amount). Payout account numbers are not included:
the bank file stays in the portal. TenaCare never moves money.

## 6. Test mode

A **Test** connection (client ID `endod_test_...`) gets the same checks and the same
answers as a live one, with `"mode": "test"` and `"stored": false`, and **stores
nothing**: no employee is added or changed, no event is sent, no Idempotency-Key is
kept. Reads show your real data. Use it to try your integration before switching to
a Live connection.

## 7. Webhooks (`webhooks`)

Endod POSTs JSON events to your webhook URL (https only, a public address):

| Event | When |
|---|---|
| `claim.approved` | a claim was approved |
| `claim.rejected` | a claim was rejected |
| `batch.paid` | a payout batch was marked paid (its claims are paid) |
| `employee.changed` | an employee was added, updated, deactivated or reactivated (in the portal or through the API; `data.change` says which) |
| `endpoint.test` | "Send test event" in the portal |

```json
{"id": "evt_8c1f...", "type": "claim.approved", "created": "2026-10-28T06:00:00+00:00",
 "organisation_id": "...", "mode": "live",
 "data": {"claim_id": "3b7d...", "code": "CLM-000123", "status": "approved", "employee_id": "5f0c...",
          "employee_number": "ET-0042", "total_santim": 100000, "approved_santim": 90000,
          "reviewed_at": "2026-10-28T05:59:58+00:00"}}
```

Events are thin (ids, numbers, statuses, amounts, times; never names, phone numbers,
accounts or medicines): read the rest with the read scopes. Answer any **2xx** within
10 seconds. Anything else, a timeout or a redirect (never followed) is retried with
backoff (1 min, 5 min, 15 min, 30 min, 1 h, 2 h, 4 h, then every 6 h) for up to
**24 hours**; then the event is dropped. Events can arrive more than once and out of
order: use `id` to skip repeats.

### Verify the signature

Every event has `Endod-Signature: t=<unix time>,v1=<hex>`, where `<hex>` is the
HMAC-SHA256 of `"<t>.<raw body>"` under your webhook secret (`whsec_...`, shown once
in the portal). Compare in constant time, against the **raw** body, and refuse
events older than 5 minutes.

Python:

```python
import hashlib, hmac, time

def verify(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    try:
        t = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs(time.time() - t) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))
```

Node.js:

```javascript
const crypto = require("crypto");

function verify(secret, header, rawBody, tolerance = 300) {
  const parts = Object.fromEntries(header.split(",").map((p) => p.split("=", 2)));
  const t = Number.parseInt(parts.t, 10);
  if (!Number.isFinite(t) || Math.abs(Date.now() / 1000 - t) > tolerance) return false;
  const expected = crypto.createHmac("sha256", secret).update(`${t}.`).update(rawBody).digest("hex");
  const given = Buffer.from(parts.v1 || "", "utf8");
  const wanted = Buffer.from(expected, "utf8");
  return given.length === wanted.length && crypto.timingSafeEqual(given, wanted);
}
// Express: app.post("/endod", express.raw({ type: "application/json" }),
//   (req, res) => verify(SECRET, req.get("Endod-Signature"), req.body) ? res.sendStatus(204) : res.sendStatus(400));
```

C#:

```csharp
using System.Security.Cryptography;
using System.Text;

static bool Verify(string secret, string header, byte[] rawBody, int tolerance = 300)
{
    var parts = header.Split(',').Select(p => p.Split('=', 2)).Where(p => p.Length == 2)
                      .ToDictionary(p => p[0], p => p[1]);
    if (!parts.TryGetValue("t", out var ts) || !long.TryParse(ts, out var t)) return false;
    if (Math.Abs(DateTimeOffset.UtcNow.ToUnixTimeSeconds() - t) > tolerance) return false;
    using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
    var signed = Encoding.UTF8.GetBytes($"{t}.").Concat(rawBody).ToArray();
    var expected = Convert.ToHexString(hmac.ComputeHash(signed)).ToLowerInvariant();
    return parts.TryGetValue("v1", out var v1) &&
           CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(expected), Encoding.UTF8.GetBytes(v1));
}
```

## 8. Retries and `Idempotency-Key`

`POST /employees` and `POST /employees/{employee_number}/deactivate` accept an
`Idempotency-Key` header (1 to 255 printable characters, e.g. a UUID). The first
successful answer is kept for 24 hours: sending the same request with the same key
again replays it (with `Idempotent-Replayed: true`) and changes nothing; the same key
with a different request is refused (`422`, `IDEMPOTENCY_KEY_REUSED`). Two requests
changing the same employees at the same moment: one answers `409`; send it again.

## 9. Errors

Everything but the token endpoint answers errors as JSON:

```json
{"error": "This needs the scope employees.write.", "error_code": "insufficient_scope"}
```

| HTTP | When |
|---|---|
| 400 | malformed JSON, a bad filter, a bad Idempotency-Key |
| 401 | no token, an invalid or expired token, a disconnected client, or credentials changed since the token was issued (`WWW-Authenticate: Bearer error="invalid_token"`) |
| 403 | a scope not granted (`insufficient_scope`), a call from an address not allowed, or an organisation not approved or suspended |
| 404 | not found (another organisation's rows are never visible) |
| 409 | the same employees changed at the same moment (send it again) |
| 413 | more than 500 employees, or a body over 2 MB |
| 415 | not `application/json` |
| 422 | rows with errors (nothing was changed), or an Idempotency-Key reused for another request |
| 429 | too many requests: wait `Retry-After` seconds |
| 503 | the API is not available |

## 10. Limits

- A sync: at most **500 employees** and **2 MB**; a list page: at most 500 rows.
- **60 requests per minute** per connection (token requests not counted).
- Token requests: 20 per minute per client from one address, 30 per minute per address.
- Access tokens live 5 minutes; client assertions at most 5 minutes.

## 11. What Endod keeps

- Your organisation's data is kept apart from every other organisation's by the
  database itself (row-level security); a connection only ever reads and changes its
  own organisation's rows.
- Every change, every read and every token request is audited with the connection
  (never a secret; payout accounts masked).
- The request log keeps method, path, status, connection, time, duration and address
  for 30 days; never a body or a query string.
- Webhook deliveries keep status and attempts for 30 days; an event's body is deleted
  once it is delivered or given up.
- Client secrets are kept only as an argon2 hash; webhook secrets are encrypted at rest.
