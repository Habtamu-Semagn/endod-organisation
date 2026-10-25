"use client";

import Link from "next/link";
import { ErrorBanner, useApi } from "@/components/ui";
import { formatDate, formatEtb, percentOf } from "@/lib/format";
import type { ClaimStatus, Overview } from "@/lib/types";

const RING = 2 * Math.PI * 38;
const SEGMENTS: { status: ClaimStatus; label: string; stroke: string; dot: string }[] = [
  { status: "approved", label: "Approved", stroke: "#00685f", dot: "bg-primary" },
  { status: "paid", label: "Paid", stroke: "#00855b", dot: "bg-tertiary-container" },
  { status: "pending", label: "Pending", stroke: "#b45309", dot: "bg-amber-600" },
  { status: "rejected", label: "Rejected", stroke: "#ba1a1a", dot: "bg-error" },
];

export default function OverviewPage() {
  const { data, error } = useApi<Overview>("overview");
  const total = data ? data.claims_submitted : 0;
  const arcs: { status: ClaimStatus; stroke: string; length: number; offset: number }[] = [];
  if (data && total > 0) {
    let offset = 0;
    for (const segment of SEGMENTS) {
      const length = (data.by_status[segment.status].claims / total) * RING;
      arcs.push({ status: segment.status, stroke: segment.stroke, length, offset });
      offset += length;
    }
  }

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Action & Context Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-lg pt-space-lg mb-space-xl">
        <div className="flex flex-col gap-space-xs max-w-2xl">
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">Medication Benefit Overview</h1>
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            Employee prescription medication reimbursements, claims processing, and payouts
            {data ? ` for the policy year ${formatDate(data.policy_year.start)} – ${formatDate(data.policy_year.end)}` : ""}.
          </p>
        </div>
      </div>
      <ErrorBanner message={error} testId="load-error" />

      {/* 4 KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        <Kpi label="Total Medication Spend" value={data ? formatEtb(data.spend_santim) : "—"} testId="kpi-spend" />
        <Kpi label="Claims Submitted" value={data ? String(data.claims_submitted) : "—"} testId="kpi-claims" />
        <Kpi
          label="Pending Approval"
          value={data ? String(data.pending_claims) : "—"}
          testId="kpi-pending"
          sub={data && data.pending_claims ? <Link className="text-primary hover:underline" href="/claims?status=pending">{formatEtb(data.pending_total_santim)} to review</Link> : null}
        />
        <Kpi label="Total Reimbursed YTD" value={data ? formatEtb(data.reimbursed_santim) : "—"} testId="kpi-reimbursed"
          sub={data ? `${formatEtb(data.awaiting_payout_santim)} approved, awaiting payout` : null} />
      </div>

      {/* Claims by status */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg mb-space-xl">
        <div className="lg:col-span-12 flex flex-col gap-space-lg">
          <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between flex-1">
            <div className="flex items-center justify-between mb-space-md">
              <div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">Claims by Status</h3>
                <span className="font-body-sm text-body-sm text-outline">
                  {data ? `Policy year ${formatDate(data.policy_year.start)} – ${formatDate(data.policy_year.end)}, by receipt date` : ""}
                </span>
              </div>
            </div>
            <div className="flex flex-col items-center justify-center gap-space-md my-2">
              <div className="relative w-44 h-44 shrink-0 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#eaedff" strokeWidth="12" />
                  {arcs.map((arc) => (
                    <circle
                      key={arc.status}
                      cx="50"
                      cy="50"
                      fill="none"
                      r="38"
                      stroke={arc.stroke}
                      strokeDasharray={`${arc.length} ${RING}`}
                      strokeDashoffset={-arc.offset}
                      strokeWidth="12"
                    />
                  ))}
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="font-headline-lg text-headline-lg font-bold text-on-surface leading-none">{total}</span>
                  <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Claims</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-space-md gap-y-space-sm w-fit">
                {SEGMENTS.map((segment) => {
                  const count = data ? data.by_status[segment.status].claims : 0;
                  return (
                    <div key={segment.status} className="flex items-center justify-center gap-2 p-1.5 rounded-lg bg-surface-container-low/50">
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2.5 h-2.5 rounded-full ${segment.dot} shrink-0`}></span>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">{segment.label}</span>
                      </div>
                      <span data-testid={`status-count-${segment.status}`} className="font-label-md text-label-md font-semibold text-on-surface">
                        {count} <span className="text-outline font-normal">({percentOf(count, total)}%)</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Coverage & Identity */}
      <div className="mb-space-xl">
        <div className="flex items-center justify-between mb-space-md">
          <h2 className="font-headline-md text-headline-md text-on-surface font-semibold tracking-tight">Coverage &amp; Identity</h2>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Endod ID (DE + 6 digits) links an employee to their Endod health card</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg">
          <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Employees linked to Endod card</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">
              {data ? data.employees.linked_endod : "—"}
              <span className="font-label-md text-label-md text-on-surface-variant ml-2">/ {data ? data.employees.active : "—"}</span>
            </div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">active employees with an Endod ID</span>
          </div>
          <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Employees reimbursed</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">{data ? data.employees.claimants : "—"}</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">with an approved claim this policy year</span>
          </div>
          <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Annual limit per employee</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">{data ? formatEtb(data.policy.annual_limit_santim) : "—"}</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">
              {data ? `${data.policy.copay_percent}% employee co-pay · dependants ${data.policy.dependants_covered ? "covered" : "not covered"}` : ""}
            </span>
          </div>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-md">
          Coverage check on approval: organisation share = total − employee co-pay, never more than what is left of the annual limit.
          {" "}
          <Link href="/settings" className="text-primary hover:underline">Change the policy</Link>
        </p>
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, testId }: { label: string; value: string; sub?: React.ReactNode; testId: string }) {
  return (
    <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between relative overflow-hidden group transition-all">
      <div>
        <div className="flex items-center justify-between mb-space-sm">
          <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">{label}</span>
        </div>
        <div data-testid={testId} className="font-display-lg text-display-lg text-on-surface tracking-tight mb-1">{value}</div>
        {sub ? <span className="font-body-sm text-body-sm text-on-surface-variant">{sub}</span> : null}
      </div>
    </div>
  );
}
