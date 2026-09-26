"""Period alignment for quarterly and yearly data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

_QUARTER_BY_MONTH_DAY = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}


def quarter_label(period: str) -> str:
    """'2026-06-30' → 'Q2 2026'; a bare year is returned unchanged."""
    if len(period) == 4:
        return period
    quarter = _QUARTER_BY_MONTH_DAY.get(period[5:])
    return f"Q{quarter} {period[:4]}" if quarter else period


def prior_year_period(period: str) -> str:
    """Same quarter one year earlier ('2026-06-30' → '2025-06-30')."""
    if len(period) == 4:
        return str(int(period) - 1)
    return f"{int(period[:4]) - 1}{period[4:]}"


@dataclass
class Alignment:
    """Result of choosing one comparable period across companies."""

    period: str | None
    per_symbol: dict[str, str | None]
    aligned: bool
    # Companies with newer data than the chosen period (comparability > recency).
    ahead: list[str] = field(default_factory=list)
    # Companies whose latest data is older than the chosen period.
    lagging: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def align_latest_common(available: Mapping[str, Iterable[str]]) -> Alignment:
    """Pick the latest period every company with data has in common.

    - Companies with no data at all are reported in ``missing`` and excluded.
    - If there is no common period, each company keeps its own latest period and
      ``aligned`` is False so downstream validation can flag the comparison.
    """
    periods = {sym: sorted(set(p)) for sym, p in available.items()}
    missing = sorted(sym for sym, p in periods.items() if not p)
    with_data = {sym: p for sym, p in periods.items() if p}
    if not with_data:
        return Alignment(None, {s: None for s in periods}, False, missing=missing)

    common = set.intersection(*(set(p) for p in with_data.values()))
    if common:
        chosen = max(common)
        ahead = sorted(sym for sym, p in with_data.items() if p[-1] > chosen)
        per_symbol: dict[str, str | None] = {s: chosen for s in with_data}
        per_symbol.update({s: None for s in missing})
        return Alignment(chosen, per_symbol, True, ahead=ahead, missing=missing)

    latest = {sym: p[-1] for sym, p in with_data.items()}
    newest = max(latest.values())
    lagging = sorted(sym for sym, p in latest.items() if p < newest)
    per_symbol = dict(latest)
    per_symbol.update({s: None for s in missing})
    return Alignment(None, per_symbol, False, lagging=lagging, missing=missing)
