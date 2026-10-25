import { NextResponse, type NextRequest } from "next/server";
import {
  backendHeaders,
  backendUrl,
  errorResponse,
  rejectForeignOrigin,
  relayError,
  sessionToken,
} from "@/lib/server/backend";

/**
 * Upload a receipt: the file is the request body, streamed to the portal API
 * (which checks its first bytes and its size). Only from this site's pages;
 * only the declared types; at most 10 MB.
 */
const TYPES = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp", "application/octet-stream"]);
const MAX_BYTES = 10 * 1024 * 1024;

export async function POST(request: NextRequest) {
  const foreign = rejectForeignOrigin(request);
  if (foreign) return foreign;
  const type = (request.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (!TYPES.has(type)) return errorResponse(415, "Only PDF, JPEG, PNG or WebP files can be attached.", "FILE_TYPE");
  const length = request.headers.get("content-length");
  if (length && (!/^\d+$/.test(length) || Number(length) > MAX_BYTES)) {
    return errorResponse(413, "A receipt can be at most 10 MB.", "FILE_TOO_LARGE");
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
    upstream = await fetch(backendUrl("receipts"), {
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
  if (!upstream.ok) return relayError(upstream, "The receipt could not be uploaded.");
  const response = NextResponse.json(await upstream.json(), { status: upstream.status });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
