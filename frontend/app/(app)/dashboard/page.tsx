import { apiFetch } from "@/lib/api/server";
import type { CurrentUser } from "@/lib/api/auth";

export default async function DashboardPage() {
  const user = await apiFetch<CurrentUser>("/auth/me");

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Signed in as {user.email}.
        </p>
      </header>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-6 flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Phase 2 status
        </h2>
        <p className="text-sm">
          Auth is wired. Goals, plans, and the calendar arrive in subsequent phases.
        </p>
        <ul className="text-sm text-zinc-600 dark:text-zinc-400 list-disc pl-5 space-y-1">
          <li>Session cookie set by <code className="text-xs">/api/auth/login</code></li>
          <li>Server-side fetch reads the cookie via <code className="text-xs">cookies()</code></li>
          <li>Logout button calls <code className="text-xs">/api/auth/logout</code> and clears React Query cache</li>
        </ul>
      </div>
    </section>
  );
}
