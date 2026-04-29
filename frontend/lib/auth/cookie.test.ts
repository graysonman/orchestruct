import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { JWT_MAX_AGE_SECONDS, sessionCookieOptions } from "./cookie";

describe("sessionCookieOptions", () => {
  const originalEnv = process.env.NODE_ENV;

  afterEach(() => {
    (process.env as Record<string, string | undefined>).NODE_ENV = originalEnv;
  });

  it("returns httpOnly: true so JS cannot read the JWT", () => {
    expect(sessionCookieOptions().httpOnly).toBe(true);
  });

  it("uses sameSite: lax so OAuth callbacks ride the cookie back", () => {
    expect(sessionCookieOptions().sameSite).toBe("lax");
  });

  it("scopes the cookie to the whole site (path: /)", () => {
    expect(sessionCookieOptions().path).toBe("/");
  });

  it("aligns maxAge with the backend JWT lifetime", () => {
    expect(sessionCookieOptions().maxAge).toBe(JWT_MAX_AGE_SECONDS);
  });

  describe("secure flag", () => {
    beforeEach(() => {
      // jsdom defaults NODE_ENV to "test", so each block sets it explicitly.
    });

    it("is false outside production (so dev over http://localhost works)", () => {
      (process.env as Record<string, string | undefined>).NODE_ENV = "development";
      expect(sessionCookieOptions().secure).toBe(false);
    });

    it("is true in production", () => {
      (process.env as Record<string, string | undefined>).NODE_ENV = "production";
      expect(sessionCookieOptions().secure).toBe(true);
    });
  });
});
