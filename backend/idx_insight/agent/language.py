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
    # Everyday and informal Indonesian.
    "kamu", "anda", "aku", "gue", "gw", "lu", "lo", "bisa", "ada", "ga", "gak", "nggak", "sih",
    "aja", "yg", "siapa", "gimana", "kenapa", "lagi", "bagus", "jelek", "menurut", "menurutlu",
    "analisis", "saham", "terima", "kasih", "seberapa", "buat", "punya", "kalau", "kok",
}
_EN_WORDS = {
    "what", "which", "the", "and", "for", "from", "with", "in", "to", "this", "that", "i", "me",
    "should", "watch", "next", "week", "month", "day", "year", "quarter", "compare", "how",
    "performance", "sector", "banking", "banks", "list", "show", "is", "are", "between", "or",
    "last", "upcoming", "disclosures", "please", "explain", "of", "on", "my", "do", "does",
    "worth", "buy", "any", "there", "about", "need", "pay", "attention",
    # Everyday English.
    "you", "who", "can", "your", "good", "bad", "best", "stock", "stocks", "analyse", "analyze",
    "thanks", "thank", "hello", "hi", "tell", "it", "a", "an", "be", "right", "now", "trouble",
}
_WORD = re.compile(r"[a-zA-Z]+")


def unsupported_script(query: str) -> bool:
    """True when a large share of letters is outside the Latin alphabet (e.g. Japanese, Arabic).

    The threshold is 40% rather than a majority because tickers are always Latin: in
    "BCAとBRIを比較する" half of the letters are tickers.

    Only Indonesian and English are supported; such messages get a fixed bilingual reply
    before any entity resolution, LLM call or Sectors call.
    """
    letters = [c for c in query if c.isalpha()]
    if not letters:
        return False
    non_latin = sum(ord(c) > 0x024F for c in letters)
    return non_latin / len(letters) >= 0.4


def detect_language(query: str) -> Language:
    words = [w.lower() for w in _WORD.findall(query)]
    id_hits = sum(w in _ID_WORDS for w in words)
    en_hits = sum(w in _EN_WORDS for w in words)
    return "en" if en_hits > id_hits else DEFAULT_LANGUAGE
