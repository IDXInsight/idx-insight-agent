/** Pure helpers for the server-side proxy to the agent API (no secrets, testable without Next.js). */
import { isIP } from "node:net";

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
export function clientIp(headers: Headers, trustedVercelProxy = false): string | null {
  // In local/self-hosted deployments these headers are supplied by the caller.
  if (!trustedVercelProxy) return null;
  const candidates = [
    headers.get("x-vercel-forwarded-for"),
    headers.get("x-forwarded-for"),
  ];
  for (const value of candidates) {
    const first = value?.split(",")[0]?.trim();
    if (first && isIP(first)) return first;
  }
  return null;
}

/** Block browser requests from another origin before they can spend API/LLM credits. */
export function sameOriginRequest(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin" && site !== "none") return false;
  const origin = request.headers.get("origin");
  if (!origin) return true; // Non-browser clients do not set Origin.
  try {
    // Compare with the Host the browser addressed: `next dev` reports `request.url` as
    // localhost even when the page was opened on 127.0.0.1. Browsers cannot forge Host.
    const own = new URL(request.url);
    const host = request.headers.get("host") ?? own.host;
    return new URL(origin).origin === new URL(`${own.protocol}//${host}`).origin;
  } catch {
    return false;
  }
}

export class BodyTooLargeError extends Error {}

/** Streaming cap also covers chunked requests with a false/missing Content-Length. */
export async function limitedJsonBody(request: Request, maxBytes = 8192): Promise<unknown> {
  const declared = Number(request.headers.get("content-length"));
  if (declared > maxBytes) throw new BodyTooLargeError();
  if (!request.body) throw new SyntaxError("Missing JSON body");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        void reader.cancel();
        throw new BodyTooLargeError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

/** Maps a non-OK backend reply onto an error code the UI can explain. */
export function errorForBackend(status: number, body: unknown): ProxyError {
  const rawError = (body as { error?: unknown } | null)?.error;
  // Backend limits use a string code; Vercel Firewall uses an object such as
  // { error: { code: "429", ... } }.
  const code = typeof rawError === "string"
    ? rawError
    : (rawError as { code?: unknown } | null)?.code;
  if (status === 429) return code === "daily_limit" ? "daily_limit" : "rate_limited";
  if (status === 422) return "invalid_request";
  if (status === 503) return "backend_unavailable";
  return "backend_error";
}
