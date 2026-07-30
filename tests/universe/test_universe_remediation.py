from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from market_strats.universe.contracts import TickerIdentityInterval, UniverseContractError
from market_strats.universe.providers.alpha_vantage import (
    AlphaVantageListingStatusAdapter,
)
from market_strats.universe.providers.sec_edgar import (
    SecAccessError,
    SecEdgarAdapter,
    SecHttpResponse,
    SecTickerMapping,
    resolve_cik_candidates,
    sec_user_agent_from_environment,
)
from market_strats.universe.remediation import (
    PriceAuditRequest,
    apply_membership_extensions,
    build_full_price_audit_requests,
    classify_price_result,
    classify_terminal_value,
    earliest_qualified_interval,
    load_completed_price_audits,
    membership_extensions_from_change_rows,
    resolve_membership_conflict,
    write_free_data_limit_document,
)


def _sec_response(status: int, payload: object = None, **headers: str) -> SecHttpResponse:
    content = json.dumps(payload or {}).encode()
    return SecHttpResponse(status, headers, content)


def test_sec_user_agent_must_come_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(UniverseContractError, match="SEC_USER_AGENT"):
        sec_user_agent_from_environment()


def test_sec_user_agent_requires_organization_and_email(tmp_path: Path) -> None:
    with pytest.raises(UniverseContractError, match="organization"):
        SecEdgarAdapter(user_agent="person@example.test", raw_root=tmp_path)


def test_sec_headers_and_bulk_mapping_parse(tmp_path: Path) -> None:
    observed: dict[str, str] = {}

    def getter(url: str, headers: dict[str, str], timeout: int) -> SecHttpResponse:
        del url, timeout
        observed.update(headers)
        return _sec_response(
            200,
            {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[123, "Alpha Corp", "AAA", "NYSE"]],
            },
            ETag="etag",
        )

    adapter = SecEdgarAdapter(
        user_agent="Market Research contact@example.test",
        raw_root=tmp_path,
        get_response=getter,
    )
    rows, snapshot = adapter.fetch_company_ticker_mappings()
    assert rows[0].cik == "0000000123"
    assert observed["Host"] == "www.sec.gov"
    assert observed["Accept-Encoding"] == "gzip, deflate"
    assert snapshot.sec_user_agent_present is True


def test_sec_403_is_distinct_and_sanitized(tmp_path: Path) -> None:
    adapter = SecEdgarAdapter(
        user_agent="Market Research contact@example.test",
        raw_root=tmp_path,
        get_response=lambda *_: _sec_response(403),
    )
    with pytest.raises(SecAccessError) as error:
        adapter.fetch_company_ticker_mappings()
    assert error.value.category == "access_forbidden"


def test_sec_429_honors_retry_after(tmp_path: Path) -> None:
    responses = [
        SecHttpResponse(429, {"Retry-After": "2"}, b""),
        _sec_response(200, {"fields": ["cik", "name", "ticker", "exchange"], "data": []}),
    ]
    sleeps: list[float] = []
    adapter = SecEdgarAdapter(
        user_agent="Market Research contact@example.test",
        raw_root=tmp_path,
        get_response=lambda *_: responses.pop(0),
        sleeper=sleeps.append,
    )
    adapter.fetch_company_ticker_mappings()
    assert sleeps


def test_sec_cache_avoids_second_request(tmp_path: Path) -> None:
    calls = 0

    def getter(*_: object) -> SecHttpResponse:
        nonlocal calls
        calls += 1
        return _sec_response(200, {"fields": ["cik", "name", "ticker", "exchange"], "data": []})

    adapter = SecEdgarAdapter(
        user_agent="Market Research contact@example.test",
        raw_root=tmp_path,
        get_response=getter,
    )
    adapter.fetch_company_ticker_mappings()
    _, snapshot = adapter.fetch_company_ticker_mappings()
    assert calls == 1
    assert snapshot.cache_hit


def test_cik_resolution_uses_former_name() -> None:
    mappings = [SecTickerMapping("0000000001", "New Name", "NEW", "NYSE")]
    status, cik = resolve_cik_candidates(
        issuer_name="Old Name",
        ticker="OLD",
        exchange="NYSE",
        mappings=mappings,
        former_names={"0000000001": ("Old Name",)},
    )
    assert (status, cik) == ("resolved_sec_cik", "0000000001")


def test_cik_resolution_reports_ambiguous_candidates() -> None:
    mappings = [
        SecTickerMapping("1", "Same Name", "AAA", "NYSE"),
        SecTickerMapping("2", "Same Name", "BBB", "NYSE"),
    ]
    status, cik = resolve_cik_candidates(
        issuer_name="Same Name", ticker="OLD", exchange="NYSE", mappings=mappings
    )
    assert status == "ambiguous_multiple_candidates"
    assert cik is None


def _extensions():
    return membership_extensions_from_change_rows(
        [{"date": "2025-09-01", "added ticker": "NEW", "removed ticker": "OLD"}],
        after=date(2025, 8, 23),
        through=date(2026, 5, 1),
        source_reference="revision:1",
        content_hash="a" * 64,
        source_classification="free_open_licence",
    )


def test_post_august_2025_membership_extension_is_event_based() -> None:
    events = _extensions()
    assert events[0].effective_date == date(2025, 9, 1)
    assert events[0].added_ticker == "NEW"


def test_membership_extension_never_infers_endpoint_difference() -> None:
    assert not membership_extensions_from_change_rows(
        [],
        after=date(2025, 8, 23),
        through=date(2026, 5, 1),
        source_reference="revision:1",
        content_hash="a" * 64,
        source_classification="free_open_licence",
    )


def test_membership_extension_applies_add_and_remove() -> None:
    state, conflicts = apply_membership_extensions(active_tickers={"OLD"}, extensions=_extensions())
    assert state == {"NEW"}
    assert not conflicts


def test_official_announcement_resolves_conflict() -> None:
    assert (
        resolve_membership_conflict(
            seed_present=True,
            wikimedia_present=False,
            official_announcement="seed",
        )
        == "resolved_official_announcement_authoritative"
    )


def test_missing_conflict_evidence_remains_unresolved() -> None:
    assert (
        resolve_membership_conflict(
            seed_present=True,
            wikimedia_present=False,
            official_announcement=None,
        )
        == "unresolved_missing_evidence"
    )


def test_full_price_requests_use_effective_ticker_intervals() -> None:
    rows = build_full_price_audit_requests(
        ticker_intervals=[
            TickerIdentityInterval("sec", "OLD", None, date(2010, 1, 1), date(2015, 1, 1), "x"),
            TickerIdentityInterval("sec", "NEW", None, date(2015, 1, 2), None, "x"),
        ],
        membership_bounds={"sec": (date(2014, 1, 1), date(2016, 1, 1))},
        endpoint=date(2026, 5, 1),
    )
    assert [row.provider_ticker for row in rows] == ["OLD", "NEW"]
    assert rows[0].request_from < rows[0].membership_from


def test_price_audit_resume_reads_only_successes(tmp_path: Path) -> None:
    (tmp_path / "good.json").write_text(
        json.dumps({"request_id": "good", "status": "available"}), encoding="utf-8"
    )
    (tmp_path / "bad.json").write_text(
        json.dumps({"request_id": "bad", "status": "temporary_provider_failure"}),
        encoding="utf-8",
    )
    assert set(load_completed_price_audits(tmp_path)) == {"good"}


def test_delisted_symbol_failure_classification() -> None:
    request = PriceAuditRequest(
        "sec", "OLD", date(2010, 1, 1), date(2015, 1, 1), date(2009, 1, 1), date(2015, 1, 1)
    )
    assert (
        classify_price_result(
            identity_resolved=True,
            provider_status="possibly_delisted_no_history",
            first_available=None,
            last_available=None,
            request=request,
        )
        == "possibly_delisted_no_history"
    )


def test_unresolved_identity_blocks_price_request() -> None:
    request = PriceAuditRequest(
        "sec", "AAA", date(2010, 1, 1), date(2015, 1, 1), date(2009, 1, 1), date(2015, 1, 1)
    )
    assert (
        classify_price_result(
            identity_resolved=False,
            provider_status="available",
            first_available=date(2009, 1, 1),
            last_available=date(2015, 1, 1),
            request=request,
        )
        == "identity_mapping_unresolved"
    )


def test_cash_acquisition_terminal_value() -> None:
    assert classify_terminal_value(cash_value_verified=True) == "cash_acquisition_value_verified"


def test_stock_acquisition_successor_mapping() -> None:
    assert (
        classify_terminal_value(stock_ratio_verified=True, successor_verified=True)
        == "stock_acquisition_ratio_verified"
    )


def test_unknown_terminal_value_remains_blocked() -> None:
    assert (
        classify_terminal_value(delisting_status_known=True)
        == "delisting_status_known_terminal_value_unknown"
    )


def test_optional_alpha_vantage_uses_redacted_key_and_free_endpoint(tmp_path: Path) -> None:
    observed = ""

    def getter(url: str, timeout: int) -> bytes:
        del timeout
        nonlocal observed
        observed = url
        return (
            b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
            b"AAA,Alpha,NYSE,Stock,2000-01-01,,Active\n"
        )

    adapter = AlphaVantageListingStatusAdapter(
        api_key="synthetic-secret", raw_root=tmp_path, get_bytes=getter
    )
    snapshot = adapter.fetch(date(2024, 1, 1))
    assert snapshot.rows[0]["symbol"] == "AAA"
    assert "LISTING_STATUS" in observed
    assert (
        "synthetic-secret"
        not in (tmp_path / next(p.name for p in tmp_path.glob("*.meta.json"))).read_text()
    )


def test_alpha_vantage_rejects_non_free_endpoint(tmp_path: Path) -> None:
    with pytest.raises(UniverseContractError, match="LISTING_STATUS"):
        AlphaVantageListingStatusAdapter(api_key="synthetic", raw_root=tmp_path, endpoint="PREMIUM")


def test_earliest_qualified_interval_is_deterministic() -> None:
    rows = [(date(2010 + index // 12, index % 12 + 1, 1), True, ()) for index in range(156)]
    interval, audit = earliest_qualified_interval(
        rows, endpoint=date(2026, 5, 1), minimum_months=156
    )
    assert interval == (rows[0][0], rows[-1][0])
    assert audit[0]["status"] == "passed"


def test_156_month_minimum_is_enforced() -> None:
    rows = [(date(2010 + index // 12, index % 12 + 1, 1), True, ()) for index in range(155)]
    interval, _ = earliest_qualified_interval(rows, endpoint=date(2026, 5, 1))
    assert interval is None


def test_stop_rule_document_generation(tmp_path: Path) -> None:
    path = write_free_data_limit_document(
        path=tmp_path / "limit.md",
        resolved=["SEC transport implemented"],
        unavailable=["terminal values"],
        earliest_partial_interval="2013-01 through 2026-01",
    )
    text = path.read_text(encoding="utf-8")
    assert "Institutional or appropriately licensed" in text
    assert "Model training remains prohibited" in text


def test_remediation_package_never_invokes_research_or_trading_modules() -> None:
    package = Path(__file__).resolve().parents[2] / "src/market_strats/universe"
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in package.rglob("*.py"))
    prohibited = ("run_backtest(", ".fit(", ".predict(", "submit_order(", "target_weights(")
    assert not any(token in text for token in prohibited)
