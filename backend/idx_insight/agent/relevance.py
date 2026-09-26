"""Relevance Engine and second-hop decisions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import SECOND_HOP_SYSTEM, second_hop_user_prompt
from idx_insight.agent.state import AgentState, RecoveryAction, SecondHopDecision
from idx_insight.analytics.events import (
    RELEVANT_THRESHOLD,
    SECOND_HOP_THRESHOLD,
    RelevanceContext,
    dedupe,
    event_density,
    score_event,
)
from idx_insight.analytics.metrics import EVENT_CONTEXT_METRICS
from idx_insight.llm.types import LLMToolDefinition
from idx_insight.models import Event

# Estimated tool calls to research one company (company report + quarterly financials).
SECOND_HOP_CALL_COST = 2

_JUSTIFICATION = {
    "dividend_ex": "Agenda dividen: tren laba dan ROE memberi konteks kapasitas pembagian dividen",
    "dividend_payment": "Agenda dividen: tren laba dan ROE memberi konteks kapasitas pembagian dividen",
    "agm": "RUPS dapat memutuskan penggunaan laba; kinerja terbaru memberi konteks",
    "stock_split": "Stock split: konteks kinerja membantu membaca aksi korporasi",
    "ownership_change": "Perubahan kepemilikan material: konteks kinerja keuangan terbaru",
}


def rank_events(state: AgentState, events: list[Event]) -> list[Event]:
    """Deduplicate, score and keep events at or above the relevance threshold."""
    unique, duplicates = dedupe(events)
    state.discovered_events = unique
    state.duplicate_events = duplicates
    ctx = RelevanceContext(
        watchlist=frozenset(state.watchlist) | frozenset(
            c.symbol for c in state.entities.companies if c.method != "sector_member"),
        density=event_density(unique),
    )
    scored = []
    for ev in unique:
        score, reasons = score_event(ev, ctx)
        scored.append(ev.model_copy(update={"relevance_score": score, "relevance_reasons": reasons}))
    state.discovered_events = scored
    relevant = [e for e in scored if e.relevance_score >= RELEVANT_THRESHOLD]
    relevant.sort(key=lambda e: (-e.relevance_score, e.event_date, e.symbol))
    state.relevant_events = relevant
    return relevant


class ContextRequest(BaseModel):
    """Arguments of the ``request_financial_context`` tool."""

    model_config = ConfigDict(extra="forbid")
    event_id: str


CONTEXT_TOOL = "request_financial_context"


def _llm_selection(state: AgentState, llm: AgentLLM) -> list[str] | None:
    """Event ids the LLM wants researched, in its order; None → use the rules."""
    candidates = state.relevant_events
    if not llm.enabled or not candidates:
        return None
    ids = [ev.event_id for ev in candidates]
    tool = LLMToolDefinition(
        name=CONTEXT_TOOL,
        description="Fetch the latest earnings growth and ROE of the company behind one "
                    "event, when that context is needed to explain why the event matters.",
        parameters={"type": "object", "properties": {"event_id": {"type": "string", "enum": ids}},
                    "required": ["event_id"], "additionalProperties": False},
    )
    lines = [f"{ev.event_id} | {ev.event_date} | {ev.symbol} | {ev.event_type} | "
             f"{ev.title} | skor {ev.relevance_score}" for ev in candidates]
    calls = llm.call_tools("second_hop", system=SECOND_HOP_SYSTEM,
                           user=second_hop_user_prompt(state.query, lines),
                           tools=[tool], args_schema={CONTEXT_TOOL: ContextRequest})
    if calls is None:
        return None
    requested = list(dict.fromkeys(args.event_id for _, args in calls))  # type: ignore[attr-defined]
    invalid = [i for i in requested if i not in ids]
    if invalid:
        state.add_trace("LLM second-hop request ignored",
                        f"{len(invalid)} id peristiwa di luar kandidat", "warning")
    return [i for i in requested if i in ids]


def decide_second_hop(state: AgentState, budget_remaining: int, max_companies: int,
                      llm: AgentLLM) -> list[str]:
    """Decide, per relevant event, whether deeper financial research is justified.

    With an LLM, the model chooses which events need context (via a tool call);
    without one, or if its reply is unusable, the score threshold decides. Either
    way the per-request company cap and the tool-call budget are enforced here.
    Returns the symbols to research; every decision is recorded with its reason.
    """
    selection = _llm_selection(state, llm)
    source = "rules" if selection is None else "llm"
    if selection is None:
        wanted = {ev.event_id for ev in state.relevant_events
                  if ev.relevance_score >= SECOND_HOP_THRESHOLD}
    else:
        wanted = set(selection)

    def decide(ev: Event, decision: str, reason: str, metrics: list[str] | None = None) -> None:
        state.second_hop.append(SecondHopDecision(
            event_id=ev.event_id, symbol=ev.symbol, decision=decision,  # type: ignore[arg-type]
            reason=reason, source=source, metrics=metrics or [],  # type: ignore[arg-type]
        ))

    researched: list[str] = []
    budget = budget_remaining
    for ev in state.relevant_events:
        if ev.event_id not in wanted:
            decide(ev, "skip", "LLM menilai konteks keuangan tidak diperlukan" if source == "llm"
                   else f"Skor relevansi {ev.relevance_score} di bawah ambang second-hop "
                        f"({SECOND_HOP_THRESHOLD})")
        elif ev.symbol in researched:
            decide(ev, "reuse", "Konteks keuangan emiten ini sudah diambil untuk peristiwa lain",
                   EVENT_CONTEXT_METRICS)
        elif len(researched) >= max_companies:
            decide(ev, "skip", f"Batas second-hop ({max_companies} emiten) tercapai")
        elif budget < SECOND_HOP_CALL_COST:
            decide(ev, "skip", "Sisa anggaran tool call tidak cukup")
            state.recovery.append(RecoveryAction(
                trigger="budget_exhausted", target=f"second-hop {ev.symbol}",
                action="Tidak melakukan riset lanjutan", outcome="Dicatat sebagai kesenjangan data",
            ))
            state.add_gap("budget_exhausted",
                          f"Konteks keuangan {ev.symbol} tidak diambil karena batas tool call.",
                          ev.symbol)
        else:
            budget -= SECOND_HOP_CALL_COST
            researched.append(ev.symbol)
            state.selected_events.append(ev.event_id)
            decide(ev, "research", _JUSTIFICATION[ev.event_type], EVENT_CONTEXT_METRICS)
    return researched
