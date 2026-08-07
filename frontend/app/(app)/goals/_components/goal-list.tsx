"use client";

import Link from "next/link";

import { useDeleteGoal, useGoals, useUpdateGoal, type Goal } from "@/lib/api/goals";

/** Format a bare "YYYY-MM-DD" without going through Date.
 *
 * `new Date("2026-08-05")` parses as UTC midnight, which renders as Aug 4 for
 * anyone west of Greenwich. Splitting the string sidesteps the timezone
 * entirely — the backend sent a calendar date, not an instant.
 */
function formatTargetDate(value: string | null): string | null {
  if (!value) return null;
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${month}/${day}/${year}`;
}

function GoalCard({ goal }: { goal: Goal }) {
  const updateGoal = useUpdateGoal();
  const deleteGoal = useDeleteGoal();
  const busy = updateGoal.isPending || deleteGoal.isPending;

  const targetDate = formatTargetDate(goal.target_date);
  const hours =
    goal.min_weekly_hours !== null || goal.max_weekly_hours !== null
      ? `${goal.min_weekly_hours ?? "—"}–${goal.max_weekly_hours ?? "—"} h/week`
      : null;

  return (
    <li
      className={`flex flex-col gap-2 rounded-lg border p-4 ${
        goal.is_active
          ? "border-zinc-200 dark:border-zinc-800"
          : "border-zinc-200 opacity-60 dark:border-zinc-800"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">
            <Link href={`/goals/${goal.id}`} className="hover:underline">
              {goal.title}
            </Link>
          </h3>
          {goal.description && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {goal.description}
            </p>
          )}
        </div>
        <span className="shrink-0 rounded-full border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
          {goal.is_active ? "Active" : "Archived"}
        </span>
      </div>

      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
        {goal.success_metric_type && (
          <div className="flex gap-1">
            <dt>Metric:</dt>
            <dd>
              {goal.success_metric_type}
              {goal.target_value !== null && ` → ${goal.target_value}`}
            </dd>
          </div>
        )}
        {targetDate && (
          <div className="flex gap-1">
            <dt>Due:</dt>
            <dd>{targetDate}</dd>
          </div>
        )}
        {hours && (
          <div className="flex gap-1">
            <dt>Budget:</dt>
            <dd>{hours}</dd>
          </div>
        )}
        <div className="flex gap-1">
          <dt>Priority:</dt>
          <dd>{goal.priority_weight}</dd>
        </div>
      </dl>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            updateGoal.mutate({ id: goal.id, is_active: !goal.is_active })
          }
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          {goal.is_active ? "Archive" : "Reactivate"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => deleteGoal.mutate(goal.id)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-red-950/50"
        >
          Delete
        </button>
      </div>
    </li>
  );
}

export function GoalList() {
  const { data: goals, isPending, error } = useGoals();

  if (isPending) {
    return <p className="text-sm text-zinc-500">Loading goals…</p>;
  }

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
      >
        Could not load goals.
      </p>
    );
  }

  if (goals.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No goals yet. Create one to start planning.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {goals.map((goal) => (
        <GoalCard key={goal.id} goal={goal} />
      ))}
    </ul>
  );
}
