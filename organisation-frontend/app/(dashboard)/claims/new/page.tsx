"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fieldClass, fieldLabelClass } from "@/components/Dialog";
import { usePortal } from "@/components/PortalShell";
import { ErrorBanner, messageOf } from "@/components/ui";
import { apiFetch, RECEIPT_TYPES, uploadReceipt, type UploadedReceipt } from "@/lib/api";
import { formatEtb, parseEtb, todayIso } from "@/lib/format";
import type { Claim, Employee, EmployeeDetail, EmployeeList } from "@/lib/types";
import { Icon } from "@/components/Icon";

type Line = { key: number; medicine: string; quantity: string; price: string };

let nextKey = 1;
const emptyLine = (): Line => ({ key: nextKey++, medicine: "", quantity: "1", price: "" });

/** Line total in santim, or null while the line is incomplete. Integers only. */
function lineTotal(line: Line): number | null {
  const quantity = /^\d{1,6}$/.test(line.quantity.trim()) ? Number(line.quantity.trim()) : null;
  const price = parseEtb(line.price);
  if (!quantity || price === null || price <= 0) return null;
  return quantity * price;
}

export default function NewClaimPage() {
  const router = useRouter();
  const { refreshCounts } = usePortal();
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState<Employee[]>([]);
  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [dependantId, setDependantId] = useState("");
  const [pharmacyName, setPharmacyName] = useState("");
  const [pharmacyTin, setPharmacyTin] = useState("");
  const [receiptNumber, setReceiptNumber] = useState("");
  const [receiptDate, setReceiptDate] = useState(todayIso());
  const [lines, setLines] = useState<Line[]>(() => [emptyLine()]);
  const [receipt, setReceipt] = useState<UploadedReceipt | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (employee || search.trim().length < 2) return;
    let alive = true;
    const timer = setTimeout(() => {
      apiFetch<EmployeeList>(`employees?q=${encodeURIComponent(search.trim())}&page_size=8`)
        .then((list) => alive && setMatches(list.items))
        .catch(() => alive && setMatches([]));
    }, 200);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [search, employee]);

  const choose = async (picked: Employee) => {
    setMatches([]);
    setSearch(picked.name);
    try {
      setEmployee(await apiFetch<EmployeeDetail>(`employees/${picked.id}`));
      setDependantId("");
    } catch (e) {
      setError(messageOf(e, "Could not load that employee."));
    }
  };

  const onFile = async (file: File | undefined) => {
    setReceipt(null);
    setError(null);
    if (!file) return;
    setUploading(true);
    try {
      setReceipt(await uploadReceipt(file));
    } catch (e) {
      setError(messageOf(e, "The receipt could not be uploaded."));
    } finally {
      setUploading(false);
    }
  };

  const totals = lines.map(lineTotal);
  const complete = totals.every((t) => t !== null) && lines.every((l) => l.medicine.trim().length >= 2);
  const total = complete ? totals.reduce<number>((sum, t) => sum + (t ?? 0), 0) : null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!employee || !receipt || !complete) return;
    setBusy(true);
    setError(null);
    try {
      const created = await apiFetch<Claim>("claims", {
        method: "POST",
        body: {
          employee_id: employee.id,
          dependant_id: dependantId || null,
          pharmacy_name: pharmacyName,
          pharmacy_tin: pharmacyTin,
          receipt_number: receiptNumber,
          receipt_date: receiptDate,
          receipt_file_id: receipt.id,
          items: lines.map((line) => ({
            medicine: line.medicine,
            quantity: Number(line.quantity.trim()),
            unit_price_santim: parseEtb(line.price),
          })),
        },
      });
      refreshCounts();
      router.push(`/claims/${created.id}`);
    } catch (e) {
      setError(messageOf(e, "The claim could not be saved."));
      setBusy(false);
    }
  };

  const setLine = (key: number, change: Partial<Line>) =>
    setLines((all) => all.map((line) => (line.key === key ? { ...line, ...change } : line)));

  return (
    <div className="w-full max-w-5xl flex flex-col gap-space-md pb-space-2xl pt-space-lg">
      <Link href="/claims" className="inline-flex items-center gap-1 font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors w-max">
        <Icon aria-hidden="true" name="arrow_back" size={18} />
        Back to claims
      </Link>
      <header className="flex flex-col gap-1">
        <h1 className="font-headline-lg text-headline-lg font-bold text-on-surface">New Claim</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          The employee paid at the pharmacy. Enter the receipt exactly as printed and attach a photo or scan of it.
        </p>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-space-md">
        <section className="bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-space-sm">
          <h2 className="font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">Employee</h2>
          <div className="relative">
            <label className="flex flex-col gap-1">
              <span className={fieldLabelClass}>Find employee</span>
              <input
                className={fieldClass}
                value={search}
                placeholder="Name, employee number or Endod ID"
                onChange={(e) => {
                  setSearch(e.target.value);
                  setEmployee(null);
                }}
              />
            </label>
            {matches.length > 0 && !employee && (
              <div className="absolute z-20 mt-1 w-full bg-surface-container-lowest rounded-lg shadow-lg border border-surface-container-high py-1">
                {matches.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    data-testid="employee-option"
                    onClick={() => void choose(m)}
                    className="w-full text-left px-3 py-2 font-body-sm text-body-sm hover:bg-surface-container-low"
                  >
                    <span className="font-semibold">{m.name}</span> · {m.employee_number} · {m.department}
                  </button>
                ))}
              </div>
            )}
          </div>
          {employee && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
              <label className="flex flex-col gap-1">
                <span className={fieldLabelClass}>Medicine for</span>
                <select className={fieldClass} value={dependantId} onChange={(e) => setDependantId(e.target.value)}>
                  <option value="">{employee.name} (the employee)</option>
                  {employee.dependants
                    .filter((d) => d.active)
                    .map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.relationship})
                      </option>
                    ))}
                </select>
              </label>
              <div className="flex flex-col justify-end font-body-sm text-body-sm text-on-surface-variant">
                <span data-testid="employee-remaining">
                  Left this policy year: <strong className="text-on-surface">{formatEtb(employee.usage.remaining_santim)}</strong> of{" "}
                  {formatEtb(employee.policy.annual_limit_santim)} · co-pay {employee.policy.copay_percent}%
                </span>
                {!employee.active && <span className="text-error">This employee is not active: the claim cannot be approved.</span>}
              </div>
            </div>
          )}
        </section>

        <section className="bg-surface-container-lowest rounded-xl border border-surface-container p-space-md grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
          <h2 className="sm:col-span-2 font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">Pharmacy receipt</h2>
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Pharmacy name</span>
            <input className={fieldClass} required minLength={2} maxLength={160} value={pharmacyName} onChange={(e) => setPharmacyName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Pharmacy TIN</span>
            <input className={fieldClass} required inputMode="numeric" placeholder="10 digits" value={pharmacyTin} onChange={(e) => setPharmacyTin(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Receipt number</span>
            <input className={fieldClass} required maxLength={40} value={receiptNumber} onChange={(e) => setReceiptNumber(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Receipt date</span>
            <input className={fieldClass} required type="date" max={todayIso()} value={receiptDate} onChange={(e) => setReceiptDate(e.target.value)} />
          </label>
        </section>

        <section className="bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-space-sm">
          <h2 className="font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">Medicines</h2>
          {lines.map((line, index) => (
            <div key={line.key} className="grid grid-cols-12 gap-space-sm items-end" data-testid="item-row">
              <label className="col-span-12 sm:col-span-6 flex flex-col gap-1">
                <span className={fieldLabelClass}>Medicine {index + 1}</span>
                <input className={fieldClass} value={line.medicine} onChange={(e) => setLine(line.key, { medicine: e.target.value })} />
              </label>
              <label className="col-span-4 sm:col-span-2 flex flex-col gap-1">
                <span className={fieldLabelClass}>Quantity {index + 1}</span>
                <input className={fieldClass} inputMode="numeric" value={line.quantity} onChange={(e) => setLine(line.key, { quantity: e.target.value })} />
              </label>
              <label className="col-span-5 sm:col-span-2 flex flex-col gap-1">
                <span className={fieldLabelClass}>Unit price (ETB) {index + 1}</span>
                <input className={fieldClass} inputMode="decimal" placeholder="0.00" value={line.price} onChange={(e) => setLine(line.key, { price: e.target.value })} />
              </label>
              <div className="col-span-3 sm:col-span-2 flex items-center justify-end gap-1 h-10">
                <span className="font-numeric-currency text-body-md font-semibold text-on-surface">
                  {totals[index] !== null ? formatEtb(totals[index], false) : "—"}
                </span>
                {lines.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Remove medicine ${index + 1}`}
                    className="p-1 rounded-lg text-on-surface-variant hover:bg-surface-container-high"
                    onClick={() => setLines((all) => all.filter((l) => l.key !== line.key))}
                  >
                    <Icon aria-hidden="true" name="close" size={18} />
                  </button>
                )}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between pt-space-sm border-t border-surface-container">
            <button
              type="button"
              className="font-label-md text-label-md text-primary font-semibold hover:underline"
              onClick={() => setLines((all) => (all.length < 50 ? [...all, emptyLine()] : all))}
            >
              + Add medicine
            </button>
            <span className="font-label-md text-label-md font-semibold text-on-surface">
              Receipt total: <span data-testid="claim-total" className="font-numeric-currency">{total !== null ? formatEtb(total) : "—"}</span>
            </span>
          </div>
        </section>

        <section className="bg-surface-container-lowest rounded-xl border border-surface-container p-space-md flex flex-col gap-space-sm">
          <h2 className="font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">Receipt photo or scan</h2>
          <label className="flex flex-col gap-1">
            <span className={fieldLabelClass}>Receipt file (PDF, JPEG, PNG or WebP, at most 10 MB)</span>
            <input
              type="file"
              accept={RECEIPT_TYPES.join(",")}
              onChange={(e) => void onFile(e.target.files?.[0])}
              className="font-body-sm text-body-sm text-on-surface"
            />
          </label>
          {uploading && <span className="font-body-sm text-body-sm text-on-surface-variant">Uploading…</span>}
          {receipt && (
            <span data-testid="receipt-uploaded" className="font-body-sm text-body-sm text-on-surface">
              <Icon aria-hidden="true" name="check_circle" className="text-tertiary align-middle" size={16} /> {receipt.filename} attached
            </span>
          )}
        </section>

        <ErrorBanner message={error} testId="form-error" />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={busy || uploading || !employee || !receipt || !complete}
            className="h-11 px-6 rounded-lg bg-primary hover:bg-secondary text-on-primary font-label-lg text-label-lg font-bold flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Icon aria-hidden="true" name="save" size={18} />
            {busy ? "Saving…" : "Save claim"}
          </button>
        </div>
      </form>
    </div>
  );
}
