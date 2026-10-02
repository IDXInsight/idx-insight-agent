import assert from "node:assert/strict";
import test from "node:test";
import { addToHistory, guessIntent, parseTickers, tickersIn, watchlistForQuery } from "../lib/research.ts";
import { formatPercent } from "../lib/agent.ts";
import { t } from "../lib/i18n.ts";

const banks = ["BBCA", "BBRI", "BMRI", "BBNI"];

test("finds upper-case tickers and watchlist tickers in any case, not finance acronyms", () => {
  assert.deepEqual(tickersIn("Bandingkan BBCA dan TLKM"), ["BBCA", "TLKM"]);
  assert.deepEqual(tickersIn("bagaimana kinerja bbri?", banks), ["BBRI"]);
  assert.deepEqual(tickersIn("Bandingkan CASA dan BOPO"), []);
  assert.deepEqual(tickersIn("Apa saja disclosure minggu depan?"), []);
});

test("sends the watchlist only when the question names no ticker or sector", () => {
  assert.deepEqual(watchlistForQuery("Bagaimana kinerja BBCA?", banks), []);
  assert.deepEqual(watchlistForQuery("Disclosure sektor perbankan minggu depan", banks), []);
  assert.deepEqual(watchlistForQuery("Disclosure apa yang perlu saya pantau minggu depan?", banks), banks);
  assert.deepEqual(watchlistForQuery("Disclosure perbankan di watchlist saya", banks), banks);
});

test("previews the research type the backend rules would pick", () => {
  assert.equal(guessIntent("Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitabilitas", banks), "peers");
  assert.equal(guessIntent("Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?", banks), "discovery");
  assert.equal(guessIntent("Bagaimana kinerja BBCA?", banks), "company");
  assert.equal(guessIntent("Which banking disclosures should I watch next week?", banks), "discovery");
  assert.equal(guessIntent("Compare TLKM and ISAT on ROE", banks), "peers");
  assert.equal(guessIntent("ab", banks), null);
});

test("parses ticker input and reports invalid tokens", () => {
  assert.deepEqual(parseTickers("tlkm, ASII bbca.jk TLKM"), { tickers: ["TLKM", "ASII", "BBCA"], invalid: [] });
  assert.deepEqual(parseTickers("BBC, CASA, ok12"), { tickers: [], invalid: ["BBC", "CASA", "ok12"] });
});

test("keeps the newest result per question and language", () => {
  const entry = (id, query, language = "id") => ({ id, query, language, askedAt: "", view: "peers", response: {} });
  const history = addToHistory(addToHistory([entry("1", "Kinerja BBCA")], entry("2", "Kinerja TLKM")), entry("3", "kinerja bbca "));
  assert.deepEqual(history.map(e => e.id), ["3", "2"]);
  assert.equal(addToHistory(history, entry("4", "Kinerja BBCA", "en")).length, 3);
});

test("formats numbers and messages in the interface language", () => {
  assert.equal(formatPercent(0.235, "id"), "23,5%");
  assert.equal(formatPercent(0.235, "en"), "23.5%");
  assert.equal(t("en", "box.scopeWatchlist", { n: 4 }), "Scope: watchlist (4 companies)");
  assert.equal(t("id", "note.offline"), "Backend mati, hubungi tim untuk menyalakan lagi.");
});
