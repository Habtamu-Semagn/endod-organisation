"use client";

import Link from "next/link";
import { useState } from "react";
import Dialog, { fieldClass, fieldLabelClass } from "@/components/Dialog";
import { Cancelled, usePortal } from "@/components/PortalShell";
import { EmptyRow, ErrorBanner, StatusBadge, SuccessBanner, messageOf, useApi } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { formatDate, formatDateTime, formatEtb, PAYOUT_LABELS } from "@/lib/format";
import type { Batch, Payments, PayoutMethod } from "@/lib/types";
import { Icon } from "@/components/Icon";

type Tab = "ready" | "open" | "completed";

export default function PaymentsPage() {
  const { runSensitive } = usePortal();
  const { data, error: loadError, reload } = useApi<Payments>("batches");
  const [tab, setTab] = useState<Tab>("ready");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [creating, setCreating] = useState<PayoutMethod | null>(null);
  const [paying, setPaying] = useState<Batch | null>(null);
  const [reference, setReference] = useState("");
  const [expanded, setExpanded] = useState<Batch | null>(null);

  const open = data?.items.filter((b) => b.status === "open") ?? [];
  const completed = data?.items.filter((b) => b.status === "paid") ?? [];

  const createBatch = async (method: PayoutMethod) => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const batch = await runSensitive(() => apiFetch<Batch>("batches", { method: "POST", body: { method } }));
      setSuccess(`${batch.code} is ready: ${batch.claim_count} claims, ${formatEtb(batch.total_santim)}. Download its file and upload it to ${batch.method_label}.`);
      setCreating(null);
      setTab("open");
      reload();
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The batch could not be made."));
    } finally {
      setBusy(false);
    }
  };

  const markPaid = async () => {
    if (!paying) return;
    setBusy(true);
    setError(null);
    try {
      const batch = await runSensitive(() =>
        apiFetch<Batch>(`batches/${paying.id}/mark-paid`, { method: "POST", body: { reference } })
      );
      setSuccess(`${batch.code} is marked paid (reference ${batch.reference}). Its claims are paid.`);
      setPaying(null);
      setTab("completed");
      reload();
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The batch could not be marked paid."));
    } finally {
      setBusy(false);
    }
  };

  const cancelBatch = async (batch: Batch) => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await runSensitive(() => apiFetch(`batches/${batch.id}/cancel`, { method: "POST" }));
      setSuccess(`${batch.code} is cancelled; its claims are ready to batch again.`);
      reload();
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "The batch could not be cancelled."));
    } finally {
      setBusy(false);
    }
  };

  const showBatch = async (batch: Batch) => {
    try {
      setExpanded(await apiFetch<Batch>(`batches/${batch.id}`));
    } catch (e) {
      setError(messageOf(e, "Could not open the batch."));
    }
  };

  const tabClass = (key: Tab) =>
    tab === key
      ? "px-4 py-2 rounded-lg bg-primary-container text-on-primary-container font-label-md text-label-md font-semibold shadow-sm flex items-center gap-2 whitespace-nowrap"
      : "px-4 py-2 rounded-lg bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-md text-label-md font-medium transition-colors flex items-center gap-2 whitespace-nowrap";

  return (
    <div className="flex flex-col w-full pb-24">
      {/* Top Command & Action Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-lg py-space-xl">
        <div className="flex flex-col gap-1">
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">Payment Disbursement &amp; Settlement</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
            Group approved claims into a payout batch per method (CBE, Awash, Dashen or Telebirr), download its file for your bank or
            Telebirr, pay it there, then mark the batch paid with the bank&apos;s reference. TenaCare never moves money.
          </p>
        </div>
      </div>

      {/* KPI Metagrid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-space-lg mb-space-xl">
        <Kpi label="Ready for Reimbursement" value={data ? formatEtb(data.ready.total_santim) : "—"} testId="kpi-ready" />
        <Kpi label="In Open Batches" value={data ? formatEtb(data.open_total_santim) : "—"} testId="kpi-open" />
        <Kpi label="Paid This Month" value={data ? formatEtb(data.paid_this_month_santim) : "—"} testId="kpi-paid-month" />
      </div>

      <div className="flex flex-col gap-space-sm mb-space-md">
        <SuccessBanner message={success} />
        <ErrorBanner message={error ?? loadError} />
        {data && data.ready.missing_payout_details.claims > 0 ? (
          <p data-testid="missing-payout" className="rounded-xl bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-900">
            {data.ready.missing_payout_details.claims} approved claim(s) ({formatEtb(data.ready.missing_payout_details.total_santim)}) wait for the
            employee&apos;s payout account. Add it on the <Link href="/employees" className="underline">Employees</Link> page.
          </p>
        ) : null}
        {data && data.ready.payout_held && data.ready.payout_held.claims > 0 ? (
          <p data-testid="payout-held" className="rounded-xl bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-900">
            {data.ready.payout_held.claims} approved claim(s) ({formatEtb(data.ready.payout_held.total_santim)}) wait: a connected
            system changed the employee&apos;s payout account less than 24 hours ago. Confirm the change on{" "}
            <Link href="/connect" className="underline">Connect your system</Link> to pay them now.
          </p>
        ) : null}
      </div>

      {/* Ready by method */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        {(data?.enabled_methods ?? []).map((method) => {
          const bucket = data?.ready.by_method[method] ?? { claims: 0, total_santim: 0 };
          return (
            <div key={method} data-testid={`method-${method}`} className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col gap-space-sm">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${method === "telebirr" ? "bg-tertiary" : "bg-primary"}`} />
                <span className="font-label-md text-label-md font-semibold">{PAYOUT_LABELS[method]}</span>
              </div>
              <span className="font-headline-md text-headline-md text-on-surface font-semibold">{formatEtb(bucket.total_santim)}</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">{bucket.claims} approved claim(s) ready</span>
              <button
                type="button"
                disabled={busy || bucket.claims === 0}
                onClick={() => setCreating(method)}
                className="mt-auto inline-flex items-center justify-center gap-space-sm px-4 py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Icon aria-hidden="true" name="send_money" size={18} />
                <span className="font-label-md text-label-md font-semibold">Create batch</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Primary Interactive Table Card */}
      <div className="rounded-xl bg-surface-container-lowest shadow-sm overflow-hidden flex flex-col">
        <div className="p-space-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md bg-surface-container-low">
          <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto" role="tablist">
            <button role="tab" aria-selected={tab === "ready"} onClick={() => setTab("ready")} className={tabClass("ready")}>
              <span>Ready to Pay</span>
              <span className="px-1.5 py-0.5 rounded-full bg-primary text-on-primary font-label-sm text-label-sm">{data?.ready.claims.length ?? 0}</span>
            </button>
            <button role="tab" aria-selected={tab === "open"} onClick={() => setTab("open")} className={tabClass("open")}>
              <span>Open Batches</span>
              <span className="px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm text-label-sm">{open.length}</span>
            </button>
            <button role="tab" aria-selected={tab === "completed"} onClick={() => setTab("completed")} className={tabClass("completed")}>
              <span>Completed Payments</span>
              <span className="px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm text-label-sm">{completed.length}</span>
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          {tab === "ready" ? (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-high/60 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                  <th className="px-4 py-3.5">Claim ID &amp; Approval</th>
                  <th className="px-4 py-3.5">Employee &amp; Dept</th>
                  <th className="px-4 py-3.5">Payout Method / Account</th>
                  <th className="px-4 py-3.5">Pharmacy</th>
                  <th className="px-4 py-3.5 text-right">Amount (ETB)</th>
                  <th className="px-4 py-3.5 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-body-md text-on-surface">
                {data && data.ready.claims.length === 0 ? <EmptyRow colSpan={6}>No approved claims are waiting for payout.</EmptyRow> : null}
                {data?.ready.claims.map((claim) => (
                  <tr key={claim.id} data-testid="ready-claim" className="hover:bg-surface-container-low/60 transition-colors">
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col">
                        <Link href={`/claims/${claim.id}`} className="font-label-md text-label-md font-semibold text-primary hover:underline">
                          {claim.code}
                        </Link>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">Approved {formatDateTime(claim.reviewed_at)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col min-w-0">
                        <span className="font-label-md text-label-md font-semibold truncate">{claim.employee?.name}</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">{claim.employee?.department}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${claim.payout_ready ? "bg-primary" : "bg-amber-500"}`} />
                          <span className="font-label-md text-label-md font-medium">
                            {claim.employee?.payout_method ? PAYOUT_LABELS[claim.employee.payout_method] : "No payout account"}
                          </span>
                        </div>
                        <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">{claim.payout_account ?? ""}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="font-label-md text-label-md">{claim.pharmacy_name}</span>
                    </td>
                    <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">{formatEtb(claim.approved_santim, false)}</td>
                    <td className="px-4 py-3.5 text-center">
                      <StatusBadge status={claim.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-high/60 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                  <th className="px-4 py-3.5">Batch</th>
                  <th className="px-4 py-3.5">Method</th>
                  <th className="px-4 py-3.5 text-center">Claims</th>
                  <th className="px-4 py-3.5 text-right">Total (ETB)</th>
                  <th className="px-4 py-3.5">{tab === "open" ? "Created" : "Paid & Reference"}</th>
                  <th className="px-4 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-body-md text-on-surface">
                {(tab === "open" ? open : completed).length === 0 ? (
                  <EmptyRow colSpan={6}>{tab === "open" ? "No open batches." : "No paid batches yet."}</EmptyRow>
                ) : null}
                {(tab === "open" ? open : completed).map((batch) => (
                  <tr key={batch.id} data-testid="batch-row" className="hover:bg-surface-container-low/60 transition-colors">
                    <td className="px-4 py-3.5">
                      <button type="button" className="font-label-md text-label-md font-semibold text-primary hover:underline" onClick={() => void showBatch(batch)}>
                        {batch.code}
                      </button>
                    </td>
                    <td className="px-4 py-3.5 font-label-md text-label-md">{batch.method_label}</td>
                    <td className="px-4 py-3.5 text-center">{batch.claim_count}</td>
                    <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">{formatEtb(batch.total_santim, false)}</td>
                    <td className="px-4 py-3.5 font-body-sm text-body-sm text-on-surface-variant">
                      {batch.status === "paid" ? (
                        <span data-testid="batch-reference">
                          {formatDate(batch.paid_at)} • Ref: {batch.reference}
                        </span>
                      ) : (
                        formatDateTime(batch.created_at)
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={`/api/export/batches/${batch.id}/export`}
                          onClick={() => setTimeout(reload, 1500)}
                          className="inline-flex items-center gap-1 px-3 py-1 rounded text-on-surface-variant hover:text-primary font-label-sm text-label-sm transition-colors"
                        >
                          <Icon aria-hidden="true" name="sim_card_download" size={16} />
                          <span>Download file</span>
                        </a>
                        {batch.status === "open" && (
                          <>
                            {/* Once its file is downloaded the batch may have been paid: it can only be marked paid. */}
                            {batch.exported_at ? null : (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void cancelBatch(batch)}
                                className="px-3 py-1 rounded text-error font-label-sm text-label-sm hover:underline"
                              >
                                Cancel
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                setReference("");
                                setError(null);
                                setPaying(batch);
                              }}
                              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm font-semibold"
                            >
                              Mark paid
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {creating && data && (
        <Dialog
          testId="batch-dialog"
          title={`Create a ${PAYOUT_LABELS[creating]} batch`}
          description={
            <>
              Group <strong className="text-on-surface">{data.ready.by_method[creating].claims} approved claim(s)</strong> totalling{" "}
              <strong className="text-primary font-numeric-currency">{formatEtb(data.ready.by_method[creating].total_santim)}</strong> into one
              payout batch. You then download its file and pay it through {PAYOUT_LABELS[creating]}.
            </>
          }
          confirmLabel="Create batch"
          busy={busy}
          error={error}
          onCancel={() => setCreating(null)}
          onConfirm={() => void createBatch(creating)}
        />
      )}

      {paying && (
        <Dialog
          testId="paid-dialog"
          title={`Mark ${paying.code} paid`}
          description={
            <>
              Confirm that <strong className="text-on-surface">{formatEtb(paying.total_santim)}</strong> for {paying.claim_count} claim(s) was paid
              through {paying.method_label}. A paid batch can no longer change. This needs a fresh code.
            </>
          }
          confirmLabel="Mark paid"
          busy={busy}
          confirmDisabled={reference.trim().length < 3}
          error={error}
          onCancel={() => setPaying(null)}
          onConfirm={() => void markPaid()}
        >
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Bank or Telebirr reference</span>
            <input className={fieldClass} value={reference} maxLength={80} onChange={(e) => setReference(e.target.value)} />
          </label>
        </Dialog>
      )}

      {expanded && (
        <Dialog
          testId="batch-detail"
          wide
          title={`${expanded.code} · ${expanded.method_label}`}
          description={`${expanded.claim_count} claim(s), ${formatEtb(expanded.total_santim)} · ${expanded.status === "paid" ? `paid, reference ${expanded.reference}` : "open"}`}
          confirmLabel="Close"
          onCancel={() => setExpanded(null)}
          onConfirm={() => setExpanded(null)}
        >
          <table className="w-full text-left font-body-sm text-body-sm">
            <thead>
              <tr className="font-label-sm text-label-sm uppercase text-on-surface-variant">
                <th className="py-1">Claim</th>
                <th className="py-1">Employee</th>
                <th className="py-1">Account</th>
                <th className="py-1 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {expanded.claims?.map((c) => (
                <tr key={c.id} className="border-t border-surface-container">
                  <td className="py-1">{c.code}</td>
                  <td className="py-1">{c.employee?.name}</td>
                  <td className="py-1 font-mono">{c.payout_account}</td>
                  <td className="py-1 text-right font-numeric-currency">{formatEtb(c.approved_santim, false)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Dialog>
      )}
    </div>
  );
}

function Kpi({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col justify-between">
      <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">{label}</span>
      <span data-testid={testId} className="font-display-lg text-display-lg text-on-surface mt-1 tracking-tight">
        {value}
      </span>
    </div>
  );
}
