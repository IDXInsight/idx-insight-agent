"""Metric catalog: what we can compute, from which documented Sectors fields.

Only metrics traceable to documented Sectors fields are listed. Anything else
(e.g. NPL) is reported as unsupported rather than estimated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["report_ratio", "quarterly_growth", "quarterly_ratio", "screener_ratio"]


@dataclass(frozen=True)
class MetricSpec:
    name: str
    label: str
    source: Source
    # report_ratio: "<category>.<field>" in historical_financial_ratio
    # quarterly_growth: quarterly field whose YoY change is computed
    # quarterly_ratio: (numerator field, denominator field)
    # screener_ratio: (numerator, denominator) yearly screener fields, e.g. gross_loan[2025]
    path: str | tuple[str, str]
    banking_only: bool = False
    label_en: str | None = None  # English label when it differs from ``label``

    def label_in(self, lang: str) -> str:
        return self.label_en if lang == "en" and self.label_en else self.label


METRICS: dict[str, MetricSpec] = {
    m.name: m
    for m in [
        MetricSpec("roa", "ROA", "report_ratio", "profitability.roa"),
        MetricSpec("roe", "ROE", "report_ratio", "profitability.roe"),
        MetricSpec("net_interest_margin", "NIM", "report_ratio",
                   "profitability.net_interest_margin", banking_only=True),
        MetricSpec("cost_to_income_ratio", "Cost-to-income", "report_ratio",
                   "profitability.cost_to_income_ratio", banking_only=True),
        MetricSpec("casa_ratio", "CASA", "report_ratio", "liquidity.casa_ratio",
                   banking_only=True),
        MetricSpec("loan_to_deposit_ratio", "LDR", "report_ratio",
                   "liquidity.loan_to_deposit_ratio", banking_only=True),
        MetricSpec("capital_adequacy_ratio", "CAR", "report_ratio",
                   "capital.capital_adequacy_ratio", banking_only=True),
        MetricSpec("earnings_growth_yoy", "Pertumbuhan laba YoY", "quarterly_growth", "earnings",
                   label_en="Earnings growth YoY"),
        MetricSpec("revenue_growth_yoy", "Pertumbuhan pendapatan YoY", "quarterly_growth",
                   "revenue", label_en="Revenue growth YoY"),
        MetricSpec("nii_growth_yoy", "Pertumbuhan NII YoY", "quarterly_growth",
                   "financials_sector_metrics.net_interest_income", banking_only=True,
                   label_en="NII growth YoY"),
        MetricSpec("loan_growth_yoy", "Pertumbuhan kredit YoY", "quarterly_growth",
                   "financials_sector_metrics.gross_loan", banking_only=True,
                   label_en="Loan growth YoY"),
        MetricSpec("ldr_quarterly", "LDR kuartalan (kredit/DPK)", "quarterly_ratio",
                   ("financials_sector_metrics.gross_loan",
                    "financials_sector_metrics.total_deposit"), banking_only=True,
                   label_en="Quarterly LDR (loans/deposits)"),
        MetricSpec("npl_ratio", "NPL (kredit bermasalah/kredit)", "screener_ratio",
                   ("non_performing_loan", "gross_loan"), banking_only=True,
                   label_en="NPL ratio (non-performing/gross loans)"),
    ]
}

BUNDLES: dict[str, list[str]] = {
    "profitability": ["roa", "roe", "net_interest_margin", "earnings_growth_yoy"],
    "efficiency": ["cost_to_income_ratio"],
    "liquidity": ["loan_to_deposit_ratio", "casa_ratio", "ldr_quarterly"],
    "capital": ["capital_adequacy_ratio"],
    "growth": ["earnings_growth_yoy", "nii_growth_yoy", "loan_growth_yoy"],
    "asset_quality": ["npl_ratio"],
}

# Direction usually read as favourable, for display only (chart hint in the UI); it never
# changes analysis or wording. Absent = no single direction (LDR has a target band).
DIRECTION: dict[str, Literal["higher", "lower"]] = {
    "roa": "higher", "roe": "higher", "net_interest_margin": "higher",
    "cost_to_income_ratio": "lower", "casa_ratio": "higher", "capital_adequacy_ratio": "higher",
    "earnings_growth_yoy": "higher", "revenue_growth_yoy": "higher",
    "nii_growth_yoy": "higher", "loan_growth_yoy": "higher", "npl_ratio": "lower",
}

# Metrics users ask for that the agent does not compute. Reported, never guessed.
KNOWN_UNSUPPORTED: dict[str, str] = {
    "bopo": "BOPO",
    "nsfr": "NSFR",
}

# Second-hop context bundle used after an event is judged relevant.
EVENT_CONTEXT_METRICS = ["earnings_growth_yoy", "roe"]
