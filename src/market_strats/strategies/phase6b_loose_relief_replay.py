from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


VALID_TARGET_WEIGHT_SOURCE = "phase6b_loose_relief_rule_replay"


@dataclass(frozen=True)
class Phase6BReplayResult:
    stream: pd.DataFrame
    summary: pd.DataFrame


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    clean = str(value).strip().lower()
    return clean in {"true", "1", "yes", "y", "pass"}


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(col).lower(): str(col) for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _normalise_signal_to_weight(value: Any) -> float | None:
    if pd.isna(value):
        return None

    if isinstance(value, int | float):
        if value >= 0.75:
            return 1.0
        if value <= 0.25:
            return 0.0
        return float(value)

    clean = str(value).strip().lower()

    offensive_values = {
        "1",
        "1.0",
        "risk_on",
        "risk-on",
        "offensive",
        "offensive_spy",
        "spy",
        "equity",
        "invested",
        "long_spy",
        "supportive",
    }
    defensive_values = {
        "0",
        "0.0",
        "risk_off",
        "risk-off",
        "defensive",
        "defensive_or_cash",
        "cash",
        "flat",
        "neutral_cash",
        "fragile",
    }

    if clean in offensive_values:
        return 1.0
    if clean in defensive_values:
        return 0.0

    try:
        numeric = float(clean)
    except ValueError:
        return None

    if numeric >= 0.75:
        return 1.0
    if numeric <= 0.25:
        return 0.0
    return numeric


def _mode_from_weight(weight: float | None) -> str:
    if weight is None or pd.isna(weight):
        return ""
    if weight >= 0.75:
        return "offensive_spy"
    if weight <= 0.25:
        return "defensive_or_cash"
    return "partial_risk"


def _normalise_benchmark(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series, str, str]:
    close_col = _first_existing_col(frame, ["SPY_close", "spy_close", "adj_close", "close"])
    return_col = _first_existing_col(
        frame,
        ["SPY_return", "spy_return", "benchmark_return", "return"],
    )

    close = (
        pd.to_numeric(frame[close_col], errors="coerce")
        if close_col
        else pd.Series(pd.NA, index=frame.index)
    )

    if return_col:
        returns = pd.to_numeric(frame[return_col], errors="coerce")
    elif close_col:
        returns = close.pct_change().fillna(0.0)
    else:
        returns = pd.Series(pd.NA, index=frame.index)

    return close, returns, close_col or "", return_col or ""


def replay_phase6b_loose_relief_target_weights(
    *,
    rule_input: pd.DataFrame,
    pinned_research_endpoint: str,
    audit_current_date: str,
    endpoint_exposure: float = 1.0,
    signal_column_priority: list[str] | None = None,
) -> Phase6BReplayResult:
    """Replay the final Phase 6B/6C target weight from post-endpoint rule signals.

    This function deliberately does not accept manually filled target weights as the
    source of truth. It requires a post-endpoint rule-input signal column produced by
    the project logic, then maps that signal into the executable
    target_offensive_weight used by the final candidate.

    Raw SPY prices alone are insufficient.
    """

    required_output_columns = [
        "date",
        "SPY_close",
        "SPY_return",
        "target_offensive_weight",
        "target_weight_source",
        "data_source_timestamp",
        "pinned_research_endpoint",
        "is_out_of_sample_extension",
        "benchmark_update_flag",
        "stream_row_validity_flag",
        "blocking_warnings",
    ]

    if rule_input.empty:
        stream = pd.DataFrame(columns=required_output_columns)
        summary = _summary(
            stream=stream,
            signal_column="",
            failure_reason="rule_input_empty",
        )
        return Phase6BReplayResult(stream=stream, summary=summary)

    signal_candidates = signal_column_priority or [
        "final_phase6b_signal",
        "confirmed_signal",
        "guarded_signal",
        "final_signal",
        "target_signal",
        "current_mode",
    ]

    date_col = _first_existing_col(rule_input, ["date", "decision_date"])
    signal_col = _first_existing_col(rule_input, signal_candidates)

    if date_col is None:
        stream = pd.DataFrame(columns=required_output_columns)
        summary = _summary(
            stream=stream,
            signal_column="",
            failure_reason="date_column_missing",
        )
        return Phase6BReplayResult(stream=stream, summary=summary)

    if signal_col is None:
        stream = pd.DataFrame(columns=required_output_columns)
        summary = _summary(
            stream=stream,
            signal_column="",
            failure_reason="phase6b_rule_signal_column_missing",
        )
        return Phase6BReplayResult(stream=stream, summary=summary)

    frame = rule_input.copy()
    frame["date"] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame[frame["date"].notna()].copy()

    pinned = pd.to_datetime(pinned_research_endpoint, errors="coerce")
    audit_date = pd.to_datetime(audit_current_date, errors="coerce")

    frame = frame[frame["date"] > pinned].copy()
    frame = frame[frame["date"] <= audit_date].copy()
    frame = frame.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    if frame.empty:
        stream = pd.DataFrame(columns=required_output_columns)
        summary = _summary(
            stream=stream,
            signal_column=signal_col,
            failure_reason="no_post_endpoint_rule_input_rows",
        )
        return Phase6BReplayResult(stream=stream, summary=summary)

    close, returns, _close_col, _return_col = _normalise_benchmark(frame)

    weights = frame[signal_col].map(_normalise_signal_to_weight)
    weights_numeric = pd.to_numeric(weights, errors="coerce")

    benchmark_ok = close.notna() | returns.notna()
    weight_ok = weights_numeric.notna() & weights_numeric.between(0.0, 1.0)
    validity = benchmark_ok & weight_ok

    warnings: list[str] = []
    for idx in frame.index:
        row_warnings: list[str] = []
        if not benchmark_ok.loc[idx]:
            row_warnings.append("benchmark_update_missing")
        if not weight_ok.loc[idx]:
            row_warnings.append("phase6b_signal_could_not_map_to_target_weight")
        warnings.append(";".join(row_warnings))

    timestamp_col = _first_existing_col(
        frame,
        ["data_source_timestamp", "source_timestamp", "updated_at"],
    )
    timestamp = (
        frame[timestamp_col].astype(str)
        if timestamp_col
        else frame["date"].dt.strftime("%Y-%m-%d")
    )

    stream = pd.DataFrame(
        {
            "date": frame["date"].dt.strftime("%Y-%m-%d"),
            "SPY_close": close,
            "SPY_return": returns,
            "target_offensive_weight": weights_numeric,
            "target_weight_source": VALID_TARGET_WEIGHT_SOURCE,
            "data_source_timestamp": timestamp,
            "pinned_research_endpoint": pinned_research_endpoint,
            "is_out_of_sample_extension": True,
            "benchmark_update_flag": benchmark_ok.map({True: "pass", False: "fail"}),
            "stream_row_validity_flag": validity.map({True: "pass", False: "fail"}),
            "blocking_warnings": warnings,
        }
    )

    summary = _summary(
        stream=stream,
        signal_column=signal_col,
        failure_reason="",
    )
    return Phase6BReplayResult(stream=stream, summary=summary)


def _summary(
    *,
    stream: pd.DataFrame,
    signal_column: str,
    failure_reason: str,
) -> pd.DataFrame:
    rows = len(stream)

    benchmark_passed = (
        rows > 0
        and "benchmark_update_flag" in stream.columns
        and stream["benchmark_update_flag"].astype(str).str.lower().eq("pass").all()
    )
    validity_passed = (
        rows > 0
        and "stream_row_validity_flag" in stream.columns
        and stream["stream_row_validity_flag"].astype(str).str.lower().eq("pass").all()
    )
    target_source_passed = (
        rows > 0
        and "target_weight_source" in stream.columns
        and stream["target_weight_source"].astype(str).str.lower().eq(VALID_TARGET_WEIGHT_SOURCE).all()
    )
    out_of_sample_passed = (
        rows > 0
        and "is_out_of_sample_extension" in stream.columns
        and stream["is_out_of_sample_extension"].map(_bool_value).all()
    )

    if not failure_reason:
        failures = []
        if rows <= 0:
            failures.append("no_post_endpoint_rows")
        if not benchmark_passed:
            failures.append("benchmark_update_failed")
        if not validity_passed:
            failures.append("stream_row_validity_failed")
        if not target_source_passed:
            failures.append("target_weight_source_failed")
        if not out_of_sample_passed:
            failures.append("out_of_sample_label_failed")
        failure_reason = ";".join(failures)

    stream_valid = bool(
        rows > 0
        and benchmark_passed
        and validity_passed
        and target_source_passed
        and out_of_sample_passed
    )

    return pd.DataFrame(
        [
            {
                "post_endpoint_rows": rows,
                "rule_signal_column": signal_column,
                "benchmark_update_passed": benchmark_passed,
                "stream_row_validity_passed": validity_passed,
                "target_weight_source_passed": target_source_passed,
                "out_of_sample_label_passed": out_of_sample_passed,
                "rule_replay_stream_valid": stream_valid,
                "failure_reason": failure_reason,
            }
        ]
    )