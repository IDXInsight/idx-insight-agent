"""Prompts and structured-output schemas for the LLM-driven decisions.

The LLM proposes; deterministic guardrails dispose. Every LLM output is checked
(allowed intents, allowed plan steps, grounded numbers, no advice) before use.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from idx_insight.agent.state import IntentName, PlanStepName

BOUNDARY = (
    "You are IDX Insight Agent, a factual research assistant for companies listed on the "
    "Indonesia Stock Exchange, using Sectors data. You never give buy, sell or hold "
    "recommendations, price targets, or trading instructions. If asked for advice, you "
    "stay with factual context and say that the decision belongs to the user."
)


class IntentProposal(BaseModel):
    intent: IntentName = Field(description="Best-fitting intent for the query.")
    skip_second_hop: bool = Field(
        default=False,
        description="True only when the user explicitly wants a plain list without deeper context.",
    )
    rationale: str = Field(description="One short sentence, no chain of thought.")


INTENT_SYSTEM = f"""{BOUNDARY}

Classify the user's research request into exactly one intent:
- discovery: which disclosures / corporate events deserve attention for a sector,
  watchlist or timeframe.
- peer_comparison: compare financial metrics across two or more companies or a sector.
- company_context: financial context and recent events for one company.
- clarify: the request cannot be scoped without asking the user.

Entities and dates are resolved separately; only classify."""


class PlanProposal(BaseModel):
    steps: list[PlanStepName] = Field(description="Ordered plan steps, from the allowed list only.")
    rationale: str = Field(description="One short sentence explaining the plan.")


PLAN_SYSTEM = f"""{BOUNDARY}

You choose the next actions of a research agent. Pick an ordered subset of the
allowed steps for the given intent. Include optional steps only when they add
evidence the user needs (for example, second-hop financial context for events that
look material). Always finish with validate_evidence then synthesize."""


class NarrativeSentence(BaseModel):
    text: str = Field(description="One sentence of the briefing.")
    citations: list[str] = Field(
        description="Ids of the facts or data gaps this sentence is based on, e.g. cl-003, gap-1.")


class NarrativeProposal(BaseModel):
    sentences: list[NarrativeSentence] = Field(description="The briefing, one sentence per item.")


LANGUAGE_NAMES = {"id": "Indonesian (Bahasa Indonesia)", "en": "English"}

SYNTHESIS_SYSTEM = f"""{BOUNDARY}

Write a short, neutral research briefing from the validated facts and data gaps
you are given. Each fact and gap has an id in square brackets.

Rules:
- Every sentence must cite the ids it is based on. Cite only listed ids.
- Use only information in the cited items. Do not add companies, dates or numbers.
- Copy every number exactly as written in the cited items, with the same decimal
  separator and units.
- Lead with what deserves attention, then why it matters, then what is still
  unknown (data gaps).
- Describe; do not interpret or predict. Avoid words such as "signals",
  "indicates", "will rise", "menandakan", "mengindikasikan", "akan naik".
- No recommendations, price targets or trading language.
- At most 6 sentences."""


def synthesis_user_prompt(query: str, language: str, facts: list[tuple[str, str]],
                          gaps: list[tuple[str, str]]) -> str:
    lines = [f"Write the briefing in {LANGUAGE_NAMES[language]}.", f"User question: {query}",
             "", "Validated facts:"]
    lines += [f"[{i}] {text}" for i, text in facts] or ["(none)"]
    lines += ["", "Data gaps:"]
    lines += [f"[{i}] {text}" for i, text in gaps] or ["(none)"]
    return "\n".join(lines)



SECOND_HOP_SYSTEM = f"""{BOUNDARY}

You decide which discovered events need follow-up financial context (the
company's latest earnings growth and ROE) so their significance can be
explained. The most material events are already being researched; they are
listed for context only.

Call request_financial_context for each additional candidate event where that
context would materially help explain why the event matters, choosing the
category that best describes why:
- dividend_capacity: dividend events, where earnings and ROE frame the payout
- governance_decision: shareholder meetings that may decide on the use of profit
- ownership_shift: large ownership changes by institutions, insiders or groups
- corporate_action_context: other corporate actions such as stock splits

Do not call it for self-explanatory events. Calling it zero times is fine.
Use only event ids from the candidate list."""


def second_hop_user_prompt(query: str, already: list[str], candidates: list[str]) -> str:
    return "\n".join([
        f"User question: {query}", "",
        "Already researched:", *(already or ["(none)"]), "",
        "Candidate events:", *candidates,
    ])
