"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";

import { useLogout, type CurrentUser } from "@/lib/api/auth";

import { AppNav } from "./app-nav";

export function AppHeader({ user }: { user: CurrentUser }) {
  const router = useRouter();
  const logout = useLogout();

  const onLogout = async () => {
    try {
      await logout.mutateAsync();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  };

  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="text-sm font-semibold tracking-tight">
            Orchestruct
          </Link>
          <AppNav />
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">
            {user.full_name ?? user.email}
          </span>
          <button
            type="button"
            onClick={onLogout}
            disabled={logout.isPending}
            className="rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            {logout.isPending ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </div>
    </header>
  );
}
