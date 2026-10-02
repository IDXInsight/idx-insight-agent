"use client";

import { useState } from "react";
import { AlertTriangle, ArrowRight, ArrowUpRight, Check, CircleHelp, Clock3, ListFilter, Search, ShieldCheck, Sparkles } from "lucide-react";
import { type AgentEvent, type AgentResponse, type EvidenceItem, dayMonth, eventTypeLabels, formatPercent, periodLabel } from "@/lib/agent";

/** What the evidence drawer shows for a live finding: the claim plus the evidence rows it cites. */
export type LiveEvidence = {
  title: string;
  ticker: string;
  period?: string;
  detail?: string;
  items: EvidenceItem[];
  reasons?: string[];
  sourceRef?: string;
  secondHop?: string | null;
};

const statusLabels: Record<AgentResponse["status"], string> = {
  completed: "Bukti lengkap", partial: "Bukti sebagian", needs_clarification: "Perlu klarifikasi", insufficient_evidence: "Bukti belum cukup",
};
const secondHopLabels: Record<string, string> = { research: "Diteliti lebih lanjut", reuse: "Memakai konteks yang ada", skip: "Tidak diteliti lanjut" };
const metricFallbackLabels: Record<string, string> = { cost_to_income_ratio: "Cost-to-income" };

export function secondHopLabel(decision: string | null | undefined): string | undefined {
  return decision ? secondHopLabels[decision] ?? decision : undefined;
}

type Props = {
  result: AgentResponse;
  metricLabels: Record<string, string>;
  onEvidence: (evidence: LiveEvidence) => void;
  onTrace: () => void;
};

/** Renders a real agent response with the prototype's panels; only data the backend returned is shown. */
export default function LiveResult({ result, metricLabels, onEvidence, onTrace }: Props) {
  const [filter, setFilter] = useState("Semua");
  const byId = new Map(result.evidence.map(e => [e.evidence_id, e]));
  const claims = new Map(result.claims.map(c => [c.claim_id, c]));
  const evidenceFor = (ids: string[]) => ids.map(id => byId.get(id)).filter((e): e is EvidenceItem => !!e);
  const { briefing } = result;
  const peers = Object.values(result.peer_comparison);
  const peerSymbols = [...new Set(peers.flatMap(p => [...Object.keys(p.values), ...p.missing]))];
  const eventTypes = ["Semua", ...new Set(result.events.map(e => eventTypeLabels[e.event_type]))];
  const events = result.events.filter(e => filter === "Semua" || eventTypeLabels[e.event_type] === filter);
  const warn = result.status !== "completed";
  // Single-company values already shown in the peer table are not repeated as findings.
  const inTable = (claimIds: string[]) => claimIds.length > 0 && claimIds.every(id => {
    const c = claims.get(id);
    return c?.kind === "metric" && !!c.metric && c.metric in result.peer_comparison;
  });
  const sections = briefing.sections
    .map(section => ({ ...section, findings: section.findings.filter(f => !inTable(f.claim_ids)) }))
    .filter(section => section.findings.length > 0);

  function openClaims(claimIds: string[], title: string) {
    const cited = claimIds.map(id => claims.get(id)).filter(c => !!c);
    const first = cited[0];
    onEvidence({
      title,
      ticker: first?.symbols.join(", ") || "—",
      period: first?.period ? periodLabel(first.period) : undefined,
      items: evidenceFor(cited.flatMap(c => c.evidence_ids)),
    });
  }
  function openPeerValue(metric: string, symbol: string) {
    const claim = result.claims.find(c => c.kind === "metric" && c.metric === metric && c.symbols.includes(symbol));
    if (claim) openClaims([claim.claim_id], claim.statement);
  }
  function openEvent(event: AgentEvent) {
    onEvidence({
      title: event.title, ticker: event.symbol, period: event.event_date, items: evidenceFor(event.evidence_ids),
      reasons: event.relevance_reasons, sourceRef: event.source_ref, secondHop: event.second_hop,
    });
  }

  return <>
    <section className="briefing panel">
      <div className="section-header"><h2><Sparkles size={17} /> {briefing.clarification_question ? "Perlu klarifikasi" : "Yang perlu diperhatikan"}</h2><span className={`status-pill ${warn ? "warn" : ""}`}>{warn ? <AlertTriangle size={12} /> : <Check size={12} />} {statusLabels[result.status]}</span></div>
      <p>{briefing.clarification_question ?? briefing.summary}</p>
      {briefing.narrative?.length ? <div className="narrative">{briefing.narrative.map((s, i) => <p key={i}>{s.text}</p>)}</div> : null}
      <div className="briefing-bottom"><span><ShieldCheck size={14} /> {result.validation.accepted} temuan tervalidasi{result.validation.rejected ? ` · ${result.validation.rejected} ditolak` : ""}</span><button className="text-button" onClick={onTrace}>Lihat proses riset <ArrowRight size={14} /></button></div>
    </section>

    {peers.length > 0 && <section className="panel peer-panel"><div className="section-header"><div><span className="eyebrow">PERBANDINGAN METRIK</span><h2>Periode disejajarkan per metrik</h2></div><span className={`status-pill ${peers.every(p => p.aligned) ? "" : "warn"}`}>{peers.every(p => p.aligned) ? <><Check size={12} /> Periode sejajar</> : <><AlertTriangle size={12} /> Periode berbeda</>}</span></div>
      <div className="table-scroll"><table><caption className="sr-only">Perbandingan metrik dari data Sectors. Klik angka untuk melihat bukti.</caption>
        <thead><tr><th>Emiten</th>{peers.map(p => <th key={p.metric}>{metricLabels[p.metric] ?? metricFallbackLabels[p.metric] ?? p.metric}<br /><small>{p.period ? periodLabel(p.period) : "Periode campuran"}</small></th>)}</tr></thead>
        <tbody>{peerSymbols.map(symbol => <tr key={symbol}><th><span className="table-bank"><span className="bank-mark">{symbol.slice(0, 2)}</span>{symbol}</span></th>{peers.map(p => {
          const value = p.values[symbol];
          return <td key={p.metric}>{value === undefined ? <span className="muted" title="Tidak tersedia atau dikeluarkan dari perbandingan">—</span> : <button onClick={() => openPeerValue(p.metric, symbol)} aria-label={`Lihat bukti ${metricLabels[p.metric] ?? metricFallbackLabels[p.metric] ?? p.metric} ${symbol}`}>{formatPercent(value)}<ArrowUpRight size={11} /></button>}</td>;
        })}</tr>)}</tbody>
      </table></div>
      <div className="panel-footnote">Klik angka untuk menelusuri bukti. Nilai lebih tinggi tidak selalu berarti lebih baik. “—” berarti data tidak tersedia atau dikeluarkan.</div>
    </section>}

    {(result.events.length > 0 || result.scope.intent === "discovery") && <section className="panel events-panel"><div className="section-header"><div><span className="eyebrow">DISCLOSURE RADAR</span><h2>Peristiwa yang relevan</h2></div><span className="small-counter">{events.length} kejadian</span></div>
      {result.events.length > 0 && <div className="event-filters"><ListFilter size={14} />{eventTypes.map(t => <button key={t} className={filter === t ? "selected" : ""} aria-pressed={filter === t} onClick={() => setFilter(t)}>{t}</button>)}</div>}
      {events.map(ev => { const { day, month } = dayMonth(ev.event_date); return <button className="event-row" key={ev.event_id} onClick={() => openEvent(ev)}><span className="event-date"><strong>{day}</strong><small>{month}</small></span><span className="event-content"><span className="event-labels"><b>{ev.symbol}</b><span>{eventTypeLabels[ev.event_type]}</span></span><strong>{ev.title}</strong><span className="relevance"><span className={ev.relevance_score >= 50 ? "tiny-dot" : "tiny-dot amber"} />Skor relevansi {ev.relevance_score}{ev.second_hop ? <span className="muted"> · {secondHopLabel(ev.second_hop)}</span> : null}</span></span><ArrowUpRight size={16} /></button>; })}
      {events.length === 0 && <div className="empty-state"><Search size={22} /><h3>Tidak ada peristiwa relevan</h3><p>Tidak ada peristiwa yang lolos aturan relevansi pada periode ini. Hasil kosong tidak berarti tidak ada dampak.</p>{filter !== "Semua" && <button className="text-button" onClick={() => setFilter("Semua")}>Reset filter</button>}</div>}
      {result.scope.timeframe?.label && <div className="panel-footnote"><Clock3 size={12} /> Periode: {result.scope.timeframe.label}</div>}
    </section>}

    {sections.map(section => <section className="panel findings-panel" key={section.heading}><div className="section-header"><div><span className="eyebrow">TEMUAN</span><h2>{section.heading}</h2></div><span className="small-counter">{section.findings.length}</span></div>
      <div className="finding-list">{section.findings.map((f, i) => f.claim_ids.length
        ? <button className="finding" key={i} onClick={() => openClaims(f.claim_ids, f.text)}><span><strong>{f.text}</strong>{f.why && <small>{f.why}</small>}</span><ArrowUpRight size={14} /></button>
        : <div className="finding" key={i}><span><strong>{f.text}</strong>{f.why && <small>{f.why}</small>}</span></div>)}</div>
    </section>)}

    {(briefing.data_gaps.length > 0 || briefing.assumptions.length > 0) && <section className="data-note"><CircleHelp size={17} /><div><strong>Ketahui batas datanya</strong>{briefing.data_gaps.map(g => <p key={g}>{g}</p>)}{briefing.assumptions.map(a => <p key={a}>Asumsi: {a}</p>)}</div></section>}
    <p className="boundary-note"><ShieldCheck size={13} /> {briefing.boundary_note}</p>
  </>;
}
