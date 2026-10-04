/** Historical ratios derived from numeric, sourced agent evidence. No chart fixtures. */
import type { AgentResponse, EvidenceItem } from "./agent.ts";

const reportFields: Record<string, string> = {
  roa: "profitability.roa",
  roe: "profitability.roe",
  net_interest_margin: "profitability.net_interest_margin",
  cost_to_income_ratio: "profitability.cost_to_income_ratio",
  casa_ratio: "liquidity.casa_ratio",
  loan_to_deposit_ratio: "liquidity.loan_to_deposit_ratio",
  capital_adequacy_ratio: "capital.capital_adequacy_ratio",
};

export type TrendPoint = {
  period: string;
  value: number;
  change: number | null;
  evidence: EvidenceItem;
};

export type TrendSeries = {
  metric: string;
  symbol: string;
  points: TrendPoint[];
  median: number | null;
  medianPeriod: string | null;
};

const isPeriod = (period: string | null): period is string =>
  typeof period === "string" && /^\d{4}(?:-\d{2}-\d{2})?$/.test(period);

export function buildTrends(
  result: Pick<AgentResponse, "peer_comparison" | "evidence" | "tool_calls">,
  order: string[],
): TrendSeries[] {
  const successfulCalls = new Set(result.tool_calls.filter(call => call.status === "ok").map(call => call.call_id));
  const trends: TrendSeries[] = [];

  for (const peer of Object.values(result.peer_comparison)) {
    const field = reportFields[peer.metric];
    if (!field) continue;
    const symbols = [...new Set([...order, ...Object.keys(peer.values)])].filter(symbol => peer.values[symbol] !== undefined);
    for (const symbol of symbols) {
      const byPeriod = new Map<string, EvidenceItem[]>();
      for (const evidence of result.evidence) {
        if (evidence.symbol !== symbol || evidence.field !== field || evidence.unit !== "ratio"
          || !isPeriod(evidence.period) || typeof evidence.value !== "number"
          || !Number.isFinite(evidence.value) || !evidence.source_ref || !successfulCalls.has(evidence.call_id)) continue;
        byPeriod.set(evidence.period, [...(byPeriod.get(evidence.period) ?? []), evidence]);
      }
      const points: TrendPoint[] = [...byPeriod.entries()].sort(([a], [b]) => a.localeCompare(b))
        .filter(([, items]) => items.every(item => item.value === items[0].value))
        .map(([period, items]) => ({ period, value: items[0].value as number, change: null, evidence: items[0] }));
      if (points.length < 2) continue;
      const latest = points.at(-1)!;
      if (peer.period === latest.period && Math.abs(latest.value - peer.values[symbol]) > 1e-8) continue;
      for (let i = 1; i < points.length; i++) points[i].change = points[i].value - points[i - 1].value;
      trends.push({
        metric: peer.metric,
        symbol,
        points,
        median: peer.period === latest.period && Number.isFinite(peer.median) ? peer.median : null,
        medianPeriod: peer.period === latest.period ? peer.period : null,
      });
    }
  }
  return trends;
}
