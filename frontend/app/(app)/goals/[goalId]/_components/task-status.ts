/** Task status vocabulary.
 *
 * The backend column is a bare `String(50)` with a "pending" default — there is
 * no enum, so the API accepts any string and the vocabulary is defined here.
 *
 * The one status with behavior attached is "pending": plan_service.py:41
 * filters `Task.status == "pending"` when collecting work to schedule. A task
 * in any other status is invisible to the planner.
 */

export const SCHEDULABLE_STATUS = "pending";

export const TASK_STATUSES = [
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
  { value: "blocked", label: "Blocked" },
] as const;

export type TaskStatusValue = (typeof TASK_STATUSES)[number]["value"];

/** Human label for a status, falling back to the raw string.
 *
 * The column is unconstrained, so a task can hold a value this UI has never
 * heard of — rendering the raw string beats rendering nothing.
 */
export function statusLabel(status: string): string {
  return TASK_STATUSES.find((s) => s.value === status)?.label ?? status;
}

/** True when a task in this status will be picked up by plan generation. */
export function isSchedulable(status: string): boolean {
  return status === SCHEDULABLE_STATUS;
}

/** The status a one-click "advance" button should move this task to.
 *
 * This is the *likely* next move, not the only legal one — the status dropdown
 * beside the button can still reach any status. Returning null hides the
 * button, leaving the dropdown as the only way to move that task.
 *
 *   blocked ──► pending ──► in_progress ──► completed ──► (terminal)
 *
 * "blocked" advances back to "pending" rather than straight to "in_progress":
 * unblocking returns a task to the backlog and makes it schedulable again
 * (see `isSchedulable`), leaving the decision to actually start it separate.
 *
 * Unrecognized statuses return null. The column is an unconstrained
 * String(50), so guessing a transition for a state this file has never heard
 * of would be worse than showing no button.
 */
export function nextStatus(current: string): string | null {
  switch (current) {
    case "pending":
      return "in_progress";
    case "blocked":
      return "pending";
    case "in_progress":
      return "completed";
    // "completed" falls through to null: terminal by design.
    default:
      return null;
  }
}
