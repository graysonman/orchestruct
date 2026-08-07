import { z } from "zod";

import type { GoalCreateInput } from "@/lib/api/goals";

/**
 * Every field here is typed as a string because that is what an uncontrolled
 * `<input>` actually produces — including numeric and date inputs, which yield
 * "" when cleared rather than undefined. Parsing to numbers/nulls happens once,
 * in `toGoalPayload`, so validation and serialization stay separate concerns.
 */
export const goalFormSchema = z
  .object({
    title: z.string().trim().min(1, "Title is required").max(200, "Title is too long"),
    description: z.string().trim().max(2000, "Description is too long"),
    success_metric_type: z.string().trim().max(100, "Metric name is too long"),
    target_value: z.string(),
    target_date: z.string(),
    priority_weight: z.string(),
    min_weekly_hours: z.string(),
    max_weekly_hours: z.string(),
  })
  .superRefine(validateGoalConstraints);

export type GoalFormValues = z.infer<typeof goalFormSchema>;

export const emptyGoalForm: GoalFormValues = {
  title: "",
  description: "",
  success_metric_type: "",
  target_value: "",
  target_date: "",
  priority_weight: "1",
  min_weekly_hours: "",
  max_weekly_hours: "",
};

/**
 * Read a numeric form field. Returns `null` for a blank field (the user chose
 * not to set it) and `NaN` for unparseable text, so callers can tell "absent"
 * apart from "invalid".
 */
export function parseNumeric(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  return Number(trimmed);
}

/**
 * Cross-field business rules for a goal.
 *
 * Zod checks each field in isolation. This function runs once with ALL the
 * values, for rules that require comparing fields against each other.
 *
 * Call `ctx.addIssue(...)` to reject the submission and show a message under
 * an input. Call nothing, and the form submits.
 */
function validateGoalConstraints(
  values: {
    title: string;
    description: string;
    success_metric_type: string;
    target_value: string;
    target_date: string;
    priority_weight: string;
    min_weekly_hours: string;
    max_weekly_hours: string;
  },
  ctx: z.RefinementCtx,
): void {
  const min = parseNumeric(values.min_weekly_hours);
  const max = parseNumeric(values.max_weekly_hours);

  // Worked example: an unsatisfiable time budget. No single-field rule can
  // catch this, because each number is fine on its own.
  if (min !== null && max !== null && min > max) {
    ctx.addIssue({
      code: "custom",
      path: ["min_weekly_hours"],
      message: "Minimum weekly hours cannot exceed the maximum",
    });
  }

  // Each rule targets exactly one field. `path` is a path INTO the value, not
  // a list of fields — `["min_weekly_hours", "max_weekly_hours"]` would resolve
  // to `errors.min_weekly_hours.max_weekly_hours`, which the form never reads,
  // so the submission would fail with no visible message.
  const numericFields = [
    { key: "target_value", label: "Target value" },
    { key: "priority_weight", label: "Priority weight" },
    { key: "min_weekly_hours", label: "Minimum weekly hours" },
    { key: "max_weekly_hours", label: "Maximum weekly hours" },
  ] as const;

  for (const { key, label } of numericFields) {
    const parsed = parseNumeric(values[key]);

    // Checked first and separately: every comparison against NaN is false, so
    // an unparseable value slips past the range rules below. Left unchecked it
    // reaches the API as `null` (JSON.stringify turns NaN into null), silently
    // becoming "unset" instead of an error.
    if (parsed !== null && Number.isNaN(parsed)) {
      ctx.addIssue({
        code: "custom",
        path: [key],
        message: `${label} must be a number`,
      });
      continue;
    }

    if (parsed !== null && parsed < 0) {
      ctx.addIssue({
        code: "custom",
        path: [key],
        message: `${label} cannot be negative`,
      });
    }
  }

  // A week has 168 hours; anything at or above that cannot be scheduled.
  for (const key of ["min_weekly_hours", "max_weekly_hours"] as const) {
    const parsed = parseNumeric(values[key]);
    if (parsed !== null && !Number.isNaN(parsed) && parsed > 168) {
      ctx.addIssue({
        code: "custom",
        path: [key],
        message: "A week only has 168 hours",
      });
    }
  }

  // priority_weight divides scheduler capacity between goals. Zero or negative
  // would mean "never schedule this", which is what archiving is for.
  const priority = parseNumeric(values.priority_weight);
  if (priority !== null && !Number.isNaN(priority) && priority <= 0) {
    ctx.addIssue({
      code: "custom",
      path: ["priority_weight"],
      message: "Priority weight must be greater than zero",
    });
  }

  // Deliberately NOT validated: a target_date in the past. This is a planning
  // tool, and recording a goal whose deadline has already slipped is a real
  // use case — the scheduler surfaces it as at-risk rather than refusing it.
}

/** Convert validated form strings into the JSON body the API expects. */
export function toGoalPayload(values: GoalFormValues): GoalCreateInput {
  return {
    title: values.title.trim(),
    description: values.description.trim() || null,
    success_metric_type: values.success_metric_type.trim() || null,
    target_value: parseNumeric(values.target_value),
    target_date: values.target_date.trim() || null,
    priority_weight: parseNumeric(values.priority_weight) ?? 1,
    min_weekly_hours: parseNumeric(values.min_weekly_hours),
    max_weekly_hours: parseNumeric(values.max_weekly_hours),
  };
}
