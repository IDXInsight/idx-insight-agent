"""Synthesis: validated claims → briefing.

The structured briefing is always assembled deterministically from accepted
claims. When an LLM is available it may add a short narrative, which is kept
only if it passes the grounding guard (no advice language, no numbers that are
absent from the validated facts).
"""

from __future__ import annotations

import re

from idx_insight.agent.prompts import SYNTHESIS_SYSTEM, synthesis_user_prompt
from idx_insight.agent.state import AgentState, Briefing, BriefingSection, Finding
from idx_insight.analytics.metrics import METRICS
from idx_insight.llm.base import LLMClient

BOUNDARY_NOTE = ("Informasi faktual untuk riset berbasis data Sectors — bukan rekomendasi beli, "
                 "jual, atau tahan.")
ADVICE_NOTE = ("Pertanyaan Anda menyentuh keputusan investasi. Agen ini tidak memberi rekomendasi; "
               "berikut konteks faktual yang dapat Anda pertimbangkan sendiri.")

_ADVICE_OUT = re.compile(
    r"\b(beli|jual|tahan|hold|buy|sell|akumulasi|serok|target harga|price target|"
    r"direkomendasikan|sebaiknya|disarankan|overweight|underweight|undervalued|overvalued)\b",
    re.IGNORECASE,
)
_ALLOWED_NEGATIONS = re.compile(r"\bbukan (rekomendasi|saran)[^.]*", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def guard_narrative(text: str, facts: list[str], extra_context: str = "") -> str | None:
    """Return the reason the narrative is rejected, or None if it is grounded."""
    scrubbed = _ALLOWED_NEGATIONS.sub("", text)
    if m := _ADVICE_OUT.search(scrubbed):
        return f"advice language: {m.group(0)!r}"
    allowed = set(_NUMBER.findall(" ".join(facts) + " " + extra_context))
    for token in _NUMBER.findall(text):
        if token in allowed or (token.isdigit() and int(token) <= 10):
            continue
        return f"ungrounded number: {token}"
    return None


def _findings(state: AgentState, section: str) -> list[Finding]:
    accepted = set(state.validation.accepted)
    return [Finding(text=c.statement, claim_ids=[c.claim_id]) for c in state.claims
            if c.claim_id in accepted and c.meta.get("section") == section]


def _event_findings(state: AgentState) -> list[Finding]:
    accepted = set(state.validation.accepted)
    out = []
    for c in state.claims:
        if c.claim_id not in accepted or c.meta.get("section") != "events":
            continue
        why = "; ".join(c.meta.get("reasons", []))
        out.append(Finding(text=f"{c.statement} — relevan karena: {why} "
                                f"(skor {c.meta.get('score')})", claim_ids=[c.claim_id]))
    return out


def _second_hop_findings(state: AgentState) -> list[Finding]:
    out = _findings(state, "second_hop")
    for d in state.second_hop:
        if d.decision == "research":
            out.append(Finding(text=f"Riset lanjutan {d.symbol}: {d.reason}", claim_ids=[]))
    return out


def _summary(state: AgentState) -> str:
    intent = state.intent.name if state.intent else "clarify"
    tf = state.timeframe
    if intent == "discovery":
        scope = state.entities.sub_sector or ", ".join(state.entities.symbols)
        return (f"{len(state.relevant_events)} peristiwa relevan dari "
                f"{len(state.discovered_events)} peristiwa unik "
                f"({len(state.duplicate_events)} duplikat dihapus) untuk {scope}, "
                f"{tf.label if tf else ''}; {len(state.selected_events)} peristiwa "
                f"mendapat riset keuangan lanjutan.")
    if intent == "peer_comparison":
        metrics = ", ".join(METRICS[m].label for m in state.analytics.get("peer_comparison", {}))
        return (f"Perbandingan {', '.join(state.entities.symbols)} untuk {metrics} "
                f"berdasarkan data Sectors.")
    return f"Konteks keuangan dan peristiwa {', '.join(state.entities.symbols)}."


def _data_gap_lines(state: AgentState) -> list[str]:
    lines = [g.detail for g in state.data_gaps]
    for c in state.conflicts:
        lines.append(f"Nilai bertentangan — {c.detail}.")
    by_claim = {c.claim_id: c for c in state.claims}
    for issue in state.validation.issues:
        claim = by_claim[issue.claim_id]
        if issue.code == "contradictory_values":
            continue  # already listed via conflicts
        prefix = "Ditolak" if issue.severity == "error" else "Catatan"
        lines.append(f"{prefix}: \"{claim.statement}\" — {issue.detail}.")
    return list(dict.fromkeys(lines))


def synthesize(state: AgentState, llm: LLMClient) -> Briefing:
    intent = state.intent.name if state.intent else "clarify"
    sections: list[BriefingSection] = []
    if intent == "discovery":
        sections = [
            BriefingSection(heading="Peristiwa yang perlu diperhatikan",
                            findings=_event_findings(state)),
            BriefingSection(heading="Konteks keuangan (second-hop)",
                            findings=_second_hop_findings(state)),
        ]
    elif intent == "peer_comparison":
        sections = [BriefingSection(heading="Perbandingan peer", findings=_findings(state, "peer"))]
    elif intent == "company_context":
        sections = [
            BriefingSection(heading="Kinerja dan tren", findings=_findings(state, "trend")),
            BriefingSection(heading="Peristiwa terkait", findings=_event_findings(state)),
        ]
    sections = [s for s in sections if s.findings]

    gaps = _data_gap_lines(state)
    assumptions = list(dict.fromkeys(
        ([state.timeframe.note] if state.timeframe and state.timeframe.note else [])
        + state.assumptions + state.analytics.get("unit_normalizations", [])
    ))
    boundary = BOUNDARY_NOTE
    if state.intent and state.intent.advice_requested:
        boundary = f"{ADVICE_NOTE} {BOUNDARY_NOTE}"

    briefing = Briefing(
        title="IDX Insight Briefing",
        summary=_summary(state),
        sections=sections,
        data_gaps=gaps,
        assumptions=assumptions,
        boundary_note=boundary,
    )
    if not any(s.findings for s in sections):
        briefing.summary = ("Bukti tidak cukup untuk menyusun temuan. "
                            if intent != "discovery" else "") + briefing.summary

    if llm.available and sections:
        facts = [f.text for s in sections for f in s.findings]
        narrative = llm.generate(system=SYNTHESIS_SYSTEM,
                                 user=synthesis_user_prompt(state.query, facts, gaps))
        if narrative:
            rejection = guard_narrative(narrative, facts + gaps + assumptions, state.query)
            if rejection is None:
                briefing.narrative = narrative
                briefing.synthesis_mode = "llm"
            else:
                state.add_trace("LLM narrative rejected", rejection, "warning")
    return briefing
