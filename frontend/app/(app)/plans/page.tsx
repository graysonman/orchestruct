import Link from "next/link";

import { PlanForm } from "./_components/plan-form";

export const metadata = { title: "Plans · Orchestruct" };

/** The plans index is generate-only.
 *
 * There is no `GET /plans` — the API can generate a plan or fetch one by id,
 * and nothing else. So this page cannot list past plans, and a generated plan
 * lives at its own URL rather than here. Adding a list means a backend change
 * first.
 */
export default function PlansPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Plans</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Fit your pending tasks into the time you actually have. Pick a window
          and the scheduler places the work.
        </p>
      </header>

      <PlanForm />

      <div className="rounded-lg border border-dashed border-zinc-300 p-6 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
        <p className="mb-2 font-medium text-zinc-900 dark:text-zinc-100">
          Only tasks marked “Pending” get scheduled.
        </p>
        <p>
          Anything in progress, completed, or blocked is skipped. If a plan comes
          back emptier than expected, check the statuses on your{" "}
          <Link href="/goals" className="underline">
            goals
          </Link>
          .
        </p>
      </div>
    </section>
  );
}
