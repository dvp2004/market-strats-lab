from __future__ import annotations

import hashlib
import io
from typing import Any

import pandas as pd
import pytest

from market_strats.intelligence.mi2.prospective_source_adapter import (
    SourceAdapterError,
    run_source_adapter,
)


def _synthetic_sidecar(raw_bytes: bytes) -> dict[str, Any]:
    return {
        "decision_date": "2026-06-25",
        "decision_timestamp_utc": "2026-06-26T00:00:00Z",
        "data_cutoff_or_availability_reference": "20:00 America/New_York",
        "raw_prediction_artifact_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "upstream_source_data_artifact_sha256": "dummy_source_hash",
        "model_identifier": "ridge_fixed_alpha_1_0",
        "model_implementation_or_specification_sha256": "dummy_spec_hash",
        "universe_identifier": "mi1_22_etf_universe",
        "feature_or_signal_schema_identifier": "mi2_technical_features_v1",
        "signal_horizon_sessions": 20,
        "operator_capture_attestation": "test_operator",
    }


def _synthetic_raw_parquet(
    assets: int = 22,
    model_name: str = "ridge_fixed_alpha_1_0",
    include_target: bool = False,
    target_is_null: bool = True,
) -> bytes:
    rows = []
    for i in range(assets):
        row = {
            "session_date": "2026-06-25",
            "instrument_id": f"asset_{i}",
            "model_name": model_name,
            "prediction": float(i) * 0.1,
        }
        if include_target:
            row["target_value"] = None if target_is_null else 0.05
        rows.append(row)

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def test_valid_adaptation() -> None:
    raw_bytes = _synthetic_raw_parquet(assets=22)
    sidecar = _synthetic_sidecar(raw_bytes)

    export = run_source_adapter(raw_bytes, sidecar)

    assert len(export) == 22
    assert export["research_only"].all()
    assert (export["portfolio_influence"] == 0.0).all()
    assert list(export.columns) == [
        "decision_date",
        "asset_identifier",
        "model_identifier",
        "feature_or_signal_schema_identifier",
        "signal_horizon_sessions",
        "signal_score",
        "signal_rank",
        "signal_percentile",
        "data_cutoff_or_availability_reference",
        "source_artifact_sha256",
        "research_only",
        "portfolio_influence",
    ]


def test_deterministic_ranking() -> None:
    raw_bytes = _synthetic_raw_parquet(assets=22)
    sidecar = _synthetic_sidecar(raw_bytes)
    export = run_source_adapter(raw_bytes, sidecar)

    # Asset 21 has the highest prediction
    top_asset = export[export["asset_identifier"] == "asset_21"]
    assert top_asset["signal_rank"].iloc[0] == 1.0
    assert top_asset["signal_percentile"].iloc[0] == 1.0

    bottom_asset = export[export["asset_identifier"] == "asset_0"]
    assert bottom_asset["signal_rank"].iloc[0] == 22.0
    assert bottom_asset["signal_percentile"].iloc[0] == 0.0


def test_hash_mismatch_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet()
    sidecar = _synthetic_sidecar(raw_bytes)
    sidecar["raw_prediction_artifact_sha256"] = "wrong_hash"

    with pytest.raises(SourceAdapterError, match="raw_artifact_hash_mismatch"):
        run_source_adapter(raw_bytes, sidecar)


def test_wrong_model_identity_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet()
    sidecar = _synthetic_sidecar(raw_bytes)
    sidecar["model_identifier"] = "wrong_model"

    with pytest.raises(SourceAdapterError, match="wrong_model_identifier"):
        run_source_adapter(raw_bytes, sidecar)


def test_wrong_model_identity_in_data_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet(model_name="wrong_model")
    sidecar = _synthetic_sidecar(raw_bytes)

    with pytest.raises(SourceAdapterError, match="wrong_model_identifier in source data"):
        run_source_adapter(raw_bytes, sidecar)


def test_cutoff_and_timestamp_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet()
    sidecar = _synthetic_sidecar(raw_bytes)
    sidecar["data_cutoff_or_availability_reference"] = "16:00 America/New_York"

    with pytest.raises(SourceAdapterError, match="invalid_or_missing_cutoff"):
        run_source_adapter(raw_bytes, sidecar)


def test_incomplete_universe_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet(assets=21)
    sidecar = _synthetic_sidecar(raw_bytes)

    with pytest.raises(SourceAdapterError, match="duplicate_or_incomplete_assets"):
        run_source_adapter(raw_bytes, sidecar)


def test_target_outcome_rejection() -> None:
    raw_bytes = _synthetic_raw_parquet(include_target=True, target_is_null=False)
    sidecar = _synthetic_sidecar(raw_bytes)

    with pytest.raises(
        SourceAdapterError, match="selected_row_contains_matured_target_or_outcome: target_value"
    ):
        run_source_adapter(raw_bytes, sidecar)


def test_null_targets_allowed() -> None:
    # If target is null, it hasn't matured, but it shouldn't be propagated.
    raw_bytes = _synthetic_raw_parquet(include_target=True, target_is_null=True)
    sidecar = _synthetic_sidecar(raw_bytes)

    export = run_source_adapter(raw_bytes, sidecar)
    assert "target_value" not in export.columns
