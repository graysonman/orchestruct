import Link from "next/link";

import { apiFetch } from "@/lib/api/server";
import type { CurrentUser } from "@/lib/api/auth";

import { LearningSummary } from "./_components/learning-summary";

export const metadata = { title: "Dashboard · Orchestruct" };

/** The three steps of the loop, in the order a user walks them. */
const STEPS = [
  {
    href: "/goals",
    label: "Goals and tasks",
    body: "Declare what you want done and break it into tasks with time estimates.",
  },
  {
    href: "/plans",
    label: "Plans",
    body: "Fit pending tasks into your free time, then approve to push the blocks to your calendar.",
  },
  {
    href: "/worklogs",
    label: "Work log",
    body: "Record what actually happened. The gap against your estimates is what tunes the next plan.",
  },
] as const;

export default async function DashboardPage() {
  const user = await apiFetch<CurrentUser>("/auth/me");

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Signed in as {user.email}.
        </p>
      </header>

      <LearningSummary />

      <div className="grid gap-3 sm:grid-cols-3">
        {STEPS.map((step) => (
          <Link
            key={step.href}
            href={step.href}
            className="flex flex-col gap-1 rounded-lg border border-zinc-200 p-4 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            <span className="text-sm font-medium">{step.label}</span>
            <span className="text-xs text-zinc-600 dark:text-zinc-400">
              {step.body}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
