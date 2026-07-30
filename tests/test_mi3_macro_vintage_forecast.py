from __future__ import annotations

import json
import urllib.error
import urllib.parse
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from market_strats.intelligence.mi2.technical_baseline import FEATURE_COLUMNS
from market_strats.intelligence.mi3.macro_vintage_forecast import (
    FRED_ENDPOINT_PATH,
    MACRO_AVAILABILITY_EVIDENCE_LEVEL,
    MACRO_FEATURE_COLUMNS,
    FredRequestError,
    FredVintageAdapter,
    MacroRawResponse,
    MacroSeries,
    build_macro_asof_panel,
    build_macro_feature_panel,
    macro_available_at_utc,
    normalize_macro_observations,
    run_mi3_macro_vintage_forecast,
    write_macro_raw_snapshots,
)

ROOT = Path(__file__).resolve().parents[1]
SERIES_IDS = ["DFF", "T10Y2Y", "BAA10YM", "CPIAUCSL", "UNRATE", "INDPRO"]


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi3_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _sessions(count: int = 340) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-02", periods=count)


def _technical_feature_panel(count: int = 340) -> pd.DataFrame:
    rows = []
    instruments = ["mi1_etf_spy", "mi1_etf_qqq", "mi1_etf_bil"]
    for instrument_index, instrument_id in enumerate(instruments):
        for session_index, session in enumerate(_sessions(count)):
            row = {
                "instrument_id": instrument_id,
                "session_date": session,
                "decision_timestamp_utc": datetime.combine(
                    session.date(), datetime.min.time(), UTC
                ),
                "availability_evidence_level": "contractual_assumption",
                "feature_available": session_index >= 252,
                "feature_block_reason": "" if session_index >= 252 else "lookback",
            }
            for feature_index, column in enumerate(FEATURE_COLUMNS):
                row[column] = instrument_index * 0.1 + session_index * 0.001 + feature_index * 0.01
            rows.append(row)
    return pd.DataFrame(rows)


def _target_panel(count: int = 340) -> pd.DataFrame:
    rows = []
    instruments = ["mi1_etf_spy", "mi1_etf_qqq", "mi1_etf_bil"]
    for instrument_index, instrument_id in enumerate(instruments):
        for session_index, session in enumerate(_sessions(count)):
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "session_date": session,
                    "target_name": "20_trading_session_forward_total_return_excess_vs_BIL",
                    "target_value": 0.01 * instrument_index + 0.0001 * session_index,
                    "target_is_future_information": True,
                    "target_price_policy": "vendor_adjusted_close_retrospective_total_return_proxy",
                    "target_available": session_index < count - 20,
                    "target_block_reason": "" if session_index < count - 20 else "future",
                }
            )
    return pd.DataFrame(rows)


def _macro_observations(series_id: str, count: int = 340) -> list[dict[str, str]]:
    observations = []
    for index, session in enumerate(_sessions(count)):
        observations.append(
            {
                "date": session.date().isoformat(),
                "realtime_start": (session + pd.Timedelta(days=1)).date().isoformat(),
                "realtime_end": "9999-12-31",
                "value": str(100 + index + len(series_id)),
            }
        )
    return observations


class FakeMacroAdapter:
    source_id = "fake_vintage_macro"
    source_name = "Fake vintage macro"

    def fetch_vintage_observations(
        self,
        series: list[MacroSeries],
        observation_start,
        observation_end,
    ) -> list[MacroRawResponse]:
        return [
            MacroRawResponse(
                series_id=item.series_id,
                request_parameters={
                    "series_id": item.series_id,
                    "output_type": 1,
                    "realtime_start": observation_start.isoformat(),
                    "realtime_end": observation_end.isoformat(),
                },
                payload={"observations": _macro_observations(item.series_id)},
                retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
            )
            for item in series
        ]


class FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class RecordingOpener:
    def __init__(
        self,
        payloads: list[dict | Exception] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payloads = list(payloads or [])
        self.error = error
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: int) -> FakeHttpResponse:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        item = self.payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeHttpResponse(item)


def _query(url: str) -> dict[str, str]:
    return {
        key: values[0]
        for key, values in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()
    }


def _vintage_payload(start: str = "2020-01-01", end: str = "2020-12-31") -> dict:
    return {"count": 2, "vintage_dates": [start, end]}


def test_missing_fred_api_key_fails_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    adapter = FredVintageAdapter()
    with pytest.raises(RuntimeError, match="FRED_API_KEY"):
        adapter.fetch_vintage_observations(
            [MacroSeries("DFF", "effective_federal_funds_rate")],
            pd.Timestamp("2020-01-01").date(),
            pd.Timestamp("2020-01-31").date(),
        )


def test_fred_request_uses_historical_realtime_range_without_vintage_dates() -> None:
    opener = RecordingOpener(
        [
            _vintage_payload(),
            {
                "count": 1,
                "observations": [
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-03",
                        "realtime_end": "2020-01-10",
                        "value": "1.0",
                    }
                ],
            },
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=50)
    responses = adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2020-12-31").date(),
    )
    params = _query(opener.urls[0])
    assert params["series_id"] == "DFF"
    assert params["file_type"] == "json"
    assert params["limit"] == "10000"
    assert params["offset"] == "0"
    assert "realtime_start" not in params
    assert "realtime_end" not in params
    assert "vintage_dates" not in params
    params = _query(opener.urls[1])
    assert params["file_type"] == "json"
    assert params["output_type"] == "1"
    assert params["realtime_start"] == "2020-01-01"
    assert params["realtime_end"] == "2020-12-31"
    assert params["observation_start"] == "2020-01-01"
    assert params["observation_end"] == "2020-12-31"
    assert params["limit"] == "50"
    assert params["offset"] == "0"
    assert "vintage_dates" not in params
    assert "api_key" not in responses[1].request_parameters
    assert responses[1].payload["observations"][0]["realtime_start"] == "2020-01-03"


def test_fred_pagination_uses_offset_and_count() -> None:
    opener = RecordingOpener(
        [
            _vintage_payload(),
            {
                "count": 3,
                "observations": [
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-03",
                        "realtime_end": "2020-01-10",
                        "value": "1.0",
                    },
                    {
                        "date": "2020-01-03",
                        "realtime_start": "2020-01-04",
                        "realtime_end": "2020-01-10",
                        "value": "2.0",
                    },
                ],
            },
            {
                "count": 3,
                "observations": [
                    {
                        "date": "2020-01-04",
                        "realtime_start": "2020-01-05",
                        "realtime_end": "2020-01-10",
                        "value": "3.0",
                    }
                ],
            },
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=2)
    responses = adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2020-12-31").date(),
    )
    assert [_query(url)["offset"] for url in opener.urls] == ["0", "0", "2"]
    assert len(responses) == 3
    assert sum(len(response.payload.get("observations", [])) for response in responses) == 3


def test_long_realtime_range_is_split_into_contiguous_three_year_chunks() -> None:
    expected_chunk_count = 9
    opener = RecordingOpener(
        [
            {"count": 2, "vintage_dates": ["2000-01-03", "2026-06-17"]},
            *[{"count": 0, "observations": []} for _ in range(expected_chunk_count)],
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=50)
    adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2000-01-03").date(),
        pd.Timestamp("2026-06-17").date(),
    )
    queries = [_query(url) for url in opener.urls[1:]]
    chunks = [
        (
            pd.Timestamp(params["realtime_start"]),
            pd.Timestamp(params["realtime_end"]),
        )
        for params in queries
    ]
    assert len(chunks) == expected_chunk_count
    assert chunks[0] == (pd.Timestamp("2000-01-03"), pd.Timestamp("2003-01-02"))
    assert chunks[-1][1] == pd.Timestamp("2026-06-17")
    for index, (chunk_start, chunk_end) in enumerate(chunks):
        max_end = chunk_start + pd.DateOffset(years=3) - pd.Timedelta(days=1)
        assert chunk_end <= max_end
        assert queries[index]["observation_start"] == "2000-01-03"
        assert queries[index]["observation_end"] == "2026-06-17"
        assert queries[index]["offset"] == "0"
        assert "vintage_dates" not in queries[index]
        if index > 0:
            assert chunk_start == chunks[index - 1][1] + pd.Timedelta(days=1)


def test_each_realtime_chunk_uses_its_own_pagination() -> None:
    opener = RecordingOpener(
        [
            {"count": 2, "vintage_dates": ["2020-01-01", "2023-01-02"]},
            {
                "count": 2,
                "observations": [
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-03",
                        "realtime_end": "2020-01-10",
                        "value": "1.0",
                    }
                ],
            },
            {
                "count": 2,
                "observations": [
                    {
                        "date": "2020-01-03",
                        "realtime_start": "2020-01-04",
                        "realtime_end": "2020-01-10",
                        "value": "2.0",
                    }
                ],
            },
            {"count": 0, "observations": []},
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=1)
    responses = adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2023-01-02").date(),
    )
    queries = [_query(url) for url in opener.urls[1:]]
    assert [
        (params["realtime_start"], params["realtime_end"], params["offset"]) for params in queries
    ] == [
        ("2020-01-01", "2022-12-31", "0"),
        ("2020-01-01", "2022-12-31", "1"),
        ("2023-01-01", "2023-01-02", "0"),
    ]
    assert len(responses) == 4


def test_safe_http_400_message_includes_context_without_api_key() -> None:
    body = b'{"error_message":"bad request api_key=unit-secret"}'
    error = urllib.error.HTTPError(
        url="https://api.stlouisfed.org/fred/series/observations?api_key=unit-secret",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=BytesIO(body),
    )
    opener = RecordingOpener([_vintage_payload(), error])
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener)
    with pytest.raises(FredRequestError) as exc:
        adapter.fetch_vintage_observations(
            [MacroSeries("DFF", "effective_federal_funds_rate")],
            pd.Timestamp("2020-01-01").date(),
            pd.Timestamp("2020-12-31").date(),
        )
    message = str(exc.value)
    assert "status_code=400" in message
    assert "series_id=DFF" in message
    assert f"endpoint_path={FRED_ENDPOINT_PATH}" in message
    assert "request_type=observations" in message
    assert "realtime_start=2020-01-01" in message
    assert "realtime_end=2020-12-31" in message
    assert "output_type=1" in message
    assert "limit=100000" in message
    assert "offset=0" in message
    assert "unit-secret" not in message
    assert "api_key=<redacted>" in message
    assert "https://api.stlouisfed.org" not in message


def test_malformed_fred_error_body_does_not_crash_error_handling() -> None:
    error = urllib.error.HTTPError(
        url="https://api.stlouisfed.org/fred/series/observations",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=BytesIO(b"\xff\xfe not json"),
    )
    opener = RecordingOpener([_vintage_payload(), error])
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener)
    with pytest.raises(FredRequestError) as exc:
        adapter.fetch_vintage_observations(
            [MacroSeries("DFF", "effective_federal_funds_rate")],
            pd.Timestamp("2020-01-01").date(),
            pd.Timestamp("2020-12-31").date(),
        )
    assert "status_code=400" in str(exc.value)
    assert "unit-secret" not in str(exc.value)


def test_vintage_date_discovery_paginates_before_observations() -> None:
    opener = RecordingOpener(
        [
            {"count": 3, "vintage_dates": ["2020-01-01", "2020-06-01"]},
            {"count": 3, "vintage_dates": ["2020-12-31"]},
            {"count": 0, "observations": []},
        ]
    )
    adapter = FredVintageAdapter(
        api_key="unit-secret",
        opener=opener,
        limit=50,
        vintage_dates_limit=2,
    )
    responses = adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2020-12-31").date(),
    )
    queries = [_query(url) for url in opener.urls]
    assert [params["offset"] for params in queries[:2]] == ["0", "2"]
    assert all("realtime_start" not in params for params in queries[:2])
    assert queries[2]["realtime_start"] == "2020-01-01"
    assert queries[2]["realtime_end"] == "2020-12-31"
    assert [response.request_parameters["request_type"] for response in responses] == [
        "vintage_dates",
        "vintage_dates",
        "observations",
    ]


def test_dff_like_vintage_coverage_shifts_observation_chunks_after_global_start() -> None:
    opener = RecordingOpener(
        [
            {"count": 2, "vintage_dates": ["2002-05-20", "2026-06-17"]},
            *[{"count": 0, "observations": []} for _ in range(9)],
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=50)
    adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2000-01-03").date(),
        pd.Timestamp("2026-06-17").date(),
    )
    observation_queries = [_query(url) for url in opener.urls[1:]]
    assert observation_queries[0]["realtime_start"] == "2002-05-20"
    assert observation_queries[0]["realtime_end"] == "2005-05-19"
    assert observation_queries[-1]["realtime_end"] == "2026-06-17"
    assert all("vintage_dates" not in params for params in observation_queries)
    assert adapter.vintage_capabilities[0].vintage_start_date.isoformat() == "2002-05-20"
    assert (
        adapter.vintage_capabilities[0].requested_effective_realtime_start.isoformat()
        == "2002-05-20"
    )


def test_series_with_no_vintage_dates_fails_before_observation_retrieval() -> None:
    opener = RecordingOpener([{"count": 0, "vintage_dates": []}])
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener)
    with pytest.raises(ValueError, match="unsupported_series_ids=DFF") as exc:
        adapter.fetch_vintage_observations(
            [MacroSeries("DFF", "effective_federal_funds_rate")],
            pd.Timestamp("2000-01-03").date(),
            pd.Timestamp("2026-06-17").date(),
        )
    assert "no FRED-current fallback is allowed" in str(exc.value)
    assert len(opener.urls) == 1
    assert "/fred/series/vintagedates" in opener.urls[0]


def test_macro_eligible_start_reflects_latest_required_series_capability() -> None:
    rows = []
    sessions = pd.bdate_range("2020-01-02", periods=10)
    late_series = "DFF"
    for session in sessions:
        row = {"session_date": session}
        for series_id in SERIES_IDS:
            available = series_id != late_series or session >= pd.Timestamp("2020-01-08")
            row[f"{series_id}_value"] = 100.0 if available else pd.NA
            row[f"{series_id}_macro_staleness_sessions"] = 1 if available else pd.NA
        row["macro_asof_available"] = all(
            pd.notna(row[f"{series_id}_value"]) for series_id in SERIES_IDS
        )
        row["availability_evidence_level_counts"] = json.dumps(
            {MACRO_AVAILABILITY_EVIDENCE_LEVEL: 6}
        )
        rows.append(row)
    asof_panel = pd.DataFrame(rows)
    first = asof_panel[asof_panel["macro_asof_available"]]["session_date"].min()
    assert first == pd.Timestamp("2020-01-08")


def test_raw_manifest_contains_chunk_page_metadata_without_api_key() -> None:
    opener = RecordingOpener(
        [
            _vintage_payload(),
            {
                "count": 2,
                "observations": [
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-03",
                        "realtime_end": "2020-01-10",
                        "value": "1.0",
                    }
                ],
            },
            {
                "count": 2,
                "observations": [
                    {
                        "date": "2020-01-03",
                        "realtime_start": "2020-01-04",
                        "realtime_end": "2020-01-10",
                        "value": "2.0",
                    }
                ],
            },
        ]
    )
    adapter = FredVintageAdapter(api_key="unit-secret", opener=opener, limit=1)
    responses = adapter.fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2020-12-31").date(),
    )
    root = _tmp("fred_manifest")
    manifest = write_macro_raw_snapshots(responses, root / "raw", root / "manifests", "FRED")
    assert list(manifest["request_type"]) == ["vintage_dates", "observations", "observations"]
    assert list(manifest["endpoint_path"]) == [
        "/fred/series/vintagedates",
        "/fred/series/observations",
        "/fred/series/observations",
    ]
    assert list(manifest["realtime_start"]) == [None, "2020-01-01", "2020-01-01"]
    assert list(manifest["realtime_end"]) == [None, "2020-12-31", "2020-12-31"]
    assert list(manifest["offset"]) == [0, 0, 1]
    assert list(manifest["limit"]) == [10000, 1, 1]
    assert list(manifest["series_vintage_start_date"]) == [None, "2020-01-01", "2020-01-01"]
    assert list(manifest["series_vintage_end_date"]) == [None, "2020-12-31", "2020-12-31"]
    text = manifest.to_json()
    assert "unit-secret" not in text
    assert "api_key" not in text


def test_exact_duplicate_provider_rows_are_deduplicated_only_by_vintage_identity() -> None:
    duplicate = {
        "date": "2020-01-02",
        "realtime_start": "2020-01-03",
        "realtime_end": "2020-01-10",
        "value": "1.0",
    }
    distinct_vintage = {
        "date": "2020-01-02",
        "realtime_start": "2020-01-11",
        "realtime_end": "9999-12-31",
        "value": "1.0",
    }
    responses = [
        MacroRawResponse(
            series_id="DFF",
            request_parameters={
                "series_id": "DFF",
                "realtime_start": "2020-01-01",
                "realtime_end": "2020-12-31",
                "offset": 0,
            },
            payload={"observations": [duplicate, distinct_vintage]},
            retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
        ),
        MacroRawResponse(
            series_id="DFF",
            request_parameters={
                "series_id": "DFF",
                "realtime_start": "2020-01-01",
                "realtime_end": "2020-12-31",
                "offset": 2,
            },
            payload={"observations": [duplicate]},
            retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    ]
    root = _tmp("dedupe")
    manifest = write_macro_raw_snapshots(responses, root / "raw", root / "manifests", "fake")
    observations = normalize_macro_observations(responses, manifest)
    assert len(observations) == 2
    assert set(observations["realtime_start"].dt.strftime("%Y-%m-%d")) == {
        "2020-01-03",
        "2020-01-11",
    }


def test_raw_snapshot_hash_manifest_omits_api_key_and_is_ignored() -> None:
    response = FakeMacroAdapter().fetch_vintage_observations(
        [MacroSeries("DFF", "effective_federal_funds_rate")],
        pd.Timestamp("2020-01-01").date(),
        pd.Timestamp("2020-01-31").date(),
    )
    root = _tmp("snapshots")
    manifest = write_macro_raw_snapshots(
        response,
        root / "data" / "private" / "mi3" / "raw",
        root / "data" / "private" / "mi3" / "manifests",
        "Fake vintage macro",
    )
    text = manifest.to_json()
    assert "FRED_API_KEY" not in text
    assert "secret" not in text.lower()
    assert len(manifest.loc[0, "content_sha256"]) == 64
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi3/*" in gitignore
    assert "/reports/mi3/*" in gitignore


def test_values_selected_by_vintage_interval_and_next_session_availability() -> None:
    response = [
        MacroRawResponse(
            series_id="DFF",
            request_parameters={"series_id": "DFF"},
            payload={
                "observations": [
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-02",
                        "realtime_end": "2020-01-06",
                        "value": "1.0",
                    },
                    {
                        "date": "2020-01-02",
                        "realtime_start": "2020-01-06",
                        "realtime_end": "9999-12-31",
                        "value": "2.0",
                    },
                ]
            },
            retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
        )
    ]
    root = _tmp("vintage")
    manifest = write_macro_raw_snapshots(response, root / "raw", root / "manifests", "fake")
    observations = normalize_macro_observations(response, manifest)
    assert macro_available_at_utc(pd.Timestamp("2020-01-02")).date().isoformat() == "2020-01-04"
    panel = build_macro_asof_panel(
        [
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-03"),
            pd.Timestamp("2020-01-06"),
            pd.Timestamp("2020-01-07"),
        ],
        observations,
    )
    assert pd.isna(panel.loc[0, "DFF_value"])
    assert panel.loc[1, "DFF_value"] == 1.0
    assert panel.loc[2, "DFF_value"] == 1.0
    assert panel.loc[3, "DFF_value"] == 2.0


def test_forward_fill_only_no_backfill_and_unverified_blocked() -> None:
    response = [
        MacroRawResponse(
            series_id="DFF",
            request_parameters={"series_id": "DFF"},
            payload={
                "observations": [
                    {
                        "date": "2020-01-06",
                        "realtime_start": "2020-01-06",
                        "realtime_end": "9999-12-31",
                        "value": "1.0",
                    },
                    {
                        "date": "2020-01-07",
                        "realtime_start": "",
                        "realtime_end": "",
                        "value": "2.0",
                    },
                ]
            },
            retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
        )
    ]
    root = _tmp("fill")
    manifest = write_macro_raw_snapshots(response, root / "raw", root / "manifests", "fake")
    observations = normalize_macro_observations(response, manifest)
    assert "unverified" in set(observations["availability_evidence_level"])
    panel = build_macro_asof_panel(
        [pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-07"), pd.Timestamp("2020-01-08")],
        observations,
    )
    assert pd.isna(panel.loc[0, "DFF_value"])
    assert panel.loc[1, "DFF_value"] == 1.0
    assert panel.loc[2, "DFF_value"] == 1.0


def test_macro_eligibility_starts_after_all_required_features_exist() -> None:
    rows = []
    for session_index, session in enumerate(_sessions(270)):
        row = {"session_date": session, "macro_asof_available": True}
        for series_id in SERIES_IDS:
            row[f"{series_id}_value"] = 100 + session_index
            row[f"{series_id}_macro_staleness_sessions"] = 1
        row["availability_evidence_level_counts"] = json.dumps(
            {MACRO_AVAILABILITY_EVIDENCE_LEVEL: 6}
        )
        rows.append(row)
    features = build_macro_feature_panel(pd.DataFrame(rows))
    first = features[features["macro_feature_available"]]["session_date"].min()
    assert first == _sessions(270)[252]
    assert set(MACRO_FEATURE_COLUMNS).issubset(features.columns)


def test_run_mi3_uses_identical_rows_and_writes_forecast_only_outputs() -> None:
    mi1_root = _tmp("mi1")
    mi2_root = _tmp("mi2")
    mi3_root = _tmp("mi3")
    report_root = _tmp("reports")
    (mi1_root / "normalized").mkdir(parents=True)
    pd.DataFrame(
        {
            "eligible": [True],
            "availability_evidence_level": ["contractual_assumption"],
        }
    ).to_parquet(mi1_root / "normalized" / "decision_panel_availability_audit.parquet")
    _technical_feature_panel().to_parquet(mi2_root / "feature_panel.parquet", index=False)
    _target_panel().to_parquet(mi2_root / "target_panel.parquet", index=False)
    result = run_mi3_macro_vintage_forecast(
        mi1_data_root=mi1_root,
        mi2_data_root=mi2_root,
        mi3_data_root=mi3_root,
        report_root=report_root,
        adapter=FakeMacroAdapter(),
        macro_config_path=ROOT / "configs" / "intelligence" / "macro_series_mi3.yaml",
        registry_path=ROOT / "configs" / "intelligence" / "mi2_research_registry.yaml",
    )
    predictions = pd.read_parquet(result.output_paths["walk_forward_macro_predictions"])
    assert result.macro_series_count == 6
    assert result.model_count == 4
    assert "ridge_technical_only_alpha_1_0" in predictions.columns
    assert "ridge_technical_plus_macro_alpha_1_0" in predictions.columns
    assert len(predictions[["instrument_id", "session_date"]].drop_duplicates()) == len(predictions)
    scoreboard = pd.read_parquet(result.output_paths["macro_forecast_scoreboard"])
    assert set(scoreboard["evaluation_layer"]) == {"forecast evaluation only"}
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "market_strats" / "intelligence").rglob("*.py")
    ).lower()
    for prohibited in ["candidate_packet", "submit_order", "tradingview", "alpaca", "ibkr"]:
        assert prohibited not in source_text
