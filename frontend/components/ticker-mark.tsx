import type { CSSProperties } from "react";
import Image from "next/image";
import { colorFor } from "@/lib/palette";

const logos: Record<string, string> = {
  BBCA: "/banks/bbca.png",
  BBRI: "/banks/bbri.svg",
  BMRI: "/banks/bmri.png",
  BBNI: "/banks/bbni.svg",
};

/** Known bank logos; other IDX symbols keep the existing colour-coded ticker mark. */
export default function TickerMark({ symbol, order, size = "md" }: { symbol: string; order: string[]; size?: "sm" | "md" }) {
  const logo = logos[symbol];
  return <span className={`ticker-mark ${size}${logo ? " has-logo" : ""}`} style={{ "--mark": colorFor(symbol, order) } as CSSProperties} aria-hidden="true">
    {logo ? <Image src={logo} alt="" width={56} height={28} /> : symbol}
  </span>;
}
