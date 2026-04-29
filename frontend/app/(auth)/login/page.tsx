"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useLogin } from "@/lib/api/auth";
import { safeNextPath } from "@/lib/auth/safe-next-path";

const loginSchema = z.object({
  email: z.email("Invalid Email Format"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));
  const [submitError, setSubmitError] = useState<string | null>(null);

  const login = useLogin();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await login.mutateAsync(values);
      router.replace(next);
      router.refresh();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Login failed");
    }
  });

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Welcome back to Orchestruct.
        </p>
      </header>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            {...form.register("email")}
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          {form.formState.errors.email && (
            <p className="text-xs text-red-600">
              {form.formState.errors.email.message}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            {...form.register("password")}
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          {form.formState.errors.password && (
            <p className="text-xs text-red-600">
              {form.formState.errors.password.message}
            </p>
          )}
        </div>

        {submitError && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300">
            {submitError}
          </p>
        )}

        <button
          type="submit"
          disabled={form.formState.isSubmitting || login.isPending}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Need an account?{" "}
        <Link href="/register" className="underline">
          Register
        </Link>
      </p>
    </section>
  );
}
