"use client";

import Link from "next/link";
import { useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Pause, Play, ShieldCheck } from "lucide-react";
import { type Lang, type MessageKey, t } from "@/lib/i18n";
import { FlipButton, FlipLink } from "@/components/ui/flip-button";

type ResearchView = "home" | "workspace" | "discovery" | "peers" | "company";
export type StartView = Exclude<ResearchView, "home">;

type AnimatedWaveFooterProps = {
  activeView: ResearchView;
  /** Starts a new research of that type (the footer starts research; the sidebar reopens results). */
  onStart: (view: StartView) => void;
  lang: Lang;
  /** Connection state shown next to the guide, e.g. "Terhubung · data Sectors". */
  statusLabel: string;
};

const navigation: { view: StartView; label: MessageKey }[] = [
  { view: "workspace", label: "nav.workspace" },
  { view: "discovery", label: "nav.discovery" },
  { view: "peers", label: "nav.peers" },
  { view: "company", label: "nav.company" },
];

/**
 * Shared footer, adapted from the supplied animated-wave-footer reference. It is site
 * navigation: it starts research or moves to a landing-page section, and never opens a modal.
 */
export default function AnimatedWaveFooter({ activeView, onStart, lang, statusLabel }: AnimatedWaveFooterProps) {
  const [paused, setPaused] = useState(false);

  function start(view: StartView) {
    onStart(view);
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
            <FlipButton className="wave-footer-cta" onClick={() => start("workspace")} label={t(lang, "footer.cta")} icon={<ArrowRight size={14} aria-hidden="true" />} />
          </section>

          <nav className="wave-footer-column" aria-labelledby="footer-explore">
            <h2 id="footer-explore">{t(lang, "footer.explore")}</h2>
            {navigation.map(item => (
              <button key={item.view} aria-current={activeView === item.view ? "page" : undefined} onClick={() => start(item.view)}>
                {t(lang, item.label)}<ArrowUpRight size={12} aria-hidden="true" />
              </button>
            ))}
          </nav>

          <section className="wave-footer-column" aria-labelledby="footer-sources">
            <h2 id="footer-sources">{t(lang, "footer.data")}</h2>
            <a href="https://sectors.app/" target="_blank" rel="noopener noreferrer">Sectors <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only">{t(lang, "newTab")}</span></a>
            <a href="https://docs.sectors.app/get-started/v2/overview" target="_blank" rel="noopener noreferrer">{t(lang, "footer.docs")} <ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only">{t(lang, "newTab")}</span></a>
            <Link href="/#journey">{t(lang, "footer.process")} <ArrowUpRight size={12} aria-hidden="true" /></Link>
            <span className="wave-footer-source-note"><ShieldCheck size={14} aria-hidden="true" /> {t(lang, "sidebar.noteTitle")}</span>
          </section>

          <section className="wave-footer-column wave-footer-guide" aria-labelledby="footer-guide">
            <h2 id="footer-guide">{t(lang, "footer.know")}</h2>
            <p>{t(lang, "footer.knowText")}</p>
            <FlipLink href="/#cara-kerja" className="wave-footer-guide-button" iconPosition="start" label={t(lang, "sidebar.guide")} icon={<BookOpen size={14} aria-hidden="true" />} />
            <Link href="/#glosarium">{t(lang, "nav.glossary")} <ArrowUpRight size={12} aria-hidden="true" /></Link>
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
