"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BarChart3, BookOpen, CalendarDays, CheckCircle2, Database, FileSearch, ShieldCheck } from "lucide-react";
import AnimatedWaveFooter from "@/components/ui/animated-wave-footer";
import Timeline from "@/components/ui/timeline";
import { ShaderBackground } from "@/components/ui/shader-background";
import HeroRadar from "@/components/hero-radar";
import { FlipLink } from "@/components/ui/flip-button";
import { LANG_STORAGE_KEY, type Lang, isLang } from "@/lib/i18n";
import { landingCopy } from "@/lib/landing-copy";
import { readStored, writeStored } from "@/lib/research";

/** Sections reachable from the header, in page order. */
const SECTIONS = ["journey", "cara-kerja", "glosarium"] as const;
type Section = typeof SECTIONS[number];
const featureIcons = [CalendarDays, BarChart3, FileSearch];

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function Home() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("id");
  const [active, setActive] = useState<Section | null>(null);
  const copy = landingCopy[lang];

  useEffect(() => {
    queueMicrotask(() => setLang(readStored(LANG_STORAGE_KEY, "id", isLang)));
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  // In-page links scroll smoothly and record the section in the URL (shareable, Back works).
  // Scrolling itself never changes the URL; the header shows the visible section instead.
  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link) return;
      const url = new URL(link.href, window.location.href);
      if (url.pathname !== window.location.pathname || !url.hash) return;
      const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
      if (window.location.hash !== url.hash) window.history.pushState(null, "", url.hash);
    }
    document.addEventListener("click", onClick, true);
    // Arriving with a hash (e.g. from the workspace): jump once the pinned timeline has its height.
    const timer = window.setTimeout(() => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (id) document.getElementById(id)?.scrollIntoView({ behavior: "auto", block: "start" });
    }, 350);
    return () => { document.removeEventListener("click", onClick, true); window.clearTimeout(timer); };
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(e => e.isIntersecting).map(e => e.target.id as Section);
      if (visible.length) setActive(visible[visible.length - 1]);
      else if (window.scrollY < window.innerHeight / 2) setActive(null);
    }, { rootMargin: "-45% 0px -50% 0px" });
    SECTIONS.forEach(id => { const el = document.getElementById(id); if (el) observer.observe(el); });
    return () => observer.disconnect();
  }, []);

  function changeLang(next: Lang) { setLang(next); writeStored(LANG_STORAGE_KEY, next); }
  const navLabel: Record<Section, string> = { journey: copy.nav.journey, "cara-kerja": copy.nav.how, glosarium: copy.nav.glossary };

  return <div className="site-page">
    <div className="site-header-bar">
      <header className="site-header"><Link href="/" className="site-brand"><span><Activity size={21} /></span>idx<em>insight</em></Link>
        <nav aria-label={copy.nav.label}>
          {SECTIONS.map(id => <a key={id} href={`#${id}`} className={active === id ? "active" : undefined} aria-current={active === id ? "location" : undefined}>{navLabel[id]}</a>)}
          <div className="lang-toggle" role="group" aria-label={copy.nav.language}>{(["id", "en"] as Lang[]).map(l => <button key={l} aria-pressed={lang === l} className={lang === l ? "selected" : ""} onClick={() => changeLang(l)}>{l.toUpperCase()}</button>)}</div>
          <FlipLink href="/research" className="header-action" label={copy.nav.open} icon={<ArrowUpRight size={15} />} />
        </nav>
      </header>
    </div>
    <main className="landing-main">
      <section className="hero"><ShaderBackground className="hero-shader" /><div className="hero-copy"><span className="kicker"><span /> {copy.hero.kicker}</span><h1>{copy.hero.line1}<br /><strong>{copy.hero.line2}</strong></h1><p>{copy.hero.text}</p><div className="hero-actions"><FlipLink href="/research" className="cta-primary" label={copy.hero.start} icon={<ArrowRight size={17} />} /><FlipLink href="#journey" className="cta-secondary" label={copy.hero.how} icon={<ArrowUpRight size={16} />} /></div><div className="hero-trust"><span><ShieldCheck size={16} /> {copy.hero.trust[0]}</span><span><Database size={16} /> {copy.hero.trust[1]}</span><span><CheckCircle2 size={16} /> {copy.hero.trust[2]}</span></div></div><HeroRadar copy={copy.radar} /></section>
      <Timeline copy={copy.journey} />
      <section className="landing-section" id="cara-kerja"><div className="section-lead"><span className="kicker">{copy.how.kicker}</span><h2>{copy.how.title}</h2><p>{copy.how.text}</p></div><div className="feature-grid">{copy.how.features.map((feature, i) => { const Icon = featureIcons[i]; return <article key={feature.title}><span className="feature-icon"><Icon size={23} /></span><span className="feature-number">{String(i + 1).padStart(2, "0")}</span><h3>{feature.title}</h3><p>{feature.text}</p></article>; })}</div></section>
      <section className="principle-band"><div><span className="kicker">{copy.principle.kicker}</span><h2>{copy.principle.title}</h2></div><p>{copy.principle.text}</p></section>
      <section className="landing-section glossary-section" id="glosarium"><div className="section-lead"><span className="kicker">{copy.glossary.kicker}</span><h2>{copy.glossary.title}</h2><p>{copy.glossary.text}</p></div><div className="glossary-grid">{copy.glossary.terms.map(item => <article key={item.term} className="glossary-card"><div><span className="glossary-term">{item.term}</span><BookOpen size={17} /></div><h3>{item.full}</h3><p>{item.meaning}</p></article>)}</div><p className="glossary-sources">{copy.glossary.sources} <a href="https://www.bi.go.id/id/statistik/Metadata/SSKI/Documents/02_Indikator_Sektor_Perbankan.pdf" target="_blank" rel="noopener noreferrer">Bank Indonesia <ArrowUpRight size={12} /></a> {copy.glossary.and} <a href="https://www.wip.ojk.go.id/id/regulasi/Documents/Pages/Transparansi-dan-Publikasi-Laporan-Bank-Umum-Konvensional/seojk%209-2020.pdf" target="_blank" rel="noopener noreferrer">OJK <ArrowUpRight size={12} /></a>.</p></section>
      <section className="landing-cta"><div><span className="kicker">{copy.cta.kicker}</span><h2>{copy.cta.title}</h2><p>{copy.cta.text}</p></div><FlipLink href="/research" className="cta-primary" label={copy.cta.button} icon={<ArrowRight size={18} />} /></section>
    </main>
    <AnimatedWaveFooter activeView="home" lang={lang} statusLabel={copy.footerStatus}
      onStart={view => router.push(view === "workspace" ? "/research" : `/research?start=${view}`)} />
  </div>;
}
