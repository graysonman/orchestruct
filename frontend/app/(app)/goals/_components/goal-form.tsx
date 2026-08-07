"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCreateGoal } from "@/lib/api/goals";

import {
  emptyGoalForm,
  goalFormSchema,
  toGoalPayload,
  type GoalFormValues,
} from "./goal-schema";

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

export function GoalForm() {
  const [open, setOpen] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const createGoal = useCreateGoal();

  const form = useForm<GoalFormValues>({
    resolver: zodResolver(goalFormSchema),
    defaultValues: emptyGoalForm,
  });

  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await createGoal.mutateAsync(toGoalPayload(values));
      // Reset before closing so a reopened form starts clean rather than
      // showing the previous goal's values.
      form.reset(emptyGoalForm);
      setOpen(false);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not create goal");
    }
  });

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        New goal
      </button>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-4 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800"
    >
      <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
        New goal
      </h2>

      <Field id="title" label="Title" error={errors.title?.message}>
        <input id="title" className={inputClass} {...form.register("title")} />
      </Field>

      <Field id="description" label="Description" error={errors.description?.message}>
        <textarea
          id="description"
          rows={3}
          className={inputClass}
          {...form.register("description")}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id="success_metric_type"
          label="Success metric"
          hint="What you are measuring, e.g. “words written”"
          error={errors.success_metric_type?.message}
        >
          <input
            id="success_metric_type"
            className={inputClass}
            {...form.register("success_metric_type")}
          />
        </Field>

        <Field
          id="target_value"
          label="Target value"
          error={errors.target_value?.message}
        >
          <input
            id="target_value"
            type="number"
            step="any"
            className={inputClass}
            {...form.register("target_value")}
          />
        </Field>

        <Field id="target_date" label="Target date" error={errors.target_date?.message}>
          <input
            id="target_date"
            type="date"
            className={inputClass}
            {...form.register("target_date")}
          />
        </Field>

        <Field
          id="priority_weight"
          label="Priority weight"
          hint="Higher competes harder for scheduled time"
          error={errors.priority_weight?.message}
        >
          <input
            id="priority_weight"
            type="number"
            step="any"
            className={inputClass}
            {...form.register("priority_weight")}
          />
        </Field>

        <Field
          id="min_weekly_hours"
          label="Min weekly hours"
          error={errors.min_weekly_hours?.message}
        >
          <input
            id="min_weekly_hours"
            type="number"
            step="any"
            className={inputClass}
            {...form.register("min_weekly_hours")}
          />
        </Field>

        <Field
          id="max_weekly_hours"
          label="Max weekly hours"
          error={errors.max_weekly_hours?.message}
        >
          <input
            id="max_weekly_hours"
            type="number"
            step="any"
            className={inputClass}
            {...form.register("max_weekly_hours")}
          />
        </Field>
      </div>

      {submitError && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {submitError}
        </p>
      )}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={createGoal.isPending}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {createGoal.isPending ? "Creating…" : "Create goal"}
        </button>
        <button
          type="button"
          onClick={() => {
            form.reset(emptyGoalForm);
            setSubmitError(null);
            setOpen(false);
          }}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
