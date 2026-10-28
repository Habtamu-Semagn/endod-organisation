"use client";

import { useState, type ReactNode } from "react";
import Dialog, { fieldClass } from "@/components/Dialog";
import { Cancelled, usePortal } from "@/components/PortalShell";
import { ErrorBanner, SuccessBanner, messageOf, useApi } from "@/components/ui";
import CopyField from "@/components/connect/CopyField";
import { apiFetch } from "@/lib/api";
import type { Connection, Delivery, PayoutChange, RequestLogEntry } from "@/lib/connect";
import { formatDateTime } from "@/lib/format";

const SECONDARY =
  "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold hover:bg-surface-variant transition-colors disabled:opacity-50";
const AREA =
  "w-full min-h-[72px] px-3 py-2 rounded-lg bg-surface text-on-surface font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary";

type Revealed = { title: string; label: string; value: string };

/**
 * The technical settings of one connection, for the company's IT staff: IP
 * restriction, public-key authentication, secret rotation, the webhook, and
 * the request and delivery logs. Every change asks for a fresh code (the
 * API answers REAUTH_REQUIRED; runSensitive asks for it and tries again).
 */
export default function AdvancedPanel({ connection, onChanged }: { connection: Connection; onChanged: () => void }) {
  const { runSensitive } = usePortal();
  const [ips, setIps] = useState(connection.allowed_ips.join("\n"));
  const [jwks, setJwks] = useState("");
  const [webhookUrl, setWebhookUrl] = useState(connection.webhook_url ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Revealed | null>(null);
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [logTick, setLogTick] = useState(0);
  const base = `connections/${connection.id}`;

  const change = async (path: string, body: unknown, done: (answer: Record<string, unknown>) => void) => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const answer = await runSensitive(() => apiFetch<Record<string, unknown>>(path, { method: "POST", body }));
      done(answer);
      onChanged();
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The change could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  const sendTest = async () => {
    setError(null);
    setSuccess(null);
    try {
      await apiFetch(`${base}/webhook/test`, { method: "POST" });
      setSuccess("Test event queued: it shows under Webhook deliveries.");
      setLogTick((n) => n + 1);
    } catch (e) {
      setError(messageOf(e, "The test event could not be sent."));
    }
  };

  return (
    <div data-testid="advanced" className="mt-space-md flex flex-col gap-space-lg border-t border-surface-variant pt-space-md">
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <Section title="Client ID">
        <code className="break-all rounded-lg bg-surface-container-low px-2 py-1 font-mono text-xs">{connection.client_id}</code>
      </Section>

      <Section title="IP restriction" hint="Only these addresses or ranges may use this connection, one per line. Empty: any address.">
        <textarea
          aria-label="Allowed IP addresses"
          className={AREA}
          value={ips}
          placeholder={"196.188.10.0/24\n41.79.1.5"}
          onChange={(e) => setIps(e.target.value)}
        />
        <button
          type="button"
          className={`${SECONDARY} mt-2`}
          disabled={busy}
          onClick={() =>
            change(`${base}/ip-restriction`, { allowed_ips: ips.split(/[\s,]+/).filter(Boolean) }, (answer) => {
              const saved = (answer.connection as Connection | undefined)?.allowed_ips ?? [];
              setIps(saved.join("\n"));
              setSuccess(saved.length ? "IP restriction saved." : "IP restriction removed: any address may connect.");
            })
          }
        >
          Save addresses
        </button>
      </Section>

      <Section
        title="Authentication"
        hint={
          connection.auth_method === "private_key_jwt"
            ? `Public key (private_key_jwt): ${connection.public_keys} key${connection.public_keys === 1 ? "" : "s"}. The client secret does not work.`
            : "Client secret (OAuth 2.0 client credentials)."
        }
      >
        <button type="button" className={SECONDARY} disabled={busy} onClick={() => setConfirmRotate(true)}>
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">autorenew</span>
          {connection.auth_method === "private_key_jwt" ? "Go back to a client secret" : "Rotate secret"}
        </button>
        <label htmlFor={`jwks-${connection.id}`} className="mt-space-md block font-label-sm text-label-sm text-on-surface-variant">
          Use a public key instead (paste your JWKS: ES256 or RS256, public keys only)
        </label>
        <textarea
          id={`jwks-${connection.id}`}
          className={AREA}
          value={jwks}
          placeholder='{"keys": [{"kty": "EC", "crv": "P-256", "kid": "my-key-1", "x": "...", "y": "..."}]}'
          onChange={(e) => setJwks(e.target.value)}
        />
        <button
          type="button"
          className={`${SECONDARY} mt-2`}
          disabled={busy || !jwks.trim()}
          onClick={() =>
            change(`${base}/public-key`, { jwks: jwks.trim() }, () => {
              setJwks("");
              setSuccess("Public key saved: the client secret no longer works.");
            })
          }
        >
          Save public key
        </button>
      </Section>

      <Section title="Webhook" hint="Claim, payment and employee events are POSTed here, signed with the webhook secret (https only).">
        <input
          aria-label="Webhook URL"
          className={fieldClass}
          value={webhookUrl}
          placeholder="https://your-system.example.com/endod"
          onChange={(e) => setWebhookUrl(e.target.value)}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            className={SECONDARY}
            disabled={busy || !webhookUrl.trim()}
            onClick={() =>
              change(`${base}/webhook`, { url: webhookUrl.trim() }, (answer) => {
                if (typeof answer.webhook_secret === "string") {
                  setRevealed({ title: "Webhook secret", label: "Webhook secret", value: answer.webhook_secret });
                } else {
                  setSuccess("Webhook saved.");
                }
              })
            }
          >
            Save webhook
          </button>
          {connection.webhook_url && (
            <>
              <button type="button" className={SECONDARY} disabled={busy} onClick={sendTest}>
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">send</span>
                Send test event
              </button>
              <button
                type="button"
                className={SECONDARY}
                disabled={busy}
                onClick={() =>
                  change(`${base}/webhook/rotate-secret`, {}, (answer) =>
                    setRevealed({ title: "New webhook secret", label: "Webhook secret", value: String(answer.webhook_secret) })
                  )
                }
              >
                Rotate webhook secret
              </button>
              <button
                type="button"
                className={SECONDARY}
                disabled={busy}
                onClick={() =>
                  change(`${base}/webhook`, { url: null }, () => {
                    setWebhookUrl("");
                    setSuccess("Webhook removed.");
                  })
                }
              >
                Remove webhook
              </button>
            </>
          )}
        </div>
      </Section>

      {connection.scopes.includes("employees.payout.write") && <PayoutChanges base={base} />}
      <RequestLog base={base} />
      <Deliveries base={base} tick={logTick} />

      {confirmRotate && (
        <Dialog
          testId="rotate-dialog"
          title="Make a new client secret?"
          description="The current secret stops working at once. Your system needs the new one."
          confirmLabel="Make a new secret"
          tone="danger"
          busy={busy}
          onCancel={() => setConfirmRotate(false)}
          onConfirm={() =>
            change(`${base}/rotate-secret`, {}, (answer) => {
              setConfirmRotate(false);
              setRevealed({ title: "New client secret", label: "Client secret", value: String(answer.client_secret) });
            })
          }
        />
      )}
      {revealed && (
        <Dialog
          testId="revealed-dialog"
          title={revealed.title}
          confirmLabel="I saved it"
          onConfirm={() => setRevealed(null)}
          onCancel={() => setRevealed(null)}
        >
          <div className="flex flex-col gap-space-md">
            <p role="alert" className="rounded-lg bg-amber-50 p-3 font-body-sm text-body-sm text-amber-900">
              <strong>Save it now.</strong> It is shown only this once. The old one has stopped working.
            </p>
            <CopyField label={revealed.label} value={revealed.value} testId="revealed-secret" secret />
          </div>
        </Dialog>
      )}
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">{title}</h3>
      {hint && <p className="mb-2 mt-0.5 font-body-sm text-body-sm text-on-surface-variant">{hint}</p>}
      <div className={hint ? "" : "mt-2"}>{children}</div>
    </section>
  );
}

function RequestLog({ base }: { base: string }) {
  const { data, error, reload } = useApi<{ items: RequestLogEntry[] }>(`${base}/requests`);
  return (
    <Section title="Recent requests" hint="The last 50 calls (kept 30 days). Never the data sent.">
      <button type="button" onClick={reload} className="mb-2 font-label-md text-label-md text-primary font-semibold hover:underline">
        Refresh
      </button>
      <ErrorBanner message={error} />
      {data && data.items.length === 0 && <p className="font-body-sm text-body-sm text-on-surface-variant">No requests yet.</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-body-sm text-body-sm" data-testid="request-log">
            <thead className="text-outline">
              <tr>
                <th className="py-1 pr-3 font-semibold">Time</th>
                <th className="py-1 pr-3 font-semibold">Request</th>
                <th className="py-1 pr-3 font-semibold">Status</th>
                <th className="py-1 pr-3 font-semibold">Duration</th>
                <th className="py-1 font-semibold">IP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row, index) => (
                <tr key={`${row.at}-${index}`} className="border-t border-surface-variant">
                  <td className="py-1 pr-3 whitespace-nowrap">{formatDateTime(row.at)}</td>
                  <td className="py-1 pr-3 font-mono text-xs">
                    {row.method} {row.path}
                  </td>
                  <td className={`py-1 pr-3 font-semibold ${row.status < 400 ? "text-emerald-700" : "text-error"}`}>{row.status}</td>
                  <td className="py-1 pr-3">{row.duration_ms} ms</td>
                  <td className="py-1 font-mono text-xs">{row.ip ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function Deliveries({ base, tick }: { base: string; tick: number }) {
  const { data, error, reload } = useApi<{ items: Delivery[] }>(`${base}/deliveries?tick=${tick}`);
  return (
    <Section title="Webhook deliveries" hint="The last 50 events sent (kept 30 days).">
      <button type="button" onClick={reload} className="mb-2 font-label-md text-label-md text-primary font-semibold hover:underline">
        Refresh
      </button>
      <ErrorBanner message={error} />
      {data && data.items.length === 0 && <p className="font-body-sm text-body-sm text-on-surface-variant">No events sent yet.</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-body-sm text-body-sm" data-testid="delivery-log">
            <thead className="text-outline">
              <tr>
                <th className="py-1 pr-3 font-semibold">Time</th>
                <th className="py-1 pr-3 font-semibold">Event</th>
                <th className="py-1 pr-3 font-semibold">Status</th>
                <th className="py-1 pr-3 font-semibold">Attempts</th>
                <th className="py-1 font-semibold">Last answer</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-t border-surface-variant">
                  <td className="py-1 pr-3 whitespace-nowrap">{formatDateTime(row.created_at)}</td>
                  <td className="py-1 pr-3 font-mono text-xs">{row.event_type}</td>
                  <td
                    className={`py-1 pr-3 font-semibold ${
                      row.status === "delivered" ? "text-emerald-700" : row.status === "failed" ? "text-error" : "text-amber-700"
                    }`}
                  >
                    {row.status}
                  </td>
                  <td className="py-1 pr-3">{row.attempts}</td>
                  <td className="py-1">{row.last_status_code ?? row.last_error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function PayoutChanges({ base }: { base: string }) {
  const { runSensitive } = usePortal();
  const { data, error, reload } = useApi<{ items: PayoutChange[] }>(`${base}/payout-changes`);
  const [actionError, setActionError] = useState<string | null>(null);
  const confirm = async (change: PayoutChange) => {
    setActionError(null);
    try {
      await runSensitive(() => apiFetch(`${base}/payout-changes/${change.id}/confirm`, { method: "POST" }));
      reload();
    } catch (e) {
      if (!(e instanceof Cancelled)) setActionError(messageOf(e, "The change could not be confirmed."));
    }
  };
  const account = (side: PayoutChange["before"]) => (side.method ? `${side.method} ${side.account ?? ""}` : "none");
  return (
    <Section
      title="Payout account changes"
      hint="Changes this system made (account numbers masked). Each waits 24 hours before it can be paid, unless you confirm it."
    >
      <ErrorBanner message={error ?? actionError} />
      {data && data.items.length === 0 && <p className="font-body-sm text-body-sm text-on-surface-variant">No changes yet.</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-body-sm text-body-sm" data-testid="payout-changes">
            <thead className="text-outline">
              <tr>
                <th className="py-1 pr-3 font-semibold">Time</th>
                <th className="py-1 pr-3 font-semibold">Employee</th>
                <th className="py-1 pr-3 font-semibold">From</th>
                <th className="py-1 pr-3 font-semibold">To</th>
                <th className="py-1 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-t border-surface-variant" data-testid="payout-change">
                  <td className="py-1 pr-3 whitespace-nowrap">{formatDateTime(row.created_at)}</td>
                  <td className="py-1 pr-3">
                    {row.employee_name ?? "—"} <span className="font-mono text-xs">{row.employee_number ?? ""}</span>
                  </td>
                  <td className="py-1 pr-3 font-mono text-xs">{account(row.before)}</td>
                  <td className="py-1 pr-3 font-mono text-xs">{account(row.after)}</td>
                  <td className="py-1">
                    {row.held ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="text-amber-700 font-semibold">Held until {formatDateTime(row.hold_until)}</span>
                        <button type="button" className={SECONDARY} onClick={() => confirm(row)}>
                          Confirm
                        </button>
                      </span>
                    ) : (
                      <span className="text-emerald-700 font-semibold">{row.confirmed_at ? "Confirmed" : "In effect"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
