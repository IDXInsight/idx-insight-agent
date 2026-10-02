"""FastAPI application.

Request-oriented and stateless between requests (each query gets its own
SectorsService, cache and AgentState), so it runs as a serverless function on
Vercel without changes to the agent. Shared state across requests (credit ledger,
caches, usage counters) lives in Redis there.

Only the Next.js server calls this API: when ``IDX_INSIGHT_API_SECRET`` is set, every
route except ``/health`` requires it in the ``X-Internal-Key`` header, and on Vercel
the API refuses to serve without it.
"""

from __future__ import annotations

import hmac
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from idx_insight import __version__
from idx_insight.agent.planner import ALLOWED
from idx_insight.analytics.metrics import BUNDLES, DIRECTION, KNOWN_UNSUPPORTED, METRICS
from idx_insight.api.guard import UsageLimitError
from idx_insight.api.schemas import QueryRequest, QueryResponse
from idx_insight.api.service import AgentService
from idx_insight.config import Settings, load_env_file
from idx_insight.llm.errors import LLMConfigurationError
from idx_insight.sectors.adapter import SectorsError
from idx_insight.sectors.service import DEFAULT_ALLOWLIST


@lru_cache
def get_settings() -> Settings:
    load_env_file()  # local development; real environment variables take precedence
    return Settings.from_env()


@lru_cache
def _build_service(settings: Settings) -> AgentService:
    return AgentService(settings)


def get_agent_service(settings: Settings = Depends(get_settings)) -> AgentService:
    if problems := settings.deployment_problems():
        raise HTTPException(status_code=503, detail="; ".join(problems))
    try:
        return _build_service(settings)
    except (SectorsError, LLMConfigurationError) as exc:
        # Messages name the missing setting only; they never contain secret values.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app = FastAPI(
    title="IDX Insight Agent API",
    version=__version__,
    description="Research and discovery agent on Sectors data. Not investment advice.",
)


_LIMIT_STATUS = {"rate_limited": 429, "daily_limit": 429, "storage_unavailable": 503}


def _current_settings() -> Settings:
    # Middleware runs outside dependency injection; honour test overrides all the same.
    return app.dependency_overrides.get(get_settings, get_settings)()


@app.middleware("http")
async def require_internal_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    settings = _current_settings()
    key = settings.internal_api_key
    if key is None:
        if settings.vercel:
            return JSONResponse({"error": "not_configured"}, status_code=503)
        return await call_next(request)  # local development without a secret
    given = request.headers.get("x-internal-key", "")
    if not hmac.compare_digest(given.encode(), key.get_secret_value().encode()):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.exception_handler(UsageLimitError)
async def usage_limit(_: Request, exc: UsageLimitError) -> JSONResponse:
    return JSONResponse({"error": exc.code, "detail": str(exc)}, status_code=_LIMIT_STATUS[exc.code])


def client_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    """The end user's IP as forwarded by the Next.js server; trusted only behind the secret."""
    forwarded = request.headers.get("x-client-ip", "").strip()
    if settings.internal_api_key is not None and forwarded:
        return forwarded[:64]
    return request.client.host if request.client else "unknown"


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "version": __version__, "data_mode": settings.sectors_data_mode,
            "llm_provider": settings.llm_provider, "llm_model": settings.llm_model}


@app.get("/v1/capabilities")
def capabilities(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "data_mode": settings.sectors_data_mode,
        "llm_provider": settings.llm_provider,
        "llm_providers_supported": ["none", "gemini", "groq"],
        "languages": ["id", "en"],
        "sectors_tools": sorted(DEFAULT_ALLOWLIST),
        "intents": sorted(ALLOWED),
        "metrics": {name: {"id": spec.label_in("id"), "en": spec.label_in("en"),
                           "direction": DIRECTION.get(name)}
                    for name, spec in METRICS.items()},
        "metric_bundles": BUNDLES,
        "unsupported_metrics": sorted(KNOWN_UNSUPPORTED.values()),
        "limits": {
            "max_tool_calls": settings.max_tool_calls,
            "max_second_hop": settings.max_second_hop,
            "max_requeries": settings.max_requeries,
        },
    }


@app.post("/v1/agent/query", response_model=QueryResponse)
def agent_query(request: QueryRequest,
                service: AgentService = Depends(get_agent_service),
                client: str = Depends(client_id)) -> QueryResponse:
    return service.query(request, client_id=client)
