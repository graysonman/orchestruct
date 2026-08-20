import type { WorkLog } from "@/lib/api/worklogs";

/**
 * Formatting for logged work.
 *
 * Unlike plan items, these are real instants — the column carries a timezone,
 * so `new Date()` is correct here and the values render in the reader's local
 * zone. Formatting a plan's `scheduled_date` this way would be a bug; formatting
 * these any other way would be too.
 */

/** Minutes between start and end, or null for a log that never ended. */
export function loggedMinutes(log: WorkLog): number | null {
  if (log.ended_at === null) return null;
  const started = new Date(log.started_at).getTime();
  const ended = new Date(log.ended_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(ended)) return null;
  const minutes = Math.round((ended - started) / 60000);
  return minutes > 0 ? minutes : null;
}

/** "1h 30m" from a minute count. */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

/** "Tue, Aug 18" in the reader's zone. */
export function formatLogDate(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/** "9:00 AM" in the reader's zone. */
export function formatLogTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

/** How this log compares to the task's estimate.
 *
 * This ratio is the raw material for `estimation_bias_multiplier` — a value
 * above 1 means the work ran long, which is what pads future plans. Returns
 * null when there is nothing to compare against.
 */
export function estimateRatio(log: WorkLog): number | null {
  const actual = loggedMinutes(log);
  const estimated = log.task.estimated_minutes;
  if (actual === null || estimated === null || estimated <= 0) return null;
  return actual / estimated;
}

/** A short human verdict on the ratio, or null when it is close enough.
 *
 * The 10% deadband keeps the history from labelling every log — a block that
 * ran five minutes long is not a signal the user needs to read. */
export function estimateVerdict(log: WorkLog): string | null {
  const ratio = estimateRatio(log);
  if (ratio === null) return null;
  if (ratio > 1.1) return `${Math.round((ratio - 1) * 100)}% over estimate`;
  if (ratio < 0.9) return `${Math.round((1 - ratio) * 100)}% under estimate`;
  return null;
}

export type LogDay = { date: string; logs: WorkLog[]; totalMinutes: number };

/** Group logs into days for display, preserving the server's newest-first order. */
export function groupLogsByDay(logs: WorkLog[]): LogDay[] {
  const byDate = new Map<string, WorkLog[]>();
  for (const log of logs) {
    const key = formatLogDate(log.started_at);
    const bucket = byDate.get(key);
    if (bucket) bucket.push(log);
    else byDate.set(key, [log]);
  }
  // Map preserves insertion order, and the API already sorts newest first, so
  // no re-sorting is needed — and re-sorting formatted labels would be wrong,
  // since "Aug 18" does not order lexicographically.
  return [...byDate.entries()].map(([date, dayLogs]) => ({
    date,
    logs: dayLogs,
    totalMinutes: dayLogs.reduce((sum, log) => sum + (loggedMinutes(log) ?? 0), 0),
  }));
}
