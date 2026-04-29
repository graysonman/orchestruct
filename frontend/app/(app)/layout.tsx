import { redirect } from "next/navigation";

import { apiFetch, ApiError } from "@/lib/api/server";
import type { CurrentUser } from "@/lib/api/auth";

import { AppHeader } from "./_components/app-header";

async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiFetch<CurrentUser>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader user={user} />
      <main className="flex flex-1 flex-col w-full max-w-5xl mx-auto px-6 py-8 gap-6">
        {children}
      </main>
    </div>
  );
}
