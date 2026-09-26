"""Deterministic peer comparison."""

from __future__ import annotations

from statistics import median

from pydantic import BaseModel

from idx_insight.analytics.numbers import robust_outliers, spread


class PeerComparison(BaseModel):
    metric: str
    period: str | None
    values: dict[str, float]
    median: float | None
    highest: str | None
    lowest: str | None
    range: float | None  # highest - lowest
    diff_vs_median: dict[str, float]
    ranking: list[str]  # descending by value (not a quality judgement)
    outliers: list[str]
    sufficient: bool  # at least two companies with comparable values


def compare_peers(metric: str, period: str | None, values: dict[str, float]) -> PeerComparison:
    if len(values) < 2:
        return PeerComparison(
            metric=metric, period=period, values=values, median=None, highest=None,
            lowest=None, range=None, diff_vs_median={}, ranking=list(values),
            outliers=[], sufficient=False,
        )
    med = median(values.values())
    ranking = sorted(values, key=lambda s: (-values[s], s))
    return PeerComparison(
        metric=metric,
        period=period,
        values=values,
        median=med,
        highest=ranking[0],
        lowest=ranking[-1],
        range=spread(values[ranking[0]], values[ranking[-1]]),
        diff_vs_median={s: v - med for s, v in values.items()},
        ranking=ranking,
        outliers=robust_outliers(values),
        sufficient=True,
    )
