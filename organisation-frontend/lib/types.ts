/** Shapes of the portal API's answers. Amounts are integers in santim. */

export type Stage = "totp" | "enroll" | "full";

export type ApplicationStatus = "draft" | "submitted" | "approved" | "rejected";

export type Me = {
  stage: Stage;
  admin: { id: string; email: string; name: string };
  /** application_status: "approved" for every organisation in business; else it is still applying (app/apply). */
  organisation: { id: string; name: string; application_status?: ApplicationStatus };
  reauth_valid_until: string | null;
};

export type ClaimStatus = "pending" | "approved" | "rejected" | "paid";
export type PayoutMethod = "cbe" | "awash" | "dashen" | "telebirr";

export type Dependant = { id: string; name: string; relationship: string; birth_date: string | null; active: boolean };

export type Employee = {
  id: string;
  employee_number: string;
  name: string;
  phone: string;
  department: string;
  endod_id: string | null;
  active: boolean;
  payout_method: PayoutMethod | null;
  payout_account: string | null;
  created_at: string;
  deactivated_at: string | null;
  claims_count: number;
  spend_santim: number;
  dependants: Dependant[];
  has_policy_override: boolean;
};

export type PolicyRules = {
  annual_limit_santim: number;
  copay_percent: number;
  dependants_covered: boolean;
  excluded_medicines: string[];
};

export type EmployeeDetail = Employee & {
  policy: PolicyRules & { override: (PolicyRules & { updated_at: string }) | null };
  usage: { policy_year: { start: string; end: string }; used_santim: number; remaining_santim: number };
  recent_claims: Claim[];
};

export type EmployeeList = {
  items: Employee[];
  total: number;
  page: number;
  page_size: number;
  departments: string[];
  counts: { active: number; inactive: number; linked: number; claimants: number; dependants: number };
  policy_year: { start: string; end: string };
};

export type ClaimItem = { medicine: string; quantity: number; unit_price_santim: number; line_total_santim: number };

export type Assessment = {
  total_santim: number;
  copay_percent: number;
  copay_santim: number;
  share_santim: number;
  payable_santim: number;
  annual_limit_santim: number;
  used_santim: number;
  remaining_santim: number;
  capped: boolean;
  policy_year: { start: string; end: string };
  problems: { code: string; message: string }[];
  notes: string[];
  approvable: boolean;
};

export type Claim = {
  id: string;
  code: string;
  number: number;
  status: ClaimStatus;
  source: string;
  employee_id: string;
  dependant_id: string | null;
  pharmacy_name: string;
  pharmacy_tin: string;
  receipt_number: string;
  receipt_date: string;
  total_santim: number;
  copay_santim: number | null;
  approved_santim: number | null;
  rejection_reason: string | null;
  has_receipt: boolean;
  receipt_file_id: string | null;
  created_at: string;
  reviewer_name: string | null;
  reviewed_at: string | null;
  batch_id: string | null;
  paid_at: string | null;
  employee?: {
    id: string;
    name: string;
    employee_number: string;
    department: string;
    endod_id: string | null;
    active: boolean;
    payout_method: PayoutMethod | null;
  };
  dependant?: Dependant;
  items?: ClaimItem[];
  medicines?: string[];
  batch?: { id: string; code: string; status: string; reference: string | null };
  assessment?: Assessment;
  notes?: string[];
  payout_account?: string | null;
  payout_ready?: boolean;
};

export type ClaimList = {
  items: Claim[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<ClaimStatus | "all", number>;
  pending_total_santim: number;
  pharmacies: string[];
  departments: string[];
};

export type Batch = {
  id: string;
  code: string;
  number: number;
  method: PayoutMethod;
  method_label: string;
  status: "open" | "paid";
  total_santim: number;
  claim_count: number;
  created_at: string;
  paid_at: string | null;
  reference: string | null;
  exported_at: string | null;
  claims?: Claim[];
};

export type Payments = {
  items: Batch[];
  ready: {
    claims: Claim[];
    by_method: Record<PayoutMethod, { claims: number; total_santim: number }>;
    missing_payout_details: { claims: number; total_santim: number };
    total_santim: number;
  };
  enabled_methods: PayoutMethod[];
  paid_this_month_santim: number;
  open_total_santim: number;
};

export type Overview = {
  policy_year: { start: string; end: string };
  spend_santim: number;
  reimbursed_santim: number;
  awaiting_payout_santim: number;
  claims_submitted: number;
  by_status: Record<ClaimStatus, { claims: number; total_santim: number; approved_santim: number }>;
  pending_claims: number;
  pending_total_santim: number;
  employees: { active: number; linked_endod: number; claimants: number };
  policy: { annual_limit_santim: number; copay_percent: number; dependants_covered: boolean };
};

export type Report = {
  period: { from: string; to: string };
  totals: { claims: number; approved_santim: number; total_santim: number; employees: number; average_claim_santim: number };
  by_month: { month: string; claims: number; approved_santim: number; total_santim: number }[];
  by_department: { department: string; claims: number; approved_santim: number; total_santim: number; employees: number }[];
  by_medicine: { medicine: string; quantity: number; total_santim: number; claims: number }[];
  by_employee: { employee_number: string; name: string; department: string; claims: number; approved_santim: number }[];
};

export type Policy = PolicyRules & {
  year_start_month: number;
  year_start_day: number;
  updated_at: string;
  current_year: { start: string; end: string };
};

export type Organisation = {
  id: string;
  name: string;
  tin: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  status: string;
  payout: { debit_account: string | null; methods: PayoutMethod[] };
};

export type ImportRow = { line: number; employee_number: string; name: string; action: "create" | "update" | "unchanged" | "error"; errors: string[] };
export type ImportPlan = { rows: ImportRow[]; summary: Record<ImportRow["action"], number>; valid: boolean };
