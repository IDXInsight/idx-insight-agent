/**
 * Client-side helpers for the research box: which tickers a question names, whether the
 * watchlist is sent, a preview of the research type, watchlist input, and the history kept
 * in this browser. The backend still decides the intent; nothing here calls the API.
 */
import type { AgentResponse, ResultView } from "./agent.ts";
import type { Lang } from "./i18n.ts";

export const MAX_WATCHLIST = 20;
/** Starting watchlist for a first visit; the visitor can replace it with any IDX tickers. */
export const DEFAULT_WATCHLIST = ["BBCA", "BBRI", "BMRI", "BBNI"];

// Same exclusions as the backend's entity resolver (`agent/entities.py`).
const NON_TICKERS = new Set([
  "CASA", "BOPO", "EBIT", "IHSG", "BUMN", "RUPS", "LQ45", "NSFR",
]);
const TICKER = /^[A-Z]{4}$/;

export function isTicker(value: string): boolean {
  return TICKER.test(value) && !NON_TICKERS.has(value);
}

/** Upper-case 4-letter tickers in a question, plus watchlist tickers written in any case. */
export function tickersIn(query: string, watchlist: string[] = []): string[] {
  const found = new Set<string>();
  for (const match of query.matchAll(/\b([A-Za-z]{4})(?:\.JK)?\b/g)) {
    const token = match[1];
    const upper = token.toUpperCase();
    if (NON_TICKERS.has(upper)) continue;
    if (token === upper || watchlist.includes(upper)) found.add(upper);
  }
  return [...found];
}

const SECTOR = /\b(sektor|sector|perbankan|banking|banks|bank-bank)\b/i;
const WATCHLIST_WORD = /\b(watchlist|daftar pantau(an)?|pantauan saya|my list)\b/i;

/**
 * The backend treats every watchlist ticker as a company to research, so the watchlist is
 * sent only when the question names no ticker and no sector of its own (or asks for it).
 */
export function watchlistForQuery(query: string, watchlist: string[]): string[] {
  if (tickersIn(query, watchlist).length) return [];
  if (SECTOR.test(query) && !WATCHLIST_WORD.test(query)) return [];
  return watchlist;
}

const DISCOVERY = /\b(disclosure|keterbukaan|pantau|memantau|monitor|event|peristiwa|agenda|jadwal|aksi korporasi|corporate action|rups|agm|dividen|dividend|filing|pengumuman|watch|announcement|upcoming|pay attention)/i;
const PEER = /\b(bandingkan|perbandingan|membandingkan|compare|comparison|versus|vs\.?|dibanding\w*)\b/i;

/** Preview of the research type the backend's rules would pick (mirrors `agent/intent.py`). */
export function guessIntent(query: string, watchlist: string[]): ResultView | null {
  if (query.trim().length < 3) return null;
  const scoped = watchlistForQuery(query, watchlist);
  const companies = tickersIn(query, watchlist).length || scoped.length;
  const sector = SECTOR.test(query);
  if (PEER.test(query) && (companies >= 2 || sector)) return "peers";
  if (DISCOVERY.test(query) && (companies || sector)) return "discovery";
  if (companies === 1) return "company";
  if (DISCOVERY.test(query)) return "discovery";
  if (companies >= 2) return "peers";
  return null;
}

/** Parses "tlkm, ASII bbca.jk" into tickers; returns the invalid tokens separately. */
export function parseTickers(input: string): { tickers: string[]; invalid: string[] } {
  const tickers: string[] = [];
  const invalid: string[] = [];
  for (const raw of input.split(/[\s,;]+/)) {
    if (!raw) continue;
    const ticker = raw.toUpperCase().replace(/\.JK$/, "");
    if (isTicker(ticker)) { if (!tickers.includes(ticker)) tickers.push(ticker); }
    else invalid.push(raw);
  }
  return { tickers, invalid };
}

export type HistoryEntry = {
  id: string;
  query: string;
  language: Lang;
  askedAt: string;
  view: ResultView;
  response: AgentResponse;
};

export const MAX_HISTORY = 12;

/** Newest first, one entry per question and language (a repeat replaces the older entry). */
export function addToHistory(history: HistoryEntry[], entry: HistoryEntry): HistoryEntry[] {
  const key = (e: HistoryEntry) => `${e.language}:${e.query.trim().toLowerCase()}`;
  return [entry, ...history.filter(e => key(e) !== key(entry))].slice(0, MAX_HISTORY);
}

/** Reads a JSON value from localStorage; any failure (private mode, bad data) gives the fallback. */
export function readStored<T>(key: string, fallback: T, valid: (value: unknown) => value is T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    const value: unknown = JSON.parse(raw);
    return valid(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

/** Writes to localStorage; drops the oldest history entries if the quota is exceeded. */
export function writeStored(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    if (Array.isArray(value) && value.length > 1) writeStored(key, value.slice(0, Math.ceil(value.length / 2)));
  }
}

export function isTickerList(value: unknown): value is string[] {
  return Array.isArray(value) && value.length <= MAX_WATCHLIST && value.every(v => typeof v === "string" && isTicker(v));
}

export function isHistory(value: unknown): value is HistoryEntry[] {
  return Array.isArray(value) && value.every(e =>
    !!e && typeof e === "object" && typeof (e as HistoryEntry).id === "string" && typeof (e as HistoryEntry).query === "string"
    && !!(e as HistoryEntry).response && typeof (e as HistoryEntry).response === "object");
}
