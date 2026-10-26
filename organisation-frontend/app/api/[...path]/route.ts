import { NextResponse, type NextRequest } from "next/server";
import {
  backendHeaders,
  callBackend,
  clearSessionCookie,
  errorResponse,
  isRecord,
  rejectCrossSite,
  sessionToken,
  setSessionCookie,
} from "@/lib/server/backend";

/**
 * The portal API, passed through with the session from the cookie. Only the
 * paths and methods below are reachable. Answers that open a session carry
 * `session_token`: it goes into the httpOnly cookie and is removed from the
 * body, so page scripts never see a token. Receipt files and CSV exports
 * have their own routes (app/api/receipts, app/api/export), and so do a
 * company's application documents (app/api/application/documents).
 *
 * Nothing under `platform/` is ever passed on: that API is Endod's super
 * admin's (over endod-bus, with its own key), never the browser's.
 */
type Rule = { pattern: RegExp; methods: string[]; signedOut?: boolean; maxBody?: number };

const ID = "[0-9a-f]{32}";
const SMALL = 20_000;
const RULES: Rule[] = [
  { pattern: /^auth\/login$/, methods: ["POST"], signedOut: true },
  { pattern: /^auth\/setup(\/check)?$/, methods: ["POST"], signedOut: true },
  { pattern: /^auth\/(totp|enroll\/start|enroll\/confirm|reauth)$/, methods: ["POST"] },
  { pattern: /^auth\/me$/, methods: ["GET"] },
  { pattern: /^overview$/, methods: ["GET"] },
  { pattern: /^employees$/, methods: ["GET", "POST"] },
  { pattern: /^employees\/import\/(preview|commit)$/, methods: ["POST"], maxBody: 1_100_000 },
  { pattern: new RegExp(`^employees/${ID}$`), methods: ["GET", "PATCH"] },
  { pattern: new RegExp(`^employees/${ID}/(deactivate|activate|dependants)$`), methods: ["POST"] },
  { pattern: new RegExp(`^employees/${ID}/dependants/${ID}/remove$`), methods: ["POST"] },
  { pattern: new RegExp(`^employees/${ID}/policy$`), methods: ["PUT", "DELETE"] },
  { pattern: /^policy$/, methods: ["GET", "PUT"] },
  { pattern: /^organisation$/, methods: ["GET"] },
  { pattern: /^organisation\/payout$/, methods: ["PUT"] },
  { pattern: /^claims$/, methods: ["GET", "POST"], maxBody: 100_000 },
  { pattern: new RegExp(`^claims/${ID}$`), methods: ["GET"] },
  { pattern: new RegExp(`^claims/${ID}/(approve|reject)$`), methods: ["POST"] },
  { pattern: /^batches$/, methods: ["GET", "POST"], maxBody: 100_000 },
  { pattern: new RegExp(`^batches/${ID}$`), methods: ["GET"] },
  { pattern: new RegExp(`^batches/${ID}/(mark-paid|cancel)$`), methods: ["POST"] },
  { pattern: /^reports$/, methods: ["GET"] },
  // A company's own application (docs/company-onboarding.md): the account is
  // made signed out; the rest needs the applicant's session.
  { pattern: /^application\/start$/, methods: ["POST"], signedOut: true },
  { pattern: /^application$/, methods: ["GET"] },
  { pattern: /^application\/(contact|company)$/, methods: ["PUT"] },
  { pattern: /^application\/submit$/, methods: ["POST"] },
];

const WITH_BODY = new Set(["POST", "PUT", "PATCH"]);

async function handle(request: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  const rule = RULES.find((r) => r.pattern.test(joined));
  if (!rule) return errorResponse(404, "Not found.");
  if (!rule.methods.includes(request.method)) return errorResponse(405, "Method not allowed.");
  const refused = rejectCrossSite(request);
  if (refused) return refused;
  const token = sessionToken(request);
  if (!token && !rule.signedOut) return errorResponse(401, "Authentication required.", "AUTH_REQUIRED");

  const upstream = backendHeaders(request, rule.signedOut ? undefined : token);
  if (upstream.error) return upstream.error;
  const headers = upstream.headers;
  let body: string | undefined;
  if (WITH_BODY.has(request.method)) {
    body = (await request.text()) || "{}";
    if (body.length > (rule.maxBody ?? SMALL)) return errorResponse(413, "Request too large.");
    headers.set("Content-Type", "application/json");
  }
  if (token && (joined === "auth/login" || joined === "auth/setup" || joined === "application/start")) {
    // A new sign-in replaces whatever session this browser had: end the old one.
    const old = backendHeaders(request, token);
    if (old.headers) await callBackend("auth/logout", { method: "POST", headers: old.headers });
  }
  const search = request.method === "GET" ? request.nextUrl.search : "";
  const result = await callBackend(`${joined}${search}`, { method: request.method, headers, body });

  let payload = result.body;
  let opened: { token: string; maxAge: number } | null = null;
  if (isRecord(payload) && typeof payload.session_token === "string") {
    const { session_token: newToken, session_max_age: maxAge, ...rest } = payload;
    opened = { token: newToken as string, maxAge: typeof maxAge === "number" ? maxAge : 900 };
    payload = rest;
  }
  const response =
    result.status === 204 ? new NextResponse(null, { status: 204 }) : NextResponse.json(payload, { status: result.status });
  response.headers.set("Cache-Control", "no-store");
  if (opened) {
    setSessionCookie(response, opened.token, opened.maxAge);
  } else if (result.status === 401 && !rule.signedOut) {
    // The session ended (expired, revoked, locked): forget it.
    clearSessionCookie(response);
  }
  return response;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
