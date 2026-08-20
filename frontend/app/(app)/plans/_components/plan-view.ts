import type { PlanItem } from "@/lib/api/plans";

/**
 * Formatting and grouping for a plan's schedule.
 *
 * Every date and time from this API is a naive wall-clock string —
 * "YYYY-MM-DD" and "HH:MM:SS" with no zone. Nothing here parses one with
 * `new Date()`, which would read it as UTC and shift it a day (or an hour)
 * west of Greenwich. Splitting strings is not a shortcut; it is the correct
 * handling for a value that has no zone to convert from.
 */

/** Today as "YYYY-MM-DD" in the user's own timezone.
 *
 * Deliberately not `new Date().toISOString().slice(0, 10)`: toISOString
 * converts to UTC first, so anyone west of Greenwich gets tomorrow's date for
 * most of their evening.
 */
export function todayIsoDate(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Shift an ISO date string by a number of days, staying in ISO.
 *
 * Uses UTC internally so the arithmetic never crosses a daylight-saving
 * boundary and lands on the wrong day — the input carries no zone, so treating
 * it as UTC for the duration of the addition is lossless. */
export function addDaysIso(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  const shifted = new Date(Date.UTC(year, month - 1, day + days));
  return shifted.toISOString().slice(0, 10);
}

/** "2026-08-18" → "Tue, Aug 18". Returns the input unchanged if unparseable. */
export function formatPlanDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  // Constructed in UTC and read back in UTC, so the weekday is computed from
  // the date as written rather than from a local-midnight reinterpretation.
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "09:00:00" → "9:00 AM". Returns the input unchanged if unparseable. */
export function formatTime(value: string): string {
  const [rawHour, rawMinute] = value.split(":");
  const hour = Number(rawHour);
  if (!Number.isInteger(hour) || rawMinute === undefined) return value;
  const suffix = hour < 12 ? "AM" : "PM";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${displayHour}:${rawMinute} ${suffix}`;
}

/** Minutes between two "HH:MM:SS" values, or null if either is unparseable.
 *
 * Plan items never span midnight — the scheduler places them inside a single
 * day's free slots — so a negative result means bad data, not a wrap. */
export function durationMinutes(start: string, end: string): number | null {
  const toMinutes = (value: string): number | null => {
    const [h, m] = value.split(":").map(Number);
    if (!Number.isInteger(h) || !Number.isInteger(m)) return null;
    return h * 60 + m;
  };
  const from = toMinutes(start);
  const to = toMinutes(end);
  if (from === null || to === null) return null;
  const delta = to - from;
  return delta > 0 ? delta : null;
}

/** "1h 30m" from a minute count. */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h ${rest}m`;
}

/** Combine a plan item's date and time into an absolute instant.
 *
 * Plan values are naive wall-clock — "2026-08-18" at "09:00" means nine in the
 * morning wherever the user is. Work logs are the opposite: the column is
 * `DateTime(timezone=True)`, so the API wants a real instant.
 *
 * Constructing through the local `Date(y, m, d, h, min)` constructor is what
 * performs the conversion, because it interprets the parts in the user's zone
 * and `toISOString` then reports the same instant in UTC. Building the string
 * by concatenation instead would claim 09:00 UTC and silently move the log by
 * the offset.
 *
 * Returns null when either part is unparseable, so a caller never posts an
 * "Invalid Date".
 */
export function toLocalIsoTimestamp(
  isoDate: string,
  timeOfDay: string,
): string | null {
  const [year, month, day] = isoDate.split("-").map(Number);
  const [hour, minute] = timeOfDay.split(":").map(Number);
  if (![year, month, day, hour, minute].every(Number.isInteger)) return null;

  const instant = new Date(year, month - 1, day, hour, minute, 0, 0);
  if (Number.isNaN(instant.getTime())) return null;
  return instant.toISOString();
}

/** "09:00:00" → "09:00", the value an `<input type="time">` expects. */
export function toTimeInputValue(value: string): string {
  const [hour, minute] = value.split(":");
  if (hour === undefined || minute === undefined) return "";
  return `${hour}:${minute}`;
}

export type PlanDay = {
  date: string;
  items: PlanItem[];
  totalMinutes: number;
};

/** Group a plan's items into days, each sorted by start time.
 *
 * The API returns items in insertion order, which is scheduler order rather
 * than chronological — a plan that fills Monday, then backfills Tuesday, then
 * returns to Monday would render out of sequence without this. */
export function groupByDay(items: PlanItem[]): PlanDay[] {
  const byDate = new Map<string, PlanItem[]>();
  for (const item of items) {
    const bucket = byDate.get(item.scheduled_date);
    if (bucket) bucket.push(item);
    else byDate.set(item.scheduled_date, [item]);
  }

  return [...byDate.entries()]
    // ISO dates sort correctly as strings — that is the format's whole point.
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, dayItems]) => {
      const sorted = [...dayItems].sort((a, b) =>
        a.start_time.localeCompare(b.start_time),
      );
      const totalMinutes = sorted.reduce((sum, item) => {
        return sum + (durationMinutes(item.start_time, item.end_time) ?? 0);
      }, 0);
      return { date, items: sorted, totalMinutes };
    });
}

/**
 * Readers for `risk_summary`.
 *
 * The backend types this column as a bare `dict`, even though `RiskSummary` in
 * schemas/plans.py documents a much richer shape. Since the API makes no
 * guarantee, every read is defensive: a missing or wrongly-typed key renders
 * nothing rather than "undefined" or NaN.
 */
export function readNumber(
  summary: Record<string, unknown> | null,
  key: string,
): number | null {
  const value = summary?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function readStrings(
  summary: Record<string, unknown> | null,
  key: string,
): string[] {
  const value = summary?.[key];
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}
