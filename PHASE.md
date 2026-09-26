# IDX Insight Agent — Development Phases

## Project Status

**Currently until Phase 3**

This document describes the complete project roadmap.
Future phases are documented for planning and team coordination.

| Phase | Name | Status |
|---|---|---|
| 0 | Repository & Foundation | Implemented |
| 1 | Agent Brain | Implemented (mock data) |
| 2 | Backend Foundation | Implemented (mock data) |
| 3 | Analytics & Validation | Implemented (mock data) |
| 4 | Real Sectors Integration | Planned |
| 5 | Product UI | Planned |
| 6 | End-to-End Validation | Planned |
| 7 | Demo & Submission Preparation | Planned |

Hackathon: SECTORS Hackathon 2026 — Track: AI Agents & Assistants.
Deadline: 8 October 2026, 23:59 WIB.

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
- Sectors MCP/REST adapter
- authentication
- real response mapping
- integration tests
- error handling

### Dependency
Official Sectors API/MCP access and verified documentation.

### Expected Outcome
The same agent runs unchanged against real Sectors data by switching
`SECTORS_DATA_MODE`.

### Complete When
- a real adapter implements the existing `SectorsAdapter` interface
- open questions recorded in the codebase (e.g. company listing shape, upcoming report dates) are resolved against official documentation

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
Vercel

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

### Dependencies
Phase 6.

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

---

## Current Boundary

**Currently until Phase 3.**

Phases 4–7 are planned future development.
