"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import AuthCard, { FormError, inputClass, labelClass, primaryButton } from "@/components/auth/AuthCard";

/** `set`: the link sets the password; `confirm`: the admin was created with one and enters it. */
type Invite = { email: string; name: string; expires_at: string; mode: "set" | "confirm" };

/**
 * The one-time setup link from `python -m app.cli create-admin (run by Endod)`:
 * /setup#<token>. The token is in the fragment, so it never reaches a server
 * log or a Referer; it is read once and removed from the address bar.
 */
export default function SetupForm() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);

  useEffect(() => {
    const value = window.location.hash.replace(/^#/, "");
    window.history.replaceState(null, "", "/setup");
    (async () => {
      if (!value) {
        setFatal("This setup link is incomplete. Open the full link you were given.");
        return;
      }
      setToken(value);
      try {
        setInvite(await apiFetch<Invite>("auth/setup/check", { method: "POST", body: { token: value }, redirectOn401: false }));
      } catch (e) {
        setFatal(e instanceof ApiError ? e.message : "This setup link cannot be checked now.");
      }
    })();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (invite?.mode !== "confirm" && password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiFetch("auth/setup", { method: "POST", body: { token, password }, redirectOn401: false });
      router.replace("/enroll");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not set the password.");
      setBusy(false);
    }
  };

  if (fatal) {
    return (
      <AuthCard title="Set up your account">
        <FormError message={fatal} />
      </AuthCard>
    );
  }
  if (!invite) {
    return (
      <AuthCard title="Set up your account">
        <p className="text-xs text-on-surface-variant">Checking the link…</p>
      </AuthCard>
    );
  }
  if (invite.mode === "confirm") {
    return (
      <AuthCard
        title="Set up your account"
        subtitle={
          <>
            Welcome, <strong data-testid="setup-name">{invite.name}</strong> ({invite.email}). Enter the password you were
            given; next you will set up two-step verification with an authenticator app.
          </>
        }
      >
        <form onSubmit={submit} className="space-y-4">
          <input type="email" autoComplete="username" value={invite.email} readOnly hidden />
          <div>
            <label htmlFor="current-password" className={labelClass}>Your password</label>
            <input
              id="current-password"
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
            {busy ? "Checking…" : "Continue"}
          </button>
        </form>
      </AuthCard>
    );
  }
  return (
    <AuthCard
      title="Set up your account"
      subtitle={
        <>
          Welcome, <strong data-testid="setup-name">{invite.name}</strong> ({invite.email}). Choose a password; next you will set
          up two-step verification with an authenticator app.
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <input type="email" autoComplete="username" value={invite.email} readOnly hidden />
        <div>
          <label htmlFor="new-password" className={labelClass}>New password</label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-[11px] text-outline">At least 8 characters. A long phrase is best; common passwords are refused.</p>
        </div>
        <div>
          <label htmlFor="confirm-password" className={labelClass}>Repeat the password</label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputClass}
          />
        </div>
        <FormError message={error} />
        <button type="submit" disabled={busy} className={primaryButton}>
          {busy ? "Saving…" : "Set password and continue"}
        </button>
      </form>
    </AuthCard>
  );
}
