"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiRequestError } from "@/lib/api/errors";
import type { PlanItem } from "@/lib/api/plans";
import { useCreateWorkLog } from "@/lib/api/worklogs";

import {
  toWorkLogPayload,
  workLogFormDefaults,
  workLogFormSchema,
  type WorkLogFormValues,
} from "../../_components/worklog-schema";

const inputClass =
  "rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900";

export function LogTimeForm({
  item,
  onClose,
}: {
  item: PlanItem;
  onClose: () => void;
}) {
  const [submitErrors, setSubmitErrors] = useState<string[]>([]);
  const createLog = useCreateWorkLog();

  const form = useForm<WorkLogFormValues>({
    resolver: zodResolver(workLogFormSchema),
    defaultValues: workLogFormDefaults(item),
  });

  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitErrors([]);
    const payload = toWorkLogPayload(item, values);
    if (payload === null) {
      setSubmitErrors(["Could not read those times."]);
      return;
    }
    try {
      await createLog.mutateAsync(payload);
      onClose();
    } catch (error) {
      setSubmitErrors(
        error instanceof ApiRequestError ? error.messages : ["Could not save work log"],
      );
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      aria-label={`Log time for ${item.task.title}`}
      className="mt-2 flex flex-col gap-2 border-t border-zinc-200 pt-2 dark:border-zinc-800"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={`start-${item.id}`} className="text-xs font-medium">
            Started
          </label>
          <input
            id={`start-${item.id}`}
            type="time"
            className={inputClass}
            {...form.register("start_time")}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor={`end-${item.id}`} className="text-xs font-medium">
            Ended
          </label>
          <input
            id={`end-${item.id}`}
            type="time"
            className={inputClass}
            {...form.register("end_time")}
          />
        </div>

        <label className="flex items-center gap-1.5 pb-1 text-xs">
          <input type="checkbox" {...form.register("completed")} />
          Finished it
        </label>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={`notes-${item.id}`} className="text-xs font-medium">
          Notes
        </label>
        <input
          id={`notes-${item.id}`}
          className={inputClass}
          placeholder="Optional"
          {...form.register("notes")}
        />
      </div>

      {(errors.start_time || errors.end_time || errors.notes) && (
        <p className="text-xs text-red-600">
          {errors.start_time?.message ??
            errors.end_time?.message ??
            errors.notes?.message}
        </p>
      )}

      {submitErrors.length > 0 && (
        <div
          role="alert"
          className="rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {submitErrors.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={createLog.isPending}
          className="rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {createLog.isPending ? "Saving…" : "Save log"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-zinc-300 px-3 py-1 text-xs dark:border-zinc-700"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
