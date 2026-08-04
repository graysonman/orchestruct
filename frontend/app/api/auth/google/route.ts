import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request): Promise<NextResponse> {
  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/google`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=google_unreachable", request.url),
      302,
    );
  }

  if (upstream.status === 501) {
    let detail: unknown = "Google OAuth is not configured on this server";
    try {
      const json = (await upstream.json()) as { detail?: unknown };
      detail = json?.detail ?? detail;
    } catch {
      // Non-JSON body — keep the default detail.
    }
    return NextResponse.json({ detail }, { status: 501 });
  }

  if (!upstream.ok) {
    return NextResponse.redirect(
      new URL("/login?error=google", request.url),
      302,
    );
  }

  const { authorization_url } = (await upstream.json()) as {
    authorization_url: string;
  };

  return NextResponse.redirect(authorization_url, 302);
}
