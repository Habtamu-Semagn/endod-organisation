import "server-only";
import { isIP } from "node:net";
import { NextResponse, type NextRequest } from "next/server";
import { secureCookies, sessionCookieName } from "@/lib/session-cookie";

/**
 * The portal's server side (BFF) talks to the organisation API. The browser only
 * ever talks to `/api/*` on this origin; the session token lives in an
 * httpOnly, Secure, SameSite=Strict cookie that page scripts cannot read.
 * The API trusts only this server (X-BFF-Secret) to name the visitor's
 * address (X-Endod-Client-IP, from our nginx).
 */

const DEFAULT_API_URL = "http://127.0.0.1:8040";

export function backendUrl(path: string): string {
  const base = (process.env.ORG_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  return `${base}/${path.replace(/^\/+/, "")}`;
}

export function sessionToken(request: NextRequest): string | undefined {
  return request.cookies.get(sessionCookieName())?.value || undefined;
}

export function setSessionCookie(response: NextResponse, token: string, maxAgeSeconds: number) {
  response.cookies.set({
    name: sessionCookieName(),
    value: token,
    httpOnly: true,
    secure: secureCookies(),
    sameSite: "strict",
    path: "/",
    // The backend enforces the idle timeout and the absolute limit; the
    // cookie only never outlives the session.
    maxAge: Math.max(60, Math.floor(maxAgeSeconds)),
  });
}

export function clearSessionCookie(response: NextResponse) {
  response.cookies.set({
    name: sessionCookieName(),
    value: "",
    httpOnly: true,
    secure: secureCookies(),
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
}

export function errorResponse(status: number, error: string, errorCode = `HTTP_${status}`) {
  const response = NextResponse.json({ error, error_code: errorCode }, { status });
  response.headers.set("Cache-Control", "no-store");
  return response;
}

/** This site's origin: SITE_ORIGIN when set (production), else the Host the request came to. */
function expectedOrigin(request: NextRequest): string | null {
  const configured = process.env.SITE_ORIGIN?.replace(/\/+$/, "");
  if (configured) return configured;
  const host = request.headers.get("host");
  if (!host) return null;
  return `${request.nextUrl.protocol}//${host}`;
}

/**
 * Changes must come from this site's own pages:
 * - an Origin header naming this site (browsers send it on every POST/DELETE);
 * - Sec-Fetch-Site, when sent, must say same-origin;
 * - a JSON body (an HTML form cannot send one without a CORS preflight).
 * SameSite=Strict on the session cookie is the other half of the defence.
 */
export function rejectCrossSite(request: NextRequest): NextResponse | null {
  if (request.method === "GET" || request.method === "HEAD") return null;
  const foreign = rejectForeignOrigin(request);
  if (foreign) return foreign;
  const type = (request.headers.get("content-type") ?? "").toLowerCase();
  const hasBody = request.method !== "DELETE" && request.headers.get("content-length") !== "0";
  if (hasBody && !type.startsWith("application/json")) {
    return errorResponse(415, "Send JSON.", "UNSUPPORTED_MEDIA_TYPE");
  }
  return null;
}

/** The Origin and Sec-Fetch-Site checks alone (uploads send a file, not JSON). */
export function rejectForeignOrigin(request: NextRequest): NextResponse | null {
  const origin = request.headers.get("origin");
  const expected = expectedOrigin(request);
  if (!origin || !expected || origin !== expected) {
    return errorResponse(403, "Cross-site request refused.", "CSRF");
  }
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin") {
    return errorResponse(403, "Cross-site request refused.", "CSRF");
  }
  return null;
}

/** A GET of a file or export: from a page or tab of this site, or the address typed in; never another site. */
export function rejectCrossSiteRead(request: NextRequest): NextResponse | null {
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
    return errorResponse(403, "Cross-site request refused.", "CSRF");
  }
  return null;
}

/** Development only: the organisation API's default too (backend/app/config.py). */
const DEV_BFF_SECRET = "dev-only-bff-secret-change-me-0123456789abcd";

/** Production is the public https site; there nothing may fall back to a default. */
function isProduction(): boolean {
  return (process.env.SITE_ORIGIN ?? "").startsWith("https://");
}

function bffSecret(): string | null {
  const secret = process.env.BFF_SHARED_SECRET ?? "";
  if (secret.length >= 32) return secret;
  return isProduction() || secret ? null : DEV_BFF_SECRET;
}

/**
 * The visitor's address: only X-Endod-Client-IP, which our nginx always sets
 * (Cloudflare's CF-Connecting-IP when the connection comes from Cloudflare,
 * else the TCP peer) and overwrites if a client sent one. X-Forwarded-For is
 * ignored. Without a valid one the site is not set up right: in production
 * that is an error, in development the address is the local machine.
 */
function clientIp(request: NextRequest): string | null {
  const value = (request.headers.get("x-endod-client-ip") ?? "").trim();
  if (value && isIP(value)) return value;
  return isProduction() ? null : "127.0.0.1";
}

export type Upstream = { headers: Headers; error?: undefined } | { headers?: undefined; error: NextResponse };

/**
 * Headers for a call to the organisation API: the shared secret (the API refuses
 * anything without it), the visitor's address, the user agent and the session.
 * An error response (503) when this site is not configured for that.
 */
export function backendHeaders(request: NextRequest, token?: string): Upstream {
  const secret = bffSecret();
  const ip = clientIp(request);
  if (!secret || !ip) {
    return { error: errorResponse(503, "This site is not configured correctly. Contact Endod.", "NOT_CONFIGURED") };
  }
  const headers = new Headers({ Accept: "application/json", "X-BFF-Secret": secret, "X-Endod-Client-IP": ip });
  const userAgent = request.headers.get("user-agent");
  if (userAgent) headers.set("User-Agent", userAgent.slice(0, 300));
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return { headers };
}

export type BackendResult = { status: number; body: unknown };

export async function callBackend(
  path: string,
  init: { method: string; headers: Headers; body?: string }
): Promise<BackendResult> {
  let response: Response;
  try {
    response = await fetch(backendUrl(path), {
      method: init.method,
      headers: init.headers,
      body: init.body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return {
      status: 502,
      body: { error: "The TenaCare service is not reachable. Try again shortly.", error_code: "API_UNAVAILABLE" },
    };
  }
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { error: "Unexpected response from the TenaCare service.", error_code: "API_INVALID" };
    }
  }
  return { status: response.status, body };
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** An error answer of the API passed on as JSON (and the cookie dropped on 401). */
export async function relayError(upstream: Response, fallback: string): Promise<NextResponse> {
  let message = fallback;
  let code = `HTTP_${upstream.status}`;
  try {
    const body = (await upstream.json()) as { error?: unknown; error_code?: unknown };
    if (typeof body.error === "string") message = body.error;
    if (typeof body.error_code === "string") code = body.error_code;
  } catch {
    // Not JSON: keep the generic message.
  }
  const status = upstream.status >= 400 && upstream.status < 600 ? upstream.status : 502;
  const response = errorResponse(status, message, code);
  if (upstream.status === 401) clearSessionCookie(response);
  return response;
}
