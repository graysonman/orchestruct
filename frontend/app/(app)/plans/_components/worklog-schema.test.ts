import { describe, expect, it } from "vitest";

import type { PlanItem } from "@/lib/api/plans";

import { toLocalIsoTimestamp, toTimeInputValue } from "./plan-view";
import {
  toWorkLogPayload,
  workLogFormDefaults,
  workLogFormSchema,
  type WorkLogFormValues,
} from "./worklog-schema";

function makeItem(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: "i1",
    plan_id: "p1",
    task_id: "t1",
    scheduled_date: "2026-08-18",
    start_time: "09:00:00",
    end_time: "10:30:00",
    risk_score: null,
    rationale: null,
    created_at: "2026-08-17T00:00:00Z",
    assigned_to_user_id: null,
    task: { id: "t1", goal_id: "g1", title: "Draft the API layer", estimated_minutes: 90 },
    ...overrides,
  };
}

function values(overrides: Partial<WorkLogFormValues> = {}): WorkLogFormValues {
  return { start_time: "09:00", end_time: "10:30", completed: true, notes: "", ...overrides };
}

describe("toTimeInputValue", () => {
  it("drops the seconds an <input type=time> will not accept", () => {
    expect(toTimeInputValue("09:00:00")).toBe("09:00");
  });

  it("returns empty for an unparseable value rather than a broken input", () => {
    expect(toTimeInputValue("nine")).toBe("");
  });
});

describe("toLocalIsoTimestamp", () => {
  it("reads the wall-clock parts in the local zone", () => {
    // The plan says 09:00 wherever the user is, so the resulting instant must
    // be 09:00 local — verified by reading it back through a local Date rather
    // than asserting a fixed UTC string, which would only hold in one zone.
    const iso = toLocalIsoTimestamp("2026-08-18", "09:00");
    expect(iso).not.toBeNull();
    const back = new Date(iso as string);
    expect(back.getHours()).toBe(9);
    expect(back.getMinutes()).toBe(0);
    expect(back.getDate()).toBe(18);
  });

  it("returns null for an unparseable date", () => {
    expect(toLocalIsoTimestamp("not-a-date", "09:00")).toBeNull();
  });

  it("returns null for an unparseable time", () => {
    expect(toLocalIsoTimestamp("2026-08-18", "")).toBeNull();
  });
});

describe("workLogFormSchema", () => {
  it("accepts a finished block", () => {
    expect(workLogFormSchema.safeParse(values()).success).toBe(true);
  });

  it("accepts an open log with no end time", () => {
    expect(
      workLogFormSchema.safeParse(values({ end_time: "", completed: false })).success,
    ).toBe(true);
  });

  it("rejects an end time at or before the start", () => {
    const result = workLogFormSchema.safeParse(values({ end_time: "09:00" }));
    expect(result.success).toBe(false);
  });

  it("rejects marking a log finished with no end time", () => {
    // The backend only counts a log toward completion_rate when it has both,
    // so this would otherwise be silently dropped by the learning loop.
    const result = workLogFormSchema.safeParse(
      values({ end_time: "", completed: true }),
    );
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].message).toContain("end time is required");
    }
  });
});

describe("workLogFormDefaults", () => {
  it("prefills from the scheduled block and assumes it happened", () => {
    expect(workLogFormDefaults(makeItem())).toEqual({
      start_time: "09:00",
      end_time: "10:30",
      completed: true,
      notes: "",
    });
  });

  it("produces defaults that pass its own validation", () => {
    expect(workLogFormSchema.safeParse(workLogFormDefaults(makeItem())).success).toBe(
      true,
    );
  });
});

describe("toWorkLogPayload", () => {
  it("carries the block's task and trims empty notes to null", () => {
    const payload = toWorkLogPayload(makeItem(), values({ notes: "   " }));
    expect(payload?.task_id).toBe("t1");
    expect(payload?.notes).toBeNull();
    expect(payload?.completed).toBe(true);
  });

  it("keeps notes that have content", () => {
    expect(toWorkLogPayload(makeItem(), values({ notes: " went long " }))?.notes).toBe(
      "went long",
    );
  });

  it("sends a null end for an open log", () => {
    const payload = toWorkLogPayload(
      makeItem(),
      values({ end_time: "", completed: false }),
    );
    expect(payload?.ended_at).toBeNull();
    expect(payload?.started_at).not.toBeNull();
  });

  it("anchors the log to the block's date, not today", () => {
    const payload = toWorkLogPayload(makeItem({ scheduled_date: "2026-08-18" }), values());
    expect(new Date(payload!.started_at).getDate()).toBe(18);
  });

  it("returns null rather than posting a malformed timestamp", () => {
    expect(toWorkLogPayload(makeItem({ scheduled_date: "garbage" }), values())).toBeNull();
  });
});
