import { NextResponse, type NextRequest } from "next/server";
import { sessionCookieName } from "@/lib/session-cookie";

// Pages open without a session: the sign-in steps, the setup link and a
// company's application (whose first step creates the account).
const PUBLIC_PAGES = new Set(["/login", "/setup", "/enroll", "/apply"]);

/**
 * Only our nginx may talk to this app. Other containers on the shared edge
 * network could otherwise reach it directly and choose X-Endod-Client-IP
 * (the address the API's sign-in limits count). nginx adds
 * X-Endod-Edge-Key: EDGE_SHARED_SECRET to every request it passes on;
 * anything without it is refused. The one exception is the container's own
 * health check (`/api/health` asked of 127.0.0.1 or ::1), which says nothing
 * but "ok". In production (an https SITE_ORIGIN) a missing or short secret
 * means the site is not set up: every request gets 503.
 */
const EDGE_HEADER = "x-endod-edge-key";
const LOCAL_HOSTS = new Set(["127.0.0.1", "[::1]", "localhost"]);

function sameSecret(given: string, expected: string): boolean {
  // Constant time for a given length (the length of the secret is not a secret).
  let difference = given.length ^ expected.length;
  for (let i = 0; i < expected.length; i += 1) {
    difference |= (given.charCodeAt(i) || 0) ^ expected.charCodeAt(i);
  }
  return difference === 0;
}

function plain(status: number, text: string) {
  return new NextResponse(text, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
}

function edgeCheck(request: NextRequest): NextResponse | null {
  const secret = process.env.EDGE_SHARED_SECRET ?? "";
  const production = (process.env.SITE_ORIGIN ?? "").startsWith("https://");
  if (production && secret.length < 32) return plain(503, "This site is not configured correctly. Contact Endod.");
  if (!secret) return null; // development and tests without nginx
  if (secret.length < 32) return plain(503, "This site is not configured correctly. Contact Endod.");
  const host = (request.headers.get("host") ?? "").replace(/:\d+$/, "");
  if (request.nextUrl.pathname === "/api/health" && LOCAL_HOSTS.has(host)) return null;
  if (!sameSecret(request.headers.get(EDGE_HEADER) ?? "", secret)) return plain(403, "Forbidden.");
  return null;
}

/**
 * Then, for pages, an optimistic session check only: signed-out visitors are
 * sent to /login before a portal page renders. The portal API still checks
 * the session (and its stage and organisation) on every call, and the BFF
 * drops a cookie the API no longer accepts.
 */
export function proxy(request: NextRequest) {
  const refused = edgeCheck(request);
  if (refused) return refused;
  const { pathname, search } = request.nextUrl;
  const isPage =
    !pathname.startsWith("/api/") &&
    !pathname.startsWith("/_next/") &&
    !/\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt|xml|json)$/.test(pathname);
  if (!isPage || PUBLIC_PAGES.has(pathname)) return NextResponse.next();
  const signedIn = Boolean(request.cookies.get(sessionCookieName())?.value);
  if (!signedIn) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    if (pathname !== "/") url.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Every request: pages, the BFF, Next's assets and public files.
  matcher: ["/:path*"],
};
