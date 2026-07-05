from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

CONTRACT_ID = "gma8c_frozen_etf_etp_tournament_contract_v1"
GRID_HASH = "513139855cb34a67f735170683dd548724574001d43b7e3c4e29c32ecead5f6a"
GMA8A_LOCK_HASH = "12b0abffa49095bdc02b5c062c36b5413a94c68e229b552ed30145a1af7b5ee8"
GMA8B_LOCK_HASH = "b55795e4458f2bed57b0d09b6c9990b259f6fa4c32141b5391673e0b335f0a30"
CORE_ARM = "gma8_core_22_etf_v1"
EXPANDED_ARM = "gma8_expanded_29_etp_v1"
COMMON_START = "2008-05-29"
COMMON_END = "2026-05-01"
SOURCE_START = "2007-05-30"
SOURCE_END = "2026-05-01"
ANNUAL_SESSIONS = 252
TOLERANCE = 1e-10

GMA8A_ROOT = Path("reports/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_v1")
GMA8B_ROOT = Path("reports/global_multi_asset_alpha/gma8b_historical_data_provenance_v1")
DEFAULT_OUTPUT_ROOT = Path("reports/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_v1")
DEFAULT_CONFIG = Path(
    "configs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.yaml"
)

GMA8A_INPUTS = (
    Path("configs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.yaml"),
    GMA8A_ROOT / "gma8a_universe_arm_registry_v1.csv",
    GMA8A_ROOT / "gma8a_strategy_grid_registry_v1.csv",
    GMA8A_ROOT / "gma8a_regime_window_registry_v1.csv",
    GMA8A_ROOT / "gma8a_metric_registry_v1.csv",
    GMA8A_ROOT / "gma8a_robustness_gate_registry_v1.csv",
    GMA8A_ROOT / "gma8a_lock_v1.json",
    GMA8A_ROOT / "gma8a_execution_manifest_v1.json",
)
GMA8B_INPUTS = (
    GMA8B_ROOT / "gma8b_parent_data_reference_resolution_v1.json",
    GMA8B_ROOT / "gma8b_adjusted_price_input_contract_v1.csv",
    GMA8B_ROOT / "gma8b_universe_asset_availability_v1.csv",
    GMA8B_ROOT / "gma8b_arm_coverage_summary_v1.csv",
    GMA8B_ROOT / "gma8b_data_quality_audit_v1.csv",
    GMA8B_ROOT / "gma8b_data_manifest_v1.json",
    GMA8B_ROOT / "gma8b_data_lock_v1.json",
    GMA8B_ROOT / "gma8b_execution_manifest_v1.json",
)
OUTPUT_FILENAMES = (
    "gma8c_trial_scoreboard_stressed_10bps_v1.csv",
    "gma8c_full_history_metrics_v1.csv",
    "gma8c_chronological_fold_metrics_v1.csv",
    "gma8c_regime_window_metrics_v1.csv",
    "gma8c_rolling_window_summary_v1.csv",
    "gma8c_robustness_gate_board_v1.csv",
    "gma8c_tournament_summary_v1.md",
    "gma8c_execution_manifest_v1.json",
    "gma8c_tournament_lock_v1.json",
)


class GMA8CTournamentError(RuntimeError):
    """Raised when frozen evidence or tournament invariants do not hold."""


@dataclass(frozen=True)
class FrozenInputs:
    config: dict[str, Any]
    strategy_rows: list[dict[str, str]]
    arms: dict[str, list[str]]
    regimes: list[dict[str, str]]
    folds: list[dict[str, str]]
    costs: dict[str, int]
    source_rows: list[dict[str, str]]
    parent_hashes: dict[str, str]


@dataclass(frozen=True)
class TrialPath:
    arm_trial_id: str
    strategy_id: str
    family: str
    universe_arm: str
    daily: pd.DataFrame
    first_target_effective_session: str
    actual_first_return_session: str


@dataclass(frozen=True)
class TournamentResult:
    artifacts: dict[str, str]
    scoreboard: pd.DataFrame
    output_paths: list[Path]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GMA8CTournamentError(f"invalid required JSON: {path.as_posix()}") from exc
    if not isinstance(value, dict):
        raise GMA8CTournamentError(f"required JSON is not an object: {path.as_posix()}")
    return value


def _csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise GMA8CTournamentError(f"cannot read required CSV: {path.as_posix()}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GMA8CTournamentError(message)


def _resolve(root: Path, relative: Path) -> Path:
    path = (root / relative).resolve()
    _require(path.is_file(), f"missing required frozen input: {relative.as_posix()}")
    return path


def load_frozen_inputs(config_path: str | Path, worktree_root: str | Path = ".") -> FrozenInputs:
    root = Path(worktree_root).resolve()
    config_file = _resolve(root, Path(config_path))
    try:
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GMA8CTournamentError("invalid GMA-8C contract YAML") from exc
    _require(isinstance(config, dict), "GMA-8C contract must be a mapping")
    for relative in (*GMA8A_INPUTS, *GMA8B_INPUTS):
        _resolve(root, relative)

    frozen = config.get("frozen_parent") or {}
    _require(
        frozen.get("strategy_grid_hash") == GRID_HASH, "configured strategy-grid hash mismatch"
    )
    _require(frozen.get("trial_template_count") == 80, "configured template count mismatch")
    _require(frozen.get("arm_trial_count") == 160, "configured arm-trial count mismatch")
    _require(
        frozen.get("resolved_normalised_series_count") == 29, "configured source count mismatch"
    )
    _require(frozen.get("adjusted_price_field") == "adj_close", "adjusted-price field mismatch")

    a_lock_path = _resolve(root, GMA8A_ROOT / "gma8a_lock_v1.json")
    b_lock_path = _resolve(root, GMA8B_ROOT / "gma8b_data_lock_v1.json")
    _require(_sha256(a_lock_path) == GMA8A_LOCK_HASH, "GMA-8A lock SHA-256 mismatch")
    _require(_sha256(b_lock_path) == GMA8B_LOCK_HASH, "GMA-8B data-lock SHA-256 mismatch")
    a_lock = _json(a_lock_path)
    b_lock = _json(b_lock_path)
    _require(
        a_lock.get("exact_base_strategy_template_count") == 80, "GMA-8A template count mismatch"
    )
    _require(a_lock.get("exact_arm_trial_count") == 160, "GMA-8A arm-trial count mismatch")
    _require(a_lock.get("strategy_grid_hash") == GRID_HASH, "GMA-8A strategy-grid hash mismatch")
    for name, expected in (a_lock.get("artifact_sha256") or {}).items():
        artifact = _resolve(root, GMA8A_ROOT / name)
        _require(_sha256(artifact) == expected, f"GMA-8A artifact hash mismatch: {name}")

    exact_b_facts = {
        "resolved_normalised_series_count": 29,
        "source_first_session": SOURCE_START,
        "source_last_session": SOURCE_END,
        "core_22_arm_first_all_assets_253_session_eligible_date": COMMON_START,
        "expanded_29_arm_first_all_assets_253_session_eligible_date": COMMON_START,
        "cross_arm_comparable_253_session_start": COMMON_START,
        "inherited_historical_adjusted_price_files_read": True,
        "indicator_calculation_performed": False,
        "backtest_performed": False,
        "strategy_ranking_performed": False,
    }
    for key, expected in exact_b_facts.items():
        _require(b_lock.get(key) == expected, f"GMA-8B frozen fact mismatch: {key}")

    strategy_rows = _csv_rows(_resolve(root, GMA8A_ROOT / "gma8a_strategy_grid_registry_v1.csv"))
    _require(len(strategy_rows) == 160, "strategy registry must contain exactly 160 arm trials")
    _require(
        len({row["strategy_id"] for row in strategy_rows}) == 80,
        "strategy registry must contain 80 templates",
    )
    _require(
        len({row["arm_trial_id"] for row in strategy_rows}) == 160, "arm trial IDs must be unique"
    )
    _require(
        all(row.get("strategy_grid_hash") == GRID_HASH for row in strategy_rows),
        "strategy row grid-hash mismatch",
    )

    universe_rows = _csv_rows(_resolve(root, GMA8A_ROOT / "gma8a_universe_arm_registry_v1.csv"))
    arms: dict[str, list[str]] = {CORE_ARM: [], EXPANDED_ARM: []}
    for row in universe_rows:
        arm = row.get("universe_arm", "")
        _require(arm in arms, f"unsupported universe arm: {arm}")
        arms[arm].append(row["symbol"])
    _require(len(arms[CORE_ARM]) == 22, "Core-22 registry mismatch")
    _require(len(arms[EXPANDED_ARM]) == 29, "Expanded-29 registry mismatch")

    regimes = _csv_rows(_resolve(root, GMA8A_ROOT / "gma8a_regime_window_registry_v1.csv"))
    _require(len(regimes) == 7, "regime registry must contain seven frozen windows")
    source_rows = _csv_rows(
        _resolve(root, GMA8B_ROOT / "gma8b_adjusted_price_input_contract_v1.csv")
    )
    _require(len(source_rows) == 29, "GMA-8B input contract must contain 29 series")
    lock_paths = b_lock.get("resolved_normalised_series_paths") or []
    lock_hashes = b_lock.get("resolved_normalised_series_sha256") or {}
    _require(
        len(lock_paths) == 29 and len(lock_hashes) == 29, "GMA-8B resolved source lock mismatch"
    )
    for row, expected_path in zip(source_rows, lock_paths):
        ticker = row.get("ticker", "")
        _require(
            row.get("immutable_snapshot_path") == expected_path, f"snapshot path mismatch: {ticker}"
        )
        _require(
            row.get("normalised_series_sha256") == lock_hashes.get(ticker),
            f"source hash mismatch: {ticker}",
        )
        _require(
            row.get("adjusted_price_field") == "adj_close",
            f"adjusted-price field mismatch: {ticker}",
        )
        _require(
            row.get("source_path_used_for_data_read") == "False", f"source_path admitted: {ticker}"
        )

    evaluation = config.get("evaluation") or {}
    costs = evaluation.get("cost_scenarios_bps") or {}
    _require(
        costs
        == {"baseline_1bps": 1, "stressed_10bps": 10, "stressed_25bps": 25, "severe_50bps": 50},
        "cost scenarios mismatch",
    )
    folds = evaluation.get("chronological_folds") or []
    _require(len(folds) == 5, "five chronological folds are required")
    parent_hashes = {
        relative.as_posix(): _sha256(_resolve(root, relative))
        for relative in (*GMA8A_INPUTS, *GMA8B_INPUTS)
    }
    parent_hashes[Path(config_path).as_posix()] = _sha256(config_file)
    return FrozenInputs(
        config, strategy_rows, arms, regimes, folds, costs, source_rows, parent_hashes
    )


def load_price_matrix(inputs: FrozenInputs) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for row in inputs.source_rows:
        ticker = row["ticker"]
        path = Path(row["immutable_snapshot_path"])
        _require(path.is_file(), f"missing immutable adjusted-price series: {ticker}")
        _require(
            _sha256(path) == row["normalised_series_sha256"],
            f"immutable source SHA-256 mismatch: {ticker}",
        )
        frame = pd.read_csv(path, usecols=["date", "adj_close"])
        _require(list(frame.columns) == ["date", "adj_close"], f"frozen schema mismatch: {ticker}")
        dates = pd.to_datetime(frame["date"], errors="raise")
        values = pd.to_numeric(frame["adj_close"], errors="raise")
        _require(
            dates.is_monotonic_increasing and not dates.duplicated().any(),
            f"invalid session sequence: {ticker}",
        )
        _require(
            np.isfinite(values).all() and (values > 0).all(), f"invalid adjusted prices: {ticker}"
        )
        series[ticker] = pd.Series(
            values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates), name=ticker
        )
    prices = pd.concat(series.values(), axis=1, join="outer")
    prices.columns = list(series)
    _require(prices.index.min().date().isoformat() == SOURCE_START, "source first session mismatch")
    _require(prices.index.max().date().isoformat() == SOURCE_END, "source last session mismatch")
    required = prices.loc[COMMON_START:COMMON_END]
    _require(not required.isna().any().any(), "common comparable range contains missing prices")
    return prices


def _decision_indices(dates: pd.DatetimeIndex, start: int, frequency: str) -> list[int]:
    candidates = {start}
    if frequency in {"none_after_initial_formation"}:
        return [start]
    if frequency == "daily_next_tradable_session":
        candidates.update(range(start, len(dates) - 1))
    elif frequency == "weekly_next_tradable_session":
        for index in range(start, len(dates) - 1):
            current = dates[index].isocalendar()
            following = dates[index + 1].isocalendar()
            if (current.year, current.week) != (following.year, following.week):
                candidates.add(index)
    elif frequency == "monthly_next_tradable_session":
        for index in range(start, len(dates) - 1):
            if dates[index].to_period("M") != dates[index + 1].to_period("M"):
                candidates.add(index)
    else:
        raise GMA8CTournamentError(f"unsupported rebalance frequency: {frequency}")
    return sorted(index for index in candidates if index < len(dates) - 1)


def _lookback(row: dict[str, str]) -> int:
    values = [int(value) for value in re.findall(r"\d+", row.get("lookback_sessions", ""))]
    return max(values, default=0)


_ARRAY_CACHE: dict[tuple[int, tuple[str, ...]], np.ndarray] = {}


def _arm_matrix(prices: pd.DataFrame, symbols: list[str]) -> np.ndarray:
    key = (id(prices), tuple(symbols))
    matrix = _ARRAY_CACHE.get(key)
    if matrix is None:
        positions = [prices.columns.get_loc(symbol) for symbol in symbols]
        matrix = prices.to_numpy(dtype=float)[:, positions]
        _ARRAY_CACHE[key] = matrix
    return matrix


def _eligible(prices: pd.DataFrame, symbols: list[str], index: int, lookback: int) -> list[str]:
    if index < lookback:
        return []
    valid = np.isfinite(_arm_matrix(prices, symbols)[index - lookback : index + 1]).all(axis=0)
    return [symbol for symbol, admitted in zip(symbols, valid) if admitted]


def _equal(symbols: list[str], arm: list[str]) -> np.ndarray:
    weights = np.zeros(len(arm), dtype=float)
    if symbols:
        weight = 1.0 / len(symbols)
        for symbol in symbols:
            weights[arm.index(symbol)] = weight
    return weights


def _with_bil_residual(weights: np.ndarray, arm: list[str]) -> np.ndarray:
    total = float(weights.sum())
    _require(total <= 1.0 + TOLERANCE, "strategy target exceeds gross exposure one")
    if total < 1.0:
        weights[arm.index("BIL")] += 1.0 - total
    _validate_target(weights)
    return weights


def _inverse_vol(
    prices: pd.DataFrame, symbols: list[str], arm: list[str], index: int
) -> np.ndarray:
    positions = [arm.index(symbol) for symbol in symbols]
    values = _arm_matrix(prices, arm)[index - 63 : index + 1, positions]
    returns = values[1:] / values[:-1] - 1.0
    volatility = np.std(returns, axis=0, ddof=1)
    valid = np.isfinite(volatility) & (volatility > 0)
    if not valid.any():
        return _with_bil_residual(np.zeros(len(arm)), arm)
    valid_symbols = [symbol for symbol, admitted in zip(symbols, valid) if admitted]
    inverse = 1.0 / volatility[valid]
    inverse /= inverse.sum()
    weights = np.zeros(len(arm), dtype=float)
    for symbol, value in zip(valid_symbols, inverse):
        weights[arm.index(symbol)] = float(value)
    return _with_bil_residual(weights, arm)


def _validate_target(weights: np.ndarray) -> None:
    _require(np.isfinite(weights).all(), "target contains non-finite weight")
    _require((weights >= -TOLERANCE).all(), "target contains negative weight")
    _require(abs(float(weights.sum()) - 1.0) <= TOLERANCE, "target does not sum to one")


def _raw_target(
    row: dict[str, str],
    index: int,
    prices: pd.DataFrame,
    arm: list[str],
    arm_curve: pd.Series,
    rows_by_strategy: dict[str, dict[str, str]],
    seen: frozenset[str] = frozenset(),
    holding_state: dict[str, dict[str, int]] | None = None,
) -> np.ndarray:
    strategy_id = row["strategy_id"]
    _require(strategy_id not in seen, f"cyclic blend definition: {strategy_id}")
    family = row["strategy_family"]
    lookback = _lookback(row)
    eligible = _eligible(prices, arm, index, lookback)
    matrix = _arm_matrix(prices, arm)
    eligible_positions = np.array([arm.index(symbol) for symbol in eligible], dtype=int)
    if family in {"benchmark_buy_and_hold", "benchmark_equal_weight_monthly"}:
        return _equal(eligible or arm, arm)
    if family == "absolute_trend":
        if lookback == 252:
            signals = (
                matrix[index, eligible_positions] / matrix[index - lookback, eligible_positions]
                - 1.0
            )
        else:
            signals = (
                matrix[index, eligible_positions]
                / matrix[index - lookback + 1 : index + 1, eligible_positions].mean(axis=0)
                - 1.0
            )
        selected = [symbol for symbol, signal in zip(eligible, signals) if signal > 0]
        if "inverse_vol" in row["portfolio_construction"]:
            return (
                _inverse_vol(prices, selected, arm, index)
                if selected
                else _with_bil_residual(np.zeros(len(arm)), arm)
            )
        return _with_bil_residual(_equal(selected, arm), arm)
    if family in {"cross_sectional_momentum", "short_horizon_mean_reversion"}:
        values = (
            matrix[index, eligible_positions] / matrix[index - lookback, eligible_positions] - 1.0
        )
        returns = dict(zip(eligible, values))
        reverse = family == "cross_sectional_momentum"
        if family == "short_horizon_mean_reversion" and holding_state is not None:
            maximum_holding_match = re.search(
                r"maximum_holding_sessions=(\d+)|maximum_holding_(\d+)_sessions",
                row["turnover_control_rule"],
            )
            _require(
                maximum_holding_match is not None,
                f"missing maximum holding rule: {strategy_id}",
            )
            maximum_holding = int(maximum_holding_match.group(1) or maximum_holding_match.group(2))
            previous_holds = holding_state.setdefault(strategy_id, {})
            returns = {
                symbol: value
                for symbol, value in returns.items()
                if previous_holds.get(symbol, 0) < maximum_holding
            }
        ranked = sorted(returns, key=lambda symbol: (returns[symbol], symbol), reverse=reverse)
        selected = ranked[: int(row["maximum_positions"])]
        if family == "short_horizon_mean_reversion" and holding_state is not None:
            previous_holds = holding_state.setdefault(strategy_id, {})
            holding_state[strategy_id] = {
                symbol: previous_holds.get(symbol, 0) + 1 for symbol in selected
            }
        if "inverse_volatility" in row["portfolio_construction"]:
            return _inverse_vol(prices, selected, arm, index)
        return _with_bil_residual(_equal(selected, arm), arm)
    if family == "breakout_trend_following":
        current_values = matrix[index, eligible_positions]
        prior_highs = matrix[index - lookback : index, eligible_positions].max(axis=0)
        selected = [
            symbol
            for symbol, current, prior_high in zip(eligible, current_values, prior_highs)
            if current > prior_high
        ]
        if "inverse_volatility" in row["portfolio_construction"]:
            return (
                _inverse_vol(prices, selected, arm, index)
                if selected
                else _with_bil_residual(np.zeros(len(arm)), arm)
            )
        return _with_bil_residual(_equal(selected, arm), arm)
    if family == "volatility_targeting_and_inverse_volatility":
        risky = [symbol for symbol in eligible if symbol != "BIL"]
        base = _inverse_vol(prices, risky, arm, index)
        base[arm.index("BIL")] = 0.0
        risky_sum = base.sum()
        if risky_sum <= 0:
            return _with_bil_residual(base, arm)
        base /= risky_sum
        values = matrix[index - lookback : index + 1]
        returns = values[1:] / values[:-1] - 1.0
        covariance = np.cov(returns, rowvar=False, ddof=1) * ANNUAL_SESSIONS
        annual_vol = math.sqrt(max(float(base @ covariance @ base), 0.0))
        target_match = re.search(r"target_volatility_0\.(\d+)", row["risk_overlay_rule"])
        _require(target_match is not None, f"missing target volatility: {strategy_id}")
        target_vol = float(f"0.{target_match.group(1)}")
        scale = min(1.0, target_vol / annual_vol) if annual_vol > 0 else 0.0
        return _with_bil_residual(base * scale, arm)
    if family == "drawdown_and_defensive_overlays":
        threshold = float(row["ranking_or_trigger_rule"].split("_")[-1])
        current = float(arm_curve.iloc[index])
        peak = float(arm_curve.iloc[: index + 1].max())
        if current / peak - 1.0 <= -threshold:
            fallback = row["fallback_asset_or_cash_rule"].removeprefix("defensive_fallback_")
            _require(fallback in arm, f"frozen fallback unavailable in arm: {fallback}")
            return _equal([fallback], arm)
        return _equal(eligible or arm, arm)
    if family == "fixed_rule_blends":
        components = row["signal_inputs"].split("|")
        _require(len(components) >= 2, f"blend has insufficient components: {strategy_id}")
        targets = [
            _raw_target(
                rows_by_strategy[component],
                index,
                prices,
                arm,
                arm_curve,
                rows_by_strategy,
                seen | {strategy_id},
                holding_state,
            )
            for component in components
        ]
        target = np.mean(targets, axis=0)
        _validate_target(target)
        return target
    raise GMA8CTournamentError(f"unsupported frozen strategy family: {family}")


def build_trial_path(
    row: dict[str, str], prices: pd.DataFrame, arm: list[str], common_start: str = COMMON_START
) -> TrialPath:
    dates = prices.index
    start = int(dates.get_loc(pd.Timestamp(common_start)))
    arm_prices = prices[arm]
    arm_values = arm_prices.to_numpy(dtype=float)
    asset_return_matrix = arm_values[1:] / arm_values[:-1] - 1.0
    normalized = arm_prices.div(arm_prices.iloc[start])
    arm_curve = normalized.mean(axis=1)
    arm_rows = {
        candidate["strategy_id"]: candidate
        for candidate in _CURRENT_STRATEGY_ROWS
        if candidate["eligible_universe_arm"] == row["eligible_universe_arm"]
    }
    decisions = _decision_indices(dates, start, row["rebalance_frequency"])
    holding_state: dict[str, dict[str, int]] = {}
    targets = {}
    for decision in decisions:
        targets[decision] = _raw_target(
            row, decision, prices, arm, arm_curve, arm_rows, holding_state=holding_state
        )
    for target in targets.values():
        _validate_target(target)

    current = np.zeros(len(arm), dtype=float)
    current[arm.index("BIL")] = 1.0
    records: list[dict[str, Any]] = []
    first_effective = start + 1
    for index in range(first_effective, len(dates)):
        if index == first_effective:
            gross_return = 0.0
            drifted = current.copy()
        else:
            asset_returns = asset_return_matrix[index - 1]
            gross_return = float(current @ asset_returns)
            denominator = 1.0 + gross_return
            _require(denominator > 0, "portfolio value became non-positive")
            drifted = current * (1.0 + asset_returns) / denominator
        decision = index - 1
        turnover = 0.0
        if decision in targets:
            target = targets[decision]
            turnover = float(np.abs(target - drifted).sum())
            current = target.copy()
        else:
            current = drifted
        records.append(
            {
                "session_date": dates[index],
                "gross_return": gross_return,
                "one_way_turnover": turnover,
                "HHI": float(np.square(current).sum()),
            }
        )
    daily = pd.DataFrame(records).set_index("session_date")
    return TrialPath(
        arm_trial_id=row["arm_trial_id"],
        strategy_id=row["strategy_id"],
        family=row["strategy_family"],
        universe_arm=row["eligible_universe_arm"],
        daily=daily,
        first_target_effective_session=dates[first_effective].date().isoformat(),
        actual_first_return_session=dates[first_effective + 1].date().isoformat(),
    )


_CURRENT_STRATEGY_ROWS: list[dict[str, str]] = []


def apply_cost(path: TrialPath, cost_bps: int) -> pd.DataFrame:
    frame = path.daily.copy()
    rate = frame["one_way_turnover"] * float(cost_bps) / 10000.0
    _require((rate < 1.0).all(), "transaction cost exhausted portfolio value")
    frame["transaction_cost"] = rate
    frame["net_return"] = (1.0 + frame["gross_return"]) * (1.0 - rate) - 1.0
    return frame


def _metric_values(frame: pd.DataFrame) -> dict[str, float | int | str]:
    _require(not frame.empty, "metric window is empty")
    gross = frame["gross_return"].to_numpy(dtype=float)
    net = frame["net_return"].to_numpy(dtype=float)
    _require(np.isfinite(gross).all() and np.isfinite(net).all(), "return window is non-finite")
    gross_total = float(np.prod(1.0 + gross) - 1.0)
    net_total = float(np.prod(1.0 + net) - 1.0)
    years = len(frame) / ANNUAL_SESSIONS
    cagr = float((1.0 + net_total) ** (1.0 / years) - 1.0) if years > 0 else math.nan
    standard_deviation = float(np.std(net, ddof=1)) if len(net) > 1 else 0.0
    sharpe = (
        float(np.mean(net) / standard_deviation * math.sqrt(ANNUAL_SESSIONS))
        if standard_deviation > 0
        else math.nan
    )
    downside = float(np.sqrt(np.mean(np.square(np.minimum(net, 0.0)))))
    sortino = (
        float(np.mean(net) / downside * math.sqrt(ANNUAL_SESSIONS)) if downside > 0 else math.nan
    )
    cumulative = np.concatenate(([1.0], np.cumprod(1.0 + net)))
    peaks = np.maximum.accumulate(cumulative)
    maximum_drawdown = float(np.min(cumulative / peaks - 1.0))
    calmar = float(cagr / abs(maximum_drawdown)) if maximum_drawdown < 0 else math.nan
    annualised_turnover = float(frame["one_way_turnover"].sum() / years) if years > 0 else math.nan
    return {
        "period_start": frame.index.min().date().isoformat(),
        "period_end": frame.index.max().date().isoformat(),
        "session_count": len(frame),
        "gross_return": gross_total,
        "net_return": net_total,
        "CAGR": cagr,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "maximum_drawdown": maximum_drawdown,
        "Calmar": calmar,
        "annualised_turnover": annualised_turnover,
        "cost_drag": gross_total - net_total,
        "maximum_HHI": float(frame["HHI"].max()),
    }


def _active_fields(trial: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, float]:
    trial_factor = 1.0 + float(trial["net_return"])
    benchmark_factor = 1.0 + float(benchmark["net_return"])
    _require(trial_factor > 0 and benchmark_factor > 0, "active-return factor is non-positive")
    return {
        "same_arm_benchmark_net_return": float(benchmark["net_return"]),
        "same_arm_benchmark_CAGR": float(benchmark["CAGR"]),
        "net_active_return_vs_benchmark": trial_factor / benchmark_factor - 1.0,
        "net_active_CAGR_vs_benchmark": float(trial["CAGR"]) - float(benchmark["CAGR"]),
        "maximum_drawdown_difference_vs_benchmark": float(trial["maximum_drawdown"])
        - float(benchmark["maximum_drawdown"]),
        "active_log_return_contribution": math.log(trial_factor) - math.log(benchmark_factor),
    }


def _window(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return frame.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def _base_identity(path: TrialPath, scenario: str, cost_bps: int) -> dict[str, Any]:
    return {
        "run_id": "gma8c_frozen_160_trial_v1",
        "arm_trial_id": path.arm_trial_id,
        "strategy_id": path.strategy_id,
        "strategy_family": path.family,
        "universe_arm": path.universe_arm,
        "cost_scenario": scenario,
        "cost_bps": cost_bps,
    }


def _rolling_summary(
    path: TrialPath,
    frame: pd.DataFrame,
    scenario: str,
    cost_bps: int,
    window_type: str,
    sessions: int,
) -> dict[str, Any]:
    index = frame.index
    months = index.to_period("M")
    endpoints = np.flatnonzero(np.r_[months[:-1].to_numpy() != months[1:].to_numpy(), True])
    endpoints = endpoints[endpoints >= sessions - 1]
    _require(len(endpoints) > 0, f"no valid {window_type} windows")
    net = frame["net_return"].to_numpy(dtype=float)
    cagrs: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    positives: list[bool] = []
    annual_exponent = ANNUAL_SESSIONS / sessions
    for position in endpoints:
        window = net[position - sessions + 1 : position + 1]
        total = float(np.prod(1.0 + window) - 1.0)
        cagr = float((1.0 + total) ** annual_exponent - 1.0)
        standard_deviation = float(np.std(window, ddof=1))
        sharpe = (
            float(np.mean(window) / standard_deviation * math.sqrt(ANNUAL_SESSIONS))
            if standard_deviation > 0
            else math.nan
        )
        cumulative = np.r_[1.0, np.cumprod(1.0 + window)]
        peaks = np.maximum.accumulate(cumulative)
        drawdown = float(np.min(cumulative / peaks - 1.0))
        cagrs.append(cagr)
        sharpes.append(sharpe)
        drawdowns.append(drawdown)
        positives.append(total > 0)
    return {
        **_base_identity(path, scenario, cost_bps),
        "rolling_window_type": window_type,
        "window_sessions": sessions,
        "window_count": len(endpoints),
        "first_window_end": frame.index[endpoints[0]].date().isoformat(),
        "last_window_end": frame.index[endpoints[-1]].date().isoformat(),
        "median_net_CAGR": float(np.median(cagrs)),
        "worst_net_CAGR": float(np.min(cagrs)),
        "median_Sharpe": float(np.median(sharpes)),
        "worst_maximum_drawdown": float(np.min(drawdowns)),
        "positive_window_fraction": float(np.mean(positives)),
    }


def _positive_contribution_share(values: list[float]) -> tuple[float, bool]:
    positive = [value for value in values if value > 0]
    denominator = float(sum(positive))
    if denominator <= 0:
        return math.nan, False
    share = max(positive) / denominator
    return share, share <= 0.50 + TOLERANCE


def _gate_rows_and_scoreboard(
    full: pd.DataFrame, folds: pd.DataFrame, regimes: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stressed = full[full["cost_scenario"] == "stressed_10bps"].copy()
    gate_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    for _, row in stressed.iterrows():
        trial_id = row["arm_trial_id"]
        trial_folds = folds[
            (folds["arm_trial_id"] == trial_id) & (folds["cost_scenario"] == "stressed_10bps")
        ]
        trial_regimes = regimes[
            (regimes["arm_trial_id"] == trial_id) & (regimes["cost_scenario"] == "stressed_10bps")
        ]
        _require(len(trial_folds) == 5, f"missing chronological folds: {trial_id}")
        _require(len(trial_regimes) == 7, f"missing regime windows: {trial_id}")
        positive_fold_count = int((trial_folds["net_active_return_vs_benchmark"] > 0).sum())
        fold_share, fold_gate = _positive_contribution_share(
            trial_folds["active_log_return_contribution"].tolist()
        )
        regime_share, regime_gate = _positive_contribution_share(
            trial_regimes["active_log_return_contribution"].tolist()
        )
        gates = [
            (
                "positive_net_active_return_vs_benchmark_at_stressed_10bps",
                float(row["net_active_return_vs_benchmark"]),
                float(row["net_active_return_vs_benchmark"]) > 0,
            ),
            (
                "at_least_3_positive_chronological_test_folds",
                positive_fold_count,
                positive_fold_count >= 3,
            ),
            ("largest_fold_return_share_lte_0_50", fold_share, fold_gate),
            (
                "maximum_drawdown_not_worse_than_benchmark_by_more_than_0_03",
                float(row["maximum_drawdown_difference_vs_benchmark"]),
                float(row["maximum_drawdown_difference_vs_benchmark"]) >= -0.03 - TOLERANCE,
            ),
            (
                "no_single_regime_window_accounts_for_majority_of_total_active_return",
                regime_share,
                regime_gate,
            ),
            (
                "turnover_and_cost_drag_reported",
                f"turnover={row['annualised_turnover']};cost_drag={row['cost_drag']}",
                math.isfinite(float(row["annualised_turnover"]))
                and math.isfinite(float(row["cost_drag"])),
            ),
        ]
        for gate_id, value, passed in gates:
            gate_rows.append(
                {
                    "run_id": row["run_id"],
                    "arm_trial_id": trial_id,
                    "strategy_id": row["strategy_id"],
                    "universe_arm": row["universe_arm"],
                    "cost_scenario": "stressed_10bps",
                    "gate_id": gate_id,
                    "observed_value": value,
                    "gate_passed": bool(passed),
                }
            )
        passed_count = sum(bool(item[2]) for item in gates)
        status = (
            "passes_all_predeclared_historical_gates"
            if passed_count == 6
            else "does_not_pass_all_predeclared_historical_gates"
        )
        score_rows.append(
            {
                "run_id": row["run_id"],
                "arm_trial_id": trial_id,
                "strategy_id": row["strategy_id"],
                "strategy_family": row["strategy_family"],
                "universe_arm": row["universe_arm"],
                "historical_robustness_status": status,
                "gates_passed_count": passed_count,
                "net_return": row["net_return"],
                "CAGR": row["CAGR"],
                "net_active_return_vs_benchmark": row["net_active_return_vs_benchmark"],
                "net_active_CAGR_vs_benchmark": row["net_active_CAGR_vs_benchmark"],
                "maximum_drawdown": row["maximum_drawdown"],
                "maximum_drawdown_difference_vs_benchmark": row[
                    "maximum_drawdown_difference_vs_benchmark"
                ],
                "annualised_turnover": row["annualised_turnover"],
                "cost_drag": row["cost_drag"],
                "maximum_HHI": row["maximum_HHI"],
                "positive_fold_count": positive_fold_count,
                "largest_fold_return_share": fold_share,
                "largest_regime_return_share": regime_share,
            }
        )
    gate_board = pd.DataFrame(gate_rows)
    scoreboard = pd.DataFrame(score_rows)
    scoreboard["_status_order"] = (
        scoreboard["historical_robustness_status"] == "passes_all_predeclared_historical_gates"
    ).astype(int)
    scoreboard = scoreboard.sort_values(
        [
            "_status_order",
            "gates_passed_count",
            "net_active_CAGR_vs_benchmark",
            "maximum_drawdown_difference_vs_benchmark",
            "annualised_turnover",
            "strategy_id",
            "universe_arm",
        ],
        ascending=[False, False, False, False, True, True, True],
        kind="mergesort",
    ).drop(columns="_status_order")
    scoreboard.insert(0, "reporting_rank", range(1, len(scoreboard) + 1))
    return gate_board, scoreboard


def evaluate_tournament(inputs: FrozenInputs, prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    global _CURRENT_STRATEGY_ROWS
    _CURRENT_STRATEGY_ROWS = inputs.strategy_rows
    paths: dict[str, TrialPath] = {}
    for row in inputs.strategy_rows:
        arm = inputs.arms[row["eligible_universe_arm"]]
        paths[row["arm_trial_id"]] = build_trial_path(row, prices, arm)
    _require(len(paths) == 160, "exactly 160 trial paths must execute")
    benchmark_paths: dict[str, TrialPath] = {}
    for arm in (CORE_ARM, EXPANDED_ARM):
        matches = [
            path
            for path in paths.values()
            if path.universe_arm == arm
            and path.strategy_id == "gma8_benchmark_equal_weight_monthly_v1"
        ]
        _require(len(matches) == 1, f"same-arm monthly benchmark missing: {arm}")
        benchmark_paths[arm] = matches[0]

    full_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    for path in paths.values():
        for scenario, cost_bps in inputs.costs.items():
            frame = apply_cost(path, cost_bps)
            benchmark_frame = apply_cost(benchmark_paths[path.universe_arm], cost_bps)
            metrics = _metric_values(frame)
            benchmark_metrics = _metric_values(benchmark_frame)
            full_rows.append(
                {
                    **_base_identity(path, scenario, cost_bps),
                    "evaluation_scope": "full_history",
                    "first_target_effective_session": path.first_target_effective_session,
                    "actual_first_return_session": path.actual_first_return_session,
                    **metrics,
                    **_active_fields(metrics, benchmark_metrics),
                }
            )
            for fold in inputs.folds:
                trial_window = _window(frame, fold["start_date"], fold["end_date"])
                benchmark_window = _window(benchmark_frame, fold["start_date"], fold["end_date"])
                trial_metrics = _metric_values(trial_window)
                benchmark_fold = _metric_values(benchmark_window)
                fold_rows.append(
                    {
                        **_base_identity(path, scenario, cost_bps),
                        "fold_id": fold["fold_id"],
                        "requested_start": fold["start_date"],
                        "requested_end": fold["end_date"],
                        **trial_metrics,
                        **_active_fields(trial_metrics, benchmark_fold),
                    }
                )
            for regime in inputs.regimes:
                requested_end = (
                    COMMON_END
                    if regime["end_date"] == "gma8b_frozen_endpoint"
                    else regime["end_date"]
                )
                trial_window = _window(frame, regime["start_date"], requested_end)
                benchmark_window = _window(benchmark_frame, regime["start_date"], requested_end)
                trial_metrics = _metric_values(trial_window)
                benchmark_regime = _metric_values(benchmark_window)
                coverage = (
                    "full_coverage"
                    if trial_metrics["period_start"] <= regime["start_date"]
                    and trial_metrics["period_end"] >= requested_end
                    else "partial_coverage"
                )
                regime_rows.append(
                    {
                        **_base_identity(path, scenario, cost_bps),
                        "regime_id": regime["regime_id"],
                        "requested_start": regime["start_date"],
                        "requested_end": requested_end,
                        "coverage_status": coverage,
                        **trial_metrics,
                        **_active_fields(trial_metrics, benchmark_regime),
                    }
                )
            for window_type, sessions in inputs.config["evaluation"][
                "rolling_windows_sessions"
            ].items():
                rolling_rows.append(
                    _rolling_summary(path, frame, scenario, cost_bps, window_type, int(sessions))
                )
    full = pd.DataFrame(full_rows)
    folds = pd.DataFrame(fold_rows)
    regimes = pd.DataFrame(regime_rows)
    rolling = pd.DataFrame(rolling_rows)
    _require(len(full) == 640, "full-history output must contain 640 rows")
    _require(len(folds) == 3200, "fold output must contain 3200 rows")
    _require(len(regimes) == 4480, "regime output must contain 4480 rows")
    _require(len(rolling) == 1280, "rolling output must contain 1280 rows")
    gates, scoreboard = _gate_rows_and_scoreboard(full, folds, regimes)
    _require(len(gates) == 960, "gate board must contain 960 rows")
    _require(len(scoreboard) == 160, "scoreboard must contain 160 rows")
    return {
        "scoreboard": scoreboard,
        "full": full,
        "folds": folds,
        "regimes": regimes,
        "rolling": rolling,
        "gates": gates,
    }


def _csv_text(frame: pd.DataFrame) -> str:
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.12g")


def _summary_markdown(tables: dict[str, pd.DataFrame]) -> str:
    scoreboard = tables["scoreboard"]
    full = tables["full"]
    pass_count = int(
        (
            scoreboard["historical_robustness_status"] == "passes_all_predeclared_historical_gates"
        ).sum()
    )
    cost_summary = (
        full.groupby("cost_scenario", sort=False)[
            ["CAGR", "net_active_CAGR_vs_benchmark", "annualised_turnover"]
        ]
        .median()
        .reset_index()
    )
    compact = scoreboard.head(20)[
        [
            "reporting_rank",
            "strategy_id",
            "universe_arm",
            "gates_passed_count",
            "net_active_CAGR_vs_benchmark",
            "maximum_drawdown_difference_vs_benchmark",
            "annualised_turnover",
        ]
    ]
    return "\n".join(
        [
            "# GMA-8C Frozen ETF/ETP Historical Tournament V1",
            "",
            "GMA-8C executes the frozen historical ETF/ETP strategy tournament using GMA-8A rules and GMA-8B verified immutable adjusted-price evidence.",
            "All results are observed development evidence, not a pristine final holdout.",
            "Highest historical CAGR or Sharpe alone is not a selection rule.",
            "No execution or promotion decision is produced.",
            "",
            "## Execution Scope",
            "",
            "- Fixed templates: `80`",
            "- Arm-level trials: `160`",
            "- Cost scenarios: `baseline_1bps`, `stressed_10bps`, `stressed_25bps`, `severe_50bps`",
            "- Common comparable start: `2008-05-29`",
            "- Frozen endpoint: `2026-05-01`",
            f"- Trials passing all six historical gates: `{pass_count}`",
            "",
            "The ordering below is a reporting convention for historical robustness evidence only.",
            "",
            "## Stressed 10 bps Compact Board",
            "",
            compact.to_markdown(index=False, floatfmt=".6f"),
            "",
            "## Cost Sensitivity",
            "",
            cost_summary.to_markdown(index=False, floatfmt=".6f"),
            "",
        ]
    )


def build_artifacts(inputs: FrozenInputs, tables: dict[str, pd.DataFrame]) -> dict[str, str]:
    artifacts = {
        OUTPUT_FILENAMES[0]: _csv_text(tables["scoreboard"]),
        OUTPUT_FILENAMES[1]: _csv_text(tables["full"]),
        OUTPUT_FILENAMES[2]: _csv_text(tables["folds"]),
        OUTPUT_FILENAMES[3]: _csv_text(tables["regimes"]),
        OUTPUT_FILENAMES[4]: _csv_text(tables["rolling"]),
        OUTPUT_FILENAMES[5]: _csv_text(tables["gates"]),
        OUTPUT_FILENAMES[6]: _summary_markdown(tables),
    }
    data_hashes = {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in artifacts.items()
    }
    manifest = {
        "contract_id": CONTRACT_ID,
        "run_id": "gma8c_frozen_160_trial_v1",
        "trial_template_count": 80,
        "arm_trial_count": 160,
        "executed_arm_trial_count": 160,
        "cost_scenario_count": 4,
        "cost_scenarios": ["baseline_1bps", "stressed_10bps", "stressed_25bps", "severe_50bps"],
        "data_source_kind": "29_per_ticker_immutable_normalised_adjusted_price_series",
        "source_first_session": SOURCE_START,
        "source_last_session": SOURCE_END,
        "common_comparable_start": COMMON_START,
        "common_comparable_end": COMMON_END,
        "historical_price_files_reverified": True,
        "data_download_performed": False,
        "indicator_calculation_performed": True,
        "model_fit_performed": False,
        "backtest_performed": True,
        "strategy_ranking_performed": True,
        "portfolio_target_generated": False,
        "paper_session_created": False,
        "broker_or_real_money_action_created": False,
        "parent_file_sha256": inputs.parent_hashes,
        "adjusted_price_series_sha256": {
            row["ticker"]: row["normalised_series_sha256"] for row in inputs.source_rows
        },
        "output_sha256": data_hashes,
        "wall_clock_timestamp_recorded": False,
    }
    artifacts[OUTPUT_FILENAMES[7]] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    lock_hashes = {
        name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in artifacts.items()
    }
    lock = {
        "contract_id": CONTRACT_ID,
        "run_id": "gma8c_frozen_160_trial_v1",
        "strategy_grid_hash": GRID_HASH,
        "gma8a_lock_sha256": GMA8A_LOCK_HASH,
        "gma8b_data_lock_sha256": GMA8B_LOCK_HASH,
        "artifact_sha256": lock_hashes,
        "historical_robustness_pass_count": int(
            (
                tables["scoreboard"]["historical_robustness_status"]
                == "passes_all_predeclared_historical_gates"
            ).sum()
        ),
        "observed_development_evidence": True,
        "pristine_final_holdout": False,
        "execution_or_promotion_decision_produced": False,
    }
    artifacts[OUTPUT_FILENAMES[8]] = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    return artifacts


def generate(
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    worktree_root: str | Path = ".",
) -> TournamentResult:
    inputs = load_frozen_inputs(config_path, worktree_root)
    prices = load_price_matrix(inputs)
    tables = evaluate_tournament(inputs, prices)
    artifacts = build_artifacts(inputs, tables)
    root = Path(output_root)
    if not root.is_absolute():
        root = Path(worktree_root).resolve() / root
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name in OUTPUT_FILENAMES:
        path = root / name
        path.write_text(artifacts[name], encoding="utf-8", newline="")
        paths.append(path)
    return TournamentResult(artifacts, tables["scoreboard"], paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute the frozen GMA-8C ETF/ETP tournament")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    result = generate(args.config, args.output_root)
    pass_count = int(
        (
            result.scoreboard["historical_robustness_status"]
            == "passes_all_predeclared_historical_gates"
        ).sum()
    )
    print(f"contract_id={CONTRACT_ID}")
    print("trial_template_count=80")
    print("executed_arm_trial_count=160")
    print("cost_scenario_count=4")
    print(f"historical_robustness_pass_count={pass_count}")
    print("observed_development_evidence=true")
    print("execution_or_promotion_decision_produced=false")
    for path in result.output_paths:
        print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
