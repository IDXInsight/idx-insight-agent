"""Pydantic models for Sectors responses.

Field names follow the official Sectors v2 REST documentation
(https://docs.sectors.app/api-references/v2/indonesia/...). Models allow extra
fields so the real API can return more than we model.

Shapes that are NOT verified against the docs are marked ``UNVERIFIED`` and must
be confirmed during the real-integration phase before relying on them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _SectorsModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def bare_symbol(symbol: str) -> str:
    """Sectors returns ``BBCA.JK`` but tools expect bare ``BBCA``."""
    return symbol.upper().removesuffix(".JK")


# --- /v2/filings/  (MCP: fetch-filings) --------------------------------------


class Filing(_SectorsModel):
    title: str
    body: str | None = None
    source: str | None = None
    timestamp: str
    sector: str | None = None
    sub_sector: str | None = None
    tags: list[str] = []
    symbol: str
    transaction_type: str | None = None
    holder_type: str | None = None
    holder_name: str | None = None
    holding_before: float | None = None
    holding_after: float | None = None
    amount_transaction: float | None = None
    price: float | None = None
    transaction_value: float | None = None
    share_percentage_before: float | None = None
    share_percentage_after: float | None = None
    share_percentage_transaction: float | None = None


class Pagination(_SectorsModel):
    total_count: int
    showing: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
    next_offset: int | None = None
    previous_offset: int | None = None


class FilingsPage(_SectorsModel):
    results: list[Filing]
    pagination: Pagination


# --- /v2/company/corporate-actions/{symbol}/  (MCP: fetch-corporate-actions) --


class AGM(_SectorsModel):
    agm_date: str
    agm_time: str | None = None
    agm_place: str | None = None
    agm_result: Any = None


class Dividend(_SectorsModel):
    ex_date: str
    payment_date: str | None = None
    dividend_yield: float | None = None
    dividend_amount: float | None = None


class StockSplit(_SectorsModel):
    date: str
    split_ratio: float


class CorporateActionsBody(_SectorsModel):
    agm: list[AGM] | None = None
    bonus: Any = None
    warrant: Any = None
    dividend: list[Dividend] | None = None
    right_issue: Any = None
    stock_split: list[StockSplit] | None = None
    # Documented example is null; the populated shape is UNVERIFIED.
    upcoming_dividend: Any = None


class CorporateActions(_SectorsModel):
    symbol: str
    corporate_actions: CorporateActionsBody


# --- /v2/financials/quarterly/{symbol}/  (MCP: fetch-quarterly-financials) ----


class FinancialsSectorMetrics(_SectorsModel):
    net_interest_income: float | None = None
    gross_loan: float | None = None
    total_deposit: float | None = None


class QuarterlyFinancial(_SectorsModel):
    symbol: str
    date: str
    revenue: float | None = None
    earnings: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_liabilities: float | None = None
    stockholders_equity: float | None = None
    operating_expense: float | None = None
    operating_pnl: float | None = None
    earnings_before_tax: float | None = None
    tax: float | None = None
    ebit: float | None = None
    ebitda: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    net_cash_flow: float | None = None
    financials_sector_metrics: FinancialsSectorMetrics | None = None


# --- /v2/company/get_quarterly_financial_dates/{symbol}/ ----------------------
# Documented as {"2026": [["2026-03-31", "q1"]]}: year -> [report_date, label].

QuarterlyFinancialDates = dict[str, list[tuple[str, str]]]


# --- /v2/company/report/{symbol}/  (MCP: fetch-company-report) ----------------


class RatioProfitability(_SectorsModel):
    roa: float | None = None
    roe: float | None = None
    efficiency_ratio: float | None = None
    net_profit_margin: float | None = None
    net_interest_margin: float | None = None
    cost_to_income_ratio: float | None = None
    operating_profit_margin: float | None = None


class RatioLiquidity(_SectorsModel):
    casa_ratio: float | None = None
    leverage_ratio: float | None = None
    loan_to_deposit_ratio: float | None = None
    liquidity_coverage_ratio: float | None = None
    operating_cash_flow_margin: float | None = None


class RatioCapital(_SectorsModel):
    capital_adequacy_ratio: float | None = None


class HistoricalFinancialRatio(_SectorsModel):
    # Category keys are documented; the per-entry ``year`` key is UNVERIFIED.
    year: int
    profitability: RatioProfitability | None = None
    liquidity: RatioLiquidity | None = None
    capital: RatioCapital | None = None


class ReportFinancials(_SectorsModel):
    historical_financial_ratio: list[HistoricalFinancialRatio] = []
    yoy_quarter_earnings_growth: float | None = None
    yoy_quarter_revenue_growth: float | None = None


class ReportOverview(_SectorsModel):
    sector: str | None = None
    sub_sector: str | None = None
    industry: str | None = None
    listing_board: str | None = None
    market_cap: float | None = None
    latest_close_date: str | None = None
    last_close_price: float | None = None


class CompanyReport(_SectorsModel):
    symbol: str
    company_name: str | None = None
    overview: ReportOverview | None = None
    financials: ReportFinancials | None = None


# --- Company listing (MCP: fetch-companies-by-subsector / get-subsectors) ------
# UNVERIFIED: the response shape of the company listing tool is not modelled from
# docs yet. CompanyRef is our internal minimum and the real adapter must map to it.


class CompanyRef(_SectorsModel):
    symbol: str
    company_name: str
    sub_sector: str
