"""Reusable GMA-4 replay adapter backed by GMA-3A accounting machinery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from market_strats.global_multi_asset.gma2_replay import normalise_weights
from market_strats.global_multi_asset.gma4_contract import FIXED_GMA4_UNIVERSE
from market_strats.global_multi_asset.gma3a_tournament import _simulate_strategy

GMA4_ALLOWED_TARGET_SYMBOLS = set(FIXED_GMA4_UNIVERSE) | {"CASH"}
GMA4_REQUIRED_PRICE_COLUMNS = ["close_raw", "total_return_index"]
GMA4_SUPPORTED_SCHEDULES = {
    "weekly_friday_next_open",
    "monthly_last_session_next_open",
}


class GMA4ReplayAdapterError(ValueError):
    """Fail-closed error for GMA-4 replay adapter validation."""


@dataclass(frozen=True)
class GMA4ReplayConfig:
    starting_capital: float = 100000.0
    cost_bps_per_notional: float = 1.0
    minimum_trade_notional: float = 1.0
    maximum_single_asset_weight: float = 1.0
    maximum_bitcoin_weight: float = 0.0

    @property
    def raw(self) -> dict[str, Any]:
        return {
            "capital": {"account_starting_capital": self.starting_capital},
            "costs": {"bps_per_notional": self.cost_bps_per_notional},
            "limits": {
                "minimum_trade_notional": self.minimum_trade_notional,
                "maximum_single_asset_weight": self.maximum_single_asset_weight,
                "maximum_bitcoin_weight": self.maximum_bitcoin_weight,
            },
        }


@dataclass(frozen=True)
class GMA4ReplayAdapterResult:
    equity: pd.DataFrame
    drawdown: pd.DataFrame
    holdings: pd.DataFrame
    orders: pd.DataFrame
    fills: pd.DataFrame
    costs: pd.DataFrame
    signals: pd.DataFrame
    signal_dates: list[Any]
    execution_dates: list[Any]


GMA4TargetResolver = Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]


def _normalise_price_index(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if "date" in frame.columns:
        if frame["date"].duplicated().any():
            raise GMA4ReplayAdapterError(f"{symbol} has duplicate dates")
        result = frame.copy()
        result["date"] = pd.to_datetime(result["date"]).dt.date
        result = result.set_index("date")
    else:
        if frame.index.duplicated().any():
            raise GMA4ReplayAdapterError(f"{symbol} has duplicate dates")
        result = frame.copy()
        result.index = pd.to_datetime(result.index).date
    result = result.sort_index()
    missing = [column for column in GMA4_REQUIRED_PRICE_COLUMNS if column not in result.columns]
    if missing:
        raise GMA4ReplayAdapterError(f"{symbol} missing required price columns: {missing}")
    for column in GMA4_REQUIRED_PRICE_COLUMNS:
        values = pd.to_numeric(result[column], errors="coerce")
        if values.isna().any():
            raise GMA4ReplayAdapterError(f"{symbol} has null required price values in {column}")
        if values.le(0).any():
            raise GMA4ReplayAdapterError(
                f"{symbol} has non-positive required price values in {column}"
            )
        result[column] = values
    if result.empty:
        raise GMA4ReplayAdapterError(f"{symbol} has no price observations")
    return result


def validate_gma4_price_inputs(
    prices: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    observed = set(prices)
    required = set(FIXED_GMA4_UNIVERSE)
    missing = sorted(required - observed)
    if missing:
        raise GMA4ReplayAdapterError(f"missing fixed GMA-4 ETF inputs: {missing}")
    unexpected = sorted(observed - required)
    if unexpected:
        raise GMA4ReplayAdapterError(f"unexpected GMA-4 price inputs: {unexpected}")
    return {
        symbol: _normalise_price_index(prices[symbol], symbol) for symbol in FIXED_GMA4_UNIVERSE
    }


def _common_dates(prices: dict[str, pd.DataFrame]) -> list[Any]:
    common = set(prices[FIXED_GMA4_UNIVERSE[0]].index)
    for symbol in FIXED_GMA4_UNIVERSE[1:]:
        common &= set(prices[symbol].index)
    dates = sorted(common)
    if len(dates) < 2:
        raise GMA4ReplayAdapterError("GMA-4 replay requires at least two common sessions")
    return dates


def build_gma4_rebalance_signal_dates(dates: list[Any], schedule: str) -> list[Any]:
    if schedule not in GMA4_SUPPORTED_SCHEDULES:
        raise GMA4ReplayAdapterError(f"unsupported GMA-4 schedule: {schedule}")
    executable_signal_dates = dates[:-1]
    if schedule == "weekly_friday_next_open":
        return [date for date in executable_signal_dates if pd.Timestamp(date).dayofweek == 4]
    return [
        dates[idx]
        for idx in range(len(dates) - 1)
        if pd.Timestamp(dates[idx]).to_period("M") != pd.Timestamp(dates[idx + 1]).to_period("M")
    ]


def _validate_and_cache_targets(
    *,
    target_resolver: GMA4TargetResolver,
    signal_dates: list[Any],
    prices: dict[str, pd.DataFrame],
) -> dict[Any, tuple[dict[str, float], dict[str, str]]]:
    cached: dict[Any, tuple[dict[str, float], dict[str, str]]] = {}
    for signal_date in signal_dates:
        raw_targets = target_resolver(signal_date, prices)
        target_symbols = set(raw_targets)
        forbidden = sorted(target_symbols - GMA4_ALLOWED_TARGET_SYMBOLS)
        if forbidden:
            raise GMA4ReplayAdapterError(f"forbidden GMA-4 target symbols: {forbidden}")
        cached[signal_date] = (
            normalise_weights(raw_targets),
            {"reason_code": "gma4_synthetic_test_resolver"},
        )
    return cached


def run_gma4_replay_adapter(
    *,
    prices: dict[str, pd.DataFrame],
    cash: pd.DataFrame,
    macro: pd.DataFrame | None,
    target_resolver: GMA4TargetResolver,
    rebalance_schedule: str,
    strategy_id: str = "gma4_synthetic_adapter_trial",
    strategy_version: str = "test_only_v0",
    config: GMA4ReplayConfig | None = None,
    minimum_signal_date: Any | None = None,
) -> GMA4ReplayAdapterResult:
    validated_prices = validate_gma4_price_inputs(prices)
    dates = _common_dates(validated_prices)
    signal_dates = build_gma4_rebalance_signal_dates(dates, rebalance_schedule)
    if minimum_signal_date is not None:
        signal_dates = [date for date in signal_dates if date >= minimum_signal_date]
    if not signal_dates:
        raise GMA4ReplayAdapterError("GMA-4 replay schedule produced no signal dates")
    cached_targets = _validate_and_cache_targets(
        target_resolver=target_resolver,
        signal_dates=signal_dates,
        prices=validated_prices,
    )

    def cached_resolver(
        _strategy_id: str,
        signal_date: Any,
        _prices: dict[str, pd.DataFrame],
        _macro: pd.DataFrame,
        _config: Any,
        _tactical_passers: list[str] | None = None,
    ) -> tuple[dict[str, float], dict[str, str]]:
        return cached_targets[signal_date]

    outputs = _simulate_strategy(
        strategy_id=strategy_id,
        dates=dates,
        prices=validated_prices,
        cash_df=cash.copy(),
        macro=macro.copy() if macro is not None else pd.DataFrame(),
        config=config or GMA4ReplayConfig(),  # type: ignore[arg-type]
        target_resolver=cached_resolver,
        rebalance_signal_dates=set(signal_dates),
        strategy_version=strategy_version,
    )
    execution_dates = (
        outputs["signals"]["execution_date"].drop_duplicates().tolist()
        if not outputs["signals"].empty
        else []
    )
    return GMA4ReplayAdapterResult(
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
