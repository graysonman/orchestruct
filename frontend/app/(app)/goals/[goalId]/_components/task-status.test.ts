import { describe, expect, it } from "vitest";

import {
  isSchedulable,
  nextStatus,
  SCHEDULABLE_STATUS,
  statusLabel,
  TASK_STATUSES,
} from "./task-status";

describe("statusLabel", () => {
  it("maps known statuses to their label", () => {
    expect(statusLabel("in_progress")).toBe("In progress");
    expect(statusLabel("pending")).toBe("Pending");
  });

  it("falls back to the raw value for unknown statuses", () => {
    // The column is an unconstrained String(50), so this is reachable.
    expect(statusLabel("deferred")).toBe("deferred");
  });
});

describe("isSchedulable", () => {
  it("is true only for the status plan generation filters on", () => {
    // plan_service.py:41 filters `Task.status == "pending"`.
    expect(SCHEDULABLE_STATUS).toBe("pending");
    expect(isSchedulable("pending")).toBe(true);
  });

  it.each([["in_progress"], ["completed"], ["blocked"], ["deferred"]])(
    "is false for %s",
    (status) => {
      expect(isSchedulable(status)).toBe(false);
    },
  );
});

describe("nextStatus", () => {
  it("advances pending to in_progress", () => {
    expect(nextStatus("pending")).toBe("in_progress");
  });

  it("advances in_progress to completed", () => {
    expect(nextStatus("in_progress")).toBe("completed");
  });

  it("unblocks back to pending, restoring schedulability", () => {
    expect(nextStatus("blocked")).toBe("pending");
    expect(isSchedulable(nextStatus("blocked")!)).toBe(true);
  });

  it("treats completed as terminal", () => {
    expect(nextStatus("completed")).toBeNull();
  });

  it("returns null for an unrecognized status rather than guessing", () => {
    expect(nextStatus("deferred")).toBeNull();
    expect(nextStatus("")).toBeNull();
  });

  it("reaches completed from every non-terminal status", () => {
    // Walks the graph to prove there are no cycles or dead ends short of
    // "completed" — a bad transition would loop until the guard trips.
    for (const start of ["pending", "in_progress", "blocked"]) {
      let status = start;
      let hops = 0;
      while (status !== "completed" && hops < 10) {
        const next = nextStatus(status);
        expect(next).not.toBeNull();
        status = next!;
        hops += 1;
      }
      expect(status).toBe("completed");
    }
  });

  it("only ever returns statuses in the vocabulary", () => {
    for (const { value } of TASK_STATUSES) {
      const next = nextStatus(value);
      if (next !== null) {
        expect(TASK_STATUSES.some((s) => s.value === next)).toBe(true);
      }
    }
  });
});

describe("TASK_STATUSES", () => {
  it("includes the schedulable status", () => {
    expect(TASK_STATUSES.some((s) => s.value === SCHEDULABLE_STATUS)).toBe(true);
  });

  it("has unique values", () => {
    const values = TASK_STATUSES.map((s) => s.value);
    expect(new Set(values).size).toBe(values.length);
  });
});
