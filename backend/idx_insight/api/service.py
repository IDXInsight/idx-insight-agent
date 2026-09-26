"""Service layer between HTTP and the agent."""

from __future__ import annotations

from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.agent.state import AgentState
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
from idx_insight.sectors import SectorsAdapter, build_adapter


class AgentService:
    def __init__(self, settings: Settings, adapter: SectorsAdapter | None = None,
                 llm: LLMProvider | None = None) -> None:
        self.settings = settings
        self.adapter = adapter or build_adapter(settings)
        self.llm = llm if llm is not None else build_llm_provider(settings)
        self.agent = InsightAgent(self.adapter, llm=self.llm, settings=settings)

    def run(self, request: QueryRequest) -> AgentState:
        return self.agent.run(request.query, as_of=request.as_of, watchlist=request.watchlist,
                              sub_sector=request.sub_sector)

    def query(self, request: QueryRequest) -> QueryResponse:
        return to_response(self.run(request), data_source=self.adapter.name,
                           llm_provider=self.llm.name if self.llm else "none")


def to_response(state: AgentState, *, data_source: str, llm_provider: str) -> QueryResponse:
    assert state.briefing is not None
    hop = {d.event_id: d.decision for d in state.second_hop}
    accepted = set(state.validation.accepted)
    tf = state.timeframe
    return QueryResponse(
        status=state.status,
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
        ),
        recovery=state.recovery,
        trace=state.trace,
        tool_calls=[ToolCallOut(**c.model_dump(include=set(ToolCallOut.model_fields)))
                    for c in state.tool_calls],
    )
