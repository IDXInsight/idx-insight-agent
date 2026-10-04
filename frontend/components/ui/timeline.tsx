"use client";

import { useLayoutEffect, useRef } from "react";
import { ArrowRight, BarChart3, CalendarDays, CheckCheck, FileSearch, ListFilter, MessageSquareText, ShieldCheck } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

type JourneyStep = {
  number: string;
  title: string;
  description: string;
  icon: typeof MessageSquareText;
};

const steps: JourneyStep[] = [
  { number: "01", title: "Mulai dengan pertanyaan", description: "Tanyakan disclosure yang perlu dipantau atau bandingkan kinerja bank dalam watchlist.", icon: MessageSquareText },
  { number: "02", title: "Pilih jalur riset", description: "Agen menyesuaikan sumber dan langkah dengan maksud pertanyaan, bukan memanggil semua data sekaligus.", icon: ListFilter },
  { number: "03", title: "Tentukan cakupan", description: "Emiten, rentang waktu, periode laporan, dan metrik diperiksa sebelum perbandingan dibuat.", icon: CalendarDays },
  { number: "04", title: "Ambil data relevan", description: "Filing, corporate action, atau laporan keuangan diminta dari sumber yang sesuai kebutuhan.", icon: FileSearch },
  { number: "05", title: "Periksa kesebandingan", description: "Tanggal, satuan, periode, duplikat, dan nilai yang hilang dicek sebelum menjadi temuan.", icon: CheckCheck },
  { number: "06", title: "Susun insight", description: "Jika datanya cukup, agen menyusun briefing dan perbandingan bank yang mudah dibaca.", icon: BarChart3 },
  { number: "07", title: "Telusuri buktinya", description: "Lihat sumber, parameter, waktu data, dan jejak tool di balik klaim yang ditampilkan.", icon: ShieldCheck },
];

export default function Timeline() {
  const sectionRef = useRef<HTMLElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const section = sectionRef.current;
    const viewport = viewportRef.current;
    const track = trackRef.current;
    if (!section || !viewport || !track) return;

    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(min-width: 761px) and (min-height: 550px) and (prefers-reduced-motion: no-preference)", () => {
      const overflow = () => Math.max(0, track.scrollWidth - viewport.clientWidth);
      gsap.timeline({
        scrollTrigger: {
          trigger: section,
          pin: true,
          start: "top top",
          end: () => `+=${Math.max(1, overflow())}`,
          scrub: true,
          anticipatePin: 1,
          invalidateOnRefresh: true,
        },
      }).to(track, { x: () => -overflow(), ease: "none", duration: 1 });
    }, section);

    return () => media.revert();
  }, []);

  return (
    <section ref={sectionRef} id="journey" className="journey-section" aria-labelledby="journey-title">
      <div className="journey-sticky">
        <div className="journey-heading">
          <div>
            <span className="kicker"><span /> 01 / ALUR RISET</span>
            <h2 id="journey-title">Satu pertanyaan.<br /><strong>Jejak riset yang jelas.</strong></h2>
          </div>
          <p>Setiap pertanyaan menempuh langkah yang relevan. Geser atau gulir untuk melihat bagaimana jawaban dibangun.</p>
        </div>
        <div ref={viewportRef} className="journey-viewport" tabIndex={0} aria-label="Tahapan alur riset, geser ke samping untuk melihat seluruh langkah">
          <div ref={trackRef} className="journey-track">
            <div className="journey-intro" aria-label="Contoh pertanyaan riset">
              <span className="journey-intro-label">IDX INSIGHT / RESEARCH</span>
              <div className="journey-intro-icon"><MessageSquareText size={28} /></div>
              <p>“Apa yang perlu saya pantau dari bank dalam watchlist minggu ini?”</p>
              <div className="journey-intro-tickers"><span>BBCA</span><span>BBRI</span><span>BMRI</span><span>BBNI</span></div>
              <div className="journey-intro-bottom"><span>PERTANYAAN → BUKTI</span><ArrowRight size={17} /></div>
            </div>
            <div className="journey-flow" aria-label="Tujuh tahapan riset">
              <div className="journey-rail" aria-hidden="true" />
              {steps.map((step, index) => {
                const Icon = step.icon;
                return <article key={step.number} className={`journey-step ${index % 2 === 0 ? "journey-step-top" : "journey-step-bottom"}`}>
                  <div className="journey-step-content"><span className="journey-step-number">{step.number} / 07</span><span className="journey-step-icon"><Icon size={20} /></span><h3>{step.title}</h3><p>{step.description}</p></div>
                  <span className="journey-step-stem" aria-hidden="true" /><span className="journey-step-dot" aria-hidden="true" />
                </article>;
              })}
            </div>
          </div>
        </div>
        <div className="journey-bottom"><span><span className="journey-bottom-dot" /> ADAPTIF TERHADAP PERTANYAAN</span><span>01 — 07 <ArrowRight size={16} /></span></div>
      </div>
    </section>
  );
}
