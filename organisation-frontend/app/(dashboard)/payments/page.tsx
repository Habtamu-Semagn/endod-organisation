"use client";

import { useState } from "react";

export default function PaymentsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [paid, setPaid] = useState<Set<string>>(new Set());

  const openBatchModal = () => setModalOpen(true);
  const closeBatchModal = () => setModalOpen(false);

  const confirmBatchTransfer = () => {
    setConfirming(true);
    setTimeout(() => {
      setModalOpen(false);
      setConfirming(false);
      window.alert(
        "Payment Batch #BATCH-105-ETH has been authorized and queued to CBE and Telebirr direct pipelines. Receipt vouchers generated."
      );
    }, 1200);
  };

  const executeFullBatch = () => openBatchModal();
  const triggerBatchExport = () =>
    window.alert("Generating combined Telebirr CSV and National Bank of Ethiopia EFT formatted export file...");
  const downloadCbeFormat = () =>
    window.alert("Generating CBE proprietary direct credit TXT payload...");
  const markAllSelectedPaid = () =>
    window.alert("Validating branch codes and beneficiary account hashes for all 38 claims...");

  const markSinglePaid = (claimId: string) => {
    setPaid((prev) => new Set(prev).add(claimId));
  };

  const handleMasterChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const checks = document.querySelectorAll<HTMLInputElement>(".claim-check");
    checks.forEach((c) => (c.checked = e.target.checked));
  };

  const isPaid = (id: string) => paid.has(id);

  return (
    <div className="flex flex-col w-full pb-24">
      {/* Top Command & Action Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-space-lg py-space-xl">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-space-sm">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-semibold">Treasury &amp; Settlement Desk</span>
            <span className="w-1.5 h-1.5 rounded-full bg-primary/40" />
            <span className="font-label-sm text-label-sm text-on-surface-variant">FY 2024 / Ethiopian Payroll Q3</span>
          </div>
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">Payment Disbursement &amp; Settlement</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
            Process reimbursement payouts for approved prescription claims via direct corporate bank integrations (CBE, Awash, Dashen, &amp; Telebirr Batch).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-space-md">
          <button
            type="button"
            onClick={triggerBatchExport}
            className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-surface-container-lowest text-on-surface shadow-sm hover:bg-surface-container-high transition-all"
          >
            <span className="material-symbols-outlined text-[19px] text-primary">download</span>
            <span className="font-label-lg text-label-lg">Export Payment File (CSV / ABA / Telebirr)</span>
          </button>
          <button
            type="button"
            onClick={openBatchModal}
            className="inline-flex items-center gap-space-sm px-5 py-2.5 rounded-lg bg-primary text-on-primary shadow-md hover:bg-primary-container transition-all"
          >
            <span className="material-symbols-outlined text-[20px]">send_money</span>
            <span className="font-label-lg text-label-lg font-semibold">Create Payment Batch (ETB 412,850.00)</span>
          </button>
        </div>
      </div>

      {/* KPI Metagrid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-space-lg mb-space-xl">
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Ready for Reimbursement</span>
              <span className="font-display-lg text-display-lg text-on-surface mt-1 tracking-tight">ETB 412,850.00</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-primary-fixed/40 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[22px]">account_balance_wallet</span>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">38 Claims</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Validated &amp; cleared for transfer</span>
            </div>
            <svg className="w-16 h-6 text-primary stroke-current fill-none stroke-2" viewBox="0 0 64 24">
              <path d="M2 18 L16 12 L30 16 L44 8 L62 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">Processed This Month</span>
              <span className="font-display-lg text-display-lg text-on-surface mt-1 tracking-tight">ETB 1,429,650.00</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-secondary-container/50 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined text-[22px]">check_circle</span>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">110 Claims</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Disbursed with bank receipts</span>
            </div>
            <svg className="w-16 h-6 text-secondary stroke-current fill-none stroke-2" viewBox="0 0 64 24">
              <path d="M2 20 L15 17 L28 12 L45 9 L62 3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg shadow-sm flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-md text-label-md text-error uppercase tracking-wider">Failed / Held Payouts</span>
              <span className="font-display-lg text-display-lg text-on-surface mt-1 tracking-tight">ETB 8,400.00</span>
            </div>
            <div className="w-10 h-10 rounded-lg bg-error-container/60 flex items-center justify-center text-error">
              <span className="material-symbols-outlined text-[22px]">error</span>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-error-container text-on-error-container font-label-sm text-label-sm font-semibold">2 Invalid Accounts</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Requires employee update</span>
            </div>
            <button className="font-label-sm text-label-sm text-error underline hover:text-on-error-container">Resolve</button>
          </div>
        </div>
      </div>

      {/* Gateway Channels Micro-Strip */}
      <div className="mb-space-lg grid grid-cols-2 sm:grid-cols-4 gap-space-md">
        {[
          { code: "CBE", name: "Commercial Bank", sub: "Host-to-Host Online" },
          { code: "TB", name: "Telebirr Bulk Pay", sub: "Instant Settlement" },
          { code: "AW", name: "Awash Direct", sub: "RTGS Batch Ready" },
          { code: "DB", name: "Dashen Omnichannel", sub: "Active Cleared" },
        ].map((g) => (
          <div key={g.code} className="flex items-center gap-3 p-3 rounded-lg bg-surface-container-low shadow-sm">
            <div className="w-8 h-8 rounded-full bg-surface-container-lowest flex items-center justify-center font-label-sm text-label-sm font-bold text-primary">{g.code}</div>
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm text-on-surface font-semibold">{g.name}</span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">{g.sub}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Primary Interactive Table Card */}
      <div className="rounded-xl bg-surface-container-lowest shadow-sm overflow-hidden flex flex-col">
        <div className="p-space-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md bg-surface-container-low">
          <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto">
            <button className="px-4 py-2 rounded-lg bg-primary-container text-on-primary-container font-label-md text-label-md font-semibold shadow-sm flex items-center gap-2 whitespace-nowrap">
              <span>Ready to Pay</span>
              <span className="px-1.5 py-0.5 rounded-full bg-primary text-on-primary font-label-sm text-label-sm">38</span>
            </button>
            <button className="px-4 py-2 rounded-lg bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-md text-label-md font-medium transition-colors flex items-center gap-2 whitespace-nowrap">
              <span>Processing #BATCH-104</span>
              <span className="px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm text-label-sm">14</span>
            </button>
            <button className="px-4 py-2 rounded-lg bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-md text-label-md font-medium transition-colors flex items-center gap-2 whitespace-nowrap">
              <span>Completed Payments</span>
              <span className="px-1.5 py-0.5 rounded-full bg-surface-container-high text-on-surface font-label-sm text-label-sm">110</span>
            </button>
            <button className="px-4 py-2 rounded-lg bg-surface-container-lowest text-error hover:bg-error-container/40 font-label-md text-label-md font-medium transition-colors flex items-center gap-2 whitespace-nowrap">
              <span>Failed Payouts</span>
              <span className="px-1.5 py-0.5 rounded-full bg-error-container text-on-error-container font-label-sm text-label-sm">2</span>
            </button>
          </div>
          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="relative w-full md:w-64">
              <span className="material-symbols-outlined absolute left-3 top-2.5 text-outline text-[18px]">search</span>
              <input className="w-full h-9 pl-9 pr-3 rounded-lg bg-surface-container-lowest text-body-sm font-body-sm placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary" placeholder="Filter employee or ref..." type="text" />
            </div>
            <button className="p-2 rounded-lg bg-surface-container-lowest text-on-surface-variant hover:text-on-surface shadow-sm">
              <span className="material-symbols-outlined text-[20px]">filter_list</span>
            </button>
          </div>
        </div>

        {/* Active Selection Notification Strip */}
        <div className="px-space-lg py-2.5 bg-primary-fixed/20 flex items-center justify-between text-on-surface">
          <div className="flex items-center gap-3">
            <input
              defaultChecked
              onChange={handleMasterChange}
              className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer"
              id="master-select"
              type="checkbox"
            />
            <label htmlFor="master-select" className="font-label-md text-label-md font-semibold cursor-pointer">
              38 claims selected <span className="text-on-surface-variant font-normal">(Total: ETB 412,850.00)</span>
            </label>
          </div>
          <div className="flex items-center gap-space-md">
            <span className="font-body-sm text-body-sm text-on-surface-variant hidden sm:inline">Direct disbursements bypass paper processing delays.</span>
            <button
              type="button"
              onClick={markAllSelectedPaid}
              className="font-label-sm text-label-sm text-primary font-semibold hover:underline"
            >
              Recheck Banking Info
            </button>
          </div>
        </div>

        {/* Main Claims Settlement Ledger */}
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-high/60 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                <th className="w-12 px-4 py-3.5 text-center"><span className="sr-only">Select</span></th>
                <th className="px-4 py-3.5">Claim ID &amp; Approval</th>
                <th className="px-4 py-3.5">Employee &amp; Dept</th>
                <th className="px-4 py-3.5">Payout Method / Route</th>
                <th className="px-4 py-3.5">Facility / Prescription</th>
                <th className="px-4 py-3.5 text-right">Amount (ETB)</th>
                <th className="px-4 py-3.5 text-center">Status</th>
                <th className="px-4 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low font-body-md text-body-md text-on-surface">
              {/* Row 1 */}
              <tr className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-4 py-3.5 text-center">
                  <input defaultChecked className="claim-check w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-primary">CLM-AA-9281</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Approved Today, 09:15</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <img className="w-7 h-7 rounded-full object-cover" alt="Bethlehem Haile" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB-1iNIyG25MJk5K1FHnzFringuqfeskSciNMz8stoB8O_MWBY9Z0_c9ZLebf2wF_tfqHus2Bp2FJlcbTQcmVWN7UpK_RLaljjSd0nBFzbAErlBIhCABkGcQmgMC5iILlHZvSHHs3AFRcGuP8JOoLguB637NR7I0dJVaP6TiKp0Th9WRwDGRw4uG1-i7mCIU0pXtzkKZSHse9G9lwLd9INQQo_AK65pA50FSg9c63jvHWNIQsecQYjv" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Bethlehem Haile</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Billing Operations</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-primary" />
                      <span className="font-label-md text-label-md font-medium">Commercial Bank of Ethiopia</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">Acc: 1000...4912</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Kenema Pharmacy #4 (Bole)</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Asthma Inhalers &amp; Anti-histamines</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">ETB 2,150.00</td>
                <td className="px-4 py-3.5 text-center">
                  {isPaid("CLM-AA-9281") ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Ready for Payment</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-right">
                  {isPaid("CLM-AA-9281") ? (
                    <button disabled className="inline-flex items-center gap-1 px-3 py-1 rounded bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm transition-all shadow-sm">
                      <span className="material-symbols-outlined text-[16px] text-tertiary">check_circle</span>
                      <span>Disbursed</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markSinglePaid("CLM-AA-9281")}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-sm text-label-sm transition-all shadow-sm"
                    >
                      <span>Pay via CBE</span>
                      <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </button>
                  )}
                </td>
              </tr>

              {/* Row 2 */}
              <tr className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-4 py-3.5 text-center">
                  <input defaultChecked className="claim-check w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-primary">CLM-AA-9285</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Approved Today, 10:20</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <img className="w-7 h-7 rounded-full object-cover" alt="Yohannes Mengistu" src="https://lh3.googleusercontent.com/aida-public/AB6AXuA2QCcVVGFRbYYymZktWa0X37R-Snz4ydFKqAqrlhht2Y8h24yXW3m0PoZSl82AAhSHYzkTzC0adJaA9gXApLtplvev0am2gJIgAENNp9F6Hip4tHoLiLq9yS1LSA2B8IjYhn_33mdRL8f4UvxWbtqQN2P3zeufvE6ispwvI_yhPjQ2gzhFpwhVdEJMHtyofBzXwz5CO2uAvmbEYI2S1SiiYyKNC0zDwfL4gizOL4PsP7sSv9EYGT7R" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Yohannes Mengistu</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Network Infrastructure</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-secondary" />
                      <span className="font-label-md text-label-md font-medium">Telebirr Corporate</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">+251 91 123 4567</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Lion Pharmacy (Kazanchis)</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Cardiovascular Maintenance Tab</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">ETB 3,400.00</td>
                <td className="px-4 py-3.5 text-center">
                  {isPaid("CLM-AA-9285") ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Ready for Payment</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-right">
                  {isPaid("CLM-AA-9285") ? (
                    <button disabled className="inline-flex items-center gap-1 px-3 py-1 rounded bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm transition-all shadow-sm">
                      <span className="material-symbols-outlined text-[16px] text-tertiary">check_circle</span>
                      <span>Disbursed</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markSinglePaid("CLM-AA-9285")}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-sm text-label-sm transition-all shadow-sm"
                    >
                      <span>Disburse Telebirr</span>
                      <span className="material-symbols-outlined text-[16px]">bolt</span>
                    </button>
                  )}
                </td>
              </tr>

              {/* Row 3 */}
              <tr className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-4 py-3.5 text-center">
                  <input defaultChecked className="claim-check w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-primary">CLM-AA-9274</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Approved Yesterday</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-surface-container-high text-primary flex items-center justify-center font-label-sm text-label-sm font-bold">DB</div>
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Dawit Bekele</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Procurement &amp; Supply</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-tertiary" />
                      <span className="font-label-md text-label-md font-medium">Awash Bank</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">Acc: 0132...9921</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Bethzatha Clinic Dispensary</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Ophthalmology drops &amp; Antibiotics</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">ETB 5,200.00</td>
                <td className="px-4 py-3.5 text-center">
                  {isPaid("CLM-AA-9274") ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Ready for Payment</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-right">
                  {isPaid("CLM-AA-9274") ? (
                    <button disabled className="inline-flex items-center gap-1 px-3 py-1 rounded bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm transition-all shadow-sm">
                      <span className="material-symbols-outlined text-[16px] text-tertiary">check_circle</span>
                      <span>Disbursed</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markSinglePaid("CLM-AA-9274")}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-sm text-label-sm transition-all shadow-sm"
                    >
                      <span>Pay via Awash</span>
                      <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </button>
                  )}
                </td>
              </tr>

              {/* Row 4 */}
              <tr className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-4 py-3.5 text-center">
                  <input defaultChecked className="claim-check w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-primary">CLM-AA-9269</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Approved Yesterday</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <img className="w-7 h-7 rounded-full object-cover" alt="Sara Tefera" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAtPiRJ-qG-idsJx_5fDZh5R01VekDNACZ56UGD6IYOE9XxYJTQBSfquWJuSu-CH5W_X4qaMzYzffhGIpxHTGV5XIyr2WHlg6kZTHau8pCBYJhC3C26Ica2_6Jvfti7ZSZTck-v77DXCdioH59Qq6nferyoPmlDZ_s0XASN7xZBvvVP5OCXoFZxGuJuVI8Q4snAzP9ZVEsEzSy2jKHQyZhQrBlet3jnFF79kkrkNWi_JhNfObbIFMVH" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Sara Tefera</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Mobile App Development</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-primary-container" />
                      <span className="font-label-md text-label-md font-medium">CBE Birr Wallet</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">+251 92 345 6789</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Medhanialem Pharmacy (Bole)</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Prenatal Vitamins &amp; Iron Suppl.</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">ETB 1,450.00</td>
                <td className="px-4 py-3.5 text-center">
                  {isPaid("CLM-AA-9269") ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Ready for Payment</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-right">
                  {isPaid("CLM-AA-9269") ? (
                    <button disabled className="inline-flex items-center gap-1 px-3 py-1 rounded bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm transition-all shadow-sm">
                      <span className="material-symbols-outlined text-[16px] text-tertiary">check_circle</span>
                      <span>Disbursed</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markSinglePaid("CLM-AA-9269")}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-sm text-label-sm transition-all shadow-sm"
                    >
                      <span>Disburse CBE Birr</span>
                      <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </button>
                  )}
                </td>
              </tr>

              {/* Row 5 */}
              <tr className="hover:bg-surface-container-low/60 transition-colors">
                <td className="px-4 py-3.5 text-center">
                  <input defaultChecked className="claim-check w-4 h-4 rounded text-primary focus:ring-primary accent-primary cursor-pointer" type="checkbox" />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-primary">CLM-AA-9260</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Approved 2 days ago</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-surface-container-high text-primary flex items-center justify-center font-label-sm text-label-sm font-bold">NG</div>
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Natnael Girma</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Telecom Solutions</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-secondary-fixed-dim" />
                      <span className="font-label-md text-label-md font-medium">Dashen Bank</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">Acc: 5120...3114</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Hayat Hospital Central Pharmacy</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Post-Op Wound Dressings &amp; Analgesics</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold">ETB 7,800.00</td>
                <td className="px-4 py-3.5 text-center">
                  {isPaid("CLM-AA-9260") ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Ready for Payment</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-right">
                  {isPaid("CLM-AA-9260") ? (
                    <button disabled className="inline-flex items-center gap-1 px-3 py-1 rounded bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm transition-all shadow-sm">
                      <span className="material-symbols-outlined text-[16px] text-tertiary">check_circle</span>
                      <span>Disbursed</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markSinglePaid("CLM-AA-9260")}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded bg-surface-container-high hover:bg-primary hover:text-on-primary text-on-surface font-label-sm text-label-sm transition-all shadow-sm"
                    >
                      <span>Pay via Dashen</span>
                      <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </button>
                  )}
                </td>
              </tr>

              {/* Row 6 - already paid */}
              <tr className="bg-surface-container-low/30 hover:bg-surface-container-low transition-colors opacity-90">
                <td className="px-4 py-3.5 text-center">
                  <span className="material-symbols-outlined text-[18px] text-tertiary">check</span>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md font-semibold text-on-surface">CLM-AA-9244</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Paid 14:10 • Ref: TX-90214</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-2">
                    <img className="w-7 h-7 rounded-full object-cover" alt="Rahel Assefa" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCiujSA7Hasp5TpYaAs6k6bolaTdX3K0Koqv5XAdFrja-qjPWFG8DaLGqSoHn2U9ETp6QRZtC2AqAfqwmg5iqeaCVSfbeITUSubyhianmmGqR1KHE53z6dNlCA_UCB9IxH4YCNoTyP-K_V6rKTW3Q9vNGK34Wu-cFPhxfBsGKLbFSbJzLJEBLW4j4pE84yhI8pW3B2WF4H7W2vvOXbTrwdOy8sX_M7vlByEr2fxuw3LxfznFJf5o43E" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-label-md text-label-md font-semibold truncate">Rahel Assefa</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Corporate Relations</span>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-tertiary" />
                      <span className="font-label-md text-label-md font-medium">Telebirr Wallet</span>
                    </div>
                    <span className="font-label-sm text-label-sm text-on-surface-variant font-numeric-currency">+251 91 234 5678</span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-col">
                    <span className="font-label-md text-label-md">Lion Pharmacy (Sarbet)</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">Pediatric Antipyretic Syrup</span>
                  </div>
                </td>
                <td className="px-4 py-3.5 text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 820.00</td>
                <td className="px-4 py-3.5 text-center">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-tertiary-container text-on-tertiary-container font-label-sm text-label-sm font-semibold">Paid</span>
                </td>
                <td className="px-4 py-3.5 text-right">
                  <button className="inline-flex items-center gap-1 px-3 py-1 rounded text-on-surface-variant hover:text-primary font-label-sm text-label-sm transition-colors">
                    <span className="material-symbols-outlined text-[16px]">receipt_long</span>
                    <span>Slip</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Table Footer / Pagination */}
        <div className="p-space-md bg-surface-container-low flex flex-col sm:flex-row items-center justify-between gap-space-md">
          <span className="font-body-sm text-body-sm text-on-surface-variant">Showing 6 of 38 pre-cleared payouts ready for automatic batch upload</span>
          <div className="flex items-center gap-1">
            <button className="px-3 py-1.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-md text-label-md shadow-sm disabled:opacity-50" disabled>Previous</button>
            <button className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-md text-label-md font-semibold shadow-sm">1</button>
            <button className="px-3 py-1.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-md text-label-md shadow-sm hover:bg-surface-container-high">2</button>
            <button className="px-3 py-1.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-md text-label-md shadow-sm hover:bg-surface-container-high">3</button>
            <button className="px-3 py-1.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-md text-label-md shadow-sm hover:bg-surface-container-high">Next</button>
          </div>
        </div>
      </div>

      {/* Persistent Floating Batch Disbursement Control Bar */}
      <div className="fixed bottom-6 left-72 right-8 z-30 transition-transform duration-300 transform translate-y-0" id="batchDrawer">
        <div className="bg-inverse-surface text-inverse-on-surface p-space-md sm:p-space-lg rounded-xl shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md backdrop-blur-xl">
          <div className="flex items-center gap-space-md">
            <div className="w-11 h-11 rounded-lg bg-primary-fixed/20 text-primary-fixed flex items-center justify-center">
              <span className="material-symbols-outlined text-[26px]">folder_zip</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-headline-sm text-headline-sm font-semibold tracking-tight">Active Batch: #BATCH-105-ETH</span>
                <span className="px-2 py-0.5 rounded-full bg-secondary text-on-secondary font-label-sm text-label-sm uppercase">CBE / Telebirr</span>
              </div>
              <span className="font-body-sm text-body-sm opacity-80">38 claims ready for disbursement • Total volume: ETB 412,850.00</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-space-sm w-full md:w-auto justify-end">
            <div className="hidden lg:flex flex-col text-right mr-3">
              <span className="font-label-sm text-label-sm opacity-70">Direct Corporate API</span>
              <span className="font-label-md text-label-md text-primary-fixed font-semibold">Connected to CBE Gateway</span>
            </div>
            <button
              type="button"
              onClick={downloadCbeFormat}
              className="px-4 py-2 rounded-lg bg-surface-container-highest/20 text-inverse-on-surface hover:bg-surface-container-highest/30 font-label-md text-label-md transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[18px]">sim_card_download</span>
              <span>Download Bank TXT</span>
            </button>
            <button
              type="button"
              onClick={executeFullBatch}
              className="px-5 py-2 rounded-lg bg-primary text-on-primary hover:bg-primary-container font-label-lg text-label-lg font-semibold shadow-md transition-all flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-[20px]">task_alt</span>
              <span>Authorize Payout (ETB 412,850.00)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-on-surface/40 backdrop-blur-sm">
          <div className="bg-surface-container-lowest rounded-xl max-w-lg w-full p-space-xl shadow-2xl flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center text-on-secondary-container">
                  <span className="material-symbols-outlined text-[20px]">security</span>
                </div>
                <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Authorize Treasury Payout</h3>
              </div>
              <button type="button" onClick={closeBatchModal} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant">
              You are about to disburse payment for <strong className="text-on-surface">38 approved employee prescription claims</strong> totaling{" "}
              <strong className="text-primary font-numeric-currency font-semibold">ETB 412,850.00</strong>.
            </p>
            <div className="bg-surface-container-low p-space-md rounded-lg flex flex-col gap-2">
              <div className="flex justify-between font-body-sm text-body-sm">
                <span className="text-on-surface-variant">Commercial Bank of Ethiopia (Direct):</span>
                <span className="font-numeric-currency text-on-surface font-semibold">ETB 245,100.00 (19 claims)</span>
              </div>
              <div className="flex justify-between font-body-sm text-body-sm">
                <span className="text-on-surface-variant">Telebirr Corporate Batch:</span>
                <span className="font-numeric-currency text-on-surface font-semibold">ETB 98,400.00 (11 claims)</span>
              </div>
              <div className="flex justify-between font-body-sm text-body-sm">
                <span className="text-on-surface-variant">Awash &amp; Dashen RTGS:</span>
                <span className="font-numeric-currency text-on-surface font-semibold">ETB 69,350.00 (8 claims)</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input className="w-4 h-4 rounded text-primary focus:ring-primary accent-primary" id="auditCheck" type="checkbox" />
              <label htmlFor="auditCheck" className="font-body-sm text-body-sm text-on-surface-variant cursor-pointer">
                I confirm pharmacy receipts and physician stamps are verified for compliance.
              </label>
            </div>
            <div className="flex items-center justify-end gap-space-md pt-2">
              <button
                type="button"
                onClick={closeBatchModal}
                className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md hover:bg-surface-variant transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmBatchTransfer}
                disabled={confirming}
                className="px-5 py-2 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-primary-container transition-all flex items-center gap-2"
              >
                {confirming ? (
                  <>
                    <span className="material-symbols-outlined text-[18px] animate-spin">refresh</span>
                    <span>Processing Wire...</span>
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[18px]">verified_user</span>
                    <span>Execute Disbursement</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
