"""Domain models shared by the agent, analytics and API layers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "ownership_change",
    "agm",
    "dividend_ex",
    "dividend_payment",
    "stock_split",
]


class Evidence(BaseModel):
    """One traceable datum retrieved from Sectors."""

    evidence_id: str
    call_id: str
    tool: str
    symbol: str | None = None
    period: str | None = None  # "2026-06-30", "2025", or an event date
    field: str  # e.g. "earnings", "profitability.roe", "filing"
    value: float | str | None = None
    unit: str | None = None  # "IDR", "ratio", "shares", "date", "text"
    source_ref: str
    note: str | None = None


class Event(BaseModel):
    event_id: str
    symbol: str
    company_name: str | None = None
    event_type: EventType
    event_date: str
    title: str
    source_ref: str
    evidence_ids: list[str] = []
    attributes: dict[str, Any] = {}
    forward_looking: bool = False
    duplicate_of: str | None = None
    relevance_score: int = 0
    relevance_reasons: list[str] = []


class MetricValue(BaseModel):
    symbol: str
    metric: str
    period: str
    value: float
    unit: Literal["ratio", "IDR", "pct_change"]
    evidence_ids: list[str]
    derived: bool = False
    # For derived values: input name -> evidence id (e.g. {"current": "ev-004"}).
    inputs: dict[str, str] = {}
    note: str | None = None


ClaimKind = Literal["metric", "comparison", "trend", "event", "calculation"]


class Claim(BaseModel):
    """A statement the briefing may make — only if the validator accepts it."""

    claim_id: str
    kind: ClaimKind
    statement: str
    symbols: list[str]
    metric: str | None = None
    period: str | None = None
    value: float | None = None
    evidence_ids: list[str] = []
    # For calculations: names of inputs that must each be backed by evidence.
    required_inputs: list[str] = []
    input_evidence: dict[str, str] = {}
    meta: dict[str, Any] = Field(default_factory=dict)
