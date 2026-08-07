"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Only routes with a real page belong here.
 *
 * proxy.ts pre-registers /tasks, /plans, /calendar and others in its matcher so
 * they are guarded the moment they exist — but linking to one before its
 * page.tsx lands gives a 404 behind an auth check, which reads as a broken
 * session. Add an entry here when the page ships, not when the route is
 * reserved.
 */
const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/goals", label: "Goals" },
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main" className="flex items-center gap-1">
      {NAV_ITEMS.map(({ href, label }) => {
        // Prefix match so nested routes (/goals/123) keep the parent lit, but
        // guard the boundary or /goals-archive would also match /goals.
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-2 py-1 text-sm ${
              active
                ? "bg-zinc-100 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
