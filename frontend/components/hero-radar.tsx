"use client";

import { BarChart3, CalendarDays, FileSearch, Sparkles } from "lucide-react";
import type { LandingCopy } from "@/lib/landing-copy";

export default function HeroRadar({ copy }: { copy: LandingCopy["radar"] }) {
  return (
    <div
      className="hero-visual"
      role="img"
      aria-label={copy.aria}
    >
      <div className="visual-orbit">
        <span className="radar-ring radar-ring-outer" aria-hidden="true" />
        <span className="radar-ring radar-ring-inner" aria-hidden="true" />
        <span className="radar-sweep" aria-hidden="true" />
        <span className="radar-wave radar-wave-one" aria-hidden="true" />
        <span className="radar-wave radar-wave-two" aria-hidden="true" />

        <div className="visual-core">
          <Sparkles size={32} />
          <span>IDX INSIGHT</span>
          <small>{copy.agent}</small>
        </div>

        <div className="orbit-lane orbit-lane-one">
          <div className="orbit-anchor">
            <div className="visual-chip"><CalendarDays size={17} /> Disclosure</div>
          </div>
        </div>
        <div className="orbit-lane orbit-lane-two">
          <div className="orbit-anchor">
            <div className="visual-chip"><BarChart3 size={17} /> Peer lens</div>
          </div>
        </div>
        <div className="orbit-lane orbit-lane-three">
          <div className="orbit-anchor">
            <div className="visual-chip"><FileSearch size={17} /> Evidence</div>
          </div>
        </div>
      </div>
      <div className="visual-caption">{copy.caption}</div>
    </div>
  );
}
