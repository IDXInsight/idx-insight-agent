"use client";

import { useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Pause, Play, ShieldCheck } from "lucide-react";

type ResearchView = "workspace" | "discovery" | "peers" | "company";

type AnimatedWaveFooterProps = {
  activeView: ResearchView;
  onNavigate: (view: ResearchView) => void;
  onNewResearch: () => void;
  onOpenGuide: () => void;
  onOpenTrace: () => void;
  live?: boolean;
  dataLabel?: string;
};

const navigation: { view: ResearchView; label: string }[] = [
  { view: "workspace", label: "Ruang riset" },
  { view: "discovery", label: "Disclosure radar" },
  { view: "peers", label: "Peer lens" },
  { view: "company", label: "Konteks emiten" },
];

/** Shared footer, adapted from the supplied animated-wave-footer reference. */
export default function AnimatedWaveFooter({
  activeView, onNavigate, onNewResearch, onOpenGuide, onOpenTrace, live = false, dataLabel = "data Sectors",
}: AnimatedWaveFooterProps) {
  const [paused, setPaused] = useState(false);

  function navigate(view: ResearchView) {
    onNavigate(view);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  return (
    <footer className="wave-footer" aria-label="Footer IDX Insight">
      <div className="wave-footer-art" aria-hidden="true">
        <div className={`wave-footer-track${paused ? " is-paused" : ""}`}>
          {[0, 1].map(copy => (
            <svg key={copy} viewBox="0 0 1800 500" preserveAspectRatio="none" focusable="false">
              <path d="M0 250C200 150 400 50 600 100C800 150 1000 350 1200 300C1400 250 1600 150 1800 250V500H0V250Z" fill="currentColor" className="wave-footer-back" />
              <path d="M0 250C200 200 400 100 600 150C800 200 1000 350 1200 300C1400 250 1600 200 1800 250V500H0V250Z" fill="currentColor" className="wave-footer-front" />
            </svg>
          ))}
        </div>
      </div>

      <div className="wave-footer-inner">
        <div className="wave-footer-grid">
          <section className="wave-footer-intro" aria-labelledby="footer-brand">
            <div className="wave-footer-brand" id="footer-brand">
              <span className="wave-footer-mark"><Activity size={20} aria-hidden="true" /></span>
              <span>idx<span>insight</span></span>
            </div>
            <p>Temukan konteks.<br />Pahami yang penting.</p>
            <span className="wave-footer-description">Ruang riset emiten perbankan dengan temuan yang bisa ditelusuri.</span>
            <button className="wave-footer-cta" onClick={() => { onNewResearch(); window.scrollTo({ top: 0, behavior: "instant" }); }}>
              Mulai riset baru <ArrowRight size={14} aria-hidden="true" />
            </button>
          </section>

          <nav className="wave-footer-column" aria-labelledby="footer-explore">
            <h2 id="footer-explore">Jelajahi riset</h2>
            {navigation.map(item => (
              <button key={item.view} aria-current={activeView === item.view ? "page" : undefined} onClick={() => navigate(item.view)}>
                {item.label}<ArrowUpRight size={12} aria-hidden="true" />
              </button>
            ))}
          </nav>

          <section className="wave-footer-column" aria-labelledby="footer-sources">
            <h2 id="footer-sources">Data & sumber</h2>
            <a href="https://sectors.app/" target="_blank" rel="noopener noreferrer">Sectors <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only"> (buka tab baru)</span></a>
            <a href="https://docs.sectors.app/get-started/v2/overview" target="_blank" rel="noopener noreferrer">Dokumentasi API v2 <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only"> (buka tab baru)</span></a>
            <button onClick={onOpenTrace}>Proses & validasi bukti <ArrowUpRight size={12} aria-hidden="true" /></button>
            <span className="wave-footer-source-note"><ShieldCheck size={14} aria-hidden="true" /> Dibangun di atas bukti</span>
          </section>

          <section className="wave-footer-column wave-footer-guide" aria-labelledby="footer-guide">
            <h2 id="footer-guide">Kenali workspace</h2>
            <p>Pelajari cara membaca disclosure, membandingkan bank, dan menelusuri sumber setiap temuan.</p>
            <button className="wave-footer-guide-button" onClick={onOpenGuide}><BookOpen size={14} aria-hidden="true" /> Panduan riset <ArrowRight size={13} aria-hidden="true" /></button>
            <span className="wave-footer-demo"><span aria-hidden="true" /> {live ? `Terhubung ke agent · ${dataLabel}` : "Prototipe · data ilustrasi"}</span>
          </section>
        </div>

        <div className="wave-footer-bottom">
          <span>© 2026 IDX Insight Agent</span>
          <span>Informasi & analisis. Bukan rekomendasi investasi.</span>
          <div className="wave-footer-bottom-right"><span>SECTORS HACKATHON 2026</span><button className="wave-footer-motion" onClick={() => setPaused(value => !value)} aria-label={paused ? "Putar animasi gelombang" : "Jeda animasi gelombang"} title={paused ? "Putar animasi gelombang" : "Jeda animasi gelombang"}>{paused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}</button></div>
        </div>
      </div>
    </footer>
  );
}
