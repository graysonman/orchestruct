/** Plan status vocabulary and the transitions the UI is allowed to offer.
 *
 * Like `Task.status`, the backend column is a bare `String(50)` with no enum,
 * so the vocabulary is defined here. Unlike tasks, the transitions are enforced
 * server-side, and this file exists mainly to keep the UI from offering a
 * button that is guaranteed to 400.
 *
 * The backend's own names disagree in three places, so this file picks what the
 * UI treats as true:
 *
 *   - `models/plan.py` defaults the column to "draft", but `generate_plan`
 *     always writes "proposed". Nothing in the codebase produces a draft plan,
 *     so "draft" is recognized but never expected.
 *   - Rejecting writes "invalidated", not "rejected".
 *   - PLAN.md documents a "committed" state. No endpoint produces it — it is
 *     recognized here so a future backend can introduce it without this file
 *     rendering a raw string at the user.
 */

export const PLAN_STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "proposed", label: "Proposed" },
  { value: "approved", label: "Approved" },
  { value: "committed", label: "Committed" },
  { value: "invalidated", label: "Invalidated" },
] as const;

export type PlanStatusValue = (typeof PLAN_STATUSES)[number]["value"];

/** Human label for a status, falling back to the raw string.
 *
 * The column is unconstrained, so a plan can hold a value this file has never
 * heard of — showing the raw string beats showing nothing. */
export function planStatusLabel(status: string): string {
  return PLAN_STATUSES.find((s) => s.value === status)?.label ?? status;
}

/** True when POST /plans/{id}/approve will be accepted.
 *
 * Mirrors `routers/plans.py`, which rejects anything but "proposed" with a 400.
 */
export function canApprove(status: string): boolean {
  return status === "proposed";
}

/** True when POST /plans/{id}/reject will be accepted.
 *
 * The backend allows rejecting an already-approved plan, which is how you undo
 * an approval — there is no separate un-approve endpoint. */
export function canReject(status: string): boolean {
  return status === "proposed" || status === "approved";
}

/** True once a plan can no longer change — no action will be offered.
 *
 * Derived from the two rules above rather than listed separately, so a status
 * can never be both terminal and actionable. */
export function isTerminal(status: string): boolean {
  return !canApprove(status) && !canReject(status);
}

/** One-line explanation of what a status means for the user.
 *
 * Returns null for unrecognized statuses rather than inventing a description
 * for a state this file does not understand. */
export function planStatusHint(status: string): string | null {
  switch (status) {
    case "draft":
      return "Not yet proposed for approval.";
    case "proposed":
      return "Waiting on you. Approve to commit these blocks to your calendar.";
    case "approved":
      return "Approved. Blocks were pushed to Google Calendar if it is connected.";
    case "committed":
      return "Committed and locked.";
    case "invalidated":
      return "Rejected. Generate a new plan to reschedule this work.";
    default:
      return null;
  }
}
