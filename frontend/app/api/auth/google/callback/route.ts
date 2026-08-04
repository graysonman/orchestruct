import { cookies } from "next/headers";
import { type NextRequest, NextResponse } from "next/server";

import { SESSION_COOKIE_NAME, sessionCookieOptions } from "@/lib/auth/cookie";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const params = request.nextUrl.searchParams;
  const code = params.get("code");
  const state = params.get("state") ?? "";

  // TODO(human): Add input validation BEFORE the fetch below.
  //
  // Three failure modes can land the browser here:
  //
  //   1. The user clicked "Cancel" on Google's consent screen. Google then
  //      redirects to <callback>?error=access_denied&error_description=...&state=...
  //      No `code` is present. This is a normal, expected, user-driven case.
  //
  //   2. Google redirected us with `?error=<something_else>` — invalid scope,
  //      misconfigured redirect URI, etc. Also no `code`.
  //
  //   3. `code` is just plain missing for an unknown reason (someone navigated
  //      directly to /api/auth/google/callback, a misconfiguration somewhere).
  //
  // The rest of this handler assumes `code` is a non-empty string. Decide
  // what to do for each case above and return a NextResponse.redirect to
  // /login with a query param that the login page can render a message from.
  //
  // Build absolute URLs with `new URL("/login?error=...", request.url)`.
  // The redirect status should be 302.

  let upstream: Response;
  try {
    const qs = new URLSearchParams({ code: code as string, state }).toString();
    upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/google/callback?${qs}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=google_unreachable", request.url),
      302,
    );
  }

  if (!upstream.ok) {
    return NextResponse.redirect(
      new URL("/login?error=google_rejected", request.url),
      302,
    );
  }

  const { access_token } = (await upstream.json()) as { access_token: string };

  (await cookies()).set(SESSION_COOKIE_NAME, access_token, sessionCookieOptions());

  return NextResponse.redirect(new URL("/dashboard", request.url), 302);
}
