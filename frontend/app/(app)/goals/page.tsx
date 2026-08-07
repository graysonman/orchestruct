import { GoalForm } from "./_components/goal-form";
import { GoalList } from "./_components/goal-list";

export const metadata = { title: "Goals · Orchestruct" };

export default function GoalsPage() {
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Goals</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          What you are working toward. The scheduler allocates time against
          these.
        </p>
      </header>

      <GoalForm />
      <GoalList />
    </section>
  );
}
