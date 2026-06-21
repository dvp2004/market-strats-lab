from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    GMA4_CANONICAL_RESEARCH_END_DATE,
)
from market_strats.global_multi_asset.gma4_data_bundle import (
    BUNDLE_ID,
    GMA3A_TOURNAMENT_CASH_METHODOLOGY_LABEL,
    GMA3A_TOURNAMENT_CASH_SOURCE_ID,
    GMA4DataBundleError,
    build_gma4_data_bundle,
    validate_gma4_bundle_outputs,
)


def _dates() -> list[Any]:
    return pd.bdate_range(end=GMA4_CANONICAL_RESEARCH_END_DATE, periods=260).date.tolist()


def _price_frame(
    symbol: str, dates: list[Any], *, include_post_endpoint: bool = False
) -> pd.DataFrame:
    use_dates = list(dates)
    if include_post_endpoint:
        use_dates.append(date(2026, 5, 4))
    values = [100.0 + idx for idx, _date in enumerate(use_dates)]
    return pd.DataFrame(
        {
            "date": use_dates,
            "instrument_id": symbol,
            "open_raw": values,
            "close_raw": [value + 0.25 for value in values],
            "dividend_cash": 0.0,
            "split_ratio": 0.0,
            "is_completed_observation": True,
            "calendar_id": "us_listed_etf",
            "total_return_index": [1.0 + idx * 0.01 for idx, _date in enumerate(use_dates)],
        }
    )


def _cash(dates: list[Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "observation_date": dates[idx - 1],
                "availability_timestamp_utc": f"{dates[idx - 1]}T22:00:00+00:00",
                "annual_yield": 0.04,
                "accrual_start": dates[idx - 1],
                "accrual_end": dates[idx],
                "accrual_days": 1,
                "period_return": f"0.00000{idx:03d}",
                "source_series": "DGS3MO",
                "source_realtime_start": dates[idx - 1],
            }
            for idx in range(1, len(dates))
        ]
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_bundle(tmp_path: Path, *, include_post_endpoint: bool = False) -> tuple[Path, Path]:
    dates = _dates()
    source_root = tmp_path / "source_market"
    rows = []
    for symbol in FIXED_GMA4_UNIVERSE:
        path = source_root / f"{symbol}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        _price_frame(symbol, dates, include_post_endpoint=include_post_endpoint).to_csv(
            path, index=False
        )
        rows.append(
            {
                "instrument_id": symbol,
                "canonical_file_path": str(path),
                "source_raw_sha256": f"raw-{symbol}",
                "source_normalised_sha256": f"normalised-{symbol}",
                "selected_manifest_sha256": f"manifest-{symbol}",
            }
        )
    inventory_path = tmp_path / "source_inventory.csv"
    pd.DataFrame(rows).to_csv(inventory_path, index=False)
    cash_path = tmp_path / "source_cash.csv"
    _cash(dates).to_csv(cash_path, index=False)
    return inventory_path, cash_path


def _build(tmp_path: Path, *, include_post_endpoint: bool = False):
    inventory_path, cash_path = _source_bundle(
        tmp_path, include_post_endpoint=include_post_endpoint
    )
    return build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )


def test_bundle_inventory_contains_exact_fixed_22_once_each(tmp_path: Path):
    result = _build(tmp_path)

    assert result.status == "ready"
    assert list(result.inventory["instrument_id"]) == FIXED_GMA4_UNIVERSE
    assert result.inventory["instrument_id"].is_unique
    assert set(result.inventory["bundle_id"]) == {BUNDLE_ID}


def test_materialized_prices_end_at_frozen_endpoint_and_drop_later_source_rows(tmp_path: Path):
    result = _build(tmp_path, include_post_endpoint=True)

    assert result.status == "ready"
    for row in result.inventory.to_dict("records"):
        frame = pd.read_csv(row["canonical_file_path"])
        dates = pd.to_datetime(frame["date"]).dt.date
        assert dates.max() == GMA4_CANONICAL_RESEARCH_END_DATE
        assert not (dates > GMA4_CANONICAL_RESEARCH_END_DATE).any()


def test_missing_inventory_record_fails_closed(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    inventory = pd.read_csv(inventory_path).iloc[:-1]
    inventory.to_csv(inventory_path, index=False)

    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    assert result.status == "blocked_data_quality"
    assert any("missing source data" in blocker for blocker in result.blockers)


def test_duplicate_inventory_record_fails_closed(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    inventory = pd.read_csv(inventory_path)
    pd.concat([inventory, inventory.iloc[[0]]], ignore_index=True).to_csv(
        inventory_path, index=False
    )

    with pytest.raises(GMA4DataBundleError, match="duplicate source inventory"):
        build_gma4_data_bundle(
            source_inventory_path=inventory_path,
            source_cash_path=cash_path,
            bundle_root=tmp_path / "bundle",
            report_root=tmp_path / "report",
            fetch_missing=False,
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "duplicate dates"),
        (
            lambda frame: frame.assign(open_raw=[pd.NA, *frame["open_raw"].iloc[1:].tolist()]),
            "null required",
        ),
        (
            lambda frame: frame.assign(close_raw=[0.0, *frame["close_raw"].iloc[1:].tolist()]),
            "invalid close_raw",
        ),
        (
            lambda frame: frame.assign(
                total_return_index=[-1.0, *frame["total_return_index"].iloc[1:].tolist()]
            ),
            "invalid total_return_index",
        ),
    ],
)
def test_invalid_price_data_fails_closed(tmp_path: Path, mutator, message: str):
    inventory_path, cash_path = _source_bundle(tmp_path)
    first_path = Path(pd.read_csv(inventory_path).iloc[0]["canonical_file_path"])
    mutator(pd.read_csv(first_path)).to_csv(first_path, index=False)

    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    assert result.status == "blocked_data_quality"
    assert any(message in blocker for blocker in result.blockers)


def test_cash_accrual_copy_is_validated_against_common_session_intervals(tmp_path: Path):
    result = _build(tmp_path)
    assert result.status == "ready"

    cash_path = result.bundle_root / "cash" / "canonical_cash_accrual.csv"
    cash = pd.read_csv(cash_path).iloc[:-1]
    cash.to_csv(cash_path, index=False)

    with pytest.raises(GMA4DataBundleError, match="missing cash accrual"):
        validate_gma4_bundle_outputs(
            inventory_path=result.report_root / "gma4_market_bundle_inventory.csv",
            cash_path=cash_path,
        )


def test_cash_copy_derives_from_gma3a_source_and_records_hashes(tmp_path: Path):
    result = _build(tmp_path)

    cash_path = result.bundle_root / "cash" / "canonical_cash_accrual.csv"
    manifest = json.loads(
        (result.report_root / "gma4_data_bundle_manifest.json").read_text(encoding="utf-8")
    )
    cash_source = manifest["cash_source"]

    assert result.status == "ready"
    assert cash_source["cash_source_id"] == GMA3A_TOURNAMENT_CASH_SOURCE_ID
    assert cash_source["methodology_label"] == GMA3A_TOURNAMENT_CASH_METHODOLOGY_LABEL
    assert cash_source["derived_from_existing_gma_historical_tournament_cash_series"] is True
    assert cash_source["new_cash_methodology_invented"] is False
    assert cash_source["cash_source_hash"] == _sha256_file(Path(cash_source["cash_source_path"]))
    assert cash_source["copied_cash_hash"] == _sha256_file(cash_path)
    assert cash_source["copied_row_count"] == len(pd.read_csv(cash_path))


def test_cash_copy_covers_required_common_pairs_and_preserves_period_returns(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    source_cash = pd.read_csv(cash_path, dtype={"period_return": "string"})
    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    copied = pd.read_csv(
        result.bundle_root / "cash" / "canonical_cash_accrual.csv",
        dtype={"period_return": "string"},
    )
    common_dates = _dates()
    required_pairs = pd.DataFrame(
        {
            "accrual_start": [str(common_dates[idx - 1]) for idx in range(1, len(common_dates))],
            "accrual_end": [str(common_dates[idx]) for idx in range(1, len(common_dates))],
        }
    )
    expected = required_pairs.merge(source_cash, on=["accrual_start", "accrual_end"], how="left")

    assert result.status == "ready"
    assert len(copied) == len(common_dates) - 1
    assert not copied.duplicated(["accrual_start", "accrual_end"]).any()
    assert copied["period_return"].tolist() == expected["period_return"].tolist()


def test_duplicate_cash_intervals_fail_closed(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    cash = pd.read_csv(cash_path)
    pd.concat([cash, cash.iloc[[0]]], ignore_index=True).to_csv(cash_path, index=False)

    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    assert result.status == "blocked_data_quality"
    assert any("duplicate accrual intervals" in blocker for blocker in result.blockers)


def test_missing_cash_interval_fails_closed(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    pd.read_csv(cash_path).iloc[1:].to_csv(cash_path, index=False)

    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    assert result.status == "blocked_data_quality"
    assert any("missing cash accrual" in blocker for blocker in result.blockers)


def test_non_numeric_cash_period_return_fails_closed(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    cash = pd.read_csv(cash_path, dtype={"period_return": "string"})
    cash.loc[0, "period_return"] = "not-a-number"
    cash.to_csv(cash_path, index=False)

    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )

    assert result.status == "blocked_data_quality"
    assert any("non-numeric period_return" in blocker for blocker in result.blockers)


def test_gma4_cash_copy_does_not_use_short_canonical_macro_fallback(tmp_path: Path):
    inventory_path, cash_path = _source_bundle(tmp_path)
    result = build_gma4_data_bundle(
        source_inventory_path=inventory_path,
        source_cash_path=cash_path,
        bundle_root=tmp_path / "bundle",
        report_root=tmp_path / "report",
        fetch_missing=False,
    )
    manifest = json.loads(
        (result.report_root / "gma4_data_bundle_manifest.json").read_text(encoding="utf-8")
    )

    assert result.status == "ready"
    assert "canonical_macro" not in manifest["cash_source"]["cash_source_path"]
    assert manifest["cash_source"]["cash_source_id"] == GMA3A_TOURNAMENT_CASH_SOURCE_ID


def test_bundle_outputs_fail_if_materialized_file_contains_post_endpoint_observation(
    tmp_path: Path,
):
    result = _build(tmp_path)
    first_path = Path(result.inventory.iloc[0]["canonical_file_path"])
    frame = pd.read_csv(first_path)
    extra = frame.iloc[[-1]].copy()
    extra["date"] = "2026-05-04"
    pd.concat([frame, extra], ignore_index=True).to_csv(first_path, index=False)

    with pytest.raises(GMA4DataBundleError, match="completed observations after"):
        validate_gma4_bundle_outputs(
            inventory_path=result.report_root / "gma4_market_bundle_inventory.csv",
            cash_path=result.bundle_root / "cash" / "canonical_cash_accrual.csv",
        )
