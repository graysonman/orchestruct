"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import { toApiError } from "@/lib/api/errors";

/** Mirrors backend `TaskSummary` (app/schemas/plans.py).
 *
 * A plan item stores only `task_id`, so the backend embeds this alongside each
 * item — otherwise rendering a schedule would need one request per block to
 * learn what the block is for. `goal_id` is here rather than a nested goal
 * object: the UI can map ids to titles from the `useGoals()` cache it already
 * holds, and embedding a third level would widen the query for little gain.
 */
export type TaskSummary = {
  id: string;
  goal_id: string;
  title: string;
  estimated_minutes: number | null;
};

/** Mirrors backend `PlanItemResponse`.
 *
 * `scheduled_date` is a bare "YYYY-MM-DD" and `start_time`/`end_time` are bare
 * "HH:MM:SS" — both are naive wall-clock values with no zone, the same trap
 * documented for `target_date` in goals.ts. Passing either to `new Date()`
 * treats it as UTC and shifts it in negative offsets, so they stay strings and
 * get formatted by splitting.
 *
 * `rationale` is the scheduler's explanation for this placement — score,
 * breakdown, risk factors, warnings. It's JSON on the backend with no schema
 * enforcement, so it stays loose here too.
 */
export type PlanItem = {
  id: string;
  plan_id: string;
  task_id: string;
  scheduled_date: string;
  start_time: string;
  end_time: string;
  risk_score: number | null;
  rationale: Record<string, unknown> | null;
  created_at: string;
  assigned_to_user_id: string | null;
  task: TaskSummary;
};

/** Mirrors backend `PlanResponse`.
 *
 * `risk_summary` is typed loosely for the same reason as `rationale`: the
 * backend declares it `dict | None` on the model even though `RiskSummary` in
 * schemas/plans.py documents a much richer shape. Typing it strictly here would
 * claim a guarantee the API doesn't make.
 */
export type Plan = {
  id: string;
  scope_type: "user" | "team" | "org";
  scope_id: string;
  planning_window_start: string;
  planning_window_end: string;
  status: string;
  risk_summary: Record<string, unknown> | null;
  items: PlanItem[];
  created_at: string;
  updated_at: string;
};

/** Body for POST /plans/generate.
 *
 * `scope_type` and `scope_id` are omitted for user plans — the backend defaults
 * the scope to the current user (routers/plans.py). Team plans must send both,
 * and the caller must be a member or the request is rejected with a 403.
 */
export type PlanGenerateInput = {
  planning_window_start: string;
  planning_window_end: string;
  scope_type?: "user" | "team";
  scope_id?: string;
};

/** Query key for a single plan.
 *
 * There is no collection key because there is no list endpoint — the API can
 * generate a plan or fetch one by id, and nothing else. Anything that wants to
 * show "my recent plans" needs a backend change first.
 */
export const planQueryKey = (planId: string) => ["plans", planId] as const;

/** Read a single plan.
 *
 * `initialData` lets a server component hand over the plan it already fetched,
 * so the page paints the schedule immediately instead of flashing a loading
 * state for data that crossed the wire once already. Mutations then keep this
 * same cache entry current.
 */
export function usePlan(planId: string, initialData?: Plan) {
  return useQuery({
    queryKey: planQueryKey(planId),
    queryFn: async (): Promise<Plan> => {
      try {
        const { data } = await apiClient.get<Plan>(`/plans/${planId}`);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not load plan");
      }
    },
    initialData,
  });
}

/** Generate a plan for a date window.
 *
 * Failure here is the one place in the app where the server sends back a list
 * of problems rather than one — the scheduler reports every reason it could
 * not build a plan at once. `toApiError` preserves them in `.messages` so the
 * form can render each on its own line.
 */
export function useGeneratePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PlanGenerateInput): Promise<Plan> => {
      try {
        const { data } = await apiClient.post<Plan>("/plans/generate", input);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not generate plan");
      }
    },
    onSuccess: (plan) => {
      // Seed rather than invalidate: the response is the complete new plan, and
      // there is no list for it to have gone stale in. Writing it under its own
      // key lets /plans/[planId] render immediately instead of re-fetching what
      // we were just handed.
      queryClient.setQueryData(planQueryKey(plan.id), plan);
    },
  });
}

/** Approve a proposed plan.
 *
 * `planId` is a hook argument rather than a mutation argument so the callbacks
 * can build the cache key without it — the same shape as useUpdateTask(goalId).
 *
 * The backend rejects this with a 400 unless the plan is currently "proposed",
 * and approving a user-scoped plan also pushes its blocks to Google Calendar
 * when the account is connected.
 */
export function useApprovePlan(planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<Plan> => {
      try {
        const { data } = await apiClient.post<Plan>(`/plans/${planId}/approve`);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not approve plan");
      }
    },
    onSuccess: (plan) => {
      // The response is the full updated plan for exactly this key, so writing
      // it directly avoids the refetch an invalidate would trigger.
      queryClient.setQueryData(planQueryKey(planId), plan);
    },
  });
}

/** Reject a plan, moving it to "invalidated".
 *
 * Legal from both "proposed" and "approved" — the backend returns a 400 from
 * any other status.
 */
export function useRejectPlan(planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<Plan> => {
      try {
        const { data } = await apiClient.post<Plan>(`/plans/${planId}/reject`);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not reject plan");
      }
    },
    onSuccess: (plan) => {
      queryClient.setQueryData(planQueryKey(planId), plan);
    },
  });
}
