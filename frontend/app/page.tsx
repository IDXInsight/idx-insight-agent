"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, ArrowUpRight, BarChart3, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Clock3, FileCheck2, FileText, Fingerprint, FlaskConical, Layers3, LayoutDashboard, ListFilter, LoaderCircle, PanelLeftClose, Plus, Search, ShieldCheck, Sparkles, Target, TrendingUp, WalletCards, X } from "lucide-react";
import AnimatedWaveFooter from "@/components/ui/animated-wave-footer";
import ChartLineDefault, { bankColors, type Bank, type Metric } from "@/components/ui/v-chart-4";

type View = "workspace" | "discovery" | "peers" | "company";
type Evidence = { title: string; ticker: string; value?: string; period?: string; field?: string; detail: string };
const banks: Bank[] = ["BBCA", "BBRI", "BMRI", "BBNI"];
const names: Record<Bank, string> = { BBCA: "Bank Central Asia", BBRI: "Bank Rakyat Indonesia", BMRI: "Bank Mandiri", BBNI: "Bank Negara Indonesia" };
const figures = { BBCA: [24.2, 3.9, 31.2, 12.8], BBRI: [19.1, 3.1, 42.6, 8.2], BMRI: [22.8, 3.5, 35.4, 10.6], BBNI: [14.7, 2.2, 46.8, 6.1] };
const events = [
  { ticker: "BBRI" as Bank, day: "29", month: "SEP", type: "Kepemilikan", title: "Perubahan kepemilikan oleh direksi", text: "Transaksi insider pada bank dalam watchlist. Tinjau skala perubahan dan konteks kinerjanya.", score: "Relevansi tinggi", icon: Fingerprint },
  { ticker: "BBCA" as Bank, day: "30", month: "SEP", type: "Dividen", title: "Jadwal pembayaran dividen interim", text: "Tanggal pembayaran berada dalam periode pantauan. Konteks profitabilitas tersedia untuk ditelusuri.", score: "Relevansi tinggi", icon: WalletCards },
  { ticker: "BMRI" as Bank, day: "02", month: "OKT", type: "RUPS", title: "Agenda rapat umum pemegang saham", text: "Agenda tata kelola dalam periode pilihan. Buka rincian untuk melihat informasi yang perlu diperiksa.", score: "Relevansi sedang", icon: FileText },
];
const prompts: Record<Exclude<View,"workspace">, string> = {
  discovery: "Disclosure apa yang perlu saya pantau minggu depan untuk bank dalam watchlist?",
  peers: "Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitabilitas dan efisiensi.",
  company: "Bagaimana perkembangan kinerja BBCA dan kejadian yang perlu diperhatikan?",
};
function format(n: number) { return `${n.toLocaleString("id-ID", { minimumFractionDigits: 1 })}%`; }
function BankMark({ bank }: { bank: Bank }) { return <span className={`bank-mark ${bank.toLowerCase()}`}>{bank.slice(0, 2)}</span>; }

export default function Home() {
  const [view, setView] = useState<View>("workspace");
  const [intent, setIntent] = useState<Exclude<View,"workspace">>("discovery");
  const [watchlist, setWatchlist] = useState<Bank[]>(banks);
  const [query, setQuery] = useState("");
  const [period, setPeriod] = useState("Minggu depan");
  const [metric, setMetric] = useState<Metric>("roe");
  const [visibleBanks, setVisibleBanks] = useState<Bank[]>(banks);
  const [filter, setFilter] = useState("Semua");
  const [drawer, setDrawer] = useState<Evidence | null>(null);
  const [trace, setTrace] = useState(false);
  const [help, setHelp] = useState(false);
  const [addBank, setAddBank] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Bank>("BBCA");
  const queryRef = useRef<HTMLTextAreaElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const overlay = !!drawer || trace || help || addBank;

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  useEffect(() => {
    if (!overlay) return;
    const previous = document.activeElement as HTMLElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") { setDrawer(null); setTrace(false); setHelp(false); setAddBank(false); }
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

  function navigate(next: View) { setView(next); setMenu(false); setError(""); if (next !== "workspace") { setIntent(next); setQuery(prompts[next]); } }
  function research() {
    if (query.trim().length < 3) { setError("Tulis pertanyaan riset atau pilih salah satu contoh di bawah."); queryRef.current?.focus(); return; }
    if (!watchlist.length) { setError("Tambahkan setidaknya satu bank ke watchlist."); return; }
    if (intent === "peers" && watchlist.length < 2) { setError("Pilih setidaknya dua bank untuk perbandingan."); return; }
    setError(""); setBusy(true);
    timer.current = setTimeout(() => { setView(intent); setBusy(false); setVisibleBanks(watchlist); }, 700);
  }
  function evidence(bank: Bank, index: number) {
    const labels = ["Return on equity", "Return on assets", "Cost-to-income", "Pertumbuhan laba YoY"];
    setDrawer({ title: labels[index], ticker: bank, value: format(figures[bank][index]), period: index === 3 ? "Q2 2026 vs Q2 2025" : "Tahun buku 2025", field: ["profitability.roe", "profitability.roa", "profitability.cost_to_income_ratio", "earnings_growth_yoy"][index], detail: "Nilai sintetis untuk meninjau desain. Saat backend dihubungkan, panel ini menampilkan evidence dan sumber yang benar-benar dikembalikan Sectors." });
  }
  function toggleSeries(bank: Bank) { setVisibleBanks(prev => prev.includes(bank) ? prev.filter(b => b !== bank) : [...prev, bank]); }
  const shownEvents = events.filter(e => watchlist.includes(e.ticker) && (filter === "Semua" || e.type === filter));
  const titles: Record<View, string> = { workspace: "Ruang riset", discovery: "Briefing disclosure", peers: "Perbandingan bank", company: "Konteks emiten" };

  return <div className="app-shell">
    <aside className={`sidebar ${menu ? "mobile-open" : ""}`}>
      <button className="brand" onClick={() => navigate("workspace")}><span className="brand-symbol"><Activity size={22} /></span><span>idx<span className="brand-light">insight</span><small>RESEARCH WORKSPACE</small></span></button>
      <button className="new-research" onClick={() => { navigate("workspace"); setQuery(""); queryRef.current?.focus(); }}><Plus size={16} /> Riset baru <span>↗</span></button>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Navigasi utama">
        {([{ id: "workspace", label: "Ringkasan", icon: LayoutDashboard }, { id: "discovery", label: "Disclosure", icon: Layers3 }, { id: "peers", label: "Peer lens", icon: BarChart3 }, { id: "company", label: "Konteks emiten", icon: BookOpen }] as const).map(item => <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}><item.icon size={17} />{item.label}{view === item.id && <span className="nav-dot" />}</button>)}
      </nav>
      <div className="sidebar-note"><span className="label-with-icon"><ShieldCheck size={16} /> Dibangun di atas bukti</span><p>Setiap temuan punya sumber. Setiap keterbatasan dijelaskan.</p></div>
      <div className="sidebar-bottom"><button className="nav-item" onClick={() => setHelp(true)}><CircleHelp size={17} /> Panduan riset <ArrowUpRight size={14} /></button><div className="profile"><span className="avatar">RI</span><div>Ruang riset pribadi<small>IDX · Sektor perbankan</small></div><ChevronDown size={14} /></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-toggle" aria-label="Buka navigasi" onClick={() => setMenu(!menu)}><PanelLeftClose size={18} /></button><span>Workspace</span><ChevronRight size={13} /><strong>{titles[view]}</strong></div><div className="topbar-right"><span className="prototype-label"><FlaskConical size={13} /> Prototipe · data ilustrasi</span><span className="header-divider" /><span className="language">ID</span></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow"><span className="tiny-dot" /> IDX BANKING INTELLIGENCE</div><h1>{view === "workspace" ? <>Temukan konteks.<br className="small-break" /> Pahami yang penting.</> : titles[view]}</h1><p>{view === "workspace" ? "Dari disclosure hingga kinerja keuangan. Riset yang bisa kamu telusuri." : "Temuan, konteks, dan bukti dalam satu ruang riset."}</p></div><span className="date-label"><Clock3 size={14} /> 28 September 2026<small>Tanggal acuan desain</small></span></div>
        <div className="demo-note"><FlaskConical size={14} /><span>Mode pratinjau desain. Semua angka dan kejadian bersifat ilustratif, bukan data pasar.</span></div>
        {view === "workspace" ? <section className="research-box" aria-labelledby="research-title">
          <div className="research-box-top"><span className="label-with-icon" id="research-title"><Sparkles size={17} /> Mulai dari sebuah pertanyaan</span><span className="muted mini">AGENT WORKSPACE</span></div>
          <div className="intent-tabs" role="group" aria-label="Jenis riset">{([{ id: "discovery", title: "Pantau disclosure", icon: Layers3 }, { id: "peers", title: "Bandingkan bank", icon: BarChart3 }, { id: "company", title: "Analisis emiten", icon: Search }] as const).map(t => <button key={t.id} className={intent === t.id ? "selected" : ""} aria-pressed={intent === t.id} onClick={() => { setIntent(t.id); setQuery(""); setError(""); }}><t.icon size={14} />{t.title}</button>)}</div>
          <label className="sr-only" htmlFor="query">Pertanyaan riset</label><textarea id="query" ref={queryRef} value={query} onChange={e => setQuery(e.target.value)} placeholder={prompts[intent]} maxLength={500} />
          <div className="query-footer"><div className="query-context"><span><Target size={13} /> {watchlist.length} bank dipilih</span><label className="period-select"><Clock3 size={13} /><select aria-label="Periode riset" value={period} onChange={e => setPeriod(e.target.value)}><option>Minggu depan</option><option>Minggu ini</option><option>Bulan ini</option></select></label></div><button className="primary-button" onClick={research} disabled={busy}>{busy ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}{busy ? "Menyiapkan contoh…" : "Lihat contoh riset"}<ArrowRight size={16} /></button></div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </section> : <section className="result-query"><span className="query-orb"><Sparkles size={19} /></span><div><span className="eyebrow">PERTANYAAN RISET</span><p>{query || prompts[intent]}</p><div className="muted mini">{watchlist.join(" · ")} <span className="dot-separator">/</span> {view === "discovery" ? period : "Periode sesuai metrik"}</div></div><button className="secondary-button" onClick={() => setView("workspace")}><ArrowLeft size={14} /> Ubah</button></section>}
        <div className="content-grid"><div className="primary-column">
          {view === "workspace" && <div className="suggestions"><span className="muted mini">COBA PERTANYAAN</span><button onClick={() => { setIntent("discovery"); setQuery(prompts.discovery); queryRef.current?.focus(); }}>Apa agenda bank minggu depan? <ArrowUpRight size={13} /></button><button onClick={() => { setIntent("peers"); setQuery(prompts.peers); queryRef.current?.focus(); }}>Bandingkan profitabilitas bank <ArrowUpRight size={13} /></button></div>}
          {view === "discovery" && <section className="briefing panel"><div className="section-header"><h2><Sparkles size={17} /> Yang perlu diperhatikan</h2><span className="status-pill">Contoh briefing</span></div><p>Ada <strong>{shownEvents.length} kejadian</strong> dalam watchlist yang ditampilkan pada contoh ini. Perubahan kepemilikan, dividen, dan agenda tata kelola memiliki alasan relevansi yang berbeda.</p><div className="briefing-bottom"><span><ShieldCheck size={14} /> Bukti ditampilkan per temuan</span><button className="text-button" onClick={() => setTrace(true)}>Lihat proses riset <ArrowRight size={14} /></button></div></section>}
          {view === "company" && <section className="company-banner panel"><div className="company-identity"><BankMark bank={selectedCompany} /><div><h2>{names[selectedCompany]}</h2><span className="muted">{selectedCompany}.JK · Perbankan</span></div></div><select className="metric-select" aria-label="Pilih emiten" value={selectedCompany} onChange={e => setSelectedCompany(e.target.value as Bank)}>{banks.map(b => <option key={b}>{b}</option>)}</select></section>}
          {view !== "discovery" && <section className="panel chart-panel"><div className="section-header"><div><span className="eyebrow">{view === "company" ? "PERKEMBANGAN EMITEN" : "PEER LENS"}</span><h2>{metric === "roe" ? "Profitabilitas dalam perspektif" : "Perkembangan pertumbuhan laba"}</h2></div><label className="sr-only" htmlFor="metric">Metrik grafik</label><select id="metric" className="metric-select" value={metric} onChange={e => setMetric(e.target.value as Metric)}><option value="roe">Return on equity</option><option value="growth">Pertumbuhan laba</option></select></div>
            <div className="chart-meta"><span>{metric === "roe" ? "ROE · tahunan · %" : "Pertumbuhan laba YoY · kuartalan · %"}</span><span>{metric === "roe" ? "2021 — 2025" : "Q2 2025 — Q2 2026"}</span></div>
            <ChartLineDefault metric={metric} banks={view === "company" ? [selectedCompany] : visibleBanks.filter(b => watchlist.includes(b))} />
            <div className="chart-footer"><div className="chart-legend">{(view === "company" ? [selectedCompany] : watchlist).map(bank => <button key={bank} aria-pressed={view === "company" || visibleBanks.includes(bank)} onClick={() => { if (view !== "company") toggleSeries(bank); }} style={{ opacity: view === "company" || visibleBanks.includes(bank) ? 1 : .4 }}><span style={{ background: bankColors[bank] }} />{bank}</button>)}</div><span className="muted mini">Data ilustrasi</span></div>
            {view === "workspace" && <button className="chart-link" onClick={() => navigate("peers")}>Buka perbandingan lengkap <ArrowUpRight size={14} /></button>}
          </section>}
          {view === "peers" && <section className="panel peer-panel"><div className="section-header"><div><span className="eyebrow">PERBANDINGAN METRIK</span><h2>Satu periode, konteks yang sebanding</h2></div><span className="status-pill"><Check size={12} /> Periode sejajar</span></div><div className="table-scroll"><table><caption className="sr-only">Perbandingan ilustratif. Klik angka untuk detail. Rasio tahunan 2025; pertumbuhan laba Q2 2026.</caption><thead><tr><th>Bank</th><th>ROE<br /><small>2025</small></th><th>ROA<br /><small>2025</small></th><th>Cost/income<br /><small>2025</small></th><th>Laba YoY<br /><small>Q2 2026</small></th></tr></thead><tbody>{watchlist.map(bank => <tr key={bank}><th><span className="table-bank"><BankMark bank={bank} />{bank}</span></th>{figures[bank].map((n, i) => <td key={i}><button onClick={() => evidence(bank, i)} aria-label={`Lihat bukti ${["ROE", "ROA", "Cost-to-income", "laba YoY"][i]} ${bank}`}>{format(n)}<ArrowUpRight size={11} /></button></td>)}</tr>)}</tbody></table></div><div className="panel-footnote">Klik angka untuk menelusuri bukti. Nilai lebih tinggi tidak selalu berarti lebih baik.</div></section>}
          {view === "company" && <div className="metric-cards">{["ROE · 2025", "ROA · 2025", "Laba YoY · Q2 2026"].map((title, i) => <button className="panel metric-card" key={title} onClick={() => evidence(selectedCompany, i === 2 ? 3 : i)}><span className="muted mini">{title}</span><strong>{format(figures[selectedCompany][i === 2 ? 3 : i])}</strong><span>Lihat bukti <ArrowUpRight size={12} /></span></button>)}</div>}
          {view !== "peers" && <section className="panel events-panel"><div className="section-header"><div><span className="eyebrow">DISCLOSURE RADAR</span><h2>{view === "company" ? "Kejadian terkait" : "Dalam pantauan minggu ini"}</h2></div><span className="small-counter">{(view === "company" ? shownEvents.filter(e => e.ticker === selectedCompany) : shownEvents).length} kejadian</span></div><div className="event-filters"><ListFilter size={14} />{["Semua", "Kepemilikan", "Dividen", "RUPS"].map(t => <button key={t} className={filter === t ? "selected" : ""} aria-pressed={filter === t} onClick={() => setFilter(t)}>{t}</button>)}</div>
            {(view === "company" ? shownEvents.filter(e => e.ticker === selectedCompany) : shownEvents).map(ev => <button className="event-row" key={ev.ticker} onClick={() => setDrawer({ title: ev.title, ticker: ev.ticker, period: `${ev.day} ${ev.month} 2026`, detail: ev.text })}><span className="event-date"><strong>{ev.day}</strong><small>{ev.month}</small></span><span className="event-content"><span className="event-labels"><b>{ev.ticker}</b><span>{ev.type}</span></span><strong>{ev.title}</strong><span className="relevance"><span className={ev.score.includes("sedang") ? "tiny-dot amber" : "tiny-dot"} />{ev.score} <span className="muted">· Contoh</span></span></span><ArrowUpRight size={16} /></button>)}
            {(view === "company" ? shownEvents.filter(e => e.ticker === selectedCompany) : shownEvents).length === 0 && <div className="empty-state"><Search size={22} /><h3>Tidak ada contoh kejadian</h3><p>Coba filter lain atau tambahkan bank ke watchlist. Hasil kosong tidak berarti tidak ada dampak.</p><button className="text-button" onClick={() => setFilter("Semua")}>Reset filter</button></div>}
            <div className="panel-footnote"><Clock3 size={12} /> Contoh periode 28 Sep — 4 Okt 2026 · Bukan kalender pasar aktual</div>
          </section>}
          {view !== "workspace" && <section className="data-note"><CircleHelp size={17} /><div><strong>Ketahui batas datanya</strong><p>Grafik, tanggal, dan angka di prototipe ini adalah ilustrasi. Jadwal laporan mendatang dan data yang tidak tersedia akan ditandai sebagai keterbatasan, bukan diperkirakan.</p></div></section>}
        </div>
        <aside className="context-column"><section className="panel watchlist-panel"><div className="section-header"><h2>Watchlist kamu <span className="count">{watchlist.length}</span></h2><button className="icon-button" aria-label="Kelola watchlist" onClick={() => setAddBank(true)}><Plus size={17} /></button></div><div className="watchlist-label"><span>EMITEN</span><span>ROE 2025</span></div>{watchlist.map(bank => <div className="watchlist-row" key={bank}><button className="watchlist-identity" onClick={() => { setSelectedCompany(bank); navigate("company"); }}><BankMark bank={bank} /><span><strong>{bank}</strong><small>{names[bank]}</small></span></button><button className="watchlist-value" onClick={() => evidence(bank, 0)}>{format(figures[bank][0])}<ArrowUpRight size={11} /></button></div>)}{!watchlist.length && <p className="empty-watchlist">Tambahkan bank untuk memulai riset.</p>}<button className="add-watchlist" onClick={() => setAddBank(true)}><Plus size={14} /> Kelola watchlist</button><p className="watchlist-caption">Angka ilustrasi · bukan harga saham</p></section>
          <section className="agent-card"><div className="agent-icon"><Sparkles size={21} /></div><span className="eyebrow">RISET DENGAN ARAH</span><h2>Dari kejadian,<br />ke pemahaman.</h2><p>Agent memilih konteks yang perlu diteliti, lalu menghubungkan setiap temuan dengan buktinya.</p><div className="agent-steps"><span><Search size={13} /> Temukan</span><ChevronRight size={12} /><span><TrendingUp size={13} /> Pahami</span><ChevronRight size={12} /><span><FileCheck2 size={13} /> Validasi</span></div><button className="text-button" onClick={() => setTrace(true)}>Jelajahi proses riset <ArrowRight size={14} /></button></section>
          <section className="source-card"><div><span className="sectors-logo">S</span><strong>Powered by Sectors</strong><ArrowUpRight size={13} /></div><p>Sumber data untuk implementasi akhir. Prototipe ini tidak melakukan panggilan API.</p><span><ShieldCheck size={13} /> Sumber & periode selalu terlihat</span></section>
        </aside></div>
      </main>
      <AnimatedWaveFooter
        activeView={view}
        onNavigate={navigate}
        onNewResearch={() => { navigate("workspace"); setQuery(""); queryRef.current?.focus(); }}
        onOpenGuide={() => setHelp(true)}
        onOpenTrace={() => setTrace(true)}
      />
    </div>
    {overlay && <div className="overlay"><section role="dialog" aria-modal="true" aria-labelledby="drawer-title" className={`drawer ${addBank || help ? "small-dialog" : ""}`}><div className="drawer-top"><span className="eyebrow">{drawer ? "EVIDENCE EXPLORER" : trace ? "AGENT TRACE" : addBank ? "WATCHLIST" : "PANDUAN"}</span><button ref={closeRef} className="icon-button" aria-label="Tutup panel" onClick={() => { setDrawer(null); setTrace(false); setHelp(false); setAddBank(false); }}><X size={19} /></button></div>
      <h2 id="drawer-title">{drawer?.title || (trace ? "Setiap langkah punya alasan." : addBank ? "Pilih bank yang kamu pantau" : "Riset dimulai dari rasa ingin tahu.")}</h2>
      {drawer && <><div className="drawer-badge"><FileCheck2 size={15} /> {drawer.ticker} · Bukti ilustratif</div>{drawer.value && <div className="evidence-value">{drawer.value}<small>{drawer.period}</small></div>}<p className="drawer-description">{drawer.detail}</p><dl className="evidence-list"><div><dt>Emiten</dt><dd>{drawer.ticker}.JK</dd></div><div><dt>Periode / tanggal</dt><dd>{drawer.period || "Contoh desain"}</dd></div><div><dt>Jenis data</dt><dd>Sintetis · pratinjau UI</dd></div><div><dt>Waktu request API</dt><dd>Belum ada request</dd></div><div><dt>Sumber aktual</dt><dd>Belum terhubung</dd></div>{drawer.field && <div><dt>Field yang direncanakan</dt><dd><code>{drawer.field}</code></dd></div>}</dl><div className="data-note"><ShieldCheck size={18} /><p>Saat terhubung, hanya sumber yang benar-benar tersedia dalam respons backend yang akan ditampilkan.</p></div><button className="secondary-button full-width" onClick={() => { setDrawer(null); navigate("company"); setSelectedCompany(drawer.ticker as Bank); }}>Lihat konteks emiten <ArrowRight size={15} /></button></>}
      {trace && <><p className="drawer-description">Contoh alur agent. Ini bukan rekaman eksekusi langsung.</p><ol className="trace-list">{[["Pahami pertanyaan", "Identifikasi bank, periode, dan tujuan riset."], ["Pilih sumber yang relevan", "Ambil filings dan aksi korporasi sesuai cakupan."], ["Nilai relevansi", "Hilangkan duplikasi dan jelaskan prioritas kejadian."], ["Teliti konteks tambahan", "Ambil metrik keuangan ketika konteks diperlukan."], ["Validasi bukti", "Periksa sumber, periode, satuan, dan konflik data."], ["Susun briefing", "Sampaikan temuan beserta batas datanya."]].map(([title, detail], i) => <li key={title}><span>{String(i + 1).padStart(2, "0")}</span><div><h3>{title}</h3><p>{detail}</p></div></li>)}</ol></>}
      {addBank && <><p className="drawer-description">Pilih hingga empat bank untuk menjelajahi contoh desain.</p><div className="bank-options">{banks.map(bank => <button key={bank} aria-pressed={watchlist.includes(bank)} onClick={() => setWatchlist(prev => prev.includes(bank) ? prev.filter(b => b !== bank) : [...prev, bank])}><BankMark bank={bank} /><span><strong>{bank}</strong><small>{names[bank]}</small></span><span className={`checkbox ${watchlist.includes(bank) ? "checked" : ""}`}>{watchlist.includes(bank) && <Check size={13} />}</span></button>)}</div><button className="primary-button full-width" onClick={() => setAddBank(false)}>Selesai · {watchlist.length} bank <Check size={15} /></button></>}
      {help && <><p className="drawer-description">Pilih jenis riset, tentukan bank, lalu tulis pertanyaan. Prototipe ini menyediakan tiga contoh tampilan hasil.</p><div className="help-items"><p><strong>01 · Disclosure</strong>Temukan kejadian dan alasan relevansinya.</p><p><strong>02 · Peer lens</strong>Bandingkan metrik pada periode yang sebanding.</p><p><strong>03 · Konteks emiten</strong>Lihat tren dan kejadian satu perusahaan.</p></div><div className="data-note"><FlaskConical size={17} /><p>Semua contoh bersifat ilustratif. Tidak ada API key, panggilan Sectors, atau kredit yang digunakan.</p></div></>}
    </section></div>}
  </div>;
}
