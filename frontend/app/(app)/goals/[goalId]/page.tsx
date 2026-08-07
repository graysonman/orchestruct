import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api/server";
import type { Goal } from "@/lib/api/goals";

import { TaskForm } from "./_components/task-form";
import { TaskList } from "./_components/task-list";

export const metadata = { title: "Goal · Orchestruct" };

/** Same string-split formatting as the goal list: `target_date` is a calendar
 * date, and `new Date()` would shift it a day west of UTC. */
function formatTargetDate(value: string | null): string | null {
  if (!value) return null;
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${month}/${day}/${year}`;
}

export default async function GoalDetailPage({
  params,
}: {
  params: Promise<{ goalId: string }>;
}) {
  const { goalId } = await params;

  let goal: Goal;
  try {
    goal = await apiFetch<Goal>(`/goals/${goalId}`);
  } catch (error) {
    // The backend returns 404 both for a missing goal and one owned by someone
    // else, so this covers "not found" and "not yours" alike.
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const targetDate = formatTargetDate(goal.target_date);

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link
          href="/goals"
          className="self-start text-xs text-zinc-500 hover:underline"
        >
          ← All goals
        </Link>
        <header className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{goal.title}</h1>
            {!goal.is_active && (
              <span className="rounded-full border border-zinc-300 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                Archived
              </span>
            )}
          </div>
          {goal.description && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {goal.description}
            </p>
          )}
        </header>

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
          <div className="flex gap-1">
            <dt>Priority:</dt>
            <dd>{goal.priority_weight}</dd>
          </div>
        </dl>
      </div>

      <div className="flex flex-col gap-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Tasks
        </h2>
        <TaskForm goalId={goalId} />
        <TaskList goalId={goalId} />
      </div>
    </section>
  );
}
