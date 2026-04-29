"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Scope =
  | { type: "user"; userId: string }
  | { type: "team"; teamId: string };

type ScopeState = {
  current: Scope | null;
  setScope: (scope: Scope) => void;
  clearScope: () => void;
};

export const useScopeStore = create<ScopeState>()(
  persist(
    (set) => ({
      current: null,
      setScope: (scope) => set({ current: scope }),
      clearScope: () => set({ current: null }),
    }),
    { name: "orchestruct.scope" },
  ),
);

export function scopeQueryParams(scope: Scope | null): Record<string, string> {
  if (!scope || scope.type !== "team") return {};
  return { team_id: scope.teamId };
}
