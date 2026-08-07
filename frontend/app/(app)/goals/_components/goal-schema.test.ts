import { describe, expect, it } from "vitest";

import {
  emptyGoalForm,
  goalFormSchema,
  parseNumeric,
  toGoalPayload,
} from "./goal-schema";

function form(overrides: Partial<typeof emptyGoalForm> = {}) {
  return { ...emptyGoalForm, title: "Ship v1", ...overrides };
}

/** Field names that carry an error, as react-hook-form would resolve them.
 *
 * A multi-segment path means the message renders under no input at all, so
 * asserting on the joined path is what actually pins the user-visible behavior.
 */
function errorPaths(values: ReturnType<typeof form>): string[] {
  const result = goalFormSchema.safeParse(values);
  if (result.success) return [];
  return result.error.issues.map((issue) => issue.path.join("."));
}

describe("parseNumeric", () => {
  it("returns null for blank and whitespace", () => {
    expect(parseNumeric("")).toBeNull();
    expect(parseNumeric("   ")).toBeNull();
  });

  it("parses numeric strings", () => {
    expect(parseNumeric("3.5")).toBe(3.5);
    expect(parseNumeric(" 12 ")).toBe(12);
  });

  it("returns NaN for unparseable text", () => {
    expect(parseNumeric("abc")).toBeNaN();
  });
});

describe("goalFormSchema", () => {
  it("requires a title", () => {
    expect(errorPaths(form({ title: "" }))).toContain("title");
  });

  it("accepts a minimal valid goal", () => {
    expect(errorPaths(form())).toEqual([]);
  });

  it("accepts a fully populated valid goal", () => {
    expect(
      errorPaths(
        form({
          description: "Get it out the door",
          success_metric_type: "features",
          target_value: "12",
          target_date: "2026-12-31",
          priority_weight: "2",
          min_weekly_hours: "4",
          max_weekly_hours: "10",
        }),
      ),
    ).toEqual([]);
  });

  describe("weekly hours", () => {
    it("rejects min above max", () => {
      expect(
        errorPaths(form({ min_weekly_hours: "10", max_weekly_hours: "5" })),
      ).toContain("min_weekly_hours");
    });

    it("allows min equal to max", () => {
      expect(
        errorPaths(form({ min_weekly_hours: "5", max_weekly_hours: "5" })),
      ).toEqual([]);
    });

    it("does not compare when one side is blank", () => {
      expect(errorPaths(form({ min_weekly_hours: "10" }))).toEqual([]);
    });

    it("rejects hours above 168", () => {
      expect(errorPaths(form({ max_weekly_hours: "200" }))).toContain(
        "max_weekly_hours",
      );
    });

    it("allows exactly 168", () => {
      expect(errorPaths(form({ max_weekly_hours: "168" }))).toEqual([]);
    });
  });

  describe("negative numbers", () => {
    it.each([
      ["target_value"],
      ["priority_weight"],
      ["min_weekly_hours"],
      ["max_weekly_hours"],
    ])("rejects a negative %s", (field) => {
      expect(errorPaths(form({ [field]: "-1" }))).toContain(field);
    });
  });

  describe("unparseable numbers", () => {
    it.each([
      ["target_value"],
      ["priority_weight"],
      ["min_weekly_hours"],
      ["max_weekly_hours"],
    ])("rejects non-numeric text in %s", (field) => {
      expect(errorPaths(form({ [field]: "abc" }))).toContain(field);
    });

    it("reports NaN once, not alongside a range error", () => {
      const paths = errorPaths(form({ min_weekly_hours: "abc" }));
      expect(paths).toEqual(["min_weekly_hours"]);
    });
  });

  describe("priority weight", () => {
    it("rejects zero", () => {
      expect(errorPaths(form({ priority_weight: "0" }))).toContain(
        "priority_weight",
      );
    });

    it("allows a fractional weight", () => {
      expect(errorPaths(form({ priority_weight: "0.5" }))).toEqual([]);
    });
  });

  it("allows a target_date in the past", () => {
    expect(errorPaths(form({ target_date: "2000-01-01" }))).toEqual([]);
  });

  it("reports every error on a single-segment path", () => {
    // Multi-segment paths render under no field; this pins that regression.
    const paths = errorPaths(
      form({
        title: "",
        target_value: "abc",
        priority_weight: "-1",
        min_weekly_hours: "200",
      }),
    );
    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect(path).not.toContain(".");
    }
  });
});

describe("toGoalPayload", () => {
  it("converts blank optional fields to null", () => {
    expect(toGoalPayload(form())).toEqual({
      title: "Ship v1",
      description: null,
      success_metric_type: null,
      target_value: null,
      target_date: null,
      priority_weight: 1,
      min_weekly_hours: null,
      max_weekly_hours: null,
    });
  });

  it("trims strings and parses numbers", () => {
    const payload = toGoalPayload(
      form({
        title: "  Ship v1  ",
        description: "  ship it  ",
        target_value: "500",
        priority_weight: "2.5",
      }),
    );
    expect(payload.title).toBe("Ship v1");
    expect(payload.description).toBe("ship it");
    expect(payload.target_value).toBe(500);
    expect(payload.priority_weight).toBe(2.5);
  });

  it("falls back to priority 1 when the field is blank", () => {
    expect(toGoalPayload(form({ priority_weight: "" })).priority_weight).toBe(1);
  });
});
