# IDX Insight Agent — Development Phases

## Project Status

**Currently until Phase 4**

This document describes the complete project roadmap.
Future phases are documented for planning and team coordination.

| Phase | Name | Status |
|---|---|---|
| 0 | Repository & Foundation | Implemented |
| 1 | Agent Brain | Implemented (mock data) |
| 2 | Backend Foundation | Implemented (mock data) |
| 3 | Analytics & Validation | Implemented (mock data) |
| 4 | Real Sectors Integration | Implemented |
| 5 | Product UI | Planned |
| 6 | End-to-End Validation | Planned |
| 7 | Demo & Submission Preparation | Planned |

Hackathon: SECTORS Hackathon 2026 — Track: AI Agents & Assistants.
Deadline: 8 October 2026, 23:59 WIB (submission and code freeze).
The official rules that shape this plan are summarised in
[Hackathon Rules That Shape the Plan](#hackathon-rules-that-shape-the-plan).

### Proposed Schedule

A proposal for the team to confirm; dates are targets, not commitments.

| Dates (2026) | Phase | Target |
|---|---|---|
| until 26 Sep | 0–3 | Foundation, Agent Brain, backend, analytics & validation (done, mock data) |
| 27–29 Sep | 4 | Real Sectors adapter with credit safeguards; first real-data evaluation |
| 29 Sep – 3 Oct | 5 | Next.js UI and Vercel deployment |
| 3–5 Oct | 6 | End-to-end validation on the deployed product; final LLM choice |
| 5–7 Oct | 7 | Videos, social post, repository cleanup, repository made public |
| 7 Oct | — | Target submission (one day of buffer before the 8 Oct deadline) |

---

## Phase 0 — Repository & Foundation

### Objective
Establish the project structure, documentation, development workflow,
and testing foundation.

### Deliverables
- GitHub repository
- branch structure
- project structure
- configuration
- README
- CLAUDE instructions
- testing foundation

### Dependencies
None.

### Expected Outcome
Every team member can clone the repository, install the backend, run the
test suite, and understand the roadmap and branch workflow.

### Complete When
- `IDXInsight/idx-insight-agent` exists with `main`, `agent-brain` and `backend` branches
- configuration is environment-driven and secrets are git-ignored
- `pytest` runs green from a clean checkout

---

## Phase 1 — Agent Brain

### Objective
Build the core agentic reasoning and orchestration layer.

### Deliverables
- Intent & Entity Resolver
- Planner / Router
- Discovery Agent
- Relevance Engine
- Second-hop decision logic
- Agent state
- LLM prompts
- Bilingual output (Indonesian and English, following the user)
- Provider-agnostic runtime LLM interface (initial candidates: Gemini, Groq)
- Evidence reasoning
- agent tests

### Dependencies
Phase 0. Uses the Sectors adapter interface and mock adapter from Phase 2
(the two phases are developed in parallel on separate branches).

### Expected Outcome
The system can determine what information it needs, choose the next
action, and decide when additional research is necessary.

### Complete When
- intent, entities, sector and timeframe are resolved into explicit, serializable state
- the planner selects a different plan for discovery vs. peer analysis vs. single-company context
- discovery → relevance → second-hop decisions are made and recorded with reasons
- LLM usage sits behind a provider-agnostic interface; the agent also runs with no
  LLM at all, and tests use a deterministic mock provider
- agent decisions (not just HTTP endpoints) are covered by tests

---

## Phase 2 — Backend Foundation

### Objective
Provide the application/backend foundation around the agent.

### Deliverables
- FastAPI
- API routes
- Pydantic schemas
- service layer
- Sectors adapter interface
- Mock Sectors adapter
- configuration
- backend tests

### Dependencies
Phase 0.

### Expected Outcome
The agent can be accessed through a structured backend API using
deterministic mock Sectors data.

### Complete When
- `POST /v1/agent/query` returns a structured briefing, evidence, validation report and execution trace
- all Sectors access goes through `SectorsService` → `SectorsAdapter`
- the mock adapter mirrors documented Sectors response shapes and simulates edge cases
- tool calls are allowlisted, cached and bounded

---

## Phase 3 — Analytics & Validation

### Objective
Add deterministic analysis and evidence validation.

### Deliverables
- financial calculations
- peer comparisons
- event relevance rules
- normalization
- period alignment
- evidence validation
- recovery behavior
- edge-case tests
- evaluation cases and harness (offline and live), to be re-run in Phase 4

### Dependencies
Phases 1 and 2.

### Expected Outcome
The system can perform reproducible analysis and avoid unsupported
conclusions when evidence is incomplete.

### Complete When
- growth, spreads, peer differences, event density and outliers are computed in code, not by the LLM
- every substantive claim links to evidence; unsupported claims are rejected and surfaced as data gaps
- recovery for ambiguous entities/timeframes, missing data, tool errors, empty results and conflicting data is explicit and bounded
- edge cases are covered by deterministic tests

---

## Phase 4 — Real Sectors Integration

### Objective
Replace the mock data layer with the actual Sectors data source.

### Deliverables
- Sectors REST adapter (v2, `https://api.sectors.app/v2/`, header `Authorization: <key>`)
- authentication from `SECTORS_API_KEY` (server-side only)
- real response mapping
- integration tests
- error handling, including exponential backoff on HTTP 429
- credit safeguards, built **before** the first bulk call:
  - a credit ledger with a hard daily cap
  - a local development cache so repeated questions cost no credits
  - one-off recordings of real responses kept locally and never committed
    (see README → Data handling)
- a real-data run of the evaluation cases

### Dependency
Official Sectors API/MCP access and verified documentation. A working API key
was confirmed on 2026-09-27 (one call to `get_quarterly_financial_dates`, HTTP 200).

### Expected Outcome
The same agent runs unchanged against real Sectors data by switching
`SECTORS_DATA_MODE`.

### Complete When
- a real adapter implements the existing `SectorsAdapter` interface
- open questions recorded in the codebase (e.g. company listing shape, upcoming report dates) are resolved against official documentation
- automated tests still use mock data and spend no credits
- the evaluation cases pass on real data within the planned credit budget

### Outcome (2026-09-27)
- Real REST adapter live: filings, market-wide corporate-actions calendar,
  quarterly financials, company report, subsectors and screener (incl. NPL)
- Credit guardrails: caps checked before sending, ledger, local cache/replay, 429 backoff
- Real-data evaluation: 8/8 structural cases with Groq; one real-data bug found and fixed
- Credits used so far: 49 of the team's allowance (probes, first runs and the evaluation)

---

## Phase 5 — Product UI

### Objective
Build the user-facing IDX Insight Agent interface.

### Deliverables
- agent query interface
- discovery results
- event/disclosure timeline
- relevance explanation
- financial context
- peer comparison
- evidence/source cards
- simplified execution trace
- loading states
- error states
- empty states

### Deployment Target
Vercel. Live deployment is not required by the rules, but the team chose to
deploy because a local demo is cumbersome. A public deployment spends Sectors
credits and LLM quota on every question, so it needs:
- API keys only in Vercel environment variables, never in frontend code
- a per-day cap on Sectors calls and LLM calls, with a friendly message when reached
- response caching for repeated questions
- basic request rate limiting per client
- persistent storage for the credit ledger and response cache: Vercel functions
  have an ephemeral file system, so the local `backend/.sectors_local/` files used
  in development do not survive between requests there

### Dependencies
Phase 2 API contract (Phase 4 for real data).

### Complete When
A user can run discovery and peer-analysis queries end-to-end in the
Next.js UI and inspect evidence and the execution trace.

---

## Phase 6 — End-to-End Validation

### Objective
Validate the complete real-data product flow.

### Flow

User
→ Next.js
→ Vercel
→ FastAPI
→ Agent Brain
→ Sectors
→ Analytics
→ Evidence Validation
→ LLM Synthesis
→ UI

### Deliverables
- real-data E2E tests
- live evaluation and selection of the runtime LLM provider and model
- failure-case testing
- performance checks
- security checks
- final integration validation
- a credit reserve kept for the judging period (9–16 Oct), when judges may use
  the deployed product

### Dependencies
Phases 4 and 5.

---

## Phase 7 — Demo & Submission Preparation

### Objective
Prepare the project for SECTORS Hackathon 2026 submission.

### Deliverables
- final demo
- 1-minute teaser
- maximum 3-minute walkthrough
- one-sentence problem statement
- architecture explanation
- repository cleanup
- final documentation
- submission materials

### Submission Checklist (official requirements)
- [ ] public repository link; the repository stays public for at least 90 days after
      winners are announced (17 Oct 2026); all API keys removed
- [ ] one-minute teaser video, published publicly on YouTube or social media
- [ ] judging video of up to three minutes: problem, intended audience and the core
      workflow end to end (public or unlisted YouTube/Vimeo, shared Drive, or Loom)
- [ ] one-sentence problem statement: who the product is for and what problem it solves
- [ ] track selection (AI Agents & Assistants) and participant names
- [ ] social media post (Instagram, LinkedIn, Threads or TikTok) tagging the official
      Sectors account and using the provided thumbnail template
- [ ] demo and videos run with the LLM enabled and real Sectors data (not mock data)

### Code Freeze
The repository and the deployed application freeze when the team submits or at
the deadline, whichever comes first. After that, no commits, pushes or edits of any
kind are allowed, including bug fixes. The only exception is a leaked credential:
notify organisers on Slack (#support), revoke and rotate the credential, then push a
commit that only removes it.

### Dependencies
Phase 6.

---

## Hackathon Rules That Shape the Plan

Summary of the official rules (https://hackathon.sectors.app/rules) and the AI Agents &
Assistants track page, read on 2026-09-27. The official pages remain authoritative.

| Rule | What it means for us |
|---|---|
| Submissions and build period close **8 Oct 2026, 23:59 WIB**; registration closes 7 Oct | Target submission on 7 Oct |
| Every participant completes Sectors onboarding **before** the team writes project code | Each member confirms their onboarding date |
| Each team gets **1,000 Sectors API credits**, claimed on the team page of the hackathon portal after all members finish onboarding; claiming **locks the roster** | The representative claims the credits; credits are for this project during the build period and expire when the event ends |
| Registering extra accounts to get more credits for the same project is grounds for **disqualification** | Only use credits obtained legitimately |
| Sectors must be a **core** data source, not a decorative call; the product must be real, functional and **not faked for the demo** | Phase 4 is mandatory; no mock data in the demo or videos |
| **Data source is restricted to the Sectors API**; AI/LLM APIs may be used in every track (Sectors team on Slack, 16 Sep 2026) | No other market-data sources (no scraping of IDX, Yahoo Finance or news sites). Links in Sectors fields such as a filing's `source` may be shown, but the linked documents are not fetched or parsed. Groq and Gemini are allowed |
| Fictional mock data is used only for automated tests and local development | Mock data mirrors the *shape* of Sectors responses with fictional values; it is never copied from real responses and never used in the demo, videos or deployment |
| AI Agents track: custom agent logic or orchestration and an AI/LLM component are **mandatory**; an off-the-shelf client connected to Sectors MCP with prompts alone does not qualify | Demo with the LLM enabled |
| Working prototype with an end-to-end core workflow; live deployment is **not required** | We deploy anyway (team decision), with the protections listed in Phase 5 |
| No financial advice; position as an information and analysis tool with a disclaimer where relevant; no automated trade execution | Already enforced by the agent's boundary note and guards |
| AI coding tools are fully permitted without disclosure | Our no-AI-attribution convention is a team preference, not a rule |
| Repository created during the build period; judges may inspect commit history | Repository created 2026-09-26; keep meaningful commits |
| Judging weights: real-world usability **40%**, video demo & storytelling **30%**, technical depth & execution **30%** | Reserve real time for the UI and the videos |
| Judging is asynchronous (9–16 Oct) from the video and repository only | The README and videos must explain the product on their own |

### Sectors Credit Budget (estimate)

Assumes one credit per call (documented for at least one endpoint; confirm on the
dashboard after the first calls). Measured with the mock data: discovery on one
sector ≈ 16–21 calls, a four-bank comparison ≈ 8, one company ≈ 4, one full
evaluation run ≈ 95.

| Activity | Credits |
|---|---|
| Phase 4: response-shape checks (once per endpoint) and edge cases | 15–20 |
| Phase 4: first real-data evaluation | ~95 |
| Re-runs after fixes (mostly served from the local cache) | 50–150 |
| Phases 5–6: UI development and end-to-end validation | 150–250 |
| Phase 7: demo rehearsals and recording | 200–300 |
| Reserve for the judging period (deployed product) | ≥ 200 |
| **Total** | **~700–1,100** |

---

## Architecture Direction

### Current

Agent Brain
→ Mock Sectors Adapter
→ Deterministic Analytics
→ Evidence Validator

### Future

Next.js
→ Vercel
→ FastAPI
→ Agent Brain
→ Sectors MCP/REST
→ Deterministic Analytics
→ Evidence Validator
→ LLM Synthesis

---

## Branch Workflow

| Branch | Purpose |
|---|---|
| `main` | Stable, integrated project state |
| `agent-brain` | Intent/entity resolution, planning, discovery, relevance, second-hop decisions, evidence reasoning, LLM prompts, agent state, analytics, agent tests |
| `backend` | FastAPI, API routes, schemas, service layer, configuration, Sectors adapters, backend tests |

Stable work is merged into `main` at milestones. Commits follow
Conventional Commits (`feat(agent): …`, `fix(sectors): …`, `test(...)`, `docs(...)`).

---

## Important Constraints

The project must:

- use Sectors as the core data source
- keep Sectors integration modular
- avoid undocumented Sectors APIs
- maintain evidence traceability
- use deterministic calculations where appropriate
- avoid financial advice
- avoid automated trading
- maintain a clear separation between discovery and analysis
- keep real Sectors data out of the repository (see README → Data handling)
- never expose API keys in the repository, frontend code or logs

---

## Current Boundary

**Currently until Phase 4.**

Phases 5–7 are planned future development.
