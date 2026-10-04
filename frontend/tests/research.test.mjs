import assert from "node:assert/strict";
import test from "node:test";
import { addToHistory, guessIntent, nextStep, parseTickers, tickersIn, watchlistForQuery } from "../lib/research.ts";
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
  // Small talk and requests for picks must not turn into a four-bank research run.
  assert.deepEqual(watchlistForQuery("Lu siapa?", banks), []);
  assert.deepEqual(watchlistForQuery("Ada ga sih bank yang jelek?", banks), []);
  assert.deepEqual(watchlistForQuery("Menurutlu bank apa yang perlu gue analisis?", banks), []);
  assert.deepEqual(watchlistForQuery("Bandingkan profitabilitas bank di daftar pantauan", banks), banks);
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

test("keeps separate results for repeated questions and more than twelve runs", () => {
  const entry = (id, query, language = "id") => ({ id, query, language, askedAt: "", view: "peers", response: {} });
  const history = addToHistory(addToHistory([entry("1", "Kinerja BBCA")], entry("2", "Kinerja TLKM")), entry("3", "kinerja bbca "));
  assert.deepEqual(history.map(e => e.id), ["3", "2", "1"]);
  assert.equal(addToHistory(history, entry("4", "Kinerja BBCA", "en")).length, 4);
  const many = Array.from({ length: 20 }, (_, i) => entry(String(i), "Pertanyaan sama"))
    .reduce((previous, current) => addToHistory(previous, current), []);
  assert.equal(many.length, 20);
});

test("formats numbers and messages in the interface language", () => {
  assert.equal(formatPercent(0.235, "id"), "23,5%");
  assert.equal(formatPercent(0.235, "en"), "23.5%");
  assert.equal(t("en", "box.scopeWatchlist", { n: 4 }), "Scope: watchlist (4 companies)");
  assert.equal(t("id", "note.offline"), "Backend mati, hubungi tim untuk menyalakan lagi.");
});

test("offers a follow-up built from the open result", () => {
  assert.deepEqual(nextStep("company", ["BBCA"], [], banks), { kind: "compare", companies: ["BBCA", "BBRI", "BMRI", "BBNI"] });
  assert.deepEqual(nextStep("company", ["TLKM"], [], banks), { kind: "compare", companies: ["TLKM", "BBCA", "BBRI", "BMRI"] });
  assert.equal(nextStep("company", ["BBCA"], [], ["BBCA"]), null);
  assert.deepEqual(nextStep("peers", ["BBCA", "BBRI"], [], banks), { kind: "disclosure", companies: ["BBCA", "BBRI"] });
  assert.deepEqual(nextStep("discovery", [], ["BBNI", "BBTN", "BBNI"], banks), { kind: "compareEvents", companies: ["BBNI", "BBTN"] });
  assert.deepEqual(nextStep("discovery", [], ["AGRO"], banks), { kind: "company", companies: ["AGRO"] });
  assert.equal(nextStep("discovery", [], [], banks), null);
});
