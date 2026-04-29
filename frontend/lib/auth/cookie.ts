import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";

export const SESSION_COOKIE_NAME = "session";

// Backend JWT lifetime (matches backend/app/core/security.py default of 60 min).
// If we exceed this, the cookie will outlive the JWT and we'll bounce to /login
// the first time the user tries to call the API after expiry — no real harm,
// but worse UX than aligning the two values.
export const JWT_MAX_AGE_SECONDS = 60 * 60;

/**
 * Builds the option object passed to `cookies().set("session", token, ...)`.
 */
export function sessionCookieOptions(): Partial<ResponseCookie> {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: JWT_MAX_AGE_SECONDS,
  };
}
