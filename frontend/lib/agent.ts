/**
 * Types and display helpers for the IDX Insight Agent API (`POST /v1/agent/query`).
 * Mirrors `backend/idx_insight/api/schemas.py`; only the fields the UI renders are typed.
 */

export type EvidenceItem = {
  evidence_id: string;
  call_id: string;
  tool: string;
  symbol: string | null;
  period: string | null;
  field: string;
  value: number | string | null;
  unit: string | null;
  source_ref: string;
  note: string | null;
};

export type AgentEvent = {
  event_id: string;
  symbol: string;
  event_type: "ownership_change" | "agm" | "dividend_ex" | "dividend_payment" | "stock_split";
  event_date: string;
  title: string;
  relevance_score: number;
  relevance_reasons: string[];
  forward_looking: boolean;
  source_ref: string;
  evidence_ids: string[];
  second_hop: "research" | "reuse" | "skip" | null;
};

export type Claim = {
  claim_id: string;
  kind: string;
  statement: string;
  symbols: string[];
  metric: string | null;
  period: string | null;
  evidence_ids: string[];
};

export type PeerMetric = {
  metric: string;
  period: string | null;
  values: Record<string, number>;
  median: number | null;
  highest: string | null;
  lowest: string | null;
  outliers: string[];
  sufficient: boolean;
  aligned: boolean;
  periods: Record<string, string>;
  missing: string[];
};

export type AgentResponse = {
  status: "completed" | "partial" | "needs_clarification" | "insufficient_evidence";
  language: "id" | "en";
  data_source: string;
  llm_provider: string;
  briefing: {
    title: string;
    summary: string;
    sections: { heading: string; findings: { text: string; claim_ids: string[]; why: string | null }[] }[];
    data_gaps: string[];
    assumptions: string[];
    boundary_note: string;
    narrative: { text: string; citations: string[] }[] | null;
    synthesis_mode: "template" | "llm";
    clarification_question: string | null;
  };
  scope: {
    intent: string | null;
    companies: string[];
    ambiguous: Record<string, string[]>;
    timeframe: { label?: string } | null;
  };
  events: AgentEvent[];
  second_hop: { event_id: string; symbol: string; decision: string; reason: string }[];
  peer_comparison: Record<string, PeerMetric>;
  claims: Claim[];
  evidence: EvidenceItem[];
  validation: { status: string; accepted: number; rejected: number; assessment: { sufficiency: string } };
  trace: { stage: string; status: "ok" | "warning" | "skipped" | "error"; detail: string }[];
  tool_calls: { call_id: string; tool: string; status: string; attempts: number }[];
};

/** Result of `GET /api/agent/status`: whether a backend is configured and reachable. */
export type AgentStatus =
  | { live: true; dataSource: string; llmProvider: string; metrics: Record<string, string> }
  | { live: false };

export type ResultView = "discovery" | "peers" | "company";

export function viewForIntent(intent: string | null, fallback: ResultView): ResultView {
  if (intent === "discovery") return "discovery";
  if (intent === "peer_comparison") return "peers";
  if (intent === "company_context") return "company";
  return fallback;
}

export const eventTypeLabels: Record<AgentEvent["event_type"], string> = {
  ownership_change: "Kepemilikan",
  agm: "RUPS",
  dividend_ex: "Dividen",
  dividend_payment: "Dividen",
  stock_split: "Stock split",
};

const months = ["JAN", "FEB", "MAR", "APR", "MEI", "JUN", "JUL", "AGU", "SEP", "OKT", "NOV", "DES"];

export function dayMonth(isoDate: string): { day: string; month: string } {
  const [, m, d] = isoDate.split("-");
  const month = months[Number(m) - 1];
  return month && d ? { day: d.slice(0, 2), month } : { day: "—", month: isoDate };
}

/** "2026-06-30" → "Q2 2026"; annual ("2025") and other periods are shown as given. */
export function periodLabel(period: string | null | undefined): string {
  if (!period) return "—";
  const match = /^(\d{4})-(03-31|06-30|09-30|12-31)$/.exec(period);
  if (!match) return period;
  return `Q${["03-31", "06-30", "09-30", "12-31"].indexOf(match[2]) + 1} ${match[1]}`;
}

export function formatPercent(fraction: number): string {
  return `${(fraction * 100).toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

/** Formats an evidence value by its unit; ratios and changes are stored as fractions. */
export function formatEvidenceValue(item: EvidenceItem): string {
  const { value, unit } = item;
  if (value === null) return "—";
  if (typeof value === "string") return value;
  if (unit === "ratio" || unit === "pct_change") return formatPercent(value);
  if (unit === "IDR") return `Rp${value.toLocaleString("id-ID")}`;
  return value.toLocaleString("id-ID");
}

export function isUrl(value: string): boolean {
  return /^https?:\/\//.test(value);
}
