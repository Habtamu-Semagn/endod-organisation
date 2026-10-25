import { NextResponse, type NextRequest } from "next/server";
import { sessionCookieName } from "@/lib/session-cookie";

// Pages open without a session: the sign-in steps and the setup link.
const PUBLIC_PAGES = new Set(["/login", "/setup", "/enroll"]);

/**
 * An optimistic check only: signed-out visitors are sent to /login before a
 * portal page renders. The portal API still checks the session (and its
 * stage and organisation) on every call, and the BFF drops a cookie the API
 * no longer accepts.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PAGES.has(pathname)) return NextResponse.next();
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
  // Pages only: not the BFF (it answers 401 itself), Next's assets or public files.
  matcher: ["/((?!api/|_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
