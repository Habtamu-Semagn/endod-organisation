"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiFetch, safeNext } from "@/lib/api";
import type { Me, Stage } from "@/lib/types";
import AuthCard, { FormError, inputClass, labelClass, linkButton, primaryButton } from "@/components/auth/AuthCard";

type Step = "loading" | "password" | "code";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const [step, setStep] = useState<Step>("loading");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = (stage: Stage) => {
    if (stage === "full") router.replace(next);
    else if (stage === "enroll") router.replace("/enroll");
    else setStep("code");
  };

  // A reload half-way through (or a signed-in visit) carries on where it was.
  useEffect(() => {
    apiFetch<Me>("auth/me", { redirectOn401: false })
      .then((me) => (me.stage === "totp" ? setStep("code") : go(me.stage)))
      .catch(() => setStep("password"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<{ stage: Stage }>("auth/login", {
        method: "POST",
        body: { email, password },
        redirectOn401: false,
      });
      setPassword("");
      go(result.stage);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch("auth/totp", {
        method: "POST",
        body: useRecovery ? { recovery_code: code } : { code },
        redirectOn401: false,
      });
      router.replace(next);
    } catch (e) {
      setCode("");
      if (e instanceof ApiError && e.status === 401) {
        // Locked, or the half-finished sign-in expired: start again.
        setStep("password");
      }
      setError(e instanceof ApiError ? e.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  if (step === "loading") {
    return (
      <AuthCard title="Sign in">
        <p className="text-xs text-on-surface-variant">Loading…</p>
      </AuthCard>
    );
  }

  if (step === "code") {
    return (
      <AuthCard
        title="Two-step verification"
        subtitle={useRecovery ? "Enter one of your recovery codes. Each works once." : "Enter the 6-digit code from your authenticator app."}
      >
        <form onSubmit={submitCode} className="space-y-4">
          <div>
            <label htmlFor="code" className={labelClass}>
              {useRecovery ? "Recovery code" : "Authentication code"}
            </label>
            <input
              id="code"
              autoFocus
              value={code}
              onChange={(e) => setCode(useRecovery ? e.target.value.slice(0, 20) : e.target.value.replace(/[^\d ]/g, "").slice(0, 7))}
              inputMode={useRecovery ? "text" : "numeric"}
              autoComplete="one-time-code"
              className={`${inputClass} font-mono tracking-[0.2em]`}
              placeholder={useRecovery ? "xxxx-xxxx-xxxx" : "123456"}
            />
          </div>
          <FormError message={error} />
          <button type="submit" disabled={busy || !code.trim()} className={primaryButton}>
            {busy ? "Checking…" : "Verify"}
          </button>
          <div className="flex justify-between">
            <button
              type="button"
              className={linkButton}
              onClick={() => {
                setUseRecovery((v) => !v);
                setCode("");
                setError(null);
              }}
            >
              {useRecovery ? "Use the authenticator app" : "Use a recovery code"}
            </button>
            <button
              type="button"
              className={linkButton}
              onClick={async () => {
                await apiFetch("auth/logout", { method: "POST", redirectOn401: false }).catch(() => null);
                setStep("password");
                setError(null);
              }}
            >
              Start again
            </button>
          </div>
        </form>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Sign in" subtitle="TenaCare organisation portal. Two-step verification is required.">
      <form onSubmit={submitPassword} className="space-y-4">
        <div>
          <label htmlFor="email" className={labelClass}>Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="password" className={labelClass}>Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </div>
        <FormError message={error} />
        <button type="submit" disabled={busy} className={primaryButton}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthCard>
  );
}
