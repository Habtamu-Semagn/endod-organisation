import type { ReactNode } from "react";

/** The frame of the sign-in, setup and enrolment pages, in the portal's design. */
export default function AuthCard({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-surface-container-low px-space-md py-space-2xl">
      <div className="w-full max-w-md">
        <div className="mb-space-lg flex items-center justify-center gap-space-sm">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="Endod Health" className="h-8 w-auto object-contain" src="/endod_logo.jpeg" />
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm text-primary tracking-tight">Endod Health</span>
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">TenaCare for employers</span>
          </div>
        </div>
        <div className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <h1 className="font-headline-md text-headline-md text-on-surface font-semibold">{title}</h1>
          {subtitle && <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">{subtitle}</p>}
          <div className="mt-space-lg">{children}</div>
        </div>
        <p className="mt-space-md text-center font-body-sm text-body-sm text-outline">
          organisation.endod-health.com · authorised HR and benefits staff only
        </p>
      </div>
    </div>
  );
}

export const inputClass =
  "mt-1 w-full h-10 px-3 rounded-lg bg-surface-container-low font-body-md text-body-md text-on-surface placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-2 focus:ring-primary";
export const labelClass = "block font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold";
export const primaryButton =
  "w-full h-10 px-4 rounded-lg bg-primary text-on-primary font-label-lg text-label-lg font-semibold hover:bg-secondary transition-colors disabled:cursor-not-allowed disabled:opacity-50";
export const linkButton = "font-label-md text-label-md font-semibold text-primary hover:underline";

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" data-testid="form-error" className="rounded-lg bg-error-container px-3 py-2 font-body-sm text-body-sm font-medium text-on-error-container">
      {message}
    </p>
  );
}
