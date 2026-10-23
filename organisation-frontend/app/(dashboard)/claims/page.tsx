"use client";

import { useRouter } from "next/navigation";

export default function ClaimsPage() {
  const router = useRouter();

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Operational Banner / Sub-Header */}
      <div className="flex flex-col gap-space-sm pt-space-lg mb-space-lg">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div>
            <div className="flex items-center gap-space-sm mb-1">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-semibold">
                Verification Desk &amp; Audit Portal
              </span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary-fixed-dim" />
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                Addis Ababa Clinical Net (FY2024/Q1)
              </span>
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">
              Prescription Claims Management
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-3xl">
              Review submitted prescription receipts, verify pharmacy invoices, approve reimbursements, or request clarifications.
            </p>
          </div>
          {/* Quick Summary Metric Pills */}
          <div className="flex items-center gap-space-sm bg-surface-container-low p-1.5 rounded-xl">
            <div className="px-space-md py-1 bg-surface-container-lowest rounded-lg shadow-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-[18px]">account_balance_wallet</span>
              <div className="flex flex-col">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">Pending Total</span>
                <span className="font-numeric-currency text-numeric-currency text-on-surface font-bold">ETB 41,850.00</span>
              </div>
            </div>
            <div className="px-space-md py-1 bg-surface-container-lowest rounded-lg shadow-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary text-[18px]">verified_user</span>
              <div className="flex flex-col">
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">SLA Adherence</span>
                <span className="font-numeric-currency text-numeric-currency text-tertiary font-bold">98.4%</span>
              </div>
            </div>
          </div>
        </div>
        {/* Filter Tabs with Badges */}
        <div className="flex items-center justify-between mt-space-md border-b-0 overflow-x-auto pb-1">
          <div className="flex items-center gap-space-xs bg-surface-container-low p-1 rounded-xl">
            <button className="px-space-md py-2 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors flex items-center gap-2">
              <span>All</span>
              <span className="px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm">148</span>
            </button>
            <button className="px-space-md py-2 rounded-lg font-label-md text-label-md bg-surface-container-lowest text-on-surface font-semibold shadow-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <span>Pending Approval</span>
              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-label-sm text-label-sm font-semibold">19</span>
            </button>
            <button className="px-space-md py-2 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors flex items-center gap-2">
              <span>Approved</span>
              <span className="px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm">94</span>
            </button>
            <button className="px-space-md py-2 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors flex items-center gap-2">
              <span>Paid</span>
              <span className="px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm">28</span>
            </button>
            <button className="px-space-md py-2 rounded-lg font-label-md text-label-md text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors flex items-center gap-2">
              <span>Rejected</span>
              <span className="px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm">7</span>
            </button>
          </div>
          <div className="flex items-center gap-space-sm text-on-surface-variant font-label-sm text-label-sm">
            <span className="material-symbols-outlined text-[16px]">sync</span>
            <span>Synced with Telebirr B2B &amp; CBE Core</span>
          </div>
        </div>
      </div>

      {/* Filters & Controls Bar */}
      <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm mb-space-lg flex flex-wrap items-center gap-space-md justify-between">
        <div className="flex-1 min-w-[280px] max-w-md relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">search</span>
          <input className="w-full h-10 pl-9 pr-4 bg-surface-container-low rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary shadow-sm" placeholder="Search by employee name, pharmacy, invoice #, claim ID..." type="text" />
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          <div className="relative group">
            <button className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors shadow-sm">
              <span className="material-symbols-outlined text-[18px] text-primary">calendar_month</span>
              <span>Oct 1 - Oct 31, 2024</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
          </div>
          <div className="relative group">
            <button className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors shadow-sm">
              <span className="material-symbols-outlined text-[18px] text-outline">domain</span>
              <span>All Departments</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
          </div>
          <div className="relative group">
            <button className="h-10 px-3 bg-surface-container-low hover:bg-surface-container rounded-lg flex items-center gap-2 font-label-md text-label-md text-on-surface transition-colors shadow-sm">
              <span className="material-symbols-outlined text-[18px] text-outline">local_pharmacy</span>
              <span>All Pharmacies (Kenema, Lion, Kadisco...)</span>
              <span className="material-symbols-outlined text-[16px] text-outline">expand_more</span>
            </button>
          </div>
          <div className="relative">
            <button className="h-10 px-4 bg-surface-container-high hover:bg-surface-container-highest text-on-surface rounded-lg font-label-md text-label-md font-semibold flex items-center gap-2 transition-colors">
              <span className="material-symbols-outlined text-[18px]">checklist</span>
              <span>Batch Actions</span>
              <span className="material-symbols-outlined text-[16px]">arrow_drop_down</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-12 gap-space-lg items-start">
        {/* LEFT: Claim Management Ledger Table */}
        <div className="col-span-12 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden">
            <div className="p-space-md bg-surface-container-low flex items-center justify-between">
              <div className="flex items-center gap-space-sm">
                <input className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
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
                    <th className="py-3 px-space-md w-10" />
                    <th className="py-3 px-space-md">Claim ID &amp; Employee</th>
                    <th className="py-3 px-space-md">Pharmacy &amp; Medication</th>
                    <th className="py-3 px-space-md text-right">Invoice (ETB)</th>
                    <th className="py-3 px-space-md text-center">Status</th>
                    <th className="py-3 px-space-md text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-high/40">
                  {/* Row 1 selected */}
                  <tr className="bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer group relative" onClick={() => router.push("/claims/CLM-8921")}>
                    <td className="py-space-md px-space-md">
                      <input defaultChecked className="w-4 h-4 rounded text-primary accent-primary cursor-pointer" type="checkbox" />
                    </td>
                    <td className="py-space-md px-space-md">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-1.5">
                          <span className="font-label-md text-label-md font-bold text-primary">#CLM-8921</span>
                          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
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
                    <td className="py-space-md px-space-md text-right align-top">
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
                    <td className="py-space-md px-space-md text-right align-top">
                      <span className="material-symbols-outlined text-primary text-[20px]">chevron_right</span>
                    </td>
                  </tr>
                  {/* Row 2 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8921")}>
                    <td className="py-space-md px-space-md">
                      <input className="w-4 h-4 rounded text-primary accent-primary cursor-pointer" type="checkbox" />
                    </td>
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
                    <td className="py-space-md px-space-md text-right align-top">
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
                    <td className="py-space-md px-space-md text-right align-top">
                      <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
                    </td>
                  </tr>
                  {/* Row 3 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8920")}>
                    <td className="py-space-md px-space-md">
                      <input className="w-4 h-4 rounded text-primary accent-primary cursor-pointer" type="checkbox" />
                    </td>
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
                    <td className="py-space-md px-space-md text-right align-top">
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
                    <td className="py-space-md px-space-md text-right align-top">
                      <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
                    </td>
                  </tr>
                  {/* Row 4 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8919")}>
                    <td className="py-space-md px-space-md">
                      <input className="w-4 h-4 rounded text-primary accent-primary cursor-pointer" type="checkbox" />
                    </td>
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
                    <td className="py-space-md px-space-md text-right align-top">
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
                    <td className="py-space-md px-space-md text-right align-top">
                      <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
                    </td>
                  </tr>
                  {/* Row 5 */}
                  <tr className="hover:bg-surface-container-low transition-colors cursor-pointer group" onClick={() => router.push("/claims/CLM-8918")}>
                    <td className="py-space-md px-space-md">
                      <input className="w-4 h-4 rounded text-primary accent-primary cursor-pointer" type="checkbox" />
                    </td>
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
                    <td className="py-space-md px-space-md text-right align-top">
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
                    <td className="py-space-md px-space-md text-right align-top">
                      <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors text-[20px]">chevron_right</span>
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
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm disabled:opacity-40" disabled>Previous</button>
                <button className="px-2.5 py-1 rounded bg-primary text-on-primary font-semibold">1</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm hover:bg-surface-container">2</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm hover:bg-surface-container">3</button>
                <button className="px-2.5 py-1 rounded bg-surface-container-lowest text-on-surface shadow-sm hover:bg-surface-container">Next</button>
              </div>
            </div>
          </div>
          <div className="p-space-md rounded-xl bg-surface-container-high/60 flex items-start gap-space-md">
            <span className="material-symbols-outlined text-primary text-[22px] mt-0.5">verified</span>
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-on-surface">Ethiopian FDA &amp; EPHI Compliance Check</span>
              <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">All electronic pharmacy vouchers processed through TenaCare are cross-verified with the Ethiopian Ministry of Health drug catalog. Prescriptions exceeding ETB 10,000 require senior physician endorsement.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
