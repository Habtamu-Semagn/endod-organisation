"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import type { ClaimStatus } from "@/lib/types";

const STATUS: Record<ClaimStatus, { label: string; badge: string; dot: string }> = {
  pending: { label: "Pending", badge: "bg-amber-100 text-amber-800", dot: "bg-amber-600" },
  approved: { label: "Approved", badge: "bg-emerald-50 text-emerald-800", dot: "bg-emerald-600" },
  paid: { label: "Paid", badge: "bg-blue-50 text-blue-800", dot: "bg-blue-600" },
  rejected: { label: "Rejected", badge: "bg-error-container text-on-error-container", dot: "bg-error" },
};

export function StatusBadge({ status, testId = "status-badge" }: { status: ClaimStatus; testId?: string }) {
  const style = STATUS[status];
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-label-sm text-label-sm font-semibold ${style.badge}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

export function KpiCard({ label, value, sub, testId }: { label: string; value: ReactNode; sub?: ReactNode; testId?: string }) {
  return (
    <div className="bg-surface-container-low p-space-lg rounded-xl flex flex-col justify-between relative overflow-hidden">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-semibold">{label}</span>
      <div data-testid={testId} className="font-display-lg text-display-lg text-on-surface tracking-tight mt-space-sm">
        {value}
      </div>
      {sub ? <span className="font-body-sm text-body-sm text-on-surface-variant mt-1">{sub}</span> : null}
    </div>
  );
}

export function ErrorBanner({ message, testId = "action-error" }: { message: string | null; testId?: string }) {
  if (!message) return null;
  return (
    <p role="alert" data-testid={testId} className="rounded-xl bg-error-container px-space-md py-space-sm font-body-sm text-body-sm font-medium text-on-error-container">
      {message}
    </p>
  );
}

export function SuccessBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="status" data-testid="success-banner" className="rounded-xl bg-tertiary-fixed px-space-md py-space-sm font-body-sm text-body-sm font-medium text-on-tertiary-fixed">
      {message}
    </p>
  );
}

export function NoticeBanner({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <div data-testid={testId} className="rounded-xl bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-900">
      {children}
    </div>
  );
}

export function EmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-space-xl px-space-md text-center font-body-md text-body-md text-on-surface-variant">
        {children}
      </td>
    </tr>
  );
}

/** Loads `path` from the BFF; `reload` fetches again. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;
    let alive = true;
    apiFetch<T>(path)
      .then((value) => {
        if (!alive) return;
        setData(value);
        setError(null);
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof ApiError ? e.message : "Could not load this page.");
      });
    return () => {
      alive = false;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, reload, setData };
}

export function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}
