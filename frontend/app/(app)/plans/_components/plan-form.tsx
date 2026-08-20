"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiRequestError } from "@/lib/api/errors";
import { useGeneratePlan } from "@/lib/api/plans";

import {
  defaultPlanForm,
  planFormSchema,
  toPlanPayload,
  type PlanFormValues,
} from "./plan-schema";

const inputClass =
  "rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-zinc-500">{hint}</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function PlanForm() {
  const router = useRouter();
  // A list, not a string: the scheduler reports every reason it could not build
  // a plan at once, and collapsing them would hide all but the first.
  const [submitErrors, setSubmitErrors] = useState<string[]>([]);
  const generatePlan = useGeneratePlan();

  const form = useForm<PlanFormValues>({
    resolver: zodResolver(planFormSchema),
    defaultValues: defaultPlanForm(),
  });

  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitErrors([]);
    try {
      const plan = await generatePlan.mutateAsync(toPlanPayload(values));
      // The mutation already seeded the cache under this plan's key, so the
      // detail page renders from memory instead of re-fetching.
      router.push(`/plans/${plan.id}`);
    } catch (error) {
      setSubmitErrors(
        error instanceof ApiRequestError
          ? error.messages
          : ["Could not generate plan"],
      );
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-4 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
        New plan
      </h2>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id="planning_window_start"
          label="From"
          error={errors.planning_window_start?.message}
        >
          <input
            id="planning_window_start"
            type="date"
            className={inputClass}
            {...form.register("planning_window_start")}
          />
        </Field>

        <Field
          id="planning_window_end"
          label="To"
          hint="Pending tasks are fitted into your free time in this window"
          error={errors.planning_window_end?.message}
        >
          <input
            id="planning_window_end"
            type="date"
            className={inputClass}
            {...form.register("planning_window_end")}
          />
        </Field>
      </div>

      {submitErrors.length > 0 && (
        <div
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {submitErrors.length === 1 ? (
            <p>{submitErrors[0]}</p>
          ) : (
            <ul className="list-disc space-y-1 pl-4">
              {submitErrors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={generatePlan.isPending}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {generatePlan.isPending ? "Generating…" : "Generate plan"}
      </button>
    </form>
  );
}
