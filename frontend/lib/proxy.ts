/** Pure helpers for the server-side proxy to the agent API (no secrets, testable without Next.js). */

export type ProxyError =
  | "not_configured" | "invalid_request" | "backend_unavailable" | "timeout"
  | "rate_limited" | "daily_limit" | "backend_error";

/** HTTP status the proxy answers with for each error. */
export const proxyStatus: Record<ProxyError, number> = {
  not_configured: 503, invalid_request: 400, backend_unavailable: 502, timeout: 504,
  rate_limited: 429, daily_limit: 429, backend_error: 502,
};

/**
 * The visitor's IP as seen by Vercel. Vercel overwrites `x-forwarded-for` and sets
 * `x-vercel-forwarded-for` / `x-real-ip` itself, so these cannot be spoofed by the client.
 * Locally there is usually none; the backend then limits by the proxy's own address.
 */
export function clientIp(headers: Headers): string | null {
  const candidates = [
    headers.get("x-vercel-forwarded-for"),
    headers.get("x-real-ip"),
    headers.get("x-forwarded-for"),
  ];
  for (const value of candidates) {
    const first = value?.split(",")[0]?.trim();
    if (first && first.length <= 64 && /^[0-9a-fA-F.:]+$/.test(first)) return first;
  }
  return null;
}

/** Maps a non-OK backend reply onto an error code the UI can explain. */
export function errorForBackend(status: number, body: unknown): ProxyError {
  const code = (body as { error?: unknown } | null)?.error;
  if (status === 429) return code === "daily_limit" ? "daily_limit" : "rate_limited";
  if (status === 422) return "invalid_request";
  if (status === 503) return "backend_unavailable";
  return "backend_error";
}
