"use client";

import { useState } from "react";
import { fieldClass, fieldLabelClass } from "@/components/Dialog";
import { Cancelled, usePortal } from "@/components/PortalShell";
import { ErrorBanner, SuccessBanner, messageOf, useApi } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { formatDate, formatEtb, parseEtb, PAYOUT_LABELS, santimToInput } from "@/lib/format";
import type { Organisation, Policy, PayoutMethod } from "@/lib/types";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export default function SettingsPage() {
  const policy = useApi<Policy>("policy");
  const organisation = useApi<Organisation>("organisation");
  return (
    <div className="flex flex-col w-full max-w-4xl pb-space-2xl pt-space-lg gap-space-lg">
      <div className="flex flex-col gap-1">
        <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">Policy &amp; Settings</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          The medication benefit every employee gets (unless they have their own policy), and how reimbursements are paid. Saving a change
          asks for a fresh code from your authenticator app.
        </p>
      </div>
      <ErrorBanner message={policy.error ?? organisation.error} testId="load-error" />
      {policy.data && <PolicyForm policy={policy.data} onSaved={policy.setData} />}
      {organisation.data && <PayoutForm organisation={organisation.data} onSaved={organisation.setData} />}
    </div>
  );
}

function PolicyForm({ policy, onSaved }: { policy: Policy; onSaved: (p: Policy) => void }) {
  const { runSensitive } = usePortal();
  const [limit, setLimit] = useState(santimToInput(policy.annual_limit_santim));
  const [copay, setCopay] = useState(String(policy.copay_percent));
  const [dependants, setDependants] = useState(policy.dependants_covered);
  const [excluded, setExcluded] = useState(policy.excluded_medicines.join("\n"));
  const [month, setMonth] = useState(policy.year_start_month);
  const [day, setDay] = useState(String(policy.year_start_day));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const limitSantim = parseEtb(limit);
  const copayOk = /^\d{1,3}$/.test(copay.trim()) && Number(copay) <= 100;
  const dayOk = /^\d{1,2}$/.test(day.trim()) && Number(day) >= 1 && Number(day) <= 31;

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (limitSantim === null || !copayOk || !dayOk) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await runSensitive(() =>
        apiFetch<Policy>("policy", {
          method: "PUT",
          body: {
            annual_limit_santim: limitSantim,
            copay_percent: Number(copay),
            dependants_covered: dependants,
            excluded_medicines: excluded.split("\n").map((s) => s.trim()).filter(Boolean),
            year_start_month: month,
            year_start_day: Number(day),
          },
        })
      );
      onSaved(saved);
      setSuccess("The benefit policy is saved.");
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The policy could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="bg-surface-container-lowest rounded-xl p-space-lg flex flex-col gap-space-md" data-testid="policy-form">
      <div className="flex items-center justify-between">
        <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold">Benefit policy</h2>
        <span className="font-label-sm text-label-sm text-on-surface-variant">
          Current policy year {formatDate(policy.current_year.start)} – {formatDate(policy.current_year.end)}
        </span>
      </div>
      <SuccessBanner message={success} />
      <ErrorBanner message={error} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-md">
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Annual limit per employee (ETB)</span>
          <input className={fieldClass} inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} />
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            {limitSantim === null ? "Enter an amount like 10000 or 10,000.50" : `${formatEtb(limitSantim)} for each employee and their dependants together`}
          </span>
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Employee co-pay (%)</span>
          <input className={fieldClass} inputMode="numeric" value={copay} onChange={(e) => setCopay(e.target.value)} />
          <span className="font-body-sm text-body-sm text-on-surface-variant">The employee&apos;s share of every receipt (0–100).</span>
        </label>
        <div className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Policy year starts on</span>
          <div className="flex gap-space-sm">
            <select aria-label="Policy year start month" className={fieldClass} value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {MONTHS.map((name, index) => (
                <option key={name} value={index + 1}>
                  {name}
                </option>
              ))}
            </select>
            <input aria-label="Policy year start day" className={`${fieldClass} max-w-[5rem]`} inputMode="numeric" value={day} onChange={(e) => setDay(e.target.value)} />
          </div>
          <span className="font-body-sm text-body-sm text-on-surface-variant">For the Ethiopian fiscal year: July 8.</span>
        </div>
        <label className="flex items-center gap-2 font-body-md text-body-md text-on-surface self-center">
          <input type="checkbox" checked={dependants} onChange={(e) => setDependants(e.target.checked)} />
          Dependants are covered
        </label>
        <label className="sm:col-span-2 flex flex-col gap-1">
          <span className={fieldLabelClass}>Excluded medicines (one per line)</span>
          <textarea
            className="w-full p-2.5 bg-surface rounded-lg font-body-sm text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            rows={4}
            value={excluded}
            onChange={(e) => setExcluded(e.target.value)}
            placeholder="Sildenafil"
          />
          <span className="font-body-sm text-body-sm text-on-surface-variant">A claim with a medicine whose name contains one of these words is not approved.</span>
        </label>
      </div>
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy || limitSantim === null || !copayOk || !dayOk}
          className="px-5 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save policy"}
        </button>
      </div>
    </form>
  );
}

function PayoutForm({ organisation, onSaved }: { organisation: Organisation; onSaved: (o: Organisation) => void }) {
  const { runSensitive } = usePortal();
  const [debit, setDebit] = useState(organisation.payout.debit_account ?? "");
  const [methods, setMethods] = useState<PayoutMethod[]>(organisation.payout.methods);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await runSensitive(() =>
        apiFetch<Organisation>("organisation/payout", { method: "PUT", body: { debit_account: debit || null, methods } })
      );
      onSaved(saved);
      setSuccess("Payout settings are saved.");
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The payout settings could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="bg-surface-container-lowest rounded-xl p-space-lg flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <h2 className="font-headline-sm text-headline-sm text-on-surface font-semibold">Payouts</h2>
        <span className="font-label-sm text-label-sm text-on-surface-variant">
          {organisation.name} · TIN {organisation.tin}
        </span>
      </div>
      <SuccessBanner message={success} />
      <ErrorBanner message={error} />
      <label className="flex flex-col gap-1 max-w-md">
        <span className={fieldLabelClass}>Account you pay from (shown in bank files)</span>
        <input className={fieldClass} inputMode="numeric" value={debit} onChange={(e) => setDebit(e.target.value)} placeholder="1000123456789" />
      </label>
      <fieldset className="flex flex-col gap-1">
        <legend className={fieldLabelClass}>Payout methods you use</legend>
        <div className="flex flex-wrap gap-space-md mt-1">
          {(Object.keys(PAYOUT_LABELS) as PayoutMethod[]).map((method) => (
            <label key={method} className="flex items-center gap-2 font-body-md text-body-md">
              <input
                type="checkbox"
                checked={methods.includes(method)}
                onChange={(e) => setMethods(e.target.checked ? [...methods, method] : methods.filter((m) => m !== method))}
              />
              {PAYOUT_LABELS[method]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy || methods.length === 0}
          className="px-5 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save payout settings"}
        </button>
      </div>
    </form>
  );
}
