"use client";

import { useId, useState } from "react";
import { type PeerMetric, formatPercent, periodLabel } from "@/lib/agent";

const colors = ["#9edab5", "#a3b8ef", "#dac28a", "#b7a3d9"];

export default function PeerChart({ metrics, labels, onEvidence }: {
  metrics: PeerMetric[];
  labels: Record<string, string>;
  onEvidence: (metric: string, symbol: string) => void;
}) {
  const id = useId();
  const [selected, setSelected] = useState("roe");
  const metric = metrics.find(m => m.metric === selected) ?? metrics[0];
  if (!metric) return null;
  const rows = Object.entries(metric.values).filter(([, value]) => Number.isFinite(value));
  const symbols = [...new Set([...rows.map(([symbol]) => symbol), ...metric.missing])];
  const values = rows.map(([, value]) => value);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const position = (value: number) => (value - min) / span * 100;
  const label = (name: string) => labels[name] ?? (name === "cost_to_income_ratio" ? "Cost-to-income" : name);

  return <section className="panel live-peer-chart" aria-labelledby={`${id}-title`}>
    <div className="section-header">
      <div><span className="eyebrow">GRAFIK PERBANDINGAN</span><h2 id={`${id}-title`}>{label(metric.metric)} antar emiten</h2></div>
      <label className="sr-only" htmlFor={`${id}-metric`}>Metrik grafik perbandingan</label>
      <select id={`${id}-metric`} className="metric-select" value={metric.metric} onChange={e => setSelected(e.target.value)}>
        {metrics.map(m => <option key={m.metric} value={m.metric}>{label(m.metric)}</option>)}
      </select>
    </div>
    <div className="chart-meta"><span>{metric.period ? periodLabel(metric.period) : "Periode berbeda per emiten"} · %</span><span>{symbols.length} emiten</span></div>
    <div className="peer-bars">
      {symbols.map((symbol, index) => {
        const value = metric.values[symbol];
        const available = Number.isFinite(value);
        const period = metric.period ?? metric.periods[symbol];
        return <button key={symbol} className="peer-bar-row" disabled={!available}
          aria-label={`${symbol}, ${label(metric.metric)} ${available ? formatPercent(value) : "tidak tersedia"}, ${periodLabel(period)}${available ? ". Lihat bukti" : ""}`}
          onClick={() => onEvidence(metric.metric, symbol)}>
          <span className="peer-bar-symbol">{symbol}{!metric.aligned && <small>{periodLabel(period)}</small>}</span>
          <span className="peer-bar-track" aria-hidden="true">
            <span className="peer-bar-zero" style={{ left: `${position(0)}%` }} />
            {available && <span className="peer-bar-fill" style={{ left: `${position(Math.min(0, value))}%`, width: `${Math.abs(value) / span * 100}%`, background: colors[index % colors.length] }} />}
          </span>
          <span className="peer-bar-value">{available ? formatPercent(value) : "—"}</span>
        </button>;
      })}
      {rows.length > 0 && <div className="peer-bar-axis" aria-hidden="true"><span>{formatPercent(min)}</span><span>{formatPercent(max)}</span></div>}
      {rows.length === 0 && <p className="muted">Belum ada nilai yang tersedia untuk metrik ini.</p>}
    </div>
    <div className="panel-footnote">Klik batang untuk melihat bukti. Setiap metrik memakai skalanya sendiri; nilai lebih tinggi tidak selalu lebih baik.</div>
  </section>;
}
