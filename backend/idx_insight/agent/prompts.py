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


SYNTHESIS_SYSTEM = f"""{BOUNDARY}

Write a short briefing in Indonesian from the validated facts you are given.
Rules:
- Use only the facts provided. Do not add numbers, dates or companies that are not in them.
- Keep every number exactly as written in the facts.
- Explain why each item may matter (context), not what to do about it.
- Mention data gaps plainly when they are listed.
- No recommendations, no price targets, no trading language.
- At most 180 words, plain prose with short paragraphs, no headings."""


def synthesis_user_prompt(query: str, facts: list[str], gaps: list[str]) -> str:
    lines = [f"Pertanyaan pengguna: {query}", "", "Fakta tervalidasi:"]
    lines += [f"- {f}" for f in facts] or ["- (tidak ada)"]
    lines += ["", "Kesenjangan data:"]
    lines += [f"- {g}" for g in gaps] or ["- (tidak ada)"]
    return "\n".join(lines)



SECOND_HOP_SYSTEM = f"""{BOUNDARY}

You decide which discovered events need deeper financial context before they can
be explained to the user. Call request_financial_context once for each event where
recent earnings growth and ROE of the company would materially help explain why
the event matters (for example dividends, AGMs deciding profit use, or large
ownership changes). Do not call it for events that are self-explanatory. You may
call it zero times. Only use event ids from the list."""


def second_hop_user_prompt(query: str, events: list[str]) -> str:
    return "\n".join([f"Pertanyaan pengguna: {query}", "", "Kandidat peristiwa:", *events])
