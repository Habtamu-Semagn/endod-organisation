import type { ReactNode } from "react";
import { STEPS } from "@/lib/application";

/**
 * The frame of a company's application and its Under review page, in the
 * sign-in pages' design (components/auth/AuthCard), wider, with the steps.
 */
export default function ApplyFrame({
  title,
  subtitle,
  step,
  footer,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  /** The current step's index in STEPS; none on the Under review page. */
  step?: number;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full items-start justify-center bg-surface-container-low px-space-md py-space-2xl">
      <div className="w-full max-w-2xl">
        <div className="mb-space-lg flex items-center justify-center gap-space-sm">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="Endod Health" className="h-8 w-auto object-contain" src="/endod_logo.jpeg" />
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm text-primary tracking-tight">Endod Health</span>
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">TenaCare for employers</span>
          </div>
        </div>
        {step !== undefined && (
          <ol data-testid="apply-steps" className="mb-space-md grid grid-cols-4 gap-2">
            {STEPS.map((s, index) => (
              <li
                key={s.key}
                aria-current={index === step ? "step" : undefined}
                className={`rounded-lg px-2 py-2 text-center font-label-sm text-label-sm font-semibold ${
                  index === step
                    ? "bg-primary text-on-primary"
                    : index < step
                      ? "bg-primary-container text-on-primary-container"
                      : "bg-surface-container-lowest text-on-surface-variant"
                }`}
              >
                <span className="mr-1">{index + 1}.</span>
                {s.label}
              </li>
            ))}
          </ol>
        )}
        <div className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <h1 className="font-headline-md text-headline-md text-on-surface font-semibold">{title}</h1>
          {subtitle && <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">{subtitle}</p>}
          <div className="mt-space-lg">{children}</div>
        </div>
        {footer}
        <p className="mt-space-md text-center font-body-sm text-body-sm text-outline">
          organisation.endod-health.com · reviewed by Endod before the portal opens
        </p>
      </div>
    </div>
  );
}
