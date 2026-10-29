"use client";

import { useState } from "react";

/** A value with a copy button (a secret is shown in amber: it is shown only once). */
export default function CopyField({
  label,
  value,
  testId,
  secret = false,
}: {
  label: string;
  value: string;
  testId: string;
  secret?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-1">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">{label}</span>
      <div className="flex items-center gap-2">
        <code
          data-testid={testId}
          className={`min-w-0 flex-1 break-all rounded-lg px-3 py-2 font-mono text-xs ${
            secret ? "bg-amber-50 text-amber-900 ring-1 ring-amber-200" : "bg-surface-container-low text-on-surface"
          }`}
        >
          {value}
        </code>
        <button
          type="button"
          aria-label={`Copy ${label}`}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 2000);
            } catch {
              setCopied(false);
            }
          }}
          className="shrink-0 px-3 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-md text-label-md hover:bg-surface-variant transition-colors"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
