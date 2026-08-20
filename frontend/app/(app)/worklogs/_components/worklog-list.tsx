"use client";

import { useUpdateWorkLog, useWorkLogs, type WorkLog } from "@/lib/api/worklogs";

import {
  estimateVerdict,
  formatLogTime,
  formatMinutes,
  groupLogsByDay,
  loggedMinutes,
} from "./worklog-view";

function LogRow({ log }: { log: WorkLog }) {
  const updateLog = useUpdateWorkLog();
  const minutes = loggedMinutes(log);
  const verdict = estimateVerdict(log);

  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-md border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <span className="text-sm font-medium tabular-nums">
        {formatLogTime(log.started_at)}
        {log.ended_at && ` – ${formatLogTime(log.ended_at)}`}
      </span>
      <span className="text-sm">{log.task.title}</span>

      {minutes !== null && (
        <span className="text-xs text-zinc-500">{formatMinutes(minutes)}</span>
      )}

      {log.ended_at === null && (
        <>
          <span className="text-xs text-amber-700 dark:text-amber-500">
            Still running — not counted yet
          </span>
          {/* Closing the log is what makes it visible to the learning loop:
              until it has an end time, there is no duration to compare against
              the task's estimate. */}
          <button
            type="button"
            disabled={updateLog.isPending}
            onClick={() =>
              updateLog.mutate({
                id: log.id,
                ended_at: new Date().toISOString(),
                completed: true,
              })
            }
            className="rounded-md border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            {updateLog.isPending ? "Finishing…" : "Finish now"}
          </button>
        </>
      )}

      {updateLog.isError && (
        <span role="alert" className="text-xs text-red-600">
          Could not finish this log.
        </span>
      )}

      {!log.completed && log.ended_at !== null && (
        <span className="text-xs text-zinc-500">Unfinished</span>
      )}

      {verdict && (
        <span
          className="text-xs text-zinc-500"
          title="Feeds your estimation bias, which pads future plans"
        >
          {verdict}
        </span>
      )}

      {log.notes && (
        <span className="w-full text-xs text-zinc-600 dark:text-zinc-400">
          {log.notes}
        </span>
      )}
    </li>
  );
}

export function WorkLogList() {
  const { data: logs, isPending, error } = useWorkLogs();

  if (isPending) {
    return <p className="text-sm text-zinc-500">Loading work logs…</p>;
  }

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
      >
        Could not load work logs.
      </p>
    );
  }

  if (logs.length === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Nothing logged yet. Open a plan and use “Log time” on a block to record
        what actually happened.
      </p>
    );
  }

  const days = groupLogsByDay(logs);

  return (
    <div className="flex flex-col gap-5">
      {days.map((day) => (
        <div key={day.date} className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="text-sm font-medium">{day.date}</h2>
            <span className="text-xs text-zinc-500 tabular-nums">
              {formatMinutes(day.totalMinutes)}
            </span>
          </div>
          <ul className="flex flex-col gap-1.5">
            {day.logs.map((log) => (
              <LogRow key={log.id} log={log} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
