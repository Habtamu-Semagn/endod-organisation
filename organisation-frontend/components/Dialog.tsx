"use client";

import { useEffect, useRef, type ReactNode } from "react";

interface DialogProps {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  tone?: "primary" | "danger";
  busy?: boolean;
  confirmDisabled?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  testId?: string;
  wide?: boolean;
}

/** A modal in the portal's style: a card over a dimmed page. */
export default function Dialog({
  title,
  description,
  children,
  confirmLabel,
  tone = "primary",
  busy = false,
  confirmDisabled = false,
  error,
  onConfirm,
  onCancel,
  testId,
  wide = false,
}: DialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  useEffect(() => {
    if (!children) cancelRef.current?.focus();
  }, [children]);

  const confirmClass =
    tone === "danger" ? "bg-error text-on-error hover:opacity-90" : "bg-primary text-on-primary hover:bg-secondary";

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-inverse-surface/40 p-4" data-testid={testId}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-y-auto rounded-xl bg-surface-container-lowest p-space-lg shadow-lg flex flex-col gap-space-md`}
      >
        <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">{title}</h2>
        {description && <div className="font-body-md text-body-md text-on-surface-variant">{description}</div>}
        {children && <div>{children}</div>}
        {error && (
          <p role="alert" data-testid="dialog-error" className="rounded-lg bg-error-container px-3 py-2 font-body-sm text-body-sm font-medium text-on-error-container">
            {error}
          </p>
        )}
        <div className="flex items-center justify-end gap-space-md pt-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-4 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md hover:bg-surface-variant transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
            className={`px-5 py-2 rounded-lg font-label-lg text-label-lg font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${confirmClass}`}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export const fieldClass =
  "h-10 w-full px-3 rounded-lg bg-surface text-on-surface font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary";
export const fieldLabelClass = "font-label-sm text-label-sm text-on-surface-variant";
