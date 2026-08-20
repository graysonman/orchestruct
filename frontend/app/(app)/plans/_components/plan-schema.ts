import { z } from "zod";

import type { PlanGenerateInput } from "@/lib/api/plans";

import { addDaysIso, todayIsoDate } from "./plan-view";

/**
 * The generate form is two date inputs, and both stay strings all the way to
 * the API — `<input type="date">` produces "YYYY-MM-DD", which is exactly what
 * pydantic's `date` expects. Converting to `Date` and back would only create
 * an opportunity to shift the day.
 */
export const planFormSchema = z
  .object({
    planning_window_start: z.string().min(1, "Start date is required"),
    planning_window_end: z.string().min(1, "End date is required"),
  })
  .superRefine((values, ctx) => {
    const { planning_window_start: start, planning_window_end: end } = values;
    if (start === "" || end === "") return;

    // ISO dates compare correctly as strings, so no parsing is needed to know
    // which came first.
    if (end < start) {
      ctx.addIssue({
        code: "custom",
        path: ["planning_window_end"],
        message: "End date cannot be before the start date",
      });
    }
  });

export type PlanFormValues = z.infer<typeof planFormSchema>;

/** Default window: today through a week out.
 *
 * Computed rather than constant so the form does not open on a stale date in a
 * long-lived tab. */
export function defaultPlanForm(today: string = todayIsoDate()): PlanFormValues {
  return {
    planning_window_start: today,
    planning_window_end: addDaysIso(today, 7),
  };
}

/** Convert validated form values into the JSON body the API expects.
 *
 * `scope_type` and `scope_id` are omitted deliberately: the backend defaults an
 * absent scope to the current user. Team plans would send both, and the caller
 * must already be a member or the request comes back 403. */
export function toPlanPayload(values: PlanFormValues): PlanGenerateInput {
  return {
    planning_window_start: values.planning_window_start,
    planning_window_end: values.planning_window_end,
  };
}
