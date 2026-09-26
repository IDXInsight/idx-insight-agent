"""FastAPI application.

Request-oriented and stateless between requests (each query gets its own
SectorsService, cache and AgentState), so it can later run as a serverless
function on Vercel without changes to the agent.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from idx_insight import __version__
from idx_insight.agent.planner import ALLOWED
from idx_insight.analytics.metrics import BUNDLES, KNOWN_UNSUPPORTED, METRICS
from idx_insight.api.schemas import QueryRequest, QueryResponse
from idx_insight.api.service import AgentService
from idx_insight.config import Settings, load_env_file
from idx_insight.llm.errors import LLMConfigurationError
from idx_insight.sectors.service import DEFAULT_ALLOWLIST


@lru_cache
def get_settings() -> Settings:
    load_env_file()  # local development; real environment variables take precedence
    return Settings.from_env()


@lru_cache
def _build_service(settings: Settings) -> AgentService:
    return AgentService(settings)


def get_agent_service(settings: Settings = Depends(get_settings)) -> AgentService:
    try:
        return _build_service(settings)
    except (NotImplementedError, LLMConfigurationError) as exc:
        # Messages name the missing setting only; they never contain secret values.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app = FastAPI(
    title="IDX Insight Agent API",
    version=__version__,
    description="Research and discovery agent on Sectors data. Not investment advice.",
)


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
        "sectors_tools": sorted(DEFAULT_ALLOWLIST),
        "intents": sorted(ALLOWED),
        "metrics": {name: spec.label for name, spec in METRICS.items()},
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
                service: AgentService = Depends(get_agent_service)) -> QueryResponse:
    return service.query(request)
