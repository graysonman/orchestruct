"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios, { AxiosError } from "axios";

import { apiClient, type ApiErrorBody } from "@/lib/api/client";

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
};

export const meQueryKey = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<CurrentUser | null> => {
      try {
        const { data } = await apiClient.get<CurrentUser>("/auth/me");
        return data;
      } catch (error) {
        if (error instanceof AxiosError && error.response?.status === 401) {
          return null;
        }
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

type LoginInput = { email: string; password: string };
type RegisterInput = { email: string; password: string; full_name?: string };

async function postAuth(path: string, body: unknown): Promise<void> {
  try {
    await axios.post(path, body, {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    if (error instanceof AxiosError) {
      const data = error.response?.data as ApiErrorBody | undefined;
      const message =
        typeof data?.detail === "string" ? data.detail : "Request failed";
      throw new Error(message);
    }
    throw error;
  }
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: LoginInput) => postAuth("/api/auth/login", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: meQueryKey });
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RegisterInput) => postAuth("/api/auth/register", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: meQueryKey });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postAuth("/api/auth/logout", {}),
    onSuccess: () => {
      queryClient.setQueryData(meQueryKey, null);
      queryClient.clear();
    },
  });
}
