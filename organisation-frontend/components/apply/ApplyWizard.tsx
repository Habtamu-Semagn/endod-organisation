"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, apiFetch, uploadApplicationDocument, RECEIPT_TYPES } from "@/lib/api";
import { hardNavigate } from "@/lib/navigation";
import { SECTORS, STEPS, sectorLabel, type Application, type Company, type StepKey } from "@/lib/application";
import type { Me } from "@/lib/types";
import ApplyFrame from "@/components/apply/ApplyFrame";
import { FormError, inputClass, labelClass, linkButton, primaryButton } from "@/components/auth/AuthCard";

const secondaryButton =
  "h-10 px-4 rounded-lg bg-surface-container-high text-on-surface font-label-lg text-label-lg font-semibold hover:bg-surface-container-highest transition-colors disabled:opacity-50";

type State =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "error"; message: string }
  | { status: "ready"; application: Application };

function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function stepIndex(key: StepKey | undefined): number {
  return Math.max(0, STEPS.findIndex((s) => s.key === key));
}

export async function signOut() {
  await apiFetch("auth/logout", { method: "POST", redirectOn401: false }).catch(() => null);
  hardNavigate("/login");
}

/** Where the visitor stands; null when the page is being left. */
async function readState(): Promise<State | null> {
  let me: Me;
  try {
    me = await apiFetch<Me>("auth/me", { redirectOn401: false });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { status: "signed-out" };
    return { status: "error", message: messageOf(error, "Something went wrong.") };
  }
  if (me.stage === "totp") {
    hardNavigate("/login");
    return null;
  }
  if (me.stage === "enroll") {
    hardNavigate("/enroll");
    return null;
  }
  if (!me.organisation.application_status || me.organisation.application_status === "approved") {
    hardNavigate("/");
    return null;
  }
  try {
    const application = await apiFetch<Application>("application", { redirectOn401: false });
    const fixing = new URLSearchParams(window.location.search).get("fix") === "1";
    if (application.status === "submitted" || application.status === "closed" || (application.status === "rejected" && !fixing)) {
      hardNavigate("/under-review");
      return null;
    }
    return { status: "ready", application };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { status: "signed-out" };
    return { status: "error", message: messageOf(error, "Something went wrong.") };
  }
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      {children}
      {hint && <p className="mt-1 font-body-sm text-body-sm text-outline">{hint}</p>}
    </div>
  );
}

/**
 * A company's application to TenaCare, after the hospital portal's
 * onboarding wizard: the account (and a mandatory authenticator), the
 * company, its documents, then review and submit. Each step is saved on the
 * API as it is completed, so a reload or a later sign-in comes back to the
 * first step still missing something.
 */
export default function ApplyWizard() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [step, setStep] = useState(0);

  const load = useCallback(() => {
    void readState().then((next) => {
      if (!next) return;
      setState(next);
      if (next.status === "ready") setStep(stepIndex(next.application.next_step));
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saved = (application: Application, advance = true) => {
    setState({ status: "ready", application });
    if (advance) {
      setStep((current) => Math.min(current + 1, STEPS.length - 1));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  const back = () => setStep((current) => Math.max(current - 1, 0));

  const footer = (
    <p className="mt-space-md text-center font-body-sm text-body-sm text-on-surface-variant">
      Saved as you go: sign in again any time to continue.{" "}
      <button type="button" onClick={() => void signOut()} className={linkButton}>
        Sign out
      </button>
    </p>
  );

  if (state.status === "loading") {
    return (
      <ApplyFrame title="Apply as a company">
        <p role="status" className="font-body-sm text-body-sm text-on-surface-variant">
          Loading your application…
        </p>
      </ApplyFrame>
    );
  }
  if (state.status === "error") {
    return (
      <ApplyFrame title="Apply as a company" footer={footer}>
        <FormError message={state.message} />
      </ApplyFrame>
    );
  }
  if (state.status === "signed-out") {
    return (
      <ApplyFrame
        title="Apply as a company"
        subtitle="Give your employees medication benefits through Endod. Create your account first: you will be the organisation's first administrator."
        step={0}
        footer={
          <p className="mt-space-md text-center font-body-sm text-body-sm text-on-surface-variant">
            Already applied or using TenaCare?{" "}
            <a href="/login" className={linkButton}>
              Sign in
            </a>
          </p>
        }
      >
        <AccountStep />
      </ApplyFrame>
    );
  }

  const { application } = state;
  const key = STEPS[step].key;
  const titles: Record<StepKey, string> = {
    contact: "Your details",
    company: "Your company",
    documents: "Documents",
    review: "Review and submit",
  };
  return (
    <ApplyFrame title={titles[key]} subtitle={application.organisation_name} step={step} footer={footer}>
      {application.status === "rejected" && application.rejection_reason && (
        <div data-testid="rejection-note" className="mb-space-md rounded-xl bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-900">
          <p className="font-semibold">Endod asked you to change your application</p>
          <p className="mt-1">{application.rejection_reason}</p>
        </div>
      )}
      {key === "contact" && <ContactStep key={key} application={application} onSaved={saved} />}
      {key === "company" && <CompanyStep key={key} application={application} onSaved={saved} onBack={back} />}
      {key === "documents" && (
        <DocumentsStep key={key} application={application} onChanged={(a) => saved(a, false)} onNext={() => setStep(3)} onBack={back} />
      )}
      {key === "review" && <ReviewStep key={key} application={application} onEdit={setStep} onBack={back} />}
    </ApplyFrame>
  );
}

// --- step 1: the account -------------------------------------------------------------------------

function AccountStep() {
  const [form, setForm] = useState({ legal_name: "", full_name: "", title: "", phone: "", email: "", password: "", repeat: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (form.password !== form.repeat) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        legal_name: form.legal_name,
        full_name: form.full_name,
        title: form.title,
        phone: form.phone,
        email: form.email,
        password: form.password,
      };
      await apiFetch("application/start", { method: "POST", body, redirectOn401: false });
      // Two-step verification comes before anything else.
      hardNavigate("/enroll");
    } catch (e) {
      setError(messageOf(e, "Could not create the account."));
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" data-testid="account-step">
      <Field id="legal_name" label="Company legal name">
        <input id="legal_name" required value={form.legal_name} onChange={set("legal_name")} className={inputClass} autoComplete="organization" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="full_name" label="Your full name">
          <input id="full_name" required value={form.full_name} onChange={set("full_name")} className={inputClass} autoComplete="name" />
        </Field>
        <Field id="title" label="Your title">
          <input id="title" required value={form.title} onChange={set("title")} className={inputClass} placeholder="HR Manager" autoComplete="organization-title" />
        </Field>
        <Field id="phone" label="Your mobile">
          <input id="phone" required value={form.phone} onChange={set("phone")} className={inputClass} placeholder="0911 223344" autoComplete="tel" inputMode="tel" />
        </Field>
        <Field id="email" label="Work email" hint="You sign in with it.">
          <input id="email" type="email" required value={form.email} onChange={set("email")} className={inputClass} autoComplete="username" />
        </Field>
        <Field id="password" label="Password" hint="At least 8 characters; a phrase is best.">
          <input id="password" type="password" required value={form.password} onChange={set("password")} className={inputClass} autoComplete="new-password" />
        </Field>
        <Field id="repeat" label="Repeat the password">
          <input id="repeat" type="password" required value={form.repeat} onChange={set("repeat")} className={inputClass} autoComplete="new-password" />
        </Field>
      </div>
      <FormError message={error} />
      <button type="submit" disabled={busy} className={primaryButton}>
        {busy ? "Creating your account…" : "Create account and continue"}
      </button>
    </form>
  );
}

// --- the contact (to fix it later) ---------------------------------------------------------------

function ContactStep({ application, onSaved }: { application: Application; onSaved: (a: Application) => void }) {
  const contact = application.contact;
  const [form, setForm] = useState({ full_name: contact?.full_name ?? "", title: contact?.title ?? "", phone: contact?.phone ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [field]: e.target.value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await apiFetch<Application>("application/contact", { method: "PUT", body: form }));
    } catch (e) {
      setError(messageOf(e, "Could not save."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" data-testid="contact-step">
      <p className="font-body-sm text-body-sm text-on-surface-variant">Signed in as {contact?.email}.</p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field id="contact_full_name" label="Your full name">
          <input id="contact_full_name" required value={form.full_name} onChange={set("full_name")} className={inputClass} />
        </Field>
        <Field id="contact_title" label="Your title">
          <input id="contact_title" required value={form.title} onChange={set("title")} className={inputClass} />
        </Field>
        <Field id="contact_phone" label="Your mobile">
          <input id="contact_phone" required value={form.phone} onChange={set("phone")} className={inputClass} inputMode="tel" />
        </Field>
      </div>
      <FormError message={error} />
      <button type="submit" disabled={busy} className={primaryButton}>
        {busy ? "Saving…" : "Save and continue"}
      </button>
    </form>
  );
}

// --- step 2: the company ---------------------------------------------------------------------------

function CompanyStep({ application, onSaved, onBack }: { application: Application; onSaved: (a: Application) => void; onBack: () => void }) {
  const c: Partial<Company> = application.company ?? {};
  const [form, setForm] = useState({
    legal_name: c.legal_name ?? "",
    trade_name: c.trade_name ?? "",
    tin: c.tin ?? "",
    business_license_number: c.business_license_number ?? "",
    sector: c.sector ?? "",
    employee_count: c.employee_count ? String(c.employee_count) : "",
    city: c.city ?? "",
    address: c.address ?? "",
    phone: c.phone ?? "",
    email: c.email ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [field]: e.target.value });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const count = Number(form.employee_count);
    if (!Number.isInteger(count) || count < 1) {
      setError("Number of employees must be a whole number, at least 1.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = { ...form, employee_count: count, trade_name: form.trade_name.trim() || null };
      onSaved(await apiFetch<Application>("application/company", { method: "PUT", body }));
    } catch (e) {
      setError(messageOf(e, "Could not save."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" data-testid="company-step">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="company_legal_name" label="Legal name">
          <input id="company_legal_name" required value={form.legal_name} onChange={set("legal_name")} className={inputClass} />
        </Field>
        <Field id="trade_name" label="Trade name (optional)">
          <input id="trade_name" value={form.trade_name} onChange={set("trade_name")} className={inputClass} />
        </Field>
        <Field id="tin" label="TIN" hint="10 digits.">
          <input id="tin" required value={form.tin} onChange={set("tin")} className={`${inputClass} font-mono`} inputMode="numeric" />
        </Field>
        <Field id="business_license_number" label="Business license number">
          <input id="business_license_number" required value={form.business_license_number} onChange={set("business_license_number")} className={inputClass} />
        </Field>
        <Field id="sector" label="Sector">
          <select id="sector" required value={form.sector} onChange={set("sector")} className={inputClass}>
            <option value="">Choose…</option>
            {SECTORS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id="employee_count" label="Number of employees">
          <input id="employee_count" required type="number" min={1} step={1} value={form.employee_count} onChange={set("employee_count")} className={inputClass} />
        </Field>
        <Field id="city" label="City">
          <input id="city" required value={form.city} onChange={set("city")} className={inputClass} />
        </Field>
        <Field id="address" label="Address">
          <input id="address" required value={form.address} onChange={set("address")} className={inputClass} placeholder="Sub-city, woreda, house number" />
        </Field>
        <Field id="company_phone" label="Company phone">
          <input id="company_phone" required value={form.phone} onChange={set("phone")} className={inputClass} placeholder="011 551 2345" inputMode="tel" />
        </Field>
        <Field id="company_email" label="Company email">
          <input id="company_email" type="email" required value={form.email} onChange={set("email")} className={inputClass} />
        </Field>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <button type="button" onClick={onBack} className={secondaryButton}>
          Back
        </button>
        <button type="submit" disabled={busy} className={primaryButton}>
          {busy ? "Saving…" : "Save and continue"}
        </button>
      </div>
    </form>
  );
}

// --- step 3: documents -----------------------------------------------------------------------------

function DocumentsStep({
  application,
  onChanged,
  onNext,
  onBack,
}: {
  application: Application;
  onChanged: (a: Application) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const [busyKind, setBusyKind] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const documents = application.documents ?? [];
  const allUploaded = documents.length > 0 && documents.every((d) => d.uploaded);

  const upload = async (kind: string, file: File | undefined) => {
    if (!file) return;
    setBusyKind(kind);
    setError(null);
    try {
      onChanged((await uploadApplicationDocument(kind, file)) as Application);
    } catch (e) {
      setError(messageOf(e, "Could not upload the document."));
    } finally {
      setBusyKind(null);
    }
  };

  return (
    <div className="space-y-4" data-testid="documents-step">
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        PDF, JPEG, PNG or WebP, at most 10 MB each. Uploading a document again replaces it.
      </p>
      <ul className="space-y-3">
        {documents.map((doc) => (
          <li key={doc.kind} className="rounded-xl bg-surface-container-low p-space-md">
            <label className="flex flex-col gap-1">
              <span className={labelClass}>{doc.label}</span>
              <input
                type="file"
                accept={RECEIPT_TYPES.join(",")}
                disabled={busyKind !== null}
                onChange={(e) => void upload(doc.kind, e.target.files?.[0])}
                className="font-body-sm text-body-sm text-on-surface"
              />
            </label>
            {busyKind === doc.kind && <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">Uploading…</p>}
            {doc.uploaded && (
              <p data-testid={`document-${doc.kind}`} className="mt-1 font-body-sm text-body-sm text-on-surface">
                <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-tertiary align-middle">check_circle</span>{" "}
                {doc.filename} uploaded ·{" "}
                <a href={`/api/application/documents/${doc.kind}`} target="_blank" rel="noopener noreferrer" className={linkButton}>
                  View
                </a>
              </p>
            )}
          </li>
        ))}
      </ul>
      <FormError message={error} />
      <div className="flex gap-2">
        <button type="button" onClick={onBack} className={secondaryButton}>
          Back
        </button>
        <button type="button" disabled={!allUploaded || busyKind !== null} onClick={onNext} className={primaryButton}>
          Continue to review
        </button>
      </div>
    </div>
  );
}

// --- step 4: review and submit -----------------------------------------------------------------------

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-surface-container last:border-0">
      <dt className="font-body-sm text-body-sm text-on-surface-variant">{label}</dt>
      <dd className="font-body-sm text-body-sm text-on-surface text-right">{value || "—"}</dd>
    </div>
  );
}

function ReviewStep({ application, onEdit, onBack }: { application: Application; onEdit: (step: number) => void; onBack: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const c = application.company;
  const contact = application.contact;
  const missing = application.missing ?? { contact: [], company: [], documents: [] };
  const incomplete = STEPS.filter((s) => s.key !== "review" && missing[s.key as keyof typeof missing]?.length);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("application/submit", { method: "POST" });
      hardNavigate("/under-review");
    } catch (e) {
      setError(messageOf(e, "Could not submit the application."));
      setBusy(false);
    }
  };

  const section = (title: string, stepAt: number, children: ReactNode) => (
    <section className="rounded-xl bg-surface-container-low p-space-md">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">{title}</h2>
        <button type="button" onClick={() => onEdit(stepAt)} className={linkButton}>
          Edit
        </button>
      </div>
      <dl>{children}</dl>
    </section>
  );

  return (
    <div className="space-y-4" data-testid="review-step">
      {section(
        "Contact",
        0,
        <>
          <Row label="Name" value={contact?.full_name} />
          <Row label="Title" value={contact?.title} />
          <Row label="Mobile" value={contact?.phone} />
          <Row label="Email" value={contact?.email} />
        </>
      )}
      {section(
        "Company",
        1,
        <>
          <Row label="Legal name" value={c?.legal_name} />
          <Row label="Trade name" value={c?.trade_name} />
          <Row label="TIN" value={c?.tin} />
          <Row label="Business license" value={c?.business_license_number} />
          <Row label="Sector" value={sectorLabel(c?.sector)} />
          <Row label="Employees" value={c?.employee_count} />
          <Row label="City" value={c?.city} />
          <Row label="Address" value={c?.address} />
          <Row label="Phone" value={c?.phone} />
          <Row label="Email" value={c?.email} />
        </>
      )}
      {section(
        "Documents",
        2,
        <>
          {(application.documents ?? []).map((d) => (
            <Row key={d.kind} label={d.label} value={d.uploaded ? d.filename : "Missing"} />
          ))}
        </>
      )}
      {incomplete.length > 0 && (
        <FormError message={`Finish these steps first: ${incomplete.map((s) => s.label.toLowerCase()).join(", ")}.`} />
      )}
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Endod reviews your application. Until it is approved, you can only see its status here.
      </p>
      <FormError message={error} />
      <div className="flex gap-2">
        <button type="button" onClick={onBack} className={secondaryButton}>
          Back
        </button>
        <button type="button" disabled={busy || incomplete.length > 0} onClick={() => void submit()} className={primaryButton}>
          {busy ? "Submitting…" : "Submit application"}
        </button>
      </div>
    </div>
  );
}
