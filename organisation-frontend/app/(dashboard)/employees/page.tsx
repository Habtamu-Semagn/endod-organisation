"use client";

import { useState } from "react";

export default function EmployeesPage() {
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [benefitEnabled, setBenefitEnabled] = useState(true);
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [utilizationFilter, setUtilizationFilter] = useState("all");
  const [addEmployeeOpen, setAddEmployeeOpen] = useState(false);
  const [addedEmployees, setAddedEmployees] = useState<
    {
      name: string;
      employeeId: string;
      department: string;
      role: string;
      email: string;
      endodId: string;
      coverage: string;
      dependents: string;
      claims: string;
      spend: string;
    }[]
  >([]);
  const [newEmployee, setNewEmployee] = useState({
    name: "",
    employeeId: "",
    department: "Engineering",
    role: "",
    email: "",
    endodId: "",
    coverage: "SHI • verified",
    dependents: "Self Only",
    claims: "0 claims",
    spend: "ETB 0.00",
  });

  return (
    <div className="flex flex-col w-full pb-space-2xl">
      {/* Top Editorial / Header Row */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-lg pt-space-lg pb-space-lg">
        <div className="flex flex-col max-w-2xl">
          <div className="flex items-center gap-space-sm mb-1.5">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-primary font-bold">Workforce Roster &amp; Actuarial Registry</span>
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">FY2024–2025</span>
          </div>
          <h1 className="font-display-lg text-display-lg text-on-surface tracking-tight font-bold">Enrolled Employees</h1>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage employee eligibility, dependent coverage, and prescription medication reimbursement limits across clinical networks.</p>
        </div>
        <div className="flex items-center gap-space-md shrink-0">
          <button className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-surface-container-lowest text-on-surface font-label-lg text-label-lg  hover:bg-surface-container-low transition-all" type="button">
            <span className="material-symbols-outlined text-[19px] text-on-surface-variant">upload_file</span>
            <span>Import Employees (CSV/HRIS)</span>
          </button>
          <button className="inline-flex items-center gap-space-sm px-4 py-2.5 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg  hover:bg-secondary transition-all" onClick={() => setAddEmployeeOpen(true)} type="button">
            <span className="material-symbols-outlined text-[20px]">person_add</span>
            <span>Add Single Employee</span>
          </button>
        </div>
      </div>

      {/* Key Metrics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-lg mb-space-xl">
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg  flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Total Enrolled</span>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg font-bold text-on-surface tracking-tight">248</span>
            <span className="font-label-md text-label-md text-on-surface-variant">Employees</span>
          </div>
          <div className="absolute -right-4 -bottom-4 w-24 h-24 rounded-full bg-primary/5 pointer-events-none" />
        </div>
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg  flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Active Benefit Users</span>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg font-bold text-on-surface tracking-tight">184</span>
            <span className="font-label-sm text-label-sm px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-bold">74% Utilization</span>
          </div>
          <div className="mt-3 w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
            <div className="bg-primary h-full rounded-full" style={{ width: "74%" }} />
          </div>
        </div>
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg  flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Dependents Covered</span>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg font-bold text-on-surface tracking-tight">412</span>
            <span className="font-label-md text-label-md text-on-surface-variant">Spouses &amp; Kids</span>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg  flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Plan Policy Model</span>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="font-display-lg text-display-lg font-bold text-tertiary tracking-tight">100%</span>
            <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">Unlimited</span>
          </div>
        </div>
      </div>

      {/* Main Work Area */}
      <div className="w-full flex flex-col gap-space-md">
        {/* Filter Strip */}
        <div className="bg-surface-container-lowest p-space-md rounded-xl  flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-space-md">
          <div className="relative flex-1 min-w-[280px]">
            <span className="material-symbols-outlined absolute left-3.5 top-2.5 text-outline text-[20px]">search</span>
            <input className="w-full h-10 pl-11 pr-4 bg-surface rounded-lg font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary " placeholder="Search by employee name, employee ID, department, email..." type="text" />
          </div>
          <div className="flex flex-wrap items-center gap-space-sm">
            <div className="relative">
              <select className="h-10 pl-3 pr-8 rounded-lg bg-surface text-on-surface font-label-md text-label-md focus:outline-none focus:ring-2 focus:ring-primary  appearance-none cursor-pointer" value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
                <option value="all">All Departments (5)</option>
                <option value="eng">Engineering (92)</option>
                <option value="sales">Sales &amp; Partnerships (64)</option>
                <option value="people">People &amp; Culture (18)</option>
                <option value="ops">Operations &amp; Fleet (52)</option>
                <option value="fin">Finance &amp; Legal (22)</option>
              </select>
              <span className="material-symbols-outlined absolute right-2.5 top-2.5 text-[18px] text-outline pointer-events-none">expand_more</span>
            </div>
            <div className="relative">
              <select className="h-10 pl-3 pr-8 rounded-lg bg-surface text-on-surface font-label-md text-label-md focus:outline-none focus:ring-2 focus:ring-primary  appearance-none cursor-pointer" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="all">Status: All (248)</option>
                <option value="active">Active (242)</option>
                <option value="leave">On Leave (4)</option>
                <option value="term">Terminated (2)</option>
              </select>
              <span className="material-symbols-outlined absolute right-2.5 top-2.5 text-[18px] text-outline pointer-events-none">expand_more</span>
            </div>
            <div className="relative">
              <select className="h-10 pl-3 pr-8 rounded-lg bg-surface text-on-surface font-label-md text-label-md focus:outline-none focus:ring-2 focus:ring-primary  appearance-none cursor-pointer" value={utilizationFilter} onChange={(e) => setUtilizationFilter(e.target.value)}>
                <option value="all">Utilization: All Users</option>
                <option value="active_claimants">Active Claimants (184)</option>
                <option value="zero_claims">Zero Claims (64)</option>
              </select>
              <span className="material-symbols-outlined absolute right-2.5 top-2.5 text-[18px] text-outline pointer-events-none">expand_more</span>
            </div>
            <button className="h-10 px-3 rounded-lg bg-surface hover:bg-surface-container-high text-on-surface-variant flex items-center gap-1  transition-all" onClick={() => { setDepartmentFilter("all"); setStatusFilter("active"); setUtilizationFilter("all"); }} title="Reset Filters" type="button">
              <span className="material-symbols-outlined text-[18px]">filter_list_off</span>
              <span className="font-label-sm text-label-sm">Reset</span>
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="w-full bg-surface-container-lowest rounded-xl  overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider select-none">
                  <th className="py-3.5 pl-6 pr-4 font-semibold">Employee</th>
                  <th className="py-3.5 px-4 font-semibold">Department &amp; Role</th>
                  <th className="py-3.5 px-4 font-semibold">Work Email</th>
                  <th className="py-3.5 px-4 font-semibold">ENDOD ID &amp; Coverage</th>
                  <th className="py-3.5 px-4 font-semibold">Dependents</th>
                  <th className="py-3.5 px-4 font-semibold text-center">Claims</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Medication Spend YTD</th>
                  <th className="py-3.5 pr-6 pl-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="font-body-md text-body-md divide-y-0">
                {/* Row 1 */}
                <tr className="bg-primary/5 hover:bg-primary/10 transition-colors cursor-pointer" onClick={() => setDrawerOpen(true)}>
                  <td className="py-3.5 pl-6 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="relative shrink-0">
                        <img className="w-10 h-10 rounded-full object-cover ring-2 ring-primary" alt="Bethlehem Haile" src="https://lh3.googleusercontent.com/aida-public/AB6AXuB-OdvV5Z1LJ5Ks1IaNDJsKxD_LkZtM81MKaL9tjLQLDr88tEcoNXbWomiUWptkQFmkjXRgddND5myHFg1INhAae35Z86oAYzAHF3VCaONPfHFaTzgC_YW0Zn7FpoiXT22hFM6EmAlbTZOJUSLU4V_-YRojhQAsIK_o6r77nKygFw3bBXzqzp8k-r1qakZQqmvsfcxECGC0CsTZyKjx6Kk4DEQXlZS_5FRtyWWJXmzgEOp77mNWOeLb" />
                        <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-headline-sm text-headline-sm font-semibold text-primary truncate">Bethlehem Haile</span>
                        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">ET-0381</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">People &amp; Culture</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Head of Talent Acquisition</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">bethlehem.h@company.et</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-label-sm text-on-surface-variant">DE-00381 (endod_id)</span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-secondary" /> CBHI • verified
                      </span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
                      <span className="material-symbols-outlined text-[15px] text-primary">diversity_1</span>
                      <span>1 Spouse, 1 Child</span>
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold ">5 claims</span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 14,350.00</span>
                  </td>
                  <td className="py-3.5 pr-6 pl-4 text-right">
                    <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold  transition-all" onClick={() => setDrawerOpen(true)} type="button">View Profile</button>
                      <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
                        <span className="material-symbols-outlined text-[19px]">more_vert</span>
                      </button>
                    </div>
                  </td>
                </tr>

                {/* Row 2 */}
                <tr className="hover:bg-surface-container-low transition-colors">
                  <td className="py-3.5 pl-6 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="relative shrink-0">
                        <img className="w-10 h-10 rounded-full object-cover" alt="Dawit Bekele" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCL0jd4AeFsiebzY4UzXzyndl3-WwHl_yX1PRZVNGTNJtAcruBsM5C9Que61vYrW7DKg-JpNmUS7CBhc25TmQUBDrz48Ftxenk-I04DZyymEt0dnZrNzo5dVpJpYfNOjja2ngcJ5g68Qx2wA2J9hS-0I6C5qoRctr3nkgQenRh75cwRfiDcpSdUDZw8wBtpYk1Mth5AIFtxhjmXcMJQJrdKkcwHwK1LEAZ6TQT1--JwX3wFu_-Q5dt2" />
                        <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">Dawit Bekele</span>
                        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">ET-0492</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">Engineering</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Senior Backend Developer</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">dawit.b@company.et</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-label-sm text-on-surface-variant">DE-00492 (endod_id)</span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-secondary" /> SHI • verified
                      </span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
                      <span className="material-symbols-outlined text-[15px] text-primary">diversity_1</span>
                      <span>1 Spouse, 2 Children</span>
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold ">6 claims</span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 24,600.00</span>
                  </td>
                  <td className="py-3.5 pr-6 pl-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold  transition-all" onClick={() => setDrawerOpen(true)} type="button">View Profile</button>
                      <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
                        <span className="material-symbols-outlined text-[19px]">more_vert</span>
                      </button>
                    </div>
                  </td>
                </tr>

                {/* Row 3 */}
                <tr className="hover:bg-surface-container-low transition-colors">
                  <td className="py-3.5 pl-6 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="relative shrink-0">
                        <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[14px]">MA</div>
                        <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">Meron Assefa</span>
                        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">ET-0118</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">Sales &amp; Partnerships</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Enterprise Account Lead</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">meron.a@company.et</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-label-sm text-on-surface-variant">DE-00512 (endod_id)</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
                      <span className="material-symbols-outlined text-[15px] text-primary">diversity_1</span>
                      <span>1 Spouse</span>
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold ">2 claims</span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 6,820.00</span>
                  </td>
                  <td className="py-3.5 pr-6 pl-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold  transition-all" type="button">View Profile</button>
                      <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
                        <span className="material-symbols-outlined text-[19px]">more_vert</span>
                      </button>
                    </div>
                  </td>
                </tr>

                {/* Row 4 */}
                <tr className="hover:bg-surface-container-low transition-colors">
                  <td className="py-3.5 pl-6 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="relative shrink-0">
                        <img className="w-10 h-10 rounded-full object-cover" alt="Yonas Girma" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBXrAUiAsO8tdpgPTv-HzTFFZXU7KtfPGDu1YEsqoTuGSTUA0-Gmm1A4YsRV8HdmEadVwo0QG6H2aNF_kzCtbIcb2lEIslSZXvCELC_9HRWfyx1mduFej8d_sjM3wV2AYJoimYxzlbDJMwsSfkFggf0xEaq6HSzkJj60PpYDgBXvYYAVmGMMYYXdwIkQbI8USE60H3Npeamoz5ISFTHwOuTPv-fRellILlssEAzlHG-dNhirDt4Adgd" />
                        <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">Yonas Girma</span>
                        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">ET-0544</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">Operations &amp; Fleet</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Logistics Coordinator</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">yonas.g@company.et</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-label-sm text-outline">not linked</span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-label-sm text-label-sm font-semibold w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Self-declared • pending verification
                      </span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
                      <span className="material-symbols-outlined text-[15px] text-primary">diversity_1</span>
                      <span>3 Children</span>
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold ">8 claims</span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="font-numeric-currency text-numeric-currency font-semibold text-on-surface">ETB 31,400.00</span>
                  </td>
                  <td className="py-3.5 pr-6 pl-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold  transition-all" type="button">View Profile</button>
                      <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
                        <span className="material-symbols-outlined text-[19px]">more_vert</span>
                      </button>
                    </div>
                  </td>
                </tr>

                {/* Row 5 */}
                <tr className="hover:bg-surface-container-low transition-colors">
                  <td className="py-3.5 pl-6 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="relative shrink-0">
                        <div className="w-10 h-10 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center font-bold text-[14px]">RM</div>
                        <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-outline-variant ring-2 ring-surface" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">Rahel Mengistu</span>
                        <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">ET-0230</span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-medium text-on-surface">Finance &amp; Legal</span>
                      <span className="font-body-sm text-body-sm text-on-surface-variant">Senior Tax Auditor</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">rahel.m@company.et</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-label-sm text-on-surface-variant">DE-00601 (endod_id)</span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface font-label-sm text-label-sm font-semibold w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-outline" /> No scheme • org benefit only
                      </span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface-variant">
                      <span className="material-symbols-outlined text-[15px]">person</span>
                      <span>Self Only</span>
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface-variant font-semibold ">0 claims</span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="font-numeric-currency text-numeric-currency font-semibold text-outline">ETB 0.00</span>
                  </td>
                  <td className="py-3.5 pr-6 pl-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold  transition-all" type="button">View Profile</button>
                      <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
                        <span className="material-symbols-outlined text-[19px]">more_vert</span>
                      </button>
                    </div>
                  </td>
                </tr>
{addedEmployees.map((emp) => {
  const initials = emp.name.split(" ").filter(Boolean).map((n) => n[0]).join("").slice(0, 2).toUpperCase() || "NA";
  const coverageClass = emp.coverage.includes("pending")
    ? "bg-amber-100 text-amber-800"
    : emp.coverage.includes("No scheme")
    ? "bg-surface-container text-on-surface"
    : "bg-secondary-container text-on-secondary-container";
  const dotClass = emp.coverage.includes("pending")
    ? "bg-amber-500"
    : emp.coverage.includes("No scheme")
    ? "bg-outline"
    : "bg-secondary";
  const spendClass = emp.spend === "ETB 0.00" ? "text-outline" : "text-on-surface";
  return (
    <tr key={emp.employeeId + emp.name} className="hover:bg-surface-container-low transition-colors">
      <td className="py-3.5 pl-6 pr-4">
        <div className="flex items-center gap-3">
          <div className="relative shrink-0">
            <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-[14px]">{initials}</div>
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface" />
          </div>
          <div className="flex flex-col min-w-0">
            <span className="font-headline-sm text-headline-sm font-semibold text-on-surface truncate">{emp.name}</span>
            <span className="font-label-sm text-label-sm font-mono text-on-surface-variant">{emp.employeeId}</span>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-4">
        <div className="flex flex-col">
          <span className="font-label-lg text-label-lg font-medium text-on-surface">{emp.department}</span>
          <span className="font-body-sm text-body-sm text-on-surface-variant">{emp.role}</span>
        </div>
      </td>
      <td className="py-3.5 px-4 text-on-surface-variant font-mono text-body-sm">{emp.email}</td>
      <td className="py-3.5 px-4">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-label-sm text-on-surface-variant">{emp.endodId ? emp.endodId + " (endod_id)" : "not linked"}</span>
          <span className={"inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold w-fit " + coverageClass}>
            <span className={"w-1.5 h-1.5 rounded-full " + dotClass} /> {emp.coverage}
          </span>
        </div>
      </td>
      <td className="py-3.5 px-4">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface">
          <span className="material-symbols-outlined text-[15px] text-primary">diversity_1</span>
          <span>{emp.dependents}</span>
        </span>
      </td>
      <td className="py-3.5 px-4 text-center">
        <span className="inline-block px-2.5 py-0.5 rounded-md bg-surface font-label-md text-label-md text-on-surface font-semibold">{emp.claims}</span>
      </td>
      <td className="py-3.5 px-4 text-right">
        <span className={"font-numeric-currency text-numeric-currency font-semibold " + spendClass}>{emp.spend}</span>
      </td>
      <td className="py-3.5 pr-6 pl-4 text-right">
        <div className="flex items-center justify-end gap-1">
          <button className="px-2.5 py-1.5 rounded-lg bg-surface text-primary hover:bg-primary hover:text-on-primary font-label-sm text-label-sm font-semibold transition-all" type="button">View Profile</button>
          <button className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high transition-colors" type="button">
            <span className="material-symbols-outlined text-[19px]">more_vert</span>
          </button>
        </div>
      </td>
    </tr>
  );
})}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="p-space-md bg-surface flex flex-col sm:flex-row items-center justify-between gap-space-md">
            <div className="flex items-center gap-2">
              <span className="font-body-sm text-body-sm text-on-surface-variant">Showing <span className="font-semibold text-on-surface">1 - 5</span> of <span className="font-semibold text-on-surface">248</span> enrolled employees</span>
            </div>
            <div className="flex items-center gap-space-xs">
              <button className="px-3 py-1 rounded-lg bg-primary text-on-primary font-label-sm text-label-sm font-semibold " type="button">1</button>
              <button className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm font-medium " type="button">2</button>
              <button className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm font-medium " type="button">3</button>
              <span className="px-2 text-outline font-label-sm text-label-sm">...</span>
              <button className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm font-medium " type="button">50</button>
            </div>
          </div>
        </div>
      </div>

      {/* Drawer backdrop */}
      {drawerOpen && (
        <div className="fixed inset-0 bg-inverse-surface/40 z-50" onClick={() => setDrawerOpen(false)} />
      )}
      {/* Drawer */}
      {drawerOpen && (
        <aside className="fixed top-0 right-0 h-full w-full max-w-xl bg-surface-container-lowest  z-50 flex flex-col justify-between overflow-y-auto transform translate-x-0 transition-transform duration-300 ease-out">
          <div className="p-space-lg bg-surface-container-low flex items-start justify-between">
            <div className="flex items-center gap-space-md">
              <div className="relative">
                <img className="w-14 h-14 rounded-full object-cover  ring-2 ring-primary" alt="Bethlehem Haile" src="https://lh3.googleusercontent.com/aida-public/AB6AXuA7R5sF2Sf0X0-hCQ91SxeAk8RqBNCj7foEk2-gkaZvkoEtfgUzP1ycbx_1Xn7TKjS_tr32bJyur1ZhRERLF8JujtvbOhJSYXgOpo0ur0i4C4uYrM9boFO_yU3J0nFJvYA6FyC_FdKJuKTWXAIa6fOEgNuW0uYCPgbTl2vTMPQ2gyFPDt0o3Jjny41QNq4w98HEXj8QiEzDrDmKfX2WHZPR2yILhJWkZvWC8GCornPykARqHNUuGQYv" />
                <span className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-tertiary ring-2 ring-surface" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <h2 className="font-headline-lg text-headline-lg font-bold text-on-surface">Bethlehem Haile</h2>
                  <span className="px-2 py-0.5 rounded-md bg-surface font-label-sm text-label-sm font-mono text-primary font-bold ">ET-0381</span>
                </div>
                <span className="font-label-lg text-label-lg text-on-surface-variant font-medium">Head of Talent Acquisition • People &amp; Culture</span>
              </div>
            </div>
            <button aria-label="Close detail pane" className="p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant transition-colors" onClick={() => setDrawerOpen(false)} type="button">
              <span className="material-symbols-outlined text-[22px]">close</span>
            </button>
          </div>
          <div className="p-space-lg flex-1 flex flex-col gap-space-lg">
            <div className="p-space-md rounded-xl bg-primary/5 flex items-center justify-between">
              <div className="flex items-center gap-space-md">
                <span className="p-2.5 rounded-xl bg-primary text-on-primary ">
                  <span className="material-symbols-outlined text-[22px]">shield_with_heart</span>
                </span>
                <div className="flex flex-col">
                  <span className="font-label-lg text-label-lg font-bold text-on-surface">Unlimited Prescription Coverage</span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">Tier-1 Direct Clinical Network (Zero Co-Pay)</span>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input checked={benefitEnabled} className="sr-only peer" type="checkbox" onChange={(e) => setBenefitEnabled(e.target.checked)} />
                <div className="w-11 h-6 bg-surface-container-high peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
              </label>
            </div>
            <div className="p-space-md rounded-xl bg-surface flex flex-col gap-space-sm ">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Contact &amp; Administrative Data</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm mt-1">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-outline text-[18px]">mail</span>
                  <span className="font-body-sm text-body-sm text-on-surface font-mono select-all">bethlehem.h@company.et</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-outline text-[18px]">call</span>
                  <span className="font-body-sm text-body-sm text-on-surface font-mono select-all">+251 91 445 6789</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-outline text-[18px]">location_on</span>
                  <span className="font-body-sm text-body-sm text-on-surface">HQ - Kazanchis, Addis Ababa</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-outline text-[18px]">calendar_today</span>
                  <span className="font-body-sm text-body-sm text-on-surface">Enrolled: Nov 01, 2022</span>
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Covered Dependents (2)</span>
                <button className="font-label-sm text-label-sm text-primary hover:underline font-semibold" type="button">+ Add Dependent</button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
                <div className="p-space-md rounded-xl bg-surface flex items-center justify-between ">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-lg bg-surface-container text-primary">
                      <span className="material-symbols-outlined text-[20px]">person</span>
                    </span>
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-bold text-on-surface">Kenenisa T.</span>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Husband • Primary Spouse</span>
                    </div>
                  </div>
                  <span className="material-symbols-outlined text-tertiary text-[18px]" title="Fully Active">check_circle</span>
                </div>
                <div className="p-space-md rounded-xl bg-surface flex items-center justify-between ">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-lg bg-surface-container text-primary">
                      <span className="material-symbols-outlined text-[20px]">child_care</span>
                    </span>
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-bold text-on-surface">Robel Kenenisa</span>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Son • 4 yrs old</span>
                    </div>
                  </div>
                  <span className="material-symbols-outlined text-tertiary text-[18px]" title="Fully Active">check_circle</span>
                </div>
              </div>
            </div>
            <div className="p-space-lg rounded-xl bg-surface-container-low flex flex-col gap-space-md ">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Annual Medication Utilization</span>
                  <span className="font-display-lg text-display-lg font-bold text-on-surface mt-1">ETB 14,350.00</span>
                </div>
                <div className="text-right">
                  <span className="font-label-sm text-label-sm text-tertiary font-bold px-2.5 py-1 rounded-full bg-secondary-container">5 Claims Approved</span>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Policy Limit: Unlimited</p>
                </div>
              </div>
              <div className="w-full pt-2">
                <div className="flex items-center justify-between text-label-sm font-label-sm text-on-surface-variant mb-1">
                  <span>Spend Velocity (Jan - Oct 2024)</span>
                  <span className="font-mono">ETB 1,435 / mo avg</span>
                </div>
                <svg className="w-full h-12 text-primary" fill="none" viewBox="0 0 300 48">
                  <path d="M0 40 Q 40 38, 75 25 T 150 30 T 225 15 T 300 8" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.5" />
                  <path d="M0 40 Q 40 38, 75 25 T 150 30 T 225 15 T 300 8 L 300 48 L 0 48 Z" fill="currentColor" fillOpacity="0.12" />
                  <circle cx="75" cy="25" fill="currentColor" r="3.5" />
                  <circle cx="150" cy="30" fill="currentColor" r="3.5" />
                  <circle cx="225" cy="15" fill="currentColor" r="3.5" />
                  <circle className="animate-ping" cx="300" cy="8" fill="currentColor" r="4.5" />
                  <circle cx="300" cy="8" fill="currentColor" r="3.5" />
                </svg>
              </div>
            </div>
            <div className="flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">Prescription Claim Ledger (2024)</span>
                <a className="font-label-sm text-label-sm text-primary hover:underline font-semibold flex items-center gap-0.5" href="#">
                  Full Audit Ledger
                  <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                </a>
              </div>
              <div className="flex flex-col gap-2">
                <div className="p-space-md rounded-xl bg-surface flex items-center justify-between  hover:bg-surface-container-high transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-lg bg-surface-container-high text-primary">
                      <span className="material-symbols-outlined text-[19px]">receipt_long</span>
                    </span>
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-semibold text-on-surface">Lion Pharmacy Kazanchis</span>
                      <div className="flex items-center gap-2 text-on-surface-variant font-body-sm text-body-sm">
                        <span>Oct 18, 2024</span>
                        <span>•</span>
                        <span>Direct Dispense #LP-891</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-numeric-currency text-numeric-currency font-bold text-on-surface">ETB 2,150.00</span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-label-sm text-label-sm font-semibold">Approved</span>
                  </div>
                </div>
                <div className="p-space-md rounded-xl bg-surface flex items-center justify-between  hover:bg-surface-container-high transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-lg bg-surface-container-high text-primary">
                      <span className="material-symbols-outlined text-[19px]">receipt_long</span>
                    </span>
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-semibold text-on-surface">Kenema Pharmacy Bole Hub</span>
                      <div className="flex items-center gap-2 text-on-surface-variant font-body-sm text-body-sm">
                        <span>Aug 04, 2024</span>
                        <span>•</span>
                        <span>Pediatric Rx #KP-204</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-numeric-currency text-numeric-currency font-bold text-on-surface">ETB 3,800.00</span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant font-label-sm text-label-sm font-semibold">Disbursed</span>
                  </div>
                </div>
                <div className="p-space-md rounded-xl bg-surface flex items-center justify-between  hover:bg-surface-container-high transition-colors">
                  <div className="flex items-center gap-3">
                    <span className="p-2 rounded-lg bg-surface-container-high text-primary">
                      <span className="material-symbols-outlined text-[19px]">receipt_long</span>
                    </span>
                    <div className="flex flex-col">
                      <span className="font-label-lg text-label-lg font-semibold text-on-surface">Kadisco Hospital Central Pharmacy</span>
                      <div className="flex items-center gap-2 text-on-surface-variant font-body-sm text-body-sm">
                        <span>Jun 12, 2024</span>
                        <span>•</span>
                        <span>Prescription Inpatient #KD-441</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-numeric-currency text-numeric-currency font-bold text-on-surface">ETB 4,200.00</span>
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant font-label-sm text-label-sm font-semibold">Disbursed</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="p-space-lg bg-surface-container-low flex items-center justify-between gap-space-md">
            <button className="flex-1 py-2.5 px-4 rounded-lg bg-surface text-on-surface font-label-lg text-label-lg font-semibold hover:bg-surface-container-high transition-colors  flex items-center justify-center gap-2" type="button">
              <span className="material-symbols-outlined text-[18px]">history_edu</span>
              <span>Export Statement</span>
            </button>
            <button className="flex-1 py-2.5 px-4 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors  flex items-center justify-center gap-2" type="button">
              <span className="material-symbols-outlined text-[18px]">edit_note</span>
              <span>Edit Beneficiary Policy</span>
            </button>
          </div>
        </aside>
      )}
      {/* Add Employee Modal */}
      {addEmployeeOpen && (
        <>
          <div className="fixed inset-0 bg-inverse-surface/40 z-50" onClick={() => setAddEmployeeOpen(false)} />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-surface-container-lowest rounded-xl w-full max-w-lg p-space-lg flex flex-col gap-space-md shadow-lg">
              <div className="flex items-center justify-between">
                <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">Add Single Employee</h2>
                <button className="p-2 rounded-full hover:bg-surface-container-high text-on-surface-variant transition-colors" onClick={() => setAddEmployeeOpen(false)} type="button">
                  <span className="material-symbols-outlined text-[20px]">close</span>
                </button>
              </div>
              <div className="flex flex-col gap-space-sm">
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Full Name</span>
                  <input className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.name} onChange={(e) => setNewEmployee({ ...newEmployee, name: e.target.value })} type="text" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Employee ID</span>
                  <input className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.employeeId} onChange={(e) => setNewEmployee({ ...newEmployee, employeeId: e.target.value })} type="text" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Department</span>
                  <select className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.department} onChange={(e) => setNewEmployee({ ...newEmployee, department: e.target.value })}>
                    <option>Engineering</option>
                    <option>Sales &amp; Partnerships</option>
                    <option>People &amp; Culture</option>
                    <option>Operations &amp; Fleet</option>
                    <option>Finance &amp; Legal</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Email</span>
                  <input className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.email} onChange={(e) => setNewEmployee({ ...newEmployee, email: e.target.value })} type="email" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Role</span>
                  <input className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.role} onChange={(e) => setNewEmployee({ ...newEmployee, role: e.target.value })} type="text" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">ENDOD ID</span>
                  <input className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.endodId} onChange={(e) => setNewEmployee({ ...newEmployee, endodId: e.target.value })} type="text" />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Coverage</span>
                  <select className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.coverage} onChange={(e) => setNewEmployee({ ...newEmployee, coverage: e.target.value })}>
                    <option>CBHI • verified</option>
                    <option>SHI • verified</option>
                    <option>No scheme • org benefit only</option>
                    <option>Self-declared • pending verification</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Dependents</span>
                  <select className="h-10 px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" value={newEmployee.dependents} onChange={(e) => setNewEmployee({ ...newEmployee, dependents: e.target.value })}>
                    <option>Self Only</option>
                    <option>Self + Spouse</option>
                    <option>Self + 1 Child</option>
                    <option>Self + Spouse + Children</option>
                  </select>
                </label>
              </div>
              <div className="flex items-center justify-end gap-space-md pt-2">
                <button className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md hover:bg-surface-variant transition-colors" onClick={() => setAddEmployeeOpen(false)} type="button">Cancel</button>
                <button className="px-5 py-2 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-primary-container transition-all" onClick={() => { setAddedEmployees((prev) => [...prev, { ...newEmployee }]); setNewEmployee({ name: "", employeeId: "", department: "Engineering", role: "", email: "", endodId: "", coverage: "SHI • verified", dependents: "Self Only", claims: "0 claims", spend: "ETB 0.00" }); setAddEmployeeOpen(false); }} type="button">Add Employee</button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
