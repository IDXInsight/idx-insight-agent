"""Deterministic mock fixtures shaped like documented Sectors responses.

All numbers are fictional except BBCA 2026-03-31, which reuses the example in the
Sectors quarterly-financials documentation. Holder names are fictional.

Deliberate edge cases (tests rely on these):
- BBTN has no 2026-06-30 quarter (late report → period alignment).
- BRIS 2026-06-30 lacks ``financials_sector_metrics`` (incomplete report).
- BBNI ratios are expressed in percent, not fractions (inconsistent units).
- BRIS / BTPS have no ``casa_ratio`` (unsupported metric for that company).
- BTPS only has 2024 ratios (stale / unavailable period).
- BMRI report ``yoy_quarter_earnings_growth`` disagrees with its quarterly
  financials (contradictory values).
- BMRI has a duplicated filing (duplicate events).
- BTPS has no corporate actions at all (empty result).
- "bank syariah" matches two companies (ambiguous entity).
"""

from __future__ import annotations

T = 1_000_000_000_000  # one trillion IDR
B = 1_000_000_000  # one billion IDR

SUBSECTORS = {
    "banks": "financials",
    "telecommunication": "infrastructures",
}

COMPANIES = {
    "BBCA": {"company_name": "Bank Central Asia Tbk.", "sub_sector": "banks"},
    "BBRI": {"company_name": "Bank Rakyat Indonesia (Persero) Tbk.", "sub_sector": "banks"},
    "BMRI": {"company_name": "Bank Mandiri (Persero) Tbk.", "sub_sector": "banks"},
    "BBNI": {"company_name": "Bank Negara Indonesia (Persero) Tbk.", "sub_sector": "banks"},
    "BBTN": {"company_name": "Bank Tabungan Negara (Persero) Tbk.", "sub_sector": "banks"},
    "BRIS": {"company_name": "Bank Syariah Indonesia Tbk.", "sub_sector": "banks"},
    "BTPS": {"company_name": "Bank BTPN Syariah Tbk.", "sub_sector": "banks"},
    "TLKM": {"company_name": "Telkom Indonesia (Persero) Tbk.", "sub_sector": "telecommunication"},
}

# (date, revenue, earnings, total_assets, total_equity, nii, gross_loan, total_deposit)
_Q = tuple[str, float, float, float, float, float | None, float | None, float | None]

_QUARTERS: dict[str, list[_Q]] = {
    "BBCA": [
        ("2025-06-30", 27.1 * T, 14.2 * T, 1585 * T, 250 * T, 20.2 * T, 930 * T, 1230 * T),
        ("2025-09-30", 27.6 * T, 14.4 * T, 1600 * T, 255 * T, 20.6 * T, 945 * T, 1245 * T),
        ("2025-12-31", 28.0 * T, 14.5 * T, 1620 * T, 262 * T, 20.9 * T, 960 * T, 1262 * T),
        ("2026-03-31", 28434118000000, 14695475000000, 1640830566000000, 259358793000000,
         21108433000000, 970701203000000, 1276408911000000),
        ("2026-06-30", 29.0 * T, 15.1 * T, 1655 * T, 268 * T, 21.5 * T, 985 * T, 1290 * T),
    ],
    "BBRI": [
        ("2025-06-30", 52.0 * T, 14.8 * T, 2050 * T, 310 * T, 36.0 * T, 1390 * T, 1520 * T),
        ("2025-09-30", 53.0 * T, 14.3 * T, 2080 * T, 318 * T, 36.5 * T, 1410 * T, 1540 * T),
        ("2025-12-31", 53.5 * T, 14.9 * T, 2110 * T, 325 * T, 36.8 * T, 1430 * T, 1565 * T),
        ("2026-03-31", 54.0 * T, 13.6 * T, 2120 * T, 322 * T, 37.0 * T, 1440 * T, 1580 * T),
        ("2026-06-30", 54.5 * T, 13.2 * T, 2140 * T, 330 * T, 37.1 * T, 1455 * T, 1600 * T),
    ],
    "BMRI": [
        ("2025-06-30", 40.0 * T, 12.9 * T, 2300 * T, 290 * T, 26.0 * T, 1550 * T, 1650 * T),
        ("2025-09-30", 41.0 * T, 13.3 * T, 2350 * T, 298 * T, 26.5 * T, 1590 * T, 1690 * T),
        ("2025-12-31", 42.0 * T, 14.1 * T, 2420 * T, 305 * T, 27.0 * T, 1640 * T, 1720 * T),
        ("2026-03-31", 42.5 * T, 13.2 * T, 2450 * T, 300 * T, 27.3 * T, 1660 * T, 1745 * T),
        ("2026-06-30", 43.0 * T, 13.8 * T, 2480 * T, 309 * T, 27.8 * T, 1690 * T, 1770 * T),
    ],
    "BBNI": [
        ("2025-06-30", 18.0 * T, 5.3 * T, 1100 * T, 160 * T, 10.2 * T, 780 * T, 820 * T),
        ("2025-09-30", 18.3 * T, 5.4 * T, 1120 * T, 163 * T, 10.3 * T, 790 * T, 835 * T),
        ("2025-12-31", 18.6 * T, 5.5 * T, 1140 * T, 166 * T, 10.5 * T, 805 * T, 850 * T),
        ("2026-03-31", 18.8 * T, 5.1 * T, 1150 * T, 165 * T, 10.4 * T, 812 * T, 860 * T),
        ("2026-06-30", 19.0 * T, 5.6 * T, 1165 * T, 169 * T, 10.6 * T, 820 * T, 870 * T),
    ],
    "BBTN": [
        ("2025-06-30", 7.2 * T, 0.75 * T, 460 * T, 30.0 * T, 4.1 * T, 340 * T, 370 * T),
        ("2025-09-30", 7.3 * T, 0.80 * T, 465 * T, 31.0 * T, 4.2 * T, 345 * T, 375 * T),
        ("2025-12-31", 7.5 * T, 0.70 * T, 470 * T, 31.5 * T, 4.3 * T, 350 * T, 380 * T),
        ("2026-03-31", 7.6 * T, 0.82 * T, 478 * T, 32.0 * T, 4.4 * T, 355 * T, 386 * T),
    ],
    "BRIS": [
        ("2025-06-30", 9.5 * T, 1.80 * T, 400 * T, 50.0 * T, 5.9 * T, 280 * T, 320 * T),
        ("2025-09-30", 9.7 * T, 1.85 * T, 410 * T, 51.5 * T, 6.0 * T, 286 * T, 327 * T),
        ("2025-12-31", 9.9 * T, 1.90 * T, 420 * T, 53.0 * T, 6.1 * T, 292 * T, 335 * T),
        ("2026-03-31", 10.1 * T, 2.00 * T, 428 * T, 54.0 * T, 6.2 * T, 298 * T, 340 * T),
        ("2026-06-30", 10.3 * T, 2.10 * T, 436 * T, 55.5 * T, None, None, None),
    ],
    "BTPS": [
        ("2025-12-31", 1.60 * T, 0.27 * T, 22.0 * T, 9.0 * T, 1.30 * T, 12.0 * T, 14.0 * T),
        ("2026-03-31", 1.62 * T, 0.28 * T, 22.4 * T, 9.2 * T, 1.31 * T, 12.2 * T, 14.3 * T),
        ("2026-06-30", 1.65 * T, 0.29 * T, 22.9 * T, 9.4 * T, 1.33 * T, 12.4 * T, 14.6 * T),
    ],
    "TLKM": [
        ("2026-03-31", 37.0 * T, 5.9 * T, 290 * T, 150 * T, None, None, None),
        ("2026-06-30", 37.4 * T, 6.1 * T, 293 * T, 153 * T, None, None, None),
    ],
}

_BANKING = {"BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BTPS"}


def quarterly_financials(symbol: str) -> list[dict]:
    rows = []
    for date, rev, earn, assets, equity, nii, loan, deposit in _QUARTERS.get(symbol, []):
        row: dict = {
            "symbol": f"{symbol}.JK",
            "date": date,
            "revenue": rev,
            "earnings": earn,
            "total_assets": assets,
            "total_equity": equity,
            "total_liabilities": assets - equity,
            "stockholders_equity": equity,
        }
        if symbol in _BANKING and nii is not None:
            row["financials_sector_metrics"] = {
                "net_interest_income": nii,
                "gross_loan": loan,
                "total_deposit": deposit,
            }
        rows.append(row)
    return rows


# year -> (roa, roe, nim, cost_to_income, casa, ldr, car)
_RATIOS: dict[str, dict[int, tuple]] = {
    "BBCA": {2024: (0.038, 0.244, 0.057, 0.310, 0.81, 0.75, 0.29),
             2025: (0.036, 0.235, 0.058, 0.305, 0.82, 0.76, 0.29)},
    "BBRI": {2024: (0.031, 0.195, 0.078, 0.400, 0.65, 0.89, 0.26),
             2025: (0.029, 0.180, 0.074, 0.420, 0.64, 0.92, 0.25)},
    "BMRI": {2024: (0.029, 0.220, 0.052, 0.360, 0.75, 0.91, 0.21),
             2025: (0.027, 0.210, 0.051, 0.370, 0.74, 0.95, 0.20)},
    # Percent units on purpose (inconsistent units edge case).
    "BBNI": {2024: (2.0, 14.5, 4.4, 41.0, 71.0, 90.0, 22.0),
             2025: (1.9, 13.8, 4.2, 42.5, 70.1, 94.3, 21.0)},
    "BBTN": {2024: (0.008, 0.100, 0.034, 0.570, 0.48, 0.93, 0.19),
             2025: (0.007, 0.095, 0.033, 0.580, 0.47, 0.92, 0.19)},
    "BRIS": {2024: (0.020, 0.165, 0.057, 0.470, None, 0.85, 0.21),
             2025: (0.021, 0.170, 0.056, 0.460, None, 0.86, 0.21)},
    "BTPS": {2024: (0.050, 0.110, 0.200, 0.600, None, 0.85, 0.45)},
    "TLKM": {2025: (0.090, 0.160, None, None, None, None, None)},
}

_REPORT_YOY_EARNINGS = {
    "BBCA": 0.063,
    "BBRI": -0.108,
    "BMRI": 0.12,  # contradicts quarterly data (+7.0%) on purpose
    "BBNI": 0.057,
    "BRIS": 0.167,
}

_OVERVIEW = {
    "BBCA": {"market_cap": 1_150 * T, "last_close_price": 9_300},
    "BBRI": {"market_cap": 620 * T, "last_close_price": 4_100},
    "BMRI": {"market_cap": 510 * T, "last_close_price": 5_450},
    "BBNI": {"market_cap": 165 * T, "last_close_price": 4_420},
    "BBTN": {"market_cap": 17 * T, "last_close_price": 1_210},
    "BRIS": {"market_cap": 125 * T, "last_close_price": 2_720},
    "BTPS": {"market_cap": 8 * T, "last_close_price": 1_050},
    "TLKM": {"market_cap": 300 * T, "last_close_price": 3_030},
}


def company_report(symbol: str) -> dict:
    info = COMPANIES[symbol]
    ratios = []
    for year, values in sorted(_RATIOS.get(symbol, {}).items()):
        roa, roe, nim, cir, casa, ldr, car = values
        ratios.append({
            "year": year,
            "profitability": {"roa": roa, "roe": roe, "net_interest_margin": nim,
                              "cost_to_income_ratio": cir},
            "liquidity": {"casa_ratio": casa, "loan_to_deposit_ratio": ldr},
            "capital": {"capital_adequacy_ratio": car},
        })
    return {
        "symbol": f"{symbol}.JK",
        "company_name": info["company_name"],
        "overview": {
            "sector": SUBSECTORS[info["sub_sector"]],
            "sub_sector": info["sub_sector"],
            "listing_board": "Main",
            "latest_close_date": "2026-09-25",
            **_OVERVIEW[symbol],
        },
        "financials": {
            "historical_financial_ratio": ratios,
            "yoy_quarter_earnings_growth": _REPORT_YOY_EARNINGS.get(symbol),
        },
    }


CORPORATE_ACTIONS: dict[str, dict] = {
    "BBCA": {
        "agm": [{"agm_date": "2026-03-12", "agm_time": "09:30:00",
                 "agm_place": "Jakarta", "agm_result": None}],
        "dividend": [
            {"ex_date": "2025-12-03", "payment_date": "2025-12-22",
             "dividend_yield": 0.0064, "dividend_amount": 55},
            {"ex_date": "2026-03-25", "payment_date": "2026-04-15",
             "dividend_yield": 0.0270, "dividend_amount": 250},
            {"ex_date": "2026-12-02", "payment_date": "2026-12-21",
             "dividend_yield": 0.0059, "dividend_amount": 55},
        ],
        "stock_split": [{"date": "2021-10-13", "split_ratio": 5}],
    },
    "BBRI": {
        "agm": [
            {"agm_date": "2026-03-24", "agm_time": "14:00:00", "agm_place": "Jakarta",
             "agm_result": None},
            {"agm_date": "2026-10-01", "agm_time": "10:00:00", "agm_place": "Jakarta",
             "agm_result": None},
        ],
        "dividend": [
            {"ex_date": "2026-10-02", "payment_date": "2026-10-20",
             "dividend_yield": 0.0330, "dividend_amount": 135},
        ],
    },
    "BMRI": {
        "agm": [{"agm_date": "2026-03-10", "agm_time": "14:00:00", "agm_place": "Jakarta",
                 "agm_result": None}],
        "dividend": [{"ex_date": "2026-03-20", "payment_date": "2026-04-08",
                      "dividend_yield": 0.0610, "dividend_amount": 333}],
    },
    "BBNI": {
        "agm": [{"agm_date": "2026-09-30", "agm_time": "14:00:00", "agm_place": "Jakarta",
                 "agm_result": None}],
        "dividend": [{"ex_date": "2026-03-27", "payment_date": "2026-04-17",
                      "dividend_yield": 0.0810, "dividend_amount": 356}],
    },
    "BBTN": {
        "agm": [{"agm_date": "2026-03-19", "agm_time": "09:00:00", "agm_place": "Jakarta",
                 "agm_result": None}],
    },
    "BRIS": {
        "dividend": [{"ex_date": "2026-10-02", "payment_date": "2026-10-16",
                      "dividend_yield": 0.0044, "dividend_amount": 12}],
    },
    "BTPS": {},
    "TLKM": {
        "agm": [{"agm_date": "2026-09-29", "agm_time": "14:00:00", "agm_place": "Jakarta",
                 "agm_result": None}],
    },
}

_IDX = "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_KSEI/"


def _filing(symbol, ts, ttype, htype, holder, before, after, amount, price, sub="banks",
            source_id=None):
    value = amount * price
    return {
        "title": f"{holder} {'buys' if ttype == 'buy' else 'sells'} shares of "
                 f"{COMPANIES[symbol]['company_name']}",
        "body": f"{holder} {'increased' if ttype == 'buy' else 'decreased'} ownership "
                f"from {before:.2f}% to {after:.2f}%.",
        "source": f"{_IDX}{source_id or symbol + ts[:10].replace('-', '')}.pdf",
        "timestamp": ts,
        "sector": SUBSECTORS[sub],
        "sub_sector": sub,
        "tags": [],
        "symbol": f"{symbol}.JK",
        "transaction_type": ttype,
        "holder_type": htype,
        "holder_name": holder,
        "amount_transaction": amount,
        "price": price,
        "transaction_value": value,
        "share_percentage_before": before,
        "share_percentage_after": after,
        "share_percentage_transaction": round(abs(after - before), 4),
    }


FILINGS: list[dict] = [
    _filing("BMRI", "2026-09-22T16:05:00", "buy", "insider", "Direksi BMRI (mock)",
            0.0010, 0.0035, 460_000, 5_430, source_id="LK-22092026-BMRI-01"),
    # Exact duplicate delivered twice by the feed.
    _filing("BMRI", "2026-09-22T16:05:00", "buy", "insider", "Direksi BMRI (mock)",
            0.0010, 0.0035, 460_000, 5_430, source_id="LK-22092026-BMRI-01"),
    _filing("BBTN", "2026-09-24T17:40:00", "sell", "institution", "Mock Asset Management",
            6.40, 5.10, 182_000_000, 1_200),
    _filing("BBRI", "2026-09-18T15:20:00", "buy", "corporate-investor", "PT Mock Investama",
            1.10, 1.45, 530_000_000, 4_080),
    _filing("BRIS", "2026-09-15T11:00:00", "buy", "institution", "Mock Pension Fund",
            0.80, 0.85, 23_000_000, 2_700),
    _filing("BBNI", "2026-09-25T18:10:00", "buy", "institution", "Mock Sovereign Fund",
            2.30, 3.35, 196_000_000, 4_400),
    _filing("BBCA", "2026-08-20T10:30:00", "sell", "insider", "Komisaris BBCA (mock)",
            0.0200, 0.0150, 6_100_000, 9_250),
    _filing("TLKM", "2026-09-20T09:00:00", "buy", "institution", "Mock Asset Management",
            1.00, 1.60, 594_000_000, 3_000, sub="telecommunication"),
]
