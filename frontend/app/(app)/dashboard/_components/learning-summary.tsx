"use client";

import Link from "next/link";

import {
  biasVerdict,
  formatHour,
  peakFocusHour,
  useMyMetrics,
} from "@/lib/api/metrics";

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
      {hint && <p className="text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

export function LearningSummary() {
  const { data: features, isPending, error } = useMyMetrics();

  if (isPending) {
    return <p className="text-sm text-zinc-500">Loading your metrics…</p>;
  }

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
      >
        Could not load your metrics.
      </p>
    );
  }

  const hour = peakFocusHour(features);
  // A user with no finished logs sits at the seeded defaults, and presenting
  // those as findings would be a lie — the loop has not run yet.
  const hasHistory = features.last_computed_at !== null && hour !== null;

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
        What Orchestruct has learned
      </h2>

      {hasHistory ? (
        <>
          <dl className="flex flex-wrap gap-x-12 gap-y-4">
            <Stat
              label="Estimation bias"
              value={`${features.estimation_bias_multiplier.toFixed(2)}×`}
            />
            <Stat
              label="Completion rate"
              value={`${Math.round(features.completion_rate * 100)}%`}
            />
            <Stat label="Peak focus" value={formatHour(hour)} />
          </dl>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {biasVerdict(features.estimation_bias_multiplier)}
          </p>
        </>
      ) : (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Nothing learned yet. Generate a{" "}
          <Link href="/plans" className="underline">
            plan
          </Link>{" "}
          and log time against its blocks — once work is recorded, Orchestruct
          compares it against your estimates and adjusts future schedules.
        </p>
      )}
    </div>
  );
}
