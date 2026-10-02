"""Deployment protections: shared store, Redis REST client, shared credit ledger,
internal API key, usage limits and the answer cache (no network, no credits)."""

import json

import httpx
import pytest
from conftest import AS_OF
from fastapi.testclient import TestClient

from idx_insight.api.app import app, get_agent_service, get_settings
from idx_insight.api.service import AgentService
from idx_insight.config import Settings
from idx_insight.llm.mock import MockLLMProvider
from idx_insight.sectors import MockSectorsAdapter, SectorsError, build_adapter
from idx_insight.sectors.adapter import SectorsUnavailableError
from idx_insight.sectors.credits import CreditLedger, SectorsCreditCapError, StoreCreditLedger
from idx_insight.sectors.http_client import SectorsHttpClient, StoreResponseCache
from idx_insight.storage import MemoryStore, RedisRestStore, StorageError

SECTORS_KEY = "sk-test-0123456789"
REDIS_TOKEN = "redis-token-abcdef"
INTERNAL_KEY = "internal-key-123456"
PEER_Q = "Bandingkan ROE BBCA dan BBRI"


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


# --- MemoryStore ---------------------------------------------------------------------------


def test_memory_store_increments_expire_and_lists_are_trimmed():
    clock = Clock()
    store = MemoryStore(clock)
    assert store.incr([("a", 2, 10), ("b", 5, None)]) == [2, 5]
    assert store.incr([("a", -1, None)]) == [1]  # keeps the existing expiry
    clock.now += 11
    assert store.get("a") is None and store.get("b") == "5"
    for i in range(5):
        store.push("log", str(i), max_len=3)
    assert store._live("log") == ["4", "3", "2"]


# --- RedisRestStore (Upstash REST format, fake transport) ------------------------------------


class FakeRedis:
    """Minimal Upstash REST endpoint backed by a MemoryStore."""

    def __init__(self, fail: str | None = None):
        self.memory = MemoryStore()
        self.requests: list[httpx.Request] = []
        self.fail = fail

    def _run(self, command: list[str]):
        name, *args = command
        if name == "GET":
            return self.memory.get(args[0])
        if name == "SET":
            ttl = int(args[3]) if len(args) > 3 else None
            self.memory.set(args[0], args[1], ttl)
            return "OK"
        if name == "INCRBY":
            return self.memory.incr([(args[0], int(args[1]), None)])[0]
        if name == "EXPIRE":
            value = self.memory.get(args[0])
            self.memory.set(args[0], value, int(args[1]))
            return 1
        if name == "LPUSH":
            self.memory.push(args[0], args[1], 10_000)
            return 1
        if name == "LTRIM":
            self.memory._data[args[0]] = (self.memory._live(args[0])[: int(args[2]) + 1], None)
            return "OK"
        raise AssertionError(name)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail == "network":
            raise httpx.ConnectError("down")
        if self.fail == "auth":
            return httpx.Response(401, json={"error": "WRONGPASS invalid password"})
        body = json.loads(request.content)
        if request.url.path == "/multi-exec":
            return httpx.Response(200, json=[{"result": self._run(c)} for c in body])
        return httpx.Response(200, json={"result": self._run(body)})


def redis_store(fake: FakeRedis) -> RedisRestStore:
    return RedisRestStore("https://example-redis.upstash.io/", REDIS_TOKEN,
                          client=httpx.Client(transport=httpx.MockTransport(fake)))


def test_redis_store_uses_upstash_rest_format():
    fake = FakeRedis()
    store = redis_store(fake)
    store.set("k", "v", 60)
    assert store.get("k") == "v"
    assert store.incr([("n", 3, 60), ("m", 1, None)]) == [3, 1]
    first = fake.requests[0]
    assert first.headers["authorization"] == f"Bearer {REDIS_TOKEN}"
    assert json.loads(first.content) == ["SET", "k", "v", "EX", "60"]
    batch = fake.requests[2]
    assert batch.url.path == "/multi-exec"
    assert json.loads(batch.content) == [["INCRBY", "n", "3"], ["EXPIRE", "n", "60"],
                                         ["INCRBY", "m", "1"]]
    assert REDIS_TOKEN not in str(first.url)


@pytest.mark.parametrize("fail", ["network", "auth"])
def test_redis_failures_raise_storage_error_without_the_token(fail):
    with pytest.raises(StorageError) as info:
        redis_store(FakeRedis(fail=fail)).get("k")
    assert REDIS_TOKEN not in str(info.value)


# --- shared credit ledger ----------------------------------------------------------------------


def test_store_ledger_refuses_the_reservation_that_would_pass_the_cap():
    store = MemoryStore()
    ledger = StoreCreditLedger(store, max_per_day=5, max_total=100)
    path, params = "/v2/company/report/BBCA/", {"sections": "overview,financials,peers"}
    first = ledger.reserve(path, params)  # 3 credits held, not yet settled
    with pytest.raises(SectorsCreditCapError, match="daily"):
        ledger.reserve(path, params)  # a concurrent request cannot use the same credits
    assert ledger.today() == 3  # the refused reservation was rolled back
    assert ledger.settle(path, params, first, 200, {}) == 3
    assert ledger.total == 3


def test_store_ledger_settles_actual_cost_and_survives_new_instances():
    store = MemoryStore()
    ledger = StoreCreditLedger(store, max_per_day=50, max_total=500)
    path = "/v2/financials/quarterly/BBCA/"
    held = ledger.reserve(path, {"n_quarters": 5})
    ledger.settle(path, {"n_quarters": 5}, held, 200, [{}, {}])  # 2 quarters returned
    ledger.release(ledger.reserve("/v2/subsectors/", {}))  # transport error: nothing spent
    restarted = StoreCreditLedger(store, max_per_day=50, max_total=500)
    assert restarted.total == 2 and restarted.today() == 2
    assert restarted.remaining_today() == 48


def test_store_ledger_fails_closed_when_the_store_is_down():
    ledger = StoreCreditLedger(redis_store(FakeRedis(fail="network")), max_per_day=5, max_total=5)
    with pytest.raises(SectorsUnavailableError, match="ledger"):
        ledger.reserve("/v2/subsectors/", {})


def test_file_ledger_holds_in_flight_reservations(tmp_path):
    ledger = CreditLedger(tmp_path / "ledger.json", max_per_day=4, max_total=100)
    held = ledger.reserve("/v2/company/report/BBCA/", {"sections": "a,b,c"})
    with pytest.raises(SectorsCreditCapError):
        ledger.reserve("/v2/company/report/BBRI/", {"sections": "a,b"})
    ledger.settle("/v2/company/report/BBCA/", {"sections": "a,b,c"}, held, 400, None)  # free
    assert ledger.total == 0 and ledger.remaining_today() == 4


# --- Sectors client on the shared store ----------------------------------------------------------


def store_client(store, fake_reply, requests, *, per_day=50):
    def transport(request):
        requests.append(request)
        if fake_reply == "network":
            raise httpx.ConnectError("down")
        return httpx.Response(200, json=fake_reply)

    ledger = StoreCreditLedger(store, max_per_day=per_day, max_total=500)
    return SectorsHttpClient(api_key=SECTORS_KEY, ledger=ledger, cache=StoreResponseCache(store),
                             client=httpx.Client(base_url="https://api.sectors.app",
                                                 transport=httpx.MockTransport(transport)))


def test_shared_cache_serves_repeats_across_instances_and_never_stores_the_key():
    store, requests = MemoryStore(), []
    store_client(store, {"ok": True}, requests).get("/v2/subsectors/")
    assert store_client(store, {"ok": True}, requests).get("/v2/subsectors/") == {"ok": True}
    assert len(requests) == 1
    assert int(store.get("idx:credits:total")) == 1
    assert SECTORS_KEY not in json.dumps({k: str(v) for k, v in store._data.items()})


def test_transport_error_releases_the_reservation():
    store = MemoryStore()
    client = store_client(store, "network", [], per_day=1)
    for _ in range(2):  # without the release, the second attempt would hit the cap
        with pytest.raises(SectorsUnavailableError, match="unreachable"):
            client.get("/v2/subsectors/")
    assert client.ledger.today() == 0


def test_real_data_on_vercel_requires_the_shared_store(tmp_path):
    settings = Settings(sectors_data_mode="real", sectors_api_key=SECTORS_KEY, vercel=True,
                        sectors_local_dir=tmp_path)
    with pytest.raises(SectorsError, match="Redis"):
        build_adapter(settings)
    adapter = build_adapter(settings, MemoryStore())
    assert isinstance(adapter.client.ledger, StoreCreditLedger)
    assert not any(tmp_path.iterdir())  # nothing written to the function's disk


# --- settings ------------------------------------------------------------------------------------


def test_settings_accept_vercel_kv_names_and_report_missing_deployment_settings():
    s = Settings.from_env({"VERCEL": "1", "SECTORS_DATA_MODE": "real",
                           "KV_REST_API_URL": "https://x.upstash.io", "KV_REST_API_TOKEN": "t"})
    assert s.vercel and s.redis_rest_url == "https://x.upstash.io"
    assert s.deployment_problems() == ["IDX_INSIGHT_API_SECRET is required on Vercel"]
    assert Settings.from_env({}).deployment_problems() == []


# --- API: internal key ---------------------------------------------------------------------------


def api(settings: Settings, service: AgentService | None = None) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    shared = service or AgentService(settings, adapter=MockSectorsAdapter())
    app.dependency_overrides[get_agent_service] = lambda: shared
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def ask(client, query=PEER_Q, headers=None, **extra):
    return client.post("/v1/agent/query", headers=headers or {},
                       json={"query": query, "as_of": AS_OF.isoformat(), **extra})


def test_internal_key_is_required_when_configured():
    client = api(Settings(internal_api_key=INTERNAL_KEY))
    assert ask(client).status_code == 401
    assert ask(client, headers={"X-Internal-Key": "wrong"}).status_code == 401
    assert client.get("/v1/capabilities").status_code == 401
    assert client.get("/docs").status_code == 401
    assert client.get("/health").status_code == 200
    assert ask(client, headers={"X-Internal-Key": INTERNAL_KEY}).status_code == 200


def test_vercel_without_internal_key_refuses_to_serve():
    client = api(Settings(vercel=True))
    assert ask(client).status_code == 503
    assert client.get("/health").status_code == 200


# --- API: usage limits and answer cache ------------------------------------------------------------


def test_rate_limit_per_client_and_cached_repeats_are_free():
    settings = Settings(internal_api_key=INTERNAL_KEY, rate_limit_per_ip=2)
    client = api(settings)
    alice = {"X-Internal-Key": INTERNAL_KEY, "X-Client-IP": "203.0.113.1"}
    bob = {"X-Internal-Key": INTERNAL_KEY, "X-Client-IP": "203.0.113.2"}
    for _ in range(5):  # the same question is answered from the cache
        assert ask(client, headers=alice).status_code == 200
    assert ask(client, "Bandingkan ROE BBCA dan BMRI", headers=alice).status_code == 200
    limited = ask(client, "Bandingkan ROE BBRI dan BMRI", headers=alice)
    assert limited.status_code == 429 and limited.json()["error"] == "rate_limited"
    assert ask(client, "Bandingkan ROE BBRI dan BMRI", headers=bob).status_code == 200


def test_client_ip_header_is_ignored_without_the_internal_key():
    client = api(Settings(rate_limit_per_ip=1))
    assert ask(client, headers={"X-Client-IP": "198.51.100.1"}).status_code == 200
    spoofed = ask(client, "Bandingkan ROE BBCA dan BMRI", headers={"X-Client-IP": "198.51.100.2"})
    assert spoofed.status_code == 429  # same real client, despite a different claimed IP


def test_daily_run_cap():
    client = api(Settings(max_queries_per_day=1))
    assert ask(client).status_code == 200
    capped = ask(client, "Bandingkan ROE BBCA dan BMRI")
    assert capped.status_code == 429 and capped.json()["error"] == "daily_limit"


def test_daily_llm_cap_falls_back_to_rules():
    llm = MockLLMProvider()
    service = AgentService(Settings(llm_max_calls_per_day=0), adapter=MockSectorsAdapter(), llm=llm)
    body = ask(api(service.settings, service)).json()
    assert body["llm_provider"] == "none" and body["llm_calls"] == []


def test_answers_are_cached_only_when_every_data_call_succeeded():
    failing = AgentService(Settings(), adapter=MockSectorsAdapter(
        failures={"get_company_report:*": "always"}))
    ask(api(failing.settings, failing))
    assert failing.guard.cached_answer(failing.guard.answer_key(service_request())) is None
    healthy = AgentService(Settings(), adapter=MockSectorsAdapter())
    ask(api(healthy.settings, healthy))
    assert healthy.guard.cached_answer(healthy.guard.answer_key(service_request())) is not None


def service_request():
    from idx_insight.api.schemas import QueryRequest
    return QueryRequest(query=PEER_Q, as_of=AS_OF)


def test_credit_headroom_refuses_new_runs():
    store = MemoryStore()
    settings = Settings(sectors_data_mode="real", sectors_api_key=SECTORS_KEY,
                        sectors_max_credits_per_day=12, query_credit_headroom=10)
    service = AgentService(settings, store=store, llm=None)
    store.incr([(service.adapter.client.ledger._day_key(), 5, None)])  # 7 left < 10 headroom
    response = ask(api(settings, service))
    assert response.status_code == 429 and response.json()["error"] == "daily_limit"


def test_store_outage_refuses_runs_instead_of_running_unmetered():
    settings = Settings()
    service = AgentService(settings, adapter=MockSectorsAdapter(),
                           store=redis_store(FakeRedis(fail="network")))
    response = ask(api(settings, service))
    assert response.status_code == 503 and response.json()["error"] == "storage_unavailable"
