"""Deterministic language detection for user queries (Indonesian or English).

The briefing is written in the user's language. Detection counts common
function words; tickers, numbers and finance jargon shared by both languages
are ignored. Anything undecided falls back to Indonesian, the primary audience.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["id", "en"]
DEFAULT_LANGUAGE: Language = "id"

_ID_WORDS = {
    "apa", "saja", "yang", "untuk", "dan", "dari", "dengan", "di", "ke", "ini", "itu", "saya",
    "perlu", "pantau", "minggu", "depan", "bulan", "hari", "tahun", "kuartal", "bandingkan",
    "bagaimana", "kinerja", "sektor", "perbankan", "sisi", "daftar", "apakah", "berapa", "emiten",
    "laba", "lalu", "terakhir", "dong", "tolong", "tampilkan", "jelaskan", "antara", "atau",
    "sebaiknya", "layak", "pekan", "mana", "agar", "juga", "sudah", "belum", "akan", "tidak",
}
_EN_WORDS = {
    "what", "which", "the", "and", "for", "from", "with", "in", "to", "this", "that", "i", "me",
    "should", "watch", "next", "week", "month", "day", "year", "quarter", "compare", "how",
    "performance", "sector", "banking", "banks", "list", "show", "is", "are", "between", "or",
    "last", "upcoming", "disclosures", "please", "explain", "of", "on", "my", "do", "does",
    "worth", "buy", "any", "there", "about", "need", "pay", "attention",
}
_WORD = re.compile(r"[a-zA-Z]+")


def detect_language(query: str) -> Language:
    words = [w.lower() for w in _WORD.findall(query)]
    id_hits = sum(w in _ID_WORDS for w in words)
    en_hits = sum(w in _EN_WORDS for w in words)
    return "en" if en_hits > id_hits else DEFAULT_LANGUAGE
