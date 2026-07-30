from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.hashing import sha256_bytes
from market_strats.universe.providers import historical_membership
from market_strats.universe.providers.historical_membership import (
    load_pinned_membership_seed,
    prepare_pinned_repository,
)
from market_strats.universe.providers.sec_edgar import SecEdgarAdapter
from market_strats.universe.providers.sp_global import reconcile_bounded_announcements
from market_strats.universe.providers.wikimedia import fetch_pinned_wikimedia_snapshot
from market_strats.universe.providers.yfinance_prices import YFinancePriceAdapter
from market_strats.universe.reporting import REQUIRED_PARQUET_OUTPUTS, write_qualification_outputs


def _write_seed(root: Path) -> dict[str, str]:
    historical = b'date,tickers\n2020-01-02,"AAA"\n2020-01-03,"AAA,BBB"\n'
    current = (
        b"symbol,security,gics sector,gics sub-industry,headquarters location,"
        b"date added,cik,founded,date\nAAA,Alpha,Tech,Software,Here,2020-01-02,"
        b"1,2000,2020-01-03\n"
    )
    licence = b"MIT License\n"
    (root / "sp_500_historical_components.csv").write_bytes(historical)
    (root / "sp500_constituents.csv").write_bytes(current)
    (root / "LICENSE").write_bytes(licence)
    return {
        "sp_500_historical_components.csv": sha256_bytes(historical),
        "sp500_constituents.csv": sha256_bytes(current),
        "LICENSE": sha256_bytes(licence),
    }


def test_pinned_membership_source_revision_and_hash_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hashes = _write_seed(tmp_path)
    monkeypatch.setattr(historical_membership, "_run_git", lambda args, cwd: "abc123")
    seed = load_pinned_membership_seed(
        repository_root=tmp_path,
        expected_commit="abc123",
        expected_hashes=hashes,
    )
    assert seed.source_commit == "abc123"
    assert len(seed.snapshots) == 2
    with pytest.raises(UniverseContractError, match="hash mismatch"):
        load_pinned_membership_seed(
            repository_root=tmp_path,
            expected_commit="abc123",
            expected_hashes={"sp_500_historical_components.csv": "0" * 64},
        )


def test_pinned_repository_clone_never_silently_refreshes(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path | None]] = []

    def fake_runner(args: list[str], cwd: Path | None) -> str:
        calls.append((args, cwd))
        if args[0] == "clone":
            Path(args[-1]).mkdir(parents=True)
        return ""

    destination = tmp_path / "source"
    prepare_pinned_repository(
        repository_url="https://example.invalid/repo.git",
        destination=destination,
        expected_commit="abc123",
        git_runner=fake_runner,
    )
    assert calls[0][0][:2] == ["clone", "--no-checkout"]
    assert calls[1][0] == ["checkout", "--detach", "abc123"]
    calls.clear()
    prepare_pinned_repository(
        repository_url="https://example.invalid/repo.git",
        destination=destination,
        expected_commit="abc123",
        git_runner=fake_runner,
    )
    assert not calls


def test_wikimedia_adapter_is_revision_pinned_and_parses_tables(tmp_path: Path) -> None:
    metadata = {
        "query": {
            "pages": [
                {
                    "pageid": 7,
                    "revisions": [{"revid": 9, "timestamp": "2024-01-01T00:00:00Z", "sha1": "abc"}],
                }
            ]
        }
    }
    html = """
    <table><tr><th>Symbol</th><th>Security</th></tr>
    <tr><td>AAA</td><td>Alpha</td></tr></table>
    <table><tr><th>Date</th><th>Added ticker</th><th>Removed ticker</th></tr>
    <tr><td>2024-01-02</td><td>AAA</td><td>BBB</td></tr></table>
    """
    parsed = {"parse": {"text": html}}
    payloads = [json.dumps(metadata).encode(), json.dumps(parsed).encode()]

    def get_bytes(url: str, headers: dict[str, str], timeout: int) -> bytes:
        del url, headers, timeout
        return payloads.pop(0)

    snapshot = fetch_pinned_wikimedia_snapshot(
        api_url="https://example.invalid/api.php",
        page_title="List",
        expected_page_id=7,
        revision_id=9,
        expected_revision_sha1="abc",
        raw_root=tmp_path,
        user_agent="test",
        timeout_seconds=1,
        get_bytes=get_bytes,
    )
    assert snapshot.revision_id == 9
    assert snapshot.current_constituents[0]["symbol"] == "AAA"
    assert snapshot.historical_changes[0]["added ticker"] == "AAA"


def test_wikimedia_revision_mismatch_fails_closed(tmp_path: Path) -> None:
    metadata = {
        "query": {
            "pages": [
                {
                    "pageid": 7,
                    "revisions": [
                        {"revid": 9, "timestamp": "2024-01-01T00:00:00Z", "sha1": "wrong"}
                    ],
                }
            ]
        }
    }

    def get_bytes(url: str, headers: dict[str, str], timeout: int) -> bytes:
        del headers, timeout
        return (
            json.dumps(metadata).encode()
            if "action=query" in url
            else json.dumps({"parse": {"text": ""}}).encode()
        )

    with pytest.raises(UniverseContractError, match="SHA-1 mismatch"):
        fetch_pinned_wikimedia_snapshot(
            api_url="https://example.invalid/api.php",
            page_title="List",
            expected_page_id=7,
            revision_id=9,
            expected_revision_sha1="abc",
            raw_root=tmp_path,
            user_agent="test",
            timeout_seconds=1,
            get_bytes=get_bytes,
        )


def test_official_announcement_unavailability_is_explicit(tmp_path: Path) -> None:
    def unavailable(url: str, headers: dict[str, str], timeout: int) -> bytes:
        del url, headers, timeout
        raise OSError("offline")

    rows = reconcile_bounded_announcements(
        samples=[
            {
                "sample_id": "sample",
                "announcement_url": "https://example.invalid",
                "publication_date": "2020-01-01",
                "effective_date": "2020-01-02",
                "added_tickers": ["AAA"],
            }
        ],
        raw_root=tmp_path,
        user_agent="test",
        timeout_seconds=1,
        get_bytes=unavailable,
    )
    assert rows[0].status == "official_evidence_unavailable"
    assert rows[0].content_sha256 is None


def test_sec_adapter_maps_cik_and_records_acceptance_timestamps(tmp_path: Path) -> None:
    mappings = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[123, "Alpha", "AAA", "NYSE"]],
    }
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["0001"],
                "acceptanceDateTime": ["2024-01-01T12:34:56.000Z"],
                "form": ["8-K"],
            }
        }
    }

    def get_bytes(url: str, headers: dict[str, str], timeout: int) -> bytes:
        del headers, timeout
        return json.dumps(submissions if "submissions" in url else mappings).encode()

    adapter = SecEdgarAdapter(
        user_agent="MarketStratsLab test test@example.com",
        raw_root=tmp_path,
        get_bytes=get_bytes,
        sleeper=lambda seconds: None,
    )
    rows, _ = adapter.fetch_company_ticker_mappings()
    filings, _ = adapter.fetch_submission_history(rows[0].cik)
    assert rows[0].cik == "0000000123"
    assert filings[0]["acceptance_timestamp"] == "2024-01-01T12:34:56.000Z"


def test_sec_adapter_requires_compliant_contact_user_agent(tmp_path: Path) -> None:
    with pytest.raises(UniverseContractError, match="contact address"):
        SecEdgarAdapter(user_agent="generic", raw_root=tmp_path)


class _FakeTicker:
    def history(self, **kwargs: object) -> pd.DataFrame:
        assert kwargs["auto_adjust"] is False
        assert kwargs["actions"] is True
        return pd.DataFrame(
            {
                "Date": pd.to_datetime(["2024-01-02"]),
                "Open": [10.0],
                "High": [11.0],
                "Low": [9.0],
                "Close": [10.5],
                "Adj Close": [10.25],
                "Volume": [1_000],
                "Dividends": [0.5],
                "Stock Splits": [0.0],
            }
        ).set_index("Date")


def test_yfinance_adapter_preserves_raw_adjusted_and_actions(tmp_path: Path) -> None:
    adapter = YFinancePriceAdapter(
        raw_root=tmp_path,
        ticker_factory=lambda ticker: _FakeTicker(),
        sleeper=lambda seconds: None,
    )
    result = adapter.fetch(
        provider_ticker="AAA",
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
    )
    assert result.status == "available"
    assert result.rows[0]["raw_close"] == 10.5
    assert result.rows[0]["adjusted_close"] == 10.25
    assert result.actions[0]["action_type"] == "dividend"
    assert result.request_parameters["auto_adjust"] is False


def test_yfinance_provider_unavailability_is_bounded(tmp_path: Path) -> None:
    calls = 0

    def factory(ticker: str) -> object:
        del ticker
        nonlocal calls
        calls += 1
        raise OSError("offline")

    adapter = YFinancePriceAdapter(
        raw_root=tmp_path,
        maximum_attempts=2,
        ticker_factory=factory,
        sleeper=lambda seconds: None,
    )
    result = adapter.fetch(
        provider_ticker="AAA",
        start=date(2024, 1, 1),
        end=date(2024, 1, 31),
    )
    assert result.status == "provider_unavailable"
    assert calls == 2


def test_report_writer_emits_exact_local_output_set(tmp_path: Path) -> None:
    tables = {name: pd.DataFrame({"value": [1]}) for name in REQUIRED_PARQUET_OUTPUTS}
    outputs = write_qualification_outputs(
        report_root=tmp_path,
        source_snapshot_manifest={"sources": {}},
        source_licence_audit={"total_data_cost_usd": 0},
        tables=tables,
        qualification_summary={
            "verdict": "blocked_free_source_coverage_failure",
            "monthly_decision_dates": 0,
            "unique_securities": 1,
            "earliest_qualified_decision_date": None,
            "latest_qualified_decision_date": None,
            "blocking_reasons": ["synthetic"],
        },
    )
    assert set(outputs) == {
        *REQUIRED_PARQUET_OUTPUTS,
        "source_snapshot_manifest.json",
        "source_licence_audit.json",
        "qualification_summary.json",
        "qualification_summary.md",
    }
    assert all(path.parent == tmp_path for path in outputs.values())


def test_universe_package_never_invokes_model_strategy_portfolio_or_broker() -> None:
    package = Path(__file__).resolve().parents[2] / "src/market_strats/universe"
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in package.rglob("*.py"))
    prohibited_calls = (
        "run_backtest(",
        "fit(",
        "predict(",
        "submit_order(",
        "paper_trade(",
        "target_weights(",
    )
    assert not any(token in text for token in prohibited_calls)
