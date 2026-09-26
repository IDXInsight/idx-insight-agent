"""Relevance Engine and second-hop decisions."""

from __future__ import annotations

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


def decide_second_hop(state: AgentState, budget_remaining: int, max_companies: int) -> list[str]:
    """Decide, per relevant event, whether deeper financial research is justified.

    Returns the symbols to research. Every decision is recorded with its reason.
    """
    researched: list[str] = []
    budget = budget_remaining
    for ev in state.relevant_events:
        if ev.relevance_score < SECOND_HOP_THRESHOLD:
            state.second_hop.append(SecondHopDecision(
                event_id=ev.event_id, symbol=ev.symbol, decision="skip",
                reason=f"Skor relevansi {ev.relevance_score} di bawah ambang second-hop "
                       f"({SECOND_HOP_THRESHOLD})",
            ))
            continue
        if ev.symbol in researched:
            state.second_hop.append(SecondHopDecision(
                event_id=ev.event_id, symbol=ev.symbol, decision="reuse",
                reason="Konteks keuangan emiten ini sudah diambil untuk peristiwa lain",
                metrics=EVENT_CONTEXT_METRICS,
            ))
            continue
        if len(researched) >= max_companies:
            state.second_hop.append(SecondHopDecision(
                event_id=ev.event_id, symbol=ev.symbol, decision="skip",
                reason=f"Batas second-hop ({max_companies} emiten) tercapai",
            ))
            continue
        if budget < SECOND_HOP_CALL_COST:
            state.second_hop.append(SecondHopDecision(
                event_id=ev.event_id, symbol=ev.symbol, decision="skip",
                reason="Sisa anggaran tool call tidak cukup",
            ))
            state.recovery.append(RecoveryAction(
                trigger="budget_exhausted", target=f"second-hop {ev.symbol}",
                action="Tidak melakukan riset lanjutan", outcome="Dicatat sebagai kesenjangan data",
            ))
            state.add_gap("budget_exhausted",
                          f"Konteks keuangan {ev.symbol} tidak diambil karena batas tool call.",
                          ev.symbol)
            continue
        budget -= SECOND_HOP_CALL_COST
        researched.append(ev.symbol)
        state.selected_events.append(ev.event_id)
        state.second_hop.append(SecondHopDecision(
            event_id=ev.event_id, symbol=ev.symbol, decision="research",
            reason=_JUSTIFICATION[ev.event_type], metrics=EVENT_CONTEXT_METRICS,
        ))
    return researched
