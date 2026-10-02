"use client";

import { useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Pause, Play, ShieldCheck } from "lucide-react";
import { type Lang, type MessageKey, t } from "@/lib/i18n";

type ResearchView = "workspace" | "discovery" | "peers" | "company";

type AnimatedWaveFooterProps = {
  activeView: ResearchView;
  onNavigate: (view: ResearchView) => void;
  onNewResearch: () => void;
  onOpenGuide: () => void;
  onOpenTrace: () => void;
  lang: Lang;
  /** Connection state shown next to the guide, e.g. "Terhubung · data Sectors". */
  statusLabel: string;
};

const navigation: { view: ResearchView; label: MessageKey }[] = [
  { view: "workspace", label: "nav.workspace" },
  { view: "discovery", label: "nav.discovery" },
  { view: "peers", label: "nav.peers" },
  { view: "company", label: "nav.company" },
];

/** Shared footer, adapted from the supplied animated-wave-footer reference. */
export default function AnimatedWaveFooter({
  activeView, onNavigate, onNewResearch, onOpenGuide, onOpenTrace, lang, statusLabel,
}: AnimatedWaveFooterProps) {
  const [paused, setPaused] = useState(false);

  function navigate(view: ResearchView) {
    onNavigate(view);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  return (
    <footer className="wave-footer" aria-label={t(lang, "footer.label")}>
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
            <p>{t(lang, "heading.line1")}<br />{t(lang, "heading.line2")}</p>
            <span className="wave-footer-description">{t(lang, "footer.description")}</span>
            <button className="wave-footer-cta" onClick={() => { onNewResearch(); window.scrollTo({ top: 0, behavior: "instant" }); }}>
              {t(lang, "footer.cta")} <ArrowRight size={14} aria-hidden="true" />
            </button>
          </section>

          <nav className="wave-footer-column" aria-labelledby="footer-explore">
            <h2 id="footer-explore">{t(lang, "footer.explore")}</h2>
            {navigation.map(item => (
              <button key={item.view} aria-current={activeView === item.view ? "page" : undefined} onClick={() => navigate(item.view)}>
                {t(lang, item.label)}<ArrowUpRight size={12} aria-hidden="true" />
              </button>
            ))}
          </nav>

          <section className="wave-footer-column" aria-labelledby="footer-sources">
            <h2 id="footer-sources">{t(lang, "footer.data")}</h2>
            <a href="https://sectors.app/" target="_blank" rel="noopener noreferrer">Sectors <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only">{t(lang, "newTab")}</span></a>
            <a href="https://docs.sectors.app/get-started/v2/overview" target="_blank" rel="noopener noreferrer">{t(lang, "footer.docs")} <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only">{t(lang, "newTab")}</span></a>
            <button onClick={onOpenTrace}>{t(lang, "footer.process")} <ArrowUpRight size={12} aria-hidden="true" /></button>
            <span className="wave-footer-source-note"><ShieldCheck size={14} aria-hidden="true" /> {t(lang, "sidebar.noteTitle")}</span>
          </section>

          <section className="wave-footer-column wave-footer-guide" aria-labelledby="footer-guide">
            <h2 id="footer-guide">{t(lang, "footer.know")}</h2>
            <p>{t(lang, "footer.knowText")}</p>
            <button className="wave-footer-guide-button" onClick={onOpenGuide}><BookOpen size={14} aria-hidden="true" /> {t(lang, "sidebar.guide")} <ArrowRight size={13} aria-hidden="true" /></button>
            <span className="wave-footer-demo"><span aria-hidden="true" /> {statusLabel}</span>
          </section>
        </div>

        <div className="wave-footer-bottom">
          <span>© 2026 IDX Insight Agent</span>
          <span>{t(lang, "footer.disclaimer")}</span>
          <div className="wave-footer-bottom-right"><span>SECTORS HACKATHON 2026</span><button className="wave-footer-motion" onClick={() => setPaused(value => !value)} aria-label={t(lang, paused ? "footer.play" : "footer.pause")} title={t(lang, paused ? "footer.play" : "footer.pause")}>{paused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}</button></div>
        </div>
      </div>
    </footer>
  );
}
