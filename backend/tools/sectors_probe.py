"""One-off probe of real Sectors v2 response shapes (spends a few credits).

    cd backend && python -m tools.sectors_probe            # shows the plan, spends nothing
    cd backend && python -m tools.sectors_probe --run      # performs the calls

Each probe goes through the credit ledger, caps and the local cache, so running
it twice does not spend credits twice. Responses are recorded in the git-ignored
``backend/.sectors_local/`` and summarised here as structure (keys and types).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from typing import Any

from idx_insight.config import Settings, load_env_file
from idx_insight.sectors.adapter import SectorsError
from idx_insight.sectors.credits import CreditLedger, max_cost
from idx_insight.sectors.http_client import SectorsHttpClient


def probes(today: date) -> list[tuple[str, str, dict[str, Any]]]:
    next_monday = today + timedelta(days=7 - today.weekday())
    return [
        ("subsectors", "/v2/subsectors/", {}),
        ("screener banks + metrics", "/v2/companies/", {
            "where": ("sub_sector = 'Banks' and roe[2025] > -100 and net_interest_margin[2025] > -100 "
                      "and earnings_q[Q2-2026] > -1000000000000000"),
            "order_by": "-market_cap", "limit": 5, "include_query_values": "true"}),
        ("corporate-actions calendar", "/v2/corporate-actions/", {
            "type": "agm,dividend,stock_split", "start": next_monday.isoformat(),
            "end": (next_monday + timedelta(days=6)).isoformat()}),
        ("filings banks", "/v2/filings/", {
            "sub_sector": "banks", "start": (today - timedelta(days=14)).isoformat(),
            "end": today.isoformat(), "limit": 30}),
        ("company report financials", "/v2/company/report/BBCA/", {"sections": "financials"}),
        ("quarterly financials latest", "/v2/financials/quarterly/BBCA/", {"n_quarters": 1}),
    ]


def shape(value: Any, depth: int = 0, max_depth: int = 4) -> str:
    pad = "  " * depth
    if isinstance(value, dict):
        if depth >= max_depth:
            return "{…}"
        lines = [f"{pad}  {k}: {shape(v, depth + 1).lstrip()}" for k, v in list(value.items())[:25]]
        more = f"\n{pad}  … {len(value) - 25} more keys" if len(value) > 25 else ""
        return "{\n" + "\n".join(lines) + more + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[] (empty)"
        return f"[{len(value)} items] of " + shape(value[0], depth, max_depth).lstrip()
    return type(value).__name__ + (f" = {value!r}" if isinstance(value, (int, float, bool)) or
                                   (isinstance(value, str) and len(value) <= 24) else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Sectors v2 response shapes")
    parser.add_argument("--run", action="store_true", help="actually call the API")
    args = parser.parse_args(argv)

    load_env_file()
    s = Settings.from_env()
    plan = probes(date.today())
    print(f"Planned probes (worst case {sum(max_cost(p, q) for _, p, q in plan)} credits):")
    for name, path, params in plan:
        print(f"  - {name}: {path} {params} → ≤{max_cost(path, params)} credit(s)")
    if not args.run:
        print("\nDry run only. Re-run with --run to call the API.")
        return 0

    ledger = CreditLedger(s.sectors_local_dir / "ledger.json",
                          max_per_day=s.sectors_max_credits_per_day,
                          max_total=s.sectors_max_credits_total)
    key = s.sectors_api_key.get_secret_value() if s.sectors_api_key else ""
    client = SectorsHttpClient(api_key=key, ledger=ledger, cache_dir=s.sectors_local_dir / "cache",
                               cache_mode=s.sectors_cache_mode)
    before = ledger.total
    for name, path, params in plan:
        print(f"\n=== {name}")
        try:
            print(shape(client.get(path, params)))
        except SectorsError as exc:
            print(f"ERROR {type(exc).__name__}: {exc}")
    print(f"\nCredits recorded by this run: {ledger.total - before} "
          f"(ledger total {ledger.total}, today {ledger.today()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
