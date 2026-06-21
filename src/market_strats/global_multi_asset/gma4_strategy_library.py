"""GMA-4 registered strategy target resolvers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from market_strats.global_multi_asset.gma2_replay import normalise_weights
from market_strats.global_multi_asset.gma4_contract import FIXED_GMA4_UNIVERSE

BIL = "BIL"
RISK_ASSETS = [symbol for symbol in FIXED_GMA4_UNIVERSE if symbol != BIL]
MONTHLY_SESSION_LOOKBACK = 21


@dataclass(frozen=True)
class GMA4TrialRule:
    trial_id: str
    rebalance_schedule: str
    required_lookback_sessions: int
    resolver: Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]


def _dates_on_or_before(prices: dict[str, pd.DataFrame], symbol: str, value: Any) -> list[Any]:
    return [item for item in prices[symbol].index if item <= value]


def _price(
    prices: dict[str, pd.DataFrame], symbol: str, value: Any, field: str = "total_return_index"
) -> float:
    return float(prices[symbol].loc[value, field])


def _trailing_return(
    prices: dict[str, pd.DataFrame], symbol: str, value: Any, lookback_sessions: int
) -> float:
    dates = _dates_on_or_before(prices, symbol, value)
    if len(dates) <= lookback_sessions:
        return 0.0
    return (
        _price(prices, symbol, dates[-1]) / _price(prices, symbol, dates[-lookback_sessions - 1])
        - 1.0
    )


def _realised_volatility(
    prices: dict[str, pd.DataFrame], symbol: str, value: Any, lookback_sessions: int = 63
) -> float:
    dates = _dates_on_or_before(prices, symbol, value)
    if len(dates) < lookback_sessions:
        return 1.0
    use = dates[-lookback_sessions:]
    values = pd.Series([_price(prices, symbol, item) for item in use], dtype="float64")
    returns = values.pct_change().dropna()
    vol = float(returns.std(ddof=0))
    return vol if math.isfinite(vol) and vol > 0 else 1.0


def _above_moving_average(
    prices: dict[str, pd.DataFrame], symbol: str, value: Any, lookback_sessions: int
) -> bool:
    dates = _dates_on_or_before(prices, symbol, value)
    if len(dates) < lookback_sessions:
        return False
    values = [_price(prices, symbol, item) for item in dates[-lookback_sessions:]]
    return _price(prices, symbol, dates[-1]) > sum(values) / len(values)


def _drawdown(
    prices: dict[str, pd.DataFrame], symbol: str, value: Any, lookback_sessions: int
) -> float:
    dates = _dates_on_or_before(prices, symbol, value)
    if len(dates) < lookback_sessions:
        return 0.0
    use = dates[-lookback_sessions:]
    current = _price(prices, symbol, use[-1])
    peak = max(_price(prices, symbol, item) for item in use)
    return current / peak - 1.0


def _cap_with_bil_residual(weights: dict[str, float], cap: float = 0.35) -> dict[str, float]:
    normalised = normalise_weights(weights)
    capped: dict[str, float] = {}
    residual = 0.0
    for symbol, weight in normalised.items():
        symbol_cap = 1.0 if symbol == BIL else cap
        clipped = min(weight, symbol_cap)
        capped[symbol] = clipped
        residual += weight - clipped
    capped[BIL] = capped.get(BIL, 0.0) + residual
    return normalise_weights(capped)


def _equal_weight(symbols: list[str]) -> dict[str, float]:
    return (
        {BIL: 1.0} if not symbols else _cap_with_bil_residual({symbol: 1.0 for symbol in symbols})
    )


def _inverse_vol_weight(
    prices: dict[str, pd.DataFrame], symbols: list[str], value: Any, lookback_sessions: int = 63
) -> dict[str, float]:
    if not symbols:
        return {BIL: 1.0}
    raw = {
        symbol: 1.0 / _realised_volatility(prices, symbol, value, lookback_sessions)
        for symbol in symbols
    }
    return _cap_with_bil_residual(raw)


def _single(symbol: str) -> Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]:
    def resolver(_value: Any, _prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        return {symbol: 1.0}

    return resolver


def _equal_22(_value: Any, _prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    return normalise_weights({symbol: 1.0 for symbol in FIXED_GMA4_UNIVERSE})


def _absolute_trend(
    lookback_months: int, weighting: str
) -> Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]:
    lookback = lookback_months * MONTHLY_SESSION_LOOKBACK

    def resolver(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        bil_return = _trailing_return(prices, BIL, value, lookback)
        selected = [
            symbol
            for symbol in RISK_ASSETS
            if _trailing_return(prices, symbol, value, lookback) > bil_return
        ]
        return (
            _inverse_vol_weight(prices, selected, value)
            if weighting == "inverse_volatility"
            else _equal_weight(selected)
        )

    return resolver


def _xsmom(
    lookback_months: int, top_n: int, weighting: str
) -> Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]:
    lookback = lookback_months * MONTHLY_SESSION_LOOKBACK

    def resolver(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        bil_return = _trailing_return(prices, BIL, value, lookback)
        ranked = sorted(
            ((symbol, _trailing_return(prices, symbol, value, lookback)) for symbol in RISK_ASSETS),
            key=lambda item: item[1],
            reverse=True,
        )
        selected = [symbol for symbol, score in ranked if score > bil_return][:top_n]
        return (
            _inverse_vol_weight(prices, selected, value)
            if weighting == "inverse_volatility"
            else _equal_weight(selected)
        )

    return resolver


def _mean_reversion(
    lookback_days: int, long_trend_filter: bool = False
) -> Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]:
    def resolver(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        ranked = sorted(
            (
                (symbol, _trailing_return(prices, symbol, value, lookback_days))
                for symbol in RISK_ASSETS
            ),
            key=lambda item: item[1],
        )
        selected = [symbol for symbol, _score in ranked[:3]]
        if long_trend_filter:
            selected = [
                symbol for symbol in selected if _above_moving_average(prices, symbol, value, 200)
            ]
        return _equal_weight(selected)

    return resolver


def _defensive_inverse_vol(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    return _inverse_vol_weight(prices, FIXED_GMA4_UNIVERSE, value)


def _risk_on_diversified() -> dict[str, float]:
    return _cap_with_bil_residual(
        {
            "SPY": 0.20,
            "QQQ": 0.15,
            "IWM": 0.10,
            "EFA": 0.10,
            "EEM": 0.05,
            "IEF": 0.15,
            "TLT": 0.10,
            "GLD": 0.10,
            "DBC": 0.05,
        }
    )


def _risk_off_defensive() -> dict[str, float]:
    return _cap_with_bil_residual(
        {"BIL": 0.35, "IEF": 0.25, "TLT": 0.15, "AGG": 0.10, "GLD": 0.10, "DBC": 0.05}
    )


def _spy_200d_rotation(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    return (
        _risk_on_diversified()
        if _above_moving_average(prices, "SPY", value, 200)
        else _risk_off_defensive()
    )


def _drawdown_guard(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    return (
        _risk_off_defensive()
        if _drawdown(prices, "SPY", value, 252) <= -0.10
        else _risk_on_diversified()
    )


def _blend(
    component_ids: list[str], component_weights: list[float] | None = None
) -> Callable[[Any, dict[str, pd.DataFrame]], dict[str, float]]:
    def resolver(value: Any, prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        rules = build_gma4_trial_rules()
        weights = component_weights or [1.0 / len(component_ids)] * len(component_ids)
        total: dict[str, float] = {}
        for component_id, component_weight in zip(component_ids, weights):
            component = rules[component_id].resolver(value, prices)
            for symbol, weight in component.items():
                total[symbol] = total.get(symbol, 0.0) + weight * component_weight
        return _cap_with_bil_residual(total)

    return resolver


def build_gma4_trial_rules() -> dict[str, GMA4TrialRule]:
    return {
        "gma4_benchmark_bil_buy_hold_v1": GMA4TrialRule(
            "gma4_benchmark_bil_buy_hold_v1", "monthly_last_session_next_open", 0, _single("BIL")
        ),
        "gma4_benchmark_spy_buy_hold_v1": GMA4TrialRule(
            "gma4_benchmark_spy_buy_hold_v1", "monthly_last_session_next_open", 0, _single("SPY")
        ),
        "gma4_benchmark_equal_weight_22_monthly_v1": GMA4TrialRule(
            "gma4_benchmark_equal_weight_22_monthly_v1",
            "monthly_last_session_next_open",
            0,
            _equal_22,
        ),
        "gma4_abs_trend_10m_equal_weight_v1": GMA4TrialRule(
            "gma4_abs_trend_10m_equal_weight_v1",
            "monthly_last_session_next_open",
            210,
            _absolute_trend(10, "equal_weight"),
        ),
        "gma4_abs_trend_12m_equal_weight_v1": GMA4TrialRule(
            "gma4_abs_trend_12m_equal_weight_v1",
            "monthly_last_session_next_open",
            252,
            _absolute_trend(12, "equal_weight"),
        ),
        "gma4_abs_trend_10m_inverse_vol_v1": GMA4TrialRule(
            "gma4_abs_trend_10m_inverse_vol_v1",
            "monthly_last_session_next_open",
            210,
            _absolute_trend(10, "inverse_volatility"),
        ),
        "gma4_abs_trend_12m_inverse_vol_v1": GMA4TrialRule(
            "gma4_abs_trend_12m_inverse_vol_v1",
            "monthly_last_session_next_open",
            252,
            _absolute_trend(12, "inverse_volatility"),
        ),
        "gma4_xsmom_6m_top3_equal_weight_v1": GMA4TrialRule(
            "gma4_xsmom_6m_top3_equal_weight_v1",
            "monthly_last_session_next_open",
            126,
            _xsmom(6, 3, "equal_weight"),
        ),
        "gma4_xsmom_12m_top3_equal_weight_v1": GMA4TrialRule(
            "gma4_xsmom_12m_top3_equal_weight_v1",
            "monthly_last_session_next_open",
            252,
            _xsmom(12, 3, "equal_weight"),
        ),
        "gma4_xsmom_6m_top5_inverse_vol_v1": GMA4TrialRule(
            "gma4_xsmom_6m_top5_inverse_vol_v1",
            "monthly_last_session_next_open",
            126,
            _xsmom(6, 5, "inverse_volatility"),
        ),
        "gma4_xsmom_12m_top5_inverse_vol_v1": GMA4TrialRule(
            "gma4_xsmom_12m_top5_inverse_vol_v1",
            "monthly_last_session_next_open",
            252,
            _xsmom(12, 5, "inverse_volatility"),
        ),
        "gma4_meanrev_5d_bottom3_equal_weight_v1": GMA4TrialRule(
            "gma4_meanrev_5d_bottom3_equal_weight_v1",
            "weekly_friday_next_open",
            5,
            _mean_reversion(5),
        ),
        "gma4_meanrev_10d_bottom3_equal_weight_v1": GMA4TrialRule(
            "gma4_meanrev_10d_bottom3_equal_weight_v1",
            "weekly_friday_next_open",
            10,
            _mean_reversion(10),
        ),
        "gma4_meanrev_5d_bottom3_long_trend_filter_v1": GMA4TrialRule(
            "gma4_meanrev_5d_bottom3_long_trend_filter_v1",
            "weekly_friday_next_open",
            200,
            _mean_reversion(5, True),
        ),
        "gma4_defensive_inverse_vol_63d_v1": GMA4TrialRule(
            "gma4_defensive_inverse_vol_63d_v1",
            "weekly_friday_next_open",
            63,
            _defensive_inverse_vol,
        ),
        "gma4_defensive_spy_200d_rotation_v1": GMA4TrialRule(
            "gma4_defensive_spy_200d_rotation_v1",
            "weekly_friday_next_open",
            200,
            _spy_200d_rotation,
        ),
        "gma4_defensive_drawdown_guard_v1": GMA4TrialRule(
            "gma4_defensive_drawdown_guard_v1", "weekly_friday_next_open", 252, _drawdown_guard
        ),
        "gma4_blend_equal_abs12_xsmom12_v1": GMA4TrialRule(
            "gma4_blend_equal_abs12_xsmom12_v1",
            "monthly_last_session_next_open",
            252,
            _blend(["gma4_abs_trend_12m_equal_weight_v1", "gma4_xsmom_12m_top3_equal_weight_v1"]),
        ),
        "gma4_blend_risk_abs12_xsmom6_meanrev5_v1": GMA4TrialRule(
            "gma4_blend_risk_abs12_xsmom6_meanrev5_v1",
            "monthly_last_session_next_open",
            252,
            _blend(
                [
                    "gma4_abs_trend_12m_inverse_vol_v1",
                    "gma4_xsmom_6m_top5_inverse_vol_v1",
                    "gma4_meanrev_5d_bottom3_equal_weight_v1",
                ],
                [0.40, 0.35, 0.25],
            ),
        ),
        "gma4_blend_equal_abs10_xsmom6_defensive_v1": GMA4TrialRule(
            "gma4_blend_equal_abs10_xsmom6_defensive_v1",
            "monthly_last_session_next_open",
            252,
            _blend(
                [
                    "gma4_abs_trend_10m_equal_weight_v1",
                    "gma4_xsmom_6m_top3_equal_weight_v1",
                    "gma4_defensive_drawdown_guard_v1",
                ]
            ),
        ),
    }


def trial_required_lookback_sessions(trial_id: str) -> int:
    return build_gma4_trial_rules()[trial_id].required_lookback_sessions
