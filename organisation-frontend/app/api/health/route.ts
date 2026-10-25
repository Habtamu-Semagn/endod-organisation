import { NextResponse } from "next/server";

/** The container's health check (Dockerfile): nothing but "ok". */
export function GET() {
  return NextResponse.json({ status: "ok" }, { headers: { "Cache-Control": "no-store" } });
}
