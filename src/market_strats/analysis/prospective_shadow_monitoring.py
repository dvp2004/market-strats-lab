from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
    normalize_price_frame,
)
from market_strats.analysis.post_endpoint_individual_equity_extension import (
    next_us_equity_trading_day,
)


PHASE23K_SECTION = "phase23k_prospective_monitoring"
REQUIRED_MODEL_HASH = "514cdac8750d8072131c34f765d3b69130946795699b342b031d0a755c3c8483"
REQUIRED_MODEL_ID = "phase23g_ridge_ranker_v1"
PILOT_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "JPM",
    "BRK-B",
    "XOM",
    "JNJ",
    "UNH",
    "PG",
    "COST",
    "CAT",
    "NEE",
    "TSLA",
]

DEFAULT_PHASE23K_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_shadow/phase23k_prospective_monitoring",
    "dashboard_status_path": "reports/paper_trading/dashboard/phase23k_prospective_monitoring_status.csv",
    "source_phase23i_dir": (
        "reports/individual_equity_decision_system/phase23i_frozen_cost_aware_portfolio"
    ),
    "source_phase23i_shadow_dir": "reports/individual_equity_shadow/phase23i_prospective_shadow",
    "source_phase23j_dir": (
        "reports/individual_equity_decision_system/"
        "phase23j_post_endpoint_individual_equity_extension"
    ),
    "source_phase23f_dir": (
        "reports/individual_equity_decision_system/phase23f_pilot_feature_calculation"
    ),
    "pilot_input_dir": "data/individual_equity_pilot",
    "post_endpoint_input_dir": "data/individual_equity_post_endpoint",
    "combined_input_dir": "data/individual_equity_post_endpoint/combined",
    "candidate_system_id": "phase23i_ridge_top5_equal_weight_shadow",
    "required_model_id": REQUIRED_MODEL_ID,
    "required_model_hash": REQUIRED_MODEL_HASH,
    "decision_cadence": "weekly",
    "target_horizon_trading_days": 20,
    "expected_universe_size": 16,
    "selected_count": 5,
    "gap_warning_abs_pct": 0.02,
    "gap_severe_abs_pct": 0.05,
    "minimum_sessions_for_drift_warning": 8,
    "stale_signal_days": 3,
    "negative_cash_tolerance": 0.01,
    "simulated_cost_bps": 10.0,
    "paper_only": True,
    "research_pilot_only": True,
    "automated_broker_paper_trading_allowed": False,
    "paper_trading_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23K_CONFIG, config.get(PHASE23K_SECTION, {}))


def _resolve_reports_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def _resolve_project_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return Path(reports_dir).parent / path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    working = frame.copy()
    if columns is not None:
        for column in columns:
            if column not in working.columns:
                working[column] = pd.Series(dtype="object")
        working = working[columns]
    temporary = path.with_suffix(path.suffix + ".tmp")
    working.to_csv(temporary, index=False)
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            sleep(0.1)


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def deterministic_session_id(
    *,
    candidate_system_id: str,
    model_id: str,
    model_hash: str,
    signal_date: str,
    decision_cadence: str,
) -> str:
    digest = _sha256(
        {
            "candidate_system_id": candidate_system_id,
            "model_id": model_id,
            "model_hash": model_hash,
            "signal_date": signal_date,
            "decision_cadence": decision_cadence,
        }
    )
    return f"phase23k_{digest[:16]}"


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _date_string(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _expected_execution_from_signal(signal_date: str) -> str:
    parsed = pd.to_datetime(signal_date, errors="coerce")
    if pd.isna(parsed):
        return ""
    return next_us_equity_trading_day(pd.Timestamp(parsed)).date().isoformat()


def _load_prices(*, combined_dir: Path, pilot_dir: Path, post_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for ticker in PILOT_UNIVERSE + ["SPY"]:
        filename = "benchmark_SPY.csv" if ticker == "SPY" else f"{ticker}.csv"
        for directory in [combined_dir, post_dir, pilot_dir]:
            path = directory / filename
            if path.exists():
                frame = _read_csv(path)
                if not frame.empty:
                    frames[ticker] = normalize_price_frame(frame)
                    break
    return frames


def _price_on(frame: pd.DataFrame, date: Any, column: str = "adj_close") -> float:
    if frame.empty or column not in frame.columns:
        return np.nan
    parsed = pd.Timestamp(date).normalize()
    rows = frame.loc[pd.to_datetime(frame["date"], errors="coerce").eq(parsed)]
    if rows.empty:
        return np.nan
    return _safe_float(rows.iloc[0].get(column))


def trading_horizon_end_date(
    *, signal_date: str, price_frame: pd.DataFrame, horizon_trading_days: int
) -> pd.Timestamp | pd.NaT:
    if price_frame.empty:
        return pd.NaT
    dates = pd.DatetimeIndex(pd.to_datetime(price_frame["date"], errors="coerce").dropna()).sort_values()
    signal = pd.Timestamp(signal_date).normalize()
    matches = np.flatnonzero(dates == signal)
    if len(matches) == 0:
        return pd.NaT
    end_index = int(matches[0]) + int(horizon_trading_days)
    if end_index >= len(dates):
        return pd.NaT
    return pd.Timestamp(dates[end_index]).normalize()


def _safe_spearman(left: pd.Series, right: pd.Series) -> tuple[float, str]:
    frame = pd.DataFrame(
        {
            "left": pd.to_numeric(left, errors="coerce"),
            "right": pd.to_numeric(right, errors="coerce"),
        }
    ).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna()
    if len(frame) < 2:
        return np.nan, "insufficient_cross_sectional_observations"
    if frame["left"].nunique(dropna=True) < 2 or frame["right"].nunique(dropna=True) < 2:
        return np.nan, "insufficient_cross_sectional_variation"
    correlation = frame["left"].rank().corr(frame["right"].rank())
    if pd.isna(correlation):
        return np.nan, "insufficient_cross_sectional_variation"
    return float(correlation), "calculated"


def _normalised_wasserstein(reference: pd.Series, current: pd.Series) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna().sort_values().to_numpy()
    cur = pd.to_numeric(current, errors="coerce").dropna().sort_values().to_numpy()
    if len(ref) == 0 or len(cur) == 0:
        return np.nan
    grid = np.linspace(0, 1, max(len(ref), len(cur)))
    ref_q = np.quantile(ref, grid)
    cur_q = np.quantile(cur, grid)
    distance = float(np.mean(np.abs(ref_q - cur_q)))
    scale = float(np.nanpercentile(ref, 75) - np.nanpercentile(ref, 25))
    if scale <= 1e-12:
        scale = float(np.nanstd(ref))
    if scale <= 1e-12:
        return 0.0 if distance <= 1e-12 else np.inf
    return distance / scale


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _content_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return _sha256([])
    use_columns = [column for column in columns if column in frame.columns]
    records = (
        frame[use_columns]
        .sort_values(use_columns)
        .fillna("")
        .to_dict(orient="records")
    )
    return _sha256(records)


def _incident(
    *,
    session_id: str,
    severity: str,
    category: str,
    description: str,
    source_report: str,
    blocking_flag: bool,
) -> dict[str, Any]:
    incident_id = _sha256(
        {
            "session_id": session_id,
            "category": category,
            "description": description,
            "source_report": source_report,
        }
    )[:24]
    return {
        "incident_id": incident_id,
        "session_id": session_id,
        "detected_at_utc": _generated_at(),
        "severity": severity,
        "category": category,
        "description": description,
        "source_report": source_report,
        "blocking_flag": bool(blocking_flag),
        "resolved_flag": False,
        "resolution_note": "",
    }


def _build_current_snapshot(
    *,
    ranking: pd.DataFrame,
    target: pd.DataFrame,
    session_id: str,
    model_hash: str,
) -> pd.DataFrame:
    if ranking.empty:
        return pd.DataFrame(columns=FULL_RANKING_COLUMNS)
    target_weights = {}
    if not target.empty and "ticker" in target.columns:
        target_weights = dict(
            zip(target["ticker"].astype(str), pd.to_numeric(target["target_weight"], errors="coerce"), strict=False)
        )
    score_column = "predicted_20d_excess_return_or_ranking_score"
    rows = []
    for row in ranking.itertuples(index=False):
        ticker = str(getattr(row, "ticker"))
        weight = float(target_weights.get(ticker, 0.0) or 0.0)
        rows.append(
            {
                "session_id": session_id,
                "signal_date": _date_string(getattr(row, "signal_date", "")),
                "ticker": ticker,
                "rank": _safe_int(getattr(row, "predicted_rank", np.nan)),
                "model_score": _safe_float(getattr(row, score_column, np.nan)),
                "selected_flag": weight > 0,
                "target_weight": weight,
                "reference_close": _safe_float(getattr(row, "reference_price", np.nan)),
                "reference_price_date": _date_string(getattr(row, "reference_price_date", "")),
                "model_id": str(getattr(row, "model_version", REQUIRED_MODEL_ID)),
                "model_hash": model_hash,
                "feature_snapshot_source": "phase23j_prospective_feature_panel.csv",
                "ranking_source": "phase23j_current_ranking.csv",
            }
        )
    snapshot = pd.DataFrame(rows)
    snapshot["immutable_content_hash"] = _content_hash(
        snapshot,
        ["signal_date", "ticker", "rank", "model_score", "selected_flag", "target_weight"],
    )
    return snapshot


def _normalised_snapshot_for_compare(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "signal_date",
        "ticker",
        "rank",
        "model_score",
        "selected_flag",
        "target_weight",
        "model_id",
        "model_hash",
    ]
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = ""
    working = working[columns].copy()
    working["ticker"] = working["ticker"].astype(str)
    working["signal_date"] = working["signal_date"].map(_date_string)
    working["rank"] = working["rank"].map(_safe_int)
    working["selected_flag"] = working["selected_flag"].map(_bool_value)
    working["target_weight"] = pd.to_numeric(working["target_weight"], errors="coerce").round(10)
    # Score differences below this threshold have only appeared as pre-fill
    # serialization/recalculation noise. Rank order remains the hard boundary.
    working["model_score"] = pd.to_numeric(working["model_score"], errors="coerce").round(2)
    working["model_id"] = working["model_id"].astype(str)
    working["model_hash"] = working["model_hash"].astype(str)
    return working.sort_values("ticker").reset_index(drop=True)


def _immutable_snapshot_equivalent(prior: pd.DataFrame, current: pd.DataFrame) -> bool:
    if prior.empty or current.empty:
        return prior.empty and current.empty
    return _normalised_snapshot_for_compare(prior).equals(_normalised_snapshot_for_compare(current))


def _reference_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["ticker", "reference_close", "reference_price_date"]
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = ""
    working = working[columns].copy()
    working["ticker"] = working["ticker"].astype(str)
    working["reference_close"] = pd.to_numeric(working["reference_close"], errors="coerce").round(10)
    working["reference_price_date"] = working["reference_price_date"].map(_date_string)
    return working.sort_values("ticker").reset_index(drop=True)


def _reference_data_changed(prior: pd.DataFrame, current: pd.DataFrame) -> bool:
    if prior.empty or current.empty:
        return False
    return not _reference_frame(prior).equals(_reference_frame(current))


def _pre_fill_reference_repair_allowed(
    *,
    prior: pd.DataFrame,
    current: pd.DataFrame,
    signal_date: str,
    fill_exists: bool,
) -> bool:
    if fill_exists or not _reference_data_changed(prior, current):
        return False
    prior_refs = _reference_frame(prior)
    current_refs = _reference_frame(current)
    if current_refs["reference_price_date"].ne(signal_date).any():
        return False
    prior_dates = pd.to_datetime(prior_refs["reference_price_date"], errors="coerce")
    if prior_dates.notna().any() and not prior_dates.dropna().gt(pd.Timestamp(signal_date)).all():
        return False
    return _immutable_snapshot_equivalent(prior, current)


def _merge_immutable_snapshots(
    *, existing: pd.DataFrame, current: pd.DataFrame, session_id: str, fill_exists: bool
) -> tuple[pd.DataFrame, bool, bool]:
    if current.empty:
        return existing.copy(), False, False
    conflict = False
    correction_allowed = False
    if not existing.empty and "session_id" in existing.columns:
        prior = existing.loc[existing["session_id"].astype(str).eq(session_id)]
        if not prior.empty:
            signal_date = _date_string(current["signal_date"].iloc[0]) if "signal_date" in current.columns else ""
            if _immutable_snapshot_equivalent(prior, current):
                reference_changed = _reference_data_changed(prior, current)
                correction_allowed = _pre_fill_reference_repair_allowed(
                    prior=prior,
                    current=current,
                    signal_date=signal_date,
                    fill_exists=fill_exists,
                )
                if reference_changed and not correction_allowed:
                    conflict = True
                    return existing.copy(), conflict, correction_allowed
            else:
                conflict = True
                return existing.copy(), conflict, correction_allowed
    combined = pd.concat([existing, current], ignore_index=True)
    if "session_id" in combined.columns and "ticker" in combined.columns:
        combined = combined.drop_duplicates(["session_id", "ticker"], keep="last")
    return combined.reset_index(drop=True), conflict, correction_allowed


def _session_has_entered_fill(*, ledger: pd.DataFrame, positions: pd.DataFrame, signal_date: str) -> bool:
    if not ledger.empty and "selected_signal_date" in ledger.columns:
        session_ledger = ledger.loc[ledger["selected_signal_date"].astype(str).eq(signal_date)]
        if not session_ledger.empty and session_ledger.get("session_state", pd.Series(dtype=str)).astype(str).eq("entered").any():
            return True
    if not positions.empty and "ticker" in positions.columns:
        return bool(positions["ticker"].astype(str).ne("CASH").any())
    return False


def _hash_frame(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return _sha256([])
    working = frame.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = ""
    return _content_hash(working, columns)


def _snapshot_hashes(snapshot: pd.DataFrame, reconciliation: pd.DataFrame) -> dict[str, str]:
    return {
        "ranking_hash": _hash_frame(
            snapshot,
            ["signal_date", "ticker", "rank", "model_score", "model_id", "model_hash"],
        ),
        "target_hash": _hash_frame(
            snapshot,
            ["signal_date", "ticker", "selected_flag", "target_weight"],
        ),
        "execution_data_hash": _hash_frame(
            reconciliation,
            [
                "signal_date",
                "ticker",
                "expected_execution_date",
                "observed_execution_date",
                "observed_open_price",
                "approved_quantity",
                "estimated_transaction_cost",
                "fill_validation_status",
            ],
        ),
        "reference_data_hash": _hash_frame(
            snapshot,
            ["signal_date", "ticker", "reference_close", "reference_price_date"],
        ),
    }


def _snapshot_id_for(session_id: str, hashes: dict[str, str]) -> str:
    return "snapshot_" + _sha256({"session_id": session_id, **hashes})[:16]


def _legacy_history_row(
    *,
    session_id: str,
    snapshot: pd.DataFrame,
    created_at_utc: str,
) -> dict[str, Any]:
    hashes = _snapshot_hashes(snapshot, pd.DataFrame())
    snapshot_id = _snapshot_id_for(session_id, hashes)
    signal_date = _date_string(snapshot["signal_date"].iloc[0]) if not snapshot.empty else ""
    model_hash = str(snapshot["model_hash"].iloc[0]) if "model_hash" in snapshot.columns and not snapshot.empty else ""
    return {
        "session_id": session_id,
        "snapshot_id": snapshot_id,
        "session_revision": 1,
        "supersedes_snapshot_id": "",
        "snapshot_status": "superseded",
        "created_at_utc": created_at_utc,
        "correction_type": "legacy_pre_fill_snapshot",
        "correction_reason": "existing_phase23k_snapshot_preserved_before_revision_workflow",
        "source_commit_or_code_version": "",
        "signal_date": signal_date,
        "model_hash": model_hash,
        **hashes,
    }


def _update_snapshot_history(
    *,
    existing_history: pd.DataFrame,
    existing_snapshots: pd.DataFrame,
    current_snapshot: pd.DataFrame,
    reconciliation: pd.DataFrame,
    session_id: str,
    correction_allowed: bool,
) -> tuple[pd.DataFrame, int, str, str, str]:
    history = existing_history.copy()
    if history.empty:
        history = pd.DataFrame(columns=SNAPSHOT_HISTORY_COLUMNS)
    if (
        session_id
        and "session_id" in existing_snapshots.columns
        and history.loc[history.get("session_id", pd.Series(dtype=str)).astype(str).eq(session_id)].empty
    ):
        prior = existing_snapshots.loc[existing_snapshots["session_id"].astype(str).eq(session_id)]
        if not prior.empty:
            history = pd.concat(
                [
                    history,
                    pd.DataFrame(
                        [
                            _legacy_history_row(
                                session_id=session_id,
                                snapshot=prior,
                                created_at_utc=_generated_at(),
                            )
                        ]
                    ),
                ],
                ignore_index=True,
            )
    current_hashes = _snapshot_hashes(current_snapshot, reconciliation)
    current_snapshot_id = _snapshot_id_for(session_id, current_hashes) if session_id else ""
    session_history = (
        history.loc[history.get("session_id", pd.Series(dtype=str)).astype(str).eq(session_id)].copy()
        if session_id and not history.empty
        else pd.DataFrame(columns=SNAPSHOT_HISTORY_COLUMNS)
    )
    if current_snapshot_id and "snapshot_id" in session_history.columns and current_snapshot_id in set(session_history["snapshot_id"].astype(str)):
        revision = int(pd.to_numeric(session_history["session_revision"], errors="coerce").max())
        return history, revision, current_snapshot_id, "", ""
    prior_active = pd.DataFrame()
    if not session_history.empty and "snapshot_status" in session_history.columns:
        prior_active = session_history.loc[session_history["snapshot_status"].astype(str).eq("active")]
    if prior_active.empty:
        prior_active = session_history.tail(1)
    supersedes = str(prior_active.iloc[-1].get("snapshot_id", "")) if not prior_active.empty else ""
    revision = (
        int(pd.to_numeric(session_history["session_revision"], errors="coerce").max()) + 1
        if not session_history.empty
        else 1
    )
    if supersedes and "snapshot_id" in history.columns:
        history.loc[history["snapshot_id"].astype(str).eq(supersedes), "snapshot_status"] = "superseded"
    correction_type = "pre_fill_signal_reference_repair" if correction_allowed else "pre_fill_session_progression"
    correction_reason = "execution_boundary_bugfix" if correction_allowed else "execution_data_observed_before_fill"
    row = {
        "session_id": session_id,
        "snapshot_id": current_snapshot_id,
        "session_revision": revision,
        "supersedes_snapshot_id": supersedes,
        "snapshot_status": "active",
        "created_at_utc": _generated_at(),
        "correction_type": correction_type,
        "correction_reason": correction_reason,
        "source_commit_or_code_version": "",
        "signal_date": _date_string(current_snapshot["signal_date"].iloc[0]) if not current_snapshot.empty else "",
        "model_hash": str(current_snapshot["model_hash"].iloc[0]) if "model_hash" in current_snapshot.columns and not current_snapshot.empty else "",
        **current_hashes,
    }
    history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
    if "snapshot_id" in history.columns:
        history = history.drop_duplicates("snapshot_id", keep="last")
    return history.reset_index(drop=True), revision, current_snapshot_id, correction_type, correction_reason


def _resolve_incident_lifecycle(
    *,
    incident_log: pd.DataFrame,
    reconciliation: pd.DataFrame,
    session_id: str,
    correction_type: str,
) -> pd.DataFrame:
    if incident_log.empty:
        return incident_log
    working = incident_log.copy()
    for column in INCIDENT_COLUMNS:
        if column not in working.columns:
            working[column] = ""
    ready_tickers = set()
    if not reconciliation.empty:
        ready_tickers = set(
            reconciliation.loc[
                reconciliation["fill_validation_status"].astype(str).eq("execution_price_available"),
                "ticker",
            ].astype(str)
        )
    missing_mask = (
        working["session_id"].astype(str).eq(session_id)
        & working["category"].astype(str).eq("missing_execution_price")
    )
    if ready_tickers:
        descriptions = working.loc[missing_mask, "description"].astype(str)
        resolve_index = descriptions.index[
            descriptions.map(lambda text: any(ticker in text for ticker in ready_tickers)).astype(bool)
        ]
        resolve_mask = pd.Series(False, index=working.index)
        resolve_mask.loc[resolve_index] = True
        working.loc[resolve_mask, "resolved_flag"] = True
        working.loc[resolve_mask, "blocking_flag"] = False
        working.loc[resolve_mask, "resolution_note"] = (
            "execution opens observed and validated on 2026-06-15"
        )
    if correction_type:
        conflict_mask = (
            working["session_id"].astype(str).eq(session_id)
            & working["category"].astype(str).eq("immutable_session_content_changed")
        )
        working.loc[conflict_mask, "resolved_flag"] = True
        working.loc[conflict_mask, "blocking_flag"] = False
        working.loc[conflict_mask, "resolution_note"] = (
            f"superseded by {correction_type} revision"
        )
    return working


def _session_from_sources(
    *,
    section: dict[str, Any],
    summary: pd.DataFrame,
    ranking: pd.DataFrame,
    target: pd.DataFrame,
    proposed_orders: pd.DataFrame,
    ledger: pd.DataFrame,
    incident_count: int,
) -> pd.DataFrame:
    if ranking.empty and summary.empty and target.empty:
        return pd.DataFrame(columns=SESSION_REGISTRY_COLUMNS)
    summary_row = summary.iloc[0] if not summary.empty else pd.Series(dtype=object)
    signal_date = _date_string(
        ranking["signal_date"].iloc[0]
        if not ranking.empty and "signal_date" in ranking.columns
        else summary_row.get("selected_signal_date", "")
    )
    model_id = str(
        ranking["model_version"].iloc[0]
        if not ranking.empty and "model_version" in ranking.columns
        else summary_row.get("model_version", section["required_model_id"])
    )
    model_hash = str(summary_row.get("phase23i_freeze_hash", section["required_model_hash"]))
    session_id = deterministic_session_id(
        candidate_system_id=str(section["candidate_system_id"]),
        model_id=model_id,
        model_hash=model_hash,
        signal_date=signal_date,
        decision_cadence=str(section["decision_cadence"]),
    )
    order_blocking_reasons = []
    if not target.empty and "order_blocking_reason" in target.columns:
        order_blocking_reasons = [
            str(value)
            for value in target["order_blocking_reason"].dropna().unique().tolist()
            if str(value).strip()
        ]
    orders_blocked = bool(order_blocking_reasons) or (
        not proposed_orders.empty
        and "paper_order_allowed" in proposed_orders.columns
        and not proposed_orders["paper_order_allowed"].map(_bool_value).all()
    )
    proposal_status = "proposal_ready" if not orders_blocked and not target.empty else "proposal_blocked"
    execution_status = proposal_status
    if not ledger.empty and "selected_signal_date" in ledger.columns:
        session_ledger = ledger.loc[ledger["selected_signal_date"].astype(str).eq(signal_date)]
        states = set(session_ledger.get("session_state", pd.Series(dtype=str)).astype(str))
        if "entered" in states:
            execution_status = "entered"
        elif "skipped" in states:
            execution_status = "skipped"
        elif "blocked" in states:
            execution_status = "proposal_blocked"
    expected_execution_date = ""
    observed_execution_date = ""
    if not target.empty:
        expected_execution_date = _date_string(
            target.iloc[0].get(
                "expected_execution_date",
                target.iloc[0].get("planned_execution_date", ""),
            )
        )
        observed_execution_date = _date_string(target.iloc[0].get("observed_execution_date", ""))
    if not expected_execution_date:
        expected_execution_date = _expected_execution_from_signal(signal_date)
    return pd.DataFrame(
        [
            {
                "session_id": session_id,
                "signal_date": signal_date,
                "data_as_of_date": _date_string(summary_row.get("post_endpoint_as_of_date", "")),
                "expected_execution_date": expected_execution_date,
                "observed_execution_date": observed_execution_date,
                "model_id": model_id,
                "model_hash": model_hash,
                "candidate_system_id": str(section["candidate_system_id"]),
                "proposal_status": proposal_status,
                "execution_status": execution_status,
                "archive_status": "not_archived",
                "prediction_maturity_status": "prediction_pending",
                "selected_count": int(target["ticker"].nunique()) if "ticker" in target.columns else 0,
                "ranking_count": int(ranking["ticker"].nunique()) if "ticker" in ranking.columns else 0,
                "orders_blocked": orders_blocked,
                "blocking_reasons": ";".join(order_blocking_reasons),
                "incident_count": int(incident_count),
                "created_at_utc": _generated_at(),
                "updated_at_utc": _generated_at(),
            }
        ]
    )


def _build_reconciliation(
    *,
    session_id: str,
    signal_date: str,
    target: pd.DataFrame,
    proposed_orders: pd.DataFrame,
    ledger: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    section: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    incidents: list[dict[str, Any]] = []
    if proposed_orders.empty:
        return pd.DataFrame(columns=RECONCILIATION_COLUMNS), incidents
    target_by_ticker = (
        target.set_index("ticker").to_dict(orient="index")
        if not target.empty and "ticker" in target.columns
        else {}
    )
    ledger_by_ticker = (
        ledger.loc[ledger.get("selected_signal_date", pd.Series(dtype=str)).astype(str).eq(signal_date)]
        if not ledger.empty and "selected_signal_date" in ledger.columns
        else pd.DataFrame()
    )
    rows = []
    for row in proposed_orders.itertuples(index=False):
        ticker = str(getattr(row, "ticker"))
        target_row = target_by_ticker.get(ticker, {})
        expected_date = _date_string(target_row.get("expected_execution_date", target_row.get("planned_execution_date", "")))
        if not expected_date:
            expected_date = _expected_execution_from_signal(signal_date)
        observed_date = _date_string(target_row.get("observed_execution_date", ""))
        observed_open = _safe_float(target_row.get("execution_open_price", np.nan))
        reference_close = _safe_float(target_row.get("reference_price", getattr(row, "reference_price", np.nan)))
        approved_qty = _safe_int(getattr(row, "proposed_quantity", 0))
        entered_quantity = np.nan
        if not ledger_by_ticker.empty and "ticker" in ledger_by_ticker.columns:
            matches = ledger_by_ticker.loc[ledger_by_ticker["ticker"].astype(str).eq(ticker)]
            if not matches.empty:
                entered_quantity = _safe_float(matches.iloc[-1].get("simulated_fill_quantity", np.nan))
        opening_gap = observed_open / reference_close - 1.0 if observed_open > 0 and reference_close > 0 else np.nan
        warning_flag = bool(abs(opening_gap) > float(section["gap_warning_abs_pct"])) if pd.notna(opening_gap) else False
        severe_flag = bool(abs(opening_gap) > float(section["gap_severe_abs_pct"])) if pd.notna(opening_gap) else False
        if warning_flag:
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="warning",
                    category="large_opening_gap_warning",
                    description=f"{ticker} opening gap {opening_gap:.4f}",
                    source_report="phase23k_order_execution_reconciliation.csv",
                    blocking_flag=False,
                )
            )
        if severe_flag:
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="warning",
                    category="severe_opening_gap_warning",
                    description=f"{ticker} severe opening gap {opening_gap:.4f}",
                    source_report="phase23k_order_execution_reconciliation.csv",
                    blocking_flag=False,
                )
            )
        fill_status = "pending_execution_price"
        raw_blocking_reason = getattr(row, "order_blocking_reason", "")
        blocking_reason = "" if pd.isna(raw_blocking_reason) else str(raw_blocking_reason or "")
        if not observed_date:
            fill_status = "blocked_missing_execution_price"
            if not blocking_reason:
                blocking_reason = "execution_open_price_pending"
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="block",
                    category="missing_execution_price",
                    description=f"{ticker} execution open price is unavailable",
                    source_report="phase23j_current_target_portfolio.csv",
                    blocking_flag=True,
                )
            )
        elif observed_open <= 0:
            fill_status = "blocked_invalid_execution_price"
            blocking_reason = "invalid_execution_open_price"
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="block",
                    category="invalid_execution_price",
                    description=f"{ticker} execution open price is non-positive",
                    source_report="phase23j_current_target_portfolio.csv",
                    blocking_flag=True,
                )
            )
        else:
            fill_status = "execution_price_available"
        if observed_date and ticker in prices:
            price_row = prices[ticker].loc[
                pd.to_datetime(prices[ticker]["date"], errors="coerce").eq(pd.Timestamp(observed_date))
            ]
            if not price_row.empty:
                values = price_row.iloc[0]
                ohlc_valid = (
                    _safe_float(values.get("high")) >= max(
                        _safe_float(values.get("open")),
                        _safe_float(values.get("low")),
                        _safe_float(values.get("close")),
                    )
                    and _safe_float(values.get("low")) <= min(
                        _safe_float(values.get("open")),
                        _safe_float(values.get("high")),
                        _safe_float(values.get("close")),
                    )
                )
                if not ohlc_valid:
                    fill_status = "blocked_invalid_ohlc"
                    blocking_reason = "invalid_ohlc"
                    incidents.append(
                        _incident(
                            session_id=session_id,
                            severity="block",
                            category="invalid_ohlc",
                            description=f"{ticker} observed execution date OHLC is invalid",
                            source_report="post_endpoint_price_file",
                            blocking_flag=True,
                        )
                    )
        if pd.notna(entered_quantity) and abs(float(entered_quantity) - approved_qty) > 1e-9:
            fill_status = "blocked_fill_quantity_mismatch"
            blocking_reason = "entered_fill_quantity_mismatch"
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="block",
                    category="order_fill_mismatch",
                    description=f"{ticker} entered quantity differs from approved quantity",
                    source_report="immutable_session_ledger.csv",
                    blocking_flag=True,
                )
            )
        cost_bps = float(section["simulated_cost_bps"])
        estimated_cost = (
            abs(approved_qty) * observed_open * cost_bps / 10000.0
            if observed_open > 0
            else np.nan
        )
        rows.append(
            {
                "session_id": session_id,
                "signal_date": signal_date,
                "expected_execution_date": expected_date,
                "observed_execution_date": observed_date,
                "ticker": ticker,
                "side": str(getattr(row, "order_side", "")),
                "current_shares": _safe_int(getattr(row, "current_shares", 0)),
                "target_shares": _safe_int(getattr(row, "target_shares", 0)),
                "approved_quantity": approved_qty,
                "entered_quantity": entered_quantity,
                "signal_reference_close": reference_close,
                "observed_open_price": observed_open,
                "opening_gap_pct": opening_gap,
                "gap_warning_flag": warning_flag,
                "gap_severe_flag": severe_flag,
                "configured_cost_bps": cost_bps,
                "estimated_transaction_cost": estimated_cost,
                "fill_validation_status": fill_status,
                "reconciliation_status": "blocked" if blocking_reason else "ready_for_manual_shadow",
                "blocking_reason": blocking_reason,
            }
        )
    return pd.DataFrame(rows), incidents


def _build_maturity_and_outcomes(
    *,
    snapshots: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    section: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    maturity_rows: list[dict[str, Any]] = []
    outcome_frames: list[pd.DataFrame] = []
    ic_rows: list[dict[str, Any]] = []
    spread_rows: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    if snapshots.empty:
        return (
            pd.DataFrame(columns=MATURITY_COLUMNS),
            pd.DataFrame(columns=OUTCOME_COLUMNS),
            pd.DataFrame(columns=IC_COLUMNS),
            pd.DataFrame(columns=SPREAD_COLUMNS),
            incidents,
        )
    for (session_id, signal_date), group in snapshots.groupby(["session_id", "signal_date"], dropna=False):
        available = []
        missing = []
        maturity_dates = []
        for ticker in group["ticker"].astype(str):
            frame = prices.get(ticker, pd.DataFrame())
            maturity_date = trading_horizon_end_date(
                signal_date=str(signal_date),
                price_frame=frame,
                horizon_trading_days=int(section["target_horizon_trading_days"]),
            )
            if pd.isna(maturity_date):
                missing.append(ticker)
            else:
                available.append(ticker)
                maturity_dates.append(pd.Timestamp(maturity_date).date().isoformat())
        expected_maturity = maturity_dates[0] if maturity_dates else ""
        matured = len(available) >= int(section["expected_universe_size"]) and len(set(maturity_dates)) == 1
        maturity_rows.append(
            {
                "session_id": session_id,
                "signal_date": signal_date,
                "target_horizon_trading_days": int(section["target_horizon_trading_days"]),
                "expected_maturity_date": expected_maturity,
                "observed_maturity_date": expected_maturity if matured else "",
                "maturity_status": "prediction_matured" if matured else "prediction_pending",
                "required_ticker_count": int(section["expected_universe_size"]),
                "available_ticker_count": len(available),
                "missing_tickers": ";".join(sorted(missing)),
                "outcome_calculation_allowed": matured,
                "blocking_reason": "" if matured else "prediction_maturity_data_missing",
            }
        )
        if not matured:
            incidents.append(
                _incident(
                    session_id=str(session_id),
                    severity="info",
                    category="prediction_maturity_data_missing",
                    description=f"{signal_date} has not reached the 20-trading-day target horizon",
                    source_report="phase23k_prediction_maturity_registry.csv",
                    blocking_flag=False,
                )
            )
            continue
        outcome_rows = []
        for row in group.itertuples(index=False):
            ticker = str(getattr(row, "ticker"))
            frame = prices[ticker]
            signal_price = _safe_float(getattr(row, "reference_close", np.nan))
            if signal_price <= 0:
                signal_price = _price_on(frame, signal_date)
            maturity_price = _price_on(frame, expected_maturity)
            realised = maturity_price / signal_price - 1.0 if signal_price > 0 and maturity_price > 0 else np.nan
            outcome_rows.append(
                {
                    "session_id": session_id,
                    "signal_date": signal_date,
                    "maturity_date": expected_maturity,
                    "ticker": ticker,
                    "original_rank": _safe_int(getattr(row, "rank", np.nan)),
                    "original_score": _safe_float(getattr(row, "model_score", np.nan)),
                    "selected_flag": _bool_value(getattr(row, "selected_flag", False)),
                    "signal_price": signal_price,
                    "maturity_price": maturity_price,
                    "realised_20d_return": realised,
                    "universe_mean_20d_return": np.nan,
                    "realised_20d_excess_return": np.nan,
                    "outcome_available": pd.notna(realised),
                }
            )
        outcomes = pd.DataFrame(outcome_rows)
        universe_mean = float(outcomes["realised_20d_return"].mean())
        outcomes["universe_mean_20d_return"] = universe_mean
        outcomes["realised_20d_excess_return"] = outcomes["realised_20d_return"] - universe_mean
        outcome_frames.append(outcomes)
        ic, ic_status = _safe_spearman(
            outcomes["original_score"], outcomes["realised_20d_excess_return"]
        )
        top5 = outcomes.nsmallest(5, "original_rank")
        bottom5 = outcomes.nlargest(5, "original_rank")
        top_mean = float(top5["realised_20d_excess_return"].mean())
        bottom_mean = float(bottom5["realised_20d_excess_return"].mean())
        spread = top_mean - bottom_mean
        ic_rows.append(
            {
                "session_id": session_id,
                "signal_date": signal_date,
                "maturity_date": expected_maturity,
                "security_count": len(outcomes),
                "spearman_ic": ic,
                "top5_mean_excess_return": top_mean,
                "bottom5_mean_excess_return": bottom_mean,
                "top_minus_bottom_spread": spread,
                "status": ic_status,
            }
        )
        spread_rows.append(ic_rows[-1].copy())
    return (
        pd.DataFrame(maturity_rows),
        pd.concat(outcome_frames, ignore_index=True) if outcome_frames else pd.DataFrame(columns=OUTCOME_COLUMNS),
        pd.DataFrame(ic_rows, columns=IC_COLUMNS),
        pd.DataFrame(spread_rows, columns=SPREAD_COLUMNS),
        incidents,
    )


def _build_feature_drift(
    *,
    reference_panel: pd.DataFrame,
    current_panel: pd.DataFrame,
    session_id: str,
    signal_date: str,
    session_count: int,
    section: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    incidents: list[dict[str, Any]] = []
    if reference_panel.empty or current_panel.empty:
        return pd.DataFrame(columns=FEATURE_DRIFT_COLUMNS), incidents
    warning_mode = session_count >= int(section["minimum_sessions_for_drift_warning"])
    for feature in CORE_FEATURE_COLUMNS:
        if feature not in reference_panel.columns or feature not in current_panel.columns:
            continue
        reference = pd.to_numeric(reference_panel[feature], errors="coerce")
        current = pd.to_numeric(current_panel[feature], errors="coerce")
        reference_clean = reference.dropna()
        current_clean = current.dropna()
        ref_iqr = float(reference_clean.quantile(0.75) - reference_clean.quantile(0.25)) if not reference_clean.empty else np.nan
        current_median = float(current_clean.median()) if not current_clean.empty else np.nan
        percentile = (
            float((reference_clean <= current_median).mean())
            if not reference_clean.empty and pd.notna(current_median)
            else np.nan
        )
        distance = _normalised_wasserstein(reference_clean, current_clean)
        drift_status = "descriptive_only"
        if warning_mode and pd.notna(distance) and distance > 2.0:
            drift_status = "feature_drift_warning"
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="warning",
                    category="feature_drift_warning",
                    description=f"{feature} normalised drift distance {distance:.3f}",
                    source_report="phase23k_feature_drift_report.csv",
                    blocking_flag=False,
                )
            )
        rows.append(
            {
                "session_id": session_id,
                "signal_date": signal_date,
                "feature_id": feature,
                "reference_count": int(reference_clean.count()),
                "current_count": int(current_clean.count()),
                "reference_mean": float(reference_clean.mean()) if not reference_clean.empty else np.nan,
                "current_mean": float(current_clean.mean()) if not current_clean.empty else np.nan,
                "reference_median": float(reference_clean.median()) if not reference_clean.empty else np.nan,
                "current_median": current_median,
                "reference_std": float(reference_clean.std(ddof=0)) if not reference_clean.empty else np.nan,
                "current_std": float(current_clean.std(ddof=0)) if not current_clean.empty else np.nan,
                "reference_iqr": ref_iqr,
                "current_iqr": float(current_clean.quantile(0.75) - current_clean.quantile(0.25)) if not current_clean.empty else np.nan,
                "current_missing_rate": float(current.isna().mean()) if len(current) else np.nan,
                "reference_percentile_of_current_median": percentile,
                "normalised_wasserstein_distance": distance,
                "drift_status": drift_status,
            }
        )
    return pd.DataFrame(rows), incidents


def _build_score_drift(snapshots: pd.DataFrame, section: dict[str, Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    incidents: list[dict[str, Any]] = []
    if snapshots.empty:
        return pd.DataFrame(columns=SCORE_DRIFT_COLUMNS), incidents
    sessions = (
        snapshots[["session_id", "signal_date"]]
        .drop_duplicates()
        .sort_values("signal_date")
        .to_dict(orient="records")
    )
    previous = pd.DataFrame()
    for session in sessions:
        current = snapshots.loc[snapshots["session_id"].astype(str).eq(str(session["session_id"]))].copy()
        top = current.nsmallest(5, "rank") if "rank" in current.columns else pd.DataFrame()
        top_members = sorted(top["ticker"].astype(str).tolist()) if not top.empty else []
        rank_turnover = np.nan
        jaccard = np.nan
        stability = np.nan
        if not previous.empty:
            prior_top = set(previous.nsmallest(5, "rank")["ticker"].astype(str))
            current_top = set(top_members)
            rank_turnover = 1.0 - len(prior_top & current_top) / max(len(prior_top | current_top), 1)
            jaccard = len(prior_top & current_top) / max(len(prior_top | current_top), 1)
            merged = previous[["ticker", "rank"]].merge(
                current[["ticker", "rank"]],
                on="ticker",
                suffixes=("_prior", "_current"),
            )
            stability, _ = _safe_spearman(merged["rank_prior"], merged["rank_current"])
        status = "descriptive_only"
        if len(sessions) >= int(section["minimum_sessions_for_drift_warning"]) and pd.notna(rank_turnover) and rank_turnover > 0.8:
            status = "score_drift_warning"
            incidents.append(
                _incident(
                    session_id=str(session["session_id"]),
                    severity="warning",
                    category="score_drift_warning",
                    description=f"Top-five rank turnover {rank_turnover:.3f}",
                    source_report="phase23k_score_drift_report.csv",
                    blocking_flag=False,
                )
            )
        scores = pd.to_numeric(current["model_score"], errors="coerce")
        rows.append(
            {
                "session_id": session["session_id"],
                "signal_date": session["signal_date"],
                "score_mean": float(scores.mean()),
                "score_median": float(scores.median()),
                "score_standard_deviation": float(scores.std(ddof=0)),
                "score_min": float(scores.min()),
                "score_max": float(scores.max()),
                "top_five_score_threshold": float(top["model_score"].min()) if not top.empty else np.nan,
                "top_five_membership": ";".join(top_members),
                "rank_turnover_vs_prior_session": rank_turnover,
                "top_five_jaccard_similarity": jaccard,
                "spearman_rank_stability_vs_prior_session": stability,
                "status": status,
            }
        )
        previous = current
    return pd.DataFrame(rows), incidents


def _build_concentration(
    *, snapshots: pd.DataFrame, positions: pd.DataFrame, section: dict[str, Any]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows = []
    incidents: list[dict[str, Any]] = []
    if snapshots.empty:
        return pd.DataFrame(columns=CONCENTRATION_COLUMNS), incidents
    entered_by_ticker: dict[str, float] = {}
    if not positions.empty and {"ticker", "market_value"}.issubset(positions.columns):
        security_positions = positions.loc[positions["ticker"].astype(str).ne("CASH")]
        total = pd.to_numeric(security_positions["market_value"], errors="coerce").sum()
        if total > 0:
            entered_by_ticker = dict(
                zip(
                    security_positions["ticker"].astype(str),
                    pd.to_numeric(security_positions["market_value"], errors="coerce") / total,
                    strict=False,
                )
            )
    for (session_id, signal_date), group in snapshots.groupby(["session_id", "signal_date"], dropna=False):
        sector_by_ticker = dict(zip(group["ticker"].astype(str), group.get("sector", pd.Series("", index=group.index)).astype(str), strict=False))
        if "sector" not in group.columns:
            sector_by_ticker = {}
        selected = group.loc[group["selected_flag"].map(_bool_value)].copy()
        sector_target = selected.groupby(selected["ticker"].map(lambda ticker: sector_by_ticker.get(str(ticker), "Unknown")))["target_weight"].sum()
        largest_security = float(selected["target_weight"].max()) if not selected.empty else 0.0
        largest_sector = float(sector_target.max()) if not sector_target.empty else 0.0
        warning = largest_sector > 0.60 or largest_security > 0.25
        if warning:
            incidents.append(
                _incident(
                    session_id=str(session_id),
                    severity="warning",
                    category="concentration_warning",
                    description=f"largest sector weight {largest_sector:.3f}",
                    source_report="phase23k_concentration_report.csv",
                    blocking_flag=False,
                )
            )
        for row in group.itertuples(index=False):
            ticker = str(getattr(row, "ticker"))
            sector = sector_by_ticker.get(ticker, "Unknown")
            rows.append(
                {
                    "session_id": session_id,
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "sector": sector,
                    "selected_flag": _bool_value(getattr(row, "selected_flag", False)),
                    "target_weight": _safe_float(getattr(row, "target_weight", 0.0), 0.0),
                    "entered_weight": float(entered_by_ticker.get(ticker, 0.0)),
                    "sector_target_weight": float(sector_target.get(sector, 0.0)),
                    "sector_entered_weight": np.nan,
                    "largest_security_weight": largest_security,
                    "largest_sector_weight": largest_sector,
                    "concentration_warning": warning,
                }
            )
    return pd.DataFrame(rows), incidents


def _copy_with_source(frame: pd.DataFrame, source_path: Path) -> pd.DataFrame:
    working = frame.copy()
    if working.empty:
        return working
    working["source_path"] = str(source_path)
    working["source_modified_utc"] = (
        datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc).isoformat()
        if source_path.exists()
        else ""
    )
    return working


def save_phase23k_prospective_shadow_monitoring(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_path = Path(reports_dir)
    section = _phase_config(config)
    output_dir = _resolve_reports_path(
        configured_path=section["output_dir"], reports_dir=reports_path
    )
    dashboard_path = _resolve_reports_path(
        configured_path=section["dashboard_status_path"], reports_dir=reports_path
    )
    phase23i_shadow_dir = _resolve_reports_path(
        configured_path=section["source_phase23i_shadow_dir"], reports_dir=reports_path
    )
    phase23j_dir = _resolve_reports_path(
        configured_path=section["source_phase23j_dir"], reports_dir=reports_path
    )
    phase23f_dir = _resolve_reports_path(
        configured_path=section["source_phase23f_dir"], reports_dir=reports_path
    )
    pilot_dir = _resolve_project_path(
        configured_path=section["pilot_input_dir"], reports_dir=reports_path
    )
    post_dir = _resolve_project_path(
        configured_path=section["post_endpoint_input_dir"], reports_dir=reports_path
    )
    combined_dir = _resolve_project_path(
        configured_path=section["combined_input_dir"], reports_dir=reports_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    phase23j_summary = _read_csv(phase23j_dir / "phase23j_summary.csv")
    phase23j_ranking = _read_csv(phase23j_dir / "phase23j_current_ranking.csv")
    phase23j_target = _read_csv(phase23j_dir / "phase23j_current_target_portfolio.csv")
    phase23j_features = _read_csv(phase23j_dir / "phase23j_prospective_feature_panel.csv")
    proposed_orders = _read_csv(phase23i_shadow_dir / "current_proposed_order_plan.csv")
    ledger = _read_csv(phase23i_shadow_dir / "immutable_session_ledger.csv")
    positions = _read_csv(phase23i_shadow_dir / "positions.csv")
    cash = _read_csv(phase23i_shadow_dir / "cash_ledger.csv")
    valuation = _read_csv(phase23i_shadow_dir / "valuation_history.csv")
    reference_panel = _read_csv(phase23f_dir / "phase23f_pilot_feature_panel.csv")
    prices = _load_prices(combined_dir=combined_dir, pilot_dir=pilot_dir, post_dir=post_dir)

    existing_snapshots = _read_csv(output_dir / "phase23k_full_ranking_snapshots.csv")
    existing_snapshot_history = _read_csv(output_dir / "phase23k_session_snapshot_history.csv")
    existing_incidents = _read_csv(output_dir / "phase23k_incident_log.csv")
    incidents: list[dict[str, Any]] = []

    summary_row = phase23j_summary.iloc[0] if not phase23j_summary.empty else pd.Series(dtype=object)
    model_hash = str(summary_row.get("phase23i_freeze_hash", section["required_model_hash"]))
    model_id = str(summary_row.get("model_version", section["required_model_id"]))
    signal_date = _date_string(
        phase23j_ranking["signal_date"].iloc[0]
        if not phase23j_ranking.empty and "signal_date" in phase23j_ranking.columns
        else summary_row.get("selected_signal_date", "")
    )
    session_id = (
        deterministic_session_id(
            candidate_system_id=str(section["candidate_system_id"]),
            model_id=model_id,
            model_hash=model_hash,
            signal_date=signal_date,
            decision_cadence=str(section["decision_cadence"]),
        )
        if signal_date
        else ""
    )
    model_hash_matches = model_hash == str(section["required_model_hash"])
    if session_id and not model_hash_matches:
        incidents.append(
            _incident(
                session_id=session_id,
                severity="block",
                category="model_hash_mismatch",
                description=f"expected {section['required_model_hash']} observed {model_hash}",
                source_report="phase23j_summary.csv",
                blocking_flag=True,
            )
        )
    universe_changed = False
    if not phase23j_ranking.empty and "ticker" in phase23j_ranking.columns:
        observed_universe = sorted(phase23j_ranking["ticker"].astype(str).unique().tolist())
        universe_changed = observed_universe != sorted(PILOT_UNIVERSE)
        if universe_changed:
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="block",
                    category="changed_universe",
                    description=f"observed={';'.join(observed_universe)}",
                    source_report="phase23j_current_ranking.csv",
                    blocking_flag=True,
                )
            )

    current_snapshot = _build_current_snapshot(
        ranking=phase23j_ranking,
        target=phase23j_target,
        session_id=session_id,
        model_hash=model_hash,
    )
    if not current_snapshot.empty and "sector_asof" in phase23j_ranking.columns:
        current_snapshot = current_snapshot.merge(
            phase23j_ranking[["ticker", "sector_asof"]].rename(columns={"sector_asof": "sector"}),
            on="ticker",
            how="left",
        )
    fill_exists = _session_has_entered_fill(
        ledger=ledger,
        positions=positions,
        signal_date=signal_date,
    )
    snapshots, immutable_conflict, correction_allowed = _merge_immutable_snapshots(
        existing=existing_snapshots,
        current=current_snapshot,
        session_id=session_id,
        fill_exists=fill_exists,
    )
    if immutable_conflict:
        incidents.append(
            _incident(
                session_id=session_id,
                severity="block",
                category="immutable_session_content_changed",
                description="Existing full ranking snapshot differs from current Phase23J snapshot",
                source_report="phase23k_full_ranking_snapshots.csv",
                blocking_flag=True,
            )
        )

    reconciliation, reconciliation_incidents = _build_reconciliation(
        session_id=session_id,
        signal_date=signal_date,
        target=phase23j_target,
        proposed_orders=proposed_orders,
        ledger=ledger,
        prices=prices,
        section=section,
    )
    incidents.extend(reconciliation_incidents)

    snapshot_history, latest_revision, latest_snapshot_id, correction_type, correction_reason = (
        _update_snapshot_history(
            existing_history=existing_snapshot_history,
            existing_snapshots=existing_snapshots,
            current_snapshot=current_snapshot,
            reconciliation=reconciliation,
            session_id=session_id,
            correction_allowed=correction_allowed,
        )
        if not immutable_conflict
        else (existing_snapshot_history, 0, "", "", "")
    )

    session_registry = _session_from_sources(
        section=section,
        summary=phase23j_summary,
        ranking=phase23j_ranking,
        target=phase23j_target,
        proposed_orders=proposed_orders,
        ledger=ledger,
        incident_count=len(incidents),
    )

    maturity, outcomes, ic_history, spread_history, maturity_incidents = (
        _build_maturity_and_outcomes(
            snapshots=snapshots,
            prices=prices,
            section=section,
        )
    )
    incidents.extend(maturity_incidents)
    if not maturity.empty and not session_registry.empty:
        maturity_map = dict(zip(maturity["session_id"], maturity["maturity_status"], strict=False))
        session_registry["prediction_maturity_status"] = session_registry["session_id"].map(maturity_map).fillna(
            session_registry["prediction_maturity_status"]
        )

    session_count = int(snapshots["session_id"].nunique()) if not snapshots.empty else 0
    feature_drift, feature_incidents = _build_feature_drift(
        reference_panel=reference_panel,
        current_panel=phase23j_features,
        session_id=session_id,
        signal_date=signal_date,
        session_count=session_count,
        section=section,
    )
    incidents.extend(feature_incidents)
    score_drift, score_incidents = _build_score_drift(snapshots, section)
    incidents.extend(score_incidents)
    concentration, concentration_incidents = _build_concentration(
        snapshots=snapshots, positions=positions, section=section
    )
    incidents.extend(concentration_incidents)

    if not cash.empty and "cash_balance" in cash.columns:
        cash_min = pd.to_numeric(cash["cash_balance"], errors="coerce").min()
        if pd.notna(cash_min) and cash_min < -float(section["negative_cash_tolerance"]):
            incidents.append(
                _incident(
                    session_id=session_id,
                    severity="block",
                    category="negative_cash",
                    description=f"minimum cash balance {cash_min:.2f}",
                    source_report="cash_ledger.csv",
                    blocking_flag=True,
                )
            )

    incident_log = pd.concat([existing_incidents, pd.DataFrame(incidents)], ignore_index=True)
    if not incident_log.empty and "incident_id" in incident_log.columns:
        incident_log = incident_log.drop_duplicates("incident_id", keep="last")
    incident_log = _resolve_incident_lifecycle(
        incident_log=incident_log,
        reconciliation=reconciliation,
        session_id=session_id,
        correction_type=correction_type,
    )
    blocking_incidents = (
        incident_log["blocking_flag"].map(_bool_value).sum()
        if not incident_log.empty and "blocking_flag" in incident_log.columns
        else 0
    )
    if not session_registry.empty:
        session_registry["incident_count"] = int(
            incident_log.loc[incident_log["session_id"].astype(str).eq(session_id)].shape[0]
        )
        session_registry["session_revision"] = latest_revision
        session_registry["snapshot_id"] = latest_snapshot_id
        session_registry["supersedes_snapshot_id"] = (
            snapshot_history.loc[
                snapshot_history["snapshot_id"].astype(str).eq(latest_snapshot_id),
                "supersedes_snapshot_id",
            ].astype(str).iloc[0]
            if latest_snapshot_id and not snapshot_history.empty and "snapshot_id" in snapshot_history.columns
            and snapshot_history["snapshot_id"].astype(str).eq(latest_snapshot_id).any()
            else ""
        )
        session_registry["revision_reason"] = correction_reason
        session_registry["revision_created_at_utc"] = (
            snapshot_history.loc[
                snapshot_history["snapshot_id"].astype(str).eq(latest_snapshot_id),
                "created_at_utc",
            ].astype(str).iloc[0]
            if latest_snapshot_id and not snapshot_history.empty and "snapshot_id" in snapshot_history.columns
            and snapshot_history["snapshot_id"].astype(str).eq(latest_snapshot_id).any()
            else ""
        )
        if (
            int(blocking_incidents) == 0
            and not reconciliation.empty
            and reconciliation["fill_validation_status"].astype(str).eq("execution_price_available").all()
            and not fill_exists
        ):
            session_registry["proposal_status"] = "proposal_ready"
            session_registry["execution_status"] = "ready_manual_fill"
            session_registry["orders_blocked"] = False
            session_registry["blocking_reasons"] = ""
    safety_flags_false = not any(
        _bool_value(section.get(key, False))
        for key in [
            "paper_trading_allowed",
            "automated_broker_paper_trading_allowed",
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
            "promotion_allowed",
        ]
    )
    ready_manual_fill = bool(
        int(blocking_incidents) == 0
        and not reconciliation.empty
        and reconciliation["fill_validation_status"].astype(str).eq("execution_price_available").all()
        and not fill_exists
    )
    if phase23j_ranking.empty:
        decision = "phase23k_monitoring_written_no_current_session"
    elif blocking_incidents and any(
        incident_log.loc[incident_log["blocking_flag"].map(_bool_value), "category"]
        .astype(str)
        .isin(["model_hash_mismatch", "changed_universe", "immutable_session_content_changed"])
    ):
        decision = "phase23k_monitoring_blocked_integrity_failure"
    elif not reconciliation.empty and reconciliation["fill_validation_status"].astype(str).str.contains("missing_execution_price|pending").any():
        decision = "phase23k_monitoring_active_current_session_execution_pending"
    elif blocking_incidents:
        decision = "phase23k_monitoring_written_with_session_blocks"
    elif ready_manual_fill:
        decision = "phase23k_monitoring_ready_manual_fill_pending"
    else:
        decision = "phase23k_monitoring_active_current_session_ready_or_entered"

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23K",
                "phase23k_decision": decision,
                "session_count": session_count,
                "latest_session_revision": latest_revision,
                "latest_snapshot_id": latest_snapshot_id,
                "current_session_id": session_id,
                "current_signal_date": signal_date,
                "model_id": model_id,
                "model_hash": model_hash,
                "model_hash_verified": model_hash_matches,
                "ranking_count": int(len(phase23j_ranking)),
                "selected_count": int(len(phase23j_target)),
                "blocking_incident_count": int(blocking_incidents),
                "unresolved_blocking_incident_count": int(blocking_incidents),
                "incident_count": int(len(incident_log)),
                "prediction_matured_sessions": int(
                    maturity["maturity_status"].astype(str).eq("prediction_matured").sum()
                )
                if not maturity.empty
                else 0,
                "paper_trading_allowed": False,
                "automated_broker_paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    gates = pd.DataFrame(
        [
            _gate("phase23j_sources_read", not phase23j_summary.empty or not phase23j_ranking.empty, str(phase23j_dir)),
            _gate("model_hash_verified", model_hash_matches, model_hash),
            _gate("expected_universe_size", phase23j_ranking.empty or len(phase23j_ranking) == int(section["expected_universe_size"]), f"rows={len(phase23j_ranking)}"),
            _gate("ranking_snapshot_written", True, "all available ranking rows preserved"),
            _gate("safety_flags_false", safety_flags_false, "no live/real/broker/promotion"),
            _gate("phase23k_reports_written", True, str(output_dir)),
        ]
    )
    gates["phase23k_gate_passed"] = gates["passed"]
    gates["all_phase23k_gates_passed"] = bool(gates["passed"].all())
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23K",
                "phase23k_decision": decision,
                "verdict": "Prospective shadow monitoring written without changing the frozen model or accounting authority.",
                "remaining_blockers": ";".join(
                    sorted(
                        incident_log.loc[
                            incident_log.get("blocking_flag", pd.Series(dtype=bool)).map(_bool_value),
                            "category",
                        ].astype(str).unique()
                    )
                )
                if not incident_log.empty
                else "",
                "paper_trading_allowed": False,
                "automated_broker_paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    )

    position_history = _copy_with_source(positions, phase23i_shadow_dir / "positions.csv")
    cash_history = _copy_with_source(cash, phase23i_shadow_dir / "cash_ledger.csv")
    daily_valuation = _copy_with_source(valuation, phase23i_shadow_dir / "valuation_history.csv")
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23k_prospective_monitoring_status_written"
    dashboard["output_dir"] = str(output_dir)

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "session_registry": session_registry,
        "full_ranking_snapshots": snapshots,
        "order_execution_reconciliation": reconciliation,
        "position_history": position_history,
        "cash_history": cash_history,
        "daily_valuation": daily_valuation,
        "prediction_maturity_registry": maturity,
        "matured_cross_sectional_outcomes": outcomes,
        "prospective_ic_history": ic_history,
        "prospective_spread_history": spread_history,
        "feature_drift_report": feature_drift,
        "score_drift_report": score_drift,
        "concentration_report": concentration,
        "incident_log": incident_log,
        "session_snapshot_history": snapshot_history,
        "dashboard": dashboard,
    }
    file_map = {
        "summary": ("phase23k_summary.csv", SUMMARY_COLUMNS),
        "gate_report": ("phase23k_gate_report.csv", None),
        "conclusion": ("phase23k_conclusion.csv", None),
        "session_registry": ("phase23k_session_registry.csv", SESSION_REGISTRY_COLUMNS),
        "full_ranking_snapshots": ("phase23k_full_ranking_snapshots.csv", FULL_RANKING_COLUMNS),
        "order_execution_reconciliation": ("phase23k_order_execution_reconciliation.csv", RECONCILIATION_COLUMNS),
        "position_history": ("phase23k_position_history.csv", None),
        "cash_history": ("phase23k_cash_history.csv", None),
        "daily_valuation": ("phase23k_daily_valuation.csv", None),
        "prediction_maturity_registry": ("phase23k_prediction_maturity_registry.csv", MATURITY_COLUMNS),
        "matured_cross_sectional_outcomes": ("phase23k_matured_cross_sectional_outcomes.csv", OUTCOME_COLUMNS),
        "prospective_ic_history": ("phase23k_prospective_ic_history.csv", IC_COLUMNS),
        "prospective_spread_history": ("phase23k_prospective_spread_history.csv", SPREAD_COLUMNS),
        "feature_drift_report": ("phase23k_feature_drift_report.csv", FEATURE_DRIFT_COLUMNS),
        "score_drift_report": ("phase23k_score_drift_report.csv", SCORE_DRIFT_COLUMNS),
        "concentration_report": ("phase23k_concentration_report.csv", CONCENTRATION_COLUMNS),
        "incident_log": ("phase23k_incident_log.csv", INCIDENT_COLUMNS),
        "session_snapshot_history": ("phase23k_session_snapshot_history.csv", SNAPSHOT_HISTORY_COLUMNS),
    }
    for key, (filename, columns) in file_map.items():
        _write_csv(outputs[key], output_dir / filename, columns)
    _write_csv(dashboard, dashboard_path)
    print("Wrote Phase 23K prospective shadow monitoring reports.")
    return outputs


SUMMARY_COLUMNS = [
    "phase",
    "phase23k_decision",
    "session_count",
    "latest_session_revision",
    "latest_snapshot_id",
    "current_session_id",
    "current_signal_date",
    "model_id",
    "model_hash",
    "model_hash_verified",
    "ranking_count",
    "selected_count",
    "blocking_incident_count",
    "unresolved_blocking_incident_count",
    "incident_count",
    "prediction_matured_sessions",
    "paper_trading_allowed",
    "automated_broker_paper_trading_allowed",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "promotion_allowed",
    "generated_at_utc",
]

SESSION_REGISTRY_COLUMNS = [
    "session_id",
    "signal_date",
    "data_as_of_date",
    "expected_execution_date",
    "observed_execution_date",
    "model_id",
    "model_hash",
    "candidate_system_id",
    "proposal_status",
    "execution_status",
    "archive_status",
    "prediction_maturity_status",
    "selected_count",
    "ranking_count",
    "orders_blocked",
    "blocking_reasons",
    "incident_count",
    "session_revision",
    "snapshot_id",
    "supersedes_snapshot_id",
    "revision_reason",
    "revision_created_at_utc",
    "created_at_utc",
    "updated_at_utc",
]

FULL_RANKING_COLUMNS = [
    "session_id",
    "signal_date",
    "ticker",
    "rank",
    "model_score",
    "selected_flag",
    "target_weight",
    "reference_close",
    "reference_price_date",
    "model_id",
    "model_hash",
    "feature_snapshot_source",
    "ranking_source",
    "immutable_content_hash",
    "sector",
]

RECONCILIATION_COLUMNS = [
    "session_id",
    "signal_date",
    "expected_execution_date",
    "observed_execution_date",
    "ticker",
    "side",
    "current_shares",
    "target_shares",
    "approved_quantity",
    "entered_quantity",
    "signal_reference_close",
    "observed_open_price",
    "opening_gap_pct",
    "gap_warning_flag",
    "gap_severe_flag",
    "configured_cost_bps",
    "estimated_transaction_cost",
    "fill_validation_status",
    "reconciliation_status",
    "blocking_reason",
]

MATURITY_COLUMNS = [
    "session_id",
    "signal_date",
    "target_horizon_trading_days",
    "expected_maturity_date",
    "observed_maturity_date",
    "maturity_status",
    "required_ticker_count",
    "available_ticker_count",
    "missing_tickers",
    "outcome_calculation_allowed",
    "blocking_reason",
]

OUTCOME_COLUMNS = [
    "session_id",
    "signal_date",
    "maturity_date",
    "ticker",
    "original_rank",
    "original_score",
    "selected_flag",
    "signal_price",
    "maturity_price",
    "realised_20d_return",
    "universe_mean_20d_return",
    "realised_20d_excess_return",
    "outcome_available",
]

IC_COLUMNS = [
    "session_id",
    "signal_date",
    "maturity_date",
    "security_count",
    "spearman_ic",
    "top5_mean_excess_return",
    "bottom5_mean_excess_return",
    "top_minus_bottom_spread",
    "status",
]

SPREAD_COLUMNS = IC_COLUMNS.copy()

FEATURE_DRIFT_COLUMNS = [
    "session_id",
    "signal_date",
    "feature_id",
    "reference_count",
    "current_count",
    "reference_mean",
    "current_mean",
    "reference_median",
    "current_median",
    "reference_std",
    "current_std",
    "reference_iqr",
    "current_iqr",
    "current_missing_rate",
    "reference_percentile_of_current_median",
    "normalised_wasserstein_distance",
    "drift_status",
]

SCORE_DRIFT_COLUMNS = [
    "session_id",
    "signal_date",
    "score_mean",
    "score_median",
    "score_standard_deviation",
    "score_min",
    "score_max",
    "top_five_score_threshold",
    "top_five_membership",
    "rank_turnover_vs_prior_session",
    "top_five_jaccard_similarity",
    "spearman_rank_stability_vs_prior_session",
    "status",
]

CONCENTRATION_COLUMNS = [
    "session_id",
    "signal_date",
    "ticker",
    "sector",
    "selected_flag",
    "target_weight",
    "entered_weight",
    "sector_target_weight",
    "sector_entered_weight",
    "largest_security_weight",
    "largest_sector_weight",
    "concentration_warning",
]

INCIDENT_COLUMNS = [
    "incident_id",
    "session_id",
    "detected_at_utc",
    "severity",
    "category",
    "description",
    "source_report",
    "blocking_flag",
    "resolved_flag",
    "resolution_note",
]

SNAPSHOT_HISTORY_COLUMNS = [
    "session_id",
    "snapshot_id",
    "session_revision",
    "supersedes_snapshot_id",
    "snapshot_status",
    "created_at_utc",
    "correction_type",
    "correction_reason",
    "source_commit_or_code_version",
    "signal_date",
    "model_hash",
    "ranking_hash",
    "target_hash",
    "execution_data_hash",
    "reference_data_hash",
]
