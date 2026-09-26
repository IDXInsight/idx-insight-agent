# IDX Insight Agent

An AI research and discovery assistant for Indonesian-listed companies, built on
[Sectors](https://sectors.app/) data for the SECTORS Hackathon 2026
(track: AI Agents & Assistants).

> **Core question:** *What should I pay attention to, and why does it matter?*

## Current Status

**Phase 0 — Repository & Foundation.** The repository, configuration and test
foundation are in place. No agent logic or Sectors integration exists yet.
See [PHASE.md](PHASE.md) for the full roadmap (currently until Phase 3).

## Project Purpose

Investors and analysts following IDX companies face a steady stream of
disclosures, corporate actions and quarterly reports. IDX Insight Agent helps
them decide what deserves attention and provides the factual financial context
behind it — with every claim traceable to Sectors data.

It is a research tool. It does **not** give buy/sell/hold recommendations and
does not trade.

## Product Concept

Our own design, inspired by two concepts from the official hackathon candidate
brief:

- **Discovery** (inspired by Candidate 06): which disclosures/events are relevant
  to my watchlist, sector or timeframe?
- **Contextual analysis** (inspired by Candidate 05): what does the relevant
  financial data show for these companies?

The agent connects them: discover events → decide which matter → decide whether
deeper financial context is justified → retrieve and analyse it → validate the
evidence → explain.

## Agentic Workflow

Planned — see [PHASE.md](PHASE.md), Phase 1.

## Architecture

Planned — see [PHASE.md](PHASE.md), "Architecture Direction".

## Data Source

Sectors (https://docs.sectors.app/). Not yet connected.

## Mock vs Real Sectors Integration

Development uses deterministic mock data behind an adapter interface. Real
Sectors integration is Phase 4.

## Implemented Features

- Environment-driven configuration (`backend/idx_insight/config.py`)
- pytest foundation

## Testing

```bash
python -m venv .venv
.venv/Scripts/pip install -e "backend[dev]"   # Windows; use .venv/bin/pip on macOS/Linux
cd backend && ../.venv/Scripts/python -m pytest -q
```

## Known Limitations

Everything beyond the foundation is not implemented yet.

## Remaining Work

Phases 1–7 in [PHASE.md](PHASE.md).
