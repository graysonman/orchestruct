import { describe, expect, it } from "vitest";

import type { WorkLog } from "@/lib/api/worklogs";

import {
  estimateRatio,
  estimateVerdict,
  formatMinutes,
  groupLogsByDay,
  loggedMinutes,
} from "./worklog-view";

function makeLog(overrides: Partial<WorkLog> = {}): WorkLog {
  return {
    id: "w1",
    task_id: "t1",
    user_id: "u1",
    started_at: "2026-08-18T09:00:00+00:00",
    ended_at: "2026-08-18T10:00:00+00:00",
    completed: true,
    notes: null,
    created_at: "2026-08-18T10:00:00+00:00",
    updated_at: "2026-08-18T10:00:00+00:00",
    task: { id: "t1", goal_id: "g1", title: "Draft the API layer", estimated_minutes: 60 },
    ...overrides,
  };
}

describe("loggedMinutes", () => {
  it("measures a completed log", () => {
    expect(loggedMinutes(makeLog())).toBe(60);
  });

  it("returns null for a log that never ended", () => {
    expect(loggedMinutes(makeLog({ ended_at: null }))).toBeNull();
  });

  it("returns null when the end precedes the start", () => {
    expect(
      loggedMinutes(
        makeLog({
          started_at: "2026-08-18T10:00:00+00:00",
          ended_at: "2026-08-18T09:00:00+00:00",
        }),
      ),
    ).toBeNull();
  });

  it("measures across a timezone offset correctly", () => {
    // Same instant expressed in two zones — the duration is one hour either way.
    expect(
      loggedMinutes(
        makeLog({
          started_at: "2026-08-18T09:00:00+02:00",
          ended_at: "2026-08-18T08:00:00+01:00",
        }),
      ),
    ).toBeNull();
    expect(
      loggedMinutes(
        makeLog({
          started_at: "2026-08-18T09:00:00+02:00",
          ended_at: "2026-08-18T09:00:00+01:00",
        }),
      ),
    ).toBe(60);
  });
});

describe("formatMinutes", () => {
  it("renders sub-hour durations in minutes", () => {
    expect(formatMinutes(45)).toBe("45m");
  });

  it("renders whole hours without stray minutes", () => {
    expect(formatMinutes(120)).toBe("2h");
  });

  it("renders mixed durations", () => {
    expect(formatMinutes(95)).toBe("1h 35m");
  });
});

describe("estimateRatio", () => {
  it("is 1 when the work matched its estimate", () => {
    expect(estimateRatio(makeLog())).toBe(1);
  });

  it("is above 1 when the work ran long", () => {
    expect(
      estimateRatio(makeLog({ ended_at: "2026-08-18T11:00:00+00:00" })),
    ).toBe(2);
  });

  it("returns null when the task carries no estimate", () => {
    expect(
      estimateRatio(
        makeLog({
          task: { id: "t1", goal_id: "g1", title: "x", estimated_minutes: null },
        }),
      ),
    ).toBeNull();
  });

  it("returns null for an unfinished log", () => {
    expect(estimateRatio(makeLog({ ended_at: null }))).toBeNull();
  });
});

describe("estimateVerdict", () => {
  it("says nothing when the log is within the deadband", () => {
    // 63 minutes against a 60-minute estimate is 5% over — noise, not signal.
    expect(
      estimateVerdict(makeLog({ ended_at: "2026-08-18T10:03:00+00:00" })),
    ).toBeNull();
  });

  it("reports overrun as a percentage", () => {
    expect(estimateVerdict(makeLog({ ended_at: "2026-08-18T10:30:00+00:00" }))).toBe(
      "50% over estimate",
    );
  });

  it("reports finishing early", () => {
    expect(estimateVerdict(makeLog({ ended_at: "2026-08-18T09:30:00+00:00" }))).toBe(
      "50% under estimate",
    );
  });
});

describe("groupLogsByDay", () => {
  it("groups logs sharing a day", () => {
    const days = groupLogsByDay([
      makeLog({ id: "a", started_at: "2026-08-18T09:00:00Z", ended_at: "2026-08-18T10:00:00Z" }),
      makeLog({ id: "b", started_at: "2026-08-18T14:00:00Z", ended_at: "2026-08-18T15:00:00Z" }),
    ]);
    expect(days).toHaveLength(1);
    expect(days[0].logs).toHaveLength(2);
    expect(days[0].totalMinutes).toBe(120);
  });

  it("keeps the server's newest-first ordering", () => {
    const days = groupLogsByDay([
      makeLog({ id: "newer", started_at: "2026-08-19T09:00:00Z", ended_at: "2026-08-19T10:00:00Z" }),
      makeLog({ id: "older", started_at: "2026-08-18T09:00:00Z", ended_at: "2026-08-18T10:00:00Z" }),
    ]);
    expect(days.map((d) => d.logs[0].id)).toEqual(["newer", "older"]);
  });

  it("counts an unfinished log as zero minutes rather than NaN", () => {
    const days = groupLogsByDay([makeLog({ ended_at: null })]);
    expect(days[0].totalMinutes).toBe(0);
  });

  it("returns an empty list for no logs", () => {
    expect(groupLogsByDay([])).toEqual([]);
  });
});
