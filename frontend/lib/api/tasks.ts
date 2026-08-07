"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";

import { apiClient, type ApiErrorBody } from "@/lib/api/client";

/** Mirrors backend `TaskResponse` (app/schemas/goals.py).
 *
 * `status` is a bare String(50) column, not an enum — see `taskStatus` in
 * app/(app)/goals/[goalId]/_components/task-status.ts for the vocabulary the
 * UI commits to and why it matters to the scheduler.
 */
export type Task = {
  id: string;
  goal_id: string;
  title: string;
  description: string | null;
  estimated_minutes: number | null;
  difficulty: number | null;
  due_date: string | null;
  dislike_score: number;
  owner_user_id: string | null;
  prerequisites: unknown[] | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type TaskCreateInput = {
  title: string;
  description: string | null;
  estimated_minutes: number | null;
  difficulty: number | null;
  due_date: string | null;
  dislike_score: number;
};

/** PATCH body. The backend applies `model_dump(exclude_unset=True)`, so an
 * omitted key is untouched while an explicit null clears the column. */
export type TaskUpdateInput = Partial<TaskCreateInput> & { status?: string };

/** Query key is goal-scoped: every task endpoint requires a goal_id, so caches
 * for two goals must never collide. */
export const tasksQueryKey = (goalId: string) => ["goals", goalId, "tasks"] as const;

function toError(error: unknown, fallback: string): Error {
  if (error instanceof AxiosError) {
    const data = error.response?.data as ApiErrorBody | undefined;
    if (typeof data?.detail === "string") return new Error(data.detail);
  }
  return error instanceof Error ? error : new Error(fallback);
}

export function useTasks(goalId: string) {
  return useQuery({
    queryKey: tasksQueryKey(goalId),
    queryFn: async (): Promise<Task[]> => {
      const { data } = await apiClient.get<Task[]>(`/goals/${goalId}/tasks`);
      return data;
    },
  });
}

export function useCreateTask(goalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: TaskCreateInput): Promise<Task> => {
      try {
        const { data } = await apiClient.post<Task>(`/goals/${goalId}/tasks`, input);
        return data;
      } catch (error) {
        throw toError(error, "Could not create task");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tasksQueryKey(goalId) });
    },
  });
}

export function useUpdateTask(goalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: TaskUpdateInput & { id: string }): Promise<Task> => {
      try {
        const { data } = await apiClient.patch<Task>(
          `/goals/${goalId}/tasks/${id}`,
          input,
        );
        return data;
      } catch (error) {
        throw toError(error, "Could not update task");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tasksQueryKey(goalId) });
    },
  });
}

export function useDeleteTask(goalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      try {
        await apiClient.delete(`/goals/${goalId}/tasks/${id}`);
      } catch (error) {
        throw toError(error, "Could not delete task");
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tasksQueryKey(goalId) });
    },
  });
}
