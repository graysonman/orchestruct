import { describe, expect, it } from "vitest";

import {
  canApprove,
  canReject,
  isTerminal,
  planStatusHint,
  planStatusLabel,
} from "./plan-status";

describe("planStatusLabel", () => {
  it("labels a known status", () => {
    expect(planStatusLabel("proposed")).toBe("Proposed");
  });

  it("falls back to the raw string for an unknown status", () => {
    // The column is an unconstrained String(50), so this is reachable.
    expect(planStatusLabel("archived_2019")).toBe("archived_2019");
  });
});

describe("canApprove", () => {
  it("allows approving a proposed plan", () => {
    expect(canApprove("proposed")).toBe(true);
  });

  it.each(["draft", "approved", "committed", "invalidated", "unknown"])(
    "refuses to approve from %s",
    (status) => {
      expect(canApprove(status)).toBe(false);
    },
  );
});

describe("canReject", () => {
  it("allows rejecting a proposed plan", () => {
    expect(canReject("proposed")).toBe(true);
  });

  it("allows rejecting an approved plan, which is how an approval is undone", () => {
    expect(canReject("approved")).toBe(true);
  });

  it.each(["draft", "committed", "invalidated", "unknown"])(
    "refuses to reject from %s",
    (status) => {
      expect(canReject(status)).toBe(false);
    },
  );
});

describe("isTerminal", () => {
  it("treats invalidated as terminal", () => {
    expect(isTerminal("invalidated")).toBe(true);
  });

  it("treats an unrecognized status as terminal, offering no action", () => {
    expect(isTerminal("something_new")).toBe(true);
  });

  it("does not treat proposed or approved as terminal", () => {
    expect(isTerminal("proposed")).toBe(false);
    expect(isTerminal("approved")).toBe(false);
  });

  it("never reports a status as both terminal and actionable", () => {
    for (const status of ["draft", "proposed", "approved", "committed", "invalidated"]) {
      const actionable = canApprove(status) || canReject(status);
      expect(isTerminal(status)).toBe(!actionable);
    }
  });
});

describe("planStatusHint", () => {
  it("explains what a proposed plan is waiting on", () => {
    expect(planStatusHint("proposed")).toContain("Approve");
  });

  it("returns null for an unknown status rather than inventing one", () => {
    expect(planStatusHint("mystery")).toBeNull();
  });
});
