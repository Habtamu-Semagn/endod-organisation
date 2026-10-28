/** "Connect your system": the company's own systems connected to the integration API (backend app/api/connections.py). */

export type ConnectionMode = "live" | "test";

export type Connection = {
  id: string;
  name: string;
  client_id: string;
  mode: ConnectionMode;
  scopes: string[];
  /** The scopes in plain words, e.g. "See claims and their status". */
  abilities: string[];
  auth_method: "client_secret" | "private_key_jwt";
  allowed_ips: string[];
  webhook_url: string | null;
  public_keys: number;
  created_at: string;
  created_by: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type ScopeInfo = { scope: string; label: string; description: string };

/** Where the integration API is (the same in every answer). */
export type ApiInfo = {
  api_url: string;
  token_url: string;
  docs_url: string;
  openapi_url: string;
  jwks_url: string;
  scopes: ScopeInfo[];
};

export type ConnectionList = ApiInfo & { items: Connection[] };

export type NewConnectionResult = ApiInfo & {
  connection: Connection;
  client_secret: string;
  webhook_secret: string | null;
};

export type RequestLogEntry = {
  at: string;
  method: string;
  path: string;
  status: number;
  duration_ms: number;
  ip: string | null;
};

export type Delivery = {
  id: string;
  event_id: string;
  event_type: string;
  status: "pending" | "delivered" | "failed";
  attempts: number;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  delivered_at: string | null;
};

/** The ability that asks for an address to send notifications to. */
export const NOTIFY_SCOPE = "webhooks";
/** The ability that can change where reimbursements are paid. */
export const PAYOUT_WRITE_SCOPE = "employees.payout.write";

export type Ability = {
  scope: string;
  label: string;
  hint: string;
  /** Only with this other ability. */
  requires?: string;
  /** Off unless ticked, with a red warning. */
  sensitive?: boolean;
};

/** The checkboxes of step 2, in order, in plain words. */
export const ABILITIES: Ability[] = [
  { scope: "employees.write", label: "Sync employees from your HR system", hint: "Add and update employees automatically" },
  {
    scope: PAYOUT_WRITE_SCOPE,
    label: "Change employees' payout accounts (bank / Telebirr)",
    hint: "Where reimbursements are paid. Each change waits 24 hours, unless you confirm it",
    requires: "employees.write",
    sensitive: true,
  },
  { scope: "employees.read", label: "See employee list", hint: "Employees and dependants; account numbers hidden" },
  {
    scope: "employees.payout.read",
    label: "See employees' full payout accounts",
    hint: "Full bank and Telebirr account numbers",
    requires: "employees.read",
    sensitive: true,
  },
  { scope: "claims.read", label: "See claims and their status", hint: "Pending, approved, rejected or paid" },
  { scope: "payments.read", label: "See payments", hint: "Payout batches and whether they are paid" },
  { scope: NOTIFY_SCOPE, label: "Get notified when claims are approved or paid", hint: "Your system is told right away" },
];

const ID_PATTERN = /^[0-9a-f]{32}$/;

export function isConnectionId(value: unknown): value is string {
  return typeof value === "string" && ID_PATTERN.test(value);
}

/** "just now", "5 minutes ago", "3 days ago". */
export function timeAgo(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "never";
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const units: [number, string][] = [
    [60, "minute"],
    [3600, "hour"],
    [86400, "day"],
    [2592000, "month"],
  ];
  let label = "minute";
  let size = 60;
  for (const [s, name] of units) {
    if (seconds >= s) {
      size = s;
      label = name;
    }
  }
  const count = Math.max(1, Math.round(seconds / size));
  return `${count} ${label}${count === 1 ? "" : "s"} ago`;
}

/** A payout account changed by a connected system (masked), held for 24 hours unless confirmed. */
export type PayoutChange = {
  id: string;
  employee_id: string;
  employee_name: string | null;
  employee_number: string | null;
  before: { method: string | null; account: string | null };
  after: { method: string | null; account: string | null };
  created_at: string;
  hold_until: string;
  confirmed_at: string | null;
  held: boolean;
};
