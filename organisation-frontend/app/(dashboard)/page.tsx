export default function OverviewPage() {
  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Action & Context Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-lg pt-space-lg mb-space-xl">
        <div className="flex flex-col gap-space-xs max-w-2xl">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
              Live Benefit Stream
            </span>
            <span className="font-label-sm text-label-sm text-outline">
              Fiscal Year 2024 / Ethiopian Calendar EFY 2016
            </span>
          </div>
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">
            Medication Benefit Overview
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            Real-time overview of employee prescription medication reimbursements, claims
            processing, and disbursements.
          </p>
        </div>
        <div className="flex items-center gap-space-md shrink-0">
          <button className="inline-flex items-center gap-2 px-4 py-2.5 bg-surface-container-lowest text-on-surface hover:bg-surface-container-high transition-all duration-150 rounded-lg shadow-sm font-label-lg text-label-lg" type="button">
            <span className="material-symbols-outlined text-[18px] text-outline">download</span>
            Export Monthly Summary
          </button>
          <button className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary hover:bg-primary-container transition-all duration-150 rounded-lg shadow-sm font-label-lg text-label-lg font-semibold" type="button">
            <span className="material-symbols-outlined text-[20px]">bolt</span>
            Quick Process Claims
          </button>
        </div>
      </div>

      {/* 4 KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        {/* Spend Card */}
        <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
          <div className="absolute -right-4 -bottom-4 w-28 h-28 bg-primary/5 rounded-full blur-2xl group-hover:bg-primary/10 transition-all pointer-events-none"></div>
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Total Medication Spend</span>
              <span className="w-8 h-8 rounded-lg bg-primary-fixed/30 flex items-center justify-center text-primary"><span className="material-symbols-outlined text-[18px]">payments</span></span>
            </div>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mb-1">ETB 1,842,500</div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center text-tertiary font-label-sm text-label-sm bg-tertiary-fixed/40 px-2 py-0.5 rounded-full"><span className="material-symbols-outlined text-[14px] mr-0.5">trending_up</span> +12.4%</span>
              <span className="font-body-sm text-body-sm text-outline">vs last month</span>
            </div>
          </div>
          <div className="pt-space-sm mt-space-sm bg-surface-container-low/60 -mx-space-lg -mb-space-lg px-space-lg py-2">
            <span className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">medication</span> Across 412 active prescriptions</span>
          </div>
        </div>

        {/* Claims Submitted Card */}
        <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Claims Submitted</span>
              <span className="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center text-on-surface-variant"><span className="material-symbols-outlined text-[18px]">receipt_long</span></span>
            </div>
            <div className="flex items-baseline gap-space-sm mb-1">
              <span className="font-display-lg text-display-lg text-on-surface tracking-tight">148</span>
              <span className="font-body-sm text-body-sm text-outline">/ 34 this week</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1 font-label-sm text-label-sm bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded-full font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-secondary"></span> +8 today</span>
              <span className="font-body-sm text-body-sm text-outline">from 11 departments</span>
            </div>
          </div>
          <div className="pt-space-sm mt-space-sm bg-surface-container-low/60 -mx-space-lg -mb-space-lg px-space-lg py-2">
            <div className="w-full bg-surface-container-high h-1.5 rounded-full overflow-hidden"><div className="bg-primary h-full rounded-full" style={{ width: "78%" }}></div></div>
          </div>
        </div>
        {/* Pending Approval Card */}
        <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Pending Approval</span>
              <span className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center text-amber-700"><span className="material-symbols-outlined text-[18px]">hourglass_top</span></span>
            </div>
            <div className="flex items-baseline gap-space-sm mb-1">
              <span className="font-display-lg text-display-lg text-on-surface tracking-tight">19</span>
              <span className="inline-flex items-center font-label-sm text-label-sm bg-amber-100 text-amber-900 px-2 py-0.5 rounded-full font-semibold">Action required</span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-2">Includes 6 OCR stamped receipts awaiting pharmacist audit.</p>
          </div>
          <div className="pt-space-sm mt-space-sm bg-surface-container-low/60 -mx-space-lg -mb-space-lg px-space-lg py-2 flex items-center justify-between">
            <span className="font-body-sm text-body-sm text-outline">Avg turnaround</span>
            <span className="font-label-md text-label-md text-on-surface font-semibold">1.4 days</span>
          </div>
        </div>

        {/* Total Reimbursed YTD */}
        <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between relative overflow-hidden group hover:shadow-md transition-all">
          <div className="absolute -right-4 -bottom-4 w-28 h-28 bg-tertiary-fixed/30 rounded-full blur-2xl group-hover:bg-tertiary-fixed/50 transition-all pointer-events-none"></div>
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Total Reimbursed YTD</span>
              <span className="w-8 h-8 rounded-lg bg-tertiary-container/20 flex items-center justify-center text-tertiary"><span className="material-symbols-outlined text-[18px]">verified_user</span></span>
            </div>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mb-1">ETB 14,280,000</div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-2">Disbursed directly via Telebirr Corporate &amp; CBE Direct.</p>
          </div>
          <div className="pt-space-sm mt-space-sm bg-surface-container-low/60 -mx-space-lg -mb-space-lg px-space-lg py-2 flex items-center justify-between">
            <span className="font-body-sm text-body-sm text-tertiary font-medium flex items-center gap-1"><span className="material-symbols-outlined text-[16px]">check_circle</span> 100% on-schedule</span>
            <span className="font-label-sm text-label-sm text-outline">0 overdue</span>
          </div>
        </div>
      </div>
      {/* Two-Column Middle Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg mb-space-xl">
        {/* Left Column: Spending Trend */}
        <div className="lg:col-span-8 bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-md mb-space-lg">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-headline-md text-headline-md text-on-surface font-semibold tracking-tight">Medication Spending Trend</h2>
                <span className="font-label-sm text-label-sm text-outline uppercase font-semibold">ETB Currency</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">Past 6 months prescription claims trend &amp; payout velocity</p>
            </div>
            <div className="inline-flex p-1 bg-surface-container-high rounded-lg text-on-surface-variant">
              <button className="px-3 py-1 font-label-md text-label-md bg-surface-container-lowest text-primary font-semibold rounded-md shadow-sm transition-all" type="button">6M</button>
              <button className="px-3 py-1 font-label-md text-label-md hover:text-on-surface transition-all" type="button">YTD</button>
              <button className="px-3 py-1 font-label-md text-label-md hover:text-on-surface transition-all" type="button">1Y</button>
            </div>
          </div>
          <div className="relative w-full aspect-[21/9] min-h-[260px] max-h-[340px] flex items-center justify-center">
            <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 760 260">
              <defs>
                <linearGradient id="spendingGradient" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#00685f" stopOpacity="0.28" />
                  <stop offset="50%" stopColor="#00685f" stopOpacity="0.08" />
                  <stop offset="100%" stopColor="#00685f" stopOpacity="0.00" />
                </linearGradient>
                <filter id="shadowPoint" x="-30%" y="-30%" width="160%" height="160%">
                  <feDropShadow dx="0" dy="2" floodColor="#00201d" floodOpacity="0.25" stdDeviation="3" />
                </filter>
              </defs>
              <line stroke="#bcc9c6" strokeDasharray="3 3" strokeOpacity="0.3" x1="40" x2="740" y1="20" y2="20" />
              <text fill="#6d7a77" fontFamily="Geist" fontSize="10" textAnchor="end" x="32" y="24">2.0M</text>
              <line stroke="#bcc9c6" strokeDasharray="3 3" strokeOpacity="0.3" x1="40" x2="740" y1="75" y2="75" />
              <text fill="#6d7a77" fontFamily="Geist" fontSize="10" textAnchor="end" x="32" y="79">1.6M</text>
              <line stroke="#bcc9c6" strokeDasharray="3 3" strokeOpacity="0.3" x1="40" x2="740" y1="130" y2="130" />
              <text fill="#6d7a77" fontFamily="Geist" fontSize="10" textAnchor="end" x="32" y="134">1.2M</text>
              <line stroke="#bcc9c6" strokeDasharray="3 3" strokeOpacity="0.3" x1="40" x2="740" y1="185" y2="185" />
              <text fill="#6d7a77" fontFamily="Geist" fontSize="10" textAnchor="end" x="32" y="189">0.8M</text>
              <path d="M 60,130 C 120,118 140,105 200,102 C 260,99 280,112 340,109 C 400,106 420,76 480,72 C 540,68 560,63 620,60 C 660,58 680,45 720,42 L 720,220 L 60,220 Z" fill="url(#spendingGradient)" />
              <path d="M 60,130 C 120,118 140,105 200,102 C 260,99 280,112 340,109 C 400,106 420,76 480,72 C 540,68 560,63 620,60 C 660,58 680,45 720,42" fill="none" stroke="#00685f" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
              <circle cx="60" cy="130" fill="#faf8ff" r="4.5" stroke="#00685f" strokeWidth="2.5" />
              <circle cx="200" cy="102" fill="#faf8ff" r="4.5" stroke="#00685f" strokeWidth="2.5" />
              <circle cx="340" cy="109" fill="#faf8ff" r="4.5" stroke="#00685f" strokeWidth="2.5" />
              <circle cx="480" cy="72" fill="#faf8ff" r="4.5" stroke="#00685f" strokeWidth="2.5" />
              <circle cx="620" cy="60" fill="#faf8ff" r="4.5" stroke="#00685f" strokeWidth="2.5" />
              <circle cx="720" cy="42" fill="#00685f" filter="url(#shadowPoint)" r="6" stroke="#89f5e7" strokeWidth="3" />
              <line stroke="#00685f" strokeDasharray="2 2" strokeOpacity="0.6" strokeWidth="1.5" x1="720" x2="720" y1="48" y2="220" />
              <text fill="#6d7a77" fontFamily="Geist" fontSize="11" fontWeight="500" textAnchor="middle" x="60" y="240">May 2024</text>
              <text fill="#6d7a77" fontFamily="Geist" fontSize="11" fontWeight="500" textAnchor="middle" x="200" y="240">Jun 2024</text>
              <text fill="#6d7a77" fontFamily="Geist" fontSize="11" fontWeight="500" textAnchor="middle" x="340" y="240">Jul 2024</text>
              <text fill="#6d7a77" fontFamily="Geist" fontSize="11" fontWeight="500" textAnchor="middle" x="480" y="240">Aug 2024</text>
              <text fill="#6d7a77" fontFamily="Geist" fontSize="11" fontWeight="500" textAnchor="middle" x="620" y="240">Sep 2024</text>
              <text fill="#00685f" fontFamily="Geist" fontSize="11" fontWeight="700" textAnchor="middle" x="720" y="240">Oct 2024</text>
            </svg>
            <div className="absolute top-2 right-4 sm:right-8 bg-surface-container-lowest text-on-surface rounded-lg p-2.5 shadow-md pointer-events-none transform -translate-y-2 flex flex-col gap-0.5">
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-primary"></span><span className="font-label-sm text-label-sm font-semibold text-primary">October Peak</span></div>
              <span className="font-headline-sm text-headline-sm font-bold text-on-surface">ETB 1,842,500</span>
              <span className="font-label-sm text-label-sm text-tertiary font-semibold flex items-center"><span className="material-symbols-outlined text-[13px]">arrow_upward</span> +7.6% MoM velocity</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-space-md pt-space-md mt-space-md bg-surface-container-low/40 rounded-lg p-space-md">
            <div className="flex items-center gap-space-md">
              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-primary"></span><span className="font-body-sm text-body-sm text-on-surface-variant">Approved Pharmacy Direct Payouts</span></div>
              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-tertiary"></span><span className="font-body-sm text-body-sm text-on-surface-variant">Employee Out-of-Pocket Reimbursements</span></div>
            </div>
            <span className="font-body-sm text-body-sm text-outline">Projections forecast ETB 1.95M for November</span>
          </div>
        </div>
        {/* Right Column */}
        <div className="lg:col-span-4 flex flex-col gap-space-lg">
          {/* Claims by Status */}
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between flex-1">
            <div className="flex items-center justify-between mb-space-md">
              <div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">Claims by Status</h3>
                <span className="font-body-sm text-body-sm text-outline">Current cycle (Oct 1 – Oct 31)</span>
              </div>
              <span className="font-label-sm text-label-sm bg-surface-container-high px-2 py-1 rounded text-on-surface font-semibold">October</span>
            </div>
            <div className="flex flex-col sm:flex-row lg:flex-col items-center justify-center gap-space-lg my-2">
              <div className="relative w-36 h-36 shrink-0 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#eaedff" strokeWidth="12" />
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#00685f" strokeDasharray="162.35 238.76" strokeDashoffset="0" strokeWidth="12" />
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#00855b" strokeDasharray="35.81 238.76" strokeDashoffset="-162.35" strokeWidth="12" />
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#b45309" strokeDasharray="31.03 238.76" strokeDashoffset="-198.16" strokeWidth="12" />
                  <circle cx="50" cy="50" fill="none" r="38" stroke="#ba1a1a" strokeDasharray="9.55 238.76" strokeDashoffset="-229.19" strokeWidth="12" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="font-headline-lg text-headline-lg font-bold text-on-surface leading-none">148</span>
                  <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">Claims</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-space-md gap-y-space-sm w-full">
                <div className="flex items-center justify-between p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-primary shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Approved</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">101 <span className="text-outline font-normal">(68%)</span></span>
                </div>
                <div className="flex items-center justify-between p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-tertiary-container shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Paid</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">22 <span className="text-outline font-normal">(15%)</span></span>
                </div>
                <div className="flex items-center justify-between p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-600 shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Pending</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">19 <span className="text-outline font-normal">(13%)</span></span>
                </div>
                <div className="flex items-center justify-between p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-error shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Rejected</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">6 <span className="text-outline font-normal">(4%)</span></span>
                </div>
              </div>
            </div>
          </div>

          {/* Benefit Unlimited */}
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between">
            <div className="absolute -right-8 -bottom-8 w-32 h-32 bg-primary/5 rounded-full pointer-events-none"></div>
            <div className="flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-primary-fixed/40 text-on-primary-fixed-variant font-label-sm text-label-sm font-semibold"><span className="material-symbols-outlined text-[16px] text-primary">all_inclusive</span> Tier-1 Corporate Health Plan</span>
                <span className="material-symbols-outlined text-primary text-[20px]">shield</span>
              </div>
              <h4 className="font-headline-sm text-headline-sm text-on-surface font-semibold pt-1">Medication Benefit: Unlimited</h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">Your organisation provides 100% prescription medication coverage with zero annual or lifetime ceilings for enrolled employees and registered dependents.</p>
            </div>
            <div className="pt-space-md mt-space-md">
              <a className="inline-flex items-center gap-1 font-label-md text-label-md text-primary font-semibold hover:gap-2 transition-all" href="#">View plan policy &amp; formulary rules <span className="material-symbols-outlined text-[16px]">arrow_forward</span></a>
            </div>
          </div>
        </div>
      </div>
      {/* Coverage & Identity Bridge (Phase 0) */}
      <div className="mb-space-xl">
        <div className="flex items-center justify-between mb-space-md">
          <h2 className="font-headline-md text-headline-md text-on-surface font-semibold tracking-tight">Coverage &amp; Identity Bridge (Phase 0)</h2>
          <span className="font-label-sm text-label-sm text-on-surface-variant">dedan_id identity bridge • CBHI/SHI/medhinLink • pending verification</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg">
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Employees linked to DEDAN card</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">231<span className="font-label-md text-label-md text-on-surface-variant ml-2">/ 248</span></div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">dedan_id (DE######) matched via phone</span>
          </div>
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">CBHI / SHI enrolment</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">42</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">insurer share applied to claims</span>
          </div>
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">medhinLink enrolment</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">18</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">payout product • patient pays cash first</span>
          </div>
          <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Pending verification</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">7</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">self-declared • awaiting EHIS confirmation</span>
          </div>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-md">Coverage check: org_share = total − insurer_share − copay, never exceeding the annual cap. EHIS has no public API — treat self-declared schemes as pending until government partnership.</p>
      </div>

      {/* Bottom Section: Recent Claims Table */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="p-space-lg flex flex-col md:flex-row md:items-center justify-between gap-space-md bg-surface-container-lowest">
          <div className="flex items-center gap-space-md">
            <div>
              <div className="flex items-center gap-space-sm">
                <h2 className="font-headline-md text-headline-md text-on-surface font-semibold tracking-tight">Recent Claims</h2>
                <span className="px-2.5 py-0.5 rounded-full bg-surface-container-high font-label-sm text-label-sm font-semibold text-on-surface">148 total</span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant">Validated clinical pharmacy receipts submitted within the current settlement batch</p>
            </div>
          </div>
          <div className="flex items-center gap-space-sm">
            <div className="relative">
              <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-outline text-[18px]">filter_list</span>
              <select className="h-9 pl-8 pr-8 bg-surface-container-low text-on-surface rounded-lg font-label-sm text-label-sm appearance-none focus:outline-none focus:bg-surface-container-high cursor-pointer transition-colors">
                <option>All Statuses</option><option>Pending Review</option><option>Approved</option><option>Paid</option><option>Rejected</option>
              </select>
              <span className="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-outline text-[16px] pointer-events-none">expand_more</span>
            </div>
            <a className="inline-flex items-center gap-1.5 px-3 py-2 bg-surface-container-low hover:bg-surface-container-high text-primary font-label-md text-label-md font-semibold rounded-lg transition-all" href="#">View All Claims <span className="material-symbols-outlined text-[16px]">arrow_forward</span></a>
          </div>
        </div>
        <div className="w-full overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-low/80 text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-lg">Employee</th>
                <th className="py-3 px-space-md">Department</th>
                <th className="py-3 px-space-md">Pharmacy / Hospital</th>
                <th className="py-3 px-space-md">Date</th>
                <th className="py-3 px-space-md text-right">Amount (ETB)</th>
                <th className="py-3 px-space-md text-center">Status</th>
                <th className="py-3 px-space-lg text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <img className="w-9 h-9 rounded-full object-cover shrink-0" alt="Portrait of Dawit Bekele" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCLgxsAzfKsVqhwLJ1dnjgjrNGlvMte4ShpKmm24xK03Lpnkic_tyKZR3vaURnpjaZAg7Xq0_NYCh2SttUgnMyHvh3IHYLOmC8zeALy9CzcaGLlvjguWGONJs6OG3-YyIAOrJr0v239wTbr_8EKL_u-rwmUdD41T8GNZqNSrQMk_To5JCeP8puAAkVlMLmNpqICSz8OwwhtHymvl-9BL0FEAHjx-mCc3v54Tv18qXuJdW9Aozb-h31f" />
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Dawit Bekele</span><span className="font-body-sm text-body-sm text-outline truncate">dawit.b@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">Tech / Engineering</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span><span className="font-body-md text-body-md text-on-surface">Lion Pharmacy Bole</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 24, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 4,850.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-tertiary-fixed/40 text-on-tertiary-fixed-variant font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span> Approved</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>

              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <img className="w-9 h-9 rounded-full object-cover shrink-0" alt="Portrait of Bethlehem Haile" src="https://lh3.googleusercontent.com/aida-public/AB6AXuAgTwvwAVsdWSL88mhdb3_7isiMEFb_6FI_de6de9U8s2XTweZiYwZL81ROb3QLPpjCiGAqjO0W-xIcoeFw3YR3uetwEEq-Rm2Wto1nbnqamFTTMnStmKKUGwMDIp724VcHpcqJNjZMTAxcFmPVLgzgaKaz0xe7Pfm88BLf-_uJHmQPWWBiTbSjI5ud-NOpdJHF_dzD5KSZ57OwtT5Opl7DnWJ8gwnjYPagVgJx17DuQ-dA4MdC2rzk" />
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Bethlehem Haile</span><span className="font-body-sm text-body-sm text-outline truncate">b.haile@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">Finance &amp; Audit</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span><span className="font-body-md text-body-md text-on-surface">Kenema Pharmacy Piassa</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 23, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 2,120.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-amber-100 text-amber-900 font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-amber-600"></span> Pending Review</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>
              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <img className="w-9 h-9 rounded-full object-cover shrink-0" alt="Portrait of Yohannes Mengistu" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCk7zwTkpTd0bNcWnqD7bRJKQ-qsJd86wXSjET_VE659SBizF8pkiexr2WAUed5c-ATRCC3Yol6hUbg2XtMUFvGQOxgI5ogey2RauWo8uxNP7nBo02GolhT8FAPKhgFLJLeMzjBFkXBuNXHjhgEB387B_PKJu8MLfGiX7xgQNTdprUWhwjO37r8pc-RY37tKUitmOeFd9zAjR4d5PNXIC2YHD3O7dozFwNvdbbjCflLq3t6bOnWPpC_" />
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Yohannes Mengistu</span><span className="font-body-sm text-body-sm text-outline truncate">yohannes.m@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">Operations</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_hospital</span><span className="font-body-md text-body-md text-on-surface">Kadisco General Hospital</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 22, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 8,940.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-tertiary-container/20 text-tertiary font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span> Paid</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>

              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <div className="w-9 h-9 rounded-full bg-primary-fixed/60 text-on-primary-fixed font-label-md text-label-md flex items-center justify-center font-bold shrink-0">TA</div>
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Tsion Alemu</span><span className="font-body-sm text-body-sm text-outline truncate">tsion.a@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">People &amp; Culture</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_hospital</span><span className="font-body-md text-body-md text-on-surface">St. Yared Clinical Center</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 21, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 1,450.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-tertiary-fixed/40 text-on-tertiary-fixed-variant font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span> Approved</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>
              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <img className="w-9 h-9 rounded-full object-cover shrink-0" alt="Portrait of Henok Tsegaye" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDGfOROv6Mw_ffVnwCKsEFYdT-E-TOPg3xW8WdoWsQYR2-P1uk5B7OolSXCjG4in89F5ME_-3mUbjdk5GWsGx_WmA9zb-ZqLTM0eor8gvzXGWs6phDnEpwJ-fnzIXHrKVRqlyJ9Ao_SmRBUeLPh-iMHz3fl2yghCabqdVZpit6iv6aCAQuSRFJI5Fa8q8C0F4jfcm8jnd9NNJiDAy0yCktVH0SFinoM4c1SGMMZKeCYbWBEkiJbnMGj" />
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Henok Tsegaye</span><span className="font-body-sm text-body-sm text-outline truncate">henok.t@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">Tech / Product</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span><span className="font-body-md text-body-md text-on-surface">Lion Pharmacy Bole</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 20, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 3,600.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-error-container text-on-error-container font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-error"></span> Rejected</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>

              <tr className="hover:bg-surface-container-low/50 transition-colors">
                <td className="py-3.5 px-space-lg">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <div className="w-9 h-9 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-md text-label-md flex items-center justify-center font-bold shrink-0">MG</div>
                    <div className="flex flex-col min-w-0"><span className="font-headline-sm text-headline-sm text-on-surface font-semibold truncate">Meron Gebremariam</span><span className="font-body-sm text-body-sm text-outline truncate">meron.g@ethiocorp.et</span></div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md"><span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container font-label-sm text-label-sm text-on-surface">Executive Office</span></td>
                <td className="py-3.5 px-space-md"><div className="flex items-center gap-1.5"><span className="material-symbols-outlined text-[16px] text-primary">local_hospital</span><span className="font-body-md text-body-md text-on-surface">Kadisco General Hospital</span></div></td>
                <td className="py-3.5 px-space-md font-body-sm text-body-sm text-on-surface-variant">Oct 19, 2024</td>
                <td className="py-3.5 px-space-md text-right font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 5,230.00</td>
                <td className="py-3.5 px-space-md text-center"><span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-label-sm text-label-sm bg-tertiary-container/20 text-tertiary font-semibold"><span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span> Paid</span></td>
                <td className="py-3.5 px-space-lg text-right"><button className="px-3 py-1 bg-surface-container-low hover:bg-surface-container text-on-surface rounded-md font-label-sm text-label-sm font-semibold transition-all" type="button">View</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="p-space-md bg-surface-container-low/50 flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm text-outline">
          <div className="flex items-center gap-2"><span className="material-symbols-outlined text-[18px] text-primary">sync</span><span className="font-body-sm text-body-sm text-on-surface-variant">Automated batch disbursement triggers daily at 17:00 EAT via CBE Gateway.</span></div>
          <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">Showing 6 of 148 submitted claims</span>
        </div>
      </div>
    </div>
  );
}
