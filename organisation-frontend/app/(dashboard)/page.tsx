export default function OverviewPage() {
  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Action & Context Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-lg pt-space-lg mb-space-xl">
        <div className="flex flex-col gap-space-xs max-w-2xl">
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight">
            Medication Benefit Overview
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            Real-time overview of employee prescription medication reimbursements, claims
            processing, and disbursements.
          </p>
        </div>
      </div>

      {/* 4 KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        {/* Spend Card */}
        <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between relative overflow-hidden group hover: transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Total Medication Spend</span>
              
            </div>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mb-1">ETB 1,842,500</div>
          </div>
        </div>

        {/* Claims Submitted Card */}
        <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between relative overflow-hidden group hover: transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Claims Submitted</span>
              
            </div>
            <div className="flex items-baseline gap-space-sm mb-1">
              <span className="font-display-lg text-display-lg text-on-surface tracking-tight">148</span>
            </div>
          </div>
        </div>
        {/* Pending Approval Card */}
        <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between relative overflow-hidden group hover: transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Pending Approval</span>
              
            </div>
            <div className="flex items-baseline gap-space-sm mb-1">
              <span className="font-display-lg text-display-lg text-on-surface tracking-tight">19</span>
            </div>
          </div>
        </div>

        {/* Total Reimbursed YTD */}
        <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between relative overflow-hidden group hover: transition-all">
          <div>
            <div className="flex items-center justify-between mb-space-sm">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Total Reimbursed YTD</span>
              
            </div>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mb-1">ETB 14,280,000</div>
          </div>
        </div>
      </div>
      {/* Two-Column Middle Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg mb-space-xl">
        {/* Right Column */}
        <div className="lg:col-span-12 flex flex-col gap-space-lg">
          {/* Claims by Status */}
          <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between flex-1">
            <div className="flex items-center justify-between mb-space-md">
              <div>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">Claims by Status</h3>
                <span className="font-body-sm text-body-sm text-outline">Current cycle (Oct 1 – Oct 31)</span>
              </div>
              <span className="font-label-sm text-label-sm bg-surface-container-high px-2 py-1 rounded text-on-surface font-semibold">October</span>
            </div>
            <div className="flex flex-col items-center justify-center gap-space-md my-2">
              <div className="relative w-44 h-44 shrink-0 flex items-center justify-center">
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
              <div className="grid grid-cols-2 gap-x-space-md gap-y-space-sm w-fit">
                <div className="flex items-center justify-center gap-2 p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-primary shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Approved</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">101 <span className="text-outline font-normal">(68%)</span></span>
                </div>
                <div className="flex items-center justify-center gap-2 p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-tertiary-container shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Paid</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">22 <span className="text-outline font-normal">(15%)</span></span>
                </div>
                <div className="flex items-center justify-center gap-2 p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-600 shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Pending</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">19 <span className="text-outline font-normal">(13%)</span></span>
                </div>
                <div className="flex items-center justify-center gap-2 p-1.5 rounded-lg bg-surface-container-low/50">
                  <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-error shrink-0"></span><span className="font-label-sm text-label-sm text-on-surface-variant">Rejected</span></div>
                  <span className="font-label-md text-label-md font-semibold text-on-surface">6 <span className="text-outline font-normal">(4%)</span></span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
      {/* Coverage & Identity Bridge (Phase 0) */}
      <div className="mb-space-xl">
        <div className="flex items-center justify-between mb-space-md">
          <h2 className="font-headline-md text-headline-md text-on-surface font-semibold tracking-tight">Coverage &amp; Identity Bridge (Phase 0)</h2>
          <span className="font-label-sm text-label-sm text-on-surface-variant">endod_id identity bridge • CBHI/SHI • pending verification</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg">
          <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Employees linked to ENDOD card</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">231<span className="font-label-md text-label-md text-on-surface-variant ml-2">/ 248</span></div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">endod_id (DE######) matched via phone</span>
          </div>
          <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">CBHI / SHI enrolment</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">42</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">insurer share applied to claims</span>
          </div>
          <div className="bg-surface-container-low p-space-lg rounded-xl  flex flex-col justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">Pending verification</span>
            <div className="font-display-lg text-display-lg text-on-surface tracking-tight mt-2">7</div>
            <span className="font-body-sm text-body-sm text-on-surface-variant mt-2">self-declared • awaiting EHIS confirmation</span>
          </div>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-md">Coverage check: org_share = total − insurer_share − copay, never exceeding the annual cap. EHIS has no public API — treat self-declared schemes as pending until government partnership.</p>
      </div>
    </div>
  );
}
