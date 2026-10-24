"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ClaimsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("pending");
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [calendar, setCalendar] = useState("Oct 1 - Oct 31, 2024");
  const [department, setDepartment] = useState("All Departments");
  const [pharmacy, setPharmacy] = useState("All Pharmacies");

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Operational Banner / Sub-Header */}
      <div className="flex flex-col gap-space-sm pt-space-lg mb-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">
              Prescription Claims Management
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
              Review submitted prescription receipts, verify pharmacy invoices, approve reimbursements, or request clarifications.
            </p>
          </div>
          {/* Quick Summary Metric Pills */}
          <div className="flex items-center gap-space-sm bg-surface-container-low p-1.5 rounded-xl">
            <div className="px-space-md py-1 bg-surface-container-lowest rounded-lg  flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-[18px]">account_balance_wallet</span>
              <div className="flex flex-col">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Pending Total</span>
                <span className="font-numeric-currency text-numeric-currency text-on-surface font-bold">ETB 41,850.00</span>
              </div>
            </div>
          </div>
        </div>
        {/* Filter Tabs with Badges */}
        <div className="flex items-center justify-between mt-space-md border-b-0 overflow-x-auto pb-1">
          <div className="flex items-center gap-space-xs bg-surface-container-low p-1 rounded-xl">
            {[
              { key: "all", label: "All", badge: "148", color: "" },
              { key: "pending", label: "Pending Approval", badge: "19", color: "amber" },
              { key: "approved", label: "Approved", badge: "94", color: "" },
              { key: "paid", label: "Paid", badge: "28", color: "" },
              { key: "rejected", label: "Rejected", badge: "7", color: "" },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-space-md py-2 rounded-lg font-label-lg text-label-lg flex items-center gap-2 transition-colors ${
                  activeTab === t.key
                    ? "bg-surface-container-lowest text-on-surface font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
                }`}
              >
                {t.key === "pending" && <span className="w-2 h-2 rounded-full bg-amber-500" />}
                <span>{t.label}</span>
                <span
                  className={`px-2 py-0.5 rounded-full font-label-sm text-label-sm ${
                    activeTab === t.key && t.key === "pending"
                      ? "bg-amber-100 text-amber-800 font-semibold"
                      : "bg-surface-container-highest text-on-surface-variant"
                  }`}
                >
                  {t.badge}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Filters & Controls Bar */}
      <div className="bg-surface-container-lowest rounded-xl p-space-md  mb-space-lg flex flex-wrap items-center gap-space-md justify-between relative">
        {openMenu && <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />}
        <div className="flex-1 min-w-[280px] max-w-md relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">search</span>
          <input className="w-full h-10 pl-9 pr-4 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary " placeholder="Search by employee name, pharmacy, invoice #, claim ID..." type="text" />
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          <div className="relative">
            <button onClick={() => setOpenMenu(openMenu === "calendar" ? null : "calendar")} className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors ">
              <span className="material-symbols-outlined text-[18px] text-primary">calendar_month</span>
              <span>{calendar}</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
            {openMenu === "calendar" && (
              <div className="absolute z-20 mt-1 w-48 bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
                {["Oct 1 - Oct 31, 2024", "Nov 1 - Nov 30, 2024", "Dec 1 - Dec 31, 2024"].map((opt) => (
                  <button key={opt} onClick={() => { setCalendar(opt); setOpenMenu(null); }} className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low">{opt}</button>
                ))}
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => setOpenMenu(openMenu === "department" ? null : "department")} className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors ">
              <span className="material-symbols-outlined text-[18px] text-outline">domain</span>
              <span>{department}</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
            {openMenu === "department" && (
              <div className="absolute z-20 mt-1 w-48 bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
                {["All Departments", "Tech", "HR", "Logistics", "Marketing", "Finance"].map((opt) => (
                  <button key={opt} onClick={() => { setDepartment(opt); setOpenMenu(null); }} className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low">{opt}</button>
                ))}
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => setOpenMenu(openMenu === "pharmacy" ? null : "pharmacy")} className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors ">
              <span className="material-symbols-outlined text-[18px] text-outline">local_pharmacy</span>
              <span>{pharmacy === "All Pharmacies" ? "All Pharmacies (Kenema, Lion, Kadisco...)" : pharmacy}</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
            {openMenu === "pharmacy" && (
              <div className="absolute z-20 mt-1 w-56 bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
                {["All Pharmacies", "Kenema Pharmacy Bole", "Lion Pharmacy Kazanchis", "Red Cross Pharmacy Mexico", "St. Gabriel General Hospital"].map((opt) => (
                  <button key={opt} onClick={() => { setPharmacy(opt); setOpenMenu(null); }} className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low">{opt}</button>
                ))}
              </div>
            )}
          </div>
          <div className="relative">
            <button onClick={() => setOpenMenu(openMenu === "batch" ? null : "batch")} className="h-10 px-4 bg-surface-container-high hover:bg-surface-container-highest text-on-surface rounded-lg font-label-md text-label-md font-semibold flex items-center gap-2 transition-colors">
              <span className="material-symbols-outlined text-[18px]">checklist</span>
              <span>Batch Actions</span>
              <span className="material-symbols-outlined text-[16px]">arrow_drop_down</span>
            </button>
            {openMenu === "batch" && (
              <div className="absolute z-20 mt-1 w-48 bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
                {["Approve Selected", "Reject Selected", "Mark as Paid", "Export CSV"].map((opt) => (
                  <button key={opt} onClick={() => { alert(opt); setOpenMenu(null); }} className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low">{opt}</button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-12 gap-space-lg items-start">
        {/* LEFT: Claim Management Ledger Table */}
        <div className="col-span-12 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest rounded-xl  overflow-hidden">
            <div className="p-space-md bg-surface-container-low flex items-center justify-between">
              <div className="flex items-center gap-space-sm">
                <span className="font-label-sm text-label-sm text-on-surface uppercase font-semibold">19 Pending Clinical Verifications</span>
              </div>
              <div className="flex items-center gap-space-sm">
                <span className="font-body-sm text-body-sm text-on-surface-variant">Showing 5 of 19 records</span>
                <button className="p-1 rounded hover:bg-surface-container text-on-surface-variant" title="Sort by Date">
                  <span className="material-symbols-outlined text-[18px]">swap_vert</span>
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                    <th className="py-3 px-space-md">Claim ID &amp; Employee</th>
                    <th className="py-3 px-space-md">Pharmacy &amp; Medication</th>
                    <th className="py-3 px-space-md text-right">Invoice (ETB)</th>
                    <th className="py-3 px-space-md text-center">Status</th>
                    <th className="py-3 px-space-md text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-high/40">
                  {/* Row 1 selected */}
                  <tr className="bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer group relative" onClick={() => router.push("/claims/CLM-8921")} style={{ display: (activeTab === "all" || activeTab === "pending") && (department === "All Departments" || department === "Tech") && (pharmacy === "All Pharmacies" || pharmacy === "Kenema Pharmacy Bole") ? "" : "none" }}>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-1.5">
                          <span className="font-label-md text-label-md font-bold text-primary">#CLM-8921</span>
                          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                        </div>
                        <span className="font-headline-sm text-body-md font-semibold text-on-surface">Dawit Bekele</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">Software Eng • Tech</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col max-w-[200px]">
                        <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                          <span className="material-symbols-outlined text-secondary text-[14px]">storefront</span>
                          Kenema Pharmacy Bole
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant truncate">Insulin Glargine + Test Strips</span>
                        <span className="inline-block mt-0.5 px-1.5 py-0.2 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">Chronic / Diabetes</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <div className="flex flex-col items-end">
                        <span className="font-numeric-currency text-numeric-currency font-bold text-on-surface">5,200.00</span>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">0% Co-pay</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-top">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-label-sm text-label-sm font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                        Pending
                      </span>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <button type="button" className="px-5 py-2 bg-primary text-on-primary rounded-md font-label-lg text-label-lg font-semibold transition-all">Detail</button>
                    </td>
                  </tr>
                  {/* Row 2 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8921")} style={{ display: (activeTab === "all" || activeTab === "pending") && (department === "All Departments" || department === "HR") && (pharmacy === "All Pharmacies" || pharmacy === "Lion Pharmacy Kazanchis") ? "" : "none" }}>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <span className="font-label-md text-label-md font-medium text-on-surface-variant">#CLM-8920</span>
                        <span className="font-body-md text-body-md font-semibold text-on-surface">Bethlehem Haile</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">People Ops • HR</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col max-w-[200px]">
                        <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                          <span className="material-symbols-outlined text-outline text-[14px]">storefront</span>
                          Lion Pharmacy Kazanchis
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant truncate">Amoxicillin + Inhaler</span>
                        <span className="inline-block mt-0.5 px-1.5 py-0.2 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">Respiratory</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <div className="flex flex-col items-end">
                        <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">2,150.00</span>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">10% Co-pay</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-top">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-label-sm text-label-sm font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                        Pending
                      </span>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <button type="button" className="px-5 py-2 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-lg text-label-lg font-semibold transition-all">Detail</button>
                    </td>
                  </tr>
                  {/* Row 3 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8920")} style={{ display: (activeTab === "all" || activeTab === "approved") && (department === "All Departments" || department === "Finance") && (pharmacy === "All Pharmacies" || pharmacy === "Kadisco General Hospital") ? "" : "none" }}>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <span className="font-label-md text-label-md font-medium text-on-surface-variant">#CLM-8919</span>
                        <span className="font-body-md text-body-md font-semibold text-on-surface">Yohannes Mengistu</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">Finance • Accounting</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col max-w-[200px]">
                        <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                          <span className="material-symbols-outlined text-outline text-[14px]">local_hospital</span>
                          Kadisco General Hospital
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant truncate">Atorvastatin 20mg</span>
                        <span className="inline-block mt-0.5 px-1.5 py-0.2 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">Cardiovascular</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <div className="flex flex-col items-end">
                        <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">3,400.00</span>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">Reimbursable</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-top">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 font-label-sm text-label-sm font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                        Approved
                      </span>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <button type="button" className="px-5 py-2 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-lg text-label-lg font-semibold transition-all">Detail</button>
                    </td>
                  </tr>
                  {/* Row 4 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8919")} style={{ display: (activeTab === "all" || activeTab === "paid") && (department === "All Departments" || department === "Marketing") && (pharmacy === "All Pharmacies" || pharmacy === "St. Gabriel General Hospital") ? "" : "none" }}>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <span className="font-label-md text-label-md font-medium text-on-surface-variant">#CLM-8918</span>
                        <span className="font-body-md text-body-md font-semibold text-on-surface">Tsion Alemu</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">Marketing • Growth</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col max-w-[200px]">
                        <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                          <span className="material-symbols-outlined text-outline text-[14px]">local_hospital</span>
                          St. Gabriel General Hospital
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant truncate">Metformin &amp; Multivitamins</span>
                        <span className="inline-block mt-0.5 px-1.5 py-0.2 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">Endocrine</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <div className="flex flex-col items-end">
                        <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">1,890.00</span>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">Telebirr Settled</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-top">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 text-blue-800 font-label-sm text-label-sm font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                        Paid
                      </span>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <button type="button" className="px-5 py-2 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-lg text-label-lg font-semibold transition-all">Detail</button>
                    </td>
                  </tr>
                  {/* Row 5 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8918")} style={{ display: (activeTab === "all" || activeTab === "rejected") && (department === "All Departments" || department === "Logistics") && (pharmacy === "All Pharmacies" || pharmacy === "Red Cross Pharmacy Mexico") ? "" : "none" }}>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <span className="font-label-md text-label-md font-medium text-on-surface-variant">#CLM-8917</span>
                        <span className="font-body-md text-body-md font-semibold text-on-surface">Henok Tsegaye</span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant">Logistics • Dispatch</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col max-w-[200px]">
                        <span className="font-label-md text-label-md text-on-surface font-medium truncate flex items-center gap-1">
                          <span className="material-symbols-outlined text-outline text-[14px]">storefront</span>
                          Red Cross Pharmacy Mexico
                        </span>
                        <span className="font-body-sm text-body-sm text-on-surface-variant truncate">Antibiotics &amp; Ointment</span>
                        <span className="inline-block mt-0.5 px-1.5 py-0.2 font-label-sm text-[10px] rounded bg-surface-container text-on-surface-variant w-max">Dermatology</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <div className="flex flex-col items-end">
                        <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">820.00</span>
                        <span className="font-label-sm text-label-sm text-error">Missing Stamp</span>
                      </div>
                    </td>
                    <td className="py-space-md px-space-md text-center align-top">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-error-container text-on-error-container font-label-sm text-label-sm font-semibold">
                        <span className="w-1.5 h-1.5 rounded-full bg-error" />
                        Rejected
                      </span>
                    </td>
                    <td className="py-space-md px-space-md text-center align-middle">
                      <button type="button" className="px-5 py-2 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-lg text-label-lg font-semibold transition-all">Detail</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="p-space-md bg-surface-container-low flex flex-wrap items-center justify-between gap-space-md text-on-surface-variant font-label-sm text-label-sm">
              <div className="flex items-center gap-2">
                <span>Showing rows 1 - 5 of 19 Pending Claims</span>
              </div>
              <div className="flex items-center gap-1">
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface  disabled:opacity-40" disabled>Previous</button>
                <button className="px-2.5 py-1 rounded bg-primary text-on-primary font-semibold">1</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface  hover:bg-surface-container">2</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface  hover:bg-surface-container">3</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface  hover:bg-surface-container">Next</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
