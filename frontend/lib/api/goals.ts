"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import { toApiError } from "@/lib/api/errors";

/** Mirrors backend `GoalResponse` (app/schemas/goals.py).
 *
 * Dates arrive as strings, not Date objects: `target_date` is a bare
 * "YYYY-MM-DD" (pydantic `date`), while the timestamps are ISO-8601 with a
 * timezone (pydantic `datetime`). Parsing `target_date` with `new Date()`
 * would treat it as UTC midnight and shift the day in negative offsets, so it
 * stays a string all the way to the `<input type="date">`, which expects
 * exactly that format.
 */
export type Goal = {
  id: string;
  title: string;
  description: string | null;
  scope_type: "user" | "team" | "org";
  scope_id: string;
  success_metric_type: string | null;
  target_value: number | null;
  target_date: string | null;
  priority_weight: number;
  min_weekly_hours: number | null;
  max_weekly_hours: number | null;
  constraints: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

/** Body for POST /goals. Backend defaults scope to the current user. */
export type GoalCreateInput = {
  title: string;
  description: string | null;
  success_metric_type: string | null;
  target_value: number | null;
  target_date: string | null;
  priority_weight: number;
  min_weekly_hours: number | null;
  max_weekly_hours: number | null;
};

/** Body for PATCH /goals/{id}.
 *
 * The backend applies `model_dump(exclude_unset=True)`, so an omitted key is
 * left untouched while an explicit `null` clears the column. Keep this a
 * Partial so callers can express that difference.
 */
export type GoalUpdateInput = Partial<GoalCreateInput> & { is_active?: boolean };

export const goalsQueryKey = ["goals"] as const;

export function useGoals() {
  return useQuery({
    queryKey: goalsQueryKey,
    queryFn: async (): Promise<Goal[]> => {
      const { data } = await apiClient.get<Goal[]>("/goals");
      return data;
    },
  });
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: GoalCreateInput): Promise<Goal> => {
      try {
        const { data } = await apiClient.post<Goal>("/goals", input);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not create goal");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalsQueryKey });
    },
  });
}

export function useUpdateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: GoalUpdateInput & { id: string }): Promise<Goal> => {
      try {
        const { data } = await apiClient.patch<Goal>(`/goals/${id}`, input);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not update goal");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalsQueryKey });
    },
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      try {
        await apiClient.delete(`/goals/${id}`);
      } catch (error) {
        throw toApiError(error, "Could not delete goal");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: goalsQueryKey });
    },
  });
}
