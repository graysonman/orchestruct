"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useCreateTask } from "@/lib/api/tasks";

/** Same string-first approach as goalFormSchema: uncontrolled inputs always
 * produce strings, so parsing happens once on submit. */
const taskFormSchema = z
  .object({
    title: z.string().trim().min(1, "Title is required").max(255, "Title is too long"),
    description: z.string().trim().max(2000, "Description is too long"),
    estimated_minutes: z.string(),
    difficulty: z.string(),
    due_date: z.string(),
    dislike_score: z.string(),
  })
  .superRefine((values, ctx) => {
    const numeric = [
      { key: "estimated_minutes", label: "Estimate", min: 1, max: 100_000 },
      { key: "difficulty", label: "Difficulty", min: 1, max: 5 },
      { key: "dislike_score", label: "Dislike score", min: 0, max: 5 },
    ] as const;

    for (const { key, label, min, max } of numeric) {
      const raw = values[key].trim();
      if (raw === "") continue;
      const parsed = Number(raw);
      // NaN fails every comparison, so it needs its own branch or it slips
      // through both bounds checks below.
      if (Number.isNaN(parsed)) {
        ctx.addIssue({ code: "custom", path: [key], message: `${label} must be a number` });
        continue;
      }
      if (!Number.isInteger(parsed)) {
        ctx.addIssue({ code: "custom", path: [key], message: `${label} must be a whole number` });
        continue;
      }
      if (parsed < min || parsed > max) {
        ctx.addIssue({
          code: "custom",
          path: [key],
          message: `${label} must be between ${min} and ${max}`,
        });
      }
    }
  });

type TaskFormValues = z.infer<typeof taskFormSchema>;

const emptyTaskForm: TaskFormValues = {
  title: "",
  description: "",
  estimated_minutes: "",
  difficulty: "",
  due_date: "",
  dislike_score: "",
};

function parseIntOrNull(raw: string): number | null {
  const trimmed = raw.trim();
  return trimmed === "" ? null : Number(trimmed);
}

const inputClass =
  "rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export function TaskForm({ goalId }: { goalId: string }) {
  const [open, setOpen] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const createTask = useCreateTask(goalId);

  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: emptyTaskForm,
  });

  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await createTask.mutateAsync({
        title: values.title.trim(),
        description: values.description.trim() || null,
        estimated_minutes: parseIntOrNull(values.estimated_minutes),
        difficulty: parseIntOrNull(values.difficulty),
        due_date: values.due_date.trim() || null,
        // Backend defaults this to 0 and types it non-null, so blank means 0
        // rather than "unset".
        dislike_score: parseIntOrNull(values.dislike_score) ?? 0,
      });
      form.reset(emptyTaskForm);
      setOpen(false);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Could not create task");
    }
  });

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        Add task
      </button>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="flex flex-col gap-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor="task-title" className="text-sm font-medium">
          Title
        </label>
        <input id="task-title" className={inputClass} {...form.register("title")} />
        {errors.title && <p className="text-xs text-red-600">{errors.title.message}</p>}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="task-description" className="text-sm font-medium">
          Description
        </label>
        <textarea
          id="task-description"
          rows={2}
          className={inputClass}
          {...form.register("description")}
        />
        {errors.description && (
          <p className="text-xs text-red-600">{errors.description.message}</p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="task-estimate" className="text-sm font-medium">
            Estimate (minutes)
          </label>
          <input
            id="task-estimate"
            type="number"
            className={inputClass}
            {...form.register("estimated_minutes")}
          />
          {errors.estimated_minutes && (
            <p className="text-xs text-red-600">{errors.estimated_minutes.message}</p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="task-due" className="text-sm font-medium">
            Due date
          </label>
          <input
            id="task-due"
            type="date"
            className={inputClass}
            {...form.register("due_date")}
          />
          {errors.due_date && (
            <p className="text-xs text-red-600">{errors.due_date.message}</p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="task-difficulty" className="text-sm font-medium">
            Difficulty (1–5)
          </label>
          <input
            id="task-difficulty"
            type="number"
            className={inputClass}
            {...form.register("difficulty")}
          />
          {errors.difficulty && (
            <p className="text-xs text-red-600">{errors.difficulty.message}</p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="task-dislike" className="text-sm font-medium">
            Dislike score (0–5)
          </label>
          <input
            id="task-dislike"
            type="number"
            className={inputClass}
            {...form.register("dislike_score")}
          />
          {errors.dislike_score && (
            <p className="text-xs text-red-600">{errors.dislike_score.message}</p>
          )}
        </div>
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
          disabled={createTask.isPending}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {createTask.isPending ? "Adding…" : "Add task"}
        </button>
        <button
          type="button"
          onClick={() => {
            form.reset(emptyTaskForm);
            setSubmitError(null);
            setOpen(false);
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
