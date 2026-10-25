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
 * A receipt (PDF or image), streamed from the portal API, which serves only
 * the signed-in admin's organisation's files and audits every view. Only
 * these types; never cached, never sniffed, and with a policy that stops a
 * file from running anything on this origin. `?download=1` saves it.
 */
const TYPES = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);

export async function GET(request: NextRequest, ctx: RouteContext<"/api/receipts/[id]">) {
  const { id } = await ctx.params;
  if (!/^[0-9a-f]{32}$/.test(id)) return errorResponse(404, "Not found.");
  const refused = rejectCrossSiteRead(request);
  if (refused) return refused;
  const token = sessionToken(request);
  if (!token) return errorResponse(401, "Authentication required.", "AUTH_REQUIRED");

  const wantsDownload = request.nextUrl.searchParams.get("download") === "1";
  const prepared = backendHeaders(request, token);
  if (prepared.error) return prepared.error;
  const headers = prepared.headers;
  headers.set("Accept", "*/*");
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl(`receipts/${id}${wantsDownload ? "?download=true" : ""}`), {
      headers,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return errorResponse(502, "The TenaCare service is not reachable. Try again shortly.", "API_UNAVAILABLE");
  }
  if (!upstream.ok) return relayError(upstream, "The receipt could not be opened.");
  const type = (upstream.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (!TYPES.has(type) || !upstream.body) {
    await upstream.body?.cancel();
    return errorResponse(502, "Unexpected file from the TenaCare service.", "API_INVALID");
  }
  const response = new NextResponse(upstream.body, { status: 200 });
  response.headers.set("Content-Type", type);
  const length = upstream.headers.get("content-length");
  if (length && /^\d+$/.test(length)) response.headers.set("Content-Length", length);
  const disposition = upstream.headers.get("content-disposition") ?? "";
  const safe = /^(inline|attachment); filename="[^"\\\r\n]{1,160}"; filename\*=UTF-8''[A-Za-z0-9%._~-]+$/.test(disposition)
    ? disposition
    : `${wantsDownload ? "attachment" : "inline"}; filename="receipt"`;
  response.headers.set(
    "Content-Disposition",
    wantsDownload ? safe.replace(/^inline/, "attachment") : safe.replace(/^attachment/, "inline")
  );
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Cross-Origin-Resource-Policy", "same-origin");
  response.headers.set("Referrer-Policy", "no-referrer");
  // Images: nothing but the image. PDFs: the browser's viewer is a plugin
  // that `default-src 'none'` would block, so only the framing rule; the type
  // allowlist and nosniff keep anything else (HTML, SVG) from rendering.
  response.headers.set(
    "Content-Security-Policy",
    type === "application/pdf"
      ? "frame-ancestors 'self'"
      : "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'self'"
  );
  return response;
}
