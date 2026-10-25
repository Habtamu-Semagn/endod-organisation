import { NextResponse, type NextRequest } from "next/server";
import {
  backendHeaders,
  backendUrl,
  errorResponse,
  rejectCrossSiteRead,
  relayError,
  sessionToken,
} from "@/lib/server/backend";

/**
 * CSV downloads (the roster, a batch's payout file, the reports), passed
 * through from the portal API as attachments. Only these paths and query
 * parameters; the API makes every cell safe to open in a spreadsheet.
 */
const ID = "[0-9a-f]{32}";
const EXPORTS: { pattern: RegExp; params: string[] }[] = [
  { pattern: /^employees\/export$/, params: [] },
  { pattern: new RegExp(`^batches/${ID}/export$`), params: [] },
  { pattern: /^reports\/export$/, params: ["kind", "from", "to"] },
];

export async function GET(request: NextRequest, ctx: RouteContext<"/api/export/[...path]">) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  const rule = EXPORTS.find((e) => e.pattern.test(joined));
  if (!rule) return errorResponse(404, "Not found.");
  const refused = rejectCrossSiteRead(request);
  if (refused) return refused;
  const token = sessionToken(request);
  if (!token) return errorResponse(401, "Authentication required.", "AUTH_REQUIRED");

  const query = new URLSearchParams();
  for (const name of rule.params) {
    const value = request.nextUrl.searchParams.get(name);
    if (value && /^[A-Za-z0-9-]{1,20}$/.test(value)) query.set(name, value);
  }
  const prepared = backendHeaders(request, token);
  if (prepared.error) return prepared.error;
  const headers = prepared.headers;
  headers.set("Accept", "text/csv");
  let upstream: Response;
  try {
    const search = query.toString();
    upstream = await fetch(backendUrl(`${joined}${search ? `?${search}` : ""}`), {
      headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return errorResponse(502, "The TenaCare service is not reachable. Try again shortly.", "API_UNAVAILABLE");
  }
  if (!upstream.ok) return relayError(upstream, "The export could not be made.");
  const type = (upstream.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (type !== "text/csv" || !upstream.body) {
    await upstream.body?.cancel();
    return errorResponse(502, "Unexpected answer from the TenaCare service.", "API_INVALID");
  }
  const disposition = upstream.headers.get("content-disposition") ?? "";
  const response = new NextResponse(upstream.body, { status: 200 });
  response.headers.set("Content-Type", "text/csv; charset=utf-8");
  response.headers.set(
    "Content-Disposition",
    /^attachment; filename="[A-Za-z0-9._-]{1,80}"$/.test(disposition) ? disposition : 'attachment; filename="export.csv"'
  );
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Cross-Origin-Resource-Policy", "same-origin");
  return response;
}
