from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
import pandas as pd


DEFAULT_PHASE10C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "audit_role": "Macro source reliability and point-in-time alignment audit only",
    "proposed_next_phase": "Phase 10D",
    "recommended_family": "macro_rates_inflation",
    "canonical_start_date": "2006-04-28",
    "canonical_end_date": "2026-05-01",
    "data_dir": "data/raw/macro",
    "allow_remote_fetch": False,
    "remote_fetch_timeout_seconds": 30,
    "allow_macro_signal_creation": False,
    "allow_allocation_rule_creation": False,
    "allow_model_feature_creation": False,
    "allow_model_training": False,
    "allow_strategy_test": False,
    "allow_strategy_promotion": False,
    "phase10d_boundary": {
        "allowed_next_step": "diagnostic-only macro regime analysis",
        "forbidden_next_step": "macro allocation rule, predictive model, or strategy test",
        "phase10d_may_create_macro_regime_diagnostic": True,
        "phase10d_may_create_strategy_signal": False,
        "phase10d_may_test_strategy": False,
        "phase10d_may_train_model": False,
        "phase10d_may_promote_candidate": False,
    },
    "selected_sources": [],
    "gates": {
        "min_selected_sources": 3,
        "min_loaded_series": 4,
        "min_phase10d_ready_series": 3,
        "min_aligned_availability_rate": 0.80,
        "require_remote_or_local_load_success": True,
        "require_release_policy_documented": True,
        "require_revision_policy_documented": True,
        "require_conservative_lag_applied": True,
        "require_revision_risk_documented": True,
        "require_rates_series_ready": True,
        "require_inflation_series_ready": True,
        "require_macro_series_ready": True,
        "require_no_macro_signal_creation": True,
        "require_no_allocation_rule_creation": True,
        "require_no_model_feature_creation": True,
        "require_no_model_training": True,
        "require_no_strategy_test": True,
        "require_no_strategy_promotion": True,
        "require_phase10d_boundary_diagnostic_only": True,
        "required_audit_role": (
            "Macro source reliability and point-in-time alignment audit only"
        ),
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase10c_macro_source_reliability_alignment_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE10C_CONFIG, user_config)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _selected_sources(phase_config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(source)
        for source in _as_list(phase_config.get("selected_sources"))
        if bool(source.get("selected_for_phase10c", False))
    ]


def build_phase10c_source_catalog(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source in _selected_sources(phase_config):
        series = _as_list(source.get("series"))
        rows.append(
            {
                "source_id": str(source.get("source_id", "")),
                "name": str(source.get("name", "")),
                "source_role": str(source.get("source_role", "")),
                "provider": str(source.get("provider", "")),
                "release_date_policy": str(source.get("release_date_policy", "")),
                "revision_policy": str(source.get("revision_policy", "")),
                "source_caveat": str(source.get("source_caveat", "")),
                "selected_for_phase10c": bool(
                    source.get("selected_for_phase10c", False)
                ),
                "allowed_for_phase10d_diagnostic": bool(
                    source.get("allowed_for_phase10d_diagnostic", False)
                ),
                "allowed_for_strategy_test": bool(
                    source.get("allowed_for_strategy_test", False)
                ),
                "series_count": len(series),
                "release_policy_documented": bool(
                    str(source.get("release_date_policy", "")).strip()
                ),
                "revision_policy_documented": bool(
                    str(source.get("revision_policy", "")).strip()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase10c_series_catalog(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for source in _selected_sources(phase_config):
        source_id = str(source.get("source_id", ""))
        source_role = str(source.get("source_role", ""))

        for series in _as_list(source.get("series")):
            rows.append(
                {
                    "source_id": source_id,
                    "source_role": source_role,
                    "series_id": str(series.get("series_id", "")),
                    "display_name": str(series.get("display_name", "")),
                    "fetch_url": str(series.get("fetch_url", "")),
                    "local_csv_path": str(series.get("local_csv_path", "")),
                    "date_column": str(series.get("date_column", "DATE")),
                    "value_column": str(series.get("value_column", "")),
                    "frequency": str(series.get("frequency", "")),
                    "value_type": str(series.get("value_type", "")),
                    "availability_lag_trading_days": int(
                        series.get("availability_lag_trading_days", 1)
                    ),
                    "has_explicit_release_dates": bool(
                        series.get("has_explicit_release_dates", False)
                    ),
                    "has_vintage_support": bool(
                        series.get("has_vintage_support", False)
                    ),
                    "uses_current_revised_values": bool(
                        series.get("uses_current_revised_values", False)
                    ),
                    "revision_risk_documented": bool(
                        series.get("revision_risk_documented", False)
                    ),
                }
            )

    return pd.DataFrame(rows)


def _read_remote_csv(url: str, timeout: int) -> pd.DataFrame:
    with urlopen(url, timeout=timeout) as response:
        payload = response.read()

    return pd.read_csv(BytesIO(payload), na_values=[".", ""])


def _normalise_series_frame(
    frame: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
    source_id: str,
    series_id: str,
) -> pd.DataFrame:
    if date_column not in frame.columns:
        fallback_date_columns = [
            "observation_date",
            "DATE",
            "date",
            "Date",
        ]
        matched_date_columns = [
            column for column in fallback_date_columns if column in frame.columns
        ]

        if matched_date_columns:
            date_column = matched_date_columns[0]
        else:
            raise ValueError(
                f"date_column {date_column!r} not found for {series_id}. "
                f"Available columns: {list(frame.columns)}"
            )

    resolved_value_column = value_column

    if resolved_value_column not in frame.columns:
        candidate_columns = [column for column in frame.columns if column != date_column]
        if not candidate_columns:
            raise ValueError(f"No value column found for {series_id}")
        resolved_value_column = str(candidate_columns[0])

    out = frame[[date_column, resolved_value_column]].copy()
    out.columns = ["date", "value"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    out["source_id"] = source_id
    out["series_id"] = series_id

    return out[["source_id", "series_id", "date", "value"]]


def build_phase10c_raw_series_frame(
    *,
    series_catalog: pd.DataFrame,
    allow_remote_fetch: bool,
    remote_fetch_timeout_seconds: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_frames: list[pd.DataFrame] = []
    load_rows: list[dict[str, Any]] = []

    for _, row in series_catalog.iterrows():
        source_id = str(row["source_id"])
        series_id = str(row["series_id"])
        local_csv_path = Path(str(row["local_csv_path"]))
        fetch_url = str(row["fetch_url"])
        loaded = False
        load_method = ""
        error = ""
        raw_frame = pd.DataFrame()

        try:
            if local_csv_path.exists():
                raw_frame = pd.read_csv(local_csv_path, na_values=[".", ""])
                loaded = True
                load_method = "local_csv"
            elif allow_remote_fetch and fetch_url:
                raw_frame = _read_remote_csv(
                    fetch_url,
                    timeout=int(remote_fetch_timeout_seconds),
                )
                loaded = True
                load_method = "remote_csv"
            else:
                error = "No local CSV found and remote fetch disabled."

            if loaded:
                normalised = _normalise_series_frame(
                    raw_frame,
                    date_column=str(row["date_column"]),
                    value_column=str(row["value_column"]),
                    source_id=source_id,
                    series_id=series_id,
                )
                raw_frames.append(normalised)

        except (OSError, ValueError, URLError) as exc:
            loaded = False
            error = str(exc)

        load_rows.append(
            {
                "source_id": source_id,
                "series_id": series_id,
                "loaded": loaded,
                "load_method": load_method,
                "raw_rows": int(len(raw_frame)) if loaded else 0,
                "error": error,
            }
        )

    raw_series = pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame(
        columns=["source_id", "series_id", "date", "value"]
    )
    load_report = pd.DataFrame(load_rows)

    return raw_series, load_report


def _extract_trading_calendar(
    *,
    ticker_outputs: dict[str, Any] | None,
    start_date: str,
    end_date: str,
) -> pd.DatetimeIndex:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    candidate_frames: list[pd.DataFrame] = []

    if ticker_outputs and "SPY" in ticker_outputs:
        spy_outputs = ticker_outputs["SPY"]

        for key in ["prices", "price_data", "data", "raw_data"]:
            value = spy_outputs.get(key) if isinstance(spy_outputs, dict) else None
            if isinstance(value, pd.DataFrame) and "date" in value.columns:
                candidate_frames.append(value)

        strategy_results = (
            spy_outputs.get("strategy_results", {})
            if isinstance(spy_outputs, dict)
            else {}
        )
        if isinstance(strategy_results, dict):
            for value in strategy_results.values():
                if isinstance(value, pd.DataFrame) and "date" in value.columns:
                    candidate_frames.append(value)

    for frame in candidate_frames:
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
        dates = dates[(dates >= start) & (dates <= end)].sort_values().unique()
        if len(dates) > 0:
            return pd.DatetimeIndex(dates)

    return pd.bdate_range(start=start, end=end)


def _available_date_for_observation(
    observation_date: pd.Timestamp,
    trading_calendar: pd.DatetimeIndex,
    lag_trading_days: int,
) -> pd.Timestamp | pd.NaT:
    if pd.isna(observation_date) or len(trading_calendar) == 0:
        return pd.NaT

    index = int(np.searchsorted(trading_calendar.values, observation_date.to_datetime64()))

    if index >= len(trading_calendar):
        return pd.NaT

    available_index = min(index + int(lag_trading_days), len(trading_calendar) - 1)

    return pd.Timestamp(trading_calendar[available_index])


def build_phase10c_aligned_series_frame(
    *,
    raw_series: pd.DataFrame,
    series_catalog: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    aligned_frames: list[pd.DataFrame] = []
    calendar_frame = pd.DataFrame({"trading_date": trading_calendar})

    for _, series_row in series_catalog.iterrows():
        source_id = str(series_row["source_id"])
        series_id = str(series_row["series_id"])
        lag_days = int(series_row["availability_lag_trading_days"])

        series = raw_series[
            (raw_series["source_id"] == source_id)
            & (raw_series["series_id"] == series_id)
        ].copy()

        if series.empty:
            continue

        series["available_date"] = series["date"].apply(
            lambda value: _available_date_for_observation(
                pd.Timestamp(value),
                trading_calendar,
                lag_days,
            )
        )
        series = series.dropna(subset=["available_date"])
        series = series.sort_values("available_date")

        aligned = pd.merge_asof(
            calendar_frame,
            series[["available_date", "value"]],
            left_on="trading_date",
            right_on="available_date",
            direction="backward",
        )
        aligned["source_id"] = source_id
        aligned["series_id"] = series_id
        aligned["availability_lag_trading_days"] = lag_days
        aligned["conservative_lag_applied"] = lag_days > 0

        aligned_frames.append(
            aligned[
                [
                    "source_id",
                    "series_id",
                    "trading_date",
                    "value",
                    "available_date",
                    "availability_lag_trading_days",
                    "conservative_lag_applied",
                ]
            ]
        )

    if not aligned_frames:
        return pd.DataFrame(
            columns=[
                "source_id",
                "series_id",
                "trading_date",
                "value",
                "available_date",
                "availability_lag_trading_days",
                "conservative_lag_applied",
            ]
        )

    return pd.concat(aligned_frames, ignore_index=True)


def build_phase10c_coverage_alignment_summary(
    *,
    raw_series: pd.DataFrame,
    aligned_series: pd.DataFrame,
    series_catalog: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    calendar_rows = max(1, len(trading_calendar))

    for _, series_row in series_catalog.iterrows():
        source_id = str(series_row["source_id"])
        series_id = str(series_row["series_id"])

        raw = raw_series[
            (raw_series["source_id"] == source_id)
            & (raw_series["series_id"] == series_id)
        ]
        aligned = aligned_series[
            (aligned_series["source_id"] == source_id)
            & (aligned_series["series_id"] == series_id)
        ]

        non_missing_aligned = int(aligned["value"].notna().sum()) if not aligned.empty else 0
        availability_rate = non_missing_aligned / calendar_rows

        rows.append(
            {
                "source_id": source_id,
                "source_role": str(series_row["source_role"]),
                "series_id": series_id,
                "frequency": str(series_row["frequency"]),
                "value_type": str(series_row["value_type"]),
                "raw_rows": int(len(raw)),
                "raw_start_date": pd.to_datetime(raw["date"].min()).date().isoformat()
                if not raw.empty
                else "",
                "raw_end_date": pd.to_datetime(raw["date"].max()).date().isoformat()
                if not raw.empty
                else "",
                "aligned_rows": int(len(aligned)),
                "non_missing_aligned_rows": non_missing_aligned,
                "aligned_availability_rate": availability_rate,
                "availability_lag_trading_days": int(
                    series_row["availability_lag_trading_days"]
                ),
                "conservative_lag_applied": int(
                    series_row["availability_lag_trading_days"]
                )
                > 0,
                "has_explicit_release_dates": bool(
                    series_row["has_explicit_release_dates"]
                ),
                "has_vintage_support": bool(series_row["has_vintage_support"]),
                "uses_current_revised_values": bool(
                    series_row["uses_current_revised_values"]
                ),
                "revision_risk_documented": bool(
                    series_row["revision_risk_documented"]
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase10c_phase10d_readiness(
    *,
    coverage_alignment_summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    min_ready_series = int(gates.get("min_phase10d_ready_series", 3))
    min_availability = float(gates.get("min_aligned_availability_rate", 0.80))

    if coverage_alignment_summary.empty:
        return pd.DataFrame(
            [
                {
                    "phase10d_allowed": False,
                    "ready_series_count": 0,
                    "ready_series": "",
                    "has_rates_series_ready": False,
                    "has_inflation_series_ready": False,
                    "has_macro_series_ready": False,
                    "next_phase": str(phase_config.get("proposed_next_phase", "")),
                    "reason": "No aligned series were available.",
                }
            ]
        )

    ready = coverage_alignment_summary[
        (coverage_alignment_summary["raw_rows"] > 0)
        & (coverage_alignment_summary["aligned_availability_rate"] >= min_availability)
        & (coverage_alignment_summary["conservative_lag_applied"])
        & (coverage_alignment_summary["revision_risk_documented"])
    ].copy()

    ready_roles = ready["source_role"].astype(str).tolist()
    has_rates = any("rates" in role for role in ready_roles)
    has_inflation = any("inflation" in role for role in ready_roles)
    has_macro = any("macro" in role for role in ready_roles)

    phase10d_allowed = (
        len(ready) >= min_ready_series
        and has_rates
        and has_inflation
        and has_macro
    )

    if phase10d_allowed:
        reason = (
            "Phase 10D may proceed only as diagnostic-only macro regime analysis; "
            "no signal, model, strategy test, or promotion is allowed."
        )
    else:
        reason = (
            "Phase 10D is not allowed until enough aligned macro/rates/inflation "
            "series pass coverage, lagging, and revision-risk checks."
        )

    return pd.DataFrame(
        [
            {
                "phase10d_allowed": phase10d_allowed,
                "ready_series_count": int(len(ready)),
                "ready_series": "; ".join(ready["series_id"].astype(str).tolist()),
                "has_rates_series_ready": has_rates,
                "has_inflation_series_ready": has_inflation,
                "has_macro_series_ready": has_macro,
                "next_phase": str(phase_config.get("proposed_next_phase", "")),
                "reason": reason,
            }
        ]
    )


def build_phase10c_phase10d_boundary_check(phase_config: dict[str, Any]) -> pd.DataFrame:
    boundary = phase_config.get("phase10d_boundary", {})

    rows = [
        {
            "boundary_item": "phase10d_allowed_next_step",
            "value": str(boundary.get("allowed_next_step", "")),
            "passed": "diagnostic" in str(boundary.get("allowed_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10d_forbidden_next_step",
            "value": str(boundary.get("forbidden_next_step", "")),
            "passed": "strategy" in str(boundary.get("forbidden_next_step", "")).lower()
            or "model" in str(boundary.get("forbidden_next_step", "")).lower(),
        },
        {
            "boundary_item": "phase10d_may_create_macro_regime_diagnostic",
            "value": bool(boundary.get("phase10d_may_create_macro_regime_diagnostic", False)),
            "passed": bool(boundary.get("phase10d_may_create_macro_regime_diagnostic", False)),
        },
        {
            "boundary_item": "phase10d_may_create_strategy_signal",
            "value": bool(boundary.get("phase10d_may_create_strategy_signal", True)),
            "passed": not bool(boundary.get("phase10d_may_create_strategy_signal", True)),
        },
        {
            "boundary_item": "phase10d_may_test_strategy",
            "value": bool(boundary.get("phase10d_may_test_strategy", True)),
            "passed": not bool(boundary.get("phase10d_may_test_strategy", True)),
        },
        {
            "boundary_item": "phase10d_may_train_model",
            "value": bool(boundary.get("phase10d_may_train_model", True)),
            "passed": not bool(boundary.get("phase10d_may_train_model", True)),
        },
        {
            "boundary_item": "phase10d_may_promote_candidate",
            "value": bool(boundary.get("phase10d_may_promote_candidate", True)),
            "passed": not bool(boundary.get("phase10d_may_promote_candidate", True)),
        },
    ]

    frame = pd.DataFrame(rows)
    frame["result"] = frame["passed"].map({True: "Passed", False: "Failed"})

    return frame


def build_phase10c_summary(
    *,
    phase_config: dict[str, Any],
    source_catalog: pd.DataFrame,
    series_catalog: pd.DataFrame,
    load_report: pd.DataFrame,
    coverage_alignment_summary: pd.DataFrame,
    phase10d_readiness: pd.DataFrame,
    phase10d_boundary_check: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})
    min_availability = float(gates.get("min_aligned_availability_rate", 0.80))

    ready = phase10d_readiness.iloc[0] if not phase10d_readiness.empty else {}

    return pd.DataFrame(
        [
            {
                "audit_role": str(phase_config.get("audit_role", "")),
                "recommended_family": str(phase_config.get("recommended_family", "")),
                "proposed_next_phase": str(phase_config.get("proposed_next_phase", "")),
                "selected_source_count": int(len(source_catalog)),
                "series_count": int(len(series_catalog)),
                "loaded_series_count": int(load_report["loaded"].sum())
                if not load_report.empty
                else 0,
                "min_aligned_availability_rate": min_availability,
                "series_passing_availability_count": int(
                    (
                        coverage_alignment_summary["aligned_availability_rate"]
                        >= min_availability
                    ).sum()
                )
                if not coverage_alignment_summary.empty
                else 0,
                "conservative_lagged_series_count": int(
                    coverage_alignment_summary["conservative_lag_applied"].sum()
                )
                if not coverage_alignment_summary.empty
                else 0,
                "revision_risk_documented_series_count": int(
                    coverage_alignment_summary["revision_risk_documented"].sum()
                )
                if not coverage_alignment_summary.empty
                else 0,
                "phase10d_allowed": _bool_value(
                    ready.get("phase10d_allowed", False)
                ),
                "phase10d_ready_series_count": int(
                    ready.get("ready_series_count", 0)
                ),
                "phase10d_boundary_passed": bool(
                    phase10d_boundary_check["passed"].all()
                )
                if not phase10d_boundary_check.empty
                else False,
                "allow_macro_signal_creation": bool(
                    phase_config.get("allow_macro_signal_creation", False)
                ),
                "allow_allocation_rule_creation": bool(
                    phase_config.get("allow_allocation_rule_creation", False)
                ),
                "allow_model_feature_creation": bool(
                    phase_config.get("allow_model_feature_creation", False)
                ),
                "allow_model_training": bool(
                    phase_config.get("allow_model_training", False)
                ),
                "allow_strategy_test": bool(
                    phase_config.get("allow_strategy_test", False)
                ),
                "allow_strategy_promotion": bool(
                    phase_config.get("allow_strategy_promotion", False)
                ),
                "strategy_promotion": False,
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase10c_gate_report(
    *,
    phase_config: dict[str, Any],
    source_catalog: pd.DataFrame,
    load_report: pd.DataFrame,
    coverage_alignment_summary: pd.DataFrame,
    phase10d_readiness: pd.DataFrame,
    phase10d_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 10C summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    min_sources = int(gates.get("min_selected_sources", 3))
    min_loaded_series = int(gates.get("min_loaded_series", 4))
    min_ready_series = int(gates.get("min_phase10d_ready_series", 3))
    min_availability = float(gates.get("min_aligned_availability_rate", 0.80))
    required_role = str(
        gates.get(
            "required_audit_role",
            "Macro source reliability and point-in-time alignment audit only",
        )
    )

    all_sources_have_release_policy = (
        bool(source_catalog["release_policy_documented"].all())
        if not source_catalog.empty
        else False
    )
    all_sources_have_revision_policy = (
        bool(source_catalog["revision_policy_documented"].all())
        if not source_catalog.empty
        else False
    )
    load_success = (
        int(row["loaded_series_count"]) >= min_loaded_series
        if not load_report.empty
        else False
    )
    availability_ok = (
        bool(
            (
                coverage_alignment_summary["aligned_availability_rate"]
                >= min_availability
            ).all()
        )
        if not coverage_alignment_summary.empty
        else False
    )
    all_lagged = (
        bool(coverage_alignment_summary["conservative_lag_applied"].all())
        if not coverage_alignment_summary.empty
        else False
    )
    all_revision_risk_documented = (
        bool(coverage_alignment_summary["revision_risk_documented"].all())
        if not coverage_alignment_summary.empty
        else False
    )

    readiness = phase10d_readiness.iloc[0] if not phase10d_readiness.empty else {}

    rows = [
        _gate_row(
            "Selected source count is sufficient",
            int(row["selected_source_count"]) >= min_sources,
            f"{int(row['selected_source_count'])} sources; required >= {min_sources}",
        ),
        _gate_row(
            "Remote/local macro series load succeeded",
            (not gates.get("require_remote_or_local_load_success", True))
            or load_success,
            f"loaded_series_count={int(row['loaded_series_count'])}; required >= {min_loaded_series}",
        ),
        _gate_row(
            "Release-date policies are documented",
            (not gates.get("require_release_policy_documented", True))
            or all_sources_have_release_policy,
            "Every selected source must document release-date handling.",
        ),
        _gate_row(
            "Revision/vintage policies are documented",
            (not gates.get("require_revision_policy_documented", True))
            or all_sources_have_revision_policy,
            "Every selected source must document revision/vintage treatment.",
        ),
        _gate_row(
            "Aligned series meet missingness threshold",
            availability_ok,
            f"minimum required availability={min_availability:.2%}",
        ),
        _gate_row(
            "Conservative trading-day lag is applied",
            (not gates.get("require_conservative_lag_applied", True))
            or all_lagged,
            f"conservative_lagged_series_count={int(row['conservative_lagged_series_count'])}",
        ),
        _gate_row(
            "Revision risk is documented for every series",
            (not gates.get("require_revision_risk_documented", True))
            or all_revision_risk_documented,
            (
                "revision_risk_documented_series_count="
                f"{int(row['revision_risk_documented_series_count'])}"
            ),
        ),
        _gate_row(
            "Rates series is ready for diagnostic audit",
            (not gates.get("require_rates_series_ready", True))
            or _bool_value(readiness.get("has_rates_series_ready", False)),
            f"has_rates_series_ready={readiness.get('has_rates_series_ready', False)}",
        ),
        _gate_row(
            "Inflation series is ready for diagnostic audit",
            (not gates.get("require_inflation_series_ready", True))
            or _bool_value(readiness.get("has_inflation_series_ready", False)),
            (
                "has_inflation_series_ready="
                f"{readiness.get('has_inflation_series_ready', False)}"
            ),
        ),
        _gate_row(
            "Macro series is ready for diagnostic audit",
            (not gates.get("require_macro_series_ready", True))
            or _bool_value(readiness.get("has_macro_series_ready", False)),
            f"has_macro_series_ready={readiness.get('has_macro_series_ready', False)}",
        ),
        _gate_row(
            "No macro signal creation is allowed",
            (not gates.get("require_no_macro_signal_creation", True))
            or not bool(row["allow_macro_signal_creation"]),
            f"allow_macro_signal_creation={bool(row['allow_macro_signal_creation'])}",
        ),
        _gate_row(
            "No allocation rule creation is allowed",
            (not gates.get("require_no_allocation_rule_creation", True))
            or not bool(row["allow_allocation_rule_creation"]),
            (
                "allow_allocation_rule_creation="
                f"{bool(row['allow_allocation_rule_creation'])}"
            ),
        ),
        _gate_row(
            "No model feature creation is allowed",
            (not gates.get("require_no_model_feature_creation", True))
            or not bool(row["allow_model_feature_creation"]),
            f"allow_model_feature_creation={bool(row['allow_model_feature_creation'])}",
        ),
        _gate_row(
            "No model training is allowed",
            (not gates.get("require_no_model_training", True))
            or not bool(row["allow_model_training"]),
            f"allow_model_training={bool(row['allow_model_training'])}",
        ),
        _gate_row(
            "No strategy test is allowed",
            (not gates.get("require_no_strategy_test", True))
            or not bool(row["allow_strategy_test"]),
            f"allow_strategy_test={bool(row['allow_strategy_test'])}",
        ),
        _gate_row(
            "No strategy promotion is allowed",
            (not gates.get("require_no_strategy_promotion", True))
            or not bool(row["allow_strategy_promotion"]),
            f"allow_strategy_promotion={bool(row['allow_strategy_promotion'])}",
        ),
        _gate_row(
            "Phase 10D boundary is diagnostic-only",
            (not gates.get("require_phase10d_boundary_diagnostic_only", True))
            or bool(phase10d_boundary_check["passed"].all()),
            f"phase10d_boundary_passed={bool(row['phase10d_boundary_passed'])}",
        ),
        _gate_row(
            "Enough series are ready to allow Phase 10D diagnostic-only analysis",
            int(row["phase10d_ready_series_count"]) >= min_ready_series
            and bool(row["phase10d_allowed"]),
            (
                f"ready_series_count={int(row['phase10d_ready_series_count'])}; "
                f"required >= {min_ready_series}; phase10d_allowed={bool(row['phase10d_allowed'])}"
            ),
        ),
        _gate_row(
            "Audit role is correct",
            str(row["audit_role"]) == required_role,
            f"audit_role={row['audit_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase10c_conclusion(
    *,
    gate_report: pd.DataFrame,
    phase10d_readiness: pd.DataFrame,
) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    readiness = phase10d_readiness.iloc[0] if not phase10d_readiness.empty else {}
    phase10d_allowed = _bool_value(readiness.get("phase10d_allowed", False))
    ready_series = str(readiness.get("ready_series", ""))

    if all_passed and phase10d_allowed:
        verdict = "Completed — macro source reliability/alignment audit passed"
        interpretation = (
            "Phase 10C loaded/aligned selected macro/rates/inflation sources with "
            "conservative lagging and documented revision risk. Phase 10D is allowed "
            "only as diagnostic macro regime analysis, not as a signal, model, "
            "strategy test, or candidate promotion."
        )
    else:
        verdict = "Failed macro source reliability/alignment audit"
        interpretation = (
            "Phase 10C did not satisfy every source reliability/alignment gate. "
            "Do not open Phase 10D until load, coverage, lagging, revision-risk, "
            "or boundary issues are corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 10C",
                "diagnostic": "Macro source reliability and point-in-time alignment audit",
                "verdict": verdict,
                "phase10d_allowed": phase10d_allowed,
                "ready_series": ready_series,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase10c_markdown(
    *,
    source_catalog: pd.DataFrame,
    series_catalog: pd.DataFrame,
    load_report: pd.DataFrame,
    coverage_alignment_summary: pd.DataFrame,
    phase10d_readiness: pd.DataFrame,
    phase10d_boundary_check: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 10C — Macro Source Reliability & Point-in-Time Alignment Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit loads or fetches selected macro/rates/inflation sources and "
            "checks source reliability, coverage, conservative trading-day lagging, "
            "revision/vintage risk, missingness, and Phase 10D readiness."
        ),
        "",
        (
            "It does not create macro signals, allocation rules, predictive model "
            "features, model training, strategy tests, or candidate promotion."
        ),
        "",
        "## Source Catalog",
        "",
        source_catalog.to_markdown(index=False),
        "",
        "## Series Catalog",
        "",
        series_catalog.to_markdown(index=False),
        "",
        "## Load Report",
        "",
        load_report.to_markdown(index=False),
        "",
        "## Coverage / Alignment Summary",
        "",
        coverage_alignment_summary.to_markdown(index=False),
        "",
        "## Phase 10D Readiness",
        "",
        phase10d_readiness.to_markdown(index=False),
        "",
        "## Phase 10D Boundary Check",
        "",
        phase10d_boundary_check.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is a source/alignment audit only.",
        "- Current revised macro values may still carry revision risk.",
        "- Conservative lagging reduces but does not eliminate all real-time timing risk.",
        "- Phase 10D may only be diagnostic regime analysis.",
        "- No macro signal or strategy test is allowed from this phase.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase10c_macro_source_reliability_alignment_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "source_catalog": empty,
            "series_catalog": empty,
            "raw_series": empty,
            "load_report": empty,
            "aligned_series": empty,
            "coverage_alignment_summary": empty,
            "phase10d_readiness": empty,
            "phase10d_boundary_check": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_catalog = build_phase10c_source_catalog(phase_config)
    series_catalog = build_phase10c_series_catalog(phase_config)
    raw_series, load_report = build_phase10c_raw_series_frame(
        series_catalog=series_catalog,
        allow_remote_fetch=bool(phase_config.get("allow_remote_fetch", False)),
        remote_fetch_timeout_seconds=int(
            phase_config.get("remote_fetch_timeout_seconds", 30)
        ),
    )
    trading_calendar = _extract_trading_calendar(
        ticker_outputs=ticker_outputs,
        start_date=str(phase_config.get("canonical_start_date", "2006-04-28")),
        end_date=str(phase_config.get("canonical_end_date", "2026-05-01")),
    )
    aligned_series = build_phase10c_aligned_series_frame(
        raw_series=raw_series,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    coverage_alignment_summary = build_phase10c_coverage_alignment_summary(
        raw_series=raw_series,
        aligned_series=aligned_series,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    phase10d_readiness = build_phase10c_phase10d_readiness(
        coverage_alignment_summary=coverage_alignment_summary,
        phase_config=phase_config,
    )
    phase10d_boundary_check = build_phase10c_phase10d_boundary_check(phase_config)
    summary = build_phase10c_summary(
        phase_config=phase_config,
        source_catalog=source_catalog,
        series_catalog=series_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage_alignment_summary,
        phase10d_readiness=phase10d_readiness,
        phase10d_boundary_check=phase10d_boundary_check,
    )
    gate_report = build_phase10c_gate_report(
        phase_config=phase_config,
        source_catalog=source_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage_alignment_summary,
        phase10d_readiness=phase10d_readiness,
        phase10d_boundary_check=phase10d_boundary_check,
        summary=summary,
    )
    conclusion = build_phase10c_conclusion(
        gate_report=gate_report,
        phase10d_readiness=phase10d_readiness,
    )

    source_catalog.to_csv(reports_path / "phase10c_macro_source_catalog.csv", index=False)
    series_catalog.to_csv(reports_path / "phase10c_macro_series_catalog.csv", index=False)
    raw_series.to_csv(reports_path / "phase10c_macro_raw_series.csv", index=False)
    load_report.to_csv(reports_path / "phase10c_macro_load_report.csv", index=False)
    aligned_series.to_csv(reports_path / "phase10c_macro_aligned_series.csv", index=False)
    coverage_alignment_summary.to_csv(
        reports_path / "phase10c_macro_coverage_alignment_summary.csv",
        index=False,
    )
    phase10d_readiness.to_csv(
        reports_path / "phase10c_macro_phase10d_readiness.csv",
        index=False,
    )
    phase10d_boundary_check.to_csv(
        reports_path / "phase10c_macro_phase10d_boundary_check.csv",
        index=False,
    )
    summary.to_csv(reports_path / "phase10c_macro_summary.csv", index=False)
    gate_report.to_csv(reports_path / "phase10c_macro_gate_report.csv", index=False)
    conclusion.to_csv(reports_path / "phase10c_macro_conclusion.csv", index=False)

    write_phase10c_markdown(
        source_catalog=source_catalog,
        series_catalog=series_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage_alignment_summary,
        phase10d_readiness=phase10d_readiness,
        phase10d_boundary_check=phase10d_boundary_check,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path
        / "phase10c_macro_source_reliability_alignment_audit.md",
    )

    print("Wrote Phase 10C macro source reliability/alignment audit reports.")

    return {
        "source_catalog": source_catalog,
        "series_catalog": series_catalog,
        "raw_series": raw_series,
        "load_report": load_report,
        "aligned_series": aligned_series,
        "coverage_alignment_summary": coverage_alignment_summary,
        "phase10d_readiness": phase10d_readiness,
        "phase10d_boundary_check": phase10d_boundary_check,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }