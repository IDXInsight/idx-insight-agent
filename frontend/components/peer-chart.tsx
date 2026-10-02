"use client";

import { type MetricDirection, type MetricInfo, type PeerMetric, formatPercent, periodLabel } from "@/lib/agent";
import { type Lang, t } from "@/lib/i18n";
import { colorFor } from "@/lib/palette";

type Props = {
  metrics: PeerMetric[];
  /** Order that fixes each company's colour (watchlist first). */
  order: string[];
  info: Record<string, MetricInfo>;
  lang: Lang;
  onEvidence: (metric: string, symbol: string) => void;
};

/** Small multiples: one column chart per metric, each on its own scale, with the peer median. */
export default function PeerChart({ metrics, order, info, lang, onEvidence }: Props) {
  if (!metrics.length) return null;
  const symbols = [...new Set(metrics.flatMap(m => [...Object.keys(m.values), ...m.missing]))];
  return <section className="panel live-peer-chart" aria-labelledby="peer-chart-title">
    <div className="section-header">
      <div><span className="eyebrow">{t(lang, "chart.eyebrow")}</span><h2 id="peer-chart-title">{t(lang, "chart.title")}</h2></div>
      <ul className="chart-legend" aria-label={t(lang, "chart.legend")}>{symbols.map(symbol => <li key={symbol}><span style={{ background: colorFor(symbol, order) }} />{symbol}</li>)}</ul>
    </div>
    <p className="chart-howto">{t(lang, "chart.howto")}</p>
    <div className="small-multiples">
      {metrics.map(metric => <MetricColumns key={metric.metric} metric={metric} symbols={symbols} order={order}
        label={info[metric.metric]?.[lang] ?? metric.metric} direction={info[metric.metric]?.direction ?? null} lang={lang} onEvidence={onEvidence} />)}
    </div>
  </section>;
}

function MetricColumns({ metric, symbols, order, label, direction, lang, onEvidence }: {
  metric: PeerMetric; symbols: string[]; order: string[]; label: string; direction: MetricDirection; lang: Lang; onEvidence: Props["onEvidence"];
}) {
  const pct = (value: number) => formatPercent(value, lang);
  const available = Object.entries(metric.values).filter(([, value]) => Number.isFinite(value));
  const sorted = [...available].sort(([, a], [, b]) => direction === "lower" ? a - b : b - a);
  const missing = symbols.filter(s => !available.some(([symbol]) => symbol === s));
  const values = available.map(([, v]) => v);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  // Headroom so the tallest column never touches the frame.
  const hi = max + range * 0.08;
  const lo = min < 0 ? min - range * 0.08 : 0;
  const span = hi - lo;
  const y = (value: number) => (hi - value) / span * 100;
  const median = metric.median !== null && Number.isFinite(metric.median) ? metric.median : null;
  const hint = t(lang, direction === "higher" ? "chart.higher" : direction === "lower" ? "chart.lower" : "chart.noDirection");

  return <figure className="sm-card">
    <figcaption><strong>{label}</strong><span>{metric.period ? periodLabel(metric.period) : t(lang, "chart.mixed")} · {hint}{median !== null && <> · <i className="sm-median-key" aria-hidden="true" /> {t(lang, "chart.median", { v: pct(median) })}</>}</span></figcaption>
    <div className="sm-plot" role="group" aria-label={t(lang, "chart.group", { label, n: available.length })}>
      <span className="sm-zero" style={{ top: `${y(0)}%` }} aria-hidden="true" />
      {median !== null && <span className="sm-median" style={{ top: `${y(median)}%` }} aria-hidden="true" />}
      {sorted.map(([symbol, value]) => {
        const period = metric.period ?? metric.periods[symbol];
        const vsMedian = median === null ? "" : t(lang, value > median ? "chart.above" : value < median ? "chart.below" : "chart.equal");
        const extra = `${vsMedian ? ` · ${vsMedian}` : ""}${metric.outliers.includes(symbol) ? ` · ${t(lang, "chart.outlier")}` : ""}`;
        return <button key={symbol} className="sm-col" onClick={() => onEvidence(metric.metric, symbol)}
          aria-label={`${symbol}: ${label} ${pct(value)}, ${periodLabel(period)}${extra}. ${t(lang, "chart.evidence")}`}>
          <span className="sm-bar" aria-hidden="true" style={{ top: `${y(Math.max(0, value))}%`, height: `${Math.abs(value) / span * 100}%`, background: colorFor(symbol, order) }} />
          <span className="sm-tip" aria-hidden="true"><b>{symbol}</b>{pct(value)}<small>{periodLabel(period)}{extra}</small></span>
        </button>;
      })}
      {missing.map(symbol => <span key={symbol} className="sm-col sm-missing" role="img" aria-label={`${symbol}: ${t(lang, "chart.unavailable")}`} />)}
      {!available.length && <p className="sm-empty">{t(lang, "chart.empty")}</p>}
    </div>
    <div className="sm-axis" aria-hidden="true">
      {sorted.map(([symbol, value]) => <span key={symbol}><b>{symbol}</b>{pct(value)}</span>)}
      {missing.map(symbol => <span key={symbol}><b>{symbol}</b>—</span>)}
    </div>
  </figure>;
}
