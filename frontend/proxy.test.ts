import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { SESSION_COOKIE_NAME } from "@/lib/auth/cookie";
import { proxy } from "./proxy";

function makeRequest(path: string, opts: { withCookie?: boolean } = {}): NextRequest {
  const url = new URL(path, "http://localhost:3000");
  const headers = new Headers();
  if (opts.withCookie) {
    headers.set("cookie", `${SESSION_COOKIE_NAME}=fake-jwt-token`);
  }
  return new NextRequest(url, { headers });
}

describe("proxy (auth gate)", () => {
  it("lets the request through when the session cookie is present", () => {
    const response = proxy(makeRequest("/dashboard", { withCookie: true }));
    // NextResponse.next() returns a response with no Location header.
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects to /login when no session cookie is present", () => {
    const response = proxy(makeRequest("/dashboard"));
    const location = response.headers.get("location");
    expect(location).not.toBeNull();
    const redirectUrl = new URL(location!);
    expect(redirectUrl.pathname).toBe("/login");
  });

  it("attaches the original path as the `next` query param", () => {
    const response = proxy(makeRequest("/dashboard"));
    const redirectUrl = new URL(response.headers.get("location")!);
    expect(redirectUrl.searchParams.get("next")).toBe("/dashboard");
  });

  it("preserves query strings on the original path through `next`", () => {
    const response = proxy(makeRequest("/calendar?date=2026-01-01&view=week"));
    const redirectUrl = new URL(response.headers.get("location")!);
    expect(redirectUrl.searchParams.get("next")).toBe("/calendar?date=2026-01-01&view=week");
  });

  it("does not redirect when already on /login (loop guard)", () => {
    const response = proxy(makeRequest("/login"));
    expect(response.headers.get("location")).toBeNull();
  });
});
