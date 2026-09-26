"""Discovery Agent: collect and normalise disclosures and corporate actions."""

from __future__ import annotations

from datetime import date, timedelta

from idx_insight.agent.i18n import t
from idx_insight.agent.recovery import record_tool_failure
from idx_insight.agent.state import AgentState, RecoveryAction
from idx_insight.analytics.events import event_id
from idx_insight.analytics.numbers import fmt_idr, fmt_share_pct
from idx_insight.models import Event
from idx_insight.sectors.schemas import CorporateActions, Filing, bare_symbol
from idx_insight.sectors.service import SectorsService

MAX_SCOPE_COMPANIES = 12  # per-company analysis (each company costs credits)
SECTOR_DISCOVERY_LIMIT = 200  # whole sector: one screener call, market-wide calendar/filings
MAX_FILING_PAGES = 3
FILINGS_PAGE_LIMIT = 30  # documented maximum for /v2/filings/
WIDENED_LOOKBACK_DAYS = 30
CALENDAR_TYPES = ("agm", "dividend", "stock_split")
CALENDAR_MAX_DAYS = 90  # documented limit of the market-wide calendar


class DiscoveryAgent:
    def __init__(self, service: SectorsService, state: AgentState, max_requeries: int) -> None:
        self.service = service
        self.state = state
        self.max_requeries = max_requeries
        self.names: dict[str, str] = {}

    # -- scope -----------------------------------------------------------------

    def scope(self, members: list[tuple[str, str | None]],
              cap: int | None = MAX_SCOPE_COMPANIES) -> list[str]:
        """Unique symbols in scope; ``cap`` bounds per-company work (None = no cap)."""
        symbols = []
        for symbol, name in members:
            if name:
                self.names[symbol] = name
            symbols.append(symbol)
        symbols = list(dict.fromkeys(symbols))
        if cap is not None and len(symbols) > cap:
            self.state.add_gap("scope_truncated", t(self.state.language, "gap.scope_truncated",
                                                    n=len(symbols), cap=cap))
            symbols = symbols[:cap]
        return symbols

    # -- collection ------------------------------------------------------------

    def collect(self, symbols: list[str], sub_sector: str | None) -> list[Event]:
        tf = self.state.timeframe
        assert tf is not None
        lang = self.state.language
        events: list[Event] = []
        filings = self._filings(symbols, sub_sector, tf.filings_start, tf.filings_end)
        if not filings and self._can_requery() and tf.direction != "backward":
            widened = tf.filings_end - timedelta(days=WIDENED_LOOKBACK_DAYS)
            self.state.requeries_used += 1
            filings = self._filings(symbols, sub_sector, widened, tf.filings_end)
            self.state.recovery.append(RecoveryAction(
                trigger="empty_result", target="fetch-filings",
                action=t(lang, "recovery.widen.action", days=WIDENED_LOOKBACK_DAYS),
                outcome=t(lang, "recovery.widen.outcome", n=len(filings)),
            ))
            if filings:
                self.state.assumptions.append(
                    t(lang, "assumption.widened", start=widened, end=tf.filings_end))
        in_scope = set(symbols)
        for call_id, filing in filings:
            sym = bare_symbol(filing.symbol)
            if in_scope and sym not in in_scope:
                continue
            events.append(self._filing_event(call_id, filing))

        events.extend(self._scheduled_events(symbols, tf.start, tf.end))

        self.state.add_gap("unsupported_capability", t(lang, "gap.no_report_schedule"))
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
                    target = next(iter(query.values()))
                    record_tool_failure(self.state, t(self.state.language, "what.filings",
                                                      target=target), result.status)
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
        lang = self.state.language
        verb = t(lang, f"event.verb.{f.transaction_type}" if f.transaction_type in ("buy", "sell")
                 else "event.verb.other")
        pct = f.share_percentage_transaction
        parts = []
        if pct is not None:
            parts.append(t(lang, "event.filing_pct", pct=fmt_share_pct(pct, lang)))
        if f.transaction_value:
            parts.append(t(lang, "event.filing_value", value=fmt_idr(f.transaction_value, lang)))
        detail = f" ({', '.join(parts)})" if parts else ""
        holder = f.holder_name or t(lang, "event.holder_default")
        return Event(
            event_id=event_id(sym, "ownership_change", f.timestamp, f.source, f.holder_name,
                              f.amount_transaction, call_id, len(self.state.evidence)),
            symbol=sym, company_name=self.names.get(sym), event_type="ownership_change",
            event_date=day,
            title=t(lang, "event.filing", holder=holder, verb=verb, sym=sym, detail=detail),
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

    def _scheduled_events(self, symbols: list[str], start: date, end: date) -> list[Event]:
        """Corporate actions in the window, choosing the cheaper Sectors call.

        Per-company lookups cost one credit each; the market-wide calendar costs one
        credit per action type. The calendar wins once the scope has more companies
        than action types, and its window is limited to 90 days.
        """
        lang = self.state.language
        use_calendar = (len(symbols) > len(CALENDAR_TYPES)
                        and (end - start).days <= CALENDAR_MAX_DAYS)
        self.state.analytics["corporate_actions_source"] = "calendar" if use_calendar else "per_company"
        if not use_calendar:
            events: list[Event] = []
            for sym in symbols:
                result = self.service.corporate_actions(sym)
                if not result.ok or result.data is None:
                    record_tool_failure(self.state, t(lang, "what.corporate_actions", sym=sym),
                                        result.status, sym)
                    continue
                events.extend(self._corporate_events(result.call_id, result.data, start, end))
            return events

        result = self.service.corporate_actions_calendar(start.isoformat(), end.isoformat(),
                                                         CALENDAR_TYPES)
        if not result.ok or result.data is None:
            record_tool_failure(self.state, t(lang, "what.corporate_actions_calendar"),
                                result.status)
            return []
        in_scope = set(symbols)
        per_symbol: dict[str, dict[str, list]] = {}
        for kind in CALENDAR_TYPES:
            for row in getattr(result.data, kind) or []:
                sym = bare_symbol(row.symbol)
                if sym in in_scope:
                    per_symbol.setdefault(sym, {}).setdefault(kind, []).append(
                        row.model_dump(exclude={"symbol"}))
        events = []
        for sym, body in sorted(per_symbol.items()):
            ca = CorporateActions.model_validate({"symbol": f"{sym}.JK", "corporate_actions": body})
            events.extend(self._corporate_events(result.call_id, ca, start, end,
                                                 tool="corporate-actions-calendar"))
        return events

    def _corporate_events(self, call_id: str, ca: CorporateActions, start: date,
                          end: date, tool: str = "fetch-corporate-actions") -> list[Event]:
        sym = bare_symbol(ca.symbol)
        body = ca.corporate_actions
        as_of = self.state.as_of
        lang = self.state.language
        items: list[tuple[str, str, str, dict]] = []  # (type, date, title, attrs)
        for agm in body.agm or []:
            items.append(("agm", agm.agm_date, t(lang, "event.agm", sym=sym),
                          {"agm_time": agm.agm_time, "agm_place": agm.agm_place}))
        for div in body.dividend or []:
            attrs = {"dividend_amount": div.dividend_amount, "dividend_yield": div.dividend_yield,
                     "ex_date": div.ex_date, "payment_date": div.payment_date}
            title = (t(lang, "event.dividend_ex", sym=sym, amount=fmt_idr(div.dividend_amount, lang))
                     if div.dividend_amount is not None else t(lang, "event.dividend_ex_plain", sym=sym))
            items.append(("dividend_ex", div.ex_date, title, attrs))
            if div.payment_date:
                items.append(("dividend_payment", div.payment_date,
                              t(lang, "event.dividend_payment", sym=sym), attrs))
        for split in body.stock_split or []:
            items.append(("stock_split", split.date,
                          t(lang, "event.stock_split", sym=sym, ratio=f"{split.split_ratio:g}"),
                          {"split_ratio": split.split_ratio}))
        if body.upcoming_dividend not in (None, [], {}):
            self.state.add_gap("unverified_shape", t(lang, "gap.unverified_shape", sym=sym), sym)

        events = []
        for etype, day, title, attrs in items:
            d = date.fromisoformat(day)
            if not start <= d <= end:
                continue
            ev = self.state.add_evidence(
                call_id=call_id, tool=tool, symbol=sym, period=day,
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
