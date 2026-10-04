import { backendFetch, backendUrl } from "@/lib/backend";
import { BodyTooLargeError, type ProxyError, clientIp, errorForBackend, limitedJsonBody, proxyStatus, sameOriginRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";
// One agent run makes several Sectors calls and optional LLM calls.
export const maxDuration = 120;

const TICKER = /^[A-Z]{4}$/;

function fail(error: ProxyError): Response {
  return Response.json({ error }, { status: proxyStatus[error], headers: { "Cache-Control": "no-store" } });
}

/** Forwards a research question to `POST /v1/agent/query` after validating it. */
export async function POST(request: Request): Promise<Response> {
  if (!sameOriginRequest(request)) return fail("invalid_request");
  if (request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") {
    return fail("invalid_request");
  }
  if (!backendUrl()) return fail("not_configured");

  let body: unknown;
  try {
    body = await limitedJsonBody(request);
  } catch (error) {
    if (error instanceof BodyTooLargeError) {
      return Response.json({ error: "invalid_request" }, { status: 413, headers: { "Cache-Control": "no-store" } });
    }
    return fail("invalid_request");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) return fail("invalid_request");
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
  const ip = clientIp(request.headers, process.env.VERCEL === "1");
  if (ip) headers["X-Client-IP"] = ip;
  try {
    const response = await backendFetch("/v1/agent/query", {
      method: "POST",
      headers,
      // Without a language the backend detects it from the question (Indonesian or English).
      body: JSON.stringify({ query: query.trim(), watchlist: tickers, ...(language ? { language } : {}) }),
    }, timeoutMs);
    if (!response.ok) return fail(errorForBackend(response.status, await response.json().catch(() => null)));
    return Response.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") return fail("timeout");
    return fail("backend_unavailable");
  }
}
