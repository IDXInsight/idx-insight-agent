"""Discovery Agent: collect and normalise disclosures and corporate actions."""

from __future__ import annotations

from datetime import date, timedelta

from idx_insight.agent.recovery import record_tool_failure
from idx_insight.agent.state import AgentState, RecoveryAction
from idx_insight.analytics.events import event_id
from idx_insight.analytics.numbers import fmt_idr
from idx_insight.models import Event
from idx_insight.sectors.schemas import CorporateActions, Filing, bare_symbol
from idx_insight.sectors.service import SectorsService

MAX_SCOPE_COMPANIES = 12
MAX_FILING_PAGES = 3
FILINGS_PAGE_LIMIT = 30  # documented maximum for /v2/filings/
WIDENED_LOOKBACK_DAYS = 30


class DiscoveryAgent:
    def __init__(self, service: SectorsService, state: AgentState, max_requeries: int) -> None:
        self.service = service
        self.state = state
        self.max_requeries = max_requeries
        self.names: dict[str, str] = {}

    # -- scope -----------------------------------------------------------------

    def scope(self, members: list[tuple[str, str | None]]) -> list[str]:
        symbols = []
        for symbol, name in members:
            if name:
                self.names[symbol] = name
            symbols.append(symbol)
        symbols = list(dict.fromkeys(symbols))
        if len(symbols) > MAX_SCOPE_COMPANIES:
            self.state.add_gap(
                "scope_truncated",
                f"Cakupan {len(symbols)} emiten dibatasi ke {MAX_SCOPE_COMPANIES} pertama "
                "untuk menjaga jumlah tool call.",
            )
            symbols = symbols[:MAX_SCOPE_COMPANIES]
        return symbols

    # -- collection ------------------------------------------------------------

    def collect(self, symbols: list[str], sub_sector: str | None) -> list[Event]:
        tf = self.state.timeframe
        assert tf is not None
        events: list[Event] = []
        filings = self._filings(symbols, sub_sector, tf.filings_start, tf.filings_end)
        if not filings and self._can_requery() and tf.direction != "backward":
            widened = tf.filings_end - timedelta(days=WIDENED_LOOKBACK_DAYS)
            self.state.requeries_used += 1
            filings = self._filings(symbols, sub_sector, widened, tf.filings_end)
            self.state.recovery.append(RecoveryAction(
                trigger="empty_result", target="fetch-filings",
                action=f"Perlebar jendela filing ke {WIDENED_LOOKBACK_DAYS} hari terakhir (sekali)",
                outcome=f"{len(filings)} filing ditemukan",
            ))
            if filings:
                self.state.assumptions.append(
                    f"Jendela filing diperlebar ke {widened} s/d {tf.filings_end} karena "
                    "jendela awal kosong."
                )
        in_scope = set(symbols)
        for call_id, filing in filings:
            sym = bare_symbol(filing.symbol)
            if in_scope and sym not in in_scope:
                continue
            events.append(self._filing_event(call_id, filing))

        for sym in symbols:
            result = self.service.corporate_actions(sym)
            if not result.ok or result.data is None:
                record_tool_failure(self.state, f"aksi korporasi {sym}", result.status, sym)
                continue
            events.extend(self._corporate_events(result.call_id, result.data, tf.start, tf.end))

        self.state.add_gap(
            "unsupported_capability",
            "Sectors tidak mendokumentasikan jadwal rilis laporan keuangan mendatang; "
            "hanya tanggal laporan yang sudah terbit yang tersedia.",
        )
        return events

    def _can_requery(self) -> bool:
        return self.state.requeries_used < self.max_requeries

    def _filings(self, symbols: list[str], sub_sector: str | None, start: date,
                 end: date) -> list[tuple[str, Filing]]:
        out: list[tuple[str, Filing]] = []
        queries = [{"sub_sector": sub_sector}] if sub_sector else [{"symbol": s} for s in symbols]
        for query in queries:
            offset = 0
            for _ in range(MAX_FILING_PAGES):
                result = self.service.filings(start=start.isoformat(), end=end.isoformat(),
                                              limit=FILINGS_PAGE_LIMIT, offset=offset, **query)
                if not result.ok or result.data is None:
                    record_tool_failure(self.state, f"filing {next(iter(query.values()))}",
                                        result.status)
                    break
                out.extend((result.call_id, f) for f in result.data.results)
                if not result.data.pagination.has_next:
                    break
                offset = result.data.pagination.next_offset or offset + FILINGS_PAGE_LIMIT
        return out

    # -- normalisation -----------------------------------------------------------

    def _filing_event(self, call_id: str, f: Filing) -> Event:
        sym = bare_symbol(f.symbol)
        day = f.timestamp[:10]
        ev = self.state.add_evidence(
            call_id=call_id, tool="fetch-filings", symbol=sym, period=day, field="filing",
            value=f.title, unit="text", source_ref=f.source or f"fetch-filings {sym} {f.timestamp}",
        )
        verb = {"buy": "membeli", "sell": "menjual"}.get(f.transaction_type or "", "bertransaksi")
        pct = f.share_percentage_transaction
        detail = f" ({pct:.2f}% saham" if pct is not None else " ("
        detail += f", nilai {fmt_idr(f.transaction_value)})" if f.transaction_value else ")"
        return Event(
            event_id=event_id(sym, "ownership_change", f.timestamp, f.source, f.holder_name,
                              f.amount_transaction, call_id, len(self.state.evidence)),
            symbol=sym, company_name=self.names.get(sym), event_type="ownership_change",
            event_date=day,
            title=f"{f.holder_name or 'Pemegang saham'} {verb} saham {sym}{detail}",
            source_ref=f.source or ev.source_ref, evidence_ids=[ev.evidence_id],
            attributes={
                "holder_name": f.holder_name, "holder_type": f.holder_type,
                "transaction_type": f.transaction_type,
                "amount_transaction": f.amount_transaction,
                "transaction_value": f.transaction_value,
                "share_percentage_before": f.share_percentage_before,
                "share_percentage_after": f.share_percentage_after,
                "share_percentage_transaction": pct,
            },
        )

    def _corporate_events(self, call_id: str, ca: CorporateActions, start: date,
                          end: date) -> list[Event]:
        sym = bare_symbol(ca.symbol)
        body = ca.corporate_actions
        as_of = self.state.as_of
        items: list[tuple[str, str, str, dict]] = []  # (type, date, title, attrs)
        for agm in body.agm or []:
            items.append(("agm", agm.agm_date, f"RUPS {sym}", {"agm_time": agm.agm_time,
                                                              "agm_place": agm.agm_place}))
        for div in body.dividend or []:
            attrs = {"dividend_amount": div.dividend_amount, "dividend_yield": div.dividend_yield,
                     "ex_date": div.ex_date, "payment_date": div.payment_date}
            items.append(("dividend_ex", div.ex_date,
                          f"Ex-dividen {sym} Rp{div.dividend_amount:g}/saham"
                          if div.dividend_amount is not None else f"Ex-dividen {sym}", attrs))
            if div.payment_date:
                items.append(("dividend_payment", div.payment_date,
                              f"Pembayaran dividen {sym}", attrs))
        for split in body.stock_split or []:
            items.append(("stock_split", split.date, f"Stock split {sym} 1:{split.split_ratio:g}",
                          {"split_ratio": split.split_ratio}))
        if body.upcoming_dividend not in (None, [], {}):
            self.state.add_gap(
                "unverified_shape",
                f"Field upcoming_dividend {sym} terisi, tetapi strukturnya belum terverifikasi "
                "di dokumentasi; tidak digunakan.", sym,
            )

        events = []
        for etype, day, title, attrs in items:
            d = date.fromisoformat(day)
            if not start <= d <= end:
                continue
            ev = self.state.add_evidence(
                call_id=call_id, tool="fetch-corporate-actions", symbol=sym, period=day,
                field=f"corporate_actions.{etype}", value=day, unit="date",
                source_ref=f"fetch-corporate-actions {sym} {etype} {day}",
            )
            events.append(Event(
                event_id=event_id(sym, etype, day, call_id), symbol=sym,
                company_name=self.names.get(sym), event_type=etype,  # type: ignore[arg-type]
                event_date=day, title=title, source_ref=ev.source_ref,
                evidence_ids=[ev.evidence_id], attributes=attrs, forward_looking=d > as_of,
            ))
        return events
