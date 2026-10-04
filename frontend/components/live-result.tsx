"use client";

import { useState } from "react";
import PeerChart from "@/components/peer-chart";
import TrendChart from "@/components/trend-chart";
import TickerMark from "@/components/ticker-mark";
import { DraggableWidgetGrid } from "@/components/ui/draggable-widget-grid";
import { AlertTriangle, ArrowRight, ArrowUpRight, Check, CircleHelp, Clock3, ListFilter, Search, ShieldCheck, Sparkles } from "lucide-react";
import { type AgentEvent, type AgentResponse, type EvidenceItem, type MetricInfo, dayMonth, formatPercent, periodLabel } from "@/lib/agent";
import { type Lang, type MessageKey, eventTypeLabels, t } from "@/lib/i18n";

/** What the evidence drawer shows for a live finding: the claim plus the evidence rows it cites. */
export type LiveEvidence = {
  title: string;
  ticker: string;
  period?: string;
  items: EvidenceItem[];
  reasons?: string[];
  sourceRef?: string;
  secondHop?: string | null;
};

export function secondHopLabel(decision: string | null | undefined, lang: Lang): string | undefined {
  if (!decision) return undefined;
  return ["research", "reuse", "skip"].includes(decision) ? t(lang, `live.hop.${decision}` as MessageKey) : decision;
}

type Props = {
  result: AgentResponse;
  metrics: Record<string, MetricInfo>;
  /** Order that fixes each company's colour (watchlist first). */
  colorOrder: string[];
  onEvidence: (evidence: LiveEvidence) => void;
  onTrace: () => void;
  layoutKey: string;
};

/** Renders a real agent response; only data the backend returned is shown, in the language of the briefing. */
export default function LiveResult({ result, metrics, colorOrder, onEvidence, onTrace, layoutKey }: Props) {
  const lang: Lang = result.language === "en" ? "en" : "id";
  const [filter, setFilter] = useState<string | null>(null);
  const byId = new Map(result.evidence.map(e => [e.evidence_id, e]));
  const claims = new Map(result.claims.map(c => [c.claim_id, c]));
  const evidenceFor = (ids: string[]) => ids.map(id => byId.get(id)).filter((e): e is EvidenceItem => !!e);
  const typeLabel = (type: string) => eventTypeLabels[lang][type] ?? type;
  const metricLabel = (metric: string) => metrics[metric]?.[lang] ?? metric;
  const { briefing } = result;
  const peers = Object.values(result.peer_comparison);
  const peerSymbols = [...new Set(peers.flatMap(p => [...Object.keys(p.values), ...p.missing]))];
  const eventTypes = [...new Set(result.events.map(e => typeLabel(e.event_type)))];
  const events = result.events.filter(e => filter === null || typeLabel(e.event_type) === filter);
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
    <DraggableWidgetGrid storageKey={`idx-insight.widgets.${layoutKey}.main`} lang={lang}
      labels={{ briefing: t(lang, briefing.clarification_question ? "live.clarify" : "live.attention"), trend: t(lang, "trend.title"), bars: t(lang, "chart.title"), table: t(lang, "live.peerTitle"), events: t(lang, "live.eventsTitle") }}>
    <section key="briefing" className="briefing panel">
      <div className="section-header"><h2><Sparkles size={17} /> {t(lang, briefing.clarification_question ? "live.clarify" : "live.attention")}</h2><span className={`status-pill ${warn ? "warn" : ""}`}>{warn ? <AlertTriangle size={12} /> : <Check size={12} />} {t(lang, `live.status.${result.status}`)}</span></div>
      <p>{briefing.clarification_question ?? briefing.summary}</p>
      {briefing.narrative?.length ? <div className="narrative">{briefing.narrative.map((s, i) => <p key={i}>{s.text}</p>)}</div> : null}
      <div className="briefing-bottom"><span><ShieldCheck size={14} /> {t(lang, "live.accepted", { n: result.validation.accepted })}{result.validation.rejected ? t(lang, "live.rejected", { n: result.validation.rejected }) : ""}</span><button className="text-button" onClick={onTrace}>{t(lang, "live.trace")} <ArrowRight size={14} /></button></div>
    </section>

    {peers.length > 0 && <TrendChart key="trend" result={result} info={metrics} order={colorOrder} lang={lang} onEvidence={onEvidence} />}
    {peers.length > 0 && <PeerChart key="bars" metrics={peers} order={colorOrder} info={metrics} lang={lang} onEvidence={openPeerValue} />}

    {peers.length > 0 && <section key="table" className="panel peer-panel"><div className="section-header"><div><span className="eyebrow">{t(lang, "live.peerEyebrow")}</span><h2>{t(lang, "live.peerTitle")}</h2></div><span className={`status-pill ${peers.every(p => p.aligned) ? "" : "warn"}`}>{peers.every(p => p.aligned) ? <><Check size={12} /> {t(lang, "live.aligned")}</> : <><AlertTriangle size={12} /> {t(lang, "live.notAligned")}</>}</span></div>
      <div className="table-scroll"><table><caption className="sr-only">{t(lang, "live.tableCaption")}</caption>
        <thead><tr><th>{t(lang, "live.company")}</th>{peers.map(p => <th key={p.metric}>{metricLabel(p.metric)}<br /><small>{p.period ? periodLabel(p.period) : t(lang, "live.mixedPeriod")}</small></th>)}</tr></thead>
        <tbody>{peerSymbols.map(symbol => <tr key={symbol}><th><span className="table-bank"><TickerMark symbol={symbol} order={colorOrder} size="sm" />{symbol}</span></th>{peers.map(p => {
          const value = p.values[symbol];
          return <td key={p.metric}>{value === undefined ? <span className="muted" title={t(lang, "live.unavailable")}>—</span> : <button onClick={() => openPeerValue(p.metric, symbol)} aria-label={t(lang, "live.evidenceFor", { m: metricLabel(p.metric), s: symbol })}>{formatPercent(value, lang)}<ArrowUpRight size={11} /></button>}</td>;
        })}</tr>)}</tbody>
      </table></div>
      <div className="panel-footnote">{t(lang, "live.tableNote")}</div>
    </section>}

    {(result.events.length > 0 || result.scope.intent === "discovery") && <section key="events" className="panel events-panel"><div className="section-header"><div><span className="eyebrow">DISCLOSURE RADAR</span><h2>{t(lang, "live.eventsTitle")}</h2></div><span className="small-counter">{t(lang, "live.events", { n: events.length })}</span></div>
      {result.events.length > 0 && <div className="event-filters"><ListFilter size={14} />{[null, ...eventTypes].map(type => <button key={type ?? "all"} className={filter === type ? "selected" : ""} aria-pressed={filter === type} onClick={() => setFilter(type)}>{type ?? t(lang, "live.all")}</button>)}</div>}
      {events.map(ev => { const { day, month } = dayMonth(ev.event_date, lang); return <button className="event-row" key={ev.event_id} onClick={() => openEvent(ev)}><span className="event-date"><strong>{day}</strong><small>{month}</small></span><span className="event-content"><span className="event-labels"><b>{ev.symbol}</b><span>{typeLabel(ev.event_type)}</span></span><strong>{ev.title}</strong><span className="relevance"><span className={ev.relevance_score >= 50 ? "tiny-dot" : "tiny-dot amber"} />{t(lang, "live.score", { n: ev.relevance_score })}{ev.second_hop ? <span className="muted"> · {secondHopLabel(ev.second_hop, lang)}</span> : null}</span></span><ArrowUpRight size={16} /></button>; })}
      {events.length === 0 && <div className="empty-state"><Search size={22} /><h3>{t(lang, "live.noEvents")}</h3><p>{t(lang, "live.noEventsText")}</p>{filter !== null && <button className="text-button" onClick={() => setFilter(null)}>{t(lang, "live.resetFilter")}</button>}</div>}
      {result.scope.timeframe?.label && <div className="panel-footnote"><Clock3 size={12} /> {t(lang, "live.period", { x: result.scope.timeframe.label })}</div>}
    </section>}

    {sections.map(section => <section className="panel findings-panel" key={`finding-${section.heading}`}><div className="section-header"><div><span className="eyebrow">{t(lang, "live.findings")}</span><h2>{section.heading}</h2></div><span className="small-counter">{section.findings.length}</span></div>
      <div className="finding-list">{section.findings.map((f, i) => f.claim_ids.length
        ? <button className="finding" key={i} onClick={() => openClaims(f.claim_ids, f.text)}><span><strong>{f.text}</strong>{f.why && <small>{f.why}</small>}</span><ArrowUpRight size={14} /></button>
        : <div className="finding" key={i}><span><strong>{f.text}</strong>{f.why && <small>{f.why}</small>}</span></div>)}</div>
    </section>)}

    </DraggableWidgetGrid>

    {(briefing.data_gaps.length > 0 || briefing.assumptions.length > 0) && <section className="data-note"><CircleHelp size={17} /><div><strong>{t(lang, "live.limits")}</strong>{briefing.data_gaps.map(g => <p key={g}>{g}</p>)}{briefing.assumptions.map(a => <p key={a}>{t(lang, "live.assumption", { a })}</p>)}</div></section>}
    <p className="boundary-note"><ShieldCheck size={13} /> {briefing.boundary_note}</p>
  </>;
}
