# IDX Insight — frontend

Next.js (App Router) research workspace for the IDX Insight Agent: query form,
disclosure radar, peer comparison, findings, evidence explorer and agent trace.
Deployment target: Vercel.

## Modes

| Mode | When | What the UI shows |
|---|---|---|
| **Connected** | `IDX_INSIGHT_API_URL` is set and the backend answers `/v1/capabilities` | "Jalankan riset" sends the question to the agent; results, evidence and trace come from the real response |
| **Example** | no backend configured or reachable | the original design prototype: "Lihat contoh riset" opens synthetic example results, clearly labelled as illustrative |

In connected mode, the example screens stay available from the navigation and remain
labelled as examples; the synthetic chart is never mixed into a real result.

## Local development

```sh
npm ci
cp .env.example .env.local        # set IDX_INSIGHT_API_URL, or leave empty for example mode
npm run dev
```

Start the backend separately (see the root README). For UI work without spending
Sectors credits, run it with `SECTORS_DATA_MODE=mock LLM_PROVIDER=none`; the UI then
labels results as mock data.

Checks: `npm run typecheck`, `npm run lint`, `npm run build`, `npm test` (after a build).

## Architecture

- The browser never calls the backend directly. `app/api/agent/status` and
  `app/api/agent/query` are server-side route handlers that validate input and forward
  to FastAPI, so the backend URL stays server-side and no CORS setup is needed.
- `lib/agent.ts` mirrors the response contract of `POST /v1/agent/query`
  (`backend/idx_insight/api/schemas.py`) and holds the display helpers.
- `components/live-result.tsx` renders a real response with the prototype's panels;
  it only shows what the backend returned (accepted claims, their evidence, data gaps,
  assumptions and the boundary note).
- `app/page.tsx` is the workspace; `components/ui/v-chart-4.tsx` is the illustrative
  chart used in example mode only.

## Environment variables

| Variable | Scope | Purpose |
|---|---|---|
| `IDX_INSIGHT_API_URL` | server | FastAPI base URL; empty = example mode |
| `AGENT_TIMEOUT_MS` | server | timeout for one agent run (default 110000) |
| `NEXT_PUBLIC_SITE_URL` | public | absolute site URL for social preview images |

No Sectors or LLM key is ever needed by the frontend.

## Not yet done

- The UI is Indonesian only; the agent also answers in English.
- The response has no multi-period series, so connected mode shows no historical chart.
- Deployment protections from PHASE.md Phase 5 (per-day caps, rate limiting,
  persistent cache and credit ledger) are not implemented yet.
- Streamed progress while the agent runs.
