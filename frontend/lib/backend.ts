/**
 * Server-only access to the FastAPI backend. The browser never talks to the backend
 * directly: requests go through the Next.js route handlers under `app/api/agent/`, so
 * no backend URL, API key or CORS configuration is exposed to the client.
 */
import "server-only";

/** Base URL of the FastAPI backend, e.g. `http://127.0.0.1:8000`; unset = example mode. */
export function backendUrl(): string | null {
  const url = process.env.IDX_INSIGHT_API_URL?.trim();
  return url ? url.replace(/\/+$/, "") : null;
}

/**
 * Calls the backend with the shared secret (`IDX_INSIGHT_API_SECRET`, the same value as on
 * the backend). The backend rejects every route except `/health` without it once it is set.
 */
export async function backendFetch(path: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const base = backendUrl();
  if (!base) throw new Error("backend not configured");
  const headers = new Headers(init.headers);
  const secret = process.env.IDX_INSIGHT_API_SECRET?.trim();
  if (secret) headers.set("X-Internal-Key", secret);
  return fetch(`${base}${path}`, { ...init, headers, cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
}
