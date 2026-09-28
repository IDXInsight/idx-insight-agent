# IDX Insight — design prototype

Interactive dark UI for the existing IDX Insight Agent. All numbers, event dates and results are synthetic design examples. No backend or market APIs are called; no credentials are required.

## Local preview

```sh
npm ci
npm run dev
```

The dev server prints the local URL. `npm run build` creates the production build. `npx tsc --noEmit` checks TypeScript.

## Structure

- `app/page.tsx`: research workspace, disclosure briefing, peer comparison, company context, evidence and trace drawers.
- `app/globals.css`: charcoal/mint design tokens and responsive layout.
- `components/ui/v-chart-4.tsx`: the supplied Recharts line-chart pattern adapted to financial periods, selectable series, units and tooltips.
- `components/ui/chart.tsx`: supplied shadcn chart primitives, with zero-value tooltip support corrected.
- `components.json`: shadcn paths (`@/components/ui`) and Tailwind configuration.

The scaffold uses React, TypeScript, Tailwind v4 and vinext (Next.js-compatible routing) for Sites preview. The existing FastAPI backend remains separate. No configuration from the parent `.env` is used.

## Interaction scope

Navigation, prompt selection, input validation, watchlist selection, event filters, chart metrics/series, and accessible detail dialogs work locally. “Lihat contoh riset” explicitly opens a synthetic example; free text is not analyzed. Watchlist and results are in memory and reset on refresh. Dates in sample results remain fixed regardless of the selected input period.

## Backend integration to do

Connect the research form to `/v1/agent/query`, render accepted claims/evidence/status from the real response and remove synthetic results from live mode. The backend response does not currently expose the multi-year series used in the chart; add a documented data contract before displaying live historical charts. Streamed progress is not implemented. Keep API keys server-side. Show actual observation periods, request timestamps, source links and cache freshness only when available from the backend.
