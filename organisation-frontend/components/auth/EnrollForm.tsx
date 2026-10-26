"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import QRCode from "qrcode";
import { ApiError, apiFetch } from "@/lib/api";
import type { Me } from "@/lib/types";
import AuthCard, { FormError, inputClass, labelClass, primaryButton } from "@/components/auth/AuthCard";

type Start = { secret: string; otpauth_uri: string; issuer: string; account: string };

/**
 * Two-step verification is mandatory: at first sign-in (or after a setup
 * link) the admin adds TenaCare to an authenticator app, confirms a code,
 * and receives 10 one-time recovery codes, shown only here.
 */
export default function EnrollForm() {
  const router = useRouter();
  const [start, setStart] = useState<Start | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [saved, setSaved] = useState(false);
  // A company's applicant goes on with the application, not the portal.
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const me = await apiFetch<Me>("auth/me", { redirectOn401: false });
        if (me.stage === "full") return router.replace("/");
        if (me.stage === "totp") return router.replace("/login");
        setApplying(Boolean(me.organisation.application_status && me.organisation.application_status !== "approved"));
        const value = await apiFetch<Start>("auth/enroll/start", { method: "POST", redirectOn401: false });
        if (!alive) return;
        setStart(value);
        setQr(await QRCode.toDataURL(value.otpauth_uri, { errorCorrectionLevel: "M", margin: 1, width: 220 }));
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return router.replace("/login");
        if (alive) setFatal(e instanceof ApiError ? e.message : "Could not start the set-up.");
      }
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  const confirm = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<{ recovery_codes: string[] }>("auth/enroll/confirm", {
        method: "POST",
        body: { code },
        redirectOn401: false,
      });
      setCodes(result.recovery_codes);
      setStart(null);
      setQr(null);
    } catch (e) {
      setCode("");
      if (e instanceof ApiError && e.status === 401) {
        setFatal(e.message);
      } else {
        setError(e instanceof ApiError ? e.message : "Could not check the code.");
      }
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    const text = `TenaCare recovery codes\nEach code works once.\n\n${(codes ?? []).join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "tenacare-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  if (fatal) {
    return (
      <AuthCard title="Set up two-step verification">
        <div className="space-y-4">
          <FormError message={fatal} />
          <a href="/login" className="text-xs font-semibold text-primary hover:underline">Back to sign in</a>
        </div>
      </AuthCard>
    );
  }

  if (codes) {
    return (
      <AuthCard
        title="Save your recovery codes"
        subtitle="If you lose your phone, each of these codes signs you in once. They are shown only now: download or write them down and keep them safe."
      >
        <ol data-testid="recovery-codes" className="grid grid-cols-2 gap-2 rounded-xl bg-surface-container-low p-4 font-mono text-sm text-on-surface">
          {codes.map((value) => (
            <li key={value} data-testid="recovery-code">{value}</li>
          ))}
        </ol>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={download}
            className="px-3 py-1.5 rounded-full text-xs font-semibold bg-surface-container-high hover:bg-surface-container-highest text-on-surface"
          >
            Download .txt
          </button>
          <button
            type="button"
            onClick={() => void navigator.clipboard?.writeText(codes.join("\n"))}
            className="px-3 py-1.5 rounded-full text-xs font-semibold bg-surface-container-high hover:bg-surface-container-highest text-on-surface"
          >
            Copy
          </button>
        </div>
        <label className="mt-4 flex items-center gap-2 text-xs text-on-surface">
          <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} />
          I have saved my recovery codes
        </label>
        <button
          type="button"
          disabled={!saved}
          onClick={() => router.replace(applying ? "/apply" : "/")}
          className={`${primaryButton} mt-4`}
        >
          {applying ? "Continue to your application" : "Continue to the portal"}
        </button>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Set up two-step verification"
      subtitle={
        applying
          ? "Before your application continues, secure your account: scan this QR code with Google Authenticator (or any authenticator app), then enter the 6-digit code it shows."
          : "Scan this QR code with Google Authenticator (or any authenticator app), then enter the 6-digit code it shows."
      }
    >
      {!start ? (
        <p className="text-xs text-on-surface-variant">Preparing…</p>
      ) : (
        <form onSubmit={confirm} className="space-y-4">
          <div className="flex justify-center">
            {qr && (
              // A data: URL made in the browser: nothing is sent to an image service.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={qr} alt="QR code for TenaCare" width={220} height={220} data-testid="totp-qr" className="rounded-lg" />
            )}
          </div>
          <div className="rounded-lg bg-surface-container-low p-3">
            <p className={labelClass}>Or enter this key</p>
            <p data-testid="totp-secret" className="mt-1 break-all font-mono text-xs text-on-surface">
              {start.secret.replace(/(.{4})/g, "$1 ").trim()}
            </p>
            <p className="mt-1 text-[11px] text-on-surface-variant">
              Account {start.account} · issuer {start.issuer} · time-based, 6 digits
            </p>
          </div>
          <div>
            <label htmlFor="enroll-code" className={labelClass}>Code from the app</label>
            <input
              id="enroll-code"
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, "").slice(0, 7))}
              inputMode="numeric"
              autoComplete="one-time-code"
              className={`${inputClass} font-mono tracking-[0.3em]`}
              placeholder="123456"
            />
          </div>
          <FormError message={error} />
          <button type="submit" disabled={busy || code.replace(/\s/g, "").length !== 6} className={primaryButton}>
            {busy ? "Checking…" : "Confirm and continue"}
          </button>
        </form>
      )}
    </AuthCard>
  );
}
