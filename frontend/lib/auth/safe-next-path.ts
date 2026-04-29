// Guards the `?next=...` query param on /login. The proxy at proxy.ts attaches
// this param when redirecting unauthenticated users; on successful login we
// honor it. Without this check, an attacker could craft `/login?next=https://evil.com`
// and a freshly-logged-in user gets phished.
//
// We accept ONLY relative paths (single leading "/", not "//" which is
// protocol-relative and would resolve to a different origin).

const RELATIVE_PATH = /^\/(?!\/)/;

export function safeNextPath(value: string | null): string {
  if (!value) return "/dashboard";
  if (!RELATIVE_PATH.test(value)) return "/dashboard";
  return value;
}
