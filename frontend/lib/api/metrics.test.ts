import { describe, expect, it } from "vitest";

import { biasVerdict, formatHour, peakFocusHour, type UserFeatures } from "./metrics";

function makeFeatures(overrides: Partial<UserFeatures> = {}): UserFeatures {
  return {
    id: "f1",
    user_id: "u1",
    completion_rate: 0.8,
    estimation_bias_multiplier: 1.0,
    focus_probability_by_hour: { "9": 0.5, "14": 0.3 },
    reschedule_rate: 0,
    burnout_score: 0,
    last_computed_at: "2026-08-20T09:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-20T09:00:00Z",
    ...overrides,
  };
}

describe("peakFocusHour", () => {
  it("picks the hour with the highest share", () => {
    expect(peakFocusHour(makeFeatures())).toBe(9);
  });

  it("returns null when no history has been computed", () => {
    expect(peakFocusHour(makeFeatures({ focus_probability_by_hour: null }))).toBeNull();
  });

  it("returns null for an empty distribution", () => {
    expect(peakFocusHour(makeFeatures({ focus_probability_by_hour: {} }))).toBeNull();
  });

  it("ignores entries whose value is not a number", () => {
    const features = makeFeatures({
      focus_probability_by_hour: { "9": 0.2, "15": "lots" } as unknown as Record<
        string,
        number
      >,
    });
    expect(peakFocusHour(features)).toBe(9);
  });
});

describe("formatHour", () => {
  it("renders a morning hour", () => {
    expect(formatHour(9)).toBe("9 AM");
  });

  it("renders midnight as 12 AM", () => {
    expect(formatHour(0)).toBe("12 AM");
  });

  it("renders noon as 12 PM", () => {
    expect(formatHour(12)).toBe("12 PM");
  });

  it("renders an evening hour", () => {
    expect(formatHour(21)).toBe("9 PM");
  });
});

describe("biasVerdict", () => {
  it("says estimates are accurate inside the deadband", () => {
    // A freshly-seeded 1.0 must not read as a finding.
    expect(biasVerdict(1.0)).toContain("close to reality");
    expect(biasVerdict(1.03)).toContain("close to reality");
  });

  it("reports overrun as a percentage", () => {
    expect(biasVerdict(1.4)).toContain("40% longer");
  });

  it("reports finishing early", () => {
    expect(biasVerdict(0.75)).toContain("25% faster");
  });
});
