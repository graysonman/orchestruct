export default function Home() {
  return (
    <main className="flex flex-1 w-full max-w-3xl mx-auto flex-col gap-6 px-8 py-24">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-semibold tracking-tight">Orchestruct</h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Autonomous goal-driven planning engine.
        </p>
      </header>
      <section className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-6 flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Frontend status
        </h2>
        <p className="text-sm">
          Phase 1 scaffolding complete. Auth, goals, plans, and the calendar
          surface arrive in subsequent phases.
        </p>
        <ul className="text-sm text-zinc-600 dark:text-zinc-400 list-disc pl-5 space-y-1">
          <li>Next.js 16 App Router + TanStack Query + Zustand wired.</li>
          <li>
            <code className="text-xs">/api/proxy/[...path]</code> forwards to
            FastAPI with the session JWT attached server-side.
          </li>
          <li>
            Run <code className="text-xs">npm run gen:types</code> with the
            backend up to populate <code className="text-xs">types/api.ts</code>.
          </li>
        </ul>
      </section>
    </main>
  );
}
