import { describe, expect, it } from "vitest";

import { defaultPlanForm, planFormSchema, toPlanPayload } from "./plan-schema";

function parse(values: { planning_window_start: string; planning_window_end: string }) {
  return planFormSchema.safeParse(values);
}

function messageFor(
  result: ReturnType<typeof parse>,
  field: "planning_window_start" | "planning_window_end",
): string | undefined {
  if (result.success) return undefined;
  return result.error.issues.find((issue) => issue.path[0] === field)?.message;
}

describe("planFormSchema", () => {
  it("accepts a normal window", () => {
    expect(
      parse({ planning_window_start: "2026-08-17", planning_window_end: "2026-08-24" })
        .success,
    ).toBe(true);
  });

  it("accepts a single-day window", () => {
    // A one-day plan is legitimate — the backend compares dates inclusively.
    expect(
      parse({ planning_window_start: "2026-08-17", planning_window_end: "2026-08-17" })
        .success,
    ).toBe(true);
  });

  it("rejects an end date before the start", () => {
    const result = parse({
      planning_window_start: "2026-08-24",
      planning_window_end: "2026-08-17",
    });
    expect(result.success).toBe(false);
    expect(messageFor(result, "planning_window_end")).toBe(
      "End date cannot be before the start date",
    );
  });

  it("requires a start date", () => {
    const result = parse({
      planning_window_start: "",
      planning_window_end: "2026-08-24",
    });
    expect(messageFor(result, "planning_window_start")).toBe("Start date is required");
  });

  it("requires an end date", () => {
    const result = parse({
      planning_window_start: "2026-08-17",
      planning_window_end: "",
    });
    expect(messageFor(result, "planning_window_end")).toBe("End date is required");
  });

  it("does not add an ordering error when a field is still blank", () => {
    // Otherwise an empty form shows both "required" and "before the start
    // date", which reads as two problems when there is one.
    const result = parse({ planning_window_start: "", planning_window_end: "" });
    expect(messageFor(result, "planning_window_end")).toBe("End date is required");
  });
});

describe("defaultPlanForm", () => {
  it("defaults to a week starting today", () => {
    expect(defaultPlanForm("2026-08-17")).toEqual({
      planning_window_start: "2026-08-17",
      planning_window_end: "2026-08-24",
    });
  });

  it("produces a window that passes its own validation", () => {
    expect(planFormSchema.safeParse(defaultPlanForm("2026-08-17")).success).toBe(true);
  });
});

describe("toPlanPayload", () => {
  it("sends only the window, leaving scope to the backend default", () => {
    // Omitting scope_type/scope_id is what makes this a user-scoped plan;
    // sending them would opt into the team-membership check.
    expect(
      toPlanPayload({
        planning_window_start: "2026-08-17",
        planning_window_end: "2026-08-24",
      }),
    ).toEqual({
      planning_window_start: "2026-08-17",
      planning_window_end: "2026-08-24",
    });
  });
});
