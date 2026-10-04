"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, ArrowUpRight, BarChart3, BookOpen, Check, ChevronRight, CircleHelp, Clock3, FileCheck2, History, Layers3, LayoutDashboard, LoaderCircle, PanelLeftClose, Plus, PowerOff, Search, ShieldCheck, Sparkles, Target, Trash2, TrendingUp, X } from "lucide-react";
import AnimatedWaveFooter, { type StartView } from "@/components/ui/animated-wave-footer";
import { FlipButton } from "@/components/ui/flip-button";
import { DraggableWidgetGrid } from "@/components/ui/draggable-widget-grid";
import LiveResult, { type LiveEvidence, secondHopLabel } from "@/components/live-result";
import TickerMark from "@/components/ticker-mark";
import { type AgentResponse, type AgentStatus, type MetricInfo, type ResultView, formatEvidenceValue, formatPercent, isUrl, periodLabel, viewForIntent } from "@/lib/agent";
import { clearHistory, listHistory, saveHistory } from "@/lib/history";
import { LANG_STORAGE_KEY, type Lang, type MessageKey, isLang, numberLocale, t } from "@/lib/i18n";
import { colorOrder } from "@/lib/palette";
import {
  DEFAULT_WATCHLIST, type HistoryEntry, MAX_WATCHLIST, addToHistory, guessIntent, isHistory, isTickerList, nextStep,
  parseTickers, readStored, watchlistForQuery, writeStored,
} from "@/lib/research";

type View = "workspace" | ResultView;

const STORAGE = { lang: LANG_STORAGE_KEY, watchlist: "idx-insight.watchlist", history: "idx-insight.history", metrics: "idx-insight.metrics" };
const RESULT_VIEWS: ResultView[] = ["discovery", "peers", "company"];
// Answers that are not research results: shown under the research box, not kept in history.
type ReplyKind = "about" | "advice" | "out_of_scope" | "clarify";
const REPLY_KINDS: ReplyKind[] = ["about", "advice", "out_of_scope", "clarify"];
const PROXY_ERRORS = ["not_configured", "invalid_request", "backend_unavailable", "timeout", "rate_limited", "daily_limit", "backend_error"] as const;
const viewIcon = { workspace: LayoutDashboard, discovery: Layers3, peers: BarChart3, company: BookOpen };
const intentIcon = { discovery: Layers3, peers: BarChart3, company: Search };
const titleKey: Record<View, MessageKey> = { workspace: "title.workspace", discovery: "title.discovery", peers: "title.peers", company: "title.company" };
const navKey: Record<View, MessageKey> = { workspace: "nav.workspace", discovery: "nav.discovery", peers: "nav.peers", company: "nav.company" };
const exampleKey: Record<ResultView, MessageKey> = { discovery: "example.discovery", peers: "example.peers", company: "example.company" };
const shortExampleKey: Record<ResultView, MessageKey> = { discovery: "example.discoveryShort", peers: "example.peersShort", company: "example.companyShort" };
function isResultView(value: string | null): value is ResultView {
  return value === "discovery" || value === "peers" || value === "company";
}

function isMetricInfo(value: unknown): value is Record<string, MetricInfo> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}
function longDate(lang: Lang): string {
  return new Date().toLocaleDateString(numberLocale[lang], { day: "numeric", month: "long", year: "numeric" });
}

export default function Home() {
  const [lang, setLang] = useState<Lang>("id");
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [metrics, setMetrics] = useState<Record<string, MetricInfo>>({});
  const [watchlist, setWatchlist] = useState<string[]>(DEFAULT_WATCHLIST);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [view, setView] = useState<View>("workspace");
  const [query, setQuery] = useState("");
  // Research type chosen from the footer or a tab while the question is still empty.
  const [picked, setPicked] = useState<ResultView | null>(null);
  const [reply, setReply] = useState<{ kind: ReplyKind; message: string; suggestions: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [evidence, setEvidence] = useState<LiveEvidence | null>(null);
  const [trace, setTrace] = useState(false);
  const [editWatchlist, setEditWatchlist] = useState(false);
  const [tickerInput, setTickerInput] = useState("");
  const [tickerError, setTickerError] = useState("");
  const [today, setToday] = useState("");
  const loaded = useRef(false);
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const overlay = !!evidence || trace || editWatchlist;
  const offline = status !== null && !status.live;
  // A result view shows the result opened from the history, else the latest result of that type.
  const entry = view === "workspace" ? null
    : history.find(e => e.id === activeId && e.view === view) ?? history.find(e => e.view === view) ?? null;
  const result = entry?.response ?? null;
  const order = colorOrder(watchlist, result ? [...result.scope.companies, ...Object.values(result.peer_comparison).flatMap(p => Object.keys(p.values))] : []);
  const scoped = watchlistForQuery(query, watchlist);
  const detected = guessIntent(query, watchlist);
  const selectedType = detected ?? (query.trim() ? null : picked);
  // The watchlist shows ROE only when the open result has it for a watchlist company.
  const roe = watchlist.some(symbol => result?.peer_comparison.roe?.values[symbol] !== undefined) ? result?.peer_comparison.roe : undefined;
  // One context-aware follow-up for the open result (fills the box, never runs by itself).
  const next = entry && result ? nextStep(entry.view, result.scope.companies, result.events.map(e => e.symbol), watchlist) : null;
  const nextQuery = next && (next.kind === "company"
    ? t(lang, "example.companyFor", { t: next.companies[0] })
    : t(lang, next.kind === "disclosure" ? "next.disclosure" : "next.compare", { list: next.companies.join(", ") }));
  const statusLabel = status === null ? t(lang, "status.connecting") : !status.live ? t(lang, "status.offline") : status.dataSource === "mock" ? t(lang, "status.mock") : t(lang, "status.sectors");

  // Preferences and history live in this browser only. Migrate older localStorage history.
  useEffect(() => {
    let mounted = true;
    queueMicrotask(() => {
      if (!mounted) return;
      const storedLang = readStored(STORAGE.lang, "id", isLang);
      setLang(storedLang);
      setWatchlist(readStored(STORAGE.watchlist, DEFAULT_WATCHLIST, isTickerList));
      const legacy = readStored(STORAGE.history, [], isHistory);
      setHistory(legacy);
      void listHistory().then(async saved => {
        const existing = new Set(saved.map(e => e.id));
        const migrated = legacy.filter(e => !existing.has(e.id));
        const results = await Promise.allSettled(migrated.map(saveHistory));
        if (results.some(r => r.status === "rejected")) throw new Error("Could not migrate all saved research");
        if (!mounted) return;
        setHistory(current => {
          const entries = new Map([...saved, ...current].map(e => [e.id, e]));
          return [...entries.values()].sort((a, b) => b.askedAt.localeCompare(a.askedAt));
        });
        try { window.localStorage.removeItem(STORAGE.history); } catch { /* IndexedDB is primary. */ }
      }).catch(() => { if (mounted) setHistoryError(t(storedLang, "history.storageError")); });
      setMetrics(readStored(STORAGE.metrics, {}, isMetricInfo));
      setToday(longDate(storedLang));
      const params = new URLSearchParams(window.location.search);
      const start = params.get("start");
      const requestedView = params.get("view");
      if (start === "workspace" || isResultView(start)) setPicked(isResultView(start) ? start : null);
      else if (requestedView === "workspace" || isResultView(requestedView)) setView(requestedView);
      loaded.current = true;
    });
    const controller = new AbortController();
    fetch("/api/agent/status", { signal: controller.signal })
      .then(r => r.json() as Promise<AgentStatus>)
      .then(next => { setStatus(next); if (next.live) { setMetrics(next.metrics); writeStored(STORAGE.metrics, next.metrics); } })
      .catch(() => { if (!controller.signal.aborted) setStatus({ live: false }); });
    return () => { mounted = false; controller.abort(); };
  }, []);
  useEffect(() => { if (loaded.current) writeStored(STORAGE.watchlist, watchlist); }, [watchlist]);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(timer);
  }, [busy]);

  function closeOverlays() { setEvidence(null); setTrace(false); setEditWatchlist(false); setTickerError(""); }
  useEffect(() => {
    if (!overlay) return;
    const previous = document.activeElement as HTMLElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") closeOverlays();
      if (e.key === "Tab") {
        const els = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"] button, [role="dialog"] input, [role="dialog"] a'));
        const first = els[0], last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    }
    window.addEventListener("keydown", key);
    return () => { document.body.style.overflow = oldOverflow; window.removeEventListener("keydown", key); previous?.focus(); };
  }, [overlay]);

  function changeLang(next: Lang) { setLang(next); writeStored(STORAGE.lang, next); setToday(longDate(next)); }
  function navigate(next: View) { setView(next); setMenu(false); setError(""); window.scrollTo({ top: 0 }); }
  function ask(text: string) { setQuery(text); setReply(null); navigate("workspace"); requestAnimationFrame(() => queryRef.current?.focus()); }
  /** A new, empty research; with a type, its tab is selected and its example is the placeholder. */
  function startNew(type: StartView) {
    setPicked(type === "workspace" ? null : type);
    ask("");
  }
  function openEntry(e: HistoryEntry) { setActiveId(e.id); navigate(e.view); }

  async function research() {
    const text = query.trim();
    if (text.length < 3) { setError(t(lang, "error.short")); queryRef.current?.focus(); return; }
    setError(""); setReply(null); setBusy(true); setElapsed(0);
    try {
      const response = await fetch("/api/agent/query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        // The backend detects the question's language; the interface then follows it.
        body: JSON.stringify({ query: text, watchlist: scoped }),
      });
      const body = await response.json().catch(() => ({})) as AgentResponse & { error?: unknown };
      if (!response.ok) {
        // The Vercel Firewall answers 429 itself, with { error: { code: "429" } }, before the proxy.
        const code = response.status === 429 && body.error !== "daily_limit" ? "rate_limited"
          : PROXY_ERRORS.find(c => c === body.error) ?? "backend_error";
        setError(t(lang, `error.${code}`));
        return;
      }
      if (isLang(body.language) && body.language !== lang) changeLang(body.language);
      if (body.status === "needs_clarification") {
        const kind = REPLY_KINDS.find(k => k === body.scope.intent) ?? "clarify";
        setReply({ kind, message: body.briefing.clarification_question ?? body.briefing.summary, suggestions: body.briefing.suggestions ?? [] });
        return;
      }
      const next: HistoryEntry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, query: text, language: isLang(body.language) ? body.language : lang,
        askedAt: new Date().toISOString(), view: viewForIntent(body.scope.intent, detected ?? "discovery"), response: body,
      };
      setHistory(prev => addToHistory(prev, next));
      void saveHistory(next).catch(() => {
        setHistoryError(t(lang, "history.saveError"));
      });
      setActiveId(next.id);
      navigate(next.view);
    } catch {
      setError(t(lang, "error.backend_unavailable"));
    } finally {
      setBusy(false);
    }
  }

  function addTickers(event: FormEvent) {
    event.preventDefault();
    const { tickers, invalid } = parseTickers(tickerInput);
    if (invalid.length) { setTickerError(t(lang, "watch.invalid", { list: invalid.join(", ") })); return; }
    const merged = [...new Set([...watchlist, ...tickers])];
    if (merged.length > MAX_WATCHLIST) { setTickerError(t(lang, "watch.full")); return; }
    setWatchlist(merged); setTickerInput(""); setTickerError("");
  }
  function askedAt(iso: string) {
    return new Date(iso).toLocaleString(numberLocale[lang], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }
  async function clearSavedHistory() {
    try {
      await clearHistory();
      try { window.localStorage.removeItem(STORAGE.history); } catch { /* No legacy data to clear. */ }
      setHistory([]); setActiveId(null); setHistoryError(""); navigate("workspace");
    } catch {
      setHistoryError(t(lang, "history.clearError"));
    }
  }

  return <div className="app-shell">
    <aside className={`sidebar ${menu ? "mobile-open" : ""}`}>
      <Link className="brand" href="/"><span className="brand-symbol"><Activity size={22} /></span><span>idx<span className="brand-light">insight</span><small>{t(lang, "brand.tagline")}</small></span></Link>
      <button className="new-research" onClick={() => startNew("workspace")}><Plus size={16} /> {t(lang, "nav.new")} <span>↗</span></button>
      <div className="nav-label">{t(lang, "nav.label")}</div>
      <nav aria-label={t(lang, "nav.main")}>
        {(["workspace", ...RESULT_VIEWS] as View[]).map(id => { const Icon = viewIcon[id]; return <button key={id} className={`nav-item ${view === id ? "active" : ""}`} aria-current={view === id ? "page" : undefined} onClick={() => navigate(id)}><Icon size={17} />{t(lang, navKey[id])}{view === id && <span className="nav-dot" />}</button>; })}
      </nav>
      <div className="history">
        <div className="nav-label history-label"><span><History size={11} /> {t(lang, "history.label")}</span>{history.length > 0 && <button className="icon-button tiny" aria-label={t(lang, "history.clear")} title={t(lang, "history.clear")} onClick={() => void clearSavedHistory()}><Trash2 size={12} /></button>}</div>
        {historyError && <p className="history-empty" role="alert">{historyError}</p>}
        {history.length === 0 ? <p className="history-empty">{t(lang, "history.empty")}</p> : <ul className="history-list">{history.map(e => { const Icon = intentIcon[e.view]; return <li key={e.id}><button className={entry?.id === e.id ? "active" : ""} onClick={() => openEntry(e)} title={e.query}><Icon size={13} /><span><strong>{e.query}</strong><small>{askedAt(e.askedAt)} · {e.language.toUpperCase()}</small></span></button></li>; })}</ul>}
      </div>
      <div className="sidebar-bottom"><Link className="nav-item" href="/#glosarium"><BookOpen size={17} /> {t(lang, "nav.glossary")} <ArrowUpRight size={14} /></Link><Link className="nav-item" href="/#cara-kerja"><CircleHelp size={17} /> {t(lang, "sidebar.guide")} <ArrowUpRight size={14} /></Link><div className="profile"><span className="avatar">R</span><div>{t(lang, "profile.name")}<small>{t(lang, "profile.sub")}</small></div></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-toggle" aria-label={t(lang, "nav.open")} aria-expanded={menu} onClick={() => setMenu(!menu)}><PanelLeftClose size={18} /></button><span>Workspace</span><ChevronRight size={13} /><strong>{t(lang, titleKey[view])}</strong></div>
        <div className="topbar-right"><span className={`prototype-label ${offline ? "offline" : ""}`}>{status === null ? <LoaderCircle size={13} className="spin" /> : offline ? <PowerOff size={13} /> : <ShieldCheck size={13} />} {statusLabel}</span><span className="header-divider" />
          <div className="lang-toggle" role="group" aria-label={t(lang, "lang.label")}>{(["id", "en"] as Lang[]).map(l => <button key={l} aria-pressed={lang === l} className={lang === l ? "selected" : ""} onClick={() => changeLang(l)}>{l.toUpperCase()}</button>)}</div></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow"><span className="tiny-dot" /> {t(lang, "heading.eyebrow")}</div><h1>{view === "workspace" ? <>{t(lang, "heading.line1")}<br className="small-break" /> {t(lang, "heading.line2")}</> : t(lang, titleKey[view])}</h1><p>{t(lang, view === "workspace" ? "heading.sub" : "heading.resultSub")}</p></div>
          {result?.scope.timeframe?.label ? <span className="date-label"><Clock3 size={14} /> {result.scope.timeframe.label}<small>{t(lang, "date.period")}</small></span> : today && <span className="date-label"><Clock3 size={14} /> {today}<small>{t(lang, "date.today")}</small></span>}</div>
        {offline
          ? <div className="offline-banner" role="status"><PowerOff size={15} /><span>{t(lang, "note.offline")}</span></div>
          : <div className="demo-note"><ShieldCheck size={14} /><span>{result
            ? t(lang, "note.result", { source: t(lang, result.data_source === "mock" ? "note.sourceMock" : "note.sourceSectors"), llm: result.llm_provider !== "none" ? t(lang, "note.withLlm") : "" })
            : status === null ? t(lang, "note.connecting") : status.live && status.dataSource === "mock" ? t(lang, "note.mock") : t(lang, "note.live")}</span></div>}
        {view === "workspace" ? <section className="research-box" aria-labelledby="research-title">
          <div className="research-box-top"><span className="label-with-icon" id="research-title"><Sparkles size={17} /> {t(lang, "box.title")}</span><span className="muted mini">{t(lang, "box.tag")}</span></div>
          <div className="intent-row"><div className="intent-tabs" role="group" aria-label={t(lang, "box.types")}>{RESULT_VIEWS.map(id => { const Icon = intentIcon[id]; return <button key={id} className={selectedType === id ? "selected" : ""} aria-pressed={selectedType === id} onClick={() => { setPicked(id); ask(t(lang, exampleKey[id])); }}><Icon size={14} />{t(lang, `intent.${id}`)}</button>; })}</div>
            <span className="intent-hint">{detected ? <><Check size={11} /> {t(lang, "box.detected")}</> : t(lang, "box.typeHint")}</span></div>
          <label className="sr-only" htmlFor="query">{t(lang, "box.label")}</label><textarea id="query" ref={queryRef} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !busy && !offline) void research(); }} placeholder={t(lang, exampleKey[picked ?? "discovery"])} maxLength={500} disabled={offline} />
          <div className="query-footer"><div className="query-context">{(!query.trim() || detected) && <span><Target size={13} /> {query.trim() && !scoped.length ? t(lang, "box.scopeQuery") : t(lang, "box.scopeWatchlist", { n: watchlist.length })}</span>}<span><Clock3 size={13} /> {t(lang, "box.period")}</span></div>
            <FlipButton className="primary-button" iconPosition="start" onClick={() => void research()} disabled={busy || offline || status === null} label={busy ? t(lang, "box.busy", { s: elapsed }) : offline ? t(lang, "box.offline") : t(lang, "box.run")} icon={busy ? <LoaderCircle size={15} className="spin" /> : offline ? <PowerOff size={15} /> : <Sparkles size={15} />} /></div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </section> : entry && <section className="result-query"><span className="query-orb"><Sparkles size={19} /></span><div><span className="eyebrow">{t(lang, "result.question")}</span><p>{entry.query}</p><div className="muted mini">{result?.scope.companies.join(" · ") || "—"} <span className="dot-separator">/</span> {t(lang, "result.asked", { time: askedAt(entry.askedAt) })}</div></div><div className="result-actions"><FlipButton className="secondary-button" iconPosition="start" onClick={() => ask(entry.query)} label={t(lang, "result.edit")} icon={<ArrowLeft size={14} />} />{next && nextQuery && <FlipButton className="secondary-button" iconPosition="start" onClick={() => ask(nextQuery)} label={t(lang, `result.next.${next.kind}`, { t: next.companies[0] })} icon={next.kind === "disclosure" ? <Layers3 size={14} /> : <BarChart3 size={14} />} />}</div></section>}
        <div className="content-grid"><div className="primary-column">
          {view === "workspace" && <>
            {reply && <section className={`panel scope-reply ${reply.kind}`} role="status" aria-live="polite"><div className="scope-reply-head"><span className="eyebrow">{reply.kind === "advice" ? <ShieldCheck size={12} /> : <Sparkles size={12} />} {t(lang, `reply.label.${reply.kind}`)}</span><button className="icon-button tiny" aria-label={t(lang, "drawer.close")} onClick={() => setReply(null)}><X size={13} /></button></div><p>{reply.message}</p>
              <div className="suggestions"><span className="muted mini">{t(lang, "reply.try")}</span>{[...new Set([
                // The agent's own suggestion first, then fixed examples.
                ...reply.suggestions,
                ...(reply.kind === "advice"
                  ? [t(lang, "suggest.npl", { list: (watchlist.length >= 2 ? watchlist : DEFAULT_WATCHLIST).slice(0, 4).join(", ") }), t(lang, "suggest.roe", { list: (watchlist.length >= 2 ? watchlist : DEFAULT_WATCHLIST).slice(0, 4).join(", ") })]
                  : RESULT_VIEWS.map(id => t(lang, exampleKey[id]))),
              ])].slice(0, 3).map((text, i) => <button key={text} className={i < reply.suggestions.length ? "agent-suggestion" : undefined} onClick={() => ask(text)}>{i < reply.suggestions.length && <Sparkles size={12} />}{text} <ArrowUpRight size={13} /></button>)}</div></section>}
            {!reply && <div className="suggestions"><span className="muted mini">{t(lang, "suggest.label")}</span>{RESULT_VIEWS.map(id => <button key={id} onClick={() => ask(t(lang, exampleKey[id]))}>{t(lang, shortExampleKey[id])} <ArrowUpRight size={13} /></button>)}</div>}
            {history.length > 0 && <section className="panel recent-panel"><div className="section-header"><div><span className="eyebrow"><History size={11} /> {t(lang, "history.saved").toUpperCase()}</span><h2>{t(lang, "recent.title")}</h2></div><span className="small-counter">{history.length}</span></div>
              <ul className="recent-list">{history.slice(0, 6).map(e => { const Icon = intentIcon[e.view]; return <li key={e.id}><button onClick={() => openEntry(e)}><span className="recent-icon"><Icon size={14} /></span><span className="recent-text"><strong>{e.query}</strong><small>{t(lang, titleKey[e.view])} · {askedAt(e.askedAt)} · {t(lang, `live.status.${e.response.status}`)}</small></span><ArrowUpRight size={14} /></button></li>; })}</ul></section>}
          </>}
          {view !== "workspace" && (result
            ? <LiveResult key={entry?.id} layoutKey={view} result={result} metrics={metrics} colorOrder={order} onEvidence={setEvidence} onTrace={() => setTrace(true)} />
            : <section className="panel"><div className="empty-state"><Search size={22} /><h3>{t(lang, "empty.title", { type: t(lang, titleKey[view]).toLowerCase() })}</h3><p>{t(lang, "empty.text")}</p><button className="secondary-button" onClick={() => ask(t(lang, exampleKey[view]))}>{t(lang, "empty.example")} <ArrowRight size={14} /></button></div></section>)}
        </div>
        <aside className="context-column"><DraggableWidgetGrid storageKey={`idx-insight.widgets.${view}.context`} lang={lang} axis="xy" className="widget-context" labels={{ watchlist: t(lang, "watch.title"), agent: t(lang, "agent.title1"), source: t(lang, "source.title") }}><section key="watchlist" className="panel watchlist-panel"><div className="section-header"><h2>{t(lang, "watch.title")} <span className="count">{watchlist.length}</span></h2><button className="icon-button" aria-label={t(lang, "watch.manage")} onClick={() => setEditWatchlist(true)}><Plus size={17} /></button></div>
          <div className="watchlist-label"><span>{t(lang, "watch.company")}</span>{roe && <span>{t(lang, "watch.roe", { period: periodLabel(roe.period) })}</span>}</div>
          {watchlist.map(symbol => <div className="watchlist-row" key={symbol}><button className="watchlist-identity" onClick={() => ask(t(lang, "example.companyFor", { t: symbol }))} aria-label={t(lang, "watch.prepare", { t: symbol })}><TickerMark symbol={symbol} order={order} /><span><strong>{symbol}</strong><small>{symbol}.JK</small></span></button>{roe && <span className="watchlist-value">{roe.values[symbol] === undefined ? "—" : formatPercent(roe.values[symbol], lang)}</span>}</div>)}
          {!watchlist.length && <p className="empty-watchlist">{t(lang, "watch.empty")}</p>}
          <button className="add-watchlist" onClick={() => setEditWatchlist(true)}><Plus size={14} /> {t(lang, "watch.manage")}</button><p className="watchlist-caption">{t(lang, roe ? "watch.captionValue" : "watch.caption")}</p></section>
          <section key="agent" className="agent-card"><div className="agent-icon"><Sparkles size={21} /></div><span className="eyebrow">{t(lang, "agent.eyebrow")}</span><h2>{t(lang, "agent.title1")}<br />{t(lang, "agent.title2")}</h2><p>{t(lang, "agent.text")}</p><div className="agent-steps"><span><Search size={13} /> {t(lang, "agent.step1")}</span><ChevronRight size={12} /><span><TrendingUp size={13} /> {t(lang, "agent.step2")}</span><ChevronRight size={12} /><span><FileCheck2 size={13} /> {t(lang, "agent.step3")}</span></div>{result
            ? <button className="text-button" onClick={() => setTrace(true)}>{t(lang, "agent.explore")} <ArrowRight size={14} /></button>
            : <Link className="text-button" href="/#journey">{t(lang, "agent.explore")} <ArrowRight size={14} /></Link>}</section>
          <section key="source" className="source-card"><a href="https://sectors.app/" target="_blank" rel="noopener noreferrer"><span className="sectors-logo">S</span><strong>{t(lang, "source.title")}</strong><ArrowUpRight size={13} /><span className="sr-only">{t(lang, "newTab")}</span></a><p>{t(lang, offline ? "source.offline" : "source.live")}</p><span><ShieldCheck size={13} /> {t(lang, "source.always")}</span></section>
        </DraggableWidgetGrid></aside></div>
      </main>
      <AnimatedWaveFooter activeView={view} onStart={startNew} lang={lang} statusLabel={statusLabel} />
    </div>
    {overlay && <div className="overlay"><section role="dialog" aria-modal="true" aria-labelledby="drawer-title" className={`drawer ${editWatchlist ? "small-dialog" : ""}`}><div className="drawer-top"><span className="eyebrow">{t(lang, evidence ? "drawer.evidence" : trace ? "drawer.trace" : "drawer.watchlist")}</span><button ref={closeRef} className="icon-button" aria-label={t(lang, "drawer.close")} onClick={closeOverlays}><X size={19} /></button></div>
      <h2 id="drawer-title">{evidence?.title || t(lang, trace ? "trace.title" : "watch.dialogTitle")}</h2>
      {evidence && <><div className="drawer-badge"><FileCheck2 size={15} /> {evidence.ticker}{evidence.period ? ` · ${evidence.period}` : ""}</div>
        {evidence.reasons?.length ? <><p className="drawer-description">{t(lang, "evidence.reasons")}</p><ul className="reason-list">{evidence.reasons.map(r => <li key={r}>{r}</li>)}</ul></> : null}
        {evidence.secondHop && <p className="drawer-description">{t(lang, "evidence.secondHop", { x: secondHopLabel(evidence.secondHop, lang) ?? "" })}</p>}
        {evidence.items.length === 0 && <p className="drawer-description">{t(lang, "evidence.none")}</p>}
        {evidence.items.map(item => <dl className="evidence-list" key={item.evidence_id}>
          <div><dt>{t(lang, "evidence.value")}</dt><dd>{formatEvidenceValue(item, lang)}</dd></div>
          <div><dt>{t(lang, "evidence.company")}</dt><dd>{item.symbol ? `${item.symbol}.JK` : "—"}</dd></div>
          <div><dt>{t(lang, "evidence.period")}</dt><dd>{periodLabel(item.period)}</dd></div>
          <div><dt>{t(lang, "evidence.field")}</dt><dd><code>{item.field}</code></dd></div>
          <div><dt>{t(lang, "evidence.endpoint")}</dt><dd>{item.tool}</dd></div>
          <div><dt>{t(lang, "evidence.source")}</dt><dd>{isUrl(item.source_ref) ? <a className="source-link" href={item.source_ref} target="_blank" rel="noopener noreferrer">{t(lang, "evidence.openDoc")} <ArrowUpRight size={11} /><span className="sr-only">{t(lang, "newTab")}</span></a> : <code>{item.source_ref}</code>}</dd></div>
          <div><dt>{t(lang, "evidence.id")}</dt><dd>{item.evidence_id}</dd></div>
          {item.note && <div><dt>{t(lang, "evidence.note")}</dt><dd>{item.note}</dd></div>}
        </dl>)}
        {evidence.sourceRef && isUrl(evidence.sourceRef) && !evidence.items.some(i => i.source_ref === evidence.sourceRef) && <a className="secondary-button full-width" href={evidence.sourceRef} target="_blank" rel="noopener noreferrer">{t(lang, "evidence.openSource")} <ArrowUpRight size={14} /></a>}
      </>}
      {trace && result && <><p className="drawer-description">{t(lang, "trace.live", { n: result.tool_calls.length, llm: result.llm_provider !== "none" ? t(lang, "trace.llm", { p: result.llm_provider }) : t(lang, "trace.noLlm") })}</p><ol className="trace-list">{result.trace.map((step, i) => <li key={`${step.stage}-${i}`}><span className={step.status === "ok" ? "" : "trace-warn"}>{String(i + 1).padStart(2, "0")}</span><div><h3>{step.stage}</h3><p>{step.detail || step.status}</p></div></li>)}</ol></>}
      {editWatchlist && <><p className="drawer-description">{t(lang, "watch.dialogText")}</p>
        <form className="ticker-form" onSubmit={addTickers}><label className="sr-only" htmlFor="ticker-input">{t(lang, "watch.input")}</label><input id="ticker-input" value={tickerInput} onChange={e => { setTickerInput(e.target.value); setTickerError(""); }} placeholder={t(lang, "watch.placeholder")} autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={120} aria-invalid={!!tickerError} aria-describedby={tickerError ? "ticker-error" : undefined} /><button type="submit" className="secondary-button" disabled={!tickerInput.trim()}><Plus size={14} /> {t(lang, "watch.add")}</button></form>
        {tickerError && <p className="form-error" id="ticker-error" role="alert">{tickerError}</p>}
        <ul className="ticker-list">{watchlist.map(symbol => <li key={symbol}><TickerMark symbol={symbol} order={order} /><strong>{symbol}</strong><button className="icon-button" aria-label={t(lang, "watch.remove", { t: symbol })} onClick={() => setWatchlist(prev => prev.filter(s => s !== symbol))}><X size={15} /></button></li>)}</ul>
        <p className="watch-note">{t(lang, "watch.note")}</p>
        <p className="logo-attribution">Logo: <a href="https://www.bca.co.id/id/tentang-bca/media-riset/pressroom/brand-assets" target="_blank" rel="noopener noreferrer">BCA</a> · <a href="https://commons.wikimedia.org/wiki/File:BRI_2025.svg" target="_blank" rel="noopener noreferrer">BRI</a> · <a href="https://www.bankmandiri.co.id/brandguideline" target="_blank" rel="noopener noreferrer">Mandiri</a> · <a href="https://commons.wikimedia.org/wiki/File:Bank_Negara_Indonesia_logo_(2004).svg" target="_blank" rel="noopener noreferrer">BNI</a>.</p>
        <FlipButton className="primary-button full-width" onClick={closeOverlays} label={t(lang, "watch.done", { n: watchlist.length })} icon={<Check size={15} />} /></>}
    </section></div>}
  </div>;
}
