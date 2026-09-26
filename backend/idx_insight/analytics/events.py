"""Event normalization helpers, duplicate detection, density and relevance rules.

Relevance is rule-based so it is reproducible and explainable. Scores are
0–100; reasons are returned as language-neutral codes with parameters and are
rendered for the user by the Agent Brain.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from idx_insight.models import Event

RELEVANT_THRESHOLD = 40
SECOND_HOP_THRESHOLD = 50

_TYPE_BASE: dict[str, int] = {
    "dividend_ex": 35,
    "dividend_payment": 15,
    "agm": 30,
    "stock_split": 30,
}

Reason = tuple[str, dict[str, float]]  # (code, parameters)

LARGE_OWNERSHIP_PCT = 1.0  # percentage points of shares outstanding
MEDIUM_OWNERSHIP_PCT = 0.25
LARGE_TRANSACTION_IDR = 500_000_000_000


def event_id(*parts: object) -> str:
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]
    return f"evt-{digest}"


def dedupe(events: list[Event]) -> tuple[list[Event], list[Event]]:
    """Split into (unique, duplicates). Identity = symbol, type, date, source,
    and the transaction size for ownership changes."""
    seen: dict[tuple, str] = {}
    unique: list[Event] = []
    duplicates: list[Event] = []
    for ev in events:
        key = (
            ev.symbol,
            ev.event_type,
            ev.event_date,
            ev.source_ref,
            ev.attributes.get("holder_name"),
            ev.attributes.get("amount_transaction"),
        )
        if key in seen:
            duplicates.append(ev.model_copy(update={"duplicate_of": seen[key]}))
        else:
            seen[key] = ev.event_id
            unique.append(ev)
    return unique, duplicates


def event_density(events: list[Event]) -> dict[str, int]:
    return dict(Counter(ev.symbol for ev in events))


@dataclass(frozen=True)
class RelevanceContext:
    watchlist: frozenset[str]
    density: dict[str, int]


def score_event(ev: Event, ctx: RelevanceContext) -> tuple[int, list[Reason]]:
    score, reasons = 0, []

    if ev.event_type == "ownership_change":
        pct = abs(ev.attributes.get("share_percentage_transaction") or 0.0)
        if pct >= LARGE_OWNERSHIP_PCT:
            score += 40
            reasons.append(("ownership_large", {"pct": pct}))
        elif pct >= MEDIUM_OWNERSHIP_PCT:
            score += 25
            reasons.append(("ownership_medium", {"pct": pct}))
        else:
            score += 10
        value = ev.attributes.get("transaction_value") or 0.0
        if value >= LARGE_TRANSACTION_IDR:
            score += 10
            reasons.append(("large_value", {}))
        if ev.attributes.get("holder_type") == "insider":
            score += 10
            reasons.append(("insider", {}))
    else:
        score += _TYPE_BASE[ev.event_type]
        reasons.append((ev.event_type, {}))

    if ev.forward_looking:
        score += 10
        reasons.append(("forward", {}))
    if ctx.density.get(ev.symbol, 0) >= 2:
        score += 10
        reasons.append(("cluster", {}))
    if ev.symbol in ctx.watchlist:
        score += 5
        reasons.append(("watchlist", {}))

    return min(score, 100), reasons
