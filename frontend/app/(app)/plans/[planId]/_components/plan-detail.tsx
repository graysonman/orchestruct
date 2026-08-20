"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiRequestError } from "@/lib/api/errors";
import { useCreateWorkLog } from "@/lib/api/worklogs";
import {
  useApprovePlan,
  usePlan,
  useRejectPlan,
  type Plan,
  type PlanItem,
} from "@/lib/api/plans";

import {
  canApprove,
  canReject,
  planStatusHint,
  planStatusLabel,
} from "../../_components/plan-status";
import {
  durationMinutes,
  formatDuration,
  formatPlanDate,
  formatTime,
  groupByDay,
  readNumber,
  readStrings,
} from "../../_components/plan-view";
import { LogTimeForm } from "./log-time-form";

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "approved" || status === "committed"
      ? "border-emerald-300 text-emerald-700 dark:border-emerald-800 dark:text-emerald-400"
      : status === "invalidated"
        ? "border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-500"
        : "border-amber-300 text-amber-700 dark:border-amber-800 dark:text-amber-400";

  return (
    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${tone}`}>
      {planStatusLabel(status)}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function RiskSummary({ summary }: { summary: Record<string, unknown> | null }) {
  const scheduled = readNumber(summary, "scheduled");
  const unscheduled = readNumber(summary, "unscheduled");
  const quality = readNumber(summary, "quality_score");
  const recommendations = readStrings(summary, "recommendations");
  const criticalDays = readStrings(summary, "critical_days");

  const hasStats = scheduled !== null || unscheduled !== null || quality !== null;
  if (!hasStats && recommendations.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      {hasStats && (
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          {scheduled !== null && (
            <Stat label="Scheduled" value={String(scheduled)} />
          )}
          {unscheduled !== null && (
            <Stat label="Unscheduled" value={String(unscheduled)} />
          )}
          {quality !== null && (
            <Stat label="Quality" value={`${Math.round(quality)}/100`} />
          )}
          {criticalDays.length > 0 && (
            <Stat label="Heavy days" value={String(criticalDays.length)} />
          )}
        </dl>
      )}

      {/* Surfaced prominently: work the scheduler could not place is the single
          most actionable thing about a plan, and it is easy to miss among the
          blocks that did fit. */}
      {unscheduled !== null && unscheduled > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-500">
          {unscheduled} task{unscheduled === 1 ? "" : "s"} did not fit in this
          window.
        </p>
      )}

      {recommendations.length > 0 && (
        <ul className="list-disc space-y-1 pl-4 text-xs text-zinc-600 dark:text-zinc-400">
          {recommendations.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ScheduleItem({ item }: { item: PlanItem }) {
  const [logging, setLogging] = useState(false);
  const startLog = useCreateWorkLog();
  const minutes = durationMinutes(item.start_time, item.end_time);

  return (
    <li className="rounded-md border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm font-medium tabular-nums">
          {formatTime(item.start_time)} – {formatTime(item.end_time)}
        </span>
        <span className="text-sm">{item.task.title}</span>
        {minutes !== null && (
          <span className="text-xs text-zinc-500">{formatDuration(minutes)}</span>
        )}
        {item.task.estimated_minutes !== null &&
          minutes !== null &&
          minutes !== item.task.estimated_minutes && (
            <span
              className="text-xs text-zinc-500"
              title="The scheduler padded this block using your estimation bias"
            >
              est. {formatDuration(item.task.estimated_minutes)}
            </span>
          )}
        {!logging && (
          <div className="ml-auto flex items-center gap-1.5">
            {/* Starts an open log at the real current time — the block's
                scheduled times describe the plan, not what is happening now.
                Finishing it happens from the work log page. */}
            <button
              type="button"
              disabled={startLog.isPending}
              onClick={() =>
                startLog.mutate({
                  task_id: item.task_id,
                  started_at: new Date().toISOString(),
                  ended_at: null,
                  completed: false,
                  notes: null,
                })
              }
              className="rounded-md border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              {startLog.isPending ? "Starting…" : "Start now"}
            </button>
            <button
              type="button"
              onClick={() => setLogging(true)}
              className="rounded-md border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              Log time
            </button>
          </div>
        )}
      </div>

      {startLog.isError && (
        <p role="alert" className="mt-1 text-xs text-red-600">
          Could not start a log for this block.
        </p>
      )}

      {startLog.isSuccess && !logging && (
        <p className="mt-1 text-xs text-zinc-500">
          Timing started. Finish it from{" "}
          <Link href="/worklogs" className="underline">
            your work log
          </Link>
          .
        </p>
      )}

      {/* Logging from the block rather than a standalone form is what makes
          this usable: the task, the day, and the planned times are all already
          known, so recording what happened is a confirmation rather than data
          entry. There is also no endpoint that lists tasks across goals, so a
          free-standing form would have nowhere to get its task picker. */}
      {logging && <LogTimeForm item={item} onClose={() => setLogging(false)} />}
    </li>
  );
}

function Schedule({ items }: { items: PlanItem[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        This plan is empty. The scheduler found no pending tasks, or no free
        time in the window.
      </p>
    );
  }

  const days = groupByDay(items);

  return (
    <div className="flex flex-col gap-5">
      {days.map((day) => (
        <div key={day.date} className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="text-sm font-medium">{formatPlanDate(day.date)}</h3>
            <span className="text-xs text-zinc-500 tabular-nums">
              {formatDuration(day.totalMinutes)}
            </span>
          </div>
          <ul className="flex flex-col gap-1.5">
            {day.items.map((item) => (
              <ScheduleItem key={item.id} item={item} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function PlanActions({ plan }: { plan: Plan }) {
  const [actionErrors, setActionErrors] = useState<string[]>([]);
  const approve = useApprovePlan(plan.id);
  const reject = useRejectPlan(plan.id);

  const busy = approve.isPending || reject.isPending;
  const showApprove = canApprove(plan.status);
  const showReject = canReject(plan.status);

  if (!showApprove && !showReject) return null;

  const run = async (action: typeof approve, fallback: string) => {
    setActionErrors([]);
    try {
      await action.mutateAsync();
    } catch (error) {
      setActionErrors(
        error instanceof ApiRequestError ? error.messages : [fallback],
      );
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {showApprove && (
          <button
            type="button"
            disabled={busy}
            onClick={() => run(approve, "Could not approve plan")}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {approve.isPending ? "Approving…" : "Approve plan"}
          </button>
        )}
        {showReject && (
          <button
            type="button"
            disabled={busy}
            onClick={() => run(reject, "Could not reject plan")}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm text-red-600 disabled:opacity-50 dark:border-zinc-700"
          >
            {reject.isPending ? "Rejecting…" : "Reject"}
          </button>
        )}
      </div>

      {actionErrors.length > 0 && (
        <div
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {actionErrors.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function PlanDetail({
  planId,
  initialPlan,
}: {
  planId: string;
  initialPlan: Plan;
}) {
  // Seeded from the server render, then kept current by the mutations —
  // approve and reject write the updated plan into this same cache key, so the
  // status and buttons re-render with no refetch.
  const { data } = usePlan(planId, initialPlan);
  const plan = data ?? initialPlan;

  const hint = planStatusHint(plan.status);

  return (
    <>
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {formatPlanDate(plan.planning_window_start)} –{" "}
            {formatPlanDate(plan.planning_window_end)}
          </h1>
          <StatusPill status={plan.status} />
        </div>
        {hint && (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{hint}</p>
        )}
      </header>

      <RiskSummary summary={plan.risk_summary} />

      <div className="flex flex-col gap-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Schedule
        </h2>
        <Schedule items={plan.items} />
      </div>

      <PlanActions plan={plan} />
    </>
  );
}
