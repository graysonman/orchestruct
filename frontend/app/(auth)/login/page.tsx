"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useLogin } from "@/lib/api/auth";
import { safeNextPath } from "@/lib/auth/safe-next-path";

const loginSchema = z.object({
  email: z.email("Invalid Email Format"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

/** Messages for the `?error=` codes set by the Google OAuth routes.
 *
 * Lookup is by exact key, so an unrecognized `?error=` value renders nothing
 * rather than being echoed back into the page.
 */
const OAUTH_ERRORS: Record<string, string> = {
  google_denied: "Google sign-in was cancelled.",
  google_failed: "Google sign-in failed. Please try again.",
  google_no_code: "Google sign-in did not complete. Please try again.",
  google_unreachable: "Could not reach the server. Please try again.",
  google_rejected: "Google sign-in was rejected. Please try again.",
  google: "Google sign-in is unavailable right now.",
};

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNextPath(searchParams.get("next"));
  const [submitError, setSubmitError] = useState<string | null>(null);

  const oauthError = OAUTH_ERRORS[searchParams.get("error") ?? ""];

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

      {oauthError && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300"
        >
          {oauthError}
        </p>
      )}

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

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
        <span className="text-xs text-zinc-500">or</span>
        <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
      </div>

      {/* Plain <a>, not next/link: this must be a full-page navigation to a
          route handler that 302s to accounts.google.com. next/link prefetches
          on hover, which would start an OAuth flow the user never clicked. */}
      <a
        href="/api/auth/google"
        className="flex items-center justify-center gap-2 rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
      >
        <svg aria-hidden="true" viewBox="0 0 18 18" className="h-4 w-4">
          <path
            fill="#4285F4"
            d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
          />
          <path
            fill="#34A853"
            d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
          />
          <path
            fill="#FBBC05"
            d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
          />
          <path
            fill="#EA4335"
            d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
          />
        </svg>
        Continue with Google
      </a>

      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Need an account?{" "}
        <Link href="/register" className="underline">
          Register
        </Link>
      </p>
    </section>
  );
}

/** `useSearchParams` opts a client component out of static prerendering, so
 * Next requires a Suspense boundary above it or `next build` fails on this
 * route. The boundary lets the shell prerender while the params resolve on the
 * client.
 */
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
