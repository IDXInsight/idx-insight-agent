"""Deterministic numeric helpers. The LLM never does this arithmetic."""

from __future__ import annotations

from statistics import median

# Ratios are expected as fractions (0.235 = 23.5%). Anything above this
# magnitude is treated as having been reported in percent.
_RATIO_PERCENT_THRESHOLD = 1.5


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def pct_change(current: float | None, previous: float | None) -> float | None:
    """Fractional change; ``None`` when inputs are missing or the base is 0.

    Uses ``abs(previous)`` so a move from a loss to a smaller loss is positive.
    """
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / abs(previous)


def spread(a: float | None, b: float | None) -> float | None:
    """Difference ``a - b`` (percentage points when both are ratios)."""
    if a is None or b is None:
        return None
    return a - b


def normalize_ratio(value: float | None) -> tuple[float | None, bool]:
    """Return (fractional value, was_converted_from_percent)."""
    if value is None:
        return None, False
    if abs(value) > _RATIO_PERCENT_THRESHOLD:
        return value / 100, True
    return value, False


def robust_outliers(values: dict[str, float], threshold: float = 2.5, min_n: int = 4) -> list[str]:
    """Keys whose robust z-score (median/MAD) exceeds ``threshold``.

    Returns [] when there are too few peers for the notion to be meaningful.
    """
    if len(values) < min_n:
        return []
    med = median(values.values())
    mad = median(abs(v - med) for v in values.values())
    if mad == 0:
        return []
    return sorted(k for k, v in values.items() if abs(0.6745 * (v - med) / mad) > threshold)


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def fmt_pp(value: float, decimals: int = 1) -> str:
    return f"{value * 100:+.{decimals}f} pp"


def fmt_idr(value: float) -> str:
    for size, label in ((1e12, "T"), (1e9, "M")):
        if abs(value) >= size:
            return f"Rp{value / size:,.1f} {label}"
    return f"Rp{value:,.0f}"
