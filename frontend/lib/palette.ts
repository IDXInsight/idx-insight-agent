/**
 * Categorical colours for companies, validated for the dark surface (#191e1a): lightness
 * band, chroma floor, colour-blind and normal-vision separation, 3:1 contrast. A company
 * keeps its colour in the watchlist, the charts and the tables (by entity, never by rank).
 */
export const seriesColors = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
/** Companies beyond the eighth share one neutral colour; their ticker label carries identity. */
export const overflowColor = "#7d8a81";

export function colorFor(symbol: string, order: string[]): string {
  const index = order.indexOf(symbol);
  return index >= 0 && index < seriesColors.length ? seriesColors[index] : overflowColor;
}

/** Watchlist first, then any other company in the result, without duplicates. */
export function colorOrder(watchlist: string[], others: string[]): string[] {
  return [...new Set([...watchlist, ...others])];
}
