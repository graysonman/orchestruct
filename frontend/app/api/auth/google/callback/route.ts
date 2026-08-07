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

  // Google redirects here with `?error=...` (and no `code`) when the user
  // declines consent or the OAuth app is misconfigured. This endpoint is
  // publicly reachable, so `error` is attacker-controlled: never interpolate
  // it into a URL. Map known values to fixed codes and discard the rest.
  const oauthError = params.get("error");
  if (oauthError) {
    const reason =
      oauthError === "access_denied" ? "google_denied" : "google_failed";
    return NextResponse.redirect(
      new URL(`/login?error=${reason}`, request.url),
      302,
    );
  }

  // No code and no error: direct navigation, or a redirect_uri mismatch.
  if (!code) {
    return NextResponse.redirect(
      new URL("/login?error=google_no_code", request.url),
      302,
    );
  }

  let upstream: Response;
  try {
    const qs = new URLSearchParams({ code, state }).toString();
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
