"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { hardNavigate } from "@/lib/navigation";
import type { Application } from "@/lib/application";
import type { Me } from "@/lib/types";
import ApplyFrame from "@/components/apply/ApplyFrame";
import { signOut } from "@/components/apply/ApplyWizard";
import { FormError, linkButton, primaryButton } from "@/components/auth/AuthCard";

const NEXT_STEPS = [
  { icon: "fact_check", text: "Endod checks your company details and documents." },
  { icon: "verified", text: "Once approved, you sign in to the full portal: add your employees and set the benefit policy." },
  { icon: "receipt_long", text: "Then you enter your employees' medication claims and pay them back." },
];

function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Addis_Ababa" });
}

/**
 * What the admins of a company that is not approved see (besides the
 * application itself): the application is with Endod, or Endod's reason for
 * sending it back with a way to fix and resubmit it. Nothing else of the
 * portal is open to them (the API answers 403 to everything else).
 */
export default function UnderReview() {
  const [application, setApplication] = useState<Application | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const me = await apiFetch<Me>("auth/me");
        if (me.stage !== "full") return hardNavigate("/login");
        if (!me.organisation.application_status || me.organisation.application_status === "approved") return hardNavigate("/");
        const loaded = await apiFetch<Application>("application");
        if (loaded.status === "approved") return hardNavigate("/");
        if (loaded.status === "draft") return hardNavigate("/apply");
        if (alive) setApplication(loaded);
      } catch (e) {
        if (alive && !(e instanceof ApiError && e.status === 401)) {
          setError(e instanceof ApiError ? e.message : "Something went wrong.");
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const footer = (
    <p className="mt-space-md text-center font-body-sm text-body-sm text-on-surface-variant">
      Endod will contact you about your application.{" "}
      <button type="button" onClick={() => void signOut()} className={linkButton}>
        Sign out
      </button>
    </p>
  );

  if (!application) {
    return (
      <ApplyFrame title="Your application" footer={footer}>
        {error ? (
          <FormError message={error} />
        ) : (
          <p role="status" className="font-body-sm text-body-sm text-on-surface-variant">
            Loading…
          </p>
        )}
      </ApplyFrame>
    );
  }

  const rejected = application.status === "rejected";
  return (
    <ApplyFrame
      title={rejected ? "Changes needed" : "Under review"}
      subtitle={application.organisation_name}
      footer={footer}
    >
      <div data-testid="under-review" data-status={application.status} className="space-y-space-md">
        {rejected ? (
          <div data-testid="rejection-reason" className="rounded-xl bg-amber-50 p-space-md font-body-sm text-body-sm text-amber-900">
            <p className="font-semibold">Endod sent your application back</p>
            <p className="mt-1">{application.rejection_reason}</p>
            <a href="/apply?fix=1" className={`${primaryButton} mt-3 inline-flex items-center justify-center`}>
              Edit and resubmit
            </a>
          </div>
        ) : (
          <p className="font-body-md text-body-md text-on-surface">
            Thank you. Your application was submitted on {formatDate(application.submitted_at)} and is with Endod for
            review. Until it is approved, this is the only page of the portal you can use.
          </p>
        )}
        <section>
          <p className="mb-2 font-label-md text-label-md uppercase tracking-wider text-on-surface-variant font-semibold">What happens next</p>
          <ol className="space-y-2">
            {NEXT_STEPS.map((item) => (
              <li key={item.icon} className="flex items-start gap-3 font-body-sm text-body-sm text-on-surface-variant">
                <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-primary">
                  {item.icon}
                </span>
                <span>{item.text}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </ApplyFrame>
  );
}
