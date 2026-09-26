"""Intent resolution: deterministic rules first, LLM when the rules are unsure."""

from __future__ import annotations

import re

from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import INTENT_SYSTEM, IntentProposal
from idx_insight.agent.state import Entities, Intent
from idx_insight.analytics.metrics import BUNDLES, KNOWN_UNSUPPORTED, METRICS

_ADVICE = re.compile(
    r"\b(beli|dibeli|jual|dijual|hold|buy|sell|layak|sebaiknya|rekomendasi|recommend\w*|"
    r"target harga|price target|entry|cuan|serok|average down)\b"
)
_DISCOVERY = re.compile(
    r"\b(disclosure|keterbukaan|pantau|memantau|monitor|event|peristiwa|agenda|jadwal|"
    r"aksi korporasi|corporate action|rups|agm|dividen|dividend|filing|pengumuman|"
    r"perlu (saya )?(perhatikan|pantau)|watch)\w*"
)
_PEER = re.compile(
    r"\b(bandingkan|perbandingan|membandingkan|compare|comparison|versus|vs\.?|dibanding\w*)\b"
)
_LIST_ONLY = re.compile(r"\b(daftar saja|list only|tanpa analisis|just list)\b")

_BUNDLE_WORDS: dict[str, str] = {
    "profitab": "profitability", "profitabilitas": "profitability", "laba": "profitability",
    "efisien": "efficiency", "efficien": "efficiency", "cost to income": "efficiency",
    "likuiditas": "liquidity", "liquidity": "liquidity", "pendanaan": "liquidity",
    "funding": "liquidity", "permodalan": "capital", "capital": "capital", "modal": "capital",
    "pertumbuhan": "growth", "growth": "growth",
}

_METRIC_WORDS: dict[str, str] = {
    "roa": "roa", "roe": "roe", "nim": "net_interest_margin", "casa": "casa_ratio",
    "ldr": "loan_to_deposit_ratio", "car": "capital_adequacy_ratio",
    "cost-to-income": "cost_to_income_ratio", "cir": "cost_to_income_ratio",
}


def _metrics(text: str) -> tuple[list[str], list[str], list[str]]:
    # Keep the order in which the user mentioned them.
    hits = sorted((text.find(word), b) for word, b in _BUNDLE_WORDS.items() if word in text)
    bundles = list(dict.fromkeys(b for _, b in hits))
    metrics = [m for word, m in _METRIC_WORDS.items() if re.search(rf"\b{re.escape(word)}\b", text)]
    unsupported = [label for word, label in KNOWN_UNSUPPORTED.items()
                   if re.search(rf"\b{word}\b", text)]
    return bundles, list(dict.fromkeys(metrics)), unsupported


def rule_intent(query: str, entities: Entities) -> Intent:
    text = query.lower()
    n_companies = len(entities.companies) + len(entities.ambiguous)
    bundles, metrics, unsupported = _metrics(text)
    common = dict(
        advice_requested=bool(_ADVICE.search(text)),
        metric_bundles=bundles,
        metrics=metrics,
        unsupported_metrics=unsupported,
        skip_second_hop=bool(_LIST_ONLY.search(text)),
    )

    if _PEER.search(text) and (n_companies >= 2 or entities.sub_sector):
        return Intent(name="peer_comparison", confidence="high", **common)
    if _DISCOVERY.search(text) and (entities.sub_sector or n_companies or entities.unknown):
        return Intent(name="discovery", confidence="high", **common)
    if n_companies >= 2 and (bundles or metrics):
        return Intent(name="peer_comparison", confidence="high", **common)
    if n_companies == 1:
        return Intent(name="company_context", confidence="high", **common)
    if _DISCOVERY.search(text):
        # Discovery words but no scope: the planner will ask for a sector/watchlist.
        return Intent(name="discovery", confidence="low", **common)
    if n_companies >= 2:
        return Intent(name="peer_comparison", confidence="low", **common)
    if entities.sub_sector:
        return Intent(name="discovery", confidence="low", **common)
    return Intent(name="clarify", confidence="low", **common)


def resolve_intent(query: str, entities: Entities, llm: AgentLLM) -> Intent:
    """Rules first; the LLM is consulted only when the rules are unsure."""
    intent = rule_intent(query, entities)
    if intent.confidence == "high" or not llm.enabled:
        return intent
    proposal = llm.decide(
        "intent",
        system=INTENT_SYSTEM,
        user=(
            f"Query: {query}\n"
            f"Resolved companies: {entities.symbols or 'none'}\n"
            f"Ambiguous mentions: {[a.text for a in entities.ambiguous] or 'none'}\n"
            f"Sector: {entities.sub_sector or 'none'}"
        ),
        schema=IntentProposal,
    )
    if proposal is None:
        return intent
    return intent.model_copy(
        update={
            "name": proposal.intent,
            "source": "llm",
            "skip_second_hop": intent.skip_second_hop or proposal.skip_second_hop,
        }
    )


def requested_metrics(intent: Intent) -> list[str]:
    """Explicit metrics first, then bundles, defaulting to profitability."""
    chosen = list(intent.metrics)
    for bundle in intent.metric_bundles or ([] if chosen else ["profitability"]):
        chosen += BUNDLES[bundle]
    return [m for m in dict.fromkeys(chosen) if m in METRICS]
