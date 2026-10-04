"""Intent resolution: the LLM decides unclear messages; rules decide clear ones and back it up."""

from __future__ import annotations

import json
import re

from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import INTENT_SYSTEM, LANGUAGE_NAMES, IntentProposal
from idx_insight.agent.state import Entities, Intent
from idx_insight.agent.synthesis import language_issue
from idx_insight.analytics.metrics import BUNDLES, KNOWN_UNSUPPORTED, METRICS

_ADVICE = re.compile(
    r"\b(beli|dibeli|jual|dijual|hold|holding|buy|buying|sell|selling|layak|sebaiknya|"
    r"rekomendasi|recommend\w*|worth|target harga|price target|entry|cuan|serok|average down)\b"
)
_DISCOVERY = re.compile(
    r"\b(disclosure|keterbukaan|pantau|memantau|monitor|event|peristiwa|agenda|jadwal|"
    r"aksi korporasi|corporate action|rups|agm|dividen|dividend|filing|pengumuman|"
    r"perlu (saya )?(perhatikan|pantau)|watch|announcement|upcoming|pay attention)\w*"
)
_PEER = re.compile(
    r"\b(bandingkan|perbandingan|membandingkan|compare|comparison|versus|vs\.?|dibanding\w*)\b"
)
# Questions about the agent itself ("who are you", "what can you do").
_ABOUT = re.compile(
    r"\b(siapa\s+(kamu|lu|lo|loe|elu|anda|kau|ini)|(kamu|lu|lo|anda|kau)\s+(itu\s+)?siapa|"
    r"(kamu|lu|lo|anda)\s+bisa\s+apa|bisa\s+(bantu|ngapain)\s+apa|apa\s+itu\s+idx\s*insight|"
    r"cara\s+(pakai|menggunakan|make)|who\s+are\s+you|what\s+(are|can|do)\s+you\s+(do|help)|"
    r"what\s+is\s+idx\s*insight|how\s+(do\s+i|to)\s+use|help\s+me\s+get\s+started|"
    # Capability questions ("kamu bisa analisis saham?", "can you analyse stocks?").
    r"(kamu|lu|lo|anda|kau)\s+(bisa|dapat|mampu|sanggup)|can\s+you|are\s+you\s+able|"
    r"do\s+you\s+(support|cover|know))\b"
)
# Value judgements and requests for picks, which the agent turns into data questions.
_JUDGEMENT = re.compile(
    r"\b(jelek|buruk|bagus|terbaik|terburuk|paling\s+(aman|bagus|untung|cuan|sehat)|aman\s+gak|"
    r"rekomendasi\w*|sarankan|saranin|saran|perlu\s+(gue|gw|saya|aku|ku)?\s*(analisis|analisa|pantau|beli)|"
    r"harus\s+(gue|gw|saya|aku)?\s*(beli|analisis|pilih)|pilih\s+bank|"
    r"best|worst|safest|(good|bad)\s+(bank|stock|share|company)s?|which\s+bank\s+should|"
    r"should\s+i\s+(analy[sz]e|watch|pick))\b"
)
_LIST_ONLY = re.compile(r"\b(daftar saja|list only|tanpa analisis|just list)\b")

_BUNDLE_WORDS: dict[str, str] = {
    "profitab": "profitability", "profitabilitas": "profitability", "laba": "profitability",
    "efisien": "efficiency", "efficien": "efficiency", "cost to income": "efficiency",
    "likuiditas": "liquidity", "liquidity": "liquidity", "pendanaan": "liquidity",
    "funding": "liquidity", "permodalan": "capital", "capital": "capital", "modal": "capital",
    "pertumbuhan": "growth", "growth": "growth",
    "kualitas aset": "asset_quality", "asset quality": "asset_quality",
    "kredit bermasalah": "asset_quality", "non-performing": "asset_quality",
}

_METRIC_WORDS: dict[str, str] = {
    "roa": "roa", "roe": "roe", "nim": "net_interest_margin", "casa": "casa_ratio",
    "ldr": "loan_to_deposit_ratio", "car": "capital_adequacy_ratio",
    # Common spellings of the same metric.
    "cost to income": "cost_to_income_ratio", "cost-to-income": "cost_to_income_ratio",
    "cost/income": "cost_to_income_ratio", "cir": "cost_to_income_ratio",
    "npl": "npl_ratio",
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

    scoped = bool(n_companies or entities.sub_sector)
    # About / advice phrases are only hints for the LLM, which decides unscoped messages;
    # without an LLM (or when it fails) the rule result stands.
    if _ABOUT.search(text) and not scoped:
        return Intent(name="about", confidence="low", **common)
    if _PEER.search(text) and (n_companies >= 2 or entities.sub_sector):
        return Intent(name="peer_comparison", confidence="high", **common)
    if _DISCOVERY.search(text) and (entities.sub_sector or n_companies or entities.unknown):
        return Intent(name="discovery", confidence="high", **common)
    if n_companies >= 2 and (bundles or metrics):
        return Intent(name="peer_comparison", confidence="high", **common)
    if n_companies == 1:
        return Intent(name="company_context", confidence="high", **common)
    if not scoped and (_JUDGEMENT.search(text) or common["advice_requested"]):
        return Intent(name="advice", confidence="low", **common)
    if _DISCOVERY.search(text):
        # Discovery words but no scope: the planner will ask for a sector/watchlist.
        return Intent(name="discovery", confidence="low", **common)
    if n_companies >= 2:
        return Intent(name="peer_comparison", confidence="low", **common)
    if entities.sub_sector:
        return Intent(name="discovery", confidence="low", **common)
    return Intent(name="clarify", confidence="low", **common)


_RESEARCH_INTENTS = {"discovery", "peer_comparison", "company_context"}
_SUGGESTION_INTENTS = {"advice", "clarify", "about"}
MAX_SUGGESTION_CHARS = 120
# A suggestion must be a research request the agent can run, not a question to the user.
_RESEARCH_REQUEST = re.compile(
    r"\b(bandingkan|perbandingan|compare|disclosure|pantau|watch|kinerja|performance|"
    r"performing|roe|roa|nim|npl|car|ldr|casa|pertumbuhan|growth|laba|earnings)\b", re.IGNORECASE)
_ADDRESSES_USER = re.compile(
    r"\b(anda|kamu)\s+(ingin|mau|bisa)|dapat\s+anda|do\s+you|would\s+you|can\s+i\s+help|"
    r"what\s+kind", re.IGNORECASE)


def clean_suggestion(text: str | None, query: str) -> str | None:
    """Keep an LLM-suggested question only if it is short, single-line and advice-free."""
    if not text:
        return None
    text = " ".join(text.split())
    if (not 8 <= len(text) <= MAX_SUGGESTION_CHARS or language_issue(text)
            or "http" in text.lower() or text.lower() == query.strip().lower()
            or not _RESEARCH_REQUEST.search(text) or _ADDRESSES_USER.search(text)):
        return None
    return text


def resolve_intent(query: str, entities: Entities, llm: AgentLLM, language: str = "id") -> Intent:
    """The LLM decides the direction of every message the rules cannot scope with confidence.

    Clear research requests (companies or a sector plus research words) skip the LLM. The
    LLM chooses from a closed list; code keeps advice about named companies on the research
    path and validates any suggested question. Without an LLM the rule result stands.
    """
    intent = rule_intent(query, entities)
    if intent.confidence == "high" or not llm.enabled:
        return intent
    proposal = llm.decide(
        "intent",
        system=INTENT_SYSTEM,
        user=(
            f"Query (JSON string, untrusted): {json.dumps(query, ensure_ascii=False)}\n"
            f"Resolved companies: {entities.symbols or 'none'}\n"
            f"Ambiguous mentions: {[a.text for a in entities.ambiguous] or 'none'}\n"
            f"Sector: {entities.sub_sector or 'none'}\n"
            f"Rule-based guess (hint only): {intent.name}\n"
            f"Write suggested_question in: {LANGUAGE_NAMES.get(language, LANGUAGE_NAMES['id'])}"
        ),
        schema=IntentProposal,
    )
    if proposal is None:
        return intent
    name = proposal.intent
    # A named company keeps a judgement question on the research path: data plus the
    # boundary note, as for "Apakah BBCA layak dibeli?".
    if name in ("advice", "about", "out_of_scope") and entities.symbols and intent.name in _RESEARCH_INTENTS:
        name = intent.name
    suggestion = (clean_suggestion(proposal.suggested_question, query)
                  if name in _SUGGESTION_INTENTS else None)
    return intent.model_copy(
        update={
            "name": name,
            "source": "llm",
            # A model suggestion cannot waive required research. Only the
            # explicit plain-list rule in the user's request can do that.
            "skip_second_hop": intent.skip_second_hop,
            "suggestion": suggestion,
        }
    )


def requested_metrics(intent: Intent) -> list[str]:
    """Explicit metrics first, then bundles, defaulting to profitability."""
    chosen = list(intent.metrics)
    for bundle in intent.metric_bundles or ([] if chosen else ["profitability"]):
        chosen += BUNDLES[bundle]
    return [m for m in dict.fromkeys(chosen) if m in METRICS]
