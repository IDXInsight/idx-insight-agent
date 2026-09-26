"""Event normalization helpers, duplicate detection, density and relevance rules.

Relevance is rule-based so it is reproducible and explainable. Scores are
0–100; reasons are user-facing (Indonesian).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from idx_insight.models import Event

RELEVANT_THRESHOLD = 40
SECOND_HOP_THRESHOLD = 50

_TYPE_BASE: dict[str, tuple[int, str]] = {
    "dividend_ex": (35, "Tanggal ex-dividen menentukan hak atas dividen"),
    "dividend_payment": (15, "Jadwal pembayaran dividen"),
    "agm": (30, "RUPS dapat memutuskan dividen, susunan pengurus, atau aksi korporasi"),
    "stock_split": (30, "Stock split mengubah jumlah dan harga nominal saham"),
}

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


def score_event(ev: Event, ctx: RelevanceContext) -> tuple[int, list[str]]:
    score, reasons = 0, []

    if ev.event_type == "ownership_change":
        pct = abs(ev.attributes.get("share_percentage_transaction") or 0.0)
        if pct >= LARGE_OWNERSHIP_PCT:
            score += 40
            reasons.append(f"Perubahan kepemilikan {pct:.2f}% dari total saham (≥1%)")
        elif pct >= MEDIUM_OWNERSHIP_PCT:
            score += 25
            reasons.append(f"Perubahan kepemilikan {pct:.2f}% dari total saham")
        else:
            score += 10
        value = ev.attributes.get("transaction_value") or 0.0
        if value >= LARGE_TRANSACTION_IDR:
            score += 10
            reasons.append("Nilai transaksi ≥ Rp500 miliar")
        if ev.attributes.get("holder_type") == "insider":
            score += 10
            reasons.append("Transaksi oleh orang dalam (insider)")
    else:
        base, reason = _TYPE_BASE[ev.event_type]
        score += base
        reasons.append(reason)

    if ev.forward_looking:
        score += 10
        reasons.append("Terjadwal di dalam jendela waktu yang diminta")
    if ctx.density.get(ev.symbol, 0) >= 2:
        score += 10
        reasons.append("Beberapa peristiwa emiten yang sama berdekatan")
    if ev.symbol in ctx.watchlist:
        score += 5
        reasons.append("Emiten ada di watchlist")

    return min(score, 100), reasons
