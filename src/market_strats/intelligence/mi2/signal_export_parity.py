"""Deterministic research-only export boundary for existing MI-2 predictions."""

from __future__ import annotations

import hashlib
import re
from typing import Final

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

EXPORT_SCHEMA_IDENTIFIER: Final = "mi2e_research_only_technical_signal_export_v1"
DEFAULT_SIGNAL_HORIZON_SESSIONS: Final = 20
SOURCE_REQUIRED_COLUMNS: Final = frozenset(
    {"session_date", "instrument_id", "model_name", "prediction"}
)
PROHIBITED_FIELDS: Final = frozenset(
    {
        "target_weight",
        "position_size",
        "portfolio_weight",
        "trade",
        "order",
        "broker",
        "account",
        "execution",
        "cash_allocation",
        "real_money",
    }
)
EXPORT_COLUMNS: Final = (
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
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class SignalExportContractError(ValueError):
    """Raised when source data cannot satisfy the MI-2E export contract."""


def _require_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise SignalExportContractError(f"{field_name} must be a non-empty canonical string")
    return value


def _validated_identifiers(values: pd.Series, field_name: str) -> pd.Series:
    if values.isna().any():
        raise SignalExportContractError(f"{field_name} contains null values")
    if not values.map(lambda value: isinstance(value, str)).all():
        raise SignalExportContractError(f"{field_name} must contain strings only")
    if values.map(lambda value: not value or value != value.strip()).any():
        raise SignalExportContractError(f"{field_name} contains non-canonical identifiers")
    return values.copy()


def _normalized_decision_dates(values: pd.Series) -> pd.Series:
    if values.isna().any():
        raise SignalExportContractError("session_date contains null values")
    try:
        parsed = pd.to_datetime(values, errors="raise")
    except (TypeError, ValueError) as exc:
        raise SignalExportContractError("session_date contains unparseable values") from exc
    if not isinstance(parsed, pd.Series):
        parsed = pd.Series(parsed, index=values.index)
    if (parsed != parsed.dt.normalize()).any():
        raise SignalExportContractError("session_date must contain date-only values")
    return parsed.dt.strftime("%Y-%m-%d")


def export_mi2_research_signals(
    source: pd.DataFrame,
    *,
    source_artifact_sha256: str,
    data_cutoff_or_availability_reference: str,
    feature_or_signal_schema_identifier: str = EXPORT_SCHEMA_IDENTIFIER,
    signal_horizon_sessions: int = DEFAULT_SIGNAL_HORIZON_SESSIONS,
) -> pd.DataFrame:
    """Map an existing MI-2 prediction table into the frozen research-only schema."""

    if not isinstance(source, pd.DataFrame):
        raise SignalExportContractError("source must be a pandas DataFrame")
    missing = SOURCE_REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise SignalExportContractError(f"source is missing required fields: {sorted(missing)}")
    prohibited = PROHIBITED_FIELDS & {str(column).casefold() for column in source.columns}
    if prohibited:
        raise SignalExportContractError(
            f"source contains prohibited portfolio or execution fields: {sorted(prohibited)}"
        )
    source_hash = _require_identifier(source_artifact_sha256, "source_artifact_sha256").lower()
    if _SHA256_PATTERN.fullmatch(source_hash) is None:
        raise SignalExportContractError("source_artifact_sha256 must be exactly 64 hex characters")
    availability_reference = _require_identifier(
        data_cutoff_or_availability_reference,
        "data_cutoff_or_availability_reference",
    )
    schema_identifier = _require_identifier(
        feature_or_signal_schema_identifier,
        "feature_or_signal_schema_identifier",
    )
    if not isinstance(signal_horizon_sessions, int) or signal_horizon_sessions <= 0:
        raise SignalExportContractError("signal_horizon_sessions must be a positive integer")
    if source.empty:
        raise SignalExportContractError("source prediction table is empty")
    if not is_numeric_dtype(source["prediction"]):
        raise SignalExportContractError("prediction must be numeric")

    scores = source["prediction"].astype("float64", copy=True)
    if not np.isfinite(scores.to_numpy()).all():
        raise SignalExportContractError("prediction contains null or non-finite values")
    exported = pd.DataFrame(
        {
            "decision_date": _normalized_decision_dates(source["session_date"]),
            "asset_identifier": _validated_identifiers(source["instrument_id"], "instrument_id"),
            "model_identifier": _validated_identifiers(source["model_name"], "model_name"),
            "signal_score": scores,
        }
    )
    identity = ["decision_date", "asset_identifier", "model_identifier"]
    if exported.duplicated(identity).any():
        raise SignalExportContractError("source contains duplicate decision/asset/model identities")

    exported = exported.sort_values(
        ["decision_date", "model_identifier", "signal_score", "asset_identifier"],
        ascending=[True, True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    groups = exported.groupby(["decision_date", "model_identifier"], sort=False)
    exported["signal_rank"] = groups.cumcount() + 1
    group_sizes = groups["asset_identifier"].transform("size")
    exported["signal_percentile"] = np.where(
        group_sizes == 1,
        1.0,
        1.0 - (exported["signal_rank"] - 1) / (group_sizes - 1),
    )
    exported["feature_or_signal_schema_identifier"] = schema_identifier
    exported["signal_horizon_sessions"] = signal_horizon_sessions
    exported["data_cutoff_or_availability_reference"] = availability_reference
    exported["source_artifact_sha256"] = source_hash
    exported["research_only"] = True
    exported["portfolio_influence"] = 0
    return exported.loc[:, EXPORT_COLUMNS]


def canonical_export_sha256(exported: pd.DataFrame) -> str:
    """Hash a validated export using a deterministic CSV representation."""

    if tuple(exported.columns) != EXPORT_COLUMNS:
        raise SignalExportContractError("exported table does not match the frozen MI-2E schema")
    payload = exported.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
