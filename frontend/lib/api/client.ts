"use client";

import axios, { AxiosError } from "axios";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/proxy";

export const apiClient = axios.create({
  baseURL: BASE,
  headers: { Accept: "application/json" },
  withCredentials: false,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (
      typeof window !== "undefined" &&
      error.response?.status === 401 &&
      !window.location.pathname.startsWith("/login")
    ) {
      const next = encodeURIComponent(window.location.pathname);
      window.location.href = `/login?next=${next}`;
    }
    return Promise.reject(error);
  },
);

export type ApiErrorBody = { detail?: string | Record<string, unknown> };
