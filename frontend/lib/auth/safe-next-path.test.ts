import { describe, expect, it } from "vitest";

import { safeNextPath } from "./safe-next-path";

describe("safeNextPath", () => {
  it("defaults to /dashboard when input is null", () => {
    expect(safeNextPath(null)).toBe("/dashboard");
  });

  it("defaults to /dashboard when input is empty string", () => {
    expect(safeNextPath("")).toBe("/dashboard");
  });

  it("preserves a relative path with no query", () => {
    expect(safeNextPath("/goals")).toBe("/goals");
  });

  it("preserves a relative path with query string", () => {
    expect(safeNextPath("/calendar?date=2026-01-01")).toBe("/calendar?date=2026-01-01");
  });

  it("rejects an absolute http URL (open-redirect attempt)", () => {
    expect(safeNextPath("https://evil.com")).toBe("/dashboard");
  });

  it("rejects a protocol-relative URL (//evil.com)", () => {
    // Browsers resolve "//evil.com" against the current scheme, so it would
    // navigate cross-origin even though it doesn't start with http://.
    expect(safeNextPath("//evil.com")).toBe("/dashboard");
  });

  it("rejects a path that doesn't start with /", () => {
    expect(safeNextPath("dashboard")).toBe("/dashboard");
  });
});
