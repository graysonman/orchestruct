// Next.js 16 renamed `middleware.ts` to `proxy.ts`. Despite the name, this
// file is NOT the API forwarder at `app/api/proxy/[...path]/route.ts` — this
// runs before every matched request, the API forwarder runs as a Route Handler.
//
// Job: gate the protected `/(app)/*` route group. If the session cookie is
// missing, redirect to /login with a `next` query param so the user can be
// returned to where they were trying to go after a successful login.
//
// We do NOT validate the JWT here. The cookie's *presence* is the cheap check
// — the proxy at app/api/proxy/[...path]/route.ts will still reject expired or
// tampered tokens via the FastAPI 401 path.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE_NAME } from "@/lib/auth/cookie";

export function proxy(request: NextRequest): NextResponse {
  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);
  if (hasSession) {
    return NextResponse.next();
  }
  if (request.nextUrl.pathname === "/login"){
    return NextResponse.next()
  }
  const redirect_url = new URL("/login", request.nextUrl.origin)
  redirect_url.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search)
  return NextResponse.redirect(redirect_url);
}

export const config = {
  // Match the protected `(app)` route group plus the dashboard root.
  // Exclude:
  //   - /api/*           (Route Handlers handle their own auth via the cookie)
  //   - /_next/*         (framework internals)
  //   - /favicon.ico, public files
  //   - /login, /register (the auth pages themselves must be reachable when logged out)
  //
  // Listing the protected segments explicitly is clearer than negative lookaheads
  // and easier to extend as new protected sections are added.
  // No "/tasks" entry: the API mounts tasks at /goals/{goal_id}/tasks and has
  // no cross-goal listing, so a top-level page would have to fetch every goal
  // and then issue one request per goal. Tasks live under /goals/:id, which
  // "/goals/:path*" already covers.
  matcher: [
    "/dashboard/:path*",
    "/goals/:path*",
    "/plans/:path*",
    "/calendar/:path*",
    "/worklogs/:path*",
    "/nudges/:path*",
    "/teams/:path*",
    "/meetings/:path*",
    "/settings/:path*",
  ],
};
