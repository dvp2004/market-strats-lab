from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from market_strats.intelligence.cli import format_data_quality_error
from market_strats.intelligence.contracts import InstrumentRegistryEntry, MarketEodBar
from market_strats.intelligence.data.availability import (
    is_decision_panel_eligible,
    session_cutoff_to_utc,
)
from market_strats.intelligence.data.pipeline import (
    build_availability_audit,
    load_mi2_decision_rules,
    load_source_config,
    refresh_mi1_market_data,
    transform_source_data,
)
from market_strats.intelligence.data.registry import load_instrument_registry, load_yaml
from market_strats.intelligence.data.snapshot import write_raw_snapshot
from market_strats.intelligence.data.source import SourceInstrumentData
from market_strats.intelligence.quality.coverage import build_coverage_audit, us_equity_sessions
from market_strats.intelligence.quality.validation import DataQualityError, validate_market_eod_bars

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "configs/intelligence/universe_mi1.yaml"
SOURCE_CONFIG = ROOT / "configs/intelligence/market_data_source_mi1.yaml"
MI2_REGISTRY = ROOT / "configs/intelligence/mi2_research_registry.yaml"


def _workspace_tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _instrument() -> InstrumentRegistryEntry:
    return load_instrument_registry(UNIVERSE)[0]


def _bar(
    *,
    instrument_id: str = "mi1_etf_spy",
    session_date: date = date(2024, 1, 2),
    open_raw: float = 100.0,
    high_raw: float = 102.0,
    low_raw: float = 99.0,
    close_raw: float = 101.0,
    volume_raw: int = 1000,
    vendor_adjusted_close: float | None = 100.5,
    evidence: str = "contractual_assumption",
) -> MarketEodBar:
    available = session_cutoff_to_utc(session_date, "20:00 America/New_York")
    return MarketEodBar(
        instrument_id=instrument_id,
        session_date=session_date,
        open_raw=open_raw,
        high_raw=high_raw,
        low_raw=low_raw,
        close_raw=close_raw,
        volume_raw=volume_raw,
        vendor_adjusted_close=vendor_adjusted_close,
        adjustment_basis="vendor_adjusted_close_separate_not_point_in_time_truth",
        available_at_utc=available,
        availability_evidence_level=evidence,
        availability_rule_id="test_rule",
        retrieved_at_utc=datetime(2024, 1, 3, tzinfo=UTC),
        snapshot_id="snapshot-1",
    )


def _source_data(instrument: InstrumentRegistryEntry) -> SourceInstrumentData:
    payload = {
        "bars": [
            {
                "source_symbol": instrument.source_symbol,
                "session_date": "2024-01-02",
                "open": 100.0,
                "high": 103.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 1234,
                "adj_close": 98.5,
            }
        ],
        "dividends": [
            {"source_symbol": instrument.source_symbol, "session_date": "2024-01-02", "value": 0.25}
        ],
        "splits": [
            {"source_symbol": instrument.source_symbol, "session_date": "2024-01-03", "value": 2.0}
        ],
    }
    return SourceInstrumentData(
        source_id="yfinance_eod_mi1",
        source_name="Yahoo Finance daily EOD via yfinance",
        dataset_name="daily_eod_ohlcv_actions",
        instrument=instrument,
        request_parameters={"source_symbol": instrument.source_symbol},
        raw_payload=payload,
        bars=list(payload["bars"]),
        dividends=list(payload["dividends"]),
        splits=list(payload["splits"]),
    )


class FakeAdapter:
    source_id = "yfinance_eod_mi1"
    source_name = "Yahoo Finance daily EOD via yfinance"

    def fetch_eod(
        self,
        instruments: list[InstrumentRegistryEntry],
        start: date,
        end: date | None,
    ) -> list[SourceInstrumentData]:
        session = start
        results = []
        for index, instrument in enumerate(instruments):
            payload = {
                "bars": [
                    {
                        "source_symbol": instrument.source_symbol,
                        "session_date": session.isoformat(),
                        "open": 100.0 + index,
                        "high": 101.0 + index,
                        "low": 99.0 + index,
                        "close": 100.5 + index,
                        "volume": 1000 + index,
                        "adj_close": 100.25 + index,
                    }
                ],
                "dividends": [],
                "splits": [],
            }
            if index == 0:
                payload["dividends"].append(
                    {
                        "source_symbol": instrument.source_symbol,
                        "session_date": session.isoformat(),
                        "value": 0.1,
                    }
                )
            results.append(
                SourceInstrumentData(
                    source_id=self.source_id,
                    source_name=self.source_name,
                    dataset_name="daily_eod_ohlcv_actions",
                    instrument=instrument,
                    request_parameters={"source_symbol": instrument.source_symbol},
                    raw_payload=payload,
                    bars=list(payload["bars"]),
                    dividends=list(payload["dividends"]),
                    splits=list(payload["splits"]),
                )
            )
        return results


def test_all_22_registry_entries_load() -> None:
    instruments = load_instrument_registry(UNIVERSE)
    universe = load_yaml(UNIVERSE)
    expected_symbols = [asset["symbol"] for asset in universe["assets"]]

    assert len(instruments) == 22
    assert [instrument.symbol for instrument in instruments] == expected_symbols


def test_raw_ohlcv_and_adjusted_close_remain_distinct() -> None:
    instrument = _instrument()
    config = load_source_config(SOURCE_CONFIG)
    bars, actions, events = transform_source_data(
        run_id="run",
        source_data=_source_data(instrument),
        instruments_by_source_symbol={instrument.source_symbol: instrument},
        source_config=config,
        retrieved_at_utc=datetime(2024, 1, 3, tzinfo=UTC),
        snapshot_id="snapshot-1",
    )
    assert not events
    assert len(bars) == 1
    assert bars[0].close_raw == 102.0
    assert bars[0].vendor_adjusted_close == 98.5
    assert "not_point_in_time_truth" in bars[0].adjustment_basis
    assert {action.action_type for action in actions} == {"dividend", "split"}


def test_valid_and_invalid_ohlc_rows() -> None:
    assert validate_market_eod_bars("run", [_bar()]) == []

    with pytest.raises(DataQualityError) as low_error:
        validate_market_eod_bars("run", [_bar(low_raw=102.0)])
    assert any(event.event_type == "invalid_ohlc_low" for event in low_error.value.events)

    with pytest.raises(DataQualityError) as high_error:
        validate_market_eod_bars("run", [_bar(high_raw=100.0, close_raw=101.0)])
    assert any(event.event_type == "invalid_ohlc_high" for event in high_error.value.events)

    with pytest.raises(DataQualityError) as price_error:
        validate_market_eod_bars("run", [_bar(open_raw=0.0)])
    assert any(event.event_type == "non_positive_price" for event in price_error.value.events)

    with pytest.raises(DataQualityError) as volume_error:
        validate_market_eod_bars("run", [_bar(volume_raw=-1)])
    assert any(event.event_type == "negative_volume" for event in volume_error.value.events)


def test_missing_close_with_finite_ohl_and_volume_fails_closed_with_cli_summary() -> None:
    bar = _bar(close_raw=float("nan"), volume_raw=3_700_643, vendor_adjusted_close=None)

    with pytest.raises(DataQualityError) as missing_price_error:
        validate_market_eod_bars("run", [bar])

    events = missing_price_error.value.events
    assert len(events) == 1
    assert events[0].event_type == "missing_required_price"
    assert events[0].severity == "fatal"
    assert "close=nan" in events[0].message
    assert "vendor_adjusted_close=None" in events[0].message

    summary = format_data_quality_error(
        missing_price_error.value,
        ROOT / "data" / "private" / "mi1" / "raw",
    )
    assert "validation_event_counts:" in summary
    assert "missing_required_price: 1" in summary
    assert "validation_examples:" in summary
    assert "instrument_id=mi1_etf_spy session_date=2024-01-02" in summary
    assert "local_raw_snapshot_path:" in summary
    assert "Raw provider payloads are local-only" in summary


def test_duplicate_detection() -> None:
    with pytest.raises(DataQualityError) as duplicate_error:
        validate_market_eod_bars("run", [_bar(), _bar()])
    assert any(
        event.event_type == "duplicate_instrument_session" for event in duplicate_error.value.events
    )


def test_sha256_snapshot_manifest_generation_is_deterministic() -> None:
    tmp_path = _workspace_tmp("snapshot_manifest")
    instrument = _instrument()
    retrieved = datetime(2024, 1, 3, tzinfo=UTC)
    first = write_raw_snapshot(
        source_data=_source_data(instrument),
        raw_root=tmp_path / "a",
        retrieved_at_utc=retrieved,
        publication_permission="raw_local_only_not_redistributable",
        availability_evidence_level="contractual_assumption",
    )
    second = write_raw_snapshot(
        source_data=_source_data(instrument),
        raw_root=tmp_path / "b",
        retrieved_at_utc=retrieved,
        publication_permission="raw_local_only_not_redistributable",
        availability_evidence_level="contractual_assumption",
    )
    assert first.snapshot_id == second.snapshot_id
    assert first.content_sha256 == second.content_sha256
    assert len(first.content_sha256) == 64


def test_unverified_rows_are_blocked() -> None:
    timestamp = datetime(2024, 1, 3, tzinfo=UTC)
    eligible, reason = is_decision_panel_eligible(
        evidence_level="unverified",
        available_at_utc=timestamp,
        decision_timestamp_utc=timestamp,
        allowed_evidence_levels={"provider_timestamp_verified", "contractual_assumption"},
        contractual_assumption_approved=True,
    )
    assert not eligible
    assert "never" in reason


def test_contractual_assumption_rows_require_approval_and_cutoff_equality_is_eligible() -> None:
    timestamp = datetime(2024, 1, 3, tzinfo=UTC)
    eligible, reason = is_decision_panel_eligible(
        evidence_level="contractual_assumption",
        available_at_utc=timestamp,
        decision_timestamp_utc=timestamp,
        allowed_evidence_levels={"contractual_assumption"},
        contractual_assumption_approved=True,
    )
    assert eligible
    assert reason == ""

    blocked, blocked_reason = is_decision_panel_eligible(
        evidence_level="contractual_assumption",
        available_at_utc=timestamp,
        decision_timestamp_utc=timestamp,
        allowed_evidence_levels={"contractual_assumption"},
        contractual_assumption_approved=False,
    )
    assert not blocked
    assert "not explicitly approved" in blocked_reason


def test_daylight_saving_conversion() -> None:
    assert session_cutoff_to_utc(date(2024, 1, 2), "20:00 America/New_York") == datetime(
        2024, 1, 3, 1, 0, tzinfo=UTC
    )
    assert session_cutoff_to_utc(date(2024, 7, 1), "20:00 America/New_York") == datetime(
        2024, 7, 2, 0, 0, tzinfo=UTC
    )


def test_corporate_action_events_are_separate_from_bars() -> None:
    instrument = _instrument()
    config = load_source_config(SOURCE_CONFIG)
    bars, actions, events = transform_source_data(
        run_id="run",
        source_data=_source_data(instrument),
        instruments_by_source_symbol={instrument.source_symbol: instrument},
        source_config=config,
        retrieved_at_utc=datetime(2024, 1, 3, tzinfo=UTC),
        snapshot_id="snapshot-1",
    )
    assert not events
    assert len(bars) == 1
    assert len(actions) == 2
    assert bars[0].close_raw == 102.0
    assert all(action.snapshot_id == "snapshot-1" for action in actions)


def test_coverage_audit_and_common_start_date_calculation() -> None:
    instruments = load_instrument_registry(UNIVERSE)
    sessions = us_equity_sessions(date(2023, 1, 3), date(2024, 2, 1))[:260]
    bars = [
        _bar(instrument_id=instrument.instrument_id, session_date=session)
        for instrument in instruments
        for session in sessions
    ]
    rows, events, common_start, reason = build_coverage_audit(
        run_id="run",
        instruments=instruments,
        bars=bars,
        start=sessions[0],
        end=sessions[-1],
        minimum_common_history_sessions=252,
    )
    assert not events
    assert common_start == sessions[251]
    assert reason == ""
    assert len(rows) == 22
    assert all(row.start_date_eligible for row in rows)


def test_missing_session_data_quality_event() -> None:
    instruments = load_instrument_registry(UNIVERSE)
    sessions = us_equity_sessions(date(2024, 1, 2), date(2024, 1, 10))
    missing_session = sessions[2]
    bars = [
        _bar(instrument_id=instruments[0].instrument_id, session_date=session)
        for session in sessions
        if session != missing_session
    ]
    rows, events, _common_start, _reason = build_coverage_audit(
        run_id="run",
        instruments=[instruments[0]],
        bars=bars,
        start=sessions[0],
        end=sessions[-1],
        minimum_common_history_sessions=3,
    )
    assert rows[0].missing_sessions == 1
    assert any(
        event.event_type == "missing_expected_session" and event.session_date == missing_session
        for event in events
    )


def test_availability_audit_uses_mi2_rules() -> None:
    source_config = load_source_config(SOURCE_CONFIG)
    mi2_rules = load_mi2_decision_rules(MI2_REGISTRY)
    rows = build_availability_audit(bars=[_bar()], source_config=source_config, mi2_rules=mi2_rules)
    assert len(rows) == 1
    assert rows[0].eligible

    blocked_source = replace(source_config, contractual_assumption_approved=False)
    blocked = build_availability_audit(
        bars=[_bar()], source_config=blocked_source, mi2_rules=mi2_rules
    )
    assert not blocked[0].eligible


def test_pipeline_writes_expected_private_artifacts_and_reports() -> None:
    tmp_path = _workspace_tmp("pipeline")
    data_root = tmp_path / "data" / "private" / "mi1"
    report_root = tmp_path / "reports" / "mi1"
    result = refresh_mi1_market_data(
        universe_config=UNIVERSE,
        source_config_path=SOURCE_CONFIG,
        mi2_registry_config=MI2_REGISTRY,
        data_root=data_root,
        report_root=report_root,
        start=date(2024, 1, 2),
        end=date(2024, 1, 2),
        adapter=FakeAdapter(),
    )
    assert result.snapshot_count == 22
    assert result.bar_count == 22
    assert result.corporate_action_count == 1
    assert result.decision_panel_availability_pass
    for path in result.output_paths.values():
        assert Path(path).exists()

    bars = pd.read_parquet(result.output_paths["market_eod_bar"])
    assert set(bars["availability_evidence_level"]) == {"contractual_assumption"}
    coverage_report = Path(result.output_paths["coverage_report_json"]).read_text(encoding="utf-8")
    assert "contractual_assumption" in coverage_report


def test_generated_artifact_roots_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.parquet" in gitignore
    assert "/data/private/*" in gitignore
    assert "/reports/mi1/*" in gitignore
    assert "!/data/private/.gitkeep" in gitignore
    assert "!/reports/mi1/.gitkeep" in gitignore


def test_no_broker_order_credential_or_dotenv_dependency_is_introduced() -> None:
    package = ROOT / "src" / "market_strats" / "intelligence"
    mi1_roots = [
        package / "contracts",
        package / "data",
        package / "quality",
        package / "reporting",
    ]
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for mi1_root in mi1_roots
        for path in mi1_root.rglob("*.py")
    ).lower()
    prohibited = ["dotenv", "alpaca", "ibkr", "tradingview", "submit_order", "target_weight"]
    for token in prohibited:
        assert token not in source_text
