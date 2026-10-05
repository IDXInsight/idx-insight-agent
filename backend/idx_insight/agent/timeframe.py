"""Timeframe resolution (Indonesian and English phrasing).

Unrecognised or vague phrasing never blocks the run: a documented default is
used and recorded as an explicit assumption.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from idx_insight.agent.i18n import t
from idx_insight.agent.language import Language
from idx_insight.agent.state import Timeframe

FILINGS_LOOKBACK_DAYS = 14
DEFAULT_FORWARD_DAYS = 7

_VAGUE = re.compile(r"\b(baru-baru ini|belakangan ini|akhir-akhir ini|recently|lately|segera|soon)\b")
_N_DAYS_FWD = re.compile(
    r"(\d{1,3})\s*(hari|days?)\s*(ke depan|kedepan|ahead|mendatang)|next\s+(\d{1,3})\s+days?"
)
_N_DAYS_BACK = re.compile(r"(\d{1,3})\s*(hari|days?)\s*(terakhir|lalu|ago)|(last|past)\s+(\d{1,3})\s+days?")
_ISO_RANGE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(?:s/d|sampai|hingga|to|until|-|–)\s*(\d{4}-\d{2}-\d{2})")
_QUARTER = re.compile(r"\b(?:q|kuartal\s*|triwulan\s*)([1-4])\s*[- ]?\s*(20\d{2})\b")
_YEAR = re.compile(r"\b(?:tahun|year|fy)\s*(20\d{2})\b")

_QUARTER_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


class InvalidTimeframeError(ValueError):
    """A date explicitly supplied by the user is not a calendar date."""


def _week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _forward(start: date, end: date, label: str, as_of: date, **kw) -> Timeframe:
    return Timeframe(
        start=start, end=end, label=label, direction="forward",
        filings_start=as_of - timedelta(days=FILINGS_LOOKBACK_DAYS), filings_end=as_of, **kw,
    )


def _backward(start: date, end: date, label: str, **kw) -> Timeframe:
    return Timeframe(start=start, end=end, label=label, direction="backward",
                     filings_start=start, filings_end=end, **kw)


def resolve_timeframe(query: str, as_of: date, intent: str, lang: Language = "id") -> Timeframe:
    text = query.lower()
    period = _financial_period(text)
    kw = {"financial_period": period}

    if m := _ISO_RANGE.search(text):
        try:
            start, end = date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
        except ValueError as exc:
            raise InvalidTimeframeError("invalid date range") from exc
        if start > end:
            start, end = end, start
        if start > as_of:
            return _forward(start, end, t(lang, "tf.range", start=start, end=end), as_of, **kw)
        return _backward(start, end, t(lang, "tf.range", start=start, end=end), **kw)

    if re.search(r"minggu depan|pekan depan|next week|coming week|upcoming week", text):
        start, end = _week_bounds(as_of + timedelta(days=7))
        return _forward(start, end, t(lang, "tf.next_week", start=start, end=end), as_of, **kw)
    if re.search(r"minggu ini|pekan ini|this week", text):
        start, end = _week_bounds(as_of)
        return Timeframe(start=start, end=end, label=t(lang, "tf.this_week", start=start, end=end),
                         direction="around", filings_start=start, filings_end=as_of, **kw)
    if re.search(r"minggu lalu|pekan lalu|last week", text):
        start, end = _week_bounds(as_of - timedelta(days=7))
        return _backward(start, end, t(lang, "tf.last_week", start=start, end=end), **kw)
    if re.search(r"bulan depan|next month", text):
        first = (as_of.replace(day=1) + timedelta(days=32)).replace(day=1)
        last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return _forward(first, last, t(lang, "tf.next_month", start=first, end=last), as_of, **kw)
    if re.search(r"hari ini|today", text):
        return Timeframe(start=as_of, end=as_of, label=t(lang, "tf.today", day=as_of), direction="around",
                         filings_start=as_of - timedelta(days=1), filings_end=as_of, **kw)
    if m := _N_DAYS_FWD.search(text):
        days = int(m.group(1) or m.group(4))
        end = as_of + timedelta(days=days)
        return _forward(as_of + timedelta(days=1), end, t(lang, "tf.next_days", n=days), as_of,
                        **kw)
    if m := _N_DAYS_BACK.search(text):
        days = int(m.group(1) or m.group(5))
        return _backward(as_of - timedelta(days=days), as_of, t(lang, "tf.last_days", n=days), **kw)

    vague = _VAGUE.search(text)
    note = t(lang, "tf.note.vague", phrase=vague.group(1)) if vague else t(lang, "tf.note.none")
    if intent == "discovery":
        start, end = as_of + timedelta(days=1), as_of + timedelta(days=DEFAULT_FORWARD_DAYS)
        return _forward(start, end, t(lang, "tf.default_forward", n=DEFAULT_FORWARD_DAYS), as_of,
                        assumed=True, note=note + t(lang, "tf.note.forward", n=DEFAULT_FORWARD_DAYS,
                                                    lookback=FILINGS_LOOKBACK_DAYS), **kw)
    if intent == "peer_comparison":
        # Comparisons use the latest reported periods; no event window is needed.
        return Timeframe(start=as_of, end=as_of, label=t(lang, "tf.latest_reports"),
                         direction="around", filings_start=as_of, filings_end=as_of, **kw)
    # Company context: recent past plus the next month of scheduled events.
    start, end = as_of - timedelta(days=30), as_of + timedelta(days=30)
    return Timeframe(start=start, end=end, label=t(lang, "tf.default_around"),
                     direction="around", assumed=True, filings_start=start, filings_end=as_of,
                     note=note + t(lang, "tf.note.around"), **kw)


def _financial_period(text: str) -> str | None:
    if m := _QUARTER.search(text):
        return f"{m.group(2)}-{_QUARTER_END[int(m.group(1))]}"
    if m := _YEAR.search(text):
        return m.group(1)
    return None
