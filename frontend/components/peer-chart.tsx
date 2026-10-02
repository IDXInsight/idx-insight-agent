"use client";

import { type PeerMetric, type MetricDirection, formatPercent, periodLabel } from "@/lib/agent";

// Categorical slots validated for the dark surface (#191e1a): lightness band, chroma,
// colour-blind and normal-vision separation, 3:1 contrast. Assigned by entity, never by rank.
export const seriesColors = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
const overflowColor = "#7d8a81";

export function colorFor(symbol: string, symbols: string[]): string {
  const index = symbols.indexOf(symbol);
  return index >= 0 && index < seriesColors.length ? seriesColors[index] : overflowColor;
}

type Props = {
  metrics: PeerMetric[];
  symbols: string[];
  labels: Record<string, string>;
  directions: Record<string, MetricDirection>;
  onEvidence: (metric: string, symbol: string) => void;
};

/** Small multiples: one column chart per metric, each on its own scale, with the peer median. */
export default function PeerChart({ metrics, symbols, labels, directions, onEvidence }: Props) {
  if (!metrics.length) return null;
  return <section className="panel live-peer-chart" aria-labelledby="peer-chart-title">
    <div className="section-header">
      <div><span className="eyebrow">GRAFIK PERBANDINGAN</span><h2 id="peer-chart-title">Satu grafik per metrik</h2></div>
      <ul className="chart-legend" aria-label="Warna emiten">{symbols.map(symbol => <li key={symbol}><span style={{ background: colorFor(symbol, symbols) }} />{symbol}</li>)}</ul>
    </div>
    <p className="chart-howto">Setiap grafik memakai skalanya sendiri dan diurutkan dari nilai yang umumnya lebih baik. Garis putus-putus adalah median peer. Arahkan kursor atau klik kolom untuk melihat nilai dan buktinya.</p>
    <div className="small-multiples">
      {metrics.map(metric => <MetricColumns key={metric.metric} metric={metric} symbols={symbols} label={labels[metric.metric] ?? metric.metric} direction={directions[metric.metric] ?? null} onEvidence={onEvidence} />)}
    </div>
  </section>;
}

function MetricColumns({ metric, symbols, label, direction, onEvidence }: {
  metric: PeerMetric; symbols: string[]; label: string; direction: MetricDirection; onEvidence: Props["onEvidence"];
}) {
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
  const hint = direction === "higher" ? "↑ umumnya lebih baik" : direction === "lower" ? "↓ umumnya lebih baik" : "tanpa arah tunggal";

  return <figure className="sm-card">
    <figcaption><strong>{label}</strong><span>{metric.period ? periodLabel(metric.period) : "Periode berbeda"} · {hint}{median !== null && <> · <i className="sm-median-key" aria-hidden="true" /> median {formatPercent(median)}</>}</span></figcaption>
    <div className="sm-plot" role="group" aria-label={`${label}, ${available.length} emiten`}>
      <span className="sm-zero" style={{ top: `${y(0)}%` }} aria-hidden="true" />
      {median !== null && <span className="sm-median" style={{ top: `${y(median)}%` }} aria-hidden="true" />}
      {sorted.map(([symbol, value]) => {
        const period = metric.period ?? metric.periods[symbol];
        const vsMedian = median === null ? "" : value > median ? "di atas median" : value < median ? "di bawah median" : "sama dengan median";
        return <button key={symbol} className="sm-col" onClick={() => onEvidence(metric.metric, symbol)}
          aria-label={`${symbol}: ${label} ${formatPercent(value)}, ${periodLabel(period)}${vsMedian ? `, ${vsMedian}` : ""}. Lihat bukti`}>
          <span className="sm-bar" aria-hidden="true" style={{ top: `${y(Math.max(0, value))}%`, height: `${Math.abs(value) / span * 100}%`, background: colorFor(symbol, symbols) }} />
          <span className="sm-tip" aria-hidden="true"><b>{symbol}</b>{formatPercent(value)}<small>{periodLabel(period)}{vsMedian ? ` · ${vsMedian}` : ""}{metric.outliers.includes(symbol) ? " · outlier" : ""}</small></span>
        </button>;
      })}
      {missing.map(symbol => <span key={symbol} className="sm-col sm-missing" title="Tidak tersedia atau dikeluarkan dari perbandingan" aria-label={`${symbol}: tidak tersedia`} />)}
      {!available.length && <p className="sm-empty">Belum ada nilai untuk metrik ini.</p>}
    </div>
    <div className="sm-axis" aria-hidden="true">
      {sorted.map(([symbol, value]) => <span key={symbol}><b>{symbol}</b>{formatPercent(value)}</span>)}
      {missing.map(symbol => <span key={symbol}><b>{symbol}</b>—</span>)}
    </div>
  </figure>;
}
