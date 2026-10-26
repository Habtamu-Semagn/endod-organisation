"use client";

import { createContext, Suspense, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import Dialog from "@/components/Dialog";
import { ApiError, apiFetch, goToLogin } from "@/lib/api";
import { hardNavigate } from "@/lib/navigation";
import type { Me, Overview } from "@/lib/types";

type PortalContextValue = {
  me: Me;
  /** Pending claims (the sidebar badge). */
  pendingCount: number | null;
  refreshCounts: () => void;
  /**
   * Runs an approve / reject / mark-paid / policy call. If the API asks for a
   * fresh TOTP first, prompts for one, then runs the call again.
   */
  runSensitive: <T>(call: () => Promise<T>) => Promise<T>;
};

const PortalContext = createContext<PortalContextValue | null>(null);

export function usePortal(): PortalContextValue {
  const value = useContext(PortalContext);
  if (!value) throw new Error("usePortal outside PortalShell");
  return value;
}

export class Cancelled extends Error {
  constructor() {
    super("Cancelled.");
  }
}

type Pending = { resolve: () => void; reject: (error: Error) => void };

export default function PortalShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [reauthOpen, setReauthOpen] = useState(false);
  const [code, setCode] = useState("");
  const [reauthError, setReauthError] = useState<string | null>(null);
  const [reauthBusy, setReauthBusy] = useState(false);
  const pending = useRef<Pending | null>(null);

  useEffect(() => {
    let alive = true;
    apiFetch<Me>("auth/me")
      .then((value) => {
        if (!alive) return;
        if (value.stage !== "full") goToLogin();
        // A company still applying sees only its application (the API refuses the rest).
        else if (value.organisation.application_status && value.organisation.application_status !== "approved") hardNavigate("/apply");
        else setMe(value);
      })
      .catch((error: unknown) => {
        if (alive && error instanceof ApiError && error.status !== 401) setLoadError(error.message);
      });
    return () => {
      alive = false;
    };
  }, []);

  const refreshCounts = useCallback(() => {
    apiFetch<Overview>("overview")
      .then((value) => setPendingCount(value.pending_claims))
      .catch(() => setPendingCount(null));
  }, []);

  useEffect(() => {
    if (me) refreshCounts();
  }, [me, refreshCounts]);

  const askForCode = useCallback(
    () =>
      new Promise<void>((resolve, reject) => {
        pending.current = { resolve, reject };
        setCode("");
        setReauthError(null);
        setReauthOpen(true);
      }),
    []
  );

  const runSensitive = useCallback(
    async <T,>(call: () => Promise<T>): Promise<T> => {
      try {
        return await call();
      } catch (error) {
        if (error instanceof ApiError && error.code === "REAUTH_REQUIRED") {
          await askForCode();
          return await call();
        }
        throw error;
      }
    },
    [askForCode]
  );

  const cancelReauth = useCallback(() => {
    setReauthOpen(false);
    pending.current?.reject(new Cancelled());
    pending.current = null;
  }, []);

  const confirmReauth = async () => {
    setReauthBusy(true);
    setReauthError(null);
    try {
      await apiFetch("auth/reauth", { method: "POST", body: { code } });
      setReauthOpen(false);
      pending.current?.resolve();
      pending.current = null;
    } catch (error) {
      setReauthError(error instanceof ApiError ? error.message : "Could not check the code.");
      setCode("");
    } finally {
      setReauthBusy(false);
    }
  };

  const signOut = async () => {
    try {
      await apiFetch("auth/logout", { method: "POST", redirectOn401: false });
    } catch {
      // Signed out on this side either way: the cookie is cleared by the BFF.
    }
    hardNavigate("/login");
  };

  return (
    <>
      <Suspense fallback={null}>
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} pendingCount={pendingCount} />
      </Suspense>
      <Suspense fallback={null}>
        <Header onMenuClick={() => setSidebarOpen(true)} me={me} onSignOut={signOut} />
      </Suspense>
      <div className="pl-0 lg:pl-64 flex flex-col min-h-screen">
        <main className="relative pt-16 w-full px-space-md sm:px-space-xl bg-surface flex-1">
          {me ? (
            <PortalContext.Provider value={{ me, pendingCount, refreshCounts, runSensitive }}>{children}</PortalContext.Provider>
          ) : loadError ? (
            <p role="alert" className="mt-space-lg rounded-xl bg-error-container p-space-md font-body-sm text-body-sm text-on-error-container">
              {loadError}
            </p>
          ) : (
            <p className="mt-space-lg font-body-sm text-body-sm text-on-surface-variant">Loading…</p>
          )}
        </main>
      </div>
      {reauthOpen && (
        <Dialog
          testId="reauth-dialog"
          title="Confirm it is you"
          description="Enter the 6-digit code from your authenticator app. It stays valid for 10 minutes of approvals and changes."
          confirmLabel="Confirm"
          busy={reauthBusy}
          confirmDisabled={code.replace(/\s/g, "").length !== 6}
          error={reauthError}
          onConfirm={confirmReauth}
          onCancel={cancelReauth}
        >
          <label className="block font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold" htmlFor="reauth-code">
            Authenticator code
          </label>
          <input
            id="reauth-code"
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, "").slice(0, 7))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && code.replace(/\s/g, "").length === 6) void confirmReauth();
            }}
            inputMode="numeric"
            autoComplete="one-time-code"
            className="mt-1 w-full h-10 px-3 rounded-lg bg-surface-container-low font-mono tracking-[0.3em] text-on-surface focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="123456"
          />
        </Dialog>
      )}
    </>
  );
}
