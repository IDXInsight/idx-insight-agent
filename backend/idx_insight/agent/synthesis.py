"""Synthesis: validated claims → briefing, in the user's language.

The structured briefing is always assembled deterministically from accepted
claims. When an LLM is available it may add a short narrative in which every
sentence cites accepted claim ids or data-gap ids. Code validates each sentence
(known citations, numbers taken only from the cited items, no advice or
predictive language); any failure drops the narrative and keeps the template.
"""

from __future__ import annotations

import re

from idx_insight.agent.i18n import t
from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import SYNTHESIS_SYSTEM, NarrativeProposal, synthesis_user_prompt
from idx_insight.agent.state import (
    AgentState,
    Briefing,
    BriefingSection,
    CitedSentence,
    Finding,
)
from idx_insight.analytics.metrics import METRICS

MAX_SENTENCES = 6
MAX_SENTENCE_CHARS = 400

_ADVICE = re.compile(
    r"\b(beli|jual|tahan|hold|buy|sell|akumulasi|serok|target harga|price target|"
    r"direkomendasikan|rekomendasi|sebaiknya|disarankan|recommend\w*|should (?:buy|sell|hold)|"
    r"accumulate|overweight|underweight|undervalued|overvalued)\b",
    re.IGNORECASE,
)
_SPECULATIVE = re.compile(
    r"\b(menandakan|mengindikasikan|pasti|dipastikan|akan naik|akan turun|berpotensi naik|"
    r"berpotensi turun|sinyal|menjanjikan|prospek cerah|bullish|bearish|signals?|"
    r"indicates? that|suggests? that|will (?:rise|fall|increase|decrease|grow)|"
    r"is likely to|guaranteed|promising|outperform\w*|underperform\w*)\b",
    re.IGNORECASE,
)
_ALLOWED_NEGATIONS = re.compile(
    r"\b(bukan (rekomendasi|saran)|not (a |an )?(investment )?(recommendation|advice))[^.]*",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def language_issue(text: str) -> str | None:
    """Advice or speculative wording in generated text, if any."""
    scrubbed = _ALLOWED_NEGATIONS.sub("", text)
    if m := _ADVICE.search(scrubbed):
        return f"advice language: {m.group(0)!r}"
    if m := _SPECULATIVE.search(scrubbed):
        return f"speculative language: {m.group(0)!r}"
    return None


def ungrounded_number(text: str, sources: str) -> str | None:
    allowed = set(_NUMBER.findall(sources))
    for token in _NUMBER.findall(text):
        if token not in allowed and not (token.isdigit() and int(token) <= 10):
            return token
    return None


def validate_narrative(proposal: NarrativeProposal,
                       items: dict[str, str]) -> tuple[list[CitedSentence] | None, str | None]:
    """All-or-nothing check of an LLM narrative against the citable items."""
    if not proposal.sentences:
        return None, "empty narrative"
    if len(proposal.sentences) > MAX_SENTENCES:
        return None, f"too many sentences ({len(proposal.sentences)})"
    out = []
    for i, sentence in enumerate(proposal.sentences, 1):
        text = sentence.text.strip()
        if not text or len(text) > MAX_SENTENCE_CHARS:
            return None, f"sentence {i}: empty or too long"
        citations = list(dict.fromkeys(sentence.citations))
        if not citations:
            return None, f"sentence {i}: no citation"
        unknown = [c for c in citations if c not in items]
        if unknown:
            return None, f"sentence {i}: unknown citation {unknown[0]}"
        if issue := language_issue(text):
            return None, f"sentence {i}: {issue}"
        if token := ungrounded_number(text, " ".join(items[c] for c in citations)):
            return None, f"sentence {i}: number {token} not in cited items"
        out.append(CitedSentence(text=text, citations=citations))
    return out, None


# --- deterministic briefing ------------------------------------------------------------


def _findings(state: AgentState, section: str) -> list[Finding]:
    accepted = set(state.validation.accepted)
    return [Finding(text=c.statement, claim_ids=[c.claim_id]) for c in state.claims
            if c.claim_id in accepted and c.meta.get("section") == section]


def _event_findings(state: AgentState) -> list[Finding]:
    accepted = set(state.validation.accepted)
    return [
        Finding(text=c.statement, claim_ids=[c.claim_id],
                why=t(state.language, "finding.why_event", why="; ".join(c.meta.get("reasons", [])),
                      score=c.meta.get("score")))
        for c in state.claims
        if c.claim_id in accepted and c.meta.get("section") == "events"
    ]


def _second_hop_findings(state: AgentState) -> list[Finding]:
    out = _findings(state, "second_hop")
    for d in state.second_hop:
        if d.decision == "research":
            out.append(Finding(text=t(state.language, "hop.finding", sym=d.symbol, reason=d.reason),
                               claim_ids=[]))
    return out


def _summary(state: AgentState) -> str:
    lang = state.language
    intent = state.intent.name if state.intent else "clarify"
    tf = state.timeframe
    if intent == "discovery":
        return t(lang, "summary.discovery", n=len(state.relevant_events),
                 unique=len(state.discovered_events), dups=len(state.duplicate_events),
                 scope=state.entities.sub_sector or ", ".join(state.entities.symbols),
                 timeframe=tf.label if tf else "", selected=len(state.selected_events))
    if intent == "peer_comparison":
        metrics = ", ".join(METRICS[m].label_in(lang)
                            for m in state.analytics.get("peer_comparison", {}))
        return t(lang, "summary.peer", syms=", ".join(state.entities.symbols), metrics=metrics)
    return t(lang, "summary.company", syms=", ".join(state.entities.symbols))


def _data_gap_lines(state: AgentState) -> list[str]:
    lang = state.language
    lines = [g.detail for g in state.data_gaps]
    lines += [t(lang, "gap.conflict", detail=c.detail) for c in state.conflicts]
    by_claim = {c.claim_id: c for c in state.claims}
    for issue in state.validation.issues:
        if issue.code == "contradictory_values":
            continue  # already listed via conflicts
        key = "gap.rejected" if issue.severity == "error" else "gap.note"
        lines.append(t(lang, key, statement=by_claim[issue.claim_id].statement, detail=issue.detail))
    return list(dict.fromkeys(lines))


def _citable_items(state: AgentState, gaps: list[str]) -> dict[str, str]:
    accepted = set(state.validation.accepted)
    items: dict[str, str] = {}
    for c in state.claims:
        if c.claim_id in accepted:
            why = "; ".join(c.meta.get("reasons", []))
            items[c.claim_id] = f"{c.statement} | {why}" if why else c.statement
    for i, gap in enumerate(gaps, 1):
        items[f"gap-{i}"] = gap
    return items


def synthesize(state: AgentState, llm: AgentLLM) -> Briefing:
    lang = state.language
    intent = state.intent.name if state.intent else "clarify"
    sections: list[BriefingSection] = []
    if intent == "discovery":
        sections = [
            BriefingSection(heading=t(lang, "heading.events"), findings=_event_findings(state)),
            BriefingSection(heading=t(lang, "heading.second_hop"),
                            findings=_second_hop_findings(state)),
        ]
    elif intent == "peer_comparison":
        sections = [BriefingSection(heading=t(lang, "heading.peer"),
                                    findings=_findings(state, "peer"))]
    elif intent == "company_context":
        sections = [
            BriefingSection(heading=t(lang, "heading.trend"), findings=_findings(state, "trend")),
            BriefingSection(heading=t(lang, "heading.related_events"),
                            findings=_event_findings(state)),
        ]
    sections = [s for s in sections if s.findings]

    gaps = _data_gap_lines(state)
    assumptions = list(dict.fromkeys(
        ([state.timeframe.note] if state.timeframe and state.timeframe.note else [])
        + state.assumptions + state.analytics.get("unit_normalizations", [])
    ))
    boundary = t(lang, "briefing.boundary")
    if state.intent and state.intent.advice_requested:
        boundary = f"{t(lang, 'briefing.advice')} {boundary}"

    briefing = Briefing(
        title="IDX Insight Briefing",
        summary=_summary(state),
        sections=sections,
        data_gaps=gaps,
        assumptions=assumptions,
        boundary_note=boundary,
    )
    if not any(s.findings for s in sections) and intent != "discovery":
        briefing.summary = t(lang, "summary.insufficient") + briefing.summary

    if llm.enabled and sections:
        items = _citable_items(state, gaps)
        facts = [(k, v) for k, v in items.items() if not k.startswith("gap-")]
        gap_items = [(k, v) for k, v in items.items() if k.startswith("gap-")]
        proposal = llm.decide(
            "synthesis", system=SYNTHESIS_SYSTEM,
            user=synthesis_user_prompt(state.query, lang, facts, gap_items),
            schema=NarrativeProposal,
        )
        if proposal is not None:
            sentences, rejection = validate_narrative(proposal, items)
            if sentences is not None:
                briefing.narrative = sentences
                briefing.synthesis_mode = "llm"
            else:
                state.add_trace("LLM narrative rejected", rejection or "", "warning")
    return briefing
