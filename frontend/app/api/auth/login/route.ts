import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { SESSION_COOKIE_NAME, sessionCookieOptions } from "@/lib/auth/cookie";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type LoginPayload = { email?: unknown; password?: unknown };

export async function POST(request: Request): Promise<NextResponse> {
  let body: LoginPayload;
  try {
    body = (await request.json()) as LoginPayload;
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  const { email, password } = body;
  if (typeof email !== "string" || typeof password !== "string") {
    return NextResponse.json(
      { detail: "Email and password are required" },
      { status: 400 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${FASTAPI_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Upstream unreachable" }, { status: 502 });
  }

  if (!upstream.ok) {
    let detail: unknown = "Authentication failed";
    try {
      const json = (await upstream.json()) as { detail?: unknown };
      detail = json?.detail ?? detail;
    } catch {
      // FastAPI returned a non-JSON error body — fall back to default message.
    }
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const { access_token } = (await upstream.json()) as { access_token: string };

  (await cookies()).set(SESSION_COOKIE_NAME, access_token, sessionCookieOptions());

  return NextResponse.json({ ok: true });
}
