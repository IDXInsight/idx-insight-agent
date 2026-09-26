from idx_insight.sectors import MockSectorsAdapter, SectorsService


def test_successful_call_is_logged_with_documented_tool_name():
    service = SectorsService(MockSectorsAdapter())
    result = service.quarterly_financials("BBCA", n_quarters=1)
    assert result.ok
    assert result.tool == "fetch-quarterly-financials"
    assert service.calls[0].call_id == result.call_id
    assert service.calls[0].args["symbol"] == "BBCA"


def test_identical_calls_are_cached():
    service = SectorsService(MockSectorsAdapter())
    first = service.corporate_actions("BBRI")
    second = service.corporate_actions("BBRI")
    assert second.cached and second.call_id == first.call_id
    assert len(service.calls) == 1
    assert service.cache_hits == 1


def test_transient_failure_is_retried_once():
    service = SectorsService(
        MockSectorsAdapter(failures={"get_corporate_actions:BBNI": 1}), max_retries=1
    )
    result = service.corporate_actions("BBNI")
    assert result.ok
    assert service.calls[0].attempts == 2


def test_persistent_failure_is_bounded_and_reported():
    service = SectorsService(
        MockSectorsAdapter(failures={"get_filings:*": "always"}), max_retries=1
    )
    result = service.filings(sub_sector="banks")
    assert not result.ok and result.status == "error"
    assert service.calls[0].attempts == 2  # 1 try + 1 bounded retry, no more


def test_not_found_is_not_retried():
    service = SectorsService(MockSectorsAdapter())
    result = service.company_report("XXXX")
    assert result.status == "not_found"
    assert service.calls[0].attempts == 1


def test_call_budget_is_enforced():
    service = SectorsService(MockSectorsAdapter(), max_calls=2)
    assert service.corporate_actions("BBCA").ok
    assert service.corporate_actions("BBRI").ok
    blocked = service.corporate_actions("BMRI")
    assert blocked.status == "budget_exhausted"
    assert service.budget_remaining == 0


def test_tool_outside_allowlist_is_refused():
    service = SectorsService(
        MockSectorsAdapter(), allowlist=frozenset({"fetch-quarterly-financials"})
    )
    result = service.filings(sub_sector="banks")
    assert result.status == "not_allowed"
    assert service.calls[0].attempts == 0


def test_malformed_response_is_reported_not_raised():
    service = SectorsService(MockSectorsAdapter(failures={"get_company_report:BBCA": "malformed"}))
    result = service.company_report("BBCA")
    assert result.status == "malformed" and result.data is None
    assert "does not match schema" in result.error
    assert service.calls[0].attempts == 1  # not retried
