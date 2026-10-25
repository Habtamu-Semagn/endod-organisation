import { NextResponse, type NextRequest } from "next/server";
import {
  callBackend,
  clearSessionCookie,
  backendHeaders,
  rejectCrossSite,
  sessionToken,
} from "@/lib/server/backend";

/** Sign out: end the session on the organisation API and drop the cookie either way. */
export async function POST(request: NextRequest) {
  const refused = rejectCrossSite(request);
  if (refused) return refused;
  const token = sessionToken(request);
  if (token) {
    const upstream = backendHeaders(request, token);
    if (upstream.headers) await callBackend("auth/logout", { method: "POST", headers: upstream.headers });
  }
  const response = NextResponse.json({ ok: true });
  response.headers.set("Cache-Control", "no-store");
  clearSessionCookie(response);
  return response;
}
