"""Service layer between HTTP and the agent."""

from __future__ import annotations

from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.agent.state import AgentState
from idx_insight.api.guard import UsageGuard, UsageLimitError
from idx_insight.api.schemas import (
    ClaimOut,
    EventOut,
    QueryRequest,
    QueryResponse,
    Scope,
    ToolCallOut,
    ValidationOut,
)
from idx_insight.config import Settings
from idx_insight.llm import LLMProvider, build_llm_provider
from idx_insight.sectors import SectorsAdapter, SectorsError, build_adapter
from idx_insight.storage import KeyValueStore, MemoryStore, build_store


class AgentService:
    def __init__(self, settings: Settings, adapter: SectorsAdapter | None = None,
                 llm: LLMProvider | None = None, store: KeyValueStore | None = None) -> None:
        self.settings = settings
        shared = store if store is not None else build_store(settings)
        self.adapter = adapter or build_adapter(settings, shared)
        self.llm = llm if llm is not None else build_llm_provider(settings)
        self.agent = InsightAgent(self.adapter, llm=self.llm, settings=settings)
        self.rules_agent = InsightAgent(self.adapter, llm=None, settings=settings)
        self.guard = UsageGuard(shared if shared is not None else MemoryStore(), settings)

    def run(self, request: QueryRequest, *, use_llm: bool = True) -> AgentState:
        agent = self.agent if use_llm else self.rules_agent
        return agent.run(request.query, as_of=request.as_of, watchlist=request.watchlist,
                         sub_sector=request.sub_sector, language=request.language)

    def query(self, request: QueryRequest, client_id: str = "unknown") -> QueryResponse:
        """Answer from the cache, or admit and run the agent within the usage limits."""
        key = self.guard.answer_key(request)
        cached = self.guard.cached_answer(key)
        if cached is not None:
            return QueryResponse.model_validate_json(cached)
        self.guard.admit(client_id)
        self._check_credit_headroom()
        use_llm = self.llm is not None and self.guard.llm_allowed()
        state = self.run(request, use_llm=use_llm)
        self.guard.record_llm_calls(len(state.llm_calls))
        response = to_response(state, data_source=self.adapter.name,
                               llm_provider=self.llm.name if self.llm and use_llm else "none")
        if _cacheable(state):
            self.guard.store_answer(key, response.model_dump_json())
        return response

    def _check_credit_headroom(self) -> None:
        ledger = getattr(getattr(self.adapter, "client", None), "ledger", None)
        if ledger is None:
            return
        try:
            remaining = ledger.remaining_today()
        except SectorsError as exc:
            raise UsageLimitError("storage_unavailable", str(exc)) from None
        if remaining < self.settings.query_credit_headroom:
            raise UsageLimitError("daily_limit", "Sectors credit budget for today is used up")


def _cacheable(state: AgentState) -> bool:
    """Only answers whose data calls all succeeded; a transient failure must not be replayed."""
    return (state.status != "insufficient_evidence"
            and all(c.status in ("ok", "not_found") for c in state.tool_calls))


def to_response(state: AgentState, *, data_source: str, llm_provider: str) -> QueryResponse:
    assert state.briefing is not None
    hop = {d.event_id: d.decision for d in state.second_hop}
    accepted = set(state.validation.accepted)
    tf = state.timeframe
    return QueryResponse(
        status=state.status,
        language=state.language,
        data_source=data_source,
        llm_provider=llm_provider,
        briefing=state.briefing,
        scope=Scope(
            intent=state.intent.name if state.intent else None,
            intent_source=state.intent.source if state.intent else None,
            advice_requested=bool(state.intent and state.intent.advice_requested),
            companies=state.entities.symbols,
            ambiguous={a.text: a.candidates for a in state.entities.ambiguous},
            sub_sector=state.entities.sub_sector,
            timeframe=tf.model_dump(mode="json") if tf else None,
            plan=state.plan.names if state.plan else [],
            plan_source=state.plan.source if state.plan else None,
        ),
        events=[
            EventOut(**e.model_dump(include=set(EventOut.model_fields) - {"second_hop"}),
                     second_hop=hop.get(e.event_id))
            for e in state.relevant_events
        ],
        second_hop=state.second_hop,
        peer_comparison=state.analytics.get("peer_comparison", {}),
        claims=[ClaimOut(**c.model_dump(include=set(ClaimOut.model_fields)))
                for c in state.claims if c.claim_id in accepted],
        evidence=list(state.evidence.values()),
        validation=ValidationOut(
            status=state.validation.status,
            accepted=len(state.validation.accepted),
            rejected=len(state.validation.rejected),
            issues=state.validation.issues,
            assessment=state.validation.assessment,
        ),
        recovery=state.recovery,
        llm_calls=state.llm_calls,
        trace=state.trace,
        tool_calls=[ToolCallOut(**c.model_dump(include=set(ToolCallOut.model_fields)))
                    for c in state.tool_calls],
    )
