"use client";

import { useLayoutEffect, useRef } from "react";
import { ArrowRight, BarChart3, CalendarDays, CheckCheck, FileSearch, ListFilter, MessageSquareText, ShieldCheck } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import type { LandingCopy } from "@/lib/landing-copy";

// One icon per step, in the order of the copy's steps.
const stepIcons = [MessageSquareText, ListFilter, CalendarDays, FileSearch, CheckCheck, BarChart3, ShieldCheck];

export default function Timeline({ copy }: { copy: LandingCopy["journey"] }) {
  const total = String(copy.steps.length).padStart(2, "0");
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
          // Pin below the sticky site header so the header never covers the timeline.
          start: () => `top ${document.querySelector(".site-header-bar")?.getBoundingClientRect().height ?? 0}px`,
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
            <span className="kicker"><span /> {copy.kicker}</span>
            <h2 id="journey-title">{copy.title1}<br /><strong>{copy.title2}</strong></h2>
          </div>
          <p>{copy.text}</p>
        </div>
        <div ref={viewportRef} className="journey-viewport" tabIndex={0} aria-label={copy.viewportAria}>
          <div ref={trackRef} className="journey-track">
            <div className="journey-intro" aria-label={copy.introAria}>
              <span className="journey-intro-label">IDX INSIGHT / RESEARCH</span>
              <div className="journey-intro-icon"><MessageSquareText size={28} /></div>
              <p>{copy.question}</p>
              <div className="journey-intro-tickers"><span>BBCA</span><span>BBRI</span><span>BMRI</span><span>BBNI</span></div>
              <div className="journey-intro-bottom"><span>PERTANYAAN → BUKTI</span><ArrowRight size={17} /></div>
            </div>
            <div className="journey-flow" aria-label={copy.flowAria}>
              <div className="journey-rail" aria-hidden="true" />
              {copy.steps.map((step, index) => {
                const Icon = stepIcons[index] ?? MessageSquareText;
                const number = String(index + 1).padStart(2, "0");
                return <article key={number} className={`journey-step ${index % 2 === 0 ? "journey-step-top" : "journey-step-bottom"}`}>
                  <div className="journey-step-content"><span className="journey-step-number">{number} / {total}</span><span className="journey-step-icon"><Icon size={20} /></span><h3>{step.title}</h3><p>{step.text}</p></div>
                  <span className="journey-step-stem" aria-hidden="true" /><span className="journey-step-dot" aria-hidden="true" />
                </article>;
              })}
            </div>
          </div>
        </div>
        <div className="journey-bottom"><span><span className="journey-bottom-dot" /> {copy.adaptive}</span><span>01 — {total} <ArrowRight size={16} /></span></div>
      </div>
    </section>
  );
}
