import { NextResponse, type NextRequest } from "next/server";
import {
  backendHeaders,
  backendUrl,
  errorResponse,
  rejectCrossSiteRead,
  rejectForeignOrigin,
  relayError,
  sessionToken,
} from "@/lib/server/backend";

/**
 * A company's application documents (docs/company-onboarding.md), as the
 * receipts are handled (app/api/receipts): POST streams the file to the API
 * (which checks its first bytes and size; only from this site's pages, only
 * the declared types, at most 10 MB); GET shows the organisation's own
 * document (the API takes the organisation from the session), never cached
 * or sniffed, with a policy that stops it from running anything here.
 */
const KINDS = new Set(["trade_license", "tin_certificate", "authorization_letter"]);
const UPLOAD_TYPES = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp", "application/octet-stream"]);
const VIEW_TYPES = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);
const MAX_BYTES = 10 * 1024 * 1024;

export async function POST(request: NextRequest, ctx: RouteContext<"/api/application/documents/[kind]">) {
  const { kind } = await ctx.params;
  if (!KINDS.has(kind)) return errorResponse(404, "Not found.");
  const foreign = rejectForeignOrigin(request);
  if (foreign) return foreign;
  const type = (request.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (!UPLOAD_TYPES.has(type)) return errorResponse(415, "Only PDF, JPEG, PNG or WebP files can be attached.", "FILE_TYPE");
  const length = request.headers.get("content-length");
  if (length && (!/^\d+$/.test(length) || Number(length) > MAX_BYTES)) {
    return errorResponse(413, "A document can be at most 10 MB.", "FILE_TOO_LARGE");
  }
  const token = sessionToken(request);
  if (!token) return errorResponse(401, "Authentication required.", "AUTH_REQUIRED");
  if (!request.body) return errorResponse(400, "The file is empty.", "FILE_REJECTED");

  const prepared = backendHeaders(request, token);
  if (prepared.error) return prepared.error;
  const headers = prepared.headers;
  headers.set("Content-Type", "application/octet-stream");
  const filename = (request.headers.get("x-filename") ?? "").slice(0, 600);
  if (filename) headers.set("X-Filename", filename);

  let upstream: Response;
  try {
    upstream = await fetch(backendUrl(`application/documents/${kind}`), {
      method: "POST",
      headers,
      body: request.body,
      cache: "no-store",
      redirect: "manual",
      // Node's fetch streams a request body only in half-duplex mode.
      duplex: "half",
    } as RequestInit & { duplex: "half" });
  } catch {
    return errorResponse(502, "The TenaCare service is not reachable. Try again shortly.", "API_UNAVAILABLE");
  }
  if (!upstream.ok) return relayError(upstream, "The document could not be uploaded.");
  const response = NextResponse.json(await upstream.json(), { status: upstream.status });
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function GET(request: NextRequest, ctx: RouteContext<"/api/application/documents/[kind]">) {
  const { kind } = await ctx.params;
  if (!KINDS.has(kind)) return errorResponse(404, "Not found.");
  const refused = rejectCrossSiteRead(request);
  if (refused) return refused;
  const token = sessionToken(request);
  if (!token) return errorResponse(401, "Authentication required.", "AUTH_REQUIRED");

  const prepared = backendHeaders(request, token);
  if (prepared.error) return prepared.error;
  const headers = prepared.headers;
  headers.set("Accept", "*/*");
  let upstream: Response;
  try {
    upstream = await fetch(backendUrl(`application/documents/${kind}`), { headers, cache: "no-store", redirect: "manual" });
  } catch {
    return errorResponse(502, "The TenaCare service is not reachable. Try again shortly.", "API_UNAVAILABLE");
  }
  if (!upstream.ok) return relayError(upstream, "The document could not be opened.");
  const type = (upstream.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (!VIEW_TYPES.has(type) || !upstream.body) {
    await upstream.body?.cancel();
    return errorResponse(502, "Unexpected file from the TenaCare service.", "API_INVALID");
  }
  const response = new NextResponse(upstream.body, { status: 200 });
  response.headers.set("Content-Type", type);
  const length = upstream.headers.get("content-length");
  if (length && /^\d+$/.test(length)) response.headers.set("Content-Length", length);
  const disposition = upstream.headers.get("content-disposition") ?? "";
  const safe = /^inline; filename="[^"\\\r\n]{1,160}"; filename\*=UTF-8''[A-Za-z0-9%._~-]+$/.test(disposition)
    ? disposition
    : 'inline; filename="document"';
  response.headers.set("Content-Disposition", safe);
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Cross-Origin-Resource-Policy", "same-origin");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set(
    "Content-Security-Policy",
    type === "application/pdf"
      ? "frame-ancestors 'self'"
      : "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'self'"
  );
  return response;
}
