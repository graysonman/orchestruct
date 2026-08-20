import { z } from "zod";

import type { PlanItem } from "@/lib/api/plans";
import type { WorkLogCreateInput } from "@/lib/api/worklogs";

import { toLocalIsoTimestamp, toTimeInputValue } from "./plan-view";

/**
 * Logging time against a scheduled block.
 *
 * The date is not a field: a log raised from a plan item belongs to that
 * item's day, and letting it drift would break the link between what was
 * scheduled and what happened. Only the times, whether it finished, and notes
 * are editable.
 */
export const workLogFormSchema = z
  .object({
    start_time: z.string().min(1, "Start time is required"),
    end_time: z.string(),
    completed: z.boolean(),
    notes: z.string().trim().max(2000, "Notes are too long"),
  })
  .superRefine((values, ctx) => {
    // "HH:MM" strings compare correctly, so no parsing is needed to order them.
    if (values.end_time !== "" && values.end_time <= values.start_time) {
      ctx.addIssue({
        code: "custom",
        path: ["end_time"],
        message: "End time must be after the start time",
      });
    }

    // The backend counts a log toward completion_rate only when it is both
    // completed and has an end — a "completed" log with no end time would be
    // silently ignored by the learning loop, so reject it here instead.
    if (values.completed && values.end_time === "") {
      ctx.addIssue({
        code: "custom",
        path: ["end_time"],
        message: "An end time is required to mark this finished",
      });
    }
  });

export type WorkLogFormValues = z.infer<typeof workLogFormSchema>;

/** Prefill from the block the user is logging against.
 *
 * Defaults to the scheduled times and to finished, because the common case is
 * confirming that the plan happened. Correcting the times is the exception. */
export function workLogFormDefaults(item: PlanItem): WorkLogFormValues {
  return {
    start_time: toTimeInputValue(item.start_time),
    end_time: toTimeInputValue(item.end_time),
    completed: true,
    notes: "",
  };
}

/** Build the POST body, converting the block's wall-clock times into instants.
 *
 * Returns null if the date and times cannot be combined, which the form treats
 * as a validation failure rather than posting a malformed timestamp.
 */
export function toWorkLogPayload(
  item: PlanItem,
  values: WorkLogFormValues,
): WorkLogCreateInput | null {
  const startedAt = toLocalIsoTimestamp(item.scheduled_date, values.start_time);
  if (startedAt === null) return null;

  const endedAt =
    values.end_time === ""
      ? null
      : toLocalIsoTimestamp(item.scheduled_date, values.end_time);
  if (values.end_time !== "" && endedAt === null) return null;

  return {
    task_id: item.task_id,
    started_at: startedAt,
    ended_at: endedAt,
    completed: values.completed,
    notes: values.notes.trim() || null,
  };
}
