import type { CSSProperties } from "react";
import { colorFor } from "@/lib/palette";

/**
 * Company monogram. Sectors provides no company logos, so the mark shows the ticker in the
 * company's chart colour, the same colour it has in every chart and table.
 */
export default function TickerMark({ symbol, order, size = "md" }: { symbol: string; order: string[]; size?: "sm" | "md" }) {
  return <span className={`ticker-mark ${size}`} style={{ "--mark": colorFor(symbol, order) } as CSSProperties} aria-hidden="true">{symbol}</span>;
}
