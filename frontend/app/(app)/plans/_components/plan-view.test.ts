import { describe, expect, it } from "vitest";

import type { PlanItem } from "@/lib/api/plans";

import {
  addDaysIso,
  durationMinutes,
  formatDuration,
  formatPlanDate,
  formatTime,
  groupByDay,
  readNumber,
  readStrings,
  todayIsoDate,
} from "./plan-view";

function makeItem(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: "i1",
    plan_id: "p1",
    task_id: "t1",
    scheduled_date: "2026-08-18",
    start_time: "09:00:00",
    end_time: "10:30:00",
    risk_score: 0.2,
    rationale: null,
    created_at: "2026-08-17T00:00:00Z",
    assigned_to_user_id: null,
    task: {
      id: "t1",
      goal_id: "g1",
      title: "Draft the API layer",
      estimated_minutes: 90,
    },
    ...overrides,
  };
}

describe("todayIsoDate", () => {
  it("uses local calendar parts, not UTC", () => {
    // 00:30 on Aug 18 in a UTC-05:00 zone is already Aug 18 locally, but
    // toISOString would report Aug 18 05:30 — the bug only shows when local
    // and UTC dates differ. Construct a local time late enough in the day that
    // UTC has rolled over for anyone east of Greenwich.
    const localNewYearsEve = new Date(2026, 11, 31, 23, 30, 0);
    expect(todayIsoDate(localNewYearsEve)).toBe("2026-12-31");
  });

  it("zero-pads single-digit months and days", () => {
    expect(todayIsoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});

describe("addDaysIso", () => {
  it("adds days within a month", () => {
    expect(addDaysIso("2026-08-17", 7)).toBe("2026-08-24");
  });

  it("rolls over a month boundary", () => {
    expect(addDaysIso("2026-08-28", 7)).toBe("2026-09-04");
  });

  it("handles a leap day", () => {
    expect(addDaysIso("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("returns the input unchanged when unparseable", () => {
    expect(addDaysIso("nonsense", 3)).toBe("nonsense");
  });
});

describe("formatPlanDate", () => {
  it("renders the weekday of the date as written", () => {
    expect(formatPlanDate("2026-08-18")).toBe("Tue, Aug 18");
  });

  it("does not shift the day for a date parsed near midnight", () => {
    // The classic failure: new Date("2026-01-01") is UTC midnight, which is
    // Dec 31 for anyone west of Greenwich.
    expect(formatPlanDate("2026-01-01")).toBe("Thu, Jan 1");
  });

  it("returns the input unchanged when unparseable", () => {
    expect(formatPlanDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatTime", () => {
  it("converts morning times to 12-hour", () => {
    expect(formatTime("09:00:00")).toBe("9:00 AM");
  });

  it("converts afternoon times to 12-hour", () => {
    expect(formatTime("14:30:00")).toBe("2:30 PM");
  });

  it("renders midnight as 12 AM, not 0 AM", () => {
    expect(formatTime("00:15:00")).toBe("12:15 AM");
  });

  it("renders noon as 12 PM, not 0 PM", () => {
    expect(formatTime("12:00:00")).toBe("12:00 PM");
  });

  it("returns the input unchanged when unparseable", () => {
    expect(formatTime("half past nine")).toBe("half past nine");
  });
});

describe("durationMinutes", () => {
  it("measures a block spanning an hour boundary", () => {
    expect(durationMinutes("09:00:00", "10:30:00")).toBe(90);
  });

  it("returns null for a zero-length block", () => {
    expect(durationMinutes("09:00:00", "09:00:00")).toBeNull();
  });

  it("returns null when the end precedes the start", () => {
    expect(durationMinutes("10:00:00", "09:00:00")).toBeNull();
  });
});

describe("formatDuration", () => {
  it("renders sub-hour durations in minutes", () => {
    expect(formatDuration(45)).toBe("45m");
  });

  it("renders whole hours without stray minutes", () => {
    expect(formatDuration(120)).toBe("2h");
  });

  it("renders mixed durations", () => {
    expect(formatDuration(90)).toBe("1h 30m");
  });
});

describe("groupByDay", () => {
  it("groups items under their scheduled date", () => {
    const days = groupByDay([
      makeItem({ id: "a", scheduled_date: "2026-08-18" }),
      makeItem({ id: "b", scheduled_date: "2026-08-19" }),
      makeItem({ id: "c", scheduled_date: "2026-08-18" }),
    ]);
    expect(days.map((d) => d.date)).toEqual(["2026-08-18", "2026-08-19"]);
    expect(days[0].items).toHaveLength(2);
  });

  it("sorts days chronologically even when the API returns them out of order", () => {
    const days = groupByDay([
      makeItem({ id: "a", scheduled_date: "2026-09-02" }),
      makeItem({ id: "b", scheduled_date: "2026-08-30" }),
    ]);
    expect(days.map((d) => d.date)).toEqual(["2026-08-30", "2026-09-02"]);
  });

  it("sorts items within a day by start time", () => {
    // Scheduler order is not chronological — it fills by score, so a later
    // block can be created before an earlier one on the same day.
    const days = groupByDay([
      makeItem({ id: "late", start_time: "15:00:00", end_time: "16:00:00" }),
      makeItem({ id: "early", start_time: "08:00:00", end_time: "09:00:00" }),
    ]);
    expect(days[0].items.map((i) => i.id)).toEqual(["early", "late"]);
  });

  it("totals the scheduled minutes for each day", () => {
    const days = groupByDay([
      makeItem({ id: "a", start_time: "09:00:00", end_time: "10:00:00" }),
      makeItem({ id: "b", start_time: "11:00:00", end_time: "11:30:00" }),
    ]);
    expect(days[0].totalMinutes).toBe(90);
  });

  it("returns an empty list for a plan with no items", () => {
    expect(groupByDay([])).toEqual([]);
  });
});

describe("risk_summary readers", () => {
  it("reads a numeric field", () => {
    expect(readNumber({ scheduled: 4 }, "scheduled")).toBe(4);
  });

  it("returns null for a missing key", () => {
    expect(readNumber({}, "scheduled")).toBeNull();
  });

  it("returns null rather than NaN for a non-numeric value", () => {
    expect(readNumber({ scheduled: "four" }, "scheduled")).toBeNull();
  });

  it("returns null for a null summary", () => {
    expect(readNumber(null, "scheduled")).toBeNull();
  });

  it("reads a list of strings", () => {
    expect(readStrings({ recommendations: ["a", "b"] }, "recommendations")).toEqual([
      "a",
      "b",
    ]);
  });

  it("drops non-string entries rather than rendering them", () => {
    expect(readStrings({ recommendations: ["a", 3, null] }, "recommendations")).toEqual(
      ["a"],
    );
  });

  it("returns an empty list when the key is not an array", () => {
    expect(readStrings({ recommendations: "nope" }, "recommendations")).toEqual([]);
  });
});
