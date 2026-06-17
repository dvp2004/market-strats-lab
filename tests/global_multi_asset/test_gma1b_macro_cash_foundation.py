from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.cli import main as gma_main
from market_strats.global_multi_asset.gma1b_config import (
    GMA1B_PHASE_ID,
    GMA1B_TRACK_ID,
    is_approved_gma1b_output_path,
    load_gma1b_config,
    validate_gma1b_config,
)
from market_strats.global_multi_asset.gma1b_macro_cash import (
    ACCEPTED_GMA1A_HASH,
    FRED_MAX_ENCODED_REQUEST_URI_BYTES,
    FRED_SAFE_VINTAGE_DATES_PER_REQUEST,
    GMA1BResult,
    _crosscheck_output_type_4_initial_releases,
    _derive_revision_event_counts,
    _fetch_current_fred_observations,
    _fetch_fred_payload,
    _fetch_observations_by_classification,
    _fetch_vintage_chunk_with_414_recovery,
    _measure_vintage_request_uri_bytes,
    _select_bounded_validation_vintages,
    _validate_output_type_2_against_reconstruction,
    build_cash_accrual,
    build_vintage_revision_audit,
    canonical_json_sha256,
    chunk_vintage_dates,
    chunk_vintage_dates_uri_aware,
    fetch_fred_json,
    fred_request_url,
    merge_vintage_observation_chunks,
    normalise_observations,
    query_point_in_time,
    retrieval_classification_for_series,
    run_gma1b_live_diagnostic,
    run_gma1b_macro_cash_foundation,
    sha256_file,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma1b_macro_cash_foundation.yaml")
REPORT_DIR = Path("reports/global_multi_asset_alpha/macro_foundation")
CANONICAL_DIR = Path("data/global_multi_asset_alpha/canonical_macro")


@pytest.fixture()
def config():
    return load_gma1b_config(CONFIG_PATH)


@pytest.fixture()
def tiny_registry() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "macro_id": "cash_3m_treasury",
            "provider": "fred",
            "series_id": "DGS3MO",
            "display_name": "3-month Treasury/cash rate",
            "economic_role": "authoritative_cash_rate",
            "frequency": "daily",
            "units": "percent",
            "seasonal_adjustment": "not_seasonally_adjusted",
            "native_observation_calendar": "federal_reserve_business_day",
            "expected_publication_frequency": "daily",
            "is_required": True,
            "is_vintage_aware": True,
            "revision_prone": False,
            "availability_timestamp_policy": "release_date_available_after_235959_utc",
            "maximum_staleness_days": 7,
            "transformation_policy": "percent_to_decimal_yield",
            "notes": "cash",
        },
        {
            "macro_id": "cpi",
            "provider": "fred",
            "series_id": "CPIAUCSL",
            "display_name": "CPI",
            "economic_role": "inflation",
            "frequency": "monthly",
            "units": "index",
            "seasonal_adjustment": "seasonally_adjusted",
            "native_observation_calendar": "monthly_release",
            "expected_publication_frequency": "monthly",
            "is_required": True,
            "is_vintage_aware": True,
            "revision_prone": True,
            "availability_timestamp_policy": "release_date_available_after_235959_utc",
            "maximum_staleness_days": 45,
            "transformation_policy": "level",
            "notes": "vintage",
        },
    ])


@pytest.fixture()
def tiny_canonical(tiny_registry: pd.DataFrame) -> pd.DataFrame:
    observations = pd.DataFrame([
        {
            "series_id": "DGS3MO",
            "observation_date": "2024-01-05",
            "value": 5.0,
            "realtime_start": "2024-01-05",
            "realtime_end": "9999-12-31",
        },
        {
            "series_id": "DGS3MO",
            "observation_date": "2024-01-08",
            "value": 5.1,
            "realtime_start": "2024-01-08",
            "realtime_end": "9999-12-31",
        },
        {
            "series_id": "CPIAUCSL",
            "observation_date": "2023-12-01",
            "value": 310.0,
            "realtime_start": "2024-01-12",
            "realtime_end": "9999-12-31",
        },
        {
            "series_id": "CPIAUCSL",
            "observation_date": "2023-12-01",
            "value": 310.2,
            "realtime_start": "2024-03-01",
            "realtime_end": "9999-12-31",
        },
    ])
    return normalise_observations(
        observations,
        tiny_registry,
        manifest_path="fixture_manifest.json",
        manifest_sha256="manifest_hash",
        raw_sha256="raw_hash",
        normalised_sha256="normalised_hash",
        retrieved_at_utc="fixture_contract",
    )


def test_01_safety_flags(config) -> None:
    assert config.track["track_id"] == GMA1B_TRACK_ID
    assert config.track["phase_id"] == GMA1B_PHASE_ID
    assert config.track["paper_only"]
    assert not config.track["live_trading_allowed"]
    assert not config.track["real_money_allowed"]
    assert not config.track["broker_api_integration_allowed"]


def test_02_unknown_config_rejected(config) -> None:
    raw = dict(config.raw)
    raw["unexpected"] = True
    with pytest.raises(ValueError, match="Unknown keys"):
        validate_gma1b_config(raw)


def test_03_official_provider_enforced(config) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["provider"]["primary_provider"] = "yahoo"
    with pytest.raises(ValueError, match="primary_provider"):
        validate_gma1b_config(raw)


def test_04_bil_cannot_be_authoritative_cash() -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["cash"]["bil_role"] = "authoritative_cash_source"
    with pytest.raises(ValueError, match="BIL"):
        validate_gma1b_config(raw)


def test_05_series_registry_unique(config) -> None:
    ids = [item["macro_id"] for item in config.series]
    sids = [item["series_id"] for item in config.series]
    assert len(ids) == len(set(ids))
    assert len(sids) == len(set(sids))


def test_06_required_series_present(config) -> None:
    ids = {item["macro_id"] for item in config.series}
    assert set(config.quality["required_series"]).issubset(ids)


def test_07_unknown_series_rejected(config) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["quality"]["required_series"].append("missing_macro")
    with pytest.raises(ValueError, match="missing"):
        validate_gma1b_config(raw)


def test_08_approved_paths(config) -> None:
    for path in config.paths.values():
        assert is_approved_gma1b_output_path(path)


def test_09_availability_timestamps_are_end_of_day(tiny_canonical) -> None:
    cpi = tiny_canonical[tiny_canonical["macro_id"].eq("cpi")].iloc[0]
    assert str(cpi["availability_timestamp_utc"]).endswith("23:59:59+00:00")


def test_10_initial_release_selection(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "cpi", "2024-01-13T00:00:00Z")
    assert result["value"] == pytest.approx(310.0)
    assert result["realtime_start"] == "2024-01-12"


def test_11_revision_selection_after_availability(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "cpi", "2024-03-02T00:00:00Z")
    assert result["value"] == pytest.approx(310.2)
    assert result["realtime_start"] == "2024-03-01"


def test_12_asof_before_first_release_unavailable(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "cpi", "2024-01-01T00:00:00Z")
    assert result["point_in_time_status"] == "unavailable_before_first_release"


def test_13_asof_between_release_and_revision(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "cpi", "2024-02-01T00:00:00Z")
    assert result["value"] == pytest.approx(310.0)


def test_14_future_revision_cannot_leak_backward(tiny_canonical) -> None:
    before = query_point_in_time(tiny_canonical, "cpi", "2024-02-15T00:00:00Z")
    after = query_point_in_time(tiny_canonical, "cpi", "2024-03-02T00:00:00Z")
    assert before["value"] != after["value"]


def test_15_unknown_series_unavailable(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "unknown", "2024-01-01T00:00:00Z")
    assert result["point_in_time_status"] == "unavailable_unknown_series"


def test_16_daily_series_availability(tiny_canonical) -> None:
    early = query_point_in_time(tiny_canonical, "cash_3m_treasury", "2024-01-05T12:00:00Z")
    late = query_point_in_time(tiny_canonical, "cash_3m_treasury", "2024-01-06T00:00:00Z")
    assert early["point_in_time_status"] == "unavailable_before_first_release"
    assert late["value"] == pytest.approx(5.0)


def test_17_monthly_series_not_available_in_observation_month(tiny_canonical) -> None:
    result = query_point_in_time(tiny_canonical, "cpi", "2023-12-31T00:00:00Z")
    assert result["point_in_time_status"] == "unavailable_before_first_release"


def test_18_vintage_revision_audit(tiny_canonical, tiny_registry) -> None:
    audit = build_vintage_revision_audit(tiny_canonical, tiny_registry)
    assert not audit.empty
    row = audit.iloc[0]
    assert row["revision_count"] == 1
    assert row["absolute_revision"] == pytest.approx(0.2)


def test_19_cpi_revision_example(tiny_canonical, tiny_registry) -> None:
    audit = build_vintage_revision_audit(tiny_canonical, tiny_registry)
    assert "cpi" in set(audit["macro_id"])


def test_20_unemployment_and_indpro_registry_are_vintage_aware(config) -> None:
    by_id = {item["macro_id"]: item for item in config.series}
    assert by_id["unemployment"]["is_vintage_aware"]
    assert by_id["industrial_production"]["is_vintage_aware"]


def test_21_cash_one_day_accrual(tiny_canonical, config) -> None:
    cash = build_cash_accrual(tiny_canonical, config)
    first = cash.iloc[0]
    assert first["accrual_days"] == 3
    assert first["period_return"] == pytest.approx(0.05 * 3 / 365)


def test_22_weekend_accrual(tiny_canonical, config) -> None:
    cash = build_cash_accrual(tiny_canonical, config)
    assert cash.iloc[0]["accrual_start"] == "2024-01-05"
    assert cash.iloc[0]["accrual_end"] == "2024-01-08"
    assert cash.iloc[0]["accrual_days"] == 3


def test_23_negative_yield_allowed(tiny_canonical, config) -> None:
    modified = tiny_canonical.copy()
    modified.loc[modified["series_id"].eq("DGS3MO"), "value"] = -0.5
    cash = build_cash_accrual(modified, config)
    assert cash.iloc[0]["period_return"] < 0


def test_24_cash_missing_rate_fails_closed(config) -> None:
    empty = pd.DataFrame(columns=["series_id"])
    assert build_cash_accrual(empty, config).empty


def test_25_hash_is_deterministic() -> None:
    payload = {"b": 2, "a": 1}
    assert canonical_json_sha256(payload) == canonical_json_sha256({"a": 1, "b": 2})


def test_26_canonical_source_selection_rejects_latest_concept(config) -> None:
    for value in config.paths.values():
        assert "latest" not in str(value).lower()


def test_27_derived_curves_use_official_series(config) -> None:
    by_id = {item["macro_id"]: item for item in config.series}
    assert by_id["curve_10y_2y"]["transformation_policy"] == "official_spread_series"
    assert by_id["curve_10y_3m"]["transformation_policy"] == "official_spread_series"


def test_28_bitcoin_calendar_does_not_alter_macro_publication_dates(config) -> None:
    assert "bitcoin" not in str(config.point_in_time).lower()


def test_29_etf_calendar_does_not_fabricate_macro_availability(config) -> None:
    assert config.point_in_time["asof_query_policy"].startswith("latest_available")


def test_30_no_credentials_written_to_reports_after_run(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in REPORT_DIR.rglob("*")
        if path.is_file()
    )
    assert "FRED_API_KEY=" not in text
    assert "api_key=" not in text.lower()
    assert "SECRET" not in text


def test_31_runner_writes_required_reports(config) -> None:
    result = run_gma1b_macro_cash_foundation(config)
    assert result.decision == "gma1b_live_data_incomplete"
    for name in [
        "series_registry.csv",
        "source_snapshot_selection.csv",
        "canonical_macro_inventory.csv",
        "canonical_macro_manifest.json",
        "canonical_macro_hash.txt",
        "availability_policy.md",
        "availability_audit.csv",
        "vintage_revision_audit.csv",
        "cash_rate_contract.md",
        "cash_rate_reconciliation.csv",
        "point_in_time_query_examples.csv",
        "macro_series_readiness.csv",
        "gma1b_gate_report.csv",
        "gma1b_conclusion.md",
    ]:
        assert (REPORT_DIR / name).exists(), name


def test_32_canonical_outputs_written(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    assert (CANONICAL_DIR / "point_in_time_macro_observations.csv").exists()
    assert (CANONICAL_DIR / "canonical_cash_accrual.csv").exists()
    assert (CANONICAL_DIR / "release_availability.csv").exists()
    assert (CANONICAL_DIR / "vintage_history.csv").exists()


def test_33_snapshot_hash_validation(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    selection = pd.read_csv(REPORT_DIR / "source_snapshot_selection.csv").iloc[0]
    assert sha256_file(Path(selection["raw_file_path"])) == selection["raw_file_sha256"]
    assert sha256_file(Path(selection["normalised_file_path"])) == selection["normalised_file_sha256"]


def test_34_canonical_hash_repeats(config) -> None:
    first = run_gma1b_macro_cash_foundation(config).canonical_hash
    second = run_gma1b_macro_cash_foundation(config).canonical_hash
    assert first == second


def test_35_required_series_failure_blocks_readiness(config) -> None:
    result = run_gma1b_macro_cash_foundation(config)
    readiness = pd.read_csv(REPORT_DIR / "macro_series_readiness.csv")
    assert result.decision == "gma1b_live_data_incomplete"
    assert not readiness.loc[readiness["is_required"], "ready_for_replay_engine"].all()


def test_36_gate_marks_live_incomplete(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    gate = pd.read_csv(REPORT_DIR / "gma1b_gate_report.csv")
    live = gate[gate["gate"].eq("live_official_source_retrieval_complete")].iloc[0]
    assert not bool(live["passed"])


def test_37_accepted_gma1a_hash_in_manifest(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    manifest = (REPORT_DIR / "canonical_macro_manifest.json").read_text(encoding="utf-8")
    assert ACCEPTED_GMA1A_HASH in manifest


def test_38_no_writes_outside_approved_paths(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    for path in [REPORT_DIR, CANONICAL_DIR, config.paths["raw_root"], config.paths["manifest_root"]]:
        assert is_approved_gma1b_output_path(path)


def test_39_gma1b_conclusion_no_strategy_scope(config) -> None:
    run_gma1b_macro_cash_foundation(config)
    text = (REPORT_DIR / "gma1b_conclusion.md").read_text(encoding="utf-8")
    assert "No GMA-2" in text
    assert "strategy signal" in text
    assert "broker work was performed" in text


def test_40_cli_config_can_load() -> None:
    assert load_gma1b_config(CONFIG_PATH).track["phase_id"] == GMA1B_PHASE_ID


def test_41_cli_default_macro_command_does_not_access_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network boundary should not be called in offline-safe mode")

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(
        "market_strats.global_multi_asset.gma1b_macro_cash.fetch_fred_json",
        fail_network,
    )
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
    ])
    assert exit_code == 0


def test_42_cli_live_missing_credential_fails_without_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live",
    ])
    captured = capsys.readouterr().out
    assert exit_code == 2
    assert "gma1b_live_data_incomplete" in captured
    assert "api_key" not in captured.lower()
    assert "FRED_API_KEY" not in captured


def test_43_cli_live_passes_explicit_live_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def fake_run(config, *, live: bool = False):
        calls.append(live)
        return GMA1BResult(
            decision="gma1b_feasible_proceed_to_replay_foundation",
            warnings=[],
            canonical_hash="abc",
            live_retrieval_status="official_fred_alfred_live_retrieval_complete",
        )

    monkeypatch.setattr("market_strats.global_multi_asset.cli.run_gma1b_macro_cash_foundation", fake_run)
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live",
    ])
    assert exit_code == 0
    assert calls == [True]


def test_44_cli_unknown_live_flag_fails() -> None:
    with pytest.raises(SystemExit):
        gma_main([
            "--config",
            str(CONFIG_PATH),
            "build-macro-cash-foundation",
            "--live-now",
        ])


def test_45_fixture_snapshots_cannot_be_accepted_as_live_evidence(
    config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    run_gma1b_macro_cash_foundation(config, live=True)
    selection = pd.read_csv(REPORT_DIR / "source_snapshot_selection.csv")
    assert not selection["selected_as_live_evidence"].astype(bool).any()
    assert not selection["fixture_snapshots_accepted_as_live_evidence"].astype(bool).any()


def test_46_live_reports_do_not_store_credential_name(config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    run_gma1b_macro_cash_foundation(config, live=True)
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in REPORT_DIR.rglob("*")
        if path.is_file()
    )
    assert "FRED_API_KEY" not in text
    assert "api_key=" not in text.lower()
    assert "SECRET" not in text


class _FakeResponse:
    def __init__(self, payload: bytes, content_type: str = "application/json"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


def _http_error(status: int, body: bytes, *, content_type: str = "application/json") -> HTTPError:
    return HTTPError(
        url="https://api.stlouisfed.org/fred/series/observations?api_key=SECRET",
        code=status,
        msg="provider error",
        hdrs={"Content-Type": content_type},
        fp=BytesIO(body),
    )


def test_47_metadata_request_includes_json_and_exact_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        return _FakeResponse(b'{"seriess":[{"id":"DGS3MO","title":"3M","units":"Percent"}]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    payload = fetch_fred_json(
        "series",
        {"series_id": "DGS3MO"},
        api_key="SECRET",
        timeout_seconds=1,
        series_id="DGS3MO",
        request_stage="metadata",
    )
    assert b"seriess" in payload
    assert seen[0].startswith("https://api.stlouisfed.org/fred/series?")
    assert "series_id=DGS3MO" in seen[0]
    assert "api_key=SECRET" in seen[0]
    assert "file_type=json" in seen[0]


def test_48_observations_request_includes_json_and_expected_parameters() -> None:
    url = fred_request_url(
        "series/observations",
        {
            "series_id": "DGS3MO",
            "observation_start": "1900-01-01",
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "limit": 1,
            "offset": 0,
            "sort_order": "asc",
        },
        api_key="SECRET",
    )
    assert url.startswith("https://api.stlouisfed.org/fred/series/observations?")
    for key in [
        "series_id=DGS3MO",
        "observation_start=1900-01-01",
        "realtime_start=1776-07-04",
        "realtime_end=9999-12-31",
        "limit=1",
        "sort_order=asc",
        "api_key=SECRET",
        "file_type=json",
    ]:
        assert key in url


def test_49_xml_when_json_expected_is_response_format_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "market_strats.global_multi_asset.gma1b_macro_cash.urlopen",
        lambda url, timeout: _FakeResponse(b"<error>xml</error>", "text/xml"),
    )
    with pytest.raises(Exception) as excinfo:
        _fetch_fred_payload(
            "series",
            {"series_id": "DGS3MO"},
            api_key="SECRET",
            timeout_seconds=1,
            series_id="DGS3MO",
            request_stage="metadata",
        )
    assert excinfo.value.incident.error_category == "response_format_failure"


def test_50_http_400_captured_not_retried_and_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        raise _http_error(400, b'{"error_code":"400","error_message":"bad api_key=SECRET"}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    with pytest.raises(Exception) as excinfo:
        fetch_fred_json(
            "series/observations",
            {"series_id": "DGS3MO"},
            api_key="SECRET",
            timeout_seconds=1,
            series_id="DGS3MO",
            request_stage="observations_current",
            retry_count=2,
        )
    incident = excinfo.value.incident
    assert calls == 1
    assert incident.http_status == 400
    assert incident.error_category == "invalid_request"
    assert not incident.retryable
    assert "SECRET" not in incident.redacted_provider_message


def test_51_http_401_403_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        raise _http_error(401, b'{"error_message":"unauthorized"}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    with pytest.raises(Exception) as excinfo:
        fetch_fred_json(
            "series",
            {"series_id": "DGS3MO"},
            api_key="SECRET",
            timeout_seconds=1,
            series_id="DGS3MO",
            request_stage="metadata",
            retry_count=2,
        )
    assert calls == 1
    assert excinfo.value.incident.error_category == "credential_or_permission_failure"


def test_52_http_429_and_500_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_error(429, b'{"error_message":"rate"}')
        if calls == 2:
            raise _http_error(500, b'{"error_message":"server"}')
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.time.sleep", lambda seconds: None)
    payload = fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO"},
        api_key="SECRET",
        timeout_seconds=1,
        series_id="DGS3MO",
        request_stage="observations_current",
        retry_count=2,
    )
    assert calls == 3
    assert b"observations" in payload


def test_53_timeout_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("timed out")
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.time.sleep", lambda seconds: None)
    fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO"},
        api_key="SECRET",
        timeout_seconds=1,
        series_id="DGS3MO",
        request_stage="observations_current",
        retry_count=1,
    )
    assert calls == 2


def test_54_json_and_xml_provider_errors_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_json(url, timeout):
        raise _http_error(400, b'{"error_code":"E","error_message":"bad api_key=SECRET"}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_json)
    with pytest.raises(Exception) as excinfo:
        fetch_fred_json("series", {"series_id": "DGS3MO"}, api_key="SECRET", timeout_seconds=1, series_id="DGS3MO", request_stage="metadata")
    assert excinfo.value.incident.provider_error_code == "E"
    assert "SECRET" not in excinfo.value.incident.redacted_provider_message

    def fake_xml(url, timeout):
        raise _http_error(400, b'<error code="X"><message>bad api_key=SECRET</message></error>', content_type="text/xml")

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_xml)
    with pytest.raises(Exception) as xml_exc:
        fetch_fred_json("series", {"series_id": "DGS3MO"}, api_key="SECRET", timeout_seconds=1, series_id="DGS3MO", request_stage="metadata")
    assert xml_exc.value.incident.provider_error_code == "X"
    assert "SECRET" not in xml_exc.value.incident.redacted_provider_message


def test_55_diagnostic_path_parses_success_and_is_ineligible(
    config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "SECRET")

    def fake_urlopen(url, timeout):
        if "/series?" in url:
            return _FakeResponse(b'{"seriess":[{"id":"DGS3MO","title":"3M","units":"Percent","frequency":"Daily"}]}')
        return _FakeResponse(
            b'{"count":1,"observations":[{"date":"2024-01-02","value":"5.1","realtime_start":"2024-01-02","realtime_end":"9999-12-31"}]}'
        )

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live-diagnose",
        "--series-id",
        "DGS3MO",
    ])
    assert exit_code == 0
    smoke = (REPORT_DIR / "diagnostics" / "production_dgs3mo_smoke_test.json").read_text(encoding="utf-8")
    assert '"diagnostic_only": true' in smoke
    assert '"eligible_for_live_canonical_selection": false' in smoke
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert diag.iloc[0]["observations_status"] == "passed"
    assert not bool(diag.iloc[0]["diagnostic_snapshot_eligible"])


def test_56_per_series_diagnostic_continues_after_failure(
    config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "SECRET")

    def fake_urlopen(url, timeout):
        if "series_id=DGS2" in url and "series%2Fobservations" not in url:
            raise _http_error(400, b'{"error_message":"bad"}')
        if "/series?" in url:
            return _FakeResponse(b'{"seriess":[{"id":"OK","title":"OK","units":"Percent"}]}')
        return _FakeResponse(b'{"count":1,"observations":[{"date":"2024-01-02","value":"1","realtime_start":"2024-01-02","realtime_end":"9999-12-31"}]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live-diagnose-all",
    ])
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert set(diag["series_id"]).issuperset({"DGS3MO", "DGS2"})
    assert "failed" in set(diag["metadata_status"])
    assert "passed" in set(diag["observations_status"])


def test_57_unknown_diagnostic_series_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "SECRET")
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live-diagnose",
        "--series-id",
        "NOT_REGISTERED",
    ])
    assert exit_code == 2
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert diag.iloc[0]["failure_category"] == "invalid_series"


def test_58_retrieval_classification_assigns_daily_and_vintage_series() -> None:
    assert retrieval_classification_for_series("DGS3MO") == "current_history_with_availability"
    assert retrieval_classification_for_series("DGS2") == "current_history_with_availability"
    assert retrieval_classification_for_series("CPIAUCSL") == "full_vintage_history_required"
    assert retrieval_classification_for_series("UNRATE") == "full_vintage_history_required"
    assert retrieval_classification_for_series("INDPRO") == "full_vintage_history_required"
    assert retrieval_classification_for_series("T10Y2Y") == "derived_point_in_time_series"
    assert retrieval_classification_for_series("STLFSI4") == "current_history_with_availability"


def test_59_dgs3mo_current_history_does_not_call_exhaustive_vintage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        return _FakeResponse(
            b'{"count":1,"observations":[{"date":"2024-01-02","value":"5.1","realtime_start":"2024-01-02","realtime_end":"9999-12-31"}]}'
        )

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    rows, info = _fetch_observations_by_classification(
        "DGS3MO",
        api_key="SECRET",
        timeout_seconds=1,
        retry_count=0,
        limit=1,
    )
    assert rows
    assert info["retrieval_classification"] == "current_history_with_availability"
    assert all("series/vintagedates" not in url for url in seen)
    assert all("realtime_start=1776-07-04" not in url for url in seen)
    assert all("realtime_end=9999-12-31" not in url for url in seen)


def test_60_full_vintage_series_calls_vintage_dates_and_explicit_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    dates = [f"2020-01-{day:02d}" for day in range(1, 4)]

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": 3, "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1", "realtime_start": dates[0], "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key="SECRET",
        timeout_seconds=1,
        retry_count=0,
        limit=1,
    )
    assert rows
    assert any("series/vintagedates" in url for url in seen)
    observation_urls = [url for url in seen if "series/observations" in url]
    assert observation_urls
    assert "vintage_dates=" in observation_urls[0]
    assert "output_type=3" in observation_urls[0]
    assert "output_type=4" not in observation_urls[0]
    assert info["vintage_date_count"] == 3
    assert info["vintage_chunk_count"] == 1


def json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


def test_61_vintage_chunk_sizes_for_5046_dates() -> None:
    chunks = chunk_vintage_dates([f"2000-01-{idx:04d}" for idx in range(5046)])
    assert [len(chunk) for chunk in chunks] == [2000, 2000, 1046]
    assert all(len(chunk) <= 2000 for chunk in chunks)


def test_62_merge_vintage_chunks_dedupes_identical_and_rejects_conflicts() -> None:
    row = {"series_id": "CPIAUCSL", "date": "2020-01-01", "value": "1", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"}
    merged = merge_vintage_observation_chunks([[row], [dict(row)]])
    assert len(merged) == 1
    conflict = dict(row)
    conflict["value"] = "2"
    with pytest.raises(ValueError, match="conflicting_duplicate"):
        merge_vintage_observation_chunks([[row], [conflict]])


def test_63_all_requested_vintage_chunks_are_accounted_for(monkeypatch: pytest.MonkeyPatch) -> None:
    # Use realistic ISO date strings so that URI measurement works correctly.
    dates = [f"2020-{(idx // 31) + 1:02d}-{(idx % 28) + 1:02d}" for idx in range(2001)]
    seen_observation_urls: list[str] = []

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        seen_observation_urls.append(url)
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    rows, info = _fetch_observations_by_classification(
        "UNRATE",
        api_key="SECRET",
        timeout_seconds=1,
        retry_count=0,
        limit=1,
    )
    assert rows
    # URI-aware chunker: every chunk must be <= 400 dates AND <= 7000 uri bytes.
    assert info["vintage_chunk_count"] >= 1
    for size_str in info["vintage_chunk_sizes"].split(";"):
        assert int(size_str) <= FRED_SAFE_VINTAGE_DATES_PER_REQUEST
    for uri_str in info["vintage_chunk_uri_bytes"].split(";"):
        assert int(uri_str) <= FRED_MAX_ENCODED_REQUEST_URI_BYTES
    # output_type=3 authoritative chunks + 1 type2 + 1 type4
    ot3_chunk_count = info["output_type_3_request_count"]
    total_obs_urls = [u for u in seen_observation_urls if "series/observations" in u]
    assert len(total_obs_urls) == ot3_chunk_count + 2
    output_types_seen = [
        url.split("output_type=")[1].split("&")[0]
        for url in total_obs_urls
        if "output_type=" in url
    ]
    # First ot3_chunk_count URLs must be output_type=3 (authoritative)
    assert all(t == "3" for t in output_types_seen[:ot3_chunk_count])
    assert set(output_types_seen) == {"3", "2", "4"}


def test_64_diagnose_all_duration_limit_is_bounded(config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "SECRET")
    result = run_gma1b_live_diagnostic(config, all_series=True, total_duration_limit_seconds=-1)
    assert result.decision == "gma1b_live_diagnostic_failed"
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert bool(diag.iloc[0]["cancelled"])
    assert diag.iloc[0]["failure_category"] == "diagnostic_duration_limit_exceeded"


def test_65_cancellation_preserves_completed_rows(config, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_diagnose(config, *, series_id, api_key, diagnostic_run_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ({
                "series_id": series_id,
                "retrieval_classification": "current_history_with_availability",
                "metadata_status": "passed",
                "metadata_http_status": 200,
                "observations_status": "passed",
                "observations_http_status": 200,
                "row_count": 1,
                "first_observation_date": "2024-01-01",
                "last_observation_date": "2024-01-01",
                "vintage_status": "not_requested_current_history",
                "vintage_date_count": 0,
                "vintage_chunk_count": 0,
                "vintage_chunk_sizes": "",
                "failure_stage": "",
                "failure_category": "",
                "retryable": False,
                "diagnostic_snapshot_eligible": False,
                "started_at_utc": "2024-01-01T00:00:00+00:00",
                "completed_at_utc": "2024-01-01T00:00:01+00:00",
                "elapsed_seconds": 1,
                "request_count": 2,
                "retry_count": 0,
                "cancelled": False,
            }, [], {})
        raise KeyboardInterrupt

    monkeypatch.setenv("FRED_API_KEY", "SECRET")
    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash._diagnose_one_series", fake_diagnose)
    result = run_gma1b_live_diagnostic(config, all_series=True)
    assert result.decision == "gma1b_live_diagnostic_failed"
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert len(diag) == 1
    assert diag.iloc[0]["series_id"] == "DGS3MO"
    assert bool(diag.iloc[0]["cancelled"])


def test_66_dgs3mo_current_request_matches_approved_parameter_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        return _FakeResponse(
            json_bytes({
                "count": 1,
                "observations": [
                    {
                        "date": "2024-01-02",
                        "value": "5.1",
                        "realtime_start": "2024-01-02",
                        "realtime_end": "9999-12-31",
                    }
                ],
            })
        )

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    rows = _fetch_current_fred_observations(
        "DGS3MO",
        api_key="SECRET",
        timeout_seconds=30,
        retry_count=0,
        diagnostic_run_id="test_run",
    )
    assert rows
    assert seen
    url = seen[0]
    for expected in [
        "/series/observations?",
        "series_id=DGS3MO",
        "file_type=json",
        "limit=100000",
        "offset=0",
        "sort_order=asc",
    ]:
        assert expected in url
    for forbidden in [
        "observation_start",
        "observation_end",
        "realtime_start",
        "realtime_end",
        "vintage_dates",
        "output_type",
    ]:
        assert forbidden not in url


def test_67_urlopen_receives_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_timeout: list[int] = []

    def fake_urlopen(url, timeout):
        seen_timeout.append(timeout)
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO"},
        api_key="SECRET",
        timeout_seconds=30,
        series_id="DGS3MO",
        request_stage="observations_current",
    )
    assert seen_timeout == [30]


def test_68_request_plan_written_before_network_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics_dir = tmp_path / "diagnostics"
    plan_path = diagnostics_dir / "production_request_plan.json"

    def fake_urlopen(url, timeout):
        assert plan_path.exists()
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO", "limit": 100000, "offset": 0, "sort_order": "asc"},
        api_key="SECRET",
        timeout_seconds=30,
        series_id="DGS3MO",
        request_stage="observations_current",
        diagnostics_dir=diagnostics_dir,
        request_number=2,
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["diagnostic_only"] is True
    assert plan["eligible_for_live_canonical_selection"] is False
    assert plan["request_number"] == 2


def test_69_request_plan_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostics_dir = tmp_path / "diagnostics"

    def fake_urlopen(url, timeout):
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO", "limit": 100000, "offset": 0, "sort_order": "asc"},
        api_key="SECRET",
        timeout_seconds=30,
        series_id="DGS3MO",
        request_stage="observations_current",
        diagnostics_dir=diagnostics_dir,
    )
    text = (diagnostics_dir / "production_request_plan.json").read_text(encoding="utf-8")
    plan = json.loads(text)
    assert "SECRET" not in text
    assert "api_key=" not in text.lower()
    assert plan["non_secret_parameters"]["api_key_present"] is True
    assert "api_key" not in plan["non_secret_parameters"]


def test_70_progress_is_emitted_before_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def fake_urlopen(url, timeout):
        assert messages
        assert messages[0].startswith("[DGS3MO] observations request started")
        return _FakeResponse(b'{"observations":[]}')

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    fetch_fred_json(
        "series/observations",
        {"series_id": "DGS3MO", "limit": 100000, "offset": 0, "sort_order": "asc"},
        api_key="SECRET",
        timeout_seconds=30,
        series_id="DGS3MO",
        request_stage="observations_current",
        progress_callback=messages.append,
    )


def test_71_timeout_updates_smoke_report_and_fails_closed(
    config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "SECRET")

    def fake_urlopen(url, timeout):
        if "/series?" in url:
            return _FakeResponse(b'{"seriess":[{"id":"DGS3MO","title":"3M","units":"Percent"}]}')
        raise TimeoutError("timed out")

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.time.sleep", lambda seconds: None)
    exit_code = gma_main([
        "--config",
        str(CONFIG_PATH),
        "build-macro-cash-foundation",
        "--live-diagnose",
        "--series-id",
        "DGS3MO",
    ])
    assert exit_code == 2
    smoke = json.loads(
        (REPORT_DIR / "diagnostics" / "production_dgs3mo_smoke_test.json").read_text(
            encoding="utf-8"
        )
    )
    assert smoke["observations_status"] == "failed"
    assert smoke["failure_category"] == "timeout"
    diag = pd.read_csv(REPORT_DIR / "diagnostics" / "per_series_live_diagnostic.csv")
    assert diag.iloc[0]["observations_status"] == "failed"
    assert diag.iloc[0]["failure_category"] == "timeout"


def test_72_timeout_retry_count_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_urlopen(url, timeout):
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.time.sleep", lambda seconds: None)
    with pytest.raises(Exception) as excinfo:
        fetch_fred_json(
            "series/observations",
            {"series_id": "DGS3MO"},
            api_key="SECRET",
            timeout_seconds=30,
            series_id="DGS3MO",
            request_stage="observations_current",
            retry_count=2,
        )
    assert calls == 3
    assert excinfo.value.incident.error_category == "timeout"


# ---------------------------------------------------------------------------
# GMA-1B-LV2 focused tests: corrected full-vintage output-type semantics
# ---------------------------------------------------------------------------


def test_73_full_vintage_retrieval_uses_output_type_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authoritative full-vintage retrieval must use output_type=3."""
    seen: list[str] = []
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        # output_type=2 and output_type=4 sub-requests also hit observations
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1", "realtime_start": dates[0], "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=1,
    )
    obs_urls = [u for u in seen if "series/observations" in u]
    assert any("output_type=3" in u for u in obs_urls), "output_type=3 must appear in observation requests"
    assert info["output_type_3_status"] == "used_as_authoritative_revision_event_stream"


def test_74_output_type_4_is_not_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """output_type=4 must not appear as the first (authoritative) observation request."""
    seen: list[str] = []
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1", "realtime_start": dates[0], "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _fetch_observations_by_classification(
        "UNRATE", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=1,
    )
    obs_urls = [u for u in seen if "series/observations" in u]
    # The first authoritative observation request must NOT be output_type=4
    assert obs_urls, "at least one observation request must be made"
    assert "output_type=4" not in obs_urls[0], (
        "output_type=4 must not be the authoritative (first) observation request"
    )


def test_75_output_type_3_captures_initial_events() -> None:
    """_derive_revision_event_counts counts the first event per obs_date as initial."""
    events = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
    ]
    total, initial, later = _derive_revision_event_counts(events)
    assert total == 1
    assert initial == 1
    assert later == 0


def test_76_output_type_3_captures_later_revisions() -> None:
    """_derive_revision_event_counts counts subsequent events as later revisions."""
    events = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        {"date": "2020-01-01", "value": "1.1", "realtime_start": "2020-03-01", "realtime_end": "9999-12-31"},
        {"date": "2020-01-01", "value": "1.2", "realtime_start": "2020-04-01", "realtime_end": "9999-12-31"},
    ]
    total, initial, later = _derive_revision_event_counts(events)
    assert total == 3
    assert initial == 1
    assert later == 2


def test_77_revision_sequence_is_deterministic() -> None:
    """Events with the same obs_date but shuffled input order produce a stable sequence."""
    events_a = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        {"date": "2020-01-01", "value": "1.1", "realtime_start": "2020-03-01", "realtime_end": "9999-12-31"},
    ]
    events_b = list(reversed(events_a))
    result_a = _derive_revision_event_counts(events_a)
    result_b = _derive_revision_event_counts(events_b)
    assert result_a == result_b


def test_78_later_revision_cannot_leak_backward(tiny_canonical: pd.DataFrame) -> None:
    """A revision available only at time T2 must not appear in an as-of query for T1 < T2."""
    before = query_point_in_time(tiny_canonical, "cpi", "2024-02-15T00:00:00Z")
    after = query_point_in_time(tiny_canonical, "cpi", "2024-03-02T00:00:00Z")
    assert before["realtime_start"] < after["realtime_start"], (
        "later revision realtime_start must be strictly later than initial"
    )
    assert before["value"] != after["value"], "leaked revision would make these equal"


def test_79_output_type_2_bounded_validation_matches_reconstruction() -> None:
    """_validate_output_type_2_against_reconstruction passes when snapshot agrees with events."""
    # Build revision events
    events = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        {"date": "2020-01-01", "value": "1.1", "realtime_start": "2020-03-01", "realtime_end": "9999-12-31"},
    ]
    vintage_dates = ["2020-02-01", "2020-03-01"]

    # Patch _fetch_fred_observations_for_vintage_dates to return a type-2-like snapshot
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    orig = mod._fetch_fred_observations_for_vintage_dates

    def fake_fetch(series_id, *, vintage_dates, output_type, **kwargs):
        assert output_type == 2, "bounded validation must use output_type=2"
        return [
            {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
            {"date": "2020-01-01", "value": "1.1", "realtime_start": "2020-03-01", "realtime_end": "9999-12-31"},
        ]

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    try:
        result = _validate_output_type_2_against_reconstruction(
            "CPIAUCSL",
            vintage_dates=vintage_dates,
            revision_events=events,
            api_key="SECRET",
            timeout_seconds=1,
        )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    assert result["output_type_2_validation_status"] == "passed"
    assert result["output_type_2_mismatch_count"] == 0


def test_80_output_type_2_mismatch_fails_closed() -> None:
    """_validate_output_type_2_against_reconstruction fails when snapshot disagrees with events."""
    events = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
    ]
    vintage_dates = ["2020-02-01"]

    import market_strats.global_multi_asset.gma1b_macro_cash as mod
    orig = mod._fetch_fred_observations_for_vintage_dates

    def fake_fetch(series_id, *, vintage_dates, output_type, **kwargs):
        # Return a different value — simulating a mismatch
        return [
            {"date": "2020-01-01", "value": "9.9", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        ]

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    try:
        result = _validate_output_type_2_against_reconstruction(
            "CPIAUCSL",
            vintage_dates=vintage_dates,
            revision_events=events,
            api_key="SECRET",
            timeout_seconds=1,
        )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    assert result["output_type_2_validation_status"] == "failed"
    assert result["output_type_2_mismatch_count"] > 0


def test_81_output_type_4_may_crosscheck_initial_values_only() -> None:
    """_crosscheck_output_type_4_initial_releases uses output_type=4 only and passes when values agree."""
    events = [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        {"date": "2020-01-01", "value": "1.1", "realtime_start": "2020-03-01", "realtime_end": "9999-12-31"},
    ]

    import market_strats.global_multi_asset.gma1b_macro_cash as mod
    orig = mod._fetch_fred_observations_for_vintage_dates
    seen_output_types: list[int] = []

    def fake_fetch(series_id, *, vintage_dates, output_type, **kwargs):
        seen_output_types.append(output_type)
        # output_type=4 returns only initial values
        return [
            {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-02-01", "realtime_end": "9999-12-31"},
        ]

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    try:
        result = _crosscheck_output_type_4_initial_releases(
            "CPIAUCSL",
            initial_release_vintages=["2020-02-01", "2020-03-01"],
            revision_events=events,
            api_key="SECRET",
            timeout_seconds=1,
        )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    assert seen_output_types == [4], "crosscheck must use exactly output_type=4"
    assert result["output_type_4_crosscheck_status"] == "passed"


def test_82_cpi_diagnostic_reports_revision_event_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CPIAUCSL retrieval info must contain revision_event_count, initial and later fields."""
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 2,
            "observations": [
                {"date": "2019-12-01", "value": "260.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
                {"date": "2019-12-01", "value": "260.1", "realtime_start": dates[1], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=10,
    )
    assert "revision_event_count" in info
    assert "initial_release_event_count" in info
    assert "later_revision_event_count" in info
    assert info["revision_event_count"] >= 1


def test_83_unrate_uses_corrected_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNRATE must use output_type=3 as the authoritative vintage source."""
    seen: list[str] = []
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "4.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "UNRATE", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=1,
    )
    obs_urls = [u for u in seen if "series/observations" in u]
    assert any("output_type=3" in u for u in obs_urls), "UNRATE must use output_type=3"
    assert info["retrieval_classification"] == "full_vintage_history_required"


def test_84_indpro_uses_corrected_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INDPRO must use output_type=3 as the authoritative vintage source."""
    seen: list[str] = []
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "102.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "INDPRO", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=1,
    )
    obs_urls = [u for u in seen if "series/observations" in u]
    assert any("output_type=3" in u for u in obs_urls), "INDPRO must use output_type=3"
    assert info["retrieval_classification"] == "full_vintage_history_required"


def test_85_dgs3mo_current_history_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DGS3MO current-history path must not call vintagedates or use output_type."""
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2024-01-02", "value": "5.1", "realtime_start": "2024-01-02", "realtime_end": "9999-12-31"}
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "DGS3MO", api_key="SECRET", timeout_seconds=1, retry_count=0, limit=1,
    )
    assert all("series/vintagedates" not in u for u in seen), "DGS3MO must not call vintagedates"
    assert all("output_type" not in u for u in seen), "DGS3MO must not use output_type parameter"
    assert info["retrieval_classification"] == "current_history_with_availability"
    assert info["output_type_3_status"] == "not_applicable_current_history"


def test_86_vintage_chunking_capped_at_2000() -> None:
    """chunk_vintage_dates must never produce a chunk larger than 2,000."""
    dates = [f"2000-{idx:06d}" for idx in range(6001)]
    chunks = chunk_vintage_dates(dates)
    assert all(len(c) <= 2000 for c in chunks)
    assert sum(len(c) for c in chunks) == len(set(dates))


def test_87_no_accepted_live_hash_created_during_diagnostics(config) -> None:
    """run_gma1b_macro_cash_foundation must not write an accepted live hash in fixture mode."""
    result = run_gma1b_macro_cash_foundation(config)
    # In fixture/offline mode: live_complete=False so accepted_live_canonical_hash must be empty.
    manifest_path = REPORT_DIR / "canonical_macro_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["accepted_live_canonical_hash"] == "", (
        "no accepted live hash must be written unless live retrieval is complete"
    )
    assert result.live_retrieval_status != "official_fred_alfred_live_retrieval_complete"


def test_88_select_bounded_validation_vintages_covers_required_points() -> None:
    """_select_bounded_validation_vintages must return at least earliest, initial and latest."""
    # Thin list
    sample = _select_bounded_validation_vintages(["2020-01-01", "2020-02-01", "2020-03-01"])
    assert "2020-01-01" in sample  # earliest
    assert "2020-03-01" in sample  # latest
    assert len(sample) <= 4

    # Single date
    single = _select_bounded_validation_vintages(["2020-01-01"])
    assert single == ["2020-01-01"]

    # Empty
    empty = _select_bounded_validation_vintages([])
    assert empty == []


# ---------------------------------------------------------------------------
# GMA-1B-LU focused tests: URI-length-aware vintage request chunking
# ---------------------------------------------------------------------------

_REAL_DATES_1000 = [f"20{y:02d}-{m:02d}-01" for y in range(0, 34) for m in range(1, 13)][:1000]
_SHORT_KEY = "A" * 32  # 32-char key typical of FRED API keys


def test_89_1000_dates_do_not_form_one_oversized_uri() -> None:
    """1,000 vintage dates with a realistic API key must be split into multiple URI-safe chunks."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    assert len(chunks) > 1, (
        "1,000 vintage dates must not form a single URI-safe chunk"
    )


def test_90_every_chunk_at_most_400_dates() -> None:
    """chunk_vintage_dates_uri_aware must never produce a chunk with more than 400 dates."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    for chunk in chunks:
        assert len(chunk) <= FRED_SAFE_VINTAGE_DATES_PER_REQUEST


def test_91_every_chunk_at_most_2000_dates() -> None:
    """chunk_vintage_dates_uri_aware must also satisfy the hard 2,000-date provider limit."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    for chunk in chunks:
        assert len(chunk) <= 2000


def test_92_every_encoded_uri_at_most_7000_bytes() -> None:
    """Every produced chunk must have an encoded URI at or below 7,000 bytes."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    for chunk in chunks:
        measured = _measure_vintage_request_uri_bytes(
            "series/observations",
            series_id="CPIAUCSL",
            api_key=_SHORT_KEY,
            output_type=3,
            limit=100000,
            offset=0,
            sort_order="asc",
            vintage_dates_chunk=chunk,
        )
        assert measured <= FRED_MAX_ENCODED_REQUEST_URI_BYTES, (
            f"Chunk of {len(chunk)} dates has encoded URI {measured} bytes > budget"
        )


def test_93_exact_uri_measurement_includes_endpoint() -> None:
    """_measure_vintage_request_uri_bytes must include the full FRED API root and endpoint path."""
    from market_strats.global_multi_asset.gma1b_macro_cash import FRED_API_ROOT
    dates = ["2020-01-01"]
    measured = _measure_vintage_request_uri_bytes(
        "series/observations",
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
        output_type=3,
        limit=100000,
        offset=0,
        sort_order="asc",
        vintage_dates_chunk=dates,
    )
    # At minimum the URL must contain the base path.
    base_len = len(FRED_API_ROOT.encode("utf-8"))
    assert measured > base_len


def test_94_exact_uri_measurement_includes_api_key_length() -> None:
    """A longer API key must produce a strictly larger encoded URI byte count."""
    dates = ["2020-01-01"]
    short_key = "A" * 10
    long_key = "A" * 64
    short_bytes = _measure_vintage_request_uri_bytes(
        "series/observations",
        series_id="CPIAUCSL",
        api_key=short_key,
        output_type=3,
        limit=100000,
        offset=0,
        sort_order="asc",
        vintage_dates_chunk=dates,
    )
    long_bytes = _measure_vintage_request_uri_bytes(
        "series/observations",
        series_id="CPIAUCSL",
        api_key=long_key,
        output_type=3,
        limit=100000,
        offset=0,
        sort_order="asc",
        vintage_dates_chunk=dates,
    )
    assert long_bytes - short_bytes == 64 - 10, (
        "URI byte difference must equal the difference in API-key lengths"
    )


def test_95_api_key_value_absent_from_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API-key value must not appear in any diagnostic info dict produced by the retrieval."""
    secret = "SUPER_SECRET_KEY_DO_NOT_LOG"
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key=secret,
        timeout_seconds=1,
    )
    for key, val in info.items():
        assert secret not in str(val), (
            f"API-key value must not appear in info field '{key}'"
        )


def test_96_deterministic_greedy_chunking_same_input_same_output() -> None:
    """Same inputs must always produce identical chunks (determinism)."""
    result_a = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    result_b = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    assert result_a == result_b


def test_97_no_date_is_omitted() -> None:
    """All input dates must appear exactly once across all output chunks."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    flat = [d for chunk in chunks for d in chunk]
    assert sorted(flat) == sorted(set(_REAL_DATES_1000))


def test_98_no_date_is_duplicated() -> None:
    """No date must appear in more than one chunk."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    flat = [d for chunk in chunks for d in chunk]
    assert len(flat) == len(set(flat))


def test_99_date_ordering_is_preserved() -> None:
    """Dates within every chunk must be sorted in ascending order."""
    chunks = chunk_vintage_dates_uri_aware(
        _REAL_DATES_1000,
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
    )
    for chunk in chunks:
        assert chunk == sorted(chunk)


def test_100_date_exceeding_uri_budget_begins_new_chunk() -> None:
    """Adding a date that would breach the URI budget must start a new chunk."""
    # Use a tiny budget so that even two dates require separate chunks.
    date_a = "2020-01-01"
    date_b = "2020-02-01"
    # Find the single-date byte count.
    single_bytes = _measure_vintage_request_uri_bytes(
        "series/observations",
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
        output_type=3,
        limit=100000,
        offset=0,
        sort_order="asc",
        vintage_dates_chunk=[date_a],
    )
    # Set budget just barely above single but below two-date size.
    two_bytes = _measure_vintage_request_uri_bytes(
        "series/observations",
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
        output_type=3,
        limit=100000,
        offset=0,
        sort_order="asc",
        vintage_dates_chunk=[date_a, date_b],
    )
    tight_budget = single_bytes  # single fits; two does not
    assert two_bytes > tight_budget, "test setup: two dates must exceed tight budget"

    chunks = chunk_vintage_dates_uri_aware(
        [date_a, date_b],
        series_id="CPIAUCSL",
        api_key=_SHORT_KEY,
        uri_byte_budget=tight_budget,
    )
    assert len(chunks) == 2, (
        "Each date must be in its own chunk when two-date URI exceeds budget"
    )


def test_101_single_date_overflow_fails_closed() -> None:
    """chunk_vintage_dates_uri_aware must raise ValueError if one date already exceeds budget."""
    with pytest.raises(ValueError, match="single_vintage_date_exceeds_uri_budget"):
        chunk_vintage_dates_uri_aware(
            ["2020-01-01"],
            series_id="CPIAUCSL",
            api_key=_SHORT_KEY,
            uri_byte_budget=10,  # impossibly small
        )


def test_102_output_type_3_uses_uri_aware_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    """output_type=3 authoritative requests must come from URI-aware chunks (<= 400 dates)."""
    dates = [f"20{y:02d}-{m:02d}-01" for y in range(0, 6) for m in range(1, 13)]  # 72 dates
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2000-01-01", "value": "1.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key=_SHORT_KEY,
        timeout_seconds=1,
    )
    obs_3_urls = [u for u in seen if "output_type=3" in u]
    for url in obs_3_urls:
        vintage_dates_param = [
            p.split("=", 1)[1] for p in url.split("&") if p.startswith("vintage_dates=")
        ]
        if vintage_dates_param:
            n_dates = len(vintage_dates_param[0].split("%2C"))
            assert n_dates <= FRED_SAFE_VINTAGE_DATES_PER_REQUEST


def test_103_output_type_2_uses_uri_aware_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """output_type=2 validation requests must not violate the URI-byte budget."""
    dates = [f"2020-{m:02d}-01" for m in range(1, 5)]  # 4 dates - bounded sample
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key=_SHORT_KEY,
        timeout_seconds=1,
    )
    type2_urls = [u for u in seen if "output_type=2" in u]
    assert type2_urls, "output_type=2 validation request must be made"
    for url in type2_urls:
        assert len(url.encode("utf-8")) <= FRED_MAX_ENCODED_REQUEST_URI_BYTES


def test_104_output_type_4_uses_uri_aware_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """output_type=4 crosscheck requests must not violate the URI-byte budget."""
    dates = [f"2020-{m:02d}-01" for m in range(1, 5)]
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 1,
            "observations": [
                {"date": "2020-01-01", "value": "1.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key=_SHORT_KEY,
        timeout_seconds=1,
    )
    type4_urls = [u for u in seen if "output_type=4" in u]
    assert type4_urls, "output_type=4 crosscheck request must be made"
    for url in type4_urls:
        assert len(url.encode("utf-8")) <= FRED_MAX_ENCODED_REQUEST_URI_BYTES


def _make_414_incident(series_id: str = "CPIAUCSL"):
    """Build a minimal ProviderRequestError wrapping an HTTP-414 incident."""
    from market_strats.global_multi_asset.gma1b_macro_cash import (
        ProviderRequestError,
        ProviderRequestIncident,
    )
    incident = ProviderRequestIncident(
        diagnostic_run_id="test",
        series_id=series_id,
        request_stage="observations_vintage",
        endpoint="series/observations",
        http_method="GET",
        parameter_names="api_key;file_type;output_type;series_id;vintage_dates",
        http_status=414,
        provider_error_code="414",
        redacted_provider_message="Request-URI Too Long",
        exception_type="HTTPError",
        error_category="request_uri_too_long",
        retryable=False,
        response_content_type="text/html",
    )
    return ProviderRequestError(incident)


def test_105_http_414_does_not_retry_identical_request() -> None:
    """_fetch_vintage_chunk_with_414_recovery must not call the identical URL twice on 414."""
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    call_payloads: list[list[str]] = []
    orig = mod._fetch_fred_observations_for_vintage_dates

    def fake_fetch(series_id, *, vintage_dates, **kwargs):
        call_payloads.append(list(vintage_dates))
        raise _make_414_incident()

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    try:
        with pytest.raises(Exception):
            _fetch_vintage_chunk_with_414_recovery(
                "CPIAUCSL",
                vintage_dates=["2020-01-01"],
                api_key=_SHORT_KEY,
                timeout_seconds=1,
                output_type=3,
                retry_count=0,
                diagnostic_run_id="test",
                limit=100000,
                diagnostics_dir=None,
                progress_callback=None,
                request_number_start=1,
                request_stage="observations_vintage",
            )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    # Identical payload must not appear more than once.
    assert call_payloads.count(["2020-01-01"]) == 1, (
        "414 must not re-submit the identical request"
    )


def test_106_http_414_splits_chunk_into_ordered_halves() -> None:
    """On HTTP 414, _fetch_vintage_chunk_with_414_recovery must split into two ordered halves."""
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    calls: list[list[str]] = []
    orig = mod._fetch_fred_observations_for_vintage_dates

    def fake_fetch(series_id, *, vintage_dates, **kwargs):
        calls.append(list(vintage_dates))
        if len(vintage_dates) > 1:
            raise _make_414_incident()
        return [{"date": "2020-01-01", "value": "1", "realtime_start": vintage_dates[0], "realtime_end": "9999-12-31"}]

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    try:
        rows, acct = _fetch_vintage_chunk_with_414_recovery(
            "CPIAUCSL",
            vintage_dates=["2020-01-01", "2020-02-01"],
            api_key=_SHORT_KEY,
            timeout_seconds=1,
            output_type=3,
            retry_count=0,
            diagnostic_run_id="test",
            limit=100000,
            diagnostics_dir=None,
            progress_callback=None,
            request_number_start=1,
            request_stage="observations_vintage",
        )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    # First call: full two-date chunk (fails with 414).
    assert calls[0] == ["2020-01-01", "2020-02-01"]
    # Subsequent calls: ordered left and right halves.
    assert ["2020-01-01"] in calls
    assert ["2020-02-01"] in calls
    # Both halves must be returned.
    assert len(rows) == 2
    assert acct["uri_414_count"] >= 1
    assert acct["adaptive_rechunk_count"] >= 1


def test_107_adaptive_splitting_preserves_exact_coverage() -> None:
    """After 414 recovery, the union of all half-chunks must equal the original dates."""
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    all_calls: list[list[str]] = []
    orig = mod._fetch_fred_observations_for_vintage_dates

    def fake_fetch(series_id, *, vintage_dates, **kwargs):
        all_calls.append(list(vintage_dates))
        if len(vintage_dates) > 1:
            raise _make_414_incident()
        return [{"date": "2020-01-01", "value": str(vintage_dates[0][-2:]), "realtime_start": vintage_dates[0], "realtime_end": "9999-12-31"}]

    mod._fetch_fred_observations_for_vintage_dates = fake_fetch
    input_dates = [f"2020-{m:02d}-01" for m in range(1, 5)]
    try:
        rows, _acct = _fetch_vintage_chunk_with_414_recovery(
            "CPIAUCSL",
            vintage_dates=input_dates,
            api_key=_SHORT_KEY,
            timeout_seconds=1,
            output_type=3,
            retry_count=0,
            diagnostic_run_id="test",
            limit=100000,
            diagnostics_dir=None,
            progress_callback=None,
            request_number_start=1,
            request_stage="observations_vintage",
        )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    # All successful leaf calls must together cover all input dates exactly.
    leaf_calls = [c for c in all_calls if len(c) == 1]
    covered = sorted(d for call in leaf_calls for d in call)
    assert covered == sorted(input_dates)


def test_108_recursive_splitting_is_bounded() -> None:
    """_fetch_vintage_chunk_with_414_recovery must raise after _MAX_414_SPLIT_DEPTH splits."""
    from market_strats.global_multi_asset.gma1b_macro_cash import (
        ProviderRequestError,
        _MAX_414_SPLIT_DEPTH,
    )
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    orig = mod._fetch_fred_observations_for_vintage_dates

    def always_414(series_id, *, vintage_dates, **kwargs):
        raise _make_414_incident()

    # Feed 2^(_MAX_414_SPLIT_DEPTH+1) dates so bisection runs to max depth.
    n = 2 ** (_MAX_414_SPLIT_DEPTH + 1)
    input_dates = [f"2020-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
    mod._fetch_fred_observations_for_vintage_dates = always_414
    try:
        with pytest.raises(ProviderRequestError) as exc_info:
            _fetch_vintage_chunk_with_414_recovery(
                "CPIAUCSL",
                vintage_dates=input_dates,
                api_key=_SHORT_KEY,
                timeout_seconds=1,
                output_type=3,
                retry_count=0,
                diagnostic_run_id="test",
                limit=100000,
                diagnostics_dir=None,
                progress_callback=None,
                request_number_start=1,
                request_stage="observations_vintage",
            )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    assert exc_info.value.incident.error_category == "request_uri_too_long"


def test_109_single_date_414_fails_closed() -> None:
    """A single-date chunk returning HTTP 414 must fail closed immediately."""
    from market_strats.global_multi_asset.gma1b_macro_cash import ProviderRequestError
    import market_strats.global_multi_asset.gma1b_macro_cash as mod

    orig = mod._fetch_fred_observations_for_vintage_dates

    def always_414(series_id, *, vintage_dates, **kwargs):
        raise _make_414_incident()

    mod._fetch_fred_observations_for_vintage_dates = always_414
    try:
        with pytest.raises(ProviderRequestError) as exc_info:
            _fetch_vintage_chunk_with_414_recovery(
                "CPIAUCSL",
                vintage_dates=["2020-01-01"],
                api_key=_SHORT_KEY,
                timeout_seconds=1,
                output_type=3,
                retry_count=0,
                diagnostic_run_id="test",
                limit=100000,
                diagnostics_dir=None,
                progress_callback=None,
                request_number_start=1,
                request_stage="observations_vintage",
            )
    finally:
        mod._fetch_fred_observations_for_vintage_dates = orig

    assert exc_info.value.incident.error_category == "request_uri_too_long"


def test_110_request_count_attempted_accurate_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """request_count_attempted must be > 0 even when observations fail after metadata passes."""
    call_count = {"n": 0}

    def fake_urlopen(url, timeout):
        call_count["n"] += 1
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": 2, "vintage_dates": ["2020-01-01", "2020-02-01"]}))
        if "series/observations" in url:
            # Simulate 414 failure.
            from urllib.error import HTTPError
            raise HTTPError(url, 414, "Request-URI Too Long", {}, None)
        return _FakeResponse(json_bytes({"seriess": [{"id": "CPIAUCSL", "title": "CPI", "units": "Index", "frequency": "Monthly", "frequency_short": "M", "seasonal_adjustment": "SA", "observation_start": "1947-01-01", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "BLS"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    row, incidents, _smoke = config.__class__.__new__(config.__class__), [], {}
    # Direct call to _diagnose_one_series.
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, _smoke = _diagnose_one_series(
        config,
        series_id="CPIAUCSL",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_110",
        progress_callback=None,
    )
    assert row.get("request_count_attempted", 0) > 0 or len(incidents) > 0, (
        "At minimum metadata + vintagedates requests must have been attempted"
    )
    assert row.get("observations_status") == "failed"


def test_111_request_count_completed_accurate(monkeypatch: pytest.MonkeyPatch) -> None:
    """request_count_completed must be <= request_count_attempted on failure."""
    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": 2, "vintage_dates": ["2020-01-01", "2020-02-01"]}))
        if "series/observations" in url:
            from urllib.error import HTTPError
            raise HTTPError(url, 414, "Request-URI Too Long", {}, None)
        return _FakeResponse(json_bytes({"seriess": [{"id": "CPIAUCSL", "title": "CPI", "units": "Index", "frequency": "Monthly", "frequency_short": "M", "seasonal_adjustment": "SA", "observation_start": "1947-01-01", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "BLS"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, _smoke = _diagnose_one_series(
        config,
        series_id="CPIAUCSL",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_111",
    )
    attempted = row.get("request_count_attempted", 0)
    completed = row.get("request_count_completed", 0)
    assert completed <= attempted


def test_112_vintage_date_count_survives_observations_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """vintage_date_count must be > 0 in the failure row if vintagedates succeeded."""
    n_dates = 50
    dates = [f"2020-{m:02d}-01" for m in range(1, n_dates + 1)]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": n_dates, "vintage_dates": dates}))
        if "series/observations" in url:
            from urllib.error import HTTPError
            raise HTTPError(url, 414, "Request-URI Too Long", {}, None)
        return _FakeResponse(json_bytes({"seriess": [{"id": "CPIAUCSL", "title": "CPI", "units": "Index", "frequency": "Monthly", "frequency_short": "M", "seasonal_adjustment": "SA", "observation_start": "1947-01-01", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "BLS"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, _smoke = _diagnose_one_series(
        config,
        series_id="CPIAUCSL",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_112",
    )
    assert row.get("vintage_date_count", 0) > 0, (
        "vintage_date_count must be preserved after successful vintagedates retrieval"
    )
    assert row.get("observations_status") == "failed"


def test_113_planned_chunk_data_survives_observations_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """vintage_chunk_count and vintage_chunk_sizes must be > 0 / non-empty after obs failure."""
    dates = [f"2020-{m:02d}-01" for m in range(1, 5)]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        if "series/observations" in url:
            from urllib.error import HTTPError
            raise HTTPError(url, 414, "Request-URI Too Long", {}, None)
        return _FakeResponse(json_bytes({"seriess": [{"id": "CPIAUCSL", "title": "CPI", "units": "Index", "frequency": "Monthly", "frequency_short": "M", "seasonal_adjustment": "SA", "observation_start": "1947-01-01", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "BLS"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, _smoke = _diagnose_one_series(
        config,
        series_id="CPIAUCSL",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_113",
    )
    assert row.get("vintage_chunk_count", 0) >= 1
    assert row.get("vintage_chunk_sizes", "") != ""


def test_114_cpi_revision_event_semantics_remain_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    """CPIAUCSL output_type=3 authoritative stream must correctly count initial and later events."""
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        return _FakeResponse(json_bytes({
            "count": 2,
            "observations": [
                {"date": "2019-12-01", "value": "260.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
                {"date": "2019-12-01", "value": "260.1", "realtime_start": dates[1], "realtime_end": "9999-12-31"},
            ],
        }))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    _rows, info = _fetch_observations_by_classification(
        "CPIAUCSL",
        api_key="SECRET",
        timeout_seconds=1,
        retry_count=0,
        limit=10,
    )
    assert info["initial_release_event_count"] == 1  # one obs_date group
    assert info["later_revision_event_count"] == 1   # one revision


def test_115_dgs3mo_remains_exactly_two_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """DGS3MO must still make exactly 2 HTTP requests in a normal diagnostic run."""
    seen: list[str] = []

    def fake_urlopen(url, timeout):
        seen.append(url)
        if "series/observations" in url:
            return _FakeResponse(json_bytes({
                "count": 1,
                "observations": [
                    {"date": "2024-01-02", "value": "5.1",
                     "realtime_start": "2024-01-02", "realtime_end": "9999-12-31"},
                ],
            }))
        # metadata
        return _FakeResponse(json_bytes({"seriess": [{"id": "DGS3MO", "title": "3-Month Treasury", "units": "Percent", "frequency": "Daily", "frequency_short": "D", "seasonal_adjustment": "Not Seasonally Adjusted", "observation_start": "1982-01-04", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "FRED"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, smoke = _diagnose_one_series(
        config,
        series_id="DGS3MO",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_115",
    )
    assert len(seen) == 2, f"DGS3MO must make exactly 2 requests, made {len(seen)}"
    assert not any("series/vintagedates" in u for u in seen)
    assert not any("output_type=" in u for u in seen)


def test_116_diagnostics_remain_ineligible_for_canonical_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every diagnostic series row must have diagnostic_snapshot_eligible=False."""
    dates = ["2020-01-01", "2020-02-01"]

    def fake_urlopen(url, timeout):
        if "series/vintagedates" in url:
            return _FakeResponse(json_bytes({"count": len(dates), "vintage_dates": dates}))
        if "series/observations" in url:
            return _FakeResponse(json_bytes({
                "count": 1,
                "observations": [
                    {"date": "2020-01-01", "value": "1.0", "realtime_start": dates[0], "realtime_end": "9999-12-31"},
                ],
            }))
        return _FakeResponse(json_bytes({"seriess": [{"id": "CPIAUCSL", "title": "CPI", "units": "Index", "frequency": "Monthly", "frequency_short": "M", "seasonal_adjustment": "SA", "observation_start": "1947-01-01", "observation_end": "2024-01-01", "last_updated": "2024-01-01", "notes": "", "source": "BLS"}]}))

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", fake_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    from market_strats.global_multi_asset.gma1b_macro_cash import _diagnose_one_series
    row, incidents, smoke = _diagnose_one_series(
        config,
        series_id="CPIAUCSL",
        api_key="FAKE_KEY_12345678901234",
        diagnostic_run_id="test_116",
    )
    assert row.get("diagnostic_snapshot_eligible") is False


def test_117_no_accepted_live_hash_created(config) -> None:
    """Offline foundation run must not create an accepted live hash."""
    result = run_gma1b_macro_cash_foundation(config)
    manifest_path = REPORT_DIR / "canonical_macro_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["accepted_live_canonical_hash"] == ""
    assert result.live_retrieval_status != "official_fred_alfred_live_retrieval_complete"


def test_118_default_offline_execution_is_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_gma1b_macro_cash_foundation in fixture mode must not make any HTTP calls."""
    import urllib.request as url_module
    network_calls: list[str] = []

    original_urlopen = url_module.urlopen

    def spy_urlopen(url, timeout=None):
        network_calls.append(str(url))
        return original_urlopen(url, timeout=timeout)

    monkeypatch.setattr("market_strats.global_multi_asset.gma1b_macro_cash.urlopen", spy_urlopen)
    config = load_gma1b_config(CONFIG_PATH)
    run_gma1b_macro_cash_foundation(config)
    assert len(network_calls) == 0, (
        f"Offline fixture run must make zero HTTP calls, made {len(network_calls)}: {network_calls[:3]}"
    )
