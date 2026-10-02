# End-to-End Validation (Phase 6)

Results of running the complete product (Next.js → FastAPI → Agent Brain → Sectors →
validation → LLM synthesis → UI) on real data. Each run lists what was asked, what the
product did, and what changed because of it.

## Run 1 — local, real data (2026-10-02)

Authored by: Prama

| Setting | Value |
|---|---|
| Where | Local machine: backend `uvicorn` + frontend `npm run dev` |
| Data | `SECTORS_DATA_MODE=real` (live Sectors v2 API) |
| LLM | Groq `openai/gpt-oss-120b` (active, no fallback observed) |
| Sectors credits | About 40 for the whole run (total, not measured per question) |
| Latency | Under 5 seconds per answer (observed, not timed per question) |

### Questions

| # | Question (as typed, paraphrased where noted) | Expected | Result |
|---|---|---|---|
| 1 | Compare the four banks (BBCA, BBRI, BMRI, BBNI), including "cost to income" (paraphrased) | Peer comparison with the cost-to-income ratio | **Issue**: "cost to income" written with spaces was not recognised as a metric. Fixed in `agent/intent.py` (spaces and "cost/income" now map to `cost_to_income_ratio`, with a test). Needs a live re-check |
| 2 | Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan? | Discovery over the bank sub-sector with second-hop research | As expected |
| 3 | Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitabilitas | Peer comparison of ROA and ROE | Answer as expected. **Issue**: the chart was hard to read (one metric at a time behind a dropdown, unsorted, no median) |
| 4 | Bandingkan NPL BBCA, BBRI, BMRI dan BBNI | NPL from the screener for all four banks | As expected |
| 5 | Disclosure bank syariah minggu depan | Clarification question (BRIS or BTPS) instead of a guess | As expected |

### UI findings

| Finding | Follow-up |
|---|---|
| Chart hard to read | Replaced by small multiples: one column chart per metric, sorted by the favourable direction, peer median line, colours fixed per company |
| After opening one company, the four-bank comparison could not be shown again | Fixed: every result is kept; each view opens the latest result of its type |
| No research history; a new question replaced the previous result | Fixed: research history in the sidebar, reopened without a new API call |
| Placeholders (profile, labels, illustrative data next to real results) | Fixed: no illustrative data, "Researcher" profile, ID/EN labels, offline message |
| The research-type tabs did not follow the typed question | Fixed: the type is detected while typing; the backend still decides |

### Not covered by this run

- Credits and latency per question type (only totals were observed)
- Cross-checking values against the Sectors app
- Non-bank companies and other sectors
- Failure cases: Groq rate limit, credit cap reached, Redis unavailable, timeouts
- The deployed product (this run was local)
- English questions

## Run 2 — deployed product, real data (2026-10-02)

| Setting | Value |
|---|---|
| Where | https://idx-insight.vercel.app, through the Next.js proxy (the browser's path: Firewall, shared secret, per-client limits) |
| Data | Live Sectors v2 API |
| LLM | Groq `openai/gpt-oss-120b` (used for synthesis in P1–P4; P5 had nothing to synthesise) |
| Sectors credits | About 20, estimated from the 15 tool calls (the deployment ledger in Redis was not read) |
| Latency | 2.3–4.9 s per new question; a repeated question came from the answer cache |

### Questions

| # | Question | Expected | Result |
|---|---|---|---|
| P1 | Bandingkan BBCA dan BBRI dari sisi cost to income | Run 1's parser fix works live | Parser fix works (2 calls, 3.7 s). **Data issue**: BBCA 51.5% vs BBRI 1.9%. The BBRI series in Sectors mixes 1.86, 1.85, 1.16, 1.00, 1.06 and 1.89; the per-value unit check read 1.89 as percent and 1.16 as a fraction. Fixed: units are now decided per series and a mixed series is reported as a malformed-data gap (needs a deploy and a live re-check) |
| P2 | Bagaimana kinerja TLKM? | Non-bank company context | As expected: ROA, ROE, earnings and revenue growth, two AGMs; NIM marked not applicable (6 calls, 4.9 s) |
| P3 | Compare ROE of TLKM and ISAT (English) | Non-bank comparison in English | As expected (2 calls, 3.5 s). Minor: the LLM narrative says "sector median" for the median of two companies |
| P4 | Bandingkan NIM BBCA dan TLKM | NIM for BBCA only; TLKM not applicable, no comparison | As expected: status partial, both gaps reported (2 calls, 2.7 s) |
| P5 | Disclosure ASII minggu depan | Non-bank discovery | 5 events found, none relevant in next week's window; status insufficient evidence, no invented events (3 calls, 2.3 s) |

The production UI was checked with P3 (answer cache, no credits): English labels,
small-multiple chart, history and the connection label work. It showed one UI issue,
the watchlist ROE column filled with dashes when no watchlist company is in the result
(fixed).

### Findings

| Finding | Follow-up |
|---|---|
| Mixed units in one ratio series produced a wrong cost-to-income comparison | Fixed in `analytics/numbers.py` and `agent/financials.py`, with tests |
| Sectors does not document the definition or unit of `cost_to_income_ratio`; the values (BBCA 0.52–0.89, BBRI 1.00–1.89) do not match commonly reported bank cost-to-income ratios | Open: cross-check with the Sectors app or ask the Sectors team; until then treat the metric as unverified |
| A company named in the question gets the relevance reason "Company is on the watchlist" | Open (wording) |
| Company questions about non-banks always add the gap "NIM applies to banks only" | Open (noise; the default bundle includes NIM) |
| The LLM narrative may call a two-company median a "sector median" | Open (wording) |

## Run 3 — fixes re-checked, real-data evaluation, failure cases (2026-10-02)

### Re-check on the deployed product

"Bandingkan cost to income BBCA dengan BBRI" (worded differently from P1 so the answer
cache is not hit): status partial, BBCA 51.5%, BBRI left out with a malformed-data gap
that lists the raw series, and the narrative explains it. The run also showed a second,
inaccurate gap ("not available in Sectors data"); fixed so a mixed-unit series is only
reported as malformed.

### Real-data evaluation (`evals/cases_real.json`, local, Groq)

`SECTORS_DATA_MODE=real python -m evals.run_eval --cases real --live --pause 25`:
6/8 passed, 31 credits, no LLM failures.

| Case | Result |
|---|---|
| real_peer_profitability_id, real_peer_npl, real_company_context, real_advice_en, real_watchlist, real_ambiguous | Pass |
| real_discovery_banks_id, real_discovery_banks_en | Fail on "at least one company researched in second hop". Replayed from the cache (0 credits): the bank sub-sector (48 companies) has 4 events for next week, three tiny insider buys (0.00%) and one AGM (AGRO, score 40, below the second-hop threshold of 50). The agent behaves as designed; the expectation assumes a busy week |

### Failure cases (no credits)

| Case | Result |
|---|---|
| Invalid input to the proxy (language `fr`, ticker `XX1`, two-letter question, non-JSON body) | 400 `invalid_request`; nothing reaches the backend |
| Direct call to the backend without the shared secret | 403 from the Vercel Firewall; with a wrong secret 401 from the API; only `/health` is public |
| Firewall rate limit (12 quick repeats of a cached question) | Requests 11 and 12 get 429 with the firewall's own body. The page showed the generic backend error for it; fixed |
| Daily credit cap reached (local, cap set to the day's spend) | The Sectors call is refused before it is sent (0 credits). **Open**: the visitor sees "ticker could not be verified" and a clarification question instead of a credit-limit message |
| Backend offline | The workspace shows "Backend mati, hubungi tim untuk menyalakan lagi." and disables the research box (checked locally) |

### Findings

| Finding | Follow-up |
|---|---|
| "Disclosure perbankan minggu depan" gives a thin answer this week | For the demo, use a window with more events (e.g. this month) or named companies |
| Credit-cap refusal is reported as an unverifiable ticker | Open |
| Real-data discovery cases expect second-hop research in every week | Open: make the expectation conditional on a relevant event above the threshold |
| Not yet tested live: Groq rate-limit fallback, Redis unavailable, timeouts | Covered by unit tests only |
