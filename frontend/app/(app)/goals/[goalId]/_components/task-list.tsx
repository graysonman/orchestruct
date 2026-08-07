"use client";

import {
  useDeleteTask,
  useTasks,
  useUpdateTask,
  type Task,
} from "@/lib/api/tasks";

import {
  isSchedulable,
  nextStatus,
  statusLabel,
  TASK_STATUSES,
} from "./task-status";

/** Format a bare "YYYY-MM-DD" without Date, which would parse it as UTC
 * midnight and shift the day in negative offsets. */
function formatDueDate(value: string | null): string | null {
  if (!value) return null;
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${month}/${day}/${year}`;
}

function formatEstimate(minutes: number | null): string | null {
  if (minutes === null) return null;
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

function TaskRow({ task, goalId }: { task: Task; goalId: string }) {
  const updateTask = useUpdateTask(goalId);
  const deleteTask = useDeleteTask(goalId);
  const busy = updateTask.isPending || deleteTask.isPending;

  const advanceTo = nextStatus(task.status);
  const due = formatDueDate(task.due_date);
  const estimate = formatEstimate(task.estimated_minutes);

  return (
    <li className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-medium">{task.title}</h3>
          {task.description && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {task.description}
            </p>
          )}
        </div>
        <span
          title={
            isSchedulable(task.status)
              ? "Eligible for plan generation"
              : "Not picked up by plan generation"
          }
          className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${
            isSchedulable(task.status)
              ? "border-emerald-300 text-emerald-700 dark:border-emerald-800 dark:text-emerald-400"
              : "border-zinc-300 text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
          }`}
        >
          {statusLabel(task.status)}
        </span>
      </div>

      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
        {estimate && (
          <div className="flex gap-1">
            <dt>Estimate:</dt>
            <dd>{estimate}</dd>
          </div>
        )}
        {due && (
          <div className="flex gap-1">
            <dt>Due:</dt>
            <dd>{due}</dd>
          </div>
        )}
        {task.difficulty !== null && (
          <div className="flex gap-1">
            <dt>Difficulty:</dt>
            <dd>{task.difficulty}/5</dd>
          </div>
        )}
        {task.dislike_score > 0 && (
          <div className="flex gap-1">
            <dt>Dislike:</dt>
            <dd>{task.dislike_score}/5</dd>
          </div>
        )}
      </dl>

      <div className="flex flex-wrap items-center gap-2">
        {advanceTo && (
          <button
            type="button"
            disabled={busy}
            onClick={() => updateTask.mutate({ id: task.id, status: advanceTo })}
            className="rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            Move to {statusLabel(advanceTo)}
          </button>
        )}

        <label className="sr-only" htmlFor={`status-${task.id}`}>
          Status for {task.title}
        </label>
        <select
          id={`status-${task.id}`}
          value={task.status}
          disabled={busy}
          onChange={(event) =>
            updateTask.mutate({ id: task.id, status: event.target.value })
          }
          className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"
        >
          {/* A task may hold a status outside our vocabulary, since the column
              is unconstrained. Render it so the select still shows the truth. */}
          {!TASK_STATUSES.some((s) => s.value === task.status) && (
            <option value={task.status}>{task.status}</option>
          )}
          {TASK_STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        <button
          type="button"
          disabled={busy}
          onClick={() => deleteTask.mutate(task.id)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-red-950/50"
        >
          Delete
        </button>
      </div>
    </li>
  );
}

export function TaskList({ goalId }: { goalId: string }) {
  const { data: tasks, isPending, error } = useTasks(goalId);

  if (isPending) {
    return <p className="text-sm text-zinc-500">Loading tasks…</p>;
  }

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
      >
        Could not load tasks.
      </p>
    );
  }

  if (tasks.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No tasks yet. Add one to give the planner something to schedule.
      </p>
    );
  }

  const schedulable = tasks.filter((task) => isSchedulable(task.status)).length;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-zinc-500">
        {schedulable} of {tasks.length} eligible for scheduling
      </p>
      <ul className="flex flex-col gap-2">
        {tasks.map((task) => (
          <TaskRow key={task.id} task={task} goalId={goalId} />
        ))}
      </ul>
    </div>
  );
}
