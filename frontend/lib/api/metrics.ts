"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import { toApiError } from "@/lib/api/errors";

/** Mirrors backend `UserFeaturesResponse` (app/schemas/metrics.py).
 *
 * These are derived, not entered — recomputed from work log history every time
 * a log is written. They are the state of the learning loop:
 *
 *   - `estimation_bias_multiplier` is mean actual ÷ estimated across finished
 *     logs. Above 1 means work runs long, and plan generation multiplies every
 *     task estimate by it before placing them.
 *   - `completion_rate` is finished logs ÷ all logs.
 *
 * `reschedule_rate` and `burnout_score` are persisted but always written as
 * 0.0 by the current `compute_user_features`, so nothing here displays them.
 */
export type UserFeatures = {
  id: string;
  user_id: string;
  completion_rate: number;
  estimation_bias_multiplier: number;
  focus_probability_by_hour: Record<string, number> | null;
  reschedule_rate: number;
  burnout_score: number;
  last_computed_at: string | null;
  created_at: string;
  updated_at: string;
};

/** Shares the ["metrics"] prefix that the work log mutations invalidate. */
export const myMetricsQueryKey = ["metrics", "me"] as const;

export function useMyMetrics() {
  return useQuery({
    queryKey: myMetricsQueryKey,
    queryFn: async (): Promise<UserFeatures> => {
      try {
        const { data } = await apiClient.get<UserFeatures>("/metrics/me");
        return data;
      } catch (error) {
        throw toApiError(error, "Could not load your metrics");
      }
    },
  });
}

/** The hour of day this user most often works, or null if unknown.
 *
 * `focus_probability_by_hour` is keyed by hour-of-day as a string, with the
 * share of completed logs that started in that hour. Only hours with activity
 * appear, so an empty object means no completed work yet.
 */
export function peakFocusHour(features: UserFeatures): number | null {
  const byHour = features.focus_probability_by_hour;
  if (!byHour) return null;

  let bestHour: number | null = null;
  let bestValue = -Infinity;
  for (const [hour, value] of Object.entries(byHour)) {
    const parsed = Number(hour);
    if (!Number.isInteger(parsed) || typeof value !== "number") continue;
    if (value > bestValue) {
      bestValue = value;
      bestHour = parsed;
    }
  }
  return bestHour;
}

/** "9 AM" from an hour-of-day integer. */
export function formatHour(hour: number): string {
  const suffix = hour < 12 ? "AM" : "PM";
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display} ${suffix}`;
}

/** Plain-language reading of the estimation bias.
 *
 * The 5% deadband keeps a freshly-seeded 1.0 — and ordinary noise — from
 * reading as a finding.
 */
export function biasVerdict(multiplier: number): string {
  if (multiplier > 1.05) {
    return `Work runs about ${Math.round((multiplier - 1) * 100)}% longer than you estimate. Plans pad for it.`;
  }
  if (multiplier < 0.95) {
    return `Work finishes about ${Math.round((1 - multiplier) * 100)}% faster than you estimate. Plans fit more in.`;
  }
  return "Your estimates are close to reality.";
}
