import { cookies } from "next/headers";
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const SESSION_COOKIE = "session";
const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";
const API_VERSION_PREFIX = "/api/v1";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "te",
  "trailer",
  "proxy-authenticate",
  "proxy-authorization",
  "host",
  "content-length",
  "cookie",
]);

async function proxy(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  const upstreamPath = path.join("/");
  const search = request.nextUrl.search;
  const upstreamUrl = `${FASTAPI_URL}${API_VERSION_PREFIX}/${upstreamPath}${search}`;

  const forwardHeaders = new Headers();
  for (const [key, value] of request.headers.entries()) {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      forwardHeaders.set(key, value);
    }
  }
  if (token) {
    forwardHeaders.set("Authorization", `Bearer ${token}`);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method);

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers: forwardHeaders,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return Response.json(
      { detail: "Upstream unreachable" },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  for (const [key, value] of upstream.headers.entries()) {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  }

  if (upstream.status === 401 && token) {
    cookieStore.delete(SESSION_COOKIE);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
