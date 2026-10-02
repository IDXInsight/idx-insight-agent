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
- The proxy sends the shared secret (`X-Internal-Key`) and the visitor's IP
  (`X-Client-IP`, read from the headers Vercel sets itself) so the backend can reject
  direct calls and limit runs per visitor. Backend limits come back as `rate_limited` or
  `daily_limit` and are explained in the UI (`lib/proxy.ts`).
- `next.config.ts` sets security headers on every page: a same-origin Content Security
  Policy, `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy and a
  permissions policy.
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
| `IDX_INSIGHT_API_SECRET` | server | shared secret, same value as on the backend |
| `AGENT_TIMEOUT_MS` | server | timeout for one agent run (default 110000) |
| `NEXT_PUBLIC_SITE_URL` | public | absolute site URL for social preview images |

No Sectors or LLM key is ever needed by the frontend.

## Status

Done:
- Workspace connected to the agent API through the server-side proxy; results,
  findings, peer table, disclosure radar, evidence explorer and agent trace come from the
  real response
- Example mode with clearly labelled illustrative data when no backend is configured
- Shared secret and visitor IP sent to the backend; backend limits shown as
  `rate_limited` or `daily_limit`
- Security headers on every page
- Deployed at https://idx-insight.vercel.app (Production uses the real backend)

Not yet done:
- The watchlist offers four banks (BBCA, BBRI, BMRI, BBNI); the API accepts any IDX ticker
  (up to 20, four letters each)
- No progress feedback while the agent runs; a new question takes 4–6 s on real data
- The proxy always asks for Indonesian (`language: "id"`), so English questions are
  answered in Indonesian; the UI labels are Indonesian only
- The Vercel Firewall rate limit (10 requests per minute per IP on `/api/agent/query`)
  answers 429 with its own body (`{"error": {"code": "429", ...}}`); the UI then shows the
  generic backend error instead of the rate-limit message
- The response has no multi-period series, so connected mode shows no historical chart
- `app/page.tsx` holds most of the UI in one file; mobile layout not reviewed
- Any external resource (fonts, images, scripts from another domain) needs a matching
  change to the Content Security Policy in `next.config.ts`

## Preview deployments

Branch pushes create Preview deployments. Set `IDX_INSIGHT_API_URL` for **Production
only** in the Vercel project, so previews run in example mode instead of calling the
production backend with real data (which spends Sectors credits).
