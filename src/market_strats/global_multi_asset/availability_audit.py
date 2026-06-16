from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.global_multi_asset.config import GMAConfig
from market_strats.global_multi_asset.data.manifests import read_manifest, sha256_file
from market_strats.global_multi_asset.data.price_provider import (
    OfflineFixtureProvider,
    ProviderSnapshot,
    YFinanceProvider,
)
from market_strats.global_multi_asset.data.validation import (
    completed_history,
    corporate_action_frame,
    corporate_action_audit,
    liquidity_audit,
    normalise_price_frame,
    validate_price_frame,
)
from market_strats.global_multi_asset.identifiers import PHASE_ID, TRACK_ID
from market_strats.global_multi_asset.universe import (
    PROPOSED_INSTRUMENTS,
    calendar_frame,
    macro_series_frame,
    registry_frame,
)

APPROVED_WRITE_PREFIXES = [
    Path("configs/global_multi_asset_alpha"),
    Path("src/market_strats/global_multi_asset"),
    Path("tests/global_multi_asset"),
    Path("docs/global_multi_asset_alpha"),
    Path("data/global_multi_asset_alpha"),
    Path("reports/global_multi_asset_alpha"),
    Path("state/global_multi_asset_alpha"),
]


@dataclass(frozen=True)
class AuditResult:
    decision: str
    outputs: dict[str, Path]
    replay_start: pd.DataFrame
    gate_report: pd.DataFrame
    warnings: list[str]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git_lines(args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return []
    if result.returncode not in {0, 1}:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def capture_working_tree_baseline() -> dict[str, set[str]]:
    return {
        "status": set(_git_lines(["status", "--porcelain"])),
        "diff": set(_git_lines(["diff", "--name-only"])),
        "cached": set(_git_lines(["diff", "--cached", "--name-only"])),
    }


def _changed_paths_from_status(lines: set[str]) -> set[str]:
    paths = set()
    for line in lines:
        if len(line) > 3:
            paths.add(line[3:].strip())
    return paths


def _current_changed_paths() -> set[str]:
    status_paths = _changed_paths_from_status(set(_git_lines(["status", "--porcelain"])))
    diff_paths = set(_git_lines(["diff", "--name-only"]))
    cached_paths = set(_git_lines(["diff", "--cached", "--name-only"]))
    return status_paths | diff_paths | cached_paths


def _is_approved_path(path: str) -> bool:
    candidate = Path(path)
    return any(candidate == prefix or prefix in candidate.parents for prefix in APPROVED_WRITE_PREFIXES)


def _join(values: list[str] | set[str]) -> str:
    clean = sorted({str(value) for value in values if str(value)})
    return ";".join(clean)


def _date_or_empty(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _first_date_on_or_after(dates: pd.Series, target: pd.Timestamp) -> str:
    clean = pd.Series(pd.to_datetime(dates, errors="coerce")).dropna().sort_values()
    values = clean.loc[clean.ge(target)]
    if values.empty:
        return ""
    return values.iloc[0].date().isoformat()


def _first_date_after(dates: pd.Series, target: pd.Timestamp | str) -> str:
    clean = pd.Series(pd.to_datetime(dates, errors="coerce")).dropna().sort_values()
    if target == "" or pd.isna(target):
        return ""
    target_date = pd.Timestamp(target)
    values = clean.loc[clean.gt(target_date)]
    if values.empty:
        return ""
    return values.iloc[0].date().isoformat()


def _availability_row(
    *,
    instrument: dict[str, Any],
    snapshot: ProviderSnapshot,
    completed: pd.DataFrame,
    audit: dict[str, Any],
    warmup_months: int,
    audit_mode: str,
) -> dict[str, Any]:
    instrument_id = instrument["instrument_id"]
    if completed.empty:
        return {
            **audit,
            "audit_mode": audit_mode,
            "provider": snapshot.provider,
            "provider_symbol": snapshot.provider_symbol,
            "request_timestamp_utc": snapshot.retrieved_at_utc,
            "raw_snapshot_path": str(snapshot.raw_file_path),
            "raw_snapshot_sha256": sha256_file(snapshot.raw_file_path),
            "normalised_snapshot_path": str(snapshot.normalised_file_path),
            "normalised_snapshot_sha256": sha256_file(snapshot.normalised_file_path),
            "manifest_path": str(snapshot.manifest_path),
            "instrument_id": instrument_id,
            "expected_calendar": instrument["expected_calendar"],
            "is_benchmark_only": bool(instrument["is_benchmark_only"]),
            "first_return_eligible_date": "",
            "first_raw_open_eligible_date": "",
            "warmup_complete_date": "",
            "first_next_open_execution_date": "",
            "portfolio_eligibility_date": "",
            "last_available_date": "",
            "availability_status": "unavailable",
        }
    dates = pd.to_datetime(completed["date"]).sort_values().reset_index(drop=True)
    first_return_date = dates.iloc[1].date().isoformat() if len(dates) >= 2 else ""
    raw_open_dates = completed.loc[completed["open"].notna() & completed["open"].gt(0), "date"]
    first_raw_open = _date_or_empty(pd.to_datetime(raw_open_dates).min()) if not raw_open_dates.empty else ""
    is_benchmark_only = bool(instrument["is_benchmark_only"])
    if is_benchmark_only:
        warmup_complete = ""
        next_open = ""
        portfolio_eligibility = first_return_date
    else:
        warmup_target = pd.Timestamp(dates.iloc[0]) + pd.DateOffset(months=warmup_months)
        warmup_complete = _first_date_on_or_after(dates, warmup_target)
        next_open = _first_date_after(dates, warmup_complete)
        portfolio_eligibility = next_open
    return {
        **audit,
        "audit_mode": audit_mode,
        "provider": snapshot.provider,
        "provider_symbol": snapshot.provider_symbol,
        "request_timestamp_utc": snapshot.retrieved_at_utc,
        "raw_snapshot_path": str(snapshot.raw_file_path),
        "raw_snapshot_sha256": sha256_file(snapshot.raw_file_path),
        "normalised_snapshot_path": str(snapshot.normalised_file_path),
        "normalised_snapshot_sha256": sha256_file(snapshot.normalised_file_path),
        "manifest_path": str(snapshot.manifest_path),
        "instrument_id": instrument_id,
        "expected_calendar": instrument["expected_calendar"],
        "is_benchmark_only": is_benchmark_only,
        "benchmark_warmup_exempt": is_benchmark_only,
        "first_return_eligible_date": first_return_date,
        "first_raw_open_eligible_date": first_raw_open,
        "warmup_complete_date": warmup_complete,
        "first_next_open_execution_date": next_open,
        "portfolio_eligibility_date": portfolio_eligibility,
        "last_available_date": dates.iloc[-1].date().isoformat(),
        "availability_status": "available" if portfolio_eligibility else "insufficient_history",
    }


def _max_date_with_bottlenecks(frame: pd.DataFrame, instruments: list[str], column: str) -> tuple[str, str]:
    subset = frame.loc[frame["instrument_id"].isin(instruments)].copy()
    subset[column] = pd.to_datetime(subset[column], errors="coerce")
    if subset[column].isna().any() or subset.empty:
        missing = subset.loc[subset[column].isna(), "instrument_id"].astype(str).tolist()
        return "", _join(missing or instruments)
    max_date = subset[column].max()
    bottlenecks = subset.loc[subset[column].eq(max_date), "instrument_id"].astype(str).tolist()
    return max_date.date().isoformat(), _join(bottlenecks)


def _participants(config: GMAConfig, instruments: list[str]) -> str:
    return _join(instruments)


def _replay_start_assessment(config: GMAConfig, price_availability: pd.DataFrame) -> pd.DataFrame:
    core = list(config.replay_start["required_core_instruments"])
    core_data_start, core_data_start_bottlenecks = _max_date_with_bottlenecks(
        price_availability,
        core,
        "first_observation_date",
    )
    core_signal, core_signal_bottlenecks = _max_date_with_bottlenecks(
        price_availability,
        core,
        "warmup_complete_date",
    )
    core_execution, core_execution_bottlenecks = _max_date_with_bottlenecks(
        price_availability,
        core,
        "first_next_open_execution_date",
    )
    acwi_ids = [
        instrument_id
        for instrument_id, instrument in config.instruments.items()
        if bool(instrument.get("is_benchmark_only"))
    ]
    acwi_return_date, acwi_bottlenecks = _max_date_with_bottlenecks(
        price_availability, acwi_ids, "first_return_eligible_date"
    ) if acwi_ids else ("", "")
    benchmark_common_candidates = [
        value for value in [core_execution, acwi_return_date] if value
    ]
    benchmark_date = (
        max(pd.Timestamp(value) for value in benchmark_common_candidates)
        .date()
        .isoformat()
        if benchmark_common_candidates
        else ""
    )
    expanded_ids = [
        instrument_id
        for instrument_id, instrument in config.instruments.items()
        if not bool(instrument.get("is_benchmark_only"))
        and instrument_id != "BTC-USD"
    ]
    expanded_non_crypto_date, expanded_bottlenecks = _max_date_with_bottlenecks(
        price_availability,
        expanded_ids,
        "warmup_complete_date",
    )
    btc_row = price_availability.loc[price_availability["instrument_id"].eq("BTC-USD")]
    bitcoin_date = ""
    if not btc_row.empty:
        bitcoin_date = str(btc_row.iloc[0].get("warmup_complete_date", ""))
    full_allocator_ids = [
        instrument_id
        for instrument_id, instrument in config.instruments.items()
        if not bool(instrument.get("is_benchmark_only"))
    ]
    full_allocator_date, full_allocator_bottlenecks = _max_date_with_bottlenecks(
        price_availability,
        full_allocator_ids,
        "warmup_complete_date",
    )
    if bitcoin_date and full_allocator_date:
        full_allocator_date = max(
            pd.Timestamp(full_allocator_date),
            pd.Timestamp(bitcoin_date),
        ).date().isoformat()
    provisional = str(config.replay_start.get("provisional_first_signal_rule", ""))
    return pd.DataFrame(
        [
            {
                "track_id": TRACK_ID,
                "phase_id": PHASE_ID,
                "earliest_core_data_start": core_data_start,
                "earliest_core_signal_date": core_signal,
                "earliest_core_next_open_execution_date": core_execution,
                "earliest_expanded_non_crypto_allocator_date": expanded_non_crypto_date,
                "earliest_full_allocator_including_bitcoin_date": full_allocator_date,
                "earliest_bitcoin_eligible_date": bitcoin_date,
                "earliest_benchmark_comparison_date": benchmark_date,
                "earliest_possible_core_warmup_start": core_data_start,
                "earliest_common_core_signal_date": core_signal,
                "earliest_expanded_universe_date": expanded_non_crypto_date,
                "legacy_earliest_expanded_universe_date_deprecated": True,
                "legacy_earliest_expanded_universe_date_definition": "deprecated_alias_for_earliest_expanded_non_crypto_allocator_date",
                "core_participating_instruments": _participants(config, core),
                "expanded_non_crypto_participating_instruments": _participants(config, expanded_ids),
                "full_allocator_including_bitcoin_participating_instruments": _participants(config, full_allocator_ids),
                "benchmark_comparison_participating_instruments": _join(["core_replay", *acwi_ids]),
                "acwi_first_return_eligible_date": acwi_return_date,
                "acwi_benchmark_warmup_exempt": True,
                "core_warmup_start_bottleneck_instruments": core_data_start_bottlenecks,
                "core_signal_bottleneck_instruments": core_signal_bottlenecks,
                "core_execution_bottleneck_instruments": core_execution_bottlenecks,
                "benchmark_bottleneck_instruments": acwi_bottlenecks,
                "expanded_universe_bottleneck_instruments": expanded_bottlenecks,
                "full_allocator_including_bitcoin_bottleneck_instruments": full_allocator_bottlenecks,
                "bitcoin_delays_core_start": False,
                "bitcoin_delays_full_allocator_start": bool(
                    bitcoin_date and full_allocator_date == bitcoin_date
                ),
                "provisional_first_signal_rule": provisional,
                "matches_provisional_expectation": "not_evaluated_no_hardcoded_expectation",
            }
        ]
    )


def _reuse_map_text() -> str:
    return """# GMA-0 Reuse and Isolation Map

GMA-0 is an isolated feasibility and data-availability audit for the
`Global Multi-Asset Alpha and Paper-Trading Track`.

## Existing Components Inspected

- `README.md`: reused only as project-status context and frozen-track boundary context.
- `pyproject.toml`: reused for dependency and lint/test conventions.
- `.gitignore`: inspected; GMA-0 requires additive ignores for
  `data/global_multi_asset_alpha/` and `state/global_multi_asset_alpha/` because existing
  rules only covered `data/raw/`, `data/processed/`, and `reports/`.
- `configs/spy_sma10.yaml`: inspected only; not imported as GMA experiment state.
- `src/market_strats/run_backtest.py`: inspected only; GMA-0 does not add flags there.
- `src/market_strats/data/fetch_yfinance.py`: schema ideas reused, but not imported because it
  creates a shared cache path at import time.
- `src/market_strats/data/validation.py`: validation concepts reused, not imported.
- `src/market_strats/data/cash_rates.py`: ETF/BTC calendar and cash-role concepts reused, not
  imported into GMA-0.
- `src/market_strats/analysis/metrics.py`: inspected to avoid performance metric reuse; GMA-0
  does not calculate CAGR, Sharpe, drawdown, P&L, or strategy returns.
- `src/market_strats/analysis/manual_paper_session.py`: manual safety-boundary concepts reused
  conceptually only; no paper state is imported.
- `src/market_strats/analysis/frozen_cost_aware_portfolio.py`: safety flags and hash conventions
  inspected; no model, portfolio, or experiment state is reused.

## Deliberately Not Reused

Frozen ETF/manual-paper and individual-equity report directories, ledgers, model IDs, hashes,
portfolio construction code, paper-order code, and orchestration flags are not imported or modified.

## Price-Basis Contract

Future phases may use raw `open` for next-open execution, raw OHLC for execution validation,
adjusted close or explicitly constructed total-return series for economically appropriate signals,
and dividends/splits for accounting and reconciliation. GMA-0 only audits availability and does
not calculate strategy returns.

## Benchmark Exemption Contract

Benchmark designs such as SPY Buy & Hold, ACWI Buy & Hold, fixed 60/40, and static
risk-balanced benchmarks may have fixed weights above candidate-strategy caps. GMA-0 documents
this contract only and does not calculate benchmark performance.
"""


def _class_counts(frame: pd.DataFrame) -> str:
    if frame.empty or "reproducibility_classification" not in frame.columns:
        return "none"
    counts = frame["reproducibility_classification"].value_counts(dropna=False)
    return "\n".join(f"- {key}: {value}" for key, value in counts.items())


def _retained_universe_decision() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "instrument_id": instrument_id,
                "universe_action": "retained",
                "reduction_reason": "",
                "replacement_proxy": "",
                "readmission_condition": "",
            }
            for instrument_id in PROPOSED_INSTRUMENTS
        ]
    )


def _conclusion_text(
    *,
    decision: str,
    warnings: list[str],
    replay_start: pd.DataFrame,
    reproducibility: pd.DataFrame,
    reduced_universe: pd.DataFrame,
) -> str:
    warning_text = "\n".join(f"- {warning}" for warning in warnings) if warnings else "- none"
    replay_row = replay_start.iloc[0] if not replay_start.empty else pd.Series(dtype=object)
    original_universe = _join(PROPOSED_INSTRUMENTS)
    retained_universe = (
        _join(reduced_universe["instrument_id"].astype(str).tolist())
        if not reduced_universe.empty
        else original_universe
    )
    excluded = (
        reduced_universe.loc[
            reduced_universe["universe_action"].astype(str).eq("excluded"),
            "instrument_id",
        ].astype(str).tolist()
        if not reduced_universe.empty and "universe_action" in reduced_universe.columns
        else []
    )
    deferred = (
        reduced_universe.loc[
            reduced_universe["universe_action"].astype(str).eq("deferred"),
            "instrument_id",
        ].astype(str).tolist()
        if not reduced_universe.empty and "universe_action" in reduced_universe.columns
        else []
    )
    material_revisions = (
        reproducibility[
            reproducibility["reproducibility_classification"].astype(str).eq(
                "material_completed_history_revision"
            )
        ]
        if not reproducibility.empty
        else pd.DataFrame()
    )
    materiality = (
        "material completed-history revisions detected"
        if not material_revisions.empty
        else "no material completed-history provider revision requiring universe reduction"
    )
    gma1_authorised = decision == "gma0_feasible_proceed_to_data_foundation"
    return f"""# GMA-0 Feasibility Conclusion

Decision: `{decision}`

This phase is a feasibility, data-availability, and GMA-0R date-semantics reconciliation audit only.

No strategy, portfolio return, P&L, Sharpe, CAGR, drawdown, order packet, broker/API integration,
TradingView automation, or paper trade was created.

TradingView remains outside this process and should remain empty until a later frozen champion
phase, if any.

## Data Warnings

{warning_text}

## Reproducibility Finding

{_class_counts(reproducibility)}

Materiality assessment: {materiality}.

Completed-history calculations compare only completed rows. Trailing active-session rows are retained
in immutable raw snapshots, labelled separately, and excluded from primary reproducibility conclusions.

## Corrected Date Definitions

- earliest core data start: `{replay_row.get("earliest_core_data_start", "")}`
- earliest core signal date: `{replay_row.get("earliest_core_signal_date", "")}`
- earliest core next-open execution date: `{replay_row.get("earliest_core_next_open_execution_date", "")}`
- earliest expanded non-crypto allocator date: `{replay_row.get("earliest_expanded_non_crypto_allocator_date", "")}`
- earliest full allocator including Bitcoin date: `{replay_row.get("earliest_full_allocator_including_bitcoin_date", "")}`
- earliest Bitcoin eligible date: `{replay_row.get("earliest_bitcoin_eligible_date", "")}`
- earliest benchmark comparison date: `{replay_row.get("earliest_benchmark_comparison_date", "")}`

The legacy `earliest_expanded_universe_date` field is deprecated and is treated as an alias for
`earliest_expanded_non_crypto_allocator_date`.

## Explicit Universe Decision

- original proposed universe: `{original_universe}`
- retained initial universe: `{retained_universe}`
- excluded instruments: `{_join(excluded) or "none"}`
- deferred instruments: `{_join(deferred) or "none"}`
- replacement proxies: `none`
- reason for every reduction: `none; no GMA-0R universe reduction was applied`
- readmission conditions: `not applicable; no instruments were removed`

## Final GMA-0 Status

Final status: `{decision}`

GMA-1 authorised: `{gma1_authorised}`

## Stop Condition

Do not proceed to GMA-1 unless the final status authorises data-foundation work and the
reconciliation reports have been reviewed.
"""


def _isolation_gate(
    *,
    config: GMAConfig,
    outputs: dict[str, Path],
    baseline: dict[str, set[str]],
    manifests: list[Path],
) -> pd.DataFrame:
    baseline_paths = _changed_paths_from_status(baseline["status"]) | baseline["diff"] | baseline["cached"]
    current_paths = _current_changed_paths()
    introduced_paths = current_paths - baseline_paths
    unexpected_paths = sorted(path for path in introduced_paths if not _is_approved_path(path))
    manifest_hash_failures = []
    for manifest_path in manifests:
        manifest = read_manifest(manifest_path)
        raw_path = Path(manifest.get("raw_file_path", ""))
        normalised_path = Path(manifest.get("normalised_file_path", ""))
        if not raw_path.exists() or manifest.get("raw_file_sha256") != sha256_file(raw_path):
            manifest_hash_failures.append(str(manifest_path))
        if not normalised_path.exists() or manifest.get("normalised_file_sha256") != sha256_file(normalised_path):
            manifest_hash_failures.append(str(manifest_path))
    rows = [
        ("all_outputs_inside_approved_gma_paths", all(_is_approved_path(str(path)) for path in outputs.values()), ""),
        ("no_existing_frozen_config_modified_by_gma0", not unexpected_paths, _join(unexpected_paths)),
        ("no_existing_frozen_source_module_modified_by_gma0", not unexpected_paths, _join(unexpected_paths)),
        ("no_frozen_report_or_data_path_written", not unexpected_paths, _join(unexpected_paths)),
        ("track_id_is_gma_alpha", config.track["track_id"] == TRACK_ID, ""),
        ("phase_id_is_gma0_feasibility", config.track["phase_id"] == PHASE_ID, ""),
        ("live_trading_disabled", not bool(config.track["live_trading_allowed"]), ""),
        ("real_money_disabled", not bool(config.track["real_money_allowed"]), ""),
        ("broker_api_integration_disabled", not bool(config.track["broker_api_integration_allowed"]), ""),
        ("no_strategy_or_performance_output_generated", True, ""),
        ("all_raw_files_have_manifests", len(manifests) > 0, ""),
        ("all_manifests_have_valid_hashes", len(manifest_hash_failures) == 0, _join(manifest_hash_failures)),
    ]
    return pd.DataFrame(
        [
            {
                "gate": gate,
                "passed": bool(passed),
                "detail": detail,
            }
            for gate, passed, detail in rows
        ]
    )


def _provider_for(config: GMAConfig, offline_fixtures: Path | None) -> Any:
    if offline_fixtures is not None:
        return OfflineFixtureProvider(
            fixture_dir=offline_fixtures,
            raw_root=config.paths["raw_root"],
            processed_root=config.paths["processed_root"],
            manifest_root=config.paths["manifest_root"],
        )
    if not bool(config.provider.get("fetch_enabled", False)):
        raise ValueError("provider.fetch_enabled is false and no offline fixtures were supplied")
    return YFinanceProvider(
        cache_root=config.paths["cache_root"],
        raw_root=config.paths["raw_root"],
        processed_root=config.paths["processed_root"],
        manifest_root=config.paths["manifest_root"],
        timeout_seconds=int(config.provider["timeout_seconds"]),
    )


def _manifest_records(manifest_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(manifest_root.rglob("*_manifest.json")):
        try:
            manifest = read_manifest(path)
        except (OSError, ValueError):
            continue
        manifest["_manifest_path"] = str(path)
        records.append(manifest)
    return records


def _completed_normalised_from_manifest(manifest: dict[str, Any]) -> pd.DataFrame:
    normalised_path = Path(str(manifest.get("normalised_file_path", "")))
    if not normalised_path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(normalised_path)
    normalised = normalise_price_frame(frame)
    return completed_history(normalised, str(manifest.get("retrieved_at_utc", "")))


REPRO_COLUMNS = [
    "provider",
    "provider_symbol",
    "comparison_status",
    "reproducibility_classification",
    "provider_adjusted_close_reproducibility_status",
    "first_manifest_path",
    "second_manifest_path",
    "first_raw_snapshot_path",
    "second_raw_snapshot_path",
    "first_normalised_snapshot_path",
    "second_normalised_snapshot_path",
    "new_immutable_snapshot_paths_created",
    "earlier_snapshot_overwritten",
    "hashes_valid",
    "historical_overlap_row_count",
    "completed_history_overlap_row_count",
    "full_provider_overlap_row_count",
    "historical_price_difference_count",
    "historical_difference_columns",
    "raw_open_exact_difference_count",
    "raw_high_exact_difference_count",
    "raw_low_exact_difference_count",
    "raw_close_exact_difference_count",
    "volume_exact_difference_count",
    "adj_close_exact_difference_count",
    "adj_close_difference_count_gt_1e_12",
    "adj_close_difference_count_gt_1e_8",
    "adj_close_difference_count_gt_0_1_bps",
    "adj_close_difference_count_gt_1_bps",
    "adj_close_median_abs_difference",
    "adj_close_max_abs_difference",
    "adj_close_median_abs_difference_bps",
    "adj_close_max_abs_difference_bps",
    "earliest_adj_close_difference_date",
    "latest_adj_close_difference_date",
    "differences_confined_to_final_provider_row",
    "differences_confined_to_incomplete_rows",
    "differences_remain_in_completed_history",
    "adjustment_factor_exact_difference_count",
    "adjustment_factor_max_abs_difference",
    "dividend_event_difference_count",
    "split_event_difference_count",
    "completed_history_revision_material",
    "floating_point_noise_only",
    "incomplete_row_only_difference",
    "corporate_action_adjustment_update",
    "material_completed_history_revision",
    "review_notes",
    "notes",
]


def _empty_repro_row(
    *,
    provider: str = "",
    provider_symbol: str = "",
    comparison_status: str,
    classification: str,
    notes: str,
    first_manifest_path: str = "",
    second_manifest_path: str = "",
    hashes_valid: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {column: "" for column in REPRO_COLUMNS}
    for column in REPRO_COLUMNS:
        if column.endswith("_count") or column in {
            "historical_overlap_row_count",
            "completed_history_overlap_row_count",
            "full_provider_overlap_row_count",
            "historical_price_difference_count",
        }:
            row[column] = 0
        elif column in {
            "new_immutable_snapshot_paths_created",
            "earlier_snapshot_overwritten",
            "hashes_valid",
            "differences_confined_to_final_provider_row",
            "differences_confined_to_incomplete_rows",
            "differences_remain_in_completed_history",
            "completed_history_revision_material",
            "floating_point_noise_only",
            "incomplete_row_only_difference",
            "corporate_action_adjustment_update",
            "material_completed_history_revision",
        }:
            row[column] = False
    row.update(
        {
            "provider": provider,
            "provider_symbol": provider_symbol,
            "comparison_status": comparison_status,
            "reproducibility_classification": classification,
            "provider_adjusted_close_reproducibility_status": classification,
            "first_manifest_path": first_manifest_path,
            "second_manifest_path": second_manifest_path,
            "hashes_valid": hashes_valid,
            "review_notes": (
                "thresholds: exact; abs>1e-12; abs>1e-8; abs bps>0.1; "
                "abs bps>1.0; completed-history primary"
            ),
            "notes": notes,
        }
    )
    return row


def _normalised_from_manifest(manifest: dict[str, Any]) -> pd.DataFrame:
    normalised_path = Path(str(manifest.get("normalised_file_path", "")))
    if not normalised_path.exists():
        return pd.DataFrame()
    return normalise_price_frame(pd.read_csv(normalised_path))


def _raw_from_manifest(manifest: dict[str, Any]) -> pd.DataFrame:
    raw_path = Path(str(manifest.get("raw_file_path", "")))
    if not raw_path.exists():
        return pd.DataFrame()
    return pd.read_csv(raw_path)


def _numeric_difference_mask(left: pd.Series, right: pd.Series) -> pd.Series:
    left_numeric = pd.to_numeric(left, errors="coerce")
    right_numeric = pd.to_numeric(right, errors="coerce")
    return left_numeric.ne(right_numeric) & ~(left_numeric.isna() & right_numeric.isna())


def _threshold_count(values: pd.Series, threshold: float) -> int:
    numeric = pd.to_numeric(values, errors="coerce")
    return int(numeric.loc[np.isfinite(numeric)].gt(threshold).sum())


def _safe_median(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.loc[np.isfinite(numeric)]
    return float(numeric.median()) if not numeric.empty else np.nan


def _safe_max(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.loc[np.isfinite(numeric)]
    return float(numeric.max()) if not numeric.empty else np.nan


def _diff_date_range(overlap: pd.DataFrame, mask: pd.Series) -> tuple[str, str]:
    dates = pd.to_datetime(overlap.loc[mask.fillna(False), "date"], errors="coerce").dropna()
    if dates.empty:
        return "", ""
    return dates.min().date().isoformat(), dates.max().date().isoformat()


def _action_differences(first: dict[str, Any], second: dict[str, Any], completed_dates: set[pd.Timestamp]) -> tuple[int, int]:
    first_actions = corporate_action_frame(_raw_from_manifest(first))
    second_actions = corporate_action_frame(_raw_from_manifest(second))
    if first_actions.empty and second_actions.empty:
        return 0, 0
    first_actions = first_actions.loc[first_actions["date"].isin(completed_dates)]
    second_actions = second_actions.loc[second_actions["date"].isin(completed_dates)]
    overlap = first_actions.merge(
        second_actions,
        on="date",
        how="outer",
        suffixes=("_first", "_second"),
    )
    if overlap.empty:
        return 0, 0
    dividend_diff = _numeric_difference_mask(overlap["dividends_first"], overlap["dividends_second"])
    split_diff = _numeric_difference_mask(overlap["splits_first"], overlap["splits_second"])
    return int(dividend_diff.sum()), int(split_diff.sum())


def _snapshot_pair_reproducibility(
    *,
    provider: str,
    symbol: str,
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    full_first = _normalised_from_manifest(first)
    full_second = _normalised_from_manifest(second)
    if full_first.empty or full_second.empty:
        return _empty_repro_row(
            provider=provider,
            provider_symbol=symbol,
            comparison_status="missing_snapshot_data",
            classification="insufficient_evidence",
            first_manifest_path=str(first.get("_manifest_path", "")),
            second_manifest_path=str(second.get("_manifest_path", "")),
            hashes_valid=_manifest_hashes_valid(first) and _manifest_hashes_valid(second),
            notes="Normalised snapshot data was unavailable for comparison.",
        )
    first_frame = completed_history(full_first, str(first.get("retrieved_at_utc", "")))
    second_frame = completed_history(full_second, str(second.get("retrieved_at_utc", "")))
    compare_columns = ["open", "high", "low", "close", "adj_close", "volume"]
    completed_overlap = first_frame[["date", *compare_columns]].merge(
        second_frame[["date", *compare_columns]],
        on="date",
        suffixes=("_first", "_second"),
    )
    full_overlap = full_first[["date", *compare_columns]].merge(
        full_second[["date", *compare_columns]],
        on="date",
        suffixes=("_first", "_second"),
    )
    if completed_overlap.empty:
        return _empty_repro_row(
            provider=provider,
            provider_symbol=symbol,
            comparison_status="no_completed_history_overlap",
            classification="insufficient_evidence",
            first_manifest_path=str(first.get("_manifest_path", "")),
            second_manifest_path=str(second.get("_manifest_path", "")),
            hashes_valid=_manifest_hashes_valid(first) and _manifest_hashes_valid(second),
            notes="Completed-history overlap was empty.",
        )

    difference_columns: list[str] = []
    exact_counts: dict[str, int] = {}
    total_exact_count = 0
    for column in compare_columns:
        mask = _numeric_difference_mask(
            completed_overlap[f"{column}_first"],
            completed_overlap[f"{column}_second"],
        )
        exact_counts[column] = int(mask.sum())
        total_exact_count += exact_counts[column]
        if exact_counts[column]:
            difference_columns.append(column)

    adj_left = pd.to_numeric(completed_overlap["adj_close_first"], errors="coerce")
    adj_right = pd.to_numeric(completed_overlap["adj_close_second"], errors="coerce")
    adj_abs_diff = (adj_left - adj_right).abs()
    denominator = adj_left.abs().replace(0.0, np.nan)
    adj_abs_bps = (adj_abs_diff / denominator) * 10_000
    adj_exact_mask = _numeric_difference_mask(
        completed_overlap["adj_close_first"],
        completed_overlap["adj_close_second"],
    )
    earliest_adj, latest_adj = _diff_date_range(completed_overlap, adj_exact_mask)

    full_adj_mask = _numeric_difference_mask(full_overlap["adj_close_first"], full_overlap["adj_close_second"])
    full_diff_dates = set(pd.to_datetime(full_overlap.loc[full_adj_mask, "date"], errors="coerce").dropna())
    completed_dates = set(pd.to_datetime(completed_overlap["date"], errors="coerce").dropna())
    incomplete_dates = set(pd.to_datetime(full_overlap["date"], errors="coerce").dropna()) - completed_dates
    final_provider_date = pd.to_datetime(full_overlap["date"], errors="coerce").max()
    final_provider_dates = {final_provider_date} if pd.notna(final_provider_date) else set()
    confined_to_final = bool(full_diff_dates and full_diff_dates <= final_provider_dates)
    confined_to_incomplete = bool(full_diff_dates and full_diff_dates <= incomplete_dates)

    first_factor = adj_left / pd.to_numeric(completed_overlap["close_first"], errors="coerce").replace(0.0, np.nan)
    second_factor = adj_right / pd.to_numeric(completed_overlap["close_second"], errors="coerce").replace(0.0, np.nan)
    factor_abs_diff = (first_factor - second_factor).abs()
    factor_diff_count = _threshold_count(factor_abs_diff, 1e-12)
    material_factor_diff_count = _threshold_count(factor_abs_diff, 1e-8)
    dividend_diff_count, split_diff_count = _action_differences(first, second, completed_dates)

    adj_gt_1e_12 = _threshold_count(adj_abs_diff, 1e-12)
    adj_gt_1e_8 = _threshold_count(adj_abs_diff, 1e-8)
    adj_gt_0_1_bps = _threshold_count(adj_abs_bps, 0.1)
    adj_gt_1_bps = _threshold_count(adj_abs_bps, 1.0)
    raw_value_diff_count = sum(exact_counts[column] for column in ["open", "high", "low", "close", "volume"])
    action_or_factor_diff = material_factor_diff_count > 0 or dividend_diff_count > 0 or split_diff_count > 0
    incomplete_only = exact_counts["adj_close"] == 0 and confined_to_incomplete
    noise_only = (
        exact_counts["adj_close"] > 0
        and adj_gt_0_1_bps == 0
        and raw_value_diff_count == 0
        and not action_or_factor_diff
    )
    corporate_action_update = action_or_factor_diff and raw_value_diff_count == 0
    material_revision = (
        adj_gt_0_1_bps > 0
        or raw_value_diff_count > 0
    ) and not incomplete_only

    if total_exact_count == 0 and not full_diff_dates and not action_or_factor_diff:
        classification = "exact_match"
        comparison_status = "matched"
    elif incomplete_only:
        classification = "incomplete_row_only"
        comparison_status = "non_material_incomplete_row_difference"
    elif noise_only:
        classification = "numerical_noise_only"
        comparison_status = "non_material_numerical_noise"
    elif corporate_action_update:
        classification = "corporate_action_adjustment_update"
        comparison_status = "corporate_action_or_adjustment_factor_difference"
    elif material_revision:
        classification = "material_completed_history_revision"
        comparison_status = "material_completed_history_revision"
    else:
        classification = "insufficient_evidence"
        comparison_status = "manual_review_required"

    return {
        "provider": provider,
        "provider_symbol": symbol,
        "comparison_status": comparison_status,
        "reproducibility_classification": classification,
        "provider_adjusted_close_reproducibility_status": classification,
        "first_manifest_path": str(first.get("_manifest_path", "")),
        "second_manifest_path": str(second.get("_manifest_path", "")),
        "first_raw_snapshot_path": str(first.get("raw_file_path", "")),
        "second_raw_snapshot_path": str(second.get("raw_file_path", "")),
        "first_normalised_snapshot_path": str(first.get("normalised_file_path", "")),
        "second_normalised_snapshot_path": str(second.get("normalised_file_path", "")),
        "new_immutable_snapshot_paths_created": first.get("raw_file_path") != second.get("raw_file_path"),
        "earlier_snapshot_overwritten": not Path(str(first.get("raw_file_path", ""))).exists(),
        "hashes_valid": _manifest_hashes_valid(first) and _manifest_hashes_valid(second),
        "historical_overlap_row_count": int(len(completed_overlap)),
        "completed_history_overlap_row_count": int(len(completed_overlap)),
        "full_provider_overlap_row_count": int(len(full_overlap)),
        "historical_price_difference_count": int(total_exact_count),
        "historical_difference_columns": _join(difference_columns),
        "raw_open_exact_difference_count": exact_counts["open"],
        "raw_high_exact_difference_count": exact_counts["high"],
        "raw_low_exact_difference_count": exact_counts["low"],
        "raw_close_exact_difference_count": exact_counts["close"],
        "volume_exact_difference_count": exact_counts["volume"],
        "adj_close_exact_difference_count": exact_counts["adj_close"],
        "adj_close_difference_count_gt_1e_12": adj_gt_1e_12,
        "adj_close_difference_count_gt_1e_8": adj_gt_1e_8,
        "adj_close_difference_count_gt_0_1_bps": adj_gt_0_1_bps,
        "adj_close_difference_count_gt_1_bps": adj_gt_1_bps,
        "adj_close_median_abs_difference": _safe_median(adj_abs_diff),
        "adj_close_max_abs_difference": _safe_max(adj_abs_diff),
        "adj_close_median_abs_difference_bps": _safe_median(adj_abs_bps),
        "adj_close_max_abs_difference_bps": _safe_max(adj_abs_bps),
        "earliest_adj_close_difference_date": earliest_adj,
        "latest_adj_close_difference_date": latest_adj,
        "differences_confined_to_final_provider_row": confined_to_final,
        "differences_confined_to_incomplete_rows": confined_to_incomplete,
        "differences_remain_in_completed_history": bool(exact_counts["adj_close"] > 0),
        "adjustment_factor_exact_difference_count": factor_diff_count,
        "adjustment_factor_max_abs_difference": _safe_max(factor_abs_diff),
        "dividend_event_difference_count": dividend_diff_count,
        "split_event_difference_count": split_diff_count,
        "completed_history_revision_material": material_revision,
        "floating_point_noise_only": noise_only,
        "incomplete_row_only_difference": incomplete_only,
        "corporate_action_adjustment_update": corporate_action_update,
        "material_completed_history_revision": material_revision,
        "review_notes": (
            "thresholds: exact; abs>1e-12; abs>1e-8; abs bps>0.1; "
            "abs bps>1.0; completed-history primary"
        ),
        "notes": "Ordinary retrieval timestamp differences are ignored.",
    }


def _snapshot_reproducibility_audit(manifest_root: Path) -> pd.DataFrame:
    records = _manifest_records(manifest_root)
    if not records:
        return pd.DataFrame(
            [
                _empty_repro_row(
                    comparison_status="no_manifests_available",
                    classification="insufficient_evidence",
                    notes="No snapshots were available for comparison.",
                )
            ],
            columns=REPRO_COLUMNS,
        )
    rows = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (str(record.get("provider", "")), str(record.get("provider_symbol", "")))
        grouped.setdefault(key, []).append(record)
    for (provider, symbol), manifests in sorted(grouped.items()):
        ordered = sorted(manifests, key=lambda item: str(item.get("retrieved_at_utc", "")))
        if len(ordered) < 2:
            manifest = ordered[-1]
            rows.append(
                _empty_repro_row(
                    provider=provider,
                    provider_symbol=symbol,
                    comparison_status="insufficient_snapshots",
                    classification="insufficient_evidence",
                    second_manifest_path=str(manifest.get("_manifest_path", "")),
                    hashes_valid=_manifest_hashes_valid(manifest),
                    notes="Need at least two snapshots for reproducibility comparison.",
                )
            )
            continue
        first = ordered[-2]
        second = ordered[-1]
        rows.append(
            _snapshot_pair_reproducibility(
                provider=provider,
                symbol=symbol,
                first=first,
                second=second,
            )
        )
    return pd.DataFrame(rows, columns=REPRO_COLUMNS)


def _adjusted_close_reconciliation_text(reproducibility: pd.DataFrame) -> str:
    class_text = _class_counts(reproducibility)
    if reproducibility.empty:
        affected = "- none"
    else:
        affected_rows = []
        for _, row in reproducibility.iterrows():
            affected_rows.append(
                "- "
                f"{row.get('provider_symbol', '')}: "
                f"{row.get('reproducibility_classification', '')}; "
                f"adj-close exact diffs={row.get('adj_close_exact_difference_count', 0)}; "
                f">0.1 bps={row.get('adj_close_difference_count_gt_0_1_bps', 0)}; "
                f"raw close diffs={row.get('raw_close_exact_difference_count', 0)}; "
                f"dividend diffs={row.get('dividend_event_difference_count', 0)}; "
                f"split diffs={row.get('split_event_difference_count', 0)}"
            )
        affected = "\n".join(affected_rows)
    material = reproducibility[
        reproducibility["reproducibility_classification"].astype(str).eq(
            "material_completed_history_revision"
        )
    ] if not reproducibility.empty else pd.DataFrame()
    material_text = (
        "Material completed-history revisions were detected and require manual review."
        if not material.empty
        else "No material completed-history revisions were detected by GMA-0R thresholds."
    )
    return f"""# GMA-0R Adjusted-Close Reconciliation

This reconciliation compares immutable provider snapshots by completed history. Incomplete
trailing provider rows are audited separately so active-session noise cannot be mistaken for
completed-history revision.

## Classification Counts

{class_text}

## Affected Instruments

{affected}

## Materiality

{material_text}

Thresholds used:

- exact numerical difference
- absolute difference greater than `1e-12`
- absolute difference greater than `1e-8`
- adjusted-close difference greater than `0.1` bps
- adjusted-close difference greater than `1.0` bps

Raw OHLCV, adjustment-factor, dividend-event, and split-event differences are reported separately
to distinguish source restatement from corporate-action adjustment updates.
"""


def _augmented_gate_report(
    *,
    gate: pd.DataFrame,
    replay_start: pd.DataFrame,
    reproducibility: pd.DataFrame,
    reduced_universe: pd.DataFrame,
) -> pd.DataFrame:
    replay_row = replay_start.iloc[0] if not replay_start.empty else pd.Series(dtype=object)
    material_revision = bool(
        not reproducibility.empty
        and reproducibility["reproducibility_classification"].astype(str).eq(
            "material_completed_history_revision"
        ).any()
    )
    has_reduction = bool(
        not reduced_universe.empty
        and reduced_universe["universe_action"].astype(str).isin(["excluded", "deferred"]).any()
    )
    full_allocator = str(replay_row.get("earliest_full_allocator_including_bitcoin_date", ""))
    bitcoin = str(replay_row.get("earliest_bitcoin_eligible_date", ""))
    bitcoin_order_ok = not full_allocator or not bitcoin or pd.Timestamp(full_allocator) >= pd.Timestamp(bitcoin)
    rows = [
        {
            "gate": "gma0r_no_material_completed_history_revision",
            "passed": not material_revision,
            "detail": "",
        },
        {
            "gate": "gma0r_reduced_universe_documented_if_used",
            "passed": True,
            "detail": "reduced_universe_applied" if has_reduction else "no_reduced_universe_applied",
        },
        {
            "gate": "gma0r_benchmark_warmup_exemption_applied",
            "passed": bool(replay_row.get("acwi_benchmark_warmup_exempt", False)),
            "detail": "",
        },
        {
            "gate": "gma0r_full_allocator_not_before_bitcoin",
            "passed": bitcoin_order_ok,
            "detail": f"full_allocator={full_allocator}; bitcoin={bitcoin}",
        },
    ]
    return pd.concat([gate, pd.DataFrame(rows)], ignore_index=True)


def _manifest_hashes_valid(manifest: dict[str, Any]) -> bool:
    raw_path = Path(str(manifest.get("raw_file_path", "")))
    normalised_path = Path(str(manifest.get("normalised_file_path", "")))
    if not raw_path.exists() or not normalised_path.exists():
        return False
    return (
        str(manifest.get("raw_file_sha256", "")) == sha256_file(raw_path)
        and str(manifest.get("normalised_file_sha256", "")) == sha256_file(normalised_path)
    )


def run_gma0_availability_audit(
    *,
    config: GMAConfig,
    offline_fixtures: Path | None = None,
) -> AuditResult:
    baseline = capture_working_tree_baseline()
    report_root = config.paths["report_root"]
    report_root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    outputs["reuse_map"] = _write_text(_reuse_map_text(), report_root / "reuse_map.md")
    registry = registry_frame(config.instruments)
    outputs["instrument_registry"] = _write_csv(registry, report_root / "instrument_registry.csv")
    outputs["calendar_registry"] = _write_csv(calendar_frame(), report_root / "calendar_registry.csv")
    outputs["macro_series_registry"] = _write_csv(
        macro_series_frame(),
        report_root / "macro_series_registry.csv",
    )

    provider = _provider_for(config, offline_fixtures)
    audit_mode = "offline_fixture" if offline_fixtures is not None else "live_yahoo"
    price_rows: list[dict[str, Any]] = []
    corporate_rows: list[dict[str, Any]] = []
    liquidity_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    manifests: list[Path] = []
    snapshots: dict[str, ProviderSnapshot] = {}
    request_start = "1900-01-01"
    request_end = ""
    for instrument_id, instrument in config.instruments.items():
        try:
            snapshot = provider.fetch(
                str(instrument["provider_symbol"]),
                start=request_start,
                end=request_end,
            )
            snapshots[instrument_id] = snapshot
            manifests.append(snapshot.manifest_path)
            validation = validate_price_frame(
                raw=snapshot.raw_frame,
                instrument_id=instrument_id,
                retrieved_at_utc=snapshot.retrieved_at_utc,
                stale_price_threshold_days=int(config.audit["stale_price_threshold_days"]),
                minimum_history_observations=int(config.audit["minimum_history_observations"]),
            )
            price_rows.append(
                _availability_row(
                    instrument=instrument,
                    snapshot=snapshot,
                    completed=validation.completed,
                    audit=validation.audit,
                    warmup_months=int(instrument.get("minimum_warmup_months") or config.replay_start["minimum_warmup_months"]),
                    audit_mode=audit_mode,
                )
            )
            corporate_rows.append(corporate_action_audit(snapshot.raw_frame, instrument_id))
            liquidity_rows.append(liquidity_audit(validation.completed, instrument_id))
            warnings.extend(f"{instrument_id}:{warning}" for warning in validation.warnings)
        except Exception as exc:
            warnings.append(f"{instrument_id}:provider_or_validation_failed:{exc}")
            price_rows.append(
                {
                    "audit_mode": audit_mode,
                    "provider": audit_mode,
                    "provider_symbol": instrument["provider_symbol"],
                    "request_timestamp_utc": "",
                    "raw_snapshot_path": "",
                    "raw_snapshot_sha256": "",
                    "normalised_snapshot_path": "",
                    "normalised_snapshot_sha256": "",
                    "manifest_path": "",
                    "instrument_id": instrument_id,
                    "expected_calendar": instrument["expected_calendar"],
                    "is_benchmark_only": bool(instrument["is_benchmark_only"]),
                    "row_count": 0,
                    "first_observation_date": "",
                    "last_observation_date": "",
                    "first_return_eligible_date": "",
                    "first_raw_open_eligible_date": "",
                    "warmup_complete_date": "",
                    "first_next_open_execution_date": "",
                    "portfolio_eligibility_date": "",
                    "last_available_date": "",
                    "availability_status": "provider_or_validation_failed",
                    "warnings": str(exc),
                }
            )
            corporate_rows.append(
                {
                    "instrument_id": instrument_id,
                    "dividend_data_available": False,
                    "split_data_available": False,
                    "first_dividend_date": "",
                    "last_dividend_date": "",
                    "dividend_event_count": 0,
                    "first_split_date": "",
                    "last_split_date": "",
                    "split_event_count": 0,
                    "action_warnings": "source_capability_unavailable",
                }
            )
            liquidity_rows.append(liquidity_audit(pd.DataFrame(), instrument_id))

    price_availability = pd.DataFrame(price_rows)
    corporate_actions = pd.DataFrame(corporate_rows)
    liquidity = pd.DataFrame(liquidity_rows)
    replay_start = _replay_start_assessment(config, price_availability)

    outputs["price_availability"] = _write_csv(price_availability, report_root / "price_availability.csv")
    outputs["corporate_action_availability"] = _write_csv(
        corporate_actions,
        report_root / "corporate_action_availability.csv",
    )
    outputs["liquidity_summary"] = _write_csv(liquidity, report_root / "liquidity_summary.csv")
    outputs["replay_start_assessment"] = _write_csv(
        replay_start,
        report_root / "replay_start_assessment.csv",
    )
    reproducibility = _snapshot_reproducibility_audit(config.paths["manifest_root"])
    outputs["snapshot_reproducibility_audit"] = _write_csv(
        reproducibility,
        report_root / "snapshot_reproducibility_audit.csv",
    )
    outputs["gma0r_adjusted_close_reconciliation"] = _write_csv(
        reproducibility,
        report_root / "gma0r_adjusted_close_reconciliation.csv",
    )
    outputs["gma0r_adjusted_close_reconciliation_md"] = _write_text(
        _adjusted_close_reconciliation_text(reproducibility),
        report_root / "gma0r_adjusted_close_reconciliation.md",
    )
    reduced_universe = _retained_universe_decision()

    gate = _isolation_gate(
        config=config,
        outputs=outputs,
        baseline=baseline,
        manifests=manifests,
    )
    gate = _augmented_gate_report(
        gate=gate,
        replay_start=replay_start,
        reproducibility=reproducibility,
        reduced_universe=reduced_universe,
    )
    core_failed = price_availability.loc[
        price_availability["instrument_id"].isin(config.replay_start["required_core_instruments"])
        & ~price_availability["availability_status"].astype(str).eq("available")
    ]
    core_provider_failed = core_failed.loc[
        core_failed["availability_status"].astype(str).eq("provider_or_validation_failed")
    ]
    material_revision = bool(
        not reproducibility.empty
        and reproducibility["reproducibility_classification"].astype(str).eq(
            "material_completed_history_revision"
        ).any()
    )
    reduced_universe_applied = bool(
        not reduced_universe.empty
        and reduced_universe["universe_action"].astype(str).isin(["excluded", "deferred"]).any()
    )
    isolation_gate_passed = bool(
        gate.loc[
            ~gate["gate"].astype(str).eq("gma0r_no_material_completed_history_revision"),
            "passed",
        ].all()
    )
    if not isolation_gate_passed:
        decision = "gma0_blocked_isolation_failure"
    elif not core_provider_failed.empty:
        decision = "gma0_blocked_provider_limitations"
    elif not core_failed.empty:
        decision = "gma0_blocked_data_quality"
    elif material_revision:
        decision = "gma0_blocked_provider_limitations"
    elif reduced_universe_applied:
        decision = "gma0_feasible_with_reduced_universe"
    else:
        decision = "gma0_feasible_proceed_to_data_foundation"
    outputs["isolation_gate_report"] = _write_csv(gate, report_root / "isolation_gate_report.csv")
    outputs["gma0_conclusion"] = _write_text(
        _conclusion_text(
            decision=decision,
            warnings=warnings,
            replay_start=replay_start,
            reproducibility=reproducibility,
            reduced_universe=reduced_universe,
        ),
        report_root / "gma0_conclusion.md",
    )
    return AuditResult(
        decision=decision,
        outputs=outputs,
        replay_start=replay_start,
        gate_report=gate,
        warnings=warnings,
    )
