# IDX Insight — frontend

Next.js (App Router) research workspace for the IDX Insight Agent: research box,
disclosure radar, peer comparison with small-multiple charts, findings, evidence
explorer, agent trace and a research history. Deployment target: Vercel.

## What the UI shows

Everything on screen comes from the agent's responses. There is no illustrative or
synthetic data.

| State | When | What the UI shows |
|---|---|---|
| **Connected** | `IDX_INSIGHT_API_URL` is set and the backend answers `/v1/capabilities` | Questions go to the agent; results, evidence and trace come from the real response. The label says "data Sectors" or "data mock" |
| **Backend offline** | no backend configured or reachable | "Backend mati, hubungi tim untuk menyalakan lagi." The research box is disabled; results already in the history can still be opened |

## Features

- **Research box**: the research type (disclosure, comparison, company) is detected
  while typing and highlighted; the backend still decides. The tabs load an example
  question for each type. The line under the box shows the scope that will be sent.
- **Watchlist**: any IDX tickers (up to 20, four letters), saved in the browser. It is
  sent only when the question names no ticker or sector, because the backend researches
  every watchlist ticker (`lib/research.ts`). Clicking a ticker prepares a company
  question without running it.
- **Research history**: every result is kept in the browser (latest 12, one per
  question and language) and reopened without a new API call. The sidebar views
  (Disclosure, Peer lens, Company context) open the latest result of that type.
- **Language**: ID/EN toggle. The question is sent with that language, so the briefing
  and the interface match; a saved result keeps the language it was asked in.
- **Peer chart**: one column chart per metric, sorted by the direction the backend
  reports as usually favourable, with the peer median as a dashed line. Each company
  keeps one colour across the watchlist, charts and tables (`lib/palette.ts`, validated
  for contrast and colour-blind separation on the dark surface).
- **Company marks**: Sectors provides no company logos, so a company is shown as its
  ticker in its chart colour (`components/ticker-mark.tsx`).
- Progress while the agent runs (elapsed seconds), and every proxy error, including the
  Vercel Firewall's own 429 body, is explained in the chosen language.

## Local development

```sh
npm ci
cp .env.example .env.local        # set IDX_INSIGHT_API_URL=http://127.0.0.1:8000
npm run dev
```

Start the backend separately (see the root README). For UI work without spending
Sectors credits, run it with `SECTORS_DATA_MODE=mock LLM_PROVIDER=none`; the UI then
labels results as mock data.

Checks: `npm run typecheck`, `npm run lint`, `npm run build`, `npm test` (after a build).

## Architecture

- The browser never calls the backend directly. `app/api/agent/status` and
  `app/api/agent/query` are server-side route handlers that validate input (question,
  tickers, `language` = `id` or `en`) and forward to FastAPI, so the backend URL stays
  server-side and no CORS setup is needed.
- The proxy sends the shared secret (`X-Internal-Key`) and the visitor's IP
  (`X-Client-IP`, read from the headers Vercel sets itself) so the backend can reject
  direct calls and limit runs per visitor (`lib/proxy.ts`).
- `next.config.ts` sets security headers on every page: a same-origin Content Security
  Policy, `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy and a
  permissions policy.
- `lib/i18n.ts` holds every user-facing string in Indonesian and English.
- `lib/agent.ts` mirrors the response contract of `POST /v1/agent/query`
  (`backend/idx_insight/api/schemas.py`) and holds the display helpers.
- `lib/research.ts` holds the client-side rules: tickers in a question, when the
  watchlist is sent, the research-type preview (mirrors `agent/intent.py`), ticker
  input and the browser history. Storage failures fall back to defaults.
- `components/live-result.tsx` renders a response; it only shows what the backend
  returned (accepted claims, their evidence, data gaps, assumptions and the boundary
  note). `components/peer-chart.tsx` draws the small multiples.

## Environment variables

| Variable | Scope | Purpose |
|---|---|---|
| `IDX_INSIGHT_API_URL` | server | FastAPI base URL; empty = backend offline |
| `IDX_INSIGHT_API_SECRET` | server | shared secret, same value as on the backend |
| `AGENT_TIMEOUT_MS` | server | timeout for one agent run (default 110000) |
| `NEXT_PUBLIC_SITE_URL` | public | absolute site URL for social preview images |

No Sectors or LLM key is ever needed by the frontend.

## Status

Done:
- Workspace connected to the agent API through the server-side proxy
- Free-ticker watchlist, research history, research-type detection, ID/EN toggle
- Small-multiple peer chart; company colours shared by watchlist, charts and tables
- Clear offline state instead of example data
- Progress feedback and localized error messages, including the firewall's 429
- Security headers on every page
- Deployed at https://idx-insight.vercel.app (Production uses the real backend)

Not yet done:
- The response has no multi-period series, so there is no historical (trend) chart
- History is per browser; there are no accounts and nothing is shared between devices
- `app/page.tsx` still holds most of the workspace in one file
- Any external resource (fonts, images, scripts from another domain) needs a matching
  change to the Content Security Policy in `next.config.ts`

## Preview deployments

Branch pushes create Preview deployments. Set `IDX_INSIGHT_API_URL` for **Production
only** in the Vercel project, so previews show the offline state instead of calling the
production backend with real data (which spends Sectors credits).
