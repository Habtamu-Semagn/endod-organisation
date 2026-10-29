"use client";

import { useState } from "react";
import Dialog, { fieldClass } from "@/components/Dialog";
import { Cancelled, usePortal } from "@/components/PortalShell";
import { ErrorBanner, SuccessBanner, messageOf, useApi } from "@/components/ui";
import AdvancedPanel from "@/components/connect/AdvancedPanel";
import CopyField from "@/components/connect/CopyField";
import { Icon } from "@/components/Icon";
import { apiFetch } from "@/lib/api";
import {
  ABILITIES,
  NOTIFY_SCOPE,
  PAYOUT_WRITE_SCOPE,
  timeAgo,
  type Connection,
  type ConnectionList,
  type ConnectionMode,
  type NewConnectionResult,
} from "@/lib/connect";

/**
 * "Connect your system": the company's own HR or payroll system, connected
 * in three plain steps. Only admins of approved organisations reach the
 * portal at all (PortalShell, and the API checks it again). Connecting,
 * disconnecting and every change under Advanced ask for a fresh code.
 */
export default function ConnectPage() {
  const { runSensitive } = usePortal();
  const { data, error, reload } = useApi<ConnectionList>("connections");
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState<Connection | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const disconnect = async () => {
    if (!disconnecting) return;
    setBusy(true);
    setActionError(null);
    try {
      await runSensitive(() => apiFetch(`connections/${disconnecting.id}/disconnect`, { method: "POST" }));
      setSuccess(`${disconnecting.name} is disconnected.`);
      setDisconnecting(null);
      reload();
    } catch (e) {
      if (!(e instanceof Cancelled)) setActionError(messageOf(e, "The system could not be disconnected."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col w-full max-w-4xl pb-space-2xl pt-space-lg gap-space-lg">
      <div className="flex flex-wrap items-start justify-between gap-space-md">
        <div className="flex flex-col gap-1">
          <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">Connect your system</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
            Let your HR or payroll system keep your employee list up to date and follow claims and payments, without typing
            anything twice.
          </p>
        </div>
        <div className="flex items-center gap-space-md">
          {data && (
            <a
              href={data.docs_url}
              target="_blank"
              rel="noreferrer"
              className="font-label-lg text-label-lg text-primary font-semibold hover:underline"
            >
              Developer guide
            </a>
          )}
          <button
            type="button"
            onClick={() => {
              setSuccess(null);
              setConnecting(true);
            }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors"
          >
            <Icon aria-hidden="true" name="add_link" size={20} />
            Connect a system
          </button>
        </div>
      </div>

      <ErrorBanner message={error} testId="load-error" />
      <SuccessBanner message={success} />
      {!data && !error && <p className="font-body-sm text-body-sm text-on-surface-variant">Loading…</p>}
      {data && data.items.length === 0 && (
        <div className="bg-surface-container-lowest rounded-xl p-space-xl text-center flex flex-col items-center gap-2" data-testid="no-connections">
          <Icon aria-hidden="true" name="hub" size={32} className="text-outline" />
          <p className="font-headline-sm text-headline-sm text-on-surface font-semibold">No systems connected yet</p>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
            Click &ldquo;Connect a system&rdquo; to let your HR or payroll system work with TenaCare.
          </p>
        </div>
      )}
      {data && data.items.length > 0 && (
        <ul className="flex flex-col gap-space-md">
          {data.items.map((connection) => (
            <ConnectionCard
              key={connection.id}
              connection={connection}
              onDisconnect={() => {
                setActionError(null);
                setDisconnecting(connection);
              }}
              onChanged={reload}
            />
          ))}
        </ul>
      )}

      {connecting && (
        <ConnectFlow
          onClose={() => {
            setConnecting(false);
            reload();
          }}
        />
      )}
      {disconnecting && (
        <Dialog
          testId="disconnect-dialog"
          title={`Disconnect ${disconnecting.name}?`}
          description="It stops working immediately. What it already sent stays in TenaCare."
          confirmLabel="Disconnect"
          tone="danger"
          busy={busy}
          error={actionError}
          onConfirm={disconnect}
          onCancel={() => setDisconnecting(null)}
        />
      )}
    </div>
  );
}

export function ModeBadge({ mode }: { mode: ConnectionMode }) {
  return (
    <span
      data-testid="mode-badge"
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full font-label-sm text-label-sm font-semibold ${
        mode === "live" ? "bg-emerald-50 text-emerald-800" : "bg-amber-100 text-amber-800"
      }`}
    >
      {mode === "live" ? "Live" : "Test"}
    </span>
  );
}

function ConnectionCard({
  connection,
  onDisconnect,
  onChanged,
}: {
  connection: Connection;
  onDisconnect: () => void;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li data-testid="connection" className="bg-surface-container-lowest rounded-xl p-space-lg flex flex-col gap-space-md">
      <div className="flex flex-wrap items-start justify-between gap-space-md">
        <div className="min-w-0 flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">{connection.name}</h2>
            <ModeBadge mode={connection.mode} />
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant" data-testid="last-used">
            {connection.last_used_at ? `Last used ${timeAgo(connection.last_used_at)}` : "Not used yet"}
          </p>
        </div>
        <button
          type="button"
          onClick={onDisconnect}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-error font-label-md text-label-md font-semibold hover:bg-error-container transition-colors"
        >
          <Icon aria-hidden="true" name="link_off" size={18} />
          Disconnect
        </button>
      </div>
      <div>
        <p className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold mb-2">What it can do</p>
        <ul className="flex flex-wrap gap-2" aria-label="What it can do">
          {connection.abilities.map((ability) => (
            <li
              key={ability}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface-container-low font-body-sm text-body-sm text-on-surface"
            >
              <Icon aria-hidden="true" name="check" size={16} className="text-primary" />
              {ability}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex items-center gap-1 font-label-md text-label-md text-on-surface-variant font-semibold hover:text-on-surface"
        >
          <Icon aria-hidden="true" name={open ? "expand_less" : "expand_more"} size={18} />
          Advanced
        </button>
        {open && <AdvancedPanel connection={connection} onChanged={onChanged} />}
      </div>
    </li>
  );
}

// --- the three steps -----------------------------------------------------------------------------

type Step = 1 | 2 | 3;

function ConnectFlow({ onClose }: { onClose: () => void }) {
  const { runSensitive } = usePortal();
  const [step, setStep] = useState<Step>(1);
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [mode, setMode] = useState<ConnectionMode>("live");
  const [notifyUrl, setNotifyUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<NewConnectionResult | null>(null);
  const notify = chosen.includes(NOTIFY_SCOPE);

  // Unticking an ability also unticks the ones that need it.
  const toggle = (scope: string) =>
    setChosen((current) =>
      current.includes(scope)
        ? current.filter((s) => s !== scope && ABILITIES.find((a) => a.scope === s)?.requires !== scope)
        : [...current, scope]
    );

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await runSensitive(() =>
        apiFetch<NewConnectionResult>("connections", {
          method: "POST",
          body: { name: name.trim(), scopes: chosen, mode, webhook_url: notify ? notifyUrl.trim() : null },
        })
      );
      setResult(created);
      setStep(3);
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The system could not be connected."));
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    setError(null);
    if (step === 1) {
      if (name.trim().length < 2) return setError("Give the system a name, e.g. “Payroll system”.");
      return setStep(2);
    }
    if (chosen.length === 0) return setError("Choose at least one thing it can do.");
    if (notify && !/^https:\/\/\S+$/i.test(notifyUrl.trim())) {
      return setError("Give the https:// address where your system wants to be notified.");
    }
    void connect();
  };

  const title = step === 3 ? "Your system is connected" : "Connect a system";
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-inverse-surface/40 p-4" data-testid="connect-flow">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-surface-container-lowest p-space-lg shadow-lg flex flex-col gap-space-md"
      >
        <div className="flex items-start justify-between gap-space-md">
          <div>
            <p className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold" data-testid="connect-step">
              Step {step} of 3
            </p>
            <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">{title}</h2>
          </div>
          {step < 3 && (
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              disabled={busy}
              className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high"
            >
              <Icon aria-hidden="true" name="close" />
            </button>
          )}
        </div>

        {step === 1 && (
          <div className="flex flex-col gap-1">
            <label htmlFor="connection-name" className="font-label-lg text-label-lg text-on-surface font-semibold">
              What is the system called?
            </label>
            <input
              id="connection-name"
              autoFocus
              className={fieldClass}
              value={name}
              maxLength={80}
              placeholder="e.g. Payroll system"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") next();
              }}
            />
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-space-md">
            <fieldset className="flex flex-col gap-2">
              <legend className="font-label-lg text-label-lg text-on-surface font-semibold mb-2">What can it do?</legend>
              {ABILITIES.map((ability) => {
                const blocked = Boolean(ability.requires && !chosen.includes(ability.requires));
                const on = chosen.includes(ability.scope);
                return (
                  <label
                    key={ability.scope}
                    className={`flex items-start gap-3 rounded-lg p-3 ring-1 ${ability.requires ? "ml-space-lg" : ""} ${
                      blocked ? "cursor-not-allowed opacity-50" : "cursor-pointer"
                    } ${on ? (ability.sensitive ? "ring-error bg-error-container/30" : "ring-primary bg-surface-container-low") : "ring-surface-variant"}`}
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={on}
                      disabled={blocked}
                      onChange={() => toggle(ability.scope)}
                    />
                    <span>
                      <span className="block font-body-md text-body-md text-on-surface font-semibold">{ability.label}</span>
                      <span className="block font-body-sm text-body-sm text-on-surface-variant">{ability.hint}</span>
                    </span>
                  </label>
                );
              })}
            </fieldset>
            {chosen.includes(PAYOUT_WRITE_SCOPE) && (
              <p
                role="alert"
                data-testid="payout-warning"
                className="flex gap-2 rounded-lg bg-error-container p-3 font-body-sm text-body-sm text-on-error-container"
              >
                <Icon aria-hidden="true" name="warning" size={20} />
                <span>
                  <strong>Careful: this system will be able to change where employees are paid.</strong> Anyone who gets
                  its secret could send reimbursements to their own account. Every change waits 24 hours before it can be
                  paid, unless you confirm it, and is shown on the Overview.
                </span>
              </p>
            )}
            {notify && (
              <div className="flex flex-col gap-1">
                <label htmlFor="notify-url" className="font-label-lg text-label-lg text-on-surface font-semibold">
                  Where should we send the notifications?
                </label>
                <input
                  id="notify-url"
                  className={fieldClass}
                  value={notifyUrl}
                  placeholder="https://your-system.example.com/endod"
                  onChange={(e) => setNotifyUrl(e.target.value)}
                />
              </div>
            )}
            <fieldset className="flex flex-col gap-2">
              <legend className="font-label-lg text-label-lg text-on-surface font-semibold mb-2">Live or test?</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {(
                  [
                    ["live", "Live", "Works with your real employees"],
                    ["test", "Test", "Checks everything, saves nothing"],
                  ] as const
                ).map(([value, label, hint]) => (
                  <label
                    key={value}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg p-3 ring-1 ${
                      mode === value ? "ring-primary bg-surface-container-low" : "ring-surface-variant"
                    }`}
                  >
                    <input type="radio" name="mode" className="mt-1" checked={mode === value} onChange={() => setMode(value)} />
                    <span>
                      <span className="block font-body-md text-body-md text-on-surface font-semibold">{label}</span>
                      <span className="block font-body-sm text-body-sm text-on-surface-variant">{hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        )}

        {step === 3 && result && <Done result={result} />}

        {error && (
          <p role="alert" data-testid="dialog-error" className="rounded-lg bg-error-container px-3 py-2 font-body-sm text-body-sm font-medium text-on-error-container">
            {error}
          </p>
        )}

        <div className="flex items-center justify-end gap-space-md pt-2">
          {step === 2 && (
            <button
              type="button"
              onClick={() => setStep(1)}
              disabled={busy}
              className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md hover:bg-surface-variant transition-colors disabled:opacity-50"
            >
              Back
            </button>
          )}
          {step < 3 ? (
            <button
              type="button"
              onClick={next}
              disabled={busy}
              className="px-5 py-2 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-all disabled:opacity-50"
            >
              {busy ? "Working…" : step === 2 ? "Connect" : "Next"}
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-all"
            >
              I saved the secret
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Done({ result }: { result: NewConnectionResult }) {
  return (
    <div className="flex flex-col gap-space-md" data-testid="connect-done">
      <div role="alert" className="flex gap-2 rounded-lg bg-amber-50 p-3 font-body-sm text-body-sm text-amber-900">
        <Icon aria-hidden="true" name="warning" size={20} />
        <span>
          <strong>Save the secret now.</strong> It is shown only this once: TenaCare keeps no readable copy. If it is lost, make a
          new one under Advanced.
        </span>
      </div>
      <CopyField label="Client ID" value={result.connection.client_id} testId="client-id" />
      <CopyField label="Client secret" value={result.client_secret} testId="client-secret" secret />
      {result.webhook_secret && (
        <CopyField label="Notification signing secret" value={result.webhook_secret} testId="notify-secret" secret />
      )}
      <a
        href={`/setup-guide/${result.connection.id}`}
        target="_blank"
        rel="noreferrer"
        className="self-start inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold hover:bg-surface-variant transition-colors"
      >
        <Icon aria-hidden="true" name="download" size={18} />
        Download setup guide
      </a>
    </div>
  );
}
