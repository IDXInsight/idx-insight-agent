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


def _fmt(x: float, decimals: int, lang: str, sign: bool = False) -> str:
    """Locale-aware number: English 1,234.5 / Indonesian 1.234,5."""
    text = f"{x:{'+' if sign else ''},.{decimals}f}"
    if lang == "id":
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return text


def fmt_pct(value: float, lang: str = "id", decimals: int = 1) -> str:
    """Fraction → percent (0.235 → 23,5% / 23.5%)."""
    return f"{_fmt(value * 100, decimals, lang)}%"


def fmt_share_pct(points: float, lang: str = "id") -> str:
    """Value already in percentage points (1.05 → 1,05% / 1.05%)."""
    return f"{_fmt(points, 2, lang)}%"


def fmt_pp(value: float, lang: str = "id", decimals: int = 1) -> str:
    """Difference of two fractions in percentage points (0.12 → +12,0 pp)."""
    return f"{_fmt(value * 100, decimals, lang, sign=True)} pp"


_IDR_UNITS = {
    "id": ((1e12, "triliun"), (1e9, "miliar"), (1e6, "juta")),
    "en": ((1e12, "tn"), (1e9, "bn"), (1e6, "mn")),
}


def fmt_idr(value: float, lang: str = "id") -> str:
    """Rupiah amount (15.1e12 → Rp15,1 triliun / IDR 15.1 tn)."""
    prefix = "Rp" if lang == "id" else "IDR "
    for size, unit in _IDR_UNITS[lang]:
        if abs(value) >= size:
            return f"{prefix}{_fmt(value / size, 1, lang)} {unit}"
    return f"{prefix}{_fmt(value, 0, lang)}"
