import { backendFetch, backendUrl } from "@/lib/backend";
import { type ProxyError, clientIp, errorForBackend, proxyStatus } from "@/lib/proxy";

export const dynamic = "force-dynamic";
// One agent run makes several Sectors calls and optional LLM calls.
export const maxDuration = 120;

const TICKER = /^[A-Z]{4}$/;

function fail(error: ProxyError): Response {
  return Response.json({ error }, { status: proxyStatus[error] });
}

/** Forwards a research question to `POST /v1/agent/query` after validating it. */
export async function POST(request: Request): Promise<Response> {
  if (!backendUrl()) return fail("not_configured");

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return fail("invalid_request");
  }
  const { query, watchlist, language } = (body ?? {}) as { query?: unknown; watchlist?: unknown; language?: unknown };
  if (typeof query !== "string" || query.trim().length < 3 || query.length > 500) {
    return fail("invalid_request");
  }
  const tickers = Array.isArray(watchlist) ? watchlist : [];
  if (tickers.length > 20 || !tickers.every(t => typeof t === "string" && TICKER.test(t))) {
    return fail("invalid_request");
  }
  if (language !== undefined && language !== "id" && language !== "en") return fail("invalid_request");

  const timeoutMs = Number(process.env.AGENT_TIMEOUT_MS) || 110_000;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // The backend limits agent runs per visitor; it trusts this header only with the shared secret.
  const ip = clientIp(request.headers);
  if (ip) headers["X-Client-IP"] = ip;
  try {
    const response = await backendFetch("/v1/agent/query", {
      method: "POST",
      headers,
      // The briefing follows the interface language the visitor chose (Indonesian by default).
      body: JSON.stringify({ query: query.trim(), watchlist: tickers, language: language ?? "id" }),
    }, timeoutMs);
    if (!response.ok) return fail(errorForBackend(response.status, await response.json().catch(() => null)));
    return Response.json(await response.json());
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") return fail("timeout");
    return fail("backend_unavailable");
  }
}
