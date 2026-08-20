"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import { toApiError } from "@/lib/api/errors";
import type { TaskSummary } from "@/lib/api/plans";

/** Mirrors backend `WorkLogResponse` (app/schemas/worklogs.py).
 *
 * `started_at` and `ended_at` are full timestamps, not the naive wall-clock
 * strings the plan endpoints return — the column is `DateTime(timezone=True)`,
 * so these carry an offset and `new Date()` is the correct way to read them.
 * That is the opposite of the rule for `scheduled_date` and `start_time` on a
 * plan item; the two APIs genuinely differ.
 *
 * `task` is embedded because a log stores only `task_id`, and there is no
 * endpoint that fetches a task without already knowing its goal.
 */
export type WorkLog = {
  id: string;
  task_id: string;
  user_id: string;
  started_at: string;
  ended_at: string | null;
  completed: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  task: TaskSummary;
};

/** Body for POST /worklogs.
 *
 * Timestamps go out as ISO strings with an offset. The backend rejects an
 * `ended_at` at or before `started_at` with a 422 carrying an `errors` list.
 */
export type WorkLogCreateInput = {
  task_id: string;
  started_at: string;
  ended_at: string | null;
  completed: boolean;
  notes: string | null;
};

/** Body for PATCH /worklogs/{id}.
 *
 * The backend applies `model_dump(exclude_unset=True)`, so an omitted key is
 * left untouched while an explicit null clears the column — the same contract
 * as the goal and task PATCH endpoints. Keep this a Partial so callers can
 * express that difference.
 */
export type WorkLogUpdateInput = Partial<{
  ended_at: string | null;
  completed: boolean;
  notes: string | null;
}>;

export const workLogsQueryKey = ["worklogs"] as const;

export function useWorkLogs() {
  return useQuery({
    queryKey: workLogsQueryKey,
    queryFn: async (): Promise<WorkLog[]> => {
      try {
        const { data } = await apiClient.get<WorkLog[]>("/worklogs");
        return data;
      } catch (error) {
        throw toApiError(error, "Could not load work logs");
      }
    },
  });
}

/** Record time against a task.
 *
 * Submitting a log recomputes the user's behavioral features server-side, so
 * this mutation invalidates `/metrics/me` as well as the log list — the
 * estimation bias shown anywhere on screen is stale the moment this succeeds.
 */
export function useCreateWorkLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: WorkLogCreateInput): Promise<WorkLog> => {
      try {
        const { data } = await apiClient.post<WorkLog>("/worklogs", input);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not save work log");
      }
    },
    onSuccess: () => {
      // Invalidate rather than seed: the list is server-ordered (newest first),
      // and one log is not a list.
      queryClient.invalidateQueries({ queryKey: workLogsQueryKey });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

/** Amend a log — in practice, closing one that was started without an end.
 *
 * A log with no `ended_at` contributes nothing to the learning loop, so this
 * is what makes timed work count. Recomputes features server-side, hence the
 * same pair of invalidations as create.
 */
export function useUpdateWorkLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: WorkLogUpdateInput & { id: string }): Promise<WorkLog> => {
      try {
        const { data } = await apiClient.patch<WorkLog>(`/worklogs/${id}`, input);
        return data;
      } catch (error) {
        throw toApiError(error, "Could not update work log");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workLogsQueryKey });
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}
