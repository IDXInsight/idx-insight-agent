"""Public API contract (request/response) for the agent endpoint."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from idx_insight.agent.language import Language
from idx_insight.agent.state import (
    Briefing,
    EvidenceAssessment,
    LLMCallRecord,
    RecoveryAction,
    SecondHopDecision,
    TraceStep,
    ValidationIssue,
)
from idx_insight.models import EventType, Evidence


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    as_of: date | None = Field(default=None, description="Reference date; defaults to today.")
    watchlist: list[str] = Field(default=[], max_length=20)
    sub_sector: str | None = Field(default=None, max_length=64)
    language: Language | None = Field(
        default=None, description="Briefing language; detected from the query when omitted.")

    @field_validator("watchlist")
    @classmethod
    def _tickers(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip().upper().removesuffix(".JK") for v in value if v.strip()]
        for ticker in cleaned:
            if not (len(ticker) == 4 and ticker.isalpha()):
                raise ValueError(f"invalid IDX ticker: {ticker!r}")
        return cleaned


class Scope(BaseModel):
    intent: str | None
    intent_source: str | None
    advice_requested: bool
    companies: list[str]
    ambiguous: dict[str, list[str]]
    sub_sector: str | None
    timeframe: dict[str, Any] | None
    plan: list[str]
    plan_source: str | None


class EventOut(BaseModel):
    event_id: str
    symbol: str
    event_type: EventType
    event_date: str
    title: str
    relevance_score: int
    relevance_reasons: list[str]
    forward_looking: bool
    source_ref: str
    evidence_ids: list[str]
    second_hop: str | None = None  # research | reuse | skip


class ClaimOut(BaseModel):
    claim_id: str
    kind: str
    statement: str
    symbols: list[str]
    metric: str | None
    period: str | None
    evidence_ids: list[str]


class ValidationOut(BaseModel):
    status: str
    accepted: int
    rejected: int
    issues: list[ValidationIssue]
    assessment: EvidenceAssessment


class ToolCallOut(BaseModel):
    call_id: str
    tool: str
    status: str
    attempts: int


class QueryResponse(BaseModel):
    status: str
    language: Language
    data_source: str
    llm_provider: str
    briefing: Briefing
    scope: Scope
    events: list[EventOut]
    second_hop: list[SecondHopDecision]
    peer_comparison: dict[str, Any]
    claims: list[ClaimOut]
    evidence: list[Evidence]
    validation: ValidationOut
    recovery: list[RecoveryAction]
    llm_calls: list[LLMCallRecord]
    trace: list[TraceStep]
    tool_calls: list[ToolCallOut]
