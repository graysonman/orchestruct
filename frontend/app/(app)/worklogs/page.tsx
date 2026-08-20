import { WorkLogList } from "./_components/worklog-list";

export const metadata = { title: "Work log · Orchestruct" };

export default function WorkLogsPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Work log</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          What actually happened. Each finished entry is compared against the
          task’s estimate, and the difference adjusts how much time future plans
          set aside.
        </p>
      </header>

      <WorkLogList />
    </section>
  );
}
