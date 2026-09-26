"""Credit guardrails and the Sectors HTTP client (fake transport; spends no credits)."""

import json

import httpx
import pytest

from idx_insight.sectors.adapter import SectorsNotFoundError, SectorsUnavailableError
from idx_insight.sectors.credits import CreditLedger, SectorsCreditCapError, actual_cost, max_cost
from idx_insight.sectors.http_client import (
    SectorsAuthError,
    SectorsBadRequestError,
    SectorsHttpClient,
)

KEY = "sk-test-0123456789"


class FakeSectors:
    """Records requests; replies from a scripted list of (status, body)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return httpx.Response(status, json=body)


def make_client(tmp_path, fake, *, mode="readwrite", per_day=50, total=500, sleeps=None):
    ledger = CreditLedger(tmp_path / "ledger.json", max_per_day=per_day, max_total=total)
    return SectorsHttpClient(
        api_key=KEY, ledger=ledger, cache_dir=tmp_path / "cache", cache_mode=mode,
        client=httpx.Client(base_url="https://api.sectors.app",
                            transport=httpx.MockTransport(fake)),
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )


# --- billing rules ----------------------------------------------------------------------


@pytest.mark.parametrize("path, params, expected", [
    ("/v2/company/report/BBCA/", {"sections": "overview,financials"}, 2),
    ("/v2/company/report/BBCA/", {}, 8),
    ("/v2/financials/quarterly/BBCA/", {"report_date": "2026-06-30"}, 1),
    ("/v2/financials/quarterly/BBCA/", {"n_quarters": 5}, 5),
    ("/v2/corporate-actions/", {"type": "agm,dividend,stock_split"}, 3),
    ("/v2/corporate-actions/", {}, 7),
    ("/v2/companies/", {"where": "sub_sector = 'Banks'"}, 1),
    ("/v2/companies/", {"q": "top banks"}, 3),
    ("/v2/filings/", {"sub_sector": "banks"}, 1),
])
def test_worst_case_cost_follows_documented_billing(path, params, expected):
    assert max_cost(path, params) == expected


def test_actual_cost_by_status():
    path = "/v2/financials/quarterly/BBCA/"
    assert actual_cost(path, {"n_quarters": 5}, 200, [{}, {}]) == 2  # per quarter returned
    assert actual_cost(path, {}, 404, None) == 1
    for free in (400, 401, 403, 429, 500, 503):
        assert actual_cost(path, {}, free, None) == 0


# --- caps -------------------------------------------------------------------------------


def test_request_refused_before_sending_when_cap_would_be_exceeded(tmp_path):
    fake = FakeSectors((200, {"results": []}))
    client = make_client(tmp_path, fake, per_day=4)
    client.get("/v2/company/report/BBCA/", {"sections": "overview,financials"})  # 2 credits
    with pytest.raises(SectorsCreditCapError, match="daily"):
        client.get("/v2/company/report/BBRI/", {"sections": "overview,financials,peers"})
    assert len(fake.requests) == 1  # the refused request never left the machine


def test_total_cap_and_ledger_persist_across_restarts(tmp_path):
    fake = FakeSectors((200, {"ok": True}))
    make_client(tmp_path, fake, mode="off", total=2).get("/v2/subsectors/")
    restarted = make_client(tmp_path, fake, mode="off", total=2)
    assert restarted.ledger.total == 1
    restarted.get("/v2/subsectors/")
    with pytest.raises(SectorsCreditCapError, match="total"):
        restarted.get("/v2/subsectors/")


# --- cache & replay ----------------------------------------------------------------------


def test_cache_avoids_repeat_calls_and_never_stores_the_key(tmp_path):
    fake = FakeSectors((200, {"2026": [["2026-03-31", "q1"]]}))
    client = make_client(tmp_path, fake)
    first = client.get("/v2/company/get_quarterly_financial_dates/BBCA/")
    second = client.get("/v2/company/get_quarterly_financial_dates/BBCA/")
    assert first == second and len(fake.requests) == 1
    assert client.ledger.total == 1
    stored = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))
    assert KEY not in stored


def test_request_sends_key_only_in_authorization_header(tmp_path):
    fake = FakeSectors((200, {"ok": True}))
    make_client(tmp_path, fake).get("/v2/subsectors/")
    request = fake.requests[0]
    assert request.headers["authorization"] == KEY
    assert KEY not in str(request.url)


def test_replay_mode_never_calls_the_api(tmp_path):
    fake = FakeSectors((200, {"ok": True}))
    make_client(tmp_path, fake).get("/v2/subsectors/")  # record once
    replay = make_client(tmp_path, fake, mode="replay")
    assert replay.get("/v2/subsectors/") == {"ok": True}
    with pytest.raises(SectorsUnavailableError, match="replay"):
        replay.get("/v2/filings/", {"sub_sector": "banks"})
    assert len(fake.requests) == 1


def test_not_found_is_cached_so_it_is_billed_once(tmp_path):
    fake = FakeSectors((404, {"message": "symbol not found"}))
    client = make_client(tmp_path, fake)
    for _ in range(2):
        with pytest.raises(SectorsNotFoundError):
            client.get("/v2/company/report/ABCD/", {"sections": "overview"})
    assert len(fake.requests) == 1 and client.ledger.total == 1


# --- errors & backoff ----------------------------------------------------------------------


def test_rate_limit_uses_bounded_backoff(tmp_path):
    sleeps: list[float] = []
    fake = FakeSectors((429, {}), (429, {}), (200, {"ok": True}))
    client = make_client(tmp_path, fake, sleeps=sleeps)
    assert client.get("/v2/subsectors/") == {"ok": True}
    assert sleeps == [1.0, 2.0] and client.ledger.total == 1  # 429s are free


@pytest.mark.parametrize("status, error", [
    (401, SectorsAuthError), (403, SectorsAuthError), (400, SectorsBadRequestError),
    (500, SectorsUnavailableError), (503, SectorsUnavailableError),
])
def test_errors_are_mapped_and_free(tmp_path, status, error):
    client = make_client(tmp_path, FakeSectors((status, {"message": "nope"})))
    with pytest.raises(error):
        client.get("/v2/subsectors/")
    assert client.ledger.total == 0


def test_missing_key_is_rejected_unless_replaying(tmp_path):
    ledger = CreditLedger(None, max_per_day=1, max_total=1)
    with pytest.raises(SectorsAuthError):
        SectorsHttpClient(api_key="", ledger=ledger, cache_dir=tmp_path)
    SectorsHttpClient(api_key="", ledger=ledger, cache_dir=tmp_path, cache_mode="replay")


def test_ledger_file_is_readable_json(tmp_path):
    make_client(tmp_path, FakeSectors((200, {"ok": True}))).get("/v2/subsectors/")
    data = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert data["total"] == 1 and data["requests"][0]["path"] == "/v2/subsectors/"
