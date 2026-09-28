import { backendFetch, backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";
// One agent run makes several Sectors calls and optional LLM calls.
export const maxDuration = 120;

const TICKER = /^[A-Z]{4}$/;

type ProxyError = "not_configured" | "invalid_request" | "backend_unavailable" | "timeout" | "rate_limited" | "backend_error";

function fail(error: ProxyError, status: number): Response {
  return Response.json({ error }, { status });
}

/** Forwards a research question to `POST /v1/agent/query` after validating it. */
export async function POST(request: Request): Promise<Response> {
  if (!backendUrl()) return fail("not_configured", 503);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return fail("invalid_request", 400);
  }
  const { query, watchlist } = (body ?? {}) as { query?: unknown; watchlist?: unknown };
  if (typeof query !== "string" || query.trim().length < 3 || query.length > 500) {
    return fail("invalid_request", 400);
  }
  const tickers = Array.isArray(watchlist) ? watchlist : [];
  if (tickers.length > 20 || !tickers.every(t => typeof t === "string" && TICKER.test(t))) {
    return fail("invalid_request", 400);
  }

  const timeoutMs = Number(process.env.AGENT_TIMEOUT_MS) || 110_000;
  try {
    const response = await backendFetch("/v1/agent/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The UI is Indonesian; the backend returns the briefing in the requested language.
      body: JSON.stringify({ query: query.trim(), watchlist: tickers, language: "id" }),
    }, timeoutMs);
    if (response.status === 429) return fail("rate_limited", 429);
    if (response.status === 422) return fail("invalid_request", 400);
    if (!response.ok) return fail("backend_error", 502);
    return Response.json(await response.json());
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") return fail("timeout", 504);
    return fail("backend_unavailable", 502);
  }
}
