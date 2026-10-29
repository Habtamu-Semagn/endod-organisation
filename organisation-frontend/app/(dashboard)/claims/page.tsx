"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { EmptyRow, ErrorBanner, StatusBadge, useApi } from "@/components/ui";
import { formatDate, formatEtb } from "@/lib/format";
import type { ClaimList } from "@/lib/types";
import { Icon, type IconName } from "@/components/Icon";

const TABS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending Approval" },
  { key: "approved", label: "Approved" },
  { key: "paid", label: "Paid" },
  { key: "rejected", label: "Rejected" },
] as const;

const PAGE_SIZE = 20;

export default function ClaimsPage() {
  return (
    <Suspense fallback={<p className="pt-space-lg font-body-sm text-body-sm text-on-surface-variant">Loading claims…</p>}>
      <ClaimsContent />
    </Suspense>
  );
}

function ClaimsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const status = params.get("status") ?? "all";
  const q = params.get("q") ?? "";
  const department = params.get("department") ?? "";
  const pharmacy = params.get("pharmacy") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const query = new URLSearchParams();
  if (status !== "all") query.set("status", status);
  if (q) query.set("q", q);
  if (department) query.set("department", department);
  if (pharmacy) query.set("pharmacy", pharmacy);
  if (from) query.set("from", from);
  if (to) query.set("to", to);
  query.set("page", String(page));
  query.set("page_size", String(PAGE_SIZE));
  const { data, error } = useApi<ClaimList>(`claims?${query.toString()}`);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    const text = next.toString();
    router.replace(text ? `${pathname}?${text}` : pathname);
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const first = data && data.total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = data ? Math.min(page * PAGE_SIZE, data.total) : 0;

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Operational Banner / Sub-Header */}
      <div className="flex flex-col gap-space-sm pt-space-lg mb-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">Prescription Claims Management</h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
              Enter employees&apos; pharmacy receipts, check them against the benefit policy, and approve or reject reimbursements.
            </p>
          </div>
          <div className="flex items-center gap-space-sm">
            <div className="flex items-center gap-space-sm bg-surface-container-low p-1.5 rounded-xl">
              <div className="px-space-md py-1 bg-surface-container-lowest rounded-lg flex items-center gap-2">
                <Icon aria-hidden="true" name="account_balance_wallet" className="text-secondary" size={18} />
                <div className="flex flex-col">
                  <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Pending Total</span>
                  <span data-testid="pending-total" className="font-numeric-currency text-numeric-currency text-on-surface font-bold">
                    {data ? formatEtb(data.pending_total_santim) : "—"}
                  </span>
                </div>
              </div>
            </div>
            <Link
              href="/claims/new"
              className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-secondary transition-all"
            >
              <Icon aria-hidden="true" name="add" size={20} />
              <span>New Claim</span>
            </Link>
          </div>
        </div>
        {/* Filter Tabs with Badges */}
        <div className="flex items-center justify-between mt-space-md border-b-0 overflow-x-auto pb-1">
          <div className="flex items-center gap-space-xs bg-surface-container-low p-1 rounded-xl" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={status === t.key}
                onClick={() => update({ status: t.key === "all" ? null : t.key })}
                className={`px-space-md py-2 rounded-lg font-label-lg text-label-lg flex items-center gap-2 transition-colors ${
                  status === t.key
                    ? "bg-surface-container-lowest text-on-surface font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {t.key === "pending" && <span className="w-2 h-2 rounded-full bg-amber-500" />}
                <span>{t.label}</span>
                <span
                  data-testid={`tab-count-${t.key}`}
                  className={`px-2 py-0.5 rounded-full font-label-sm text-label-sm ${
                    status === t.key && t.key === "pending"
                      ? "bg-amber-100 text-amber-800 font-semibold"
                      : "bg-surface-container-highest text-on-surface-variant"
                  }`}
                >
                  {data ? data.counts[t.key] : "·"}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Filters & Controls Bar */}
      <div className="bg-surface-container-lowest rounded-xl p-space-md mb-space-lg flex flex-wrap items-center gap-space-md justify-between relative">
        {openMenu && <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />}
        <SearchBox key={q} initial={q} onSearch={(value) => update({ q: value || null })} />
        <div className="flex flex-wrap items-center gap-space-sm">
          <label className="h-10 px-3 bg-surface-container-low rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface">
            <Icon aria-hidden="true" name="calendar_month" className="text-primary" size={18} />
            <input aria-label="Receipts from" type="date" value={from} onChange={(e) => update({ from: e.target.value || null })} className="bg-transparent focus:outline-none" />
            <span className="text-outline">–</span>
            <input aria-label="Receipts to" type="date" value={to} onChange={(e) => update({ to: e.target.value || null })} className="bg-transparent focus:outline-none" />
          </label>
          <Menu
            id="department"
            icon="domain"
            open={openMenu}
            setOpen={setOpenMenu}
            label={department || "All Departments"}
            options={["", ...(data?.departments ?? [])]}
            render={(value) => value || "All Departments"}
            onPick={(value) => update({ department: value || null })}
          />
          <Menu
            id="pharmacy"
            icon="local_pharmacy"
            open={openMenu}
            setOpen={setOpenMenu}
            label={pharmacy || "All Pharmacies"}
            options={["", ...(data?.pharmacies ?? [])]}
            render={(value) => value || "All Pharmacies"}
            onPick={(value) => update({ pharmacy: value || null })}
          />
        </div>
      </div>
      <ErrorBanner message={error} testId="load-error" />

      {/* Claim Management Ledger Table */}
      <div className="grid grid-cols-12 gap-space-lg items-start">
        <div className="col-span-12 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
            <div className="p-space-md bg-surface-container-low flex items-center justify-between">
              <span className="font-label-sm text-label-sm text-on-surface uppercase font-semibold">
                {data ? `${data.total} ${status === "all" ? "" : TABS.find((t) => t.key === status)?.label ?? ""} claims` : "Claims"}
              </span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">
                {data ? `Showing ${first}–${last} of ${data.total}` : ""}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                    <th className="py-3 px-space-md">Claim ID &amp; Employee</th>
                    <th className="py-3 px-space-md">Pharmacy &amp; Medication</th>
                    <th className="py-3 px-space-md text-right">Receipt (ETB)</th>
                    <th className="py-3 px-space-md text-center">Status</th>
                    <th className="py-3 px-space-md text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-high/40">
                  {data && data.items.length === 0 ? (
                    <EmptyRow colSpan={5}>
                      No claims here yet. <Link href="/claims/new" className="text-primary hover:underline">Enter a claim</Link> from an employee&apos;s receipt.
                    </EmptyRow>
                  ) : null}
                  {data?.items.map((claim) => (
                    <tr
                      key={claim.id}
                      data-testid="claim-row"
                      className="hover:bg-surface-container-low transition-colors cursor-pointer group"
                      onClick={() => router.push(`/claims/${claim.id}`)}
                    >
                      <td className="py-space-md px-space-md">
                        <div className="flex flex-col">
                          <span className="font-label-md text-label-md font-bold text-primary">#{claim.code}</span>
                          <span className="font-body-md text-body-md font-semibold text-on-surface">
                            {claim.employee?.name}
                            {claim.dependant_id ? <span className="font-body-sm text-body-sm text-on-surface-variant"> (dependant)</span> : null}
                          </span>
                          <span className="font-body-sm text-body-sm text-on-surface-variant">
                            {claim.employee?.employee_number} • {claim.employee?.department}
                          </span>
                        </div>
                      </td>
                      <td className="py-space-md px-space-md">
                        <div className="flex flex-col max-w-[260px]">
                          <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                            <Icon aria-hidden="true" name="storefront" className="text-outline" size={14} />
                            {claim.pharmacy_name}
                          </span>
                          <span className="font-body-sm text-body-sm text-on-surface-variant truncate">{(claim.medicines ?? []).join(" + ")}</span>
                          <span className="inline-block mt-0.5 px-1.5 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">
                            Receipt {claim.receipt_number} • {formatDate(claim.receipt_date)}
                          </span>
                        </div>
                      </td>
                      <td className="py-space-md px-space-md text-center align-middle">
                        <div className="flex flex-col items-end">
                          <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">{formatEtb(claim.total_santim, false)}</span>
                          {claim.approved_santim !== null ? (
                            <span className="font-label-sm text-label-sm text-on-surface-variant">Reimbursed {formatEtb(claim.approved_santim, false)}</span>
                          ) : claim.status === "rejected" ? (
                            <span className="font-label-sm text-label-sm text-error truncate max-w-[180px]">{claim.rejection_reason}</span>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-space-md px-space-md text-center align-middle">
                        <StatusBadge status={claim.status} />
                      </td>
                      <td className="py-space-md px-space-md text-center align-middle">
                        <Link
                          href={`/claims/${claim.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="px-5 py-2 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-lg text-label-lg font-semibold transition-all"
                        >
                          Detail
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-space-md bg-surface-container-low flex flex-wrap items-center justify-between gap-space-md text-on-surface-variant font-label-sm text-label-sm">
              <span>{data ? `Page ${page} of ${pages}` : ""}</span>
              <div className="flex items-center gap-1">
                <button
                  className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface disabled:opacity-40"
                  disabled={page <= 1}
                  onClick={() => update({ page: String(page - 1) })}
                >
                  Previous
                </button>
                <span className="px-2.5 py-1 rounded bg-primary text-on-primary font-semibold">{page}</span>
                <button
                  className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface hover:bg-surface-container disabled:opacity-40"
                  disabled={page >= pages}
                  onClick={() => update({ page: String(page + 1) })}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Menu({
  id,
  icon,
  label,
  options,
  render,
  onPick,
  open,
  setOpen,
}: {
  id: string;
  icon: IconName;
  label: string;
  options: string[];
  render: (value: string) => string;
  onPick: (value: string) => void;
  open: string | null;
  setOpen: (value: string | null) => void;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Filter by ${id}`}
        onClick={() => setOpen(open === id ? null : id)}
        className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors"
      >
        <Icon aria-hidden="true" name={icon} className="text-outline" size={18} />
        <span>{label}</span>
        <Icon aria-hidden="true" name="expand_more" className="text-outline" size={16} />
      </button>
      {open === id && (
        <div className="absolute z-20 mt-1 w-56 max-h-72 overflow-y-auto bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
          {options.map((value) => (
            <button
              key={value || "all"}
              type="button"
              onClick={() => {
                onPick(value);
                setOpen(null);
              }}
              className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low"
            >
              {render(value)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchBox({ initial, onSearch }: { initial: string; onSearch: (value: string) => void }) {
  const [search, setSearch] = useState(initial);
  return (
    <form
      className="flex-1 min-w-[280px] max-w-md relative"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(search.trim());
      }}
    >
      <Icon aria-hidden="true" name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" size={18} />
      <input
        aria-label="Search claims list"
        className="w-full h-10 pl-9 pr-4 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary"
        placeholder="Search by employee name, pharmacy, receipt # or claim number..."
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
    </form>
  );
}
