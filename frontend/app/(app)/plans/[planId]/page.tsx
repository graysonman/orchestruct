import Link from "next/link";
import { notFound } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api/server";
import type { Plan } from "@/lib/api/plans";

import { PlanDetail } from "./_components/plan-detail";

export const metadata = { title: "Plan · Orchestruct" };

export default async function PlanDetailPage({
  params,
}: {
  params: Promise<{ planId: string }>;
}) {
  const { planId } = await params;

  let plan: Plan;
  try {
    plan = await apiFetch<Plan>(`/plans/${planId}`);
  } catch (error) {
    // The backend returns 404 both for a missing plan and one belonging to
    // someone else, so this covers "not found" and "not yours" alike.
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <section className="flex flex-col gap-6">
      <Link
        href="/plans"
        className="self-start text-xs text-zinc-500 hover:underline"
      >
        ← All plans
      </Link>

      {/* Fetched here so the schedule is in the first paint and a missing plan
          404s before anything renders. PlanDetail takes it as initial data and
          keeps it live from there — approve and reject write the updated plan
          straight into the query cache. */}
      <PlanDetail planId={planId} initialPlan={plan} />
    </section>
  );
}
