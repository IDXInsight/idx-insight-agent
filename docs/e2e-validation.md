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
| After opening one company, the four-bank comparison could not be shown again | Open: the UI keeps only one result |
| No research history; a new question replaced the previous result | Open |
| Placeholders (profile, labels, illustrative data next to real results) | Open |
| The research-type tabs did not follow the typed question | Open |

### Not covered by this run

- Credits and latency per question type (only totals were observed)
- Cross-checking values against the Sectors app
- Non-bank companies and other sectors
- Failure cases: Groq rate limit, credit cap reached, Redis unavailable, timeouts
- The deployed product (this run was local)
- English questions
