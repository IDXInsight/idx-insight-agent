"""Entity resolution: tickers, company aliases and sectors.

Aliases are agent knowledge; existence and sector membership are verified
against Sectors through ``SectorsService`` (never assumed).
"""

from __future__ import annotations

import re

from idx_insight.agent.recovery import record_tool_failure
from idx_insight.agent.state import AgentState, AmbiguousMention, Entities, ResolvedCompany
from idx_insight.sectors.schemas import bare_symbol
from idx_insight.sectors.service import SectorsService

# alias (lowercase) -> candidate tickers. More than one candidate = ambiguous.
COMPANY_ALIASES: dict[str, list[str]] = {
    "bank central asia": ["BBCA"],
    "bca": ["BBCA"],
    "bank rakyat indonesia": ["BBRI"],
    "bri": ["BBRI"],
    "bank mandiri": ["BMRI"],
    "mandiri": ["BMRI"],
    "bank negara indonesia": ["BBNI"],
    "bni": ["BBNI"],
    "bank tabungan negara": ["BBTN"],
    "btn": ["BBTN"],
    "bank syariah indonesia": ["BRIS"],
    "bsi": ["BRIS"],
    "btpn syariah": ["BTPS"],
    "bank syariah": ["BRIS", "BTPS"],
    "telkom": ["TLKM"],
}

# phrase (lowercase) -> sub_sector slug (Sectors uses kebab-case slugs, e.g. "banks")
SECTOR_ALIASES: dict[str, str] = {
    "perbankan": "banks",
    "bank-bank": "banks",
    "sektor bank": "banks",
    "banking": "banks",
    "banks": "banks",
    "telekomunikasi": "telecommunication",
    "telecommunication": "telecommunication",
    "telco": "telecommunication",
}

# Upper-case 4-letter tokens that are finance jargon, not tickers.
NON_TICKERS = {
    "CASA", "BOPO", "EBIT", "IHSG", "BUMN", "RUPS", "RUPST", "LQ45", "NSFR", "TBK",
    "NPL", "ROA", "ROE", "NIM", "LDR", "CAR", "YOY", "QOQ", "EPS", "OJK", "WIB",
}

MAX_TICKER_VERIFICATIONS = 3

_TICKER_RE = re.compile(r"\b([A-Za-z]{4})(?:\.JK)?\b")


class EntityResolver:
    def __init__(self, service: SectorsService) -> None:
        self.service = service

    def resolve(self, state: AgentState) -> Entities:
        text = state.query
        lowered = text.lower()
        entities = Entities()
        seen: set[str] = set()

        def add(symbol: str, matched: str, method: str) -> None:
            if symbol not in seen:
                seen.add(symbol)
                entities.companies.append(
                    ResolvedCompany(symbol=symbol, matched_text=matched, method=method)  # type: ignore[arg-type]
                )

        # 1) Aliases, longest first so "bank syariah indonesia" wins over "bank syariah".
        consumed = lowered
        for alias in sorted(COMPANY_ALIASES, key=len, reverse=True):
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, consumed):
                candidates = COMPANY_ALIASES[alias]
                if len(candidates) == 1:
                    add(candidates[0], alias, "alias")
                else:
                    entities.ambiguous.append(AmbiguousMention(text=alias, candidates=candidates))
                consumed = re.sub(pattern, " ", consumed)

        # 2) Explicit tickers (upper-case in the query, or matching the watchlist).
        known = set(COMPANY_ALIASES_TICKERS)
        for match in _TICKER_RE.finditer(text):
            token = match.group(1)
            upper = token.upper()
            if upper in NON_TICKERS:
                continue
            if token.isupper() or upper in known:
                if upper in known:
                    add(upper, token, "ticker")
                elif token.isupper():
                    entities.unknown.append(upper)

        for sym in state.watchlist:
            bare = bare_symbol(sym)
            if bare in known:
                add(bare, sym, "ticker")
            elif bare not in entities.unknown:
                entities.unknown.append(bare)

        # 3) Sector.
        for phrase in sorted(SECTOR_ALIASES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(phrase)}\b", lowered):
                entities.sub_sector = SECTOR_ALIASES[phrase]
                entities.sector_text = phrase
                break
        if state.requested_sub_sector:
            entities.sub_sector = state.requested_sub_sector

        # 4) Verify tickers the agent does not know yet (bounded number of calls).
        unknown, unverified = [], []
        for i, token in enumerate(dict.fromkeys(entities.unknown)):
            if i >= MAX_TICKER_VERIFICATIONS:
                unverified.append(token)
                continue
            # Same sections as FinancialContext so a later report fetch is a cache hit.
            result = self.service.company_report(token, ("overview", "financials"))
            if result.ok and result.data is not None:
                add(token, token, "ticker")
                entities.companies[-1].company_name = result.data.company_name
            elif result.status == "not_found":
                unknown.append(token)
            elif result.status == "credit_cap":
                # Not a doubtful ticker: the credit cap stopped the check. Keep it in scope so
                # the briefing reports the cap instead of asking which company was meant.
                add(token, token, "ticker")
                record_tool_failure(state, token, "credit_cap", token)
            else:
                unverified.append(token)
        entities.unknown, entities.unverified = unknown, unverified
        return entities

    def verify_sub_sector(self, slug: str) -> bool:
        result = self.service.list_subsectors()
        return bool(result.ok and result.data and slug in result.data)

    def sector_members(self, slug: str, limit: int = 12) -> list[ResolvedCompany] | None:
        result = self.service.list_companies(slug, limit)
        if not result.ok or result.data is None:
            return None
        return [
            ResolvedCompany(
                symbol=bare_symbol(c.symbol), matched_text=slug, method="sector_member",
                company_name=c.company_name,
            )
            for c in result.data
        ]


# Tickers the agent can recognise from lower-case text without verification.
COMPANY_ALIASES_TICKERS = sorted({s for v in COMPANY_ALIASES.values() for s in v})
