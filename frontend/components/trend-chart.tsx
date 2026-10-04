"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, ChartNoAxesCombined, FileCheck2 } from "lucide-react";
import { PointsChart } from "@/components/ui/points-chart";
import type { LiveEvidence } from "@/components/live-result";
import { type AgentResponse, type MetricInfo, periodLabel } from "@/lib/agent";
import { type Lang, t } from "@/lib/i18n";
import { colorFor } from "@/lib/palette";
import { buildTrends } from "@/lib/trends";

type Props = {
  result: AgentResponse;
  info: Record<string, MetricInfo>;
  order: string[];
  lang: Lang;
  onEvidence: (evidence: LiveEvidence) => void;
};

/** A line chart only when the response contains at least two sourced periods. */
export default function TrendChart({ result, info, order, lang, onEvidence }: Props) {
  const trends = useMemo(() => buildTrends(result, order), [result, order]);
  const [metricChoice, setMetricChoice] = useState("roe");
  const [symbolChoice, setSymbolChoice] = useState(order[0] ?? "");
  const metricNames = [...new Set(trends.map(trend => trend.metric))];
  const metric = metricNames.includes(metricChoice) ? metricChoice : metricNames[0];
  const symbols = trends.filter(trend => trend.metric === metric).map(trend => trend.symbol);
  const symbol = symbols.includes(symbolChoice) ? symbolChoice : symbols[0];
  const selected = trends.find(trend => trend.metric === metric && trend.symbol === symbol);
  const label = info[metric]?.[lang] ?? metric;

  function openEvidence() {
    if (!selected) return;
    onEvidence({
      title: `${label} · ${selected.symbol}`,
      ticker: selected.symbol,
      period: selected.points.map(point => periodLabel(point.period)).join(" → "),
      items: selected.points.map(point => point.evidence),
    });
  }

  return <section className="panel trend-panel" aria-labelledby="trend-chart-title">
    <div className="section-header"><div><span className="eyebrow"><ChartNoAxesCombined size={13} /> {t(lang, "trend.eyebrow")}</span><h2 id="trend-chart-title">{t(lang, "trend.title")}</h2></div>
      {selected && <span className="small-counter">{t(lang, "trend.periods", { n: selected.points.length })}</span>}</div>
    <p className="trend-intro">{t(lang, "trend.intro")}</p>
    {selected ? <>
      <div className="trend-controls">
        <label>{t(lang, "trend.metric")}<select value={metric} onChange={event => setMetricChoice(event.target.value)}>
          {metricNames.map(name => <option key={name} value={name}>{info[name]?.[lang] ?? name}</option>)}
        </select></label>
        <div className="trend-banks" role="group" aria-label={t(lang, "trend.bank")}>
          {symbols.map(name => <button key={name} className={name === symbol ? "selected" : ""} aria-pressed={name === symbol} onClick={() => setSymbolChoice(name)}>
            <span style={{ background: colorFor(name, order) }} />{name}
          </button>)}
        </div>
      </div>
      <PointsChart className="trend-visual" title={`${label} · ${symbol}`} lang={lang} lineColor={colorFor(symbol, order)}
        headerRight={`${periodLabel(selected.points[0].period)} — ${periodLabel(selected.points.at(-1)!.period)}`}
        data={selected.points.map(point => ({ date: periodLabel(point.period), total: point.value * 100,
          change: point.change === null ? null : point.change * 100 }))}
        levels={selected.median === null ? [] : [{ value: selected.median * 100, color: "#b6d8be", label: t(lang, "trend.median", { period: periodLabel(selected.medianPeriod) }) }]} />
      <div className="trend-footer"><p>{t(lang, "trend.note")}</p><button className="text-button" onClick={openEvidence}><FileCheck2 size={14} /> {t(lang, "trend.evidence")} <ArrowUpRight size={13} /></button></div>
    </> : <p className="trend-empty">{t(lang, "trend.empty")}</p>}
  </section>;
}
