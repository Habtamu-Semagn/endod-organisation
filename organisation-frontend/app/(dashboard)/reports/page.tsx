export default function ReportsPage() {
  return (
    <div className="flex flex-col w-full pb-16">
      {/* Top View Heading & Global Export Controls */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-lg mb-space-xl">
        <div className="flex flex-col gap-1 max-w-2xl">
          <div className="flex items-center gap-space-sm mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-secondary-container/50 text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
              Fiscal Cycle FY 2024 • Q4
            </span>
            <span className="text-outline text-label-sm font-label-sm">•</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">Addis Ababa Central Region</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">Benefit Reports &amp; Analytics</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Analyze employee medication utilization, pharmacy expenditure trends, and export financial audit statements.
          </p>
        </div>
        <div className="flex items-center gap-space-md self-start lg:self-auto shrink-0">
          <button className="group inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high transition-all  font-label-lg text-label-lg" type="button">
            <span className="material-symbols-outlined text-[18px] text-outline group-hover:text-on-surface transition-colors">description</span>
            <span>Download PDF Statement</span>
          </button>
          <button className="inline-flex items-center gap-2 h-10 px-5 rounded-lg bg-primary text-on-primary hover:bg-primary-container transition-all  font-label-lg text-label-lg " type="button">
            <span className="material-symbols-outlined text-[18px]">table_view</span>
            <span>Download Excel / CSV</span>
          </button>
        </div>
      </div>
      {/* Summary KPI Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-space-lg mb-space-xl">
        <div className="p-space-lg rounded-xl bg-surface-container-lowest  flex flex-col justify-between hover: transition-shadow">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Total Medication Spend</span>
              <div className="flex items-baseline gap-1.5 mt-2">
                <span className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">ETB 1,842,500</span>
                <span className="font-label-md text-label-md text-on-surface-variant">.00</span>
              </div>
            </div>
          </div>
        </div>
        <div className="p-space-lg rounded-xl bg-surface-container-lowest  flex flex-col justify-between hover: transition-shadow">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Total Claims Processed</span>
              <div className="flex items-baseline gap-1.5 mt-2">
                <span className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">148</span>
                <span className="font-label-md text-label-md text-on-surface-variant">Claims</span>
              </div>
            </div>
          </div>
        </div>
        <div className="p-space-lg rounded-xl bg-surface-container-lowest  flex flex-col justify-between hover: transition-shadow">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Average Claim Value</span>
              <div className="flex items-baseline gap-1.5 mt-2">
                <span className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">ETB 12,449</span>
                <span className="font-label-md text-label-md text-on-surface-variant">.32</span>
              </div>
            </div>
          </div>
        </div>
        <div className="p-space-lg rounded-xl bg-surface-container-lowest  flex flex-col justify-between hover: transition-shadow">
          <div className="flex items-start justify-between">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Employees Supported</span>
              <div className="flex items-baseline gap-1.5 mt-2">
                <span className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">184</span>
                <span className="font-label-md text-label-md text-on-surface-variant">Beneficiaries</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Analytics Visualization Grid (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-space-lg mb-space-xl">
        <div className="p-space-xl rounded-xl bg-surface-container-lowest  flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-space-sm">
                <span className="material-symbols-outlined text-primary text-[20px]">domain</span>
                <h2 className="font-headline-sm text-headline-sm text-on-surface">Medication Spend by Department</h2>
              </div>
              <span className="font-label-sm text-label-sm text-outline uppercase tracking-wider">5 Functional Divisions</span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-lg">
              Disbursement volume correlated with headcounts and average maintenance therapy utilization.
            </p>
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between font-label-md text-label-md">
                  <span className="text-on-surface font-semibold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm bg-primary"></span>
                    Engineering &amp; Technology
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-on-surface font-numeric-currency font-semibold">ETB 642,800.00</span>
                    <span className="text-outline text-label-sm font-label-sm">(34.9%)</span>
                  </div>
                </div>
                <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: "34.9%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>Avg. per employee: ETB 10,367.74</span>
                  <span>62 Beneficiaries</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between font-label-md text-label-md">
                  <span className="text-on-surface font-semibold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm bg-on-surface-variant"></span>
                    Operations &amp; Fleet
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-on-surface font-numeric-currency font-semibold">ETB 418,200.00</span>
                    <span className="text-outline text-label-sm font-label-sm">(22.7%)</span>
                  </div>
                </div>
                <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-on-surface-variant rounded-full transition-all duration-500" style={{ width: "22.7%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>Avg. per employee: ETB 8,534.69</span>
                  <span>49 Beneficiaries</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between font-label-md text-label-md">
                  <span className="text-on-surface font-semibold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm bg-primary-container"></span>
                    Sales &amp; Commercial
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-on-surface font-numeric-currency font-semibold">ETB 354,100.00</span>
                    <span className="text-outline text-label-sm font-label-sm">(19.2%)</span>
                  </div>
                </div>
                <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary-container rounded-full transition-all duration-500" style={{ width: "19.2%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>Avg. per employee: ETB 9,318.42</span>
                  <span>38 Beneficiaries</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between font-label-md text-label-md">
                  <span className="text-on-surface font-semibold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm bg-tertiary"></span>
                    People &amp; Culture
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-on-surface font-numeric-currency font-semibold">ETB 246,900.00</span>
                    <span className="text-outline text-label-sm font-label-sm">(13.4%)</span>
                  </div>
                </div>
                <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-tertiary rounded-full transition-all duration-500" style={{ width: "13.4%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>Avg. per employee: ETB 12,994.73</span>
                  <span>19 Beneficiaries</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between font-label-md text-label-md">
                  <span className="text-on-surface font-semibold flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm bg-secondary-fixed-dim"></span>
                    Finance &amp; Executive
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-on-surface font-numeric-currency font-semibold">ETB 180,500.00</span>
                    <span className="text-outline text-label-sm font-label-sm">(9.8%)</span>
                  </div>
                </div>
                <div className="w-full h-2.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-secondary-fixed-dim rounded-full transition-all duration-500" style={{ width: "9.8%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>Avg. per employee: ETB 11,281.25</span>
                  <span>16 Beneficiaries</span>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-space-lg pt-space-md flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm">
            <span>Highest per capita: People &amp; Culture (Chronic Care enrollment)</span>
            <a className="text-primary hover:underline font-semibold flex items-center gap-1" href="#">
              Full breakdown <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            </a>
          </div>
        </div>
        <div className="p-space-xl rounded-xl bg-surface-container-lowest  flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-space-sm">
                <span className="material-symbols-outlined text-secondary text-[20px]">local_pharmacy</span>
                <h2 className="font-headline-sm text-headline-sm text-on-surface">Medication Spend by Pharmacy Network</h2>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-tertiary-container/10 text-tertiary font-label-sm text-[10px] font-bold uppercase">Direct Cashless</span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-lg">
              Disbursements across direct billing clinics vs out-of-network claims in Addis Ababa.
            </p>
            <div className="flex flex-col gap-4">
              <div className="p-3 rounded-lg bg-surface flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[18px]">verified</span>
                    <span className="font-label-md text-label-md text-on-surface font-semibold">Kenema Pharmacy Network (Tier-1 Direct)</span>
                  </div>
                  <span className="font-numeric-currency text-label-lg font-bold text-on-surface">ETB 785,400.00</span>
                </div>
                <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: "42.6%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>68 direct cashless claims processed</span>
                  <span className="font-semibold text-primary">42.6% of total spend</span>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-surface flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[18px]">verified</span>
                    <span className="font-label-md text-label-md text-on-surface font-semibold">Lion Pharmacy (Kazanchis &amp; Bole)</span>
                  </div>
                  <span className="font-numeric-currency text-label-lg font-bold text-on-surface">ETB 462,100.00</span>
                </div>
                <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                  <div className="h-full bg-primary-container rounded-full" style={{ width: "25.1%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>41 direct verified invoices</span>
                  <span className="font-semibold text-primary-container">25.1% of total spend</span>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-surface flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-outline text-[18px]">domain</span>
                    <span className="font-label-md text-label-md text-on-surface font-semibold">Kadisco General Hospital Pharmacy</span>
                  </div>
                  <span className="font-numeric-currency text-label-lg font-bold text-on-surface">ETB 328,000.00</span>
                </div>
                <div className="w-full h-2 bg-surface-container-high rounded-full overflow-hidden">
                  <div className="h-full bg-secondary rounded-full" style={{ width: "17.8%" }}></div>
                </div>
                <div className="flex justify-between items-center text-on-surface-variant font-label-sm text-[11px]">
                  <span>22 claims (Specialized oncology &amp; endocrine)</span>
                  <span className="font-semibold text-secondary">17.8% of total spend</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-2.5 rounded-lg bg-surface">
                  <div className="font-label-sm text-label-sm text-on-surface font-semibold truncate">St. Gabriel &amp; Red Cross</div>
                  <div className="font-numeric-currency text-label-md font-bold text-on-surface mt-0.5">ETB 162,000.00</div>
                  <div className="font-label-sm text-[10px] text-on-surface-variant mt-0.5">11 claims (8.8%)</div>
                </div>
                <div className="p-2.5 rounded-lg bg-surface">
                  <div className="font-label-sm text-label-sm text-on-surface font-semibold truncate">Other Licensed Dispensaries</div>
                  <div className="font-numeric-currency text-label-md font-bold text-on-surface mt-0.5">ETB 105,000.00</div>
                  <div className="font-label-sm text-[10px] text-on-surface-variant mt-0.5">6 claims (5.7%)</div>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-space-lg p-3 rounded-lg bg-secondary-container/30 flex items-center gap-space-sm text-on-secondary-container font-label-sm text-label-sm">
            <span className="material-symbols-outlined text-[18px] text-primary shrink-0">savings</span>
            <span>
              <strong>Direct Settlement Efficiency:</strong> Tier-1 cashless direct billing saved an estimated <strong>ETB 42,000</strong> in manual reimbursement processing overhead.
            </span>
          </div>
        </div>
      </div>
      {/* Employee Utilization Ledger Card & Data Table */}
      <div className="rounded-xl bg-surface-container-lowest  mb-space-xl overflow-hidden">
        <div className="p-space-lg flex flex-col md:flex-row md:items-center justify-between gap-space-md">
          <div className="flex flex-col">
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Employee Utilization Ledger (October 2024)</h2>
            <span className="font-body-sm text-body-sm text-on-surface-variant">Real-time prescription claims authenticated via Endod Health smart card tokens</span>
          </div>
          <div className="flex items-center gap-space-sm w-full md:w-auto">
            <div className="relative flex-1 md:w-72">
              <span className="material-symbols-outlined absolute left-3 top-2.5 text-outline text-[18px]">search</span>
              <input className="w-full h-9 pl-9 pr-3 rounded-lg bg-surface font-body-sm text-body-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary " placeholder="Filter by employee name, ID..." type="text" />
            </div>
            <button className="h-9 px-3 rounded-lg bg-surface text-on-surface-variant hover:bg-surface-container-high transition-colors font-label-sm text-label-sm flex items-center gap-1.5 shrink-0">
              <span className="material-symbols-outlined text-[16px]">tune</span>
              <span>Filters</span>
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-body-md text-body-md border-collapse">
            <thead>
              <tr className="bg-surface text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-md font-semibold">Employee Name &amp; ID</th>
                <th className="py-3 px-space-md font-semibold">Department</th>
                <th className="py-3 px-space-md font-semibold">Primary Pharmacy</th>
                <th className="py-3 px-space-md font-semibold text-center">Claims</th>
                <th className="py-3 px-space-md font-semibold">Prescription Category</th>
                <th className="py-3 px-space-md font-semibold text-right">Total Benefit Paid</th>
                <th className="py-3 px-space-md font-semibold">Utilization Status</th>
                <th className="py-3 px-space-md font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container">
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-label-sm">BH</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Bethlehem Haile</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0381 • Sr. HR Specialist</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">People &amp; Culture</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span>
                    <span className="text-body-sm font-body-sm">Lion Pharmacy Kazanchis</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">5</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Chronic / Maintenance</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 14,350.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-tertiary-container/10 text-tertiary font-label-sm text-[11px] font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-tertiary"></span>
                    Chronic Care Plan
                  </span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-secondary/10 text-secondary flex items-center justify-center font-bold text-label-sm">DB</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Dawit Bekele</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0492 • Principal Architect</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">Engineering &amp; Tech</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span>
                    <span className="text-body-sm font-body-sm">Kenema Pharmacy Bole</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">4</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Diabetes Care (Insulin Glargine)</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 13,800.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-700 font-label-sm text-[11px] font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600"></span>
                    High Utilization
                  </span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary-fixed/40 text-on-primary-fixed flex items-center justify-center font-bold text-label-sm">YM</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Yohannes Mengistu</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0214 • Core Network Lead</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">Infrastructure</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span>
                    <span className="text-body-sm font-body-sm">Lion Pharmacy Bole</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">3</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Cardiovascular (Antihypertensive)</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 11,250.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-[11px] font-semibold">Normal</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-surface-container-high text-on-surface flex items-center justify-center font-bold text-label-sm">NG</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Natnael Girma</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0552 • Solutions Architect</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">Telecom Solutions</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-outline">domain</span>
                    <span className="text-body-sm font-body-sm">Hayat Hospital Pharmacy</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">3</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Post-Op &amp; Analgesics</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 9,450.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-[11px] font-semibold">Normal</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center font-bold text-label-sm">MA</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Meron Assefa</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0108 • Key Account Manager</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">Sales &amp; Partnerships</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-primary">local_pharmacy</span>
                    <span className="text-body-sm font-body-sm">Kenema Pharmacy #4 (Piazza)</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">2</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Maternal Care / Vitamins</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 6,800.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-[11px] font-semibold">Normal</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
              <tr className="hover:bg-surface/60 transition-colors group">
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-tertiary/10 text-tertiary flex items-center justify-center font-bold text-label-sm">TA</div>
                    <div className="flex flex-col">
                      <span className="font-label-md text-label-md font-semibold text-on-surface group-hover:text-primary transition-colors">Tsion Alemu</span>
                      <span className="font-label-sm text-[11px] text-outline">ET-0671 • Growth Strategist</span>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium">Marketing &amp; Growth</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <div className="flex items-center gap-1.5 text-on-surface">
                    <span className="material-symbols-outlined text-[16px] text-outline">domain</span>
                    <span className="text-body-sm font-body-sm">St. Gabriel Hospital</span>
                  </div>
                </td>
                <td className="py-3.5 px-space-md text-center">
                  <span className="font-numeric-currency text-body-md font-semibold text-on-surface">2</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="text-body-sm font-body-sm text-on-surface-variant font-medium">Endocrine / Thyroid Care</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <span className="font-numeric-currency text-body-md font-bold text-on-surface">ETB 5,200.00</span>
                </td>
                <td className="py-3.5 px-space-md">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-[11px] font-semibold">Normal</span>
                </td>
                <td className="py-3.5 px-space-md text-right">
                  <button className="inline-flex items-center gap-1 text-primary hover:text-primary-container font-label-sm text-label-sm font-semibold transition-colors">
                    <span>Statement</span>
                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="p-space-md bg-surface flex flex-col sm:flex-row items-center justify-between gap-space-sm">
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            Showing <strong>6</strong> of <strong>184</strong> active employee beneficiaries
          </span>
          <div className="flex items-center gap-space-md">
            <button className="font-label-sm text-label-sm font-semibold text-primary hover:underline flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px]">download</span>
              Export Filtered Table
            </button>
            <div className="flex items-center gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded bg-surface-container-high text-on-surface-variant disabled:opacity-50" disabled>
                <span className="material-symbols-outlined text-[18px]">chevron_left</span>
              </button>
              <span className="px-2 font-label-sm text-label-sm font-bold text-on-surface">1</span>
              <button className="w-8 h-8 flex items-center justify-center rounded bg-surface-container-high text-on-surface hover:bg-surface-container-highest transition-colors">
                <span className="material-symbols-outlined text-[18px]">chevron_right</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      {/* Bottom Regulatory & EFDA Formulary Audit Banner */}
      <div className="p-space-lg rounded-xl bg-surface-container-low  flex flex-col md:flex-row items-start md:items-center justify-between gap-space-md">
        <div className="flex items-start gap-space-md">
          <div className="w-10 h-10 rounded-lg bg-tertiary-container/15 text-tertiary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[24px]">verified_user</span>
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-label-lg text-label-lg font-bold text-on-surface">Ethiopian Food and Drug Authority (EFDA) Formulary Verified</span>
              <span className="px-2 py-0.25 rounded bg-tertiary-container/20 text-tertiary font-label-sm text-[10px] font-bold">100% Compliant</span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5">
              Unlimited Prescription Benefit Compliance Note: All 148 submitted claims have been cross-verified with the Ethiopian Food and Drug Authority (EFDA) formulary and verified against the Ethiopian National Essential Medicines List (NEML). 0 out-of-formulary exceptions recorded this cycle.
            </p>
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-2 self-end md:self-center">
          <span className="font-label-sm text-[11px] text-outline font-numeric-currency">Reg# EFDA/MED-2024-AA</span>
          <button className="px-3 py-1.5 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high transition-colors font-label-sm text-label-sm font-semibold ">
            Audit Log
          </button>
        </div>
      </div>
    </div>
  );
}
