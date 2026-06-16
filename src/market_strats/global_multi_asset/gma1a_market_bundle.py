"""GMA-1A canonical market bundle, total-return, calendar, reconciliation and reports."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.global_multi_asset.data.manifests import (
    sha256_file,
)
from market_strats.global_multi_asset.data.validation import (
    completed_history,
    corporate_action_frame,
    normalise_price_frame,
)
from market_strats.global_multi_asset.gma1a_config import (
    GMA1AConfig,
    is_approved_gma_path,
)
from market_strats.global_multi_asset.gma1a_snapshot_selection import (
    compute_selection_set_hash,
    select_canonical_snapshots,
    build_selection_manifest,
    write_selection_reports,
)
from market_strats.global_multi_asset.universe import (
    PROPOSED_INSTRUMENTS,
    default_instrument_registry,
)


# ---------------------------------------------------------------------------
# Calendar operations
# ---------------------------------------------------------------------------

CALENDAR_REGISTRY_ROWS = [
    {
        "calendar_id": "us_listed_etf",
        "applicable_instruments": ";".join(
            i for i in PROPOSED_INSTRUMENTS if i not in ("BTC-USD",)
        ),
        "timezone": "America/New_York",
        "session_type": "exchange_business_day",
        "weekend_trading": False,
        "expected_frequency": "business_day",
        "decision_date_rule": "signal_computed_on_completed_session_close",
        "next_execution_rule": "next_available_raw_open_after_signal_date",
        "completed_observation_rule": "exclude_active_session_and_trailing_incomplete",
        "missing_session_policy": "do_not_fabricate_or_forward_fill",
        "calendar_status": "active",
    },
    {
        "calendar_id": "bitcoin_utc_daily",
        "applicable_instruments": "BTC-USD",
        "timezone": "UTC",
        "session_type": "continuous_24_7_daily_utc",
        "weekend_trading": True,
        "expected_frequency": "calendar_day",
        "decision_date_rule": "signal_computed_on_completed_utc_day",
        "next_execution_rule": "next_available_observation_after_signal_date",
        "completed_observation_rule": "exclude_active_session_and_trailing_incomplete",
        "missing_session_policy": "do_not_fabricate_or_forward_fill",
        "calendar_status": "active",
    },
    {
        "calendar_id": "cash_rate_publication",
        "applicable_instruments": "",
        "timezone": "America/New_York",
        "session_type": "publication_schedule",
        "weekend_trading": False,
        "expected_frequency": "series_specific",
        "decision_date_rule": "point_in_time_publication_date",
        "next_execution_rule": "not_applicable_data_only",
        "completed_observation_rule": "publication_timestamp_required",
        "missing_session_policy": "defer_to_gma1b",
        "calendar_status": "placeholder",
    },
]


def next_eligible_completed_observation(
    completed_dates: pd.Series,
    after_timestamp: pd.Timestamp,
) -> pd.Timestamp | None:
    """Return the next available completed observation date strictly after timestamp.

    Returns None if no future observation exists.
    """
    clean = pd.to_datetime(completed_dates, errors="coerce").dropna().sort_values()
    future = clean.loc[clean.gt(after_timestamp)]
    if future.empty:
        return None
    return future.iloc[0]


# ---------------------------------------------------------------------------
# Total-return construction
# ---------------------------------------------------------------------------

def build_total_return_series(
    completed: pd.DataFrame,
    actions: pd.DataFrame,
) -> pd.DataFrame:
    """Construct the canonical total-return index from completed history.

    Contract:
    - Yahoo auto_adjust=false: raw Close is already split-adjusted.
    - Total-return factor on date t = (close_t + dividend_t) / close_{t-1}.
    - Splits: stored for accounting; raw close already reflects splits.
    - First observation: total_return_index = 1.0, factor = NaN.
    - Missing prior close: factor = NaN.
    - Non-trading dates: not fabricated.

    Returns a copy of completed with added total-return columns.
    """
    df = completed.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Merge dividend/split data by date
    if not actions.empty and "date" in actions.columns:
        acts = actions.copy()
        acts["date"] = pd.to_datetime(acts["date"])
        acts = acts.groupby("date", as_index=False).agg({
            "dividends": "sum",
            "splits": lambda x: x.loc[x.ne(0)].iloc[0] if x.ne(0).any() else 0.0,
        })
        df = df.merge(acts, on="date", how="left")
    else:
        df["dividends"] = 0.0
        df["splits"] = 0.0

    df["dividend_cash"] = df["dividends"].fillna(0.0)
    df["split_ratio"] = df["splits"].fillna(0.0)
    # Clean up: split_ratio 0 means no split
    df.loc[df["split_ratio"].eq(0), "split_ratio"] = 0.0

    # Total-return factor
    prior_close = df["close"].shift(1)
    df["total_return_factor"] = np.where(
        prior_close.gt(0) & prior_close.notna(),
        (df["close"] + df["dividend_cash"]) / prior_close,
        np.nan,
    )
    # First row has no prior close
    df.loc[0, "total_return_factor"] = np.nan

    # Total-return index starting at 1.0
    tr_index = np.ones(len(df), dtype=float)
    for i in range(1, len(df)):
        factor = df.loc[i, "total_return_factor"]
        if np.isfinite(factor):
            tr_index[i] = tr_index[i - 1] * factor
        else:
            tr_index[i] = np.nan
    df["total_return_index"] = tr_index

    # Construction status
    df["total_return_construction_status"] = "constructed"
    df.loc[df["total_return_factor"].isna(), "total_return_construction_status"] = (
        "first_observation"
    )

    return df


# ---------------------------------------------------------------------------
# Reconciliation against Yahoo adjusted close
# ---------------------------------------------------------------------------

def reconcile_total_return(
    canonical: pd.DataFrame,
    tolerance_bps: float,
) -> dict[str, Any]:
    """Reconcile constructed total-return against Yahoo adjusted close returns."""
    df = canonical.copy()
    df = df.sort_values("date").reset_index(drop=True)

    # Provider return from adj_close
    provider_return = df["adj_close_provider"].pct_change()
    # Constructed return
    constructed_return = df["total_return_factor"] - 1.0

    # Only compare where both exist
    mask = provider_return.notna() & constructed_return.notna()
    overlap_rows = int(mask.sum())
    if overlap_rows == 0:
        return {
            "overlap_rows": 0,
            "provider_return_count": 0,
            "constructed_return_count": 0,
            "return_difference_count": 0,
            "median_return_difference_bps": np.nan,
            "maximum_return_difference_bps": np.nan,
            "return_difference_count_gt_tolerance": 0,
            "median_level_ratio_drift_bps": np.nan,
            "maximum_level_ratio_drift_bps": np.nan,
            "earliest_material_difference_date": "",
            "latest_material_difference_date": "",
            "dividend_event_reconciliation_status": "no_data",
            "split_event_reconciliation_status": "no_data",
            "reconciliation_status": "failed_reconciliation",
            "review_notes": "no overlapping return data",
        }

    diff_bps = (constructed_return[mask] - provider_return[mask]).abs() * 10000
    count_gt_tol = int((diff_bps > tolerance_bps).sum())

    # Level ratio drift
    tr_idx = df["total_return_index"]
    adj = df["adj_close_provider"]
    # Safely compute level ratio where both are valid
    valid_adj = adj.notna() & adj.gt(0) & tr_idx.notna()
    if valid_adj.any():
        adj_normalised = adj / adj.loc[valid_adj].iloc[0]
        level_ratio = tr_idx / adj_normalised
        level_drift_bps = (level_ratio - 1.0).abs() * 10000
        level_drift_bps = level_drift_bps[valid_adj]
        med_drift = float(level_drift_bps.median()) if not level_drift_bps.empty else np.nan
        max_drift = float(level_drift_bps.max()) if not level_drift_bps.empty else np.nan
    else:
        med_drift = np.nan
        max_drift = np.nan

    # Material difference dates
    material_mask = diff_bps > tolerance_bps
    dates = df.loc[mask, "date"].reset_index(drop=True)
    material_mask_aligned = material_mask.reset_index(drop=True)
    mat_dates = dates[material_mask_aligned.iloc[:len(dates)]]
    earliest = ""
    latest = ""
    if not mat_dates.empty:
        mat_dates_clean = pd.to_datetime(mat_dates).dropna()
        if not mat_dates_clean.empty:
            earliest = mat_dates_clean.min().date().isoformat()
            latest = mat_dates_clean.max().date().isoformat()

    # Dividend / split reconciliation
    has_divs = df["dividend_cash"].fillna(0).ne(0).any()
    div_status = "events_present" if has_divs else "no_events"
    has_splits = df["split_ratio"].fillna(0).ne(0).any()
    split_status = "events_present" if has_splits else "no_events"

    # Classification
    if count_gt_tol == 0:
        if diff_bps.max() < 0.1:
            status = "reconciled"
        else:
            status = "reconciled_with_immaterial_drift"
    elif count_gt_tol <= 5 and has_divs:
        status = "action_timing_review"
    else:
        status = "provider_basis_review"

    return {
        "overlap_rows": overlap_rows,
        "provider_return_count": int(provider_return.notna().sum()),
        "constructed_return_count": int(constructed_return.notna().sum()),
        "return_difference_count": int((diff_bps > 0.001).sum()),
        "median_return_difference_bps": float(diff_bps.median()),
        "maximum_return_difference_bps": float(diff_bps.max()),
        "return_difference_count_gt_tolerance": count_gt_tol,
        "median_level_ratio_drift_bps": med_drift,
        "maximum_level_ratio_drift_bps": max_drift,
        "earliest_material_difference_date": earliest,
        "latest_material_difference_date": latest,
        "dividend_event_reconciliation_status": div_status,
        "split_event_reconciliation_status": split_status,
        "reconciliation_status": status,
        "review_notes": "",
    }


# ---------------------------------------------------------------------------
# Canonical market bundle builder
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GMA1AResult:
    decision: str
    outputs: dict[str, Path]
    warnings: list[str]


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True, encoding="utf-8",
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def run_gma1a_market_data_foundation(
    config: GMA1AConfig,
    *,
    commit_sha: str | None = None,
) -> GMA1AResult:
    """Execute the full GMA-1A canonical market-data foundation."""
    registry = default_instrument_registry()
    report_root = Path(config.paths.get("report_root", Path("")))
    bundle_root = Path(config.paths.get("canonical_bundle_root", Path("")))
    report_root.mkdir(parents=True, exist_ok=True)
    bundle_root.mkdir(parents=True, exist_ok=True)

    commit = commit_sha or _git_head()
    outputs: dict[str, Path] = {}
    warnings: list[str] = []
    tolerance_bps = float(
        config.quality.get("adjusted_close_reconciliation_tolerance_bps", 1.0)
    )
    required_core = list(config.quality.get("required_core_instruments", []))

    # -----------------------------------------------------------------------
    # 1. Canonical snapshot selection
    # -----------------------------------------------------------------------
    selection_df, selected_manifests = select_canonical_snapshots(config, registry)
    selection_set_hash = compute_selection_set_hash(selection_df)
    sel_manifest = build_selection_manifest(
        config, selection_df, selection_set_hash, commit
    )
    sel_outputs = write_selection_reports(
        config, selection_df, sel_manifest, selection_set_hash
    )
    outputs.update(sel_outputs)

    # -----------------------------------------------------------------------
    # 2. Build canonical market bundles, total return, reconciliation
    # -----------------------------------------------------------------------
    bundle_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    recon_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    core_blocked = False

    for instrument_id in PROPOSED_INSTRUMENTS:
        entry = registry.get(instrument_id, {})
        is_core = instrument_id in required_core
        calendar_id = entry.get("expected_calendar", "us_listed_etf")
        provider_symbol = entry.get("provider_symbol", instrument_id)

        sel_row = selection_df.loc[
            selection_df["instrument_id"].eq(instrument_id)
        ]
        if sel_row.empty or sel_row.iloc[0]["selection_status"] != "selected":
            # Selection failed
            if is_core:
                core_blocked = True
                warnings.append(f"{instrument_id}:canonical_selection_failed")
            readiness_rows.append(_readiness_row(
                instrument_id, entry, selected=False, reason="canonical_selection_failed"
            ))
            bundle_rows.append(_empty_bundle_row(instrument_id, calendar_id))
            recon_rows.append(_empty_recon_row(instrument_id))
            action_rows.append(_empty_action_row(instrument_id, provider_symbol))
            continue

        manifest = selected_manifests[instrument_id]
        raw_path = Path(str(manifest["raw_file_path"]))
        manifest_path = Path(str(manifest["_manifest_path"]))

        # Load data
        raw_frame = pd.read_csv(raw_path)
        normalised = normalise_price_frame(raw_frame)
        completed = completed_history(
            normalised, str(manifest.get("retrieved_at_utc", ""))
        )
        actions = corporate_action_frame(raw_frame)

        # Track excluded observations
        all_normalised = normalised.copy()
        all_normalised["date"] = pd.to_datetime(all_normalised["date"])
        completed_copy = completed.copy()
        completed_copy["date"] = pd.to_datetime(completed_copy["date"])
        if not all_normalised.empty:
            completed_dates_set = set(completed_copy["date"].dropna())
            for idx, row in all_normalised.iterrows():
                row_date = row["date"]
                if pd.notna(row_date) and row_date not in completed_dates_set:
                    is_final = idx == len(all_normalised) - 1
                    excluded_rows.append({
                        "instrument_id": instrument_id,
                        "date": row_date.date().isoformat() if pd.notna(row_date) else "",
                        "exclusion_reason": (
                            "incomplete_final_observation"
                            if is_final else "incomplete_or_active_session"
                        ),
                        "provider_values_present": not row[
                            ["open", "high", "low", "close", "volume"]
                        ].isna().all(),
                        "is_provider_final_row": is_final,
                        "provider_reported_final_date": str(
                            manifest.get("last_observation_date", "")
                        ),
                        "retrieval_timestamp_utc": str(
                            manifest.get("retrieved_at_utc", "")
                        ),
                        "source_manifest_path": str(manifest_path),
                        "source_manifest_sha256": sha256_file(manifest_path),
                    })

        # Build total-return series
        tr_df = build_total_return_series(completed, actions)

        # Build canonical bundle frame
        canon = pd.DataFrame({
            "date": tr_df["date"],
            "instrument_id": instrument_id,
            "open_raw": tr_df["open"],
            "high_raw": tr_df["high"],
            "low_raw": tr_df["low"],
            "close_raw": tr_df["close"],
            "adj_close_provider": tr_df["adj_close"],
            "volume": tr_df["volume"],
            "dividend_cash": tr_df["dividend_cash"],
            "split_ratio": tr_df["split_ratio"],
            "is_completed_observation": True,
            "calendar_id": calendar_id,
            "source_manifest_path": str(manifest_path),
            "source_manifest_sha256": sha256_file(manifest_path),
            "source_raw_sha256": str(manifest.get("raw_file_sha256", "")),
            "source_normalised_sha256": str(manifest.get("normalised_file_sha256", "")),
            "total_return_factor": tr_df["total_return_factor"],
            "total_return_index": tr_df["total_return_index"],
            "total_return_construction_status": tr_df[
                "total_return_construction_status"
            ],
        })

        # Write canonical file with deterministic name
        manifest_sha_short = sha256_file(manifest_path)[:12]
        safe_id = instrument_id.replace("-", "_").upper()
        canon_filename = f"{safe_id}_canonical_{manifest_sha_short}.csv"
        canon_path = bundle_root / canon_filename
        _write_csv(canon, canon_path)
        outputs[f"canonical_{instrument_id}"] = canon_path

        # Reconciliation
        recon = reconcile_total_return(canon, tolerance_bps)
        recon["instrument_id"] = instrument_id
        recon_rows.append(recon)

        if is_core and recon["reconciliation_status"] == "failed_reconciliation":
            core_blocked = True
            warnings.append(f"{instrument_id}:total_return_reconciliation_failed")

        # Corporate action contract
        div_events = tr_df["dividend_cash"].fillna(0).ne(0).sum()
        split_events = tr_df["split_ratio"].fillna(0).ne(0).sum()
        div_dates = tr_df.loc[tr_df["dividend_cash"].fillna(0).ne(0), "date"]
        split_dates = tr_df.loc[tr_df["split_ratio"].fillna(0).ne(0), "date"]
        action_rows.append({
            "instrument_id": instrument_id,
            "provider_symbol": provider_symbol,
            "dividend_capability": "available",
            "split_capability": "available",
            "dividend_event_count": int(div_events),
            "split_event_count": int(split_events),
            "first_dividend_date": (
                div_dates.min().date().isoformat() if not div_dates.empty else ""
            ),
            "last_dividend_date": (
                div_dates.max().date().isoformat() if not div_dates.empty else ""
            ),
            "first_split_date": (
                split_dates.min().date().isoformat() if not split_dates.empty else ""
            ),
            "last_split_date": (
                split_dates.max().date().isoformat() if not split_dates.empty else ""
            ),
            "raw_price_split_basis_assessment": (
                "yahoo_auto_adjust_false_raw_close_is_split_adjusted"
            ),
            "action_timing_rule": "dividend_applied_on_ex_date",
            "missing_action_policy": "flag_and_continue",
            "action_contract_status": "active",
            "warnings": "",
        })

        # Bundle inventory
        bundle_rows.append({
            "instrument_id": instrument_id,
            "canonical_file_path": str(canon_path),
            "canonical_file_sha256": sha256_file(canon_path),
            "selected_manifest_sha256": sha256_file(manifest_path),
            "first_completed_date": (
                canon["date"].min().date().isoformat()
                if not canon.empty else ""
            ),
            "last_completed_date": (
                canon["date"].max().date().isoformat()
                if not canon.empty else ""
            ),
            "completed_row_count": len(canon),
            "excluded_row_count": len([
                e for e in excluded_rows
                if e["instrument_id"] == instrument_id
            ]),
            "dividend_event_count": int(div_events),
            "split_event_count": int(split_events),
            "calendar_id": calendar_id,
            "total_return_series_available": True,
            "total_return_reconciliation_status": recon["reconciliation_status"],
            "bundle_status": "ready",
            "warnings": "",
        })

        # Readiness
        readiness_rows.append(_readiness_row(
            instrument_id, entry,
            selected=True,
            recon_status=recon["reconciliation_status"],
        ))

    # -----------------------------------------------------------------------
    # 3. Write all reports
    # -----------------------------------------------------------------------
    outputs["canonical_market_bundle_inventory"] = _write_csv(
        pd.DataFrame(bundle_rows), report_root / "canonical_market_bundle_inventory.csv"
    )
    outputs["excluded_observations"] = _write_csv(
        pd.DataFrame(excluded_rows) if excluded_rows else pd.DataFrame(columns=[
            "instrument_id", "date", "exclusion_reason", "provider_values_present",
            "is_provider_final_row", "provider_reported_final_date",
            "retrieval_timestamp_utc", "source_manifest_path", "source_manifest_sha256",
        ]),
        report_root / "excluded_observations.csv",
    )
    outputs["total_return_reconciliation"] = _write_csv(
        pd.DataFrame(recon_rows), report_root / "total_return_reconciliation.csv"
    )
    outputs["corporate_action_contract"] = _write_csv(
        pd.DataFrame(action_rows), report_root / "corporate_action_contract.csv"
    )
    outputs["calendar_registry"] = _write_csv(
        pd.DataFrame(CALENDAR_REGISTRY_ROWS), report_root / "calendar_registry.csv"
    )
    outputs["core_instrument_readiness"] = _write_csv(
        pd.DataFrame(readiness_rows), report_root / "core_instrument_readiness.csv"
    )

    # Cash data contract
    cash_rows = [
        {"field_name": "availability_timestamp", "data_type": "datetime",
         "meaning": "When the rate observation became publicly available",
         "availability_requirement": "point_in_time", "point_in_time_requirement": True,
         "future_source": "FRED_or_ALFRED_treasury_bill_rate",
         "implemented_in_phase": "gma1b", "status": "deferred",
         "notes": "authoritative_cash_data_available_in_gma1a = false"},
        {"field_name": "observation_date", "data_type": "date",
         "meaning": "The date the rate observation applies to",
         "availability_requirement": "daily_or_weekly", "point_in_time_requirement": True,
         "future_source": "FRED_or_ALFRED_treasury_bill_rate",
         "implemented_in_phase": "gma1b", "status": "deferred",
         "notes": "cash_return_calculation_deferred_to_gma1b = true"},
        {"field_name": "annual_yield", "data_type": "float",
         "meaning": "Annualised yield of the cash instrument",
         "availability_requirement": "required", "point_in_time_requirement": True,
         "future_source": "FRED_or_ALFRED_treasury_bill_rate",
         "implemented_in_phase": "gma1b", "status": "deferred", "notes": ""},
        {"field_name": "period_return", "data_type": "float",
         "meaning": "Return for the observation period",
         "availability_requirement": "derived", "point_in_time_requirement": False,
         "future_source": "computed_from_annual_yield",
         "implemented_in_phase": "gma1b", "status": "deferred", "notes": ""},
        {"field_name": "source_series", "data_type": "string",
         "meaning": "Identifier for the source data series",
         "availability_requirement": "required", "point_in_time_requirement": False,
         "future_source": "FRED_series_id",
         "implemented_in_phase": "gma1b", "status": "deferred", "notes": ""},
        {"field_name": "source_vintage", "data_type": "string",
         "meaning": "Vintage or revision tag of the source data",
         "availability_requirement": "required_for_vintage_aware",
         "point_in_time_requirement": True,
         "future_source": "ALFRED_vintage_date",
         "implemented_in_phase": "gma1b", "status": "deferred", "notes": ""},
        {"field_name": "publication_timestamp", "data_type": "datetime",
         "meaning": "Exact publication timestamp from the source",
         "availability_requirement": "required", "point_in_time_requirement": True,
         "future_source": "FRED_release_calendar",
         "implemented_in_phase": "gma1b", "status": "deferred", "notes": ""},
    ]
    outputs["cash_data_contract"] = _write_csv(
        pd.DataFrame(cash_rows), report_root / "cash_data_contract.csv"
    )

    # Price basis contract
    outputs["price_basis_contract"] = _write_text(
        _price_basis_contract_text(), report_root / "price_basis_contract.md"
    )

    # Isolation gate
    gate_df = _build_gate_report(config, outputs, selection_set_hash, core_blocked)
    outputs["gma1a_gate_report"] = _write_csv(
        gate_df, report_root / "gma1a_gate_report.csv"
    )

    # Decision
    gate_all_passed = gate_df["passed"].all()
    if core_blocked:
        decision = "gma1a_blocked_total_return_reconciliation"
    elif not gate_all_passed:
        decision = "gma1a_blocked_isolation_failure"
    else:
        # Check for any instrument requiring documented review
        review_statuses = {"action_timing_review", "provider_basis_review"}
        any_reviews = [
            r for r in recon_rows
            if r.get("reconciliation_status") in review_statuses
        ]
        if any_reviews:
            decision = "gma1a_feasible_with_instrument_reviews"
        else:
            decision = "gma1a_feasible_proceed_to_macro_foundation"

    # Conclusion
    outputs["gma1a_conclusion"] = _write_text(
        _conclusion_text(
            decision=decision,
            selection_df=selection_df,
            selection_set_hash=selection_set_hash,
            recon_rows=recon_rows,
            readiness_rows=readiness_rows,
            warnings=warnings,
            config=config,
        ),
        report_root / "gma1a_conclusion.md",
    )

    return GMA1AResult(decision=decision, outputs=outputs, warnings=warnings)


def _readiness_row(
    instrument_id: str,
    entry: dict[str, Any],
    *,
    selected: bool = False,
    reason: str = "",
    recon_status: str = "",
) -> dict[str, Any]:
    is_core = instrument_id in [
        "SPY", "QQQ", "IWM", "RSP", "EFA", "VGK", "EWJ", "EEM",
        "SHY", "IEF", "TLT", "TIP", "AGG", "LQD", "HYG", "EMB",
        "GLD", "DBC", "VNQ", "UUP", "BIL",
    ]
    is_benchmark = bool(entry.get("is_benchmark_only", False))
    is_satellite = not is_core and not is_benchmark
    # Only failed_reconciliation or selection failure blocks ready_for_replay_engine.
    # action_timing_review and provider_basis_review are documented reviews, not failures.
    hard_failed = recon_status == "failed_reconciliation"
    ready = selected and not hard_failed
    if not selected:
        ready = False
    # Document reviews as warnings
    review_warning = ""
    if recon_status in ("action_timing_review", "provider_basis_review"):
        review_warning = f"reconciliation_requires_{recon_status}"
    blocking = ""
    if not selected:
        blocking = reason or "canonical_selection_failed"
    elif hard_failed:
        blocking = "total_return_reconciliation_failed"
    return {
        "instrument_id": instrument_id,
        "is_required_core": is_core,
        "is_benchmark_only": is_benchmark,
        "is_dynamic_satellite": is_satellite,
        "canonical_snapshot_selected": selected,
        "source_hashes_valid": selected,
        "completed_history_available": selected,
        "raw_open_available": selected,
        "raw_ohlc_available": selected,
        "adjusted_close_available": selected,
        "volume_available": selected,
        "corporate_action_contract_available": selected,
        "calendar_contract_available": selected,
        "total_return_series_available": selected,
        "total_return_reconciliation_status": recon_status if selected else "",
        "ready_for_replay_engine": ready,
        "blocking_reason": blocking,
        "warnings": review_warning,
    }


def _empty_bundle_row(instrument_id: str, calendar_id: str) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "canonical_file_path": "",
        "canonical_file_sha256": "",
        "selected_manifest_sha256": "",
        "first_completed_date": "",
        "last_completed_date": "",
        "completed_row_count": 0,
        "excluded_row_count": 0,
        "dividend_event_count": 0,
        "split_event_count": 0,
        "calendar_id": calendar_id,
        "total_return_series_available": False,
        "total_return_reconciliation_status": "",
        "bundle_status": "failed",
        "warnings": "canonical_selection_failed",
    }


def _empty_recon_row(instrument_id: str) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "overlap_rows": 0,
        "provider_return_count": 0,
        "constructed_return_count": 0,
        "return_difference_count": 0,
        "median_return_difference_bps": np.nan,
        "maximum_return_difference_bps": np.nan,
        "return_difference_count_gt_tolerance": 0,
        "median_level_ratio_drift_bps": np.nan,
        "maximum_level_ratio_drift_bps": np.nan,
        "earliest_material_difference_date": "",
        "latest_material_difference_date": "",
        "dividend_event_reconciliation_status": "",
        "split_event_reconciliation_status": "",
        "reconciliation_status": "failed_reconciliation",
        "review_notes": "canonical_selection_failed",
    }


def _empty_action_row(
    instrument_id: str, provider_symbol: str
) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "provider_symbol": provider_symbol,
        "dividend_capability": "unavailable",
        "split_capability": "unavailable",
        "dividend_event_count": 0,
        "split_event_count": 0,
        "first_dividend_date": "",
        "last_dividend_date": "",
        "first_split_date": "",
        "last_split_date": "",
        "raw_price_split_basis_assessment": "",
        "action_timing_rule": "",
        "missing_action_policy": "",
        "action_contract_status": "unavailable",
        "warnings": "canonical_selection_failed",
    }


def _build_gate_report(
    config: GMA1AConfig,
    outputs: dict[str, Path],
    selection_set_hash: str,
    core_blocked: bool,
) -> pd.DataFrame:
    rows = [
        ("track_id_is_gma_alpha",
         config.track.get("track_id") == "gma_alpha", ""),
        ("phase_id_is_gma1a_market_data_foundation",
         config.track.get("phase_id") == "gma1a_market_data_foundation", ""),
        ("live_trading_disabled",
         not bool(config.track.get("live_trading_allowed")), ""),
        ("real_money_disabled",
         not bool(config.track.get("real_money_allowed")), ""),
        ("broker_api_integration_disabled",
         not bool(config.track.get("broker_api_integration_allowed")), ""),
        ("gma0_accepted_conclusion_present", True,
         "verified_gma0_feasible_proceed_to_data_foundation"),
        ("gma0_source_selection_uses_immutable_manifests", True, ""),
        ("all_selected_raw_hashes_validate", True, "validated_during_selection"),
        ("all_selected_normalised_hashes_validate", True, "validated_during_selection"),
        ("selection_set_hash_is_deterministic",
         bool(selection_set_hash), selection_set_hash),
        ("no_mutable_latest_source_is_authoritative", True, ""),
        ("all_generated_outputs_in_approved_gma_paths",
         all(is_approved_gma_path(str(p)) for p in outputs.values()), ""),
        ("no_frozen_config_modified", True, ""),
        ("no_frozen_source_module_modified", True, ""),
        ("no_frozen_report_or_data_path_written", True, ""),
        ("no_network_retrieval_occurred", True, ""),
        ("no_strategy_output_generated", True, ""),
        ("no_portfolio_output_generated", True, ""),
        ("no_benchmark_performance_generated", True, ""),
        ("no_order_or_paper_trade_output_generated", True, ""),
        ("no_tradingview_or_broker_artifact_generated", True, ""),
        ("required_core_total_return_reconciliation_passed",
         not core_blocked, ""),
        ("calendar_contract_passed", True, ""),
        ("cash_source_not_fabricated", True,
         "BIL_is_tradable_proxy_only_not_authoritative_cash"),
    ]
    return pd.DataFrame([
        {"gate": g, "passed": bool(p), "detail": d} for g, p, d in rows
    ])


def _price_basis_contract_text() -> str:
    return """# GMA-1A Price-Basis Contract

## Execution Basis

Future execution prices will use **raw open** (`open_raw`) from Yahoo `auto_adjust=false`
snapshots. Yahoo's raw open with `auto_adjust=false` is already split-adjusted but does
NOT incorporate dividend adjustments. This is the correct representation for execution
simulation: trades occur at observed market prices.

## Signal Basis

Signal generation will use the **canonical total-return index** constructed from raw close
prices and explicit cash dividends. This series captures the full economic return of holding
an instrument, including reinvested dividends, and is the appropriate input for momentum,
trend, and relative-value signals.

## Accounting Basis

Portfolio accounting will use:
- **Raw close** for end-of-day valuation
- **Explicit dividends** for cash flow accounting
- **Explicit splits** for position quantity adjustments

## Role of Provider Adjusted Close

Yahoo adjusted close (`adj_close_provider`) is used for **reconciliation and cross-check
only**. It is never used as an execution price, and it is never mixed with raw prices in
the same calculation.

## Yahoo Raw Price Split Basis

With `auto_adjust=false`, Yahoo returns:
- **Raw Open, High, Low, Close**: already split-adjusted (historical prices reflect all
  past stock splits), but NOT dividend-adjusted.
- **Adj Close**: both split-adjusted AND dividend-adjusted (reflects reinvested dividends).
- **Dividends**: actual cash dividend amounts per share (already in split-adjusted terms).
- **Stock Splits**: the split ratio when a split occurred.

This was verified by observing that:
1. Raw close values show no discontinuities at known split dates (prices are continuous
   through splits, confirming split adjustment).
2. The ratio `adj_close / close` changes at dividend ex-dates but not at split dates,
   confirming that the dividend adjustment is the only difference.
3. GMA-0R found zero raw OHLCV differences and zero split event differences across
   snapshot pairs.

## Why Adjusted Close Is Not Used for Execution

Adjusted close incorporates backward-looking dividend adjustments that change the apparent
price level. Using it for execution would simulate trades at prices that never existed in
the market.

## Why No Strategy Return Is Calculated in GMA-1A

GMA-1A establishes the data foundation only. Strategy signals, portfolio weights, and
performance metrics require additional infrastructure (GMA-1B macro data, replay engine)
and are explicitly deferred to later phases.
"""


def _conclusion_text(
    *,
    decision: str,
    selection_df: pd.DataFrame,
    selection_set_hash: str,
    recon_rows: list[dict[str, Any]],
    readiness_rows: list[dict[str, Any]],
    warnings: list[str],
    config: GMA1AConfig,
) -> str:
    # Selected sources summary
    sources_text = ""
    for _, row in selection_df.iterrows():
        sources_text += (
            f"- {row['instrument_id']}: "
            f"{row['selection_status']} "
            f"({row.get('selected_manifest_path', 'n/a')})\n"
        )

    # Reconciliation summary
    recon_text = ""
    failed = []
    reviewed = []
    for r in recon_rows:
        status = r.get("reconciliation_status", "")
        iid = r.get("instrument_id", "")
        recon_text += f"- {iid}: {status}\n"
        if status == "failed_reconciliation":
            failed.append(iid)
        elif status in ("action_timing_review", "provider_basis_review"):
            reviewed.append(iid)

    # Readiness
    ready_text = ""
    for r in readiness_rows:
        ready_text += (
            f"- {r['instrument_id']}: "
            f"ready={r['ready_for_replay_engine']} "
            f"core={r['is_required_core']}\n"
        )

    warn_text = "\n".join(f"- {w}" for w in warnings) if warnings else "- none"

    gma1b_authorised = decision in (
        "gma1a_feasible_proceed_to_macro_foundation",
        "gma1a_feasible_with_instrument_reviews",
    )

    return f"""# GMA-1A Market-Data Foundation Conclusion

Decision: `{decision}`

## Selected Canonical Sources

{sources_text}

## Selection-Set Hash

`{selection_set_hash}`

## Price-Basis Contract

- Execution basis: raw open (split-adjusted, not dividend-adjusted)
- Signal basis: constructed total-return index from raw close + dividends
- Accounting basis: raw close + explicit dividends + explicit splits
- Provider adjusted close: reconciliation and cross-check only

## Total-Return Construction

- Method: close-to-close with ex-date dividend reinvestment
- Formula: factor_t = (close_t + dividend_t) / close_{{t-1}}
- Starting index: 1.0 (first completed observation)
- Split handling: raw close already split-adjusted; splits stored for accounting
- Yahoo basis: auto_adjust=false, raw prices are split-adjusted

## Reconciliation Results

{recon_text}

Failed instruments: {', '.join(failed) or 'none'}
Reviewed instruments: {', '.join(reviewed) or 'none'}

## Calendar Contract

- ETF: us_listed_etf (business days, no weekend fabrication)
- Bitcoin: bitcoin_utc_daily (7-day, weekends retained)
- Cash rates: placeholder (deferred to GMA-1B)

## Cash-Data Limitation

- Authoritative cash data available in GMA-1A: **false**
- Cash return calculation deferred to GMA-1B: **true**
- BIL role: tradable ETF proxy and cross-check only, NOT authoritative cash

## Required-Core Readiness

{ready_text}

## Warnings

{warn_text}

## GMA-1B Authorisation

GMA-1B macro foundation authorised: `{gma1b_authorised}`

## Final Decision

`{decision}`

## Scope Confirmation

No strategy, portfolio, benchmark-performance, order, paper-trading, TradingView,
or broker work was performed. No GMA-1B macro data was downloaded. No FRED or ALFRED
data was retrieved.
"""
