"""GMA-6D frozen cross-universe historical tournament execution.

The wrapper uses the frozen GMA-6B normalised bundle and the shared GMA-4
strategy/replay components. It does not fetch data or create operational paths.
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import pandas as pd

from market_strats.global_multi_asset import gma4_replay_adapter as replay_adapter
from market_strats.global_multi_asset import gma4_strategy_library as strategy_library
from market_strats.global_multi_asset.gma2_replay import normalise_weights
from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    REQUIRED_COST_SCENARIOS,
    load_gma4_tournament_config,
    load_gma4_trial_registry,
    validate_gma4_contract,
)
from market_strats.global_multi_asset.gma6c_tournament_contract import (
    CONTROL_UNIVERSE_VERSION,
    EXPANDED_UNIVERSE,
    EXPANDED_UNIVERSE_VERSION,
    REQUIRED_DBA_FLAG,
    REQUIRED_USO_FLAG,
)

PHASE_ID = "gma6d_cross_universe_tournament_v1"
DEFAULT_CONFIG_PATH = Path(
    "configs/global_multi_asset_alpha/gma6c_cross_universe_tournament_v1.yaml"
)
DEFAULT_OUTPUT_ROOT = Path("reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1")
DEFAULT_NORMALISED_ROOT = Path(
    "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/normalised/yahoo_yfinance"
)
DEFAULT_NORMALISED_HASHES = Path(
    "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/gma6b_normalised_file_hashes_v1.csv"
)
HISTORY_START = "2007-05-30"
HISTORY_END = "2026-05-01"
NETWORK_ACCESS_ATTEMPTED = False
EXECUTION_STATUS = "historical_research_execution_only"
GMA4_REFERENCE_LIMIT = (
    "not_directly_numeric_comparable_to_prior_gma4_run_without_identical_data_snapshot"
)
INTERPRETATION_LIMIT = "primary comparison is within-run core-22 versus expanded-29; highest historical CAGR or Sharpe alone is not a selection rule"
RUN_OUTPUT_FILENAMES = [
    "gma6d_run_manifest_v1.json",
    "gma6d_input_verification_v1.csv",
    "gma6d_input_verification_v1.md",
    "gma6d_tournament_scoreboard_v1.csv",
    "gma6d_tournament_scoreboard_v1.md",
    "gma6d_evaluation_detail_v1.csv",
    "gma6d_cross_universe_comparison_v1.csv",
    "gma6d_cross_universe_comparison_v1.md",
    "gma6d_sample_comparability_audit_v1.csv",
    "gma6d_sample_comparability_audit_v1.md",
    "gma6d_monthly_target_weights_v1.csv",
    "gma6d_uso_methodology_regime_detail_v1.csv",
    "gma6d_execution_provenance_v1.json",
    "gma6d_results_discussion_v1.md",
]
SCOREBOARD_COLUMNS = [
    "run_id",
    "universe_version",
    "trial_id",
    "trial_family",
    "cost_scenario",
    "evaluation_scope",
    "window_id",
    "regime_id",
    "period_start",
    "period_end",
    "effective_period_start",
    "session_count",
    "net_cagr",
    "annualised_volatility",
    "sharpe",
    "sortino",
    "maximum_drawdown",
    "cumulative_net_return",
    "annualised_turnover",
    "cost_drag",
    "maximum_hhi",
    "methodology_regime_flag",
    "measurement_status",
    "source_run_id",
]
COMPARISON_METRICS = [
    "net_cagr",
    "annualised_volatility",
    "sharpe",
    "maximum_drawdown",
    "cumulative_net_return",
    "annualised_turnover",
    "cost_drag",
    "maximum_hhi",
]
COST_BPS = {
    "baseline_1bps": 1.0,
    "stressed_10bps": 10.0,
    "stressed_25bps": 25.0,
    "severe_50bps": 50.0,
}
REQUIRED_REPORT_LANGUAGE = [
    "This is observed development evidence and not a pristine final holdout.",
    "No execution or promotion decision is produced.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "The GMA-4 and GMA-5 V1 records remain unchanged.",
    "USO and DBA are treated as historical traded ETP return exposures, not spot commodity return series.",
]


class GMA6DExecutionError(ValueError):
    """Fail-closed GMA-6D execution error."""


@dataclass(frozen=True)
class ArmSpec:
    universe_version: str
    symbols: list[str]
    methodology_regime_flag: str


@dataclass(frozen=True)
class GMA6DResult:
    run_id: str
    run_dir: Path
    manifest: dict[str, Any]
    scoreboard: pd.DataFrame
    comparison: pd.DataFrame
    sample_audit: pd.DataFrame
    uso_detail: pd.DataFrame


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _structured_hash(value: Any) -> str:
    return _sha256_text(_stable_json(value))


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6DExecutionError(f"{path} must contain a JSON object")
    return raw


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise GMA6DExecutionError(f"{path} must contain rows")
    return rows


def _new_run_id(executed_at_utc: datetime | None = None) -> str:
    stamp = (executed_at_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"gma6d_{stamp.strftime('%Y%m%dT%H%M%SZ')}"


def _make_run_dir(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / "runs" / run_id
    if not run_dir.exists():
        run_dir.mkdir(parents=True)
        return run_dir
    for idx in range(1, 100):
        candidate = output_root / "runs" / f"{run_id}_{idx:02d}"
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
    raise GMA6DExecutionError(f"unable to create unique run directory for {run_id}")


def _read_gma6c_paths(config_path: Path) -> dict[str, Path]:
    import yaml

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6DExecutionError("GMA-6C config must be a mapping")
    source_inputs = raw.get("source_inputs") or {}
    required = [
        "gma6b_data_bundle_manifest",
        "gma6b_data_bundle_verdict",
        "gma6b_commodity_pool_overlay",
        "gma6b2_continuity_overlay",
        "gma4_tournament_config",
        "gma4_trial_registry",
    ]
    paths = {key: Path(str(source_inputs.get(key))) for key in required}
    missing = [key for key, path in paths.items() if not str(path) or not path.exists()]
    if missing:
        raise GMA6DExecutionError(f"GMA-6C config missing readable source inputs: {missing}")
    paths["gma6c_lock"] = Path(
        "reports/global_multi_asset_alpha/gma6c_cross_universe_tournament_lock_v1.json"
    )
    return paths


def _derive_b1_status(rows: list[dict[str, str]]) -> str:
    by_ticker = {row.get("ticker", ""): row for row in rows}
    if set(by_ticker) != {"USO", "DBA"}:
        raise GMA6DExecutionError("GMA-6B structure overlay must contain exactly USO and DBA")
    for ticker, row in by_ticker.items():
        if (
            row.get("later_research_execution_eligibility")
            != "eligible_for_later_research_execution"
        ):
            raise GMA6DExecutionError(f"{ticker} B.1 eligibility is not eligible")
        if row.get("structure_review_status") != "documented_for_later_research_execution":
            raise GMA6DExecutionError(f"{ticker} B.1 structure review is not documented")
    return "eligible_for_later_gma6_research_execution"


def _derive_b2_status(rows: list[dict[str, str]]) -> dict[str, str]:
    by_ticker = {row.get("ticker", ""): row for row in rows}
    if set(by_ticker) != {"USO", "DBA"}:
        raise GMA6DExecutionError("GMA-6B.2 continuity overlay must contain exactly USO and DBA")
    uso = by_ticker["USO"]
    dba = by_ticker["DBA"]
    if uso.get("required_later_regime_flag") != REQUIRED_USO_FLAG:
        raise GMA6DExecutionError("missing USO methodology-regime flag")
    if (
        uso.get("later_research_execution_overlay_eligibility")
        != "eligible_only_with_documented_methodology_regime_flags"
    ):
        raise GMA6DExecutionError("USO continuity overlay is not regime-flag eligible")
    if dba.get("required_later_regime_flag") != REQUIRED_DBA_FLAG:
        raise GMA6DExecutionError("DBA methodology-regime flag must remain not_required")
    return {"USO": REQUIRED_USO_FLAG, "DBA": REQUIRED_DBA_FLAG}


def _verify_normalised_bundle(
    *,
    manifest: dict[str, Any],
    hash_csv_path: Path,
    normalised_root: Path,
    required_symbols: list[str],
) -> tuple[dict[str, Path], list[dict[str, str]], str]:
    if _sha256_file(hash_csv_path) != manifest.get("normalised_file_hashes_hash"):
        raise GMA6DExecutionError("normalised file hash manifest mismatch")
    rows = _load_csv_rows(hash_csv_path)
    by_ticker = {row["ticker"]: row["normalised_series_file_hash"] for row in rows}
    if list(by_ticker) != list(manifest.get("requested_tickers") or []):
        raise GMA6DExecutionError(
            "normalised hash manifest ticker order does not match bundle manifest"
        )
    missing = [symbol for symbol in required_symbols if symbol not in by_ticker]
    if missing:
        raise GMA6DExecutionError(f"missing required ticker in normalised hash manifest: {missing}")
    files: dict[str, Path] = {}
    verification_rows: list[dict[str, str]] = []
    for symbol in required_symbols:
        matches = sorted((normalised_root / symbol).glob("*_normalised.csv"))
        if len(matches) != 1:
            raise GMA6DExecutionError(f"{symbol} must have exactly one normalised series file")
        file_hash = _sha256_file(matches[0])
        expected = by_ticker[symbol]
        status = "pass" if file_hash == expected else "fail"
        verification_rows.append(
            {
                "check_name": f"normalised_file_hash_{symbol}",
                "expected": expected,
                "observed": file_hash,
                "status": status,
                "details": str(matches[0]),
            }
        )
        if status != "pass":
            raise GMA6DExecutionError(f"normalised file hash mismatch for {symbol}")
        files[symbol] = matches[0]
    return files, verification_rows, _sha256_file(hash_csv_path)


def verify_inputs(
    *,
    config_path: Path,
    lock_path: Path | None = None,
    normalised_root: Path = DEFAULT_NORMALISED_ROOT,
    normalised_hashes_path: Path = DEFAULT_NORMALISED_HASHES,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Path]]:
    paths = _read_gma6c_paths(config_path)
    if lock_path is not None:
        paths["gma6c_lock"] = lock_path
    lock = _load_json(paths["gma6c_lock"])
    data_manifest = _load_json(paths["gma6b_data_bundle_manifest"])
    data_verdict = _load_json(paths["gma6b_data_bundle_verdict"])
    b1_rows = _load_csv_rows(paths["gma6b_commodity_pool_overlay"])
    b2_rows = _load_csv_rows(paths["gma6b2_continuity_overlay"])
    b1_status = _derive_b1_status(b1_rows)
    b2_flags = _derive_b2_status(b2_rows)
    checks: list[dict[str, str]] = []

    def add_check(name: str, expected: str, observed: str, details: str = "") -> None:
        status = "pass" if expected == observed else "fail"
        checks.append(
            {
                "check_name": name,
                "expected": expected,
                "observed": observed,
                "status": status,
                "details": details,
            }
        )
        if status != "pass":
            raise GMA6DExecutionError(f"input verification failed: {name}")

    add_check(
        "gma6b_universe_status_after_overlay",
        "eligible_for_later_gma6_research_execution",
        b1_status,
    )
    add_check(
        "gma6b2_historical_commodity_etp_continuity_overlay_status",
        "eligible_only_with_documented_methodology_regime_flags",
        b2_rows[0].get("later_research_execution_overlay_eligibility", ""),
        "USO row carries the limiting overlay status; DBA remains not_required.",
    )
    add_check("uso_methodology_regime_flag", REQUIRED_USO_FLAG, b2_flags["USO"])
    add_check("dba_methodology_regime_flag", REQUIRED_DBA_FLAG, b2_flags["DBA"])
    add_check(
        "gma6b_data_bundle_manifest_hash",
        str(lock["gma6b_data_bundle_manifest_hash"]),
        _sha256_file(paths["gma6b_data_bundle_manifest"]),
    )
    add_check(
        "gma6b_commodity_pool_overlay_hash",
        str(lock["gma6b_commodity_pool_overlay_hash"]),
        _sha256_file(paths["gma6b_commodity_pool_overlay"]),
    )
    add_check(
        "gma6b2_continuity_overlay_hash",
        str(lock["gma6b2_continuity_overlay_hash"]),
        _sha256_file(paths["gma6b2_continuity_overlay"]),
    )
    add_check(
        "gma6b_universe_data_contract_verdict_hash",
        str(data_manifest["universe_data_contract_verdict_hash"]),
        _sha256_file(paths["gma6b_data_bundle_verdict"]),
    )
    if data_verdict.get("blocked_or_pending_tickers") != ["USO", "DBA"]:
        raise GMA6DExecutionError("pre-overlay data verdict must be blocked only by USO/DBA")
    files, file_checks, normalised_bundle_hash = _verify_normalised_bundle(
        manifest=data_manifest,
        hash_csv_path=normalised_hashes_path,
        normalised_root=normalised_root,
        required_symbols=EXPANDED_UNIVERSE,
    )
    checks.extend(file_checks)
    metadata = {
        "lock": lock,
        "gma6c_lock_hash": _sha256_file(paths["gma6c_lock"]),
        "data_manifest": data_manifest,
        "normalised_bundle_hash": normalised_bundle_hash,
        "source_paths": {key: str(value) for key, value in paths.items()},
    }
    return metadata, checks, files


def _load_prices(files: dict[str, Path], symbols: list[str]) -> dict[str, pd.DataFrame]:
    prices: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = pd.read_csv(files[symbol])
        required = {"date", "close", "adj_close"}
        missing = required - set(frame.columns)
        if missing:
            raise GMA6DExecutionError(f"{symbol} missing normalised columns: {sorted(missing)}")
        result = pd.DataFrame(
            {
                "date": pd.to_datetime(frame["date"]).dt.date,
                "close_raw": pd.to_numeric(frame["close"], errors="raise"),
                "total_return_index": pd.to_numeric(frame["adj_close"], errors="raise"),
            }
        )
        result = result.loc[
            (pd.to_datetime(result["date"]) >= pd.Timestamp(HISTORY_START))
            & (pd.to_datetime(result["date"]) <= pd.Timestamp(HISTORY_END))
        ].copy()
        if result.empty:
            raise GMA6DExecutionError(f"{symbol} has no observations in the frozen history window")
        first = float(result["total_return_index"].iloc[0])
        if first <= 0:
            raise GMA6DExecutionError(f"{symbol} has non-positive first adjusted close")
        result["total_return_index"] = result["total_return_index"] / first * 100.0
        prices[symbol] = result.set_index("date").sort_index()
    return prices


def _common_dates(prices: dict[str, pd.DataFrame], symbols: list[str]) -> list[Any]:
    common = set(prices[symbols[0]].index)
    for symbol in symbols[1:]:
        common &= set(prices[symbol].index)
    dates = [date for date in sorted(common) if HISTORY_START <= str(date) <= HISTORY_END]
    if not dates or str(dates[0]) > HISTORY_START or str(dates[-1]) < HISTORY_END:
        raise GMA6DExecutionError("frozen bundle does not cover the required common history window")
    return dates


def _cash_from_bil(prices: dict[str, pd.DataFrame], dates: list[Any]) -> pd.DataFrame:
    rows = []
    bil = prices["BIL"]
    for idx in range(1, len(dates)):
        previous = float(bil.loc[dates[idx - 1], "total_return_index"])
        current = float(bil.loc[dates[idx], "total_return_index"])
        rows.append(
            {
                "accrual_start": dates[idx - 1],
                "accrual_end": dates[idx],
                "period_return": current / previous - 1.0,
            }
        )
    return pd.DataFrame(rows)


@contextlib.contextmanager
def _patched_shared_universe(
    symbols: list[str], prices: dict[str, pd.DataFrame] | None = None
) -> Iterator[None]:
    old_strategy_universe = strategy_library.FIXED_GMA4_UNIVERSE
    old_strategy_risk = strategy_library.RISK_ASSETS
    old_replay_universe = replay_adapter.FIXED_GMA4_UNIVERSE
    old_allowed = replay_adapter.GMA4_ALLOWED_TARGET_SYMBOLS
    old_dates_on_or_before = strategy_library._dates_on_or_before
    date_cache = (
        {symbol: list(frame.index) for symbol, frame in prices.items()}
        if prices is not None
        else {}
    )

    def fast_dates_on_or_before(
        _prices: dict[str, pd.DataFrame], symbol: str, value: Any
    ) -> list[Any]:
        dates = date_cache.get(symbol)
        if dates is None:
            return old_dates_on_or_before(_prices, symbol, value)
        return dates[: bisect.bisect_right(dates, value)]

    try:
        strategy_library.FIXED_GMA4_UNIVERSE = symbols
        strategy_library.RISK_ASSETS = [symbol for symbol in symbols if symbol != "BIL"]
        strategy_library._dates_on_or_before = fast_dates_on_or_before
        replay_adapter.FIXED_GMA4_UNIVERSE = symbols
        replay_adapter.GMA4_ALLOWED_TARGET_SYMBOLS = set(symbols) | {"CASH"}
        yield
    finally:
        strategy_library.FIXED_GMA4_UNIVERSE = old_strategy_universe
        strategy_library.RISK_ASSETS = old_strategy_risk
        strategy_library._dates_on_or_before = old_dates_on_or_before
        replay_adapter.FIXED_GMA4_UNIVERSE = old_replay_universe
        replay_adapter.GMA4_ALLOWED_TARGET_SYMBOLS = old_allowed


def _run_gma4_replay_with_cached_targets(
    *,
    prices: dict[str, pd.DataFrame],
    cash: pd.DataFrame,
    cached_targets: dict[Any, tuple[dict[str, float], dict[str, str]]],
    dates: list[Any],
    signal_dates: list[Any],
    strategy_id: str,
    strategy_version: str,
    cost_bps: float,
) -> replay_adapter.GMA4ReplayAdapterResult:
    def cached_resolver(
        _strategy_id: str,
        signal_date: Any,
        _prices: dict[str, pd.DataFrame],
        _macro: pd.DataFrame,
        _config: Any,
        _tactical_passers: list[str] | None = None,
    ) -> tuple[dict[str, float], dict[str, str]]:
        return cached_targets[signal_date]

    outputs = replay_adapter._simulate_strategy(
        strategy_id=strategy_id,
        dates=dates,
        prices=prices,
        cash_df=cash.copy(),
        macro=pd.DataFrame(),
        config=replay_adapter.GMA4ReplayConfig(
            cost_bps_per_notional=cost_bps,
            maximum_single_asset_weight=0.35,
        ),
        target_resolver=cached_resolver,
        rebalance_signal_dates=set(signal_dates),
        strategy_version=strategy_version,
    )
    execution_dates = (
        outputs["signals"]["execution_date"].drop_duplicates().tolist()
        if not outputs["signals"].empty
        else []
    )
    return replay_adapter.GMA4ReplayAdapterResult(
        equity=outputs["equity"],
        drawdown=outputs["drawdown"],
        holdings=outputs["holdings"],
        orders=outputs["orders"],
        fills=outputs["fills"],
        costs=outputs["costs"],
        signals=outputs["signals"],
        signal_dates=signal_dates,
        execution_dates=execution_dates,
    )


def _evaluation_windows(config_path: Path, dates: list[Any]) -> list[dict[str, Any]]:
    config = load_gma4_tournament_config(config_path)
    windows: list[dict[str, Any]] = [
        {
            "evaluation_scope": "full_history",
            "window_id": "full_history",
            "regime_id": "",
            "period_start": dates[0],
            "period_end": dates[-1],
        }
    ]
    for years, scope in [(3, "rolling_3y"), (5, "rolling_5y")]:
        for year in range(pd.Timestamp(dates[0]).year, pd.Timestamp(dates[-1]).year + 1):
            start = pd.Timestamp(year=year, month=1, day=1).date()
            end = (pd.Timestamp(year=year + years, month=1, day=1) - pd.Timedelta(days=1)).date()
            if start >= dates[0] and end <= dates[-1]:
                windows.append(
                    {
                        "evaluation_scope": scope,
                        "window_id": f"{year}_{year + years - 1}",
                        "regime_id": "",
                        "period_start": start,
                        "period_end": end,
                    }
                )
    for year in range(pd.Timestamp(dates[0]).year, pd.Timestamp(dates[-1]).year + 1):
        start = max(pd.Timestamp(year=year, month=1, day=1).date(), dates[0])
        end = min(pd.Timestamp(year=year, month=12, day=31).date(), dates[-1])
        windows.append(
            {
                "evaluation_scope": "sequential_walk_forward",
                "window_id": str(year),
                "regime_id": "",
                "period_start": start,
                "period_end": end,
            }
        )
    for regime in config.regimes:
        start = max(pd.Timestamp(regime["start_date"]).date(), dates[0])
        end = min(pd.Timestamp(regime["end_date"]).date(), dates[-1])
        if start <= end:
            windows.append(
                {
                    "evaluation_scope": "predefined_regimes",
                    "window_id": str(regime["regime_id"]),
                    "regime_id": str(regime["regime_id"]),
                    "period_start": start,
                    "period_end": end,
                }
            )
    return windows


def _window_years(start: Any, end: Any) -> float:
    return max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)


def _slice_result(
    result: replay_adapter.GMA4ReplayAdapterResult, start: Any, end: Any
) -> dict[str, pd.DataFrame]:
    equity = result.equity.loc[
        (pd.to_datetime(result.equity["valuation_date"]) >= pd.Timestamp(start))
        & (pd.to_datetime(result.equity["valuation_date"]) <= pd.Timestamp(end))
    ].copy()
    holdings = result.holdings.loc[
        (pd.to_datetime(result.holdings["valuation_date"]) >= pd.Timestamp(start))
        & (pd.to_datetime(result.holdings["valuation_date"]) <= pd.Timestamp(end))
    ].copy()
    costs = result.costs.copy()
    if not costs.empty:
        costs = costs.loc[
            (pd.to_datetime(costs["execution_date"]) >= pd.Timestamp(start))
            & (pd.to_datetime(costs["execution_date"]) <= pd.Timestamp(end))
        ].copy()
    return {"equity": equity, "holdings": holdings, "costs": costs}


def _empty_scoreboard_row(
    *,
    run_id: str,
    universe_version: str,
    trial: dict[str, Any],
    cost_scenario: str,
    window: dict[str, Any],
    effective_start: Any,
    methodology_regime_flag: str,
) -> dict[str, Any]:
    row = {column: "" for column in SCOREBOARD_COLUMNS}
    row.update(
        {
            "run_id": run_id,
            "universe_version": universe_version,
            "trial_id": trial["trial_id"],
            "trial_family": trial["family"],
            "cost_scenario": cost_scenario,
            "evaluation_scope": window["evaluation_scope"],
            "window_id": window["window_id"],
            "regime_id": window["regime_id"],
            "period_start": str(window["period_start"]),
            "period_end": str(window["period_end"]),
            "effective_period_start": str(effective_start),
            "methodology_regime_flag": methodology_regime_flag,
            "measurement_status": "missing_measurement",
        }
    )
    return row


def _metrics_from_frames(
    *,
    run_id: str,
    source_run_id: str,
    universe_version: str,
    trial: dict[str, Any],
    cost_scenario: str,
    window: dict[str, Any],
    effective_start: Any,
    frames: dict[str, pd.DataFrame],
    methodology_regime_flag: str,
) -> dict[str, Any]:
    equity = frames["equity"].sort_values("valuation_date")
    if equity.empty:
        return _empty_scoreboard_row(
            run_id=run_id,
            universe_version=universe_version,
            trial=trial,
            cost_scenario=cost_scenario,
            window=window,
            effective_start=effective_start,
            methodology_regime_flag=methodology_regime_flag,
        )
    start_value = float(equity.iloc[0]["portfolio_value"])
    end_value = float(equity.iloc[-1]["portfolio_value"])
    cumulative = end_value / start_value - 1.0
    years = _window_years(equity.iloc[0]["valuation_date"], equity.iloc[-1]["valuation_date"])
    returns = pd.to_numeric(equity["daily_return"], errors="coerce").fillna(0.0)
    downside = returns.loc[returns < 0]
    annual_vol = float(returns.std(ddof=0) * (252**0.5))
    downside_vol = float(downside.std(ddof=0) * (252**0.5)) if not downside.empty else 0.0
    costs = frames["costs"]
    cost_sum = float(
        pd.to_numeric(costs.get("transaction_cost", pd.Series(dtype=float)), errors="coerce").sum()
    )
    trade_abs = float(
        pd.to_numeric(
            costs.get("trade_notional_abs", pd.Series(dtype=float)), errors="coerce"
        ).sum()
    )
    holdings = frames["holdings"]
    weights = holdings.pivot_table(
        index="valuation_date", columns="symbol", values="weight", aggfunc="sum"
    ).fillna(0.0)
    non_cash = [column for column in weights.columns if column != "CASH"]
    hhi = (weights[non_cash] ** 2).sum(axis=1) if non_cash else pd.Series([0.0])
    return {
        "run_id": run_id,
        "universe_version": universe_version,
        "trial_id": trial["trial_id"],
        "trial_family": trial["family"],
        "cost_scenario": cost_scenario,
        "evaluation_scope": window["evaluation_scope"],
        "window_id": window["window_id"],
        "regime_id": window["regime_id"],
        "period_start": str(window["period_start"]),
        "period_end": str(window["period_end"]),
        "effective_period_start": str(effective_start),
        "session_count": int(len(equity)),
        "net_cagr": (end_value / start_value) ** (1.0 / years) - 1.0,
        "annualised_volatility": annual_vol,
        "sharpe": 0.0 if annual_vol == 0 else float(returns.mean() * 252 / annual_vol),
        "sortino": 0.0 if downside_vol == 0 else float(returns.mean() * 252 / downside_vol),
        "maximum_drawdown": float(pd.to_numeric(equity["drawdown"], errors="coerce").min()),
        "cumulative_net_return": cumulative,
        "annualised_turnover": 0.0 if start_value == 0 else (trade_abs / start_value) / years,
        "cost_drag": 0.0 if start_value == 0 else cost_sum / start_value,
        "maximum_hhi": float(hhi.max()),
        "methodology_regime_flag": methodology_regime_flag,
        "measurement_status": "valid",
        "source_run_id": source_run_id,
    }


def _eligible_start(dates: list[Any], lookback: int) -> Any:
    return dates[0] if lookback == 0 else dates[min(lookback, len(dates) - 1)]


def _run_arm(
    *,
    arm: ArmSpec,
    registry: Any,
    config_path: Path,
    prices: dict[str, pd.DataFrame],
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    arm_prices = {symbol: prices[symbol] for symbol in arm.symbols}
    dates = _common_dates(arm_prices, arm.symbols)
    cash = _cash_from_bil(arm_prices, dates)
    windows = _evaluation_windows(config_path, dates)
    scoreboard_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    with _patched_shared_universe(arm.symbols, arm_prices):
        rules = strategy_library.build_gma4_trial_rules()
        validated_prices = replay_adapter.validate_gma4_price_inputs(arm_prices)
        for trial in registry.trials:
            trial_id = str(trial["trial_id"])
            rule = rules[trial_id]
            eligible_start = _eligible_start(dates, rule.required_lookback_sessions)
            signal_dates = replay_adapter.build_gma4_rebalance_signal_dates(
                dates, rule.rebalance_schedule
            )
            signal_dates = [date for date in signal_dates if date >= eligible_start]
            if not signal_dates:
                raise GMA6DExecutionError(f"{trial_id} produced no signal dates")
            cached_targets = {
                signal_date: (
                    normalise_weights(rule.resolver(signal_date, validated_prices)),
                    {"reason_code": "gma6d_frozen_trial_resolver"},
                )
                for signal_date in signal_dates
            }
            for cost_scenario, bps in COST_BPS.items():
                result = _run_gma4_replay_with_cached_targets(
                    prices=validated_prices,
                    cash=cash,
                    cached_targets=cached_targets,
                    dates=dates,
                    signal_dates=signal_dates,
                    strategy_id=f"{arm.universe_version}__{trial_id}",
                    strategy_version=str(trial["version"]),
                    cost_bps=bps,
                )
                detail_rows.append(
                    {
                        "run_id": run_id,
                        "universe_version": arm.universe_version,
                        "source_gma4_trial_id": trial_id,
                        "arm_trial_id": f"{arm.universe_version}__{trial_id}",
                        "cost_scenario": cost_scenario,
                        "rebalance_schedule": rule.rebalance_schedule,
                        "required_lookback_sessions": rule.required_lookback_sessions,
                        "trial_identity_application": "locked_trial_identity_with_arm_specific_universe_application",
                        "signal_rows": len(result.signals),
                        "order_rows": len(result.orders),
                        "equity_rows": len(result.equity),
                    }
                )
                if not result.signals.empty:
                    signals = result.signals.copy()
                    signals.insert(0, "run_id", run_id)
                    signals.insert(1, "universe_version", arm.universe_version)
                    signals.insert(2, "source_gma4_trial_id", trial_id)
                    signals.insert(3, "cost_scenario", cost_scenario)
                    target_rows.extend(signals.to_dict("records"))
                for window in windows:
                    effective_start = max(window["period_start"], eligible_start)
                    frames = _slice_result(result, effective_start, window["period_end"])
                    scoreboard_rows.append(
                        _metrics_from_frames(
                            run_id=run_id,
                            source_run_id=run_id,
                            universe_version=arm.universe_version,
                            trial=trial,
                            cost_scenario=cost_scenario,
                            window=window,
                            effective_start=effective_start,
                            frames=frames,
                            methodology_regime_flag=arm.methodology_regime_flag,
                        )
                    )
    scoreboard = pd.DataFrame(scoreboard_rows)
    for column in SCOREBOARD_COLUMNS:
        if column not in scoreboard.columns:
            scoreboard[column] = ""
    return scoreboard[SCOREBOARD_COLUMNS], pd.DataFrame(detail_rows), pd.DataFrame(target_rows)


def _compare(scoreboard: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    grouped = scoreboard.groupby(
        ["trial_id", "cost_scenario", "evaluation_scope", "window_id"], dropna=False
    )
    for (trial_id, cost_scenario, evaluation_scope, window_id), group in grouped:
        core = group.loc[group["universe_version"] == CONTROL_UNIVERSE_VERSION]
        expanded = group.loc[group["universe_version"] == EXPANDED_UNIVERSE_VERSION]
        core_row = core.iloc[0].to_dict() if not core.empty else {}
        expanded_row = expanded.iloc[0].to_dict() if not expanded.empty else {}
        if len(core) != 1 or len(expanded) != 1:
            status = "not_comparable_due_to_missing_measurement"
        else:
            status = (
                "identical_effective_sample"
                if core_row["effective_period_start"] == expanded_row["effective_period_start"]
                and core_row["period_end"] == expanded_row["period_end"]
                and core_row["measurement_status"] == "valid"
                and expanded_row["measurement_status"] == "valid"
                else "not_comparable_due_to_effective_start"
            )
        audit_rows.append(
            {
                "trial_id": trial_id,
                "cost_scenario": cost_scenario,
                "evaluation_scope": evaluation_scope,
                "window_id": window_id,
                "core_effective_start": core_row.get("effective_period_start", ""),
                "expanded_effective_start": expanded_row.get("effective_period_start", ""),
                "core_period_end": core_row.get("period_end", ""),
                "expanded_period_end": expanded_row.get("period_end", ""),
                "sample_comparability_status": status,
            }
        )
        for metric in COMPARISON_METRICS:
            core_value = pd.to_numeric(pd.Series([core_row.get(metric, "")]), errors="coerce").iloc[
                0
            ]
            expanded_value = pd.to_numeric(
                pd.Series([expanded_row.get(metric, "")]), errors="coerce"
            ).iloc[0]
            difference = (
                expanded_value - core_value
                if pd.notna(core_value) and pd.notna(expanded_value)
                else ""
            )
            rows.append(
                {
                    "trial_id": trial_id,
                    "cost_scenario": cost_scenario,
                    "evaluation_scope": evaluation_scope,
                    "window_id": window_id,
                    "period_start": core_row.get(
                        "period_start", expanded_row.get("period_start", "")
                    ),
                    "period_end": core_row.get("period_end", expanded_row.get("period_end", "")),
                    "core_22_metric": core_value if pd.notna(core_value) else "",
                    "expanded_29_metric": expanded_value if pd.notna(expanded_value) else "",
                    "difference": difference,
                    "metric_name": metric,
                    "sample_comparability_status": status,
                    "interpretation_limit": INTERPRETATION_LIMIT,
                    "methodology_regime_flag": REQUIRED_USO_FLAG,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(audit_rows)


def _uso_detail(scoreboard: pd.DataFrame) -> pd.DataFrame:
    expanded = scoreboard.loc[scoreboard["universe_version"] == EXPANDED_UNIVERSE_VERSION].copy()
    rows = []
    for slice_id, start, end in [
        ("pre_may_2020_uso_roll_methodology", HISTORY_START, "2020-04-30"),
        ("from_may_2020_uso_roll_methodology", "2020-05-01", HISTORY_END),
    ]:
        scoped = expanded.loc[
            (pd.to_datetime(expanded["period_start"]) <= pd.Timestamp(end))
            & (pd.to_datetime(expanded["period_end"]) >= pd.Timestamp(start))
            & (expanded["measurement_status"] == "valid")
        ]
        rows.append(
            {
                "methodology_slice": slice_id,
                "slice_start": start,
                "slice_end": end,
                "methodology_regime_flag": REQUIRED_USO_FLAG,
                "result_row_count": int(len(scoped)),
                "interpretation_limit": "descriptive historical context only; no causation proof or standalone selection rule",
            }
        )
    return pd.DataFrame(rows)


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _write_reports(
    *,
    run_dir: Path,
    output_root: Path,
    manifest: dict[str, Any],
    verification: pd.DataFrame,
    scoreboard: pd.DataFrame,
    detail: pd.DataFrame,
    comparison: pd.DataFrame,
    sample_audit: pd.DataFrame,
    targets: pd.DataFrame,
    uso_detail: pd.DataFrame,
    provenance: dict[str, Any],
) -> None:
    verification.to_csv(run_dir / "gma6d_input_verification_v1.csv", index=False)
    scoreboard.to_csv(run_dir / "gma6d_tournament_scoreboard_v1.csv", index=False)
    detail.to_csv(run_dir / "gma6d_evaluation_detail_v1.csv", index=False)
    comparison.to_csv(run_dir / "gma6d_cross_universe_comparison_v1.csv", index=False)
    sample_audit.to_csv(run_dir / "gma6d_sample_comparability_audit_v1.csv", index=False)
    targets.to_csv(run_dir / "gma6d_monthly_target_weights_v1.csv", index=False)
    uso_detail.to_csv(run_dir / "gma6d_uso_methodology_regime_detail_v1.csv", index=False)
    (run_dir / "gma6d_run_manifest_v1.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "gma6d_execution_provenance_v1.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_markdown(
        run_dir / "gma6d_input_verification_v1.md",
        "GMA-6D Input Verification v1",
        [
            *REQUIRED_REPORT_LANGUAGE,
            "",
            *_table(
                ["check", "status", "observed"],
                [
                    [row["check_name"], row["status"], str(row["observed"])]
                    for row in verification.to_dict("records")
                ],
            ),
        ],
    )
    full = scoreboard.loc[
        (scoreboard["evaluation_scope"] == "full_history")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["measurement_status"] == "valid")
    ].copy()
    full["net_cagr"] = pd.to_numeric(full["net_cagr"], errors="coerce")
    full = full.sort_values(["universe_version", "net_cagr"], ascending=[True, False])
    _write_markdown(
        run_dir / "gma6d_tournament_scoreboard_v1.md",
        "GMA-6D Tournament Scoreboard v1",
        [
            *REQUIRED_REPORT_LANGUAGE,
            "",
            *_table(
                ["universe", "trial", "net_cagr", "sharpe", "drawdown"],
                [
                    [
                        row["universe_version"],
                        row["trial_id"],
                        f"{float(row['net_cagr']):.6f}",
                        f"{float(row['sharpe']):.6f}",
                        f"{float(row['maximum_drawdown']):.6f}",
                    ]
                    for row in full.head(40).to_dict("records")
                ],
            ),
        ],
    )
    headline = comparison.loc[
        (comparison["evaluation_scope"] == "full_history")
        & (comparison["metric_name"] == "net_cagr")
    ].copy()
    _write_markdown(
        run_dir / "gma6d_cross_universe_comparison_v1.md",
        "GMA-6D Cross-Universe Comparison v1",
        [
            *REQUIRED_REPORT_LANGUAGE,
            "",
            GMA4_REFERENCE_LIMIT,
            "",
            *_table(
                ["trial", "cost", "core", "expanded", "difference", "sample"],
                [
                    [
                        row["trial_id"],
                        row["cost_scenario"],
                        f"{float(row['core_22_metric']):.6f}",
                        f"{float(row['expanded_29_metric']):.6f}",
                        f"{float(row['difference']):.6f}",
                        row["sample_comparability_status"],
                    ]
                    for row in headline.to_dict("records")
                    if row["core_22_metric"] != "" and row["expanded_29_metric"] != ""
                ],
            ),
        ],
    )
    _write_markdown(
        run_dir / "gma6d_sample_comparability_audit_v1.md",
        "GMA-6D Sample Comparability Audit v1",
        [
            *REQUIRED_REPORT_LANGUAGE,
            "",
            *_table(
                ["status", "count"],
                [
                    [name, str(count)]
                    for name, count in sample_audit["sample_comparability_status"]
                    .value_counts()
                    .sort_index()
                    .items()
                ],
            ),
        ],
    )
    _write_markdown(
        run_dir / "gma6d_results_discussion_v1.md",
        "GMA-6D Results Discussion v1",
        [
            *REQUIRED_REPORT_LANGUAGE,
            "",
            "The primary comparison is core-22 versus expanded-29 within this GMA-6D run.",
            GMA4_REFERENCE_LIMIT,
            "USO methodology-regime slices are descriptive historical context only.",
            "No selection, deployment, or operational workflow is created.",
        ],
    )
    output_root.mkdir(parents=True, exist_ok=True)
    for filename in RUN_OUTPUT_FILENAMES:
        shutil.copy2(run_dir / filename, output_root / filename)


def run_gma6d_cross_universe_tournament(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    normalised_root: Path = DEFAULT_NORMALISED_ROOT,
    normalised_hashes_path: Path = DEFAULT_NORMALISED_HASHES,
    run_id_override: str | None = None,
    executed_at_utc: datetime | None = None,
    price_loader: Callable[[dict[str, Path], list[str]], dict[str, pd.DataFrame]] | None = None,
) -> GMA6DResult:
    paths = _read_gma6c_paths(config_path)
    metadata, checks, files = verify_inputs(
        config_path=config_path,
        lock_path=paths["gma6c_lock"],
        normalised_root=normalised_root,
        normalised_hashes_path=normalised_hashes_path,
    )
    gma4_config = load_gma4_tournament_config(paths["gma4_tournament_config"])
    registry = load_gma4_trial_registry(paths["gma4_trial_registry"])
    validate_gma4_contract(gma4_config, registry)
    if len(registry.trials) != 20:
        raise GMA6DExecutionError("trial inventory mismatch")
    if gma4_config.cost_scenarios != REQUIRED_COST_SCENARIOS:
        raise GMA6DExecutionError("unapproved cost scenario")
    prices = (price_loader or _load_prices)(files, EXPANDED_UNIVERSE)
    run_id = run_id_override or _new_run_id(executed_at_utc)
    run_dir = _make_run_dir(output_root, run_id)
    arms = [
        ArmSpec(CONTROL_UNIVERSE_VERSION, FIXED_GMA4_UNIVERSE, "not_applicable_no_uso"),
        ArmSpec(EXPANDED_UNIVERSE_VERSION, EXPANDED_UNIVERSE, REQUIRED_USO_FLAG),
    ]
    scoreboard_parts = []
    detail_parts = []
    target_parts = []
    for arm in arms:
        arm_scoreboard, arm_detail, arm_targets = _run_arm(
            arm=arm,
            registry=registry,
            config_path=paths["gma4_tournament_config"],
            prices=prices,
            run_id=run_id,
        )
        scoreboard_parts.append(arm_scoreboard)
        detail_parts.append(arm_detail)
        target_parts.append(arm_targets)
    scoreboard = pd.concat(scoreboard_parts, ignore_index=True)
    expanded_flags = scoreboard.loc[
        scoreboard["universe_version"] == EXPANDED_UNIVERSE_VERSION, "methodology_regime_flag"
    ]
    if not (expanded_flags == REQUIRED_USO_FLAG).all():
        raise GMA6DExecutionError("missing USO methodology-regime flag in expanded outputs")
    detail = pd.concat(detail_parts, ignore_index=True)
    targets = pd.concat(target_parts, ignore_index=True) if target_parts else pd.DataFrame()
    comparison, sample_audit = _compare(scoreboard)
    uso_detail = _uso_detail(scoreboard)
    lock = metadata["lock"]
    manifest = {
        "run_id": run_id,
        "executed_at_utc": (executed_at_utc or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat(),
        "parent_gma4_commit": lock["parent_gma4_commit"],
        "gma6c_lock_hash": metadata["gma6c_lock_hash"],
        "gma6b_data_bundle_manifest_hash": lock["gma6b_data_bundle_manifest_hash"],
        "normalised_bundle_hash": metadata["normalised_bundle_hash"],
        "control_universe_hash": lock["control_universe_hash"],
        "expanded_universe_hash": lock["expanded_universe_hash"],
        "trial_inventory_hash": lock["trial_inventory_hash"],
        "cost_scenario_hash": lock["cost_scenario_hash"],
        "methodology_regime_rules_hash": lock["methodology_regime_rules_hash"],
        "history_start": HISTORY_START,
        "history_end": HISTORY_END,
        "network_access_attempted": NETWORK_ACCESS_ATTEMPTED,
        "strategy_engine_module": "market_strats.global_multi_asset.gma4_strategy_library",
        "replay_adapter_module": "market_strats.global_multi_asset.gma4_replay_adapter",
    }
    provenance = {
        "execution_status": EXECUTION_STATUS,
        "source_paths": metadata["source_paths"],
        "normalised_file_count": len(files),
        "trial_count": len(registry.trials),
        "arm_count": len(arms),
        "cost_scenario_count": len(REQUIRED_COST_SCENARIOS),
        "gma4_reference_limit": GMA4_REFERENCE_LIMIT,
    }
    verification = pd.DataFrame(checks)
    _write_reports(
        run_dir=run_dir,
        output_root=output_root,
        manifest=manifest,
        verification=verification,
        scoreboard=scoreboard,
        detail=detail,
        comparison=comparison,
        sample_audit=sample_audit,
        targets=targets,
        uso_detail=uso_detail,
        provenance=provenance,
    )
    return GMA6DResult(run_id, run_dir, manifest, scoreboard, comparison, sample_audit, uso_detail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma6d_cross_universe_tournament"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)
    result = run_gma6d_cross_universe_tournament(config_path=args.config)
    print(f"run_id: {result.run_id}")
    print(f"run_dir: {result.run_dir}")
    print(f"scoreboard_rows: {len(result.scoreboard)}")
    print(f"comparison_rows: {len(result.comparison)}")
    print("network_access_attempted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
