"use client";

import { useState } from "react";
import { EmptyRow, ErrorBanner, useApi } from "@/components/ui";
import { formatDate, formatEtb, formatMonth, percentOf } from "@/lib/format";
import type { Report } from "@/lib/types";

const SHADES = ["bg-primary", "bg-on-surface-variant", "bg-primary-container", "bg-outline", "bg-secondary", "bg-surface-dim"];

export default function ReportsPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const query = new URLSearchParams();
  if (from) query.set("from", from);
  if (to) query.set("to", to);
  const { data, error } = useApi<Report>(`reports${query.toString() ? `?${query.toString()}` : ""}`);
  const exportQuery = (kind: string) => {
    const params = new URLSearchParams({ kind });
    if (data) {
      params.set("from", data.period.from);
      params.set("to", data.period.to);
    }
    return `/api/export/reports/export?${params.toString()}`;
  };
  const maxMonth = data ? Math.max(1, ...data.by_month.map((m) => m.approved_santim)) : 1;

  return (
    <div className="flex flex-col w-full pb-16 pt-space-lg">
      {/* Top View Heading & Global Export Controls */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-lg mb-space-xl">
        <div className="flex flex-col gap-1 max-w-2xl">
          <div className="flex items-center gap-space-sm mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-container/50 text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
              {data ? `${formatDate(data.period.from)} – ${formatDate(data.period.to)}` : "Policy year"}
            </span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">Benefit Reports &amp; Analytics</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Reimbursed medication spend (approved and paid claims, by receipt date) by month, department, medicine and employee.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-space-md self-start lg:self-auto shrink-0">
          <label className="h-10 px-3 bg-surface-container-lowest rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface">
            <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-primary">calendar_month</span>
            <input aria-label="Report from" type="date" value={from || data?.period.from || ""} onChange={(e) => setFrom(e.target.value)} className="bg-transparent focus:outline-none" />
            <span className="text-outline">–</span>
            <input aria-label="Report to" type="date" value={to || data?.period.to || ""} onChange={(e) => setTo(e.target.value)} className="bg-transparent focus:outline-none" />
          </label>
          <a
            href={exportQuery("month")}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all font-label-lg text-label-lg"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">table_view</span>
            <span>Download CSV (by month)</span>
          </a>
        </div>
      </div>
      <ErrorBanner message={error} testId="load-error" />

      {/* Summary KPI Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        <Kpi label="Total Medication Spend" value={data ? formatEtb(data.totals.approved_santim) : "—"} testId="report-spend" />
        <Kpi label="Total Claims Reimbursed" value={data ? String(data.totals.claims) : "—"} unit="Claims" testId="report-claims" />
        <Kpi label="Average Claim Value" value={data ? formatEtb(data.totals.average_claim_santim) : "—"} />
        <Kpi label="Employees Supported" value={data ? String(data.totals.employees) : "—"} unit="Beneficiaries" />
      </div>

      {/* Analytics Visualization Grid (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg mb-space-xl">
        <div className="p-space-xl rounded-xl bg-surface-container-lowest flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-space-sm">
              <span aria-hidden="true" className="material-symbols-outlined text-primary text-[20px]">domain</span>
              <h2 className="font-headline-sm text-headline-sm text-on-surface">Medication Spend by Department</h2>
            </div>
            <a href={exportQuery("department")} className="font-label-sm text-label-sm text-primary hover:underline">CSV</a>
          </div>
          <div className="flex flex-col gap-5 mt-space-md" data-testid="by-department">
            {data && data.by_department.length === 0 ? <span className="font-body-sm text-body-sm text-on-surface-variant">No reimbursed claims in this period.</span> : null}
            {data?.by_department.map((row, index) => {
              const share = percentOf(row.approved_santim, data.totals.approved_santim);
              return (
                <div key={row.department} className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between font-label-md text-label-md">
                    <span className="text-on-surface font-semibold flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-sm ${SHADES[index % SHADES.length]}`}></span>
                      {row.department}
                    </span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-on-surface font-numeric-currency font-semibold">{formatEtb(row.approved_santim)}</span>
                      <span className="text-outline text-label-sm font-label-sm">({share}%)</span>
                    </div>
                  </div>
                  <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                    <div className={`h-full ${SHADES[index % SHADES.length]} rounded-full transition-all duration-500`} style={{ width: `${share}%` }}></div>
                  </div>
                  <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                    <span>{row.claims} claim(s)</span>
                    <span>{row.employees} Beneficiaries</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="p-space-xl rounded-xl bg-surface-container-lowest flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-space-sm">
              <span aria-hidden="true" className="material-symbols-outlined text-primary text-[20px]">calendar_month</span>
              <h2 className="font-headline-sm text-headline-sm text-on-surface">Medication Spend by Month</h2>
            </div>
            <a href={exportQuery("month")} className="font-label-sm text-label-sm text-primary hover:underline">CSV</a>
          </div>
          <div className="flex flex-col gap-2 mt-space-md" data-testid="by-month">
            {data?.by_month.map((row) => (
              <div key={row.month} className="grid grid-cols-12 items-center gap-2 font-label-md text-label-md">
                <span className="col-span-3 text-on-surface-variant">{formatMonth(row.month)}</span>
                <div className="col-span-6 h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${percentOf(row.approved_santim, maxMonth)}%` }}></div>
                </div>
                <span className="col-span-3 text-right font-numeric-currency text-on-surface">{formatEtb(row.approved_santim, false)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg mb-space-xl">
        <div className="rounded-xl bg-surface-container-lowest overflow-hidden flex flex-col">
          <div className="p-space-lg flex items-center justify-between bg-surface-container-low">
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Spend by Medicine</h2>
            <a href={exportQuery("medicine")} className="font-label-sm text-label-sm text-primary hover:underline">Download CSV</a>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                <th className="px-space-md py-2">Medicine</th>
                <th className="px-space-md py-2 text-right">Quantity</th>
                <th className="px-space-md py-2 text-right">Claims</th>
                <th className="px-space-md py-2 text-right">Receipts (ETB)</th>
              </tr>
            </thead>
            <tbody className="font-body-md text-body-md" data-testid="by-medicine">
              {data && data.by_medicine.length === 0 ? <EmptyRow colSpan={4}>No medicines in this period.</EmptyRow> : null}
              {data?.by_medicine.slice(0, 20).map((row) => (
                <tr key={row.medicine} className="border-t border-surface-container">
                  <td className="px-space-md py-2">{row.medicine}</td>
                  <td className="px-space-md py-2 text-right">{row.quantity}</td>
                  <td className="px-space-md py-2 text-right">{row.claims}</td>
                  <td className="px-space-md py-2 text-right font-numeric-currency">{formatEtb(row.total_santim, false)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="rounded-xl bg-surface-container-lowest overflow-hidden flex flex-col">
          <div className="p-space-lg flex items-center justify-between bg-surface-container-low">
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Employee Utilization Ledger</h2>
            <a href={exportQuery("employee")} className="font-label-sm text-label-sm text-primary hover:underline">Download CSV</a>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                <th className="px-space-md py-2">Employee</th>
                <th className="px-space-md py-2">Department</th>
                <th className="px-space-md py-2 text-right">Claims</th>
                <th className="px-space-md py-2 text-right">Reimbursed (ETB)</th>
              </tr>
            </thead>
            <tbody className="font-body-md text-body-md">
              {data && data.by_employee.length === 0 ? <EmptyRow colSpan={4}>No reimbursed claims in this period.</EmptyRow> : null}
              {data?.by_employee.slice(0, 20).map((row) => (
                <tr key={row.employee_number} className="border-t border-surface-container">
                  <td className="px-space-md py-2">
                    <span className="font-semibold">{row.name}</span>
                    <span className="block font-label-sm text-label-sm text-on-surface-variant font-mono">{row.employee_number}</span>
                  </td>
                  <td className="px-space-md py-2">{row.department}</td>
                  <td className="px-space-md py-2 text-right">{row.claims}</td>
                  <td className="px-space-md py-2 text-right font-numeric-currency">{formatEtb(row.approved_santim, false)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, unit, testId }: { label: string; value: string; unit?: string; testId?: string }) {
  return (
    <div className="p-space-lg rounded-xl bg-surface-container-lowest flex flex-col justify-between">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">{label}</span>
      <div className="flex items-baseline gap-1.5 mt-2">
        <span data-testid={testId} className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">
          {value}
        </span>
        {unit ? <span className="font-label-md text-label-md text-on-surface-variant">{unit}</span> : null}
      </div>
    </div>
  );
}
