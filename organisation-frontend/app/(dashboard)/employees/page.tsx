"use client";

import Link from "next/link";
import { useState } from "react";
import Dialog, { fieldClass, fieldLabelClass } from "@/components/Dialog";
import { Cancelled, usePortal } from "@/components/PortalShell";
import { EmptyRow, ErrorBanner, StatusBadge, SuccessBanner, messageOf, useApi } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { formatDate, formatEtb, initials, parseEtb, PAYOUT_LABELS, santimToInput } from "@/lib/format";
import type { Employee, EmployeeDetail, EmployeeList, ImportPlan } from "@/lib/types";

const PAGE_SIZE = 20;

type EmployeeForm = {
  employee_number: string;
  name: string;
  phone: string;
  department: string;
  endod_id: string;
  payout_method: string;
  payout_account: string;
};

const blankForm: EmployeeForm = {
  employee_number: "",
  name: "",
  phone: "",
  department: "",
  endod_id: "",
  payout_method: "",
  payout_account: "",
};

export default function EmployeesPage() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("active");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState<{ employee: Employee | null } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [drawerKey, setDrawerKey] = useState(0);

  const query = new URLSearchParams({ status, page: String(page), page_size: String(PAGE_SIZE) });
  if (q) query.set("q", q);
  if (department) query.set("department", department);
  const { data, error, reload } = useApi<EmployeeList>(`employees?${query.toString()}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Editorial / Header Row */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-lg pt-space-lg pb-space-lg">
        <div className="flex flex-col max-w-2xl">
          <div className="flex items-center gap-space-sm mb-1.5">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">Workforce Roster</span>
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
              {data ? `Policy year ${formatDate(data.policy_year.start)} – ${formatDate(data.policy_year.end)}` : ""}
            </span>
          </div>
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">Enrolled Employees</h1>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">
            Manage employee eligibility, dependant coverage, payout accounts and prescription medication limits.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-space-md shrink-0">
          {/* A CSV download from the BFF (a route handler), not a page: a plain link. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href="/api/export/employees/export"
            className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-lg text-label-lg hover:bg-surface-container-low transition-all"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[19px] text-on-surface-variant">download</span>
            <span>Export CSV</span>
          </a>
          <button
            className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-lg text-label-lg hover:bg-surface-container-low transition-all"
            type="button"
            onClick={() => setImportOpen(true)}
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[19px] text-on-surface-variant">upload_file</span>
            <span>Import Employees (CSV)</span>
          </button>
          <button
            className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-secondary transition-all"
            onClick={() => setFormOpen({ employee: null })}
            type="button"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">person_add</span>
            <span>Add Single Employee</span>
          </button>
        </div>
      </div>

      {/* Key Metrics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-lg mb-space-xl">
        <Metric label="Total Enrolled" value={data?.counts.active} unit="Active employees" testId="kpi-active" />
        <Metric label="Active Benefit Users" value={data?.counts.claimants} unit="With claims this year" />
        <Metric label="Dependants Covered" value={data?.counts.dependants} unit="Spouses, children & others" />
        <Metric label="Linked to Endod Card" value={data?.counts.linked} unit="With an Endod ID" />
      </div>

      <SuccessBanner message={success} />
      <ErrorBanner message={error} testId="load-error" />

      <div className="w-full flex flex-col gap-space-md mt-space-sm">
        {/* Filter Strip */}
        <div className="bg-surface-container-lowest p-space-md rounded-xl flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-space-md">
          <form
            className="relative flex-1 min-w-[280px]"
            onSubmit={(e) => {
              e.preventDefault();
              setQ(search.trim());
              setPage(1);
            }}
          >
            <span aria-hidden="true" className="material-symbols-outlined absolute left-3.5 top-2.5 text-outline text-[20px]">search</span>
            <input
              aria-label="Search employees"
              className="w-full h-10 pl-11 pr-4 bg-surface rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary"
              placeholder="Search by name, employee number, department, phone or Endod ID..."
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </form>
          <div className="flex flex-wrap items-center gap-space-sm">
            <select
              aria-label="Department"
              className="h-10 pl-3 pr-8 rounded-lg bg-surface text-on-surface font-label-md text-label-md focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Departments ({data?.departments.length ?? 0})</option>
              {data?.departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              aria-label="Status"
              className="h-10 pl-3 pr-8 rounded-lg bg-surface text-on-surface font-label-md text-label-md focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="active">Active ({data?.counts.active ?? 0})</option>
              <option value="inactive">Inactive ({data?.counts.inactive ?? 0})</option>
              <option value="all">Status: All</option>
            </select>
            <button
              className="h-10 px-3 rounded-lg bg-surface hover:bg-surface-container-high text-on-surface-variant flex items-center gap-1 transition-all"
              onClick={() => {
                setDepartment("");
                setStatus("active");
                setQ("");
                setSearch("");
                setPage(1);
              }}
              title="Reset Filters"
              type="button"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[18px]">filter_list_off</span>
              <span className="font-label-sm text-label-sm">Reset</span>
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="w-full bg-surface-container-lowest rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider select-none">
                  <th className="py-3.5 pl-6 pr-4 font-semibold">Employee</th>
                  <th className="py-3.5 px-4 font-semibold">Department</th>
                  <th className="py-3.5 px-4 font-semibold">Phone</th>
                  <th className="py-3.5 px-4 font-semibold">ENDOD ID &amp; Payout</th>
                  <th className="py-3.5 px-4 font-semibold">Dependants</th>
                  <th className="py-3.5 px-4 font-semibold text-center">Claims</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Reimbursed This Year</th>
                  <th className="py-3.5 pr-6 pl-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="font-body-md text-body-md divide-y-0">
                {data && data.items.length === 0 ? <EmptyRow colSpan={8}>No employees match. Add one, or import your roster from a CSV file.</EmptyRow> : null}
                {data?.items.map((emp) => (
                  <tr key={emp.id} data-testid="employee-row" className="hover:bg-surface-container-low transition-colors cursor-pointer" onClick={() => setSelected(emp.id)}>
                    <td className="py-3.5 pl-6 pr-4">
                      <div className="flex items-center gap-3">
                        <div className="relative shrink-0">
                          <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[14px]">
                            {initials(emp.name)}
                          </div>
                          <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full ring-2 ring-surface ${emp.active ? "bg-tertiary" : "bg-outline-variant"}`} />
                        </div>
                        <div className="flex flex-col min-w-0">
                          <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">{emp.name}</span>
                          <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">{emp.employee_number}</span>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">{emp.department}</span>
                      {!emp.active && <span className="block font-body-sm text-body-sm text-error">Inactive</span>}
                    </td>
                    <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">{emp.phone}</td>
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-1">
                        <span className={`font-mono text-label-sm ${emp.endod_id ? "text-on-surface-variant" : "text-outline"}`}>
                          {emp.endod_id ? `${emp.endod_id} (endod_id)` : "not linked"}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold w-fit ${
                            emp.payout_method ? "bg-secondary-container text-on-secondary-container" : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${emp.payout_method ? "bg-secondary" : "bg-amber-500"}`} />
                          {emp.payout_method ? PAYOUT_LABELS[emp.payout_method] : "No payout account"}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
                        <span aria-hidden="true" className="material-symbols-outlined text-[15px] text-primary">{emp.dependants.length ? "diversity_1" : "person"}</span>
                        <span>{emp.dependants.length ? `${emp.dependants.length} dependant${emp.dependants.length > 1 ? "s" : ""}` : "Self Only"}</span>
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold">
                        {emp.claims_count} claim{emp.claims_count === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className={`font-numeric-currency text-numeric-currency font-semibold ${emp.spend_santim ? "text-on-surface" : "text-outline"}`}>
                        {formatEtb(emp.spend_santim)}
                      </span>
                    </td>
                    <td className="py-3.5 pr-6 pl-4 text-right">
                      <button
                        className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold transition-all"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelected(emp.id);
                        }}
                        type="button"
                      >
                        View Profile
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-space-md bg-surface flex flex-col sm:flex-row items-center justify-between gap-space-md">
            <span className="font-body-sm text-body-sm text-on-surface-variant">
              {data ? (
                <>
                  Showing <span className="font-semibold text-on-surface">{data.items.length}</span> of{" "}
                  <span className="font-semibold text-on-surface">{data.total}</span> employees
                </>
              ) : null}
            </span>
            <div className="flex items-center gap-space-xs">
              <button
                className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm disabled:opacity-40"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                type="button"
              >
                Previous
              </button>
              <span className="px-3 py-1 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm font-semibold">{page}</span>
              <button
                className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm disabled:opacity-40"
                disabled={page >= pages}
                onClick={() => setPage(page + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      {selected && (
        <EmployeeDrawer
          key={`${selected}-${drawerKey}`}
          id={selected}
          onClose={() => setSelected(null)}
          onChanged={reload}
          onEdit={(employee) => setFormOpen({ employee })}
        />
      )}
      {formOpen && (
        <EmployeeFormDialog
          employee={formOpen.employee}
          departments={data?.departments ?? []}
          onClose={() => setFormOpen(null)}
          onSaved={(employee, created) => {
            setFormOpen(null);
            setSuccess(created ? `${employee.name} is added.` : `${employee.name} is updated.`);
            reload();
            if (!created) setDrawerKey((k) => k + 1);
          }}
        />
      )}
      {importOpen && (
        <ImportDialog
          onClose={() => setImportOpen(false)}
          onImported={(plan) => {
            setImportOpen(false);
            setSuccess(`Imported: ${plan.summary.create} added, ${plan.summary.update} updated, ${plan.summary.unchanged} unchanged.`);
            reload();
          }}
        />
      )}
    </div>
  );
}

function Metric({ label, value, unit, testId }: { label: string; value: number | undefined; unit: string; testId?: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg flex flex-col justify-between">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">{label}</span>
      <div className="mt-4 flex items-baseline gap-2">
        <span data-testid={testId} className="font-display-lg text-display-lg font-bold text-on-surface tracking-tight">
          {value ?? "—"}
        </span>
        <span className="font-label-md text-label-md text-on-surface-variant">{unit}</span>
      </div>
      <div className="absolute -right-4 -bottom-4 w-24 h-24 rounded-full bg-primary/5 pointer-events-none" />
    </div>
  );
}

// --- the profile drawer ---------------------------------------------------------------------

function EmployeeDrawer({
  id,
  onClose,
  onChanged,
  onEdit,
}: {
  id: string;
  onClose: () => void;
  onChanged: () => void;
  onEdit: (employee: Employee) => void;
}) {
  const { runSensitive } = usePortal();
  const { data: emp, error: loadError, setData } = useApi<EmployeeDetail>(`employees/${id}`);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [addingDependant, setAddingDependant] = useState(false);
  const [dependant, setDependant] = useState({ name: "", relationship: "spouse", birth_date: "" });
  const [policyOpen, setPolicyOpen] = useState(false);

  const run = async (call: () => Promise<EmployeeDetail>) => {
    setBusy(true);
    setError(null);
    try {
      setData(await call());
      onChanged();
      return true;
    } catch (e) {
      if (!(e instanceof Cancelled)) setError(messageOf(e, "That did not work."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 bg-inverse-surface/40 z-50" onClick={onClose} />
      <aside
        data-testid="employee-drawer"
        className="fixed top-0 right-0 h-full w-full max-w-xl bg-surface-container-lowest z-50 flex flex-col justify-between overflow-y-auto"
      >
        {!emp ? (
          <div className="p-space-lg flex flex-col gap-space-md">
            <ErrorBanner message={loadError} />
            {!loadError && <p className="font-body-sm text-body-sm text-on-surface-variant">Loading…</p>}
            <button type="button" className="font-label-md text-label-md text-primary hover:underline w-max" onClick={onClose}>
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="p-space-lg bg-surface-container-low flex items-start justify-between">
              <div className="flex items-center gap-space-md">
                <div className="relative">
                  <div className="w-14 h-14 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[18px] ring-2 ring-primary">
                    {initials(emp.name)}
                  </div>
                  <span className={`absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full ring-2 ring-surface ${emp.active ? "bg-tertiary" : "bg-outline-variant"}`} />
                </div>
                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <h2 data-testid="drawer-name" className="font-headline-lg text-headline-lg font-bold text-on-surface">
                      {emp.name}
                    </h2>
                    <span className="px-2 py-0.5 rounded-md bg-surface font-label-sm text-label-sm font-mono text-primary font-bold">{emp.employee_number}</span>
                  </div>
                  <span className="font-label-lg text-label-lg text-on-surface-variant font-medium">
                    {emp.department}
                    {emp.active ? "" : " • Inactive"}
                  </span>
                </div>
              </div>
              <button aria-label="Close detail pane" className="p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant transition-colors" onClick={onClose} type="button">
                <span aria-hidden="true" className="material-symbols-outlined text-[22px]">close</span>
              </button>
            </div>
            <div className="p-space-lg flex-1 flex flex-col gap-space-lg">
              <ErrorBanner message={error} />
              <div className="p-space-md rounded-xl bg-primary/5 flex items-center justify-between gap-space-md">
                <div className="flex items-center gap-space-md">
                  <span className="p-2.5 rounded-xl bg-primary text-on-primary">
                    <span aria-hidden="true" className="material-symbols-outlined text-[22px]">shield_with_heart</span>
                  </span>
                  <div className="flex flex-col">
                    <span className="font-label-lg text-label-lg font-bold text-on-surface">
                      {formatEtb(emp.policy.annual_limit_santim)} a year · {emp.policy.copay_percent}% co-pay
                    </span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">
                      {emp.policy.override ? "Own policy for this employee" : "Organisation policy"} · dependants{" "}
                      {emp.policy.dependants_covered ? "covered" : "not covered"}
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-space-md rounded-xl bg-surface flex flex-col gap-space-sm">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Contact &amp; Payout</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm mt-1">
                  <Info icon="call" text={emp.phone} />
                  <Info icon="badge" text={emp.endod_id ? `Endod ID ${emp.endod_id}` : "No Endod ID"} />
                  <Info
                    icon="account_balance"
                    text={emp.payout_method ? `${PAYOUT_LABELS[emp.payout_method]} · ${emp.payout_account}` : "No payout account: claims cannot be paid"}
                  />
                  <Info icon="calendar_today" text={`Enrolled ${formatDate(emp.created_at)}`} />
                </div>
              </div>
              <div className="flex flex-col gap-space-sm">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">
                    Covered Dependants ({emp.dependants.filter((d) => d.active).length})
                  </span>
                  <button className="font-label-sm text-label-sm text-primary hover:underline font-semibold" type="button" onClick={() => setAddingDependant(true)}>
                    + Add Dependant
                  </button>
                </div>
                {addingDependant && (
                  <div className="p-space-md rounded-xl bg-surface grid grid-cols-1 sm:grid-cols-3 gap-space-sm">
                    <label className="flex flex-col gap-1">
                      <span className={fieldLabelClass}>Dependant name</span>
                      <input className={fieldClass} value={dependant.name} onChange={(e) => setDependant({ ...dependant, name: e.target.value })} />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className={fieldLabelClass}>Relationship</span>
                      <select className={fieldClass} value={dependant.relationship} onChange={(e) => setDependant({ ...dependant, relationship: e.target.value })}>
                        <option value="spouse">Spouse</option>
                        <option value="child">Child</option>
                        <option value="parent">Parent</option>
                        <option value="other">Other</option>
                      </select>
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className={fieldLabelClass}>Birth date (optional)</span>
                      <input className={fieldClass} type="date" value={dependant.birth_date} onChange={(e) => setDependant({ ...dependant, birth_date: e.target.value })} />
                    </label>
                    <div className="sm:col-span-3 flex justify-end gap-space-sm">
                      <button type="button" className="px-3 py-1.5 rounded-lg bg-surface-container-high font-label-md text-label-md" onClick={() => setAddingDependant(false)}>
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={busy || dependant.name.trim().length < 2}
                        className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md disabled:opacity-50"
                        onClick={async () => {
                          const ok = await run(() =>
                            apiFetch<EmployeeDetail>(`employees/${emp.id}/dependants`, {
                              method: "POST",
                              body: { name: dependant.name, relationship: dependant.relationship, birth_date: dependant.birth_date || null },
                            })
                          );
                          if (ok) {
                            setAddingDependant(false);
                            setDependant({ name: "", relationship: "spouse", birth_date: "" });
                          }
                        }}
                      >
                        Save dependant
                      </button>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
                  {emp.dependants.filter((d) => d.active).length === 0 && !addingDependant ? (
                    <span className="font-body-sm text-body-sm text-on-surface-variant">No dependants.</span>
                  ) : null}
                  {emp.dependants
                    .filter((d) => d.active)
                    .map((d) => (
                      <div key={d.id} data-testid="dependant" className="p-space-md rounded-xl bg-surface flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="p-2 rounded-lg bg-surface-container text-primary">
                            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{d.relationship === "child" ? "child_care" : "person"}</span>
                          </span>
                          <div className="flex flex-col">
                            <span className="font-label-lg text-label-lg font-bold text-on-surface">{d.name}</span>
                            <span className="font-label-sm text-label-sm text-on-surface-variant capitalize">
                              {d.relationship}
                              {d.birth_date ? ` • born ${formatDate(d.birth_date)}` : ""}
                            </span>
                          </div>
                        </div>
                        <button
                          type="button"
                          aria-label={`Remove ${d.name}`}
                          className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high"
                          onClick={() => void run(() => apiFetch<EmployeeDetail>(`employees/${emp.id}/dependants/${d.id}/remove`, { method: "POST" }))}
                        >
                          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">person_remove</span>
                        </button>
                      </div>
                    ))}
                </div>
              </div>
              <div className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-md">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Annual Medication Utilization</span>
                    <span data-testid="drawer-used" className="font-display-lg text-display-lg font-bold text-on-surface mt-1">
                      {formatEtb(emp.usage.used_santim)}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="font-label-sm text-label-sm text-tertiary font-bold px-2.5 py-1 rounded-full bg-secondary-container">
                      {formatEtb(emp.usage.remaining_santim)} left
                    </span>
                    <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">
                      {formatDate(emp.usage.policy_year.start)} – {formatDate(emp.usage.policy_year.end)}
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-space-sm">
                <div className="flex items-center justify-between">
                  <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Prescription Claim Ledger</span>
                  <Link className="font-label-sm text-label-sm text-primary hover:underline font-semibold flex items-center gap-0.5" href={`/claims?q=${encodeURIComponent(emp.employee_number)}`}>
                    All claims
                    <span aria-hidden="true" className="material-symbols-outlined text-[14px]">arrow_forward</span>
                  </Link>
                </div>
                <div className="flex flex-col gap-2">
                  {emp.recent_claims.length === 0 ? <span className="font-body-sm text-body-sm text-on-surface-variant">No claims yet.</span> : null}
                  {emp.recent_claims.map((c) => (
                    <Link key={c.id} href={`/claims/${c.id}`} className="p-space-md rounded-xl bg-surface flex items-center justify-between hover:bg-surface-container-high transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="p-2 rounded-lg bg-surface-container-high text-primary">
                          <span aria-hidden="true" className="material-symbols-outlined text-[19px]">receipt_long</span>
                        </span>
                        <div className="flex flex-col">
                          <span className="font-label-lg text-label-lg font-semibold text-on-surface">{c.pharmacy_name}</span>
                          <span className="font-body-sm text-body-sm text-on-surface-variant">
                            {formatDate(c.receipt_date)} • {c.code}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-numeric-currency text-numeric-currency font-bold text-on-surface">{formatEtb(c.total_santim)}</span>
                        <StatusBadge status={c.status} testId="ledger-status" />
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-space-lg bg-surface-container-low flex flex-wrap items-center justify-between gap-space-md">
              <button
                className="flex-1 py-2.5 px-4 rounded-lg bg-surface text-on-surface font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors flex items-center justify-center gap-2"
                type="button"
                onClick={() => onEdit(emp)}
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">edit</span>
                <span>Edit Employee</span>
              </button>
              <button
                className="flex-1 py-2.5 px-4 rounded-lg bg-surface text-on-surface font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors flex items-center justify-center gap-2"
                type="button"
                disabled={busy}
                onClick={() => void run(() => apiFetch<EmployeeDetail>(`employees/${emp.id}/${emp.active ? "deactivate" : "activate"}`, { method: "POST" }))}
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">{emp.active ? "person_off" : "person_check"}</span>
                <span>{emp.active ? "Deactivate" : "Reactivate"}</span>
              </button>
              <button
                className="flex-1 py-2.5 px-4 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors flex items-center justify-center gap-2"
                type="button"
                onClick={() => setPolicyOpen(true)}
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">edit_note</span>
                <span>Edit Beneficiary Policy</span>
              </button>
            </div>
            {policyOpen && (
              <OverrideDialog
                employee={emp}
                onClose={() => setPolicyOpen(false)}
                onSave={async (body) => {
                  const ok = await run(() =>
                    runSensitive(() =>
                      body
                        ? apiFetch<EmployeeDetail>(`employees/${emp.id}/policy`, { method: "PUT", body })
                        : apiFetch<EmployeeDetail>(`employees/${emp.id}/policy`, { method: "DELETE" })
                    )
                  );
                  if (ok) setPolicyOpen(false);
                }}
                busy={busy}
                error={error}
              />
            )}
          </>
        )}
      </aside>
    </>
  );
}

function Info({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden="true" className="material-symbols-outlined text-outline text-[18px]">{icon}</span>
      <span className="font-body-sm text-body-sm text-on-surface font-mono select-all">{text}</span>
    </div>
  );
}

function OverrideDialog({
  employee,
  onClose,
  onSave,
  busy,
  error,
}: {
  employee: EmployeeDetail;
  onClose: () => void;
  onSave: (body: Record<string, unknown> | null) => Promise<void>;
  busy: boolean;
  error: string | null;
}) {
  const current = employee.policy;
  const [limit, setLimit] = useState(santimToInput(current.annual_limit_santim));
  const [copay, setCopay] = useState(String(current.copay_percent));
  const [dependants, setDependants] = useState(current.dependants_covered);
  const [excluded, setExcluded] = useState(current.excluded_medicines.join("\n"));
  const limitSantim = parseEtb(limit);
  const copayOk = /^\d{1,3}$/.test(copay) && Number(copay) <= 100;
  return (
    <Dialog
      testId="override-dialog"
      title={`Policy for ${employee.name}`}
      description="An employee's own policy replaces the organisation's limit, co-pay, dependant cover and exclusions for them. Saving needs a fresh code."
      confirmLabel="Save policy"
      busy={busy}
      confirmDisabled={limitSantim === null || !copayOk}
      error={error}
      onCancel={onClose}
      onConfirm={() =>
        void onSave({
          annual_limit_santim: limitSantim,
          copay_percent: Number(copay),
          dependants_covered: dependants,
          excluded_medicines: excluded.split("\n").map((s) => s.trim()).filter(Boolean),
        })
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Annual limit (ETB)</span>
          <input className={fieldClass} inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Employee co-pay (%)</span>
          <input className={fieldClass} inputMode="numeric" value={copay} onChange={(e) => setCopay(e.target.value)} />
        </label>
        <label className="sm:col-span-2 flex items-center gap-2 font-body-sm text-body-sm">
          <input type="checkbox" checked={dependants} onChange={(e) => setDependants(e.target.checked)} /> Dependants covered
        </label>
        <label className="sm:col-span-2 flex flex-col gap-1">
          <span className={fieldLabelClass}>Excluded medicines (one per line)</span>
          <textarea className="w-full p-2.5 bg-surface rounded-lg font-body-sm text-body-sm" rows={3} value={excluded} onChange={(e) => setExcluded(e.target.value)} />
        </label>
        {current.override && (
          <button type="button" className="sm:col-span-2 text-left font-label-md text-label-md text-error hover:underline" onClick={() => void onSave(null)}>
            Remove this employee&apos;s own policy (use the organisation&apos;s)
          </button>
        )}
      </div>
    </Dialog>
  );
}

// --- add / edit ---------------------------------------------------------------------------------

function EmployeeFormDialog({
  employee,
  departments,
  onClose,
  onSaved,
}: {
  employee: Employee | null;
  departments: string[];
  onClose: () => void;
  onSaved: (employee: Employee, created: boolean) => void;
}) {
  const [form, setForm] = useState<EmployeeForm>(
    employee
      ? {
          employee_number: employee.employee_number,
          name: employee.name,
          phone: employee.phone,
          department: employee.department,
          endod_id: employee.endod_id ?? "",
          payout_method: employee.payout_method ?? "",
          payout_account: employee.payout_account ?? "",
        }
      : blankForm
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof EmployeeForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.value });

  const save = async () => {
    setBusy(true);
    setError(null);
    const body = { ...form, endod_id: form.endod_id || null, payout_method: form.payout_method || null, payout_account: form.payout_account || null };
    try {
      const saved = employee
        ? await apiFetch<Employee>(`employees/${employee.id}`, { method: "PATCH", body })
        : await apiFetch<Employee>("employees", { method: "POST", body });
      onSaved(saved, !employee);
    } catch (e) {
      setError(messageOf(e, "The employee could not be saved."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      testId="employee-dialog"
      title={employee ? `Edit ${employee.name}` : "Add Single Employee"}
      confirmLabel={employee ? "Save Changes" : "Add Employee"}
      busy={busy}
      confirmDisabled={!form.employee_number.trim() || form.name.trim().length < 2 || !form.phone.trim() || !form.department.trim()}
      error={error}
      onCancel={onClose}
      onConfirm={() => void save()}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Full Name</span>
          <input className={fieldClass} value={form.name} onChange={set("name")} type="text" />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Employee Number</span>
          <input className={fieldClass} value={form.employee_number} onChange={set("employee_number")} type="text" />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Department</span>
          <input className={fieldClass} value={form.department} onChange={set("department")} list="departments" type="text" />
          <datalist id="departments">
            {departments.map((d) => (
              <option key={d} value={d} />
            ))}
          </datalist>
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Mobile Phone</span>
          <input className={fieldClass} value={form.phone} onChange={set("phone")} placeholder="+251911234567" type="tel" />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>ENDOD ID (optional)</span>
          <input className={fieldClass} value={form.endod_id} onChange={set("endod_id")} placeholder="DE123456" type="text" />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Payout Method</span>
          <select className={fieldClass} value={form.payout_method} onChange={set("payout_method")}>
            <option value="">None yet</option>
            {Object.entries(PAYOUT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="sm:col-span-2 flex flex-col gap-1">
          <span className={fieldLabelClass}>Payout Account (bank account number, or the Telebirr phone number)</span>
          <input className={fieldClass} value={form.payout_account} onChange={set("payout_account")} type="text" />
        </label>
      </div>
    </Dialog>
  );
}

// --- CSV import ------------------------------------------------------------------------------------

function ImportDialog({ onClose, onImported }: { onClose: () => void; onImported: (plan: ImportPlan) => void }) {
  const [csv, setCsv] = useState("");
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const readFile = async (file: File | undefined) => {
    setPlan(null);
    setError(null);
    if (!file) return;
    if (file.size > 1_000_000) {
      setError("The file is too large (at most 1 MB).");
      return;
    }
    setCsv(await file.text());
  };

  const preview = async () => {
    setBusy(true);
    setError(null);
    try {
      setPlan(await apiFetch<ImportPlan>("employees/import/preview", { method: "POST", body: { csv } }));
    } catch (e) {
      setError(messageOf(e, "The file could not be read."));
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    setBusy(true);
    setError(null);
    try {
      onImported(await apiFetch<ImportPlan>("employees/import/commit", { method: "POST", body: { csv } }));
    } catch (e) {
      setError(messageOf(e, "Nothing was imported."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      testId="import-dialog"
      wide
      title="Import Employees (CSV)"
      description={
        <>
          Columns: <code>employee_number, name, phone, department</code> and, optionally, <code>endod_id, payout_method, payout_account</code>.
          Rows are matched by employee number: new numbers are added, known ones updated. Nothing is imported while any row has an error.
        </>
      }
      confirmLabel={plan ? `Import ${plan.summary.create + plan.summary.update} employees` : "Preview"}
      busy={busy}
      confirmDisabled={!csv.trim() || (plan !== null && !plan.valid)}
      error={error}
      onCancel={onClose}
      onConfirm={() => void (plan ? commit() : preview())}
    >
      <div className="flex flex-col gap-space-sm">
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>CSV file</span>
          <input type="file" accept=".csv,text/csv" onChange={(e) => void readFile(e.target.files?.[0])} className="font-body-sm text-body-sm" />
        </label>
        <label className="flex flex-col gap-1">
          <span className={fieldLabelClass}>Or paste the CSV</span>
          <textarea
            className="w-full p-2.5 bg-surface rounded-lg font-mono text-body-sm"
            rows={5}
            value={csv}
            onChange={(e) => {
              setCsv(e.target.value);
              setPlan(null);
            }}
          />
        </label>
        {plan && (
          <div className="flex flex-col gap-space-sm">
            <p data-testid="import-summary" className="font-body-sm text-body-sm text-on-surface">
              {plan.summary.create} to add · {plan.summary.update} to update · {plan.summary.unchanged} unchanged ·{" "}
              <span className={plan.summary.error ? "text-error font-semibold" : ""}>{plan.summary.error} with errors</span>
            </p>
            <div className="max-h-64 overflow-y-auto rounded-lg bg-surface">
              <table className="w-full text-left font-body-sm text-body-sm">
                <thead>
                  <tr className="font-label-sm text-label-sm uppercase text-on-surface-variant">
                    <th className="px-2 py-1">Line</th>
                    <th className="px-2 py-1">Employee</th>
                    <th className="px-2 py-1">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.rows.map((row) => (
                    <tr key={row.line} data-testid="import-row" className="border-t border-surface-container align-top">
                      <td className="px-2 py-1">{row.line}</td>
                      <td className="px-2 py-1">
                        {row.employee_number} {row.name}
                      </td>
                      <td className={`px-2 py-1 ${row.action === "error" ? "text-error" : ""}`}>
                        {row.action === "error" ? row.errors.join(" ") : row.action}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}
