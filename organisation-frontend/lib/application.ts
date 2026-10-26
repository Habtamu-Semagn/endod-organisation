import type { ApplicationStatus } from "@/lib/types";

/** A company's application, as GET /api/application answers (docs/company-onboarding.md). */

export type DocumentKind = "trade_license" | "tin_certificate" | "authorization_letter";

export type ApplicationDocument = {
  kind: DocumentKind;
  label: string;
  uploaded: boolean;
  filename?: string;
  content_type?: string;
  size?: number;
  uploaded_at?: string;
};

export type Company = {
  legal_name: string | null;
  trade_name: string | null;
  tin: string | null;
  business_license_number: string | null;
  sector: string | null;
  employee_count: number | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
};

export type Contact = { full_name: string | null; title: string | null; phone: string | null; email: string | null };

export type StepKey = "contact" | "company" | "documents" | "review";

export type Application = {
  status: ApplicationStatus;
  organisation_name: string;
  editable?: boolean;
  next_step?: StepKey;
  complete?: boolean;
  missing?: Record<"contact" | "company" | "documents", string[]>;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
  contact?: Contact;
  company?: Company;
  documents?: ApplicationDocument[];
};

export const STEPS: { key: StepKey; label: string }[] = [
  { key: "contact", label: "Account" },
  { key: "company", label: "Company" },
  { key: "documents", label: "Documents" },
  { key: "review", label: "Review" },
];

export const SECTORS: { value: string; label: string }[] = [
  { value: "government", label: "Government" },
  { value: "ngo", label: "NGO" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "services", label: "Services" },
  { value: "finance", label: "Finance" },
  { value: "telecom", label: "Telecom" },
  { value: "health", label: "Health" },
  { value: "education", label: "Education" },
  { value: "retail", label: "Retail" },
  { value: "transport", label: "Transport" },
  { value: "agriculture", label: "Agriculture" },
  { value: "other", label: "Other" },
];

export function sectorLabel(value: string | null | undefined): string {
  return SECTORS.find((s) => s.value === value)?.label ?? value ?? "";
}
