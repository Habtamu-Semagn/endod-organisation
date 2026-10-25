"use client";

import { hardNavigate } from "@/lib/navigation";

/** An error answer from the portal API (`{"error": "...", "error_code": "..."}`). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function messageOf(body: unknown, status: number): { message: string; code?: string } {
  if (typeof body === "object" && body !== null) {
    const record = body as Record<string, unknown>;
    if (typeof record.error === "string") {
      return { message: record.error, code: typeof record.error_code === "string" ? record.error_code : undefined };
    }
  }
  return { message: status >= 500 ? "Something went wrong. Try again." : `Request failed (${status}).` };
}

/** The portal's own pages (where a `next` after sign-in may lead). */
const PORTAL_PATH = /^\/(claims|employees|payments|reports|settings)?(\/[A-Za-z0-9/_?=&%.-]*)?$/;

/** Where the browser goes when the session is gone or half-finished. */
export function goToLogin() {
  const here = `${window.location.pathname}${window.location.search}`;
  const next = here !== "/" && PORTAL_PATH.test(here) ? `?next=${encodeURIComponent(here)}` : "";
  hardNavigate(`/login${next}`);
}

async function parse(response: Response, redirectOn401: boolean | undefined): Promise<unknown> {
  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }
  if (!response.ok) {
    const { message, code } = messageOf(parsed, response.status);
    const sessionGone = response.status === 401 || (response.status === 403 && code === "SESSION_INCOMPLETE");
    if (sessionGone && redirectOn401 !== false) goToLogin();
    throw new ApiError(message, response.status, code);
  }
  return parsed;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * Calls this site's own `/api/...` (the BFF). The session cookie goes with it
 * automatically; this code never sees the token.
 */
export async function apiFetch<T>(
  path: string,
  init: { method?: Method; body?: unknown; redirectOn401?: boolean } = {}
): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: string | undefined;
  if (method === "POST" || method === "PUT" || method === "PATCH") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body ?? {});
  }
  let response: Response;
  try {
    response = await fetch(`/api/${path.replace(/^\/+/, "")}`, {
      method,
      headers,
      body,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Cannot reach TenaCare. Check your connection.", 0, "NETWORK");
  }
  return (await parse(response, init.redirectOn401)) as T;
}

export type UploadedReceipt = { id: string; filename: string; content_type: string; size: number };

export const RECEIPT_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"];
export const MAX_RECEIPT_BYTES = 10 * 1024 * 1024;

/** Sends a receipt file as the request body (the API checks its content). */
export async function uploadReceipt(file: File): Promise<UploadedReceipt> {
  if (file.size > MAX_RECEIPT_BYTES) throw new ApiError("A receipt can be at most 10 MB.", 413, "FILE_TOO_LARGE");
  const type = RECEIPT_TYPES.includes(file.type) ? file.type : "application/octet-stream";
  let response: Response;
  try {
    response = await fetch("/api/receipts", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": type, "X-Filename": encodeURIComponent(file.name) },
      body: file,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Cannot reach TenaCare. Check your connection.", 0, "NETWORK");
  }
  return (await parse(response, true)) as UploadedReceipt;
}

/** A `next` path from the query string, only if it is one of this site's pages. */
export function safeNext(value: string | null): string {
  if (value && PORTAL_PATH.test(value) && !value.startsWith("//")) return value;
  return "/";
}
