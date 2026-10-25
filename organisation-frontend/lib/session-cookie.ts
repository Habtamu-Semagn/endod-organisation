/**
 * The session cookie's name, shared by the BFF and proxy.ts (kept free of
 * server-only imports so the proxy bundle stays small).
 *
 * Secure cookies use the `__Host-` prefix: the browser then insists on
 * Secure, Path=/ and no Domain, so no other host can set or shadow it.
 */
export function secureCookies(): boolean {
  const override = process.env.SESSION_COOKIE_SECURE;
  if (override === "true") return true;
  if (override === "false") return false;
  return process.env.NODE_ENV === "production";
}

export function sessionCookieName(): string {
  return secureCookies() ? "__Host-tenacare_org" : "tenacare_org";
}
