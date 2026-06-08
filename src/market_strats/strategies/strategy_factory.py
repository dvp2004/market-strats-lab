from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


STRATEGY_FACTORY_CANDIDATES = [
    "sf_spy_buy_hold",
    "sf_spy_qqq_60_40_monthly_rebalanced",
    "sf_spy_qqq_tactical_momentum",
    "sf_spy_qqq_gld_tlt_risk_off_rotation",
    "sf_spy_core_phase6_overlay_satellite_qqq",
    "sf_spy_qqq_btc_capped_offensive",
]

FACTORY_ASSETS = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD", "CASH"]


@dataclass(frozen=True)
class StrategyFactoryConfig:
    initial_capital: float = 10000.0
    btc_max_weight: float = 0.10
    qqq_satellite_max_weight: float = 0.40
    momentum_lookback_days: int = 126
    trend_lookback_days: int = 200


def _normalise_ticker(ticker: str) -> str:
    return ticker.upper()


def _price_frame(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    required = {"date", "adj_close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"{ticker} price frame missing columns: {sorted(missing)}")

    out = prices[["date", "adj_close"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["adj_close"] = out["adj_close"].astype(float)
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    return out.rename(columns={"adj_close": ticker})


def build_strategy_factory_price_panel(
    price_data: dict[str, pd.DataFrame],
    *,
    cash_returns: pd.Series | None = None,
) -> pd.DataFrame:
    tickers = [_normalise_ticker(ticker) for ticker in price_data]
    if not tickers:
        raise ValueError("price_data cannot be empty")

    panel: pd.DataFrame | None = None
    for ticker in tickers:
        frame = _price_frame(price_data[ticker], ticker)
        panel = frame if panel is None else panel.merge(frame, on="date", how="inner")

    if panel is None or panel.empty:
        raise ValueError("No common dates across Strategy Factory price data")

    panel = panel.sort_values("date").reset_index(drop=True)

    for ticker in tickers:
        panel[f"{ticker}_return"] = panel[ticker].pct_change().fillna(0.0)

    if cash_returns is None:
        panel["CASH_return"] = 0.0
    else:
        aligned_cash = cash_returns.copy()
        aligned_cash.index = pd.to_datetime(aligned_cash.index)
        panel["CASH_return"] = (
            aligned_cash.reindex(pd.to_datetime(panel["date"]))
            .ffill()
            .fillna(0.0)
            .to_numpy()
        )

    return panel


def _month_end_mask(dates: pd.Series) -> pd.Series:
    periods = pd.to_datetime(dates).dt.to_period("M")
    return periods.ne(periods.shift(-1)).fillna(True)


def _empty_weights(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=index, columns=FACTORY_ASSETS)


def _rebalance_next_day_mask(dates: pd.Series) -> pd.Series:
    month_end = _month_end_mask(dates)
    return month_end.shift(1, fill_value=True).astype(bool)


def _next_day_targets(
    panel: pd.DataFrame,
    monthly_weights: dict[int, dict[str, float]],
    *,
    default_weights: dict[str, float],
) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(np.nan, index=panel.index, columns=FACTORY_ASSETS)
    first_row = _cash_weight_row(**default_weights)
    for asset in FACTORY_ASSETS:
        weights.loc[0, asset] = float(first_row.get(asset, 0.0))

    rebalance_mask = pd.Series(False, index=panel.index)
    rebalance_mask.iloc[0] = True

    for signal_index, target in monthly_weights.items():
        execution_index = signal_index + 1
        if execution_index >= len(panel):
            continue
        for asset in FACTORY_ASSETS:
            weights.loc[execution_index, asset] = float(target.get(asset, 0.0))
        rebalance_mask.iloc[execution_index] = True

    weights = weights.ffill().fillna(0.0)
    return weights, rebalance_mask


def _assert_valid_weights(weights: pd.DataFrame) -> None:
    asset_cols = [asset for asset in FACTORY_ASSETS if asset in weights.columns]
    if (weights[asset_cols] < -1e-9).any().any():
        raise ValueError("Strategy Factory weights cannot be negative")
    totals = weights[asset_cols].sum(axis=1)
    if not np.allclose(totals, 1.0, atol=1e-8):
        raise ValueError("Strategy Factory weights must sum to 1")


def _result_from_weight_targets(
    panel: pd.DataFrame,
    target_weights: pd.DataFrame,
    *,
    rebalance_mask: pd.Series,
    strategy_name: str,
    initial_capital: float,
) -> pd.DataFrame:
    _assert_valid_weights(target_weights)

    return_cols = [f"{asset}_return" for asset in FACTORY_ASSETS]
    missing_returns = set(return_cols) - set(panel.columns)
    if missing_returns:
        raise ValueError(f"Price panel missing returns: {sorted(missing_returns)}")

    asset_returns = panel[return_cols].copy()
    asset_returns.columns = FACTORY_ASSETS

    current_weights = target_weights.iloc[0].astype(float)
    rows: list[dict] = []
    equity = float(initial_capital)
    previous_equity = equity

    for idx, date in enumerate(pd.to_datetime(panel["date"])):
        daily_returns = asset_returns.iloc[idx].astype(float)
        strategy_return = float((current_weights * daily_returns).sum())
        if idx == 0:
            strategy_return = 0.0

        equity = previous_equity * (1.0 + strategy_return)
        drifted_weights = current_weights * (1.0 + daily_returns)
        if drifted_weights.sum() > 0:
            drifted_weights = drifted_weights / drifted_weights.sum()

        turnover = 0.0
        if bool(rebalance_mask.iloc[idx]):
            new_weights = target_weights.iloc[idx].astype(float)
            turnover = float((drifted_weights - new_weights).abs().sum())
            current_weights = new_weights
        else:
            current_weights = drifted_weights

        reported_weights = target_weights.iloc[idx].astype(float)

        row = {
            "date": date,
            "adj_close": float(panel["SPY"].iloc[idx]),
            "strategy_return": strategy_return,
            "equity": equity,
            "position": float(1.0 - reported_weights.get("CASH", 0.0)),
            "cash_position": float(reported_weights.get("CASH", 0.0)),
            "turnover": turnover if idx > 0 else 1.0,
            "strategy": strategy_name,
        }
        for asset in FACTORY_ASSETS:
            row[f"{asset.lower().replace('-', '_')}_weight"] = float(
                reported_weights.get(asset, 0.0)
            )
        rows.append(row)
        previous_equity = equity

    return pd.DataFrame(rows)


def _momentum(panel: pd.DataFrame, asset: str, idx: int, lookback: int) -> float:
    if idx < lookback:
        return np.nan
    previous = float(panel[asset].iloc[idx - lookback])
    if previous <= 0:
        return np.nan
    return float(panel[asset].iloc[idx] / previous - 1.0)


def _trend_positive(panel: pd.DataFrame, asset: str, idx: int, lookback: int) -> bool:
    if idx < lookback:
        return False
    sma = float(panel[asset].iloc[idx - lookback + 1 : idx + 1].mean())
    return bool(float(panel[asset].iloc[idx]) > sma)


def _cash_weight_row(**weights: float) -> dict[str, float]:
    row = {asset: 0.0 for asset in FACTORY_ASSETS}
    for asset, weight in weights.items():
        row[asset] = float(weight)
    row["CASH"] = max(0.0, 1.0 - sum(row[asset] for asset in FACTORY_ASSETS if asset != "CASH"))
    return row


def run_sf_spy_buy_hold(panel: pd.DataFrame, config: StrategyFactoryConfig) -> pd.DataFrame:
    weights = _empty_weights(panel.index)
    weights["SPY"] = 1.0
    rebalance = pd.Series(False, index=panel.index)
    rebalance.iloc[0] = True
    return _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_buy_hold",
        initial_capital=config.initial_capital,
    )


def run_sf_spy_qqq_60_40_monthly_rebalanced(
    panel: pd.DataFrame,
    config: StrategyFactoryConfig,
) -> pd.DataFrame:
    weights = _empty_weights(panel.index)
    weights["SPY"] = 0.60
    weights["QQQ"] = 0.40
    rebalance = _rebalance_next_day_mask(panel["date"])
    return _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_qqq_60_40_monthly_rebalanced",
        initial_capital=config.initial_capital,
    )


def run_sf_spy_qqq_tactical_momentum(
    panel: pd.DataFrame,
    config: StrategyFactoryConfig,
) -> pd.DataFrame:
    monthly_weights: dict[int, dict[str, float]] = {}
    month_end = _month_end_mask(panel["date"])

    for idx in panel.index[month_end]:
        spy_momentum = _momentum(panel, "SPY", int(idx), config.momentum_lookback_days)
        qqq_momentum = _momentum(panel, "QQQ", int(idx), config.momentum_lookback_days)

        if np.nan_to_num(spy_momentum, nan=-np.inf) < 0 and np.nan_to_num(
            qqq_momentum, nan=-np.inf
        ) < 0:
            monthly_weights[int(idx)] = _cash_weight_row()
        elif np.nan_to_num(qqq_momentum, nan=-np.inf) > np.nan_to_num(
            spy_momentum, nan=-np.inf
        ):
            monthly_weights[int(idx)] = _cash_weight_row(QQQ=1.0)
        else:
            monthly_weights[int(idx)] = _cash_weight_row(SPY=1.0)

    weights, rebalance = _next_day_targets(
        panel,
        monthly_weights,
        default_weights={"SPY": 1.0},
    )
    return _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_qqq_tactical_momentum",
        initial_capital=config.initial_capital,
    )


def run_sf_spy_qqq_gld_tlt_risk_off_rotation(
    panel: pd.DataFrame,
    config: StrategyFactoryConfig,
) -> pd.DataFrame:
    monthly_weights: dict[int, dict[str, float]] = {}
    month_end = _month_end_mask(panel["date"])

    for idx in panel.index[month_end]:
        idx_int = int(idx)
        spy_momentum = _momentum(panel, "SPY", idx_int, config.momentum_lookback_days)
        spy_risk_on = bool(
            np.nan_to_num(spy_momentum, nan=-np.inf) > 0
            and _trend_positive(panel, "SPY", idx_int, config.trend_lookback_days)
        )

        if spy_risk_on:
            spy_mom = np.nan_to_num(
                _momentum(panel, "SPY", idx_int, config.momentum_lookback_days),
                nan=-np.inf,
            )
            qqq_mom = np.nan_to_num(
                _momentum(panel, "QQQ", idx_int, config.momentum_lookback_days),
                nan=-np.inf,
            )
            if spy_mom > 0 and qqq_mom > 0:
                monthly_weights[idx_int] = _cash_weight_row(SPY=0.5, QQQ=0.5)
            elif qqq_mom > spy_mom and qqq_mom > 0:
                monthly_weights[idx_int] = _cash_weight_row(QQQ=1.0)
            else:
                monthly_weights[idx_int] = _cash_weight_row(SPY=1.0)
        else:
            defensive = {
                "GLD": np.nan_to_num(
                    _momentum(panel, "GLD", idx_int, config.momentum_lookback_days),
                    nan=-np.inf,
                ),
                "TLT": np.nan_to_num(
                    _momentum(panel, "TLT", idx_int, config.momentum_lookback_days),
                    nan=-np.inf,
                ),
            }
            best_asset = max(defensive, key=defensive.get)
            if defensive[best_asset] > 0:
                monthly_weights[idx_int] = _cash_weight_row(**{best_asset: 1.0})
            else:
                monthly_weights[idx_int] = _cash_weight_row()

    weights, rebalance = _next_day_targets(
        panel,
        monthly_weights,
        default_weights={"SPY": 1.0},
    )
    return _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_qqq_gld_tlt_risk_off_rotation",
        initial_capital=config.initial_capital,
    )


def run_sf_spy_core_phase6_overlay_satellite_qqq(
    panel: pd.DataFrame,
    config: StrategyFactoryConfig,
    *,
    overlay_exposure: pd.Series | None = None,
) -> tuple[pd.DataFrame, str]:
    if overlay_exposure is None or overlay_exposure.empty:
        risk_on = [
            _trend_positive(panel, "SPY", int(idx), config.trend_lookback_days)
            and np.nan_to_num(
                _momentum(panel, "SPY", int(idx), config.momentum_lookback_days),
                nan=-np.inf,
            )
            > 0
            for idx in panel.index
        ]
        exposure = pd.Series(risk_on, index=panel.index, dtype=float)
        implementation_status = "simplified_prototype_no_phase6_stream_available"
    else:
        aligned = overlay_exposure.copy()
        aligned.index = pd.to_datetime(aligned.index)
        exposure = (
            aligned.reindex(pd.to_datetime(panel["date"]))
            .ffill()
            .fillna(0.0)
            .astype(float)
            .reset_index(drop=True)
        )
        implementation_status = "implemented_with_phase14g_corrected_visual_overlay_exposure"

    weights = _empty_weights(panel.index)
    satellite = float(config.qqq_satellite_max_weight)
    core = max(0.0, 1.0 - satellite)
    risk_on = exposure.clip(lower=0.0, upper=1.0)
    weights["SPY"] = core * risk_on
    weights["QQQ"] = satellite * risk_on
    weights["CASH"] = 1.0 - weights["SPY"] - weights["QQQ"]
    rebalance = _rebalance_next_day_mask(panel["date"])
    result = _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_core_phase6_overlay_satellite_qqq",
        initial_capital=config.initial_capital,
    )
    result["implementation_status"] = implementation_status
    return result, implementation_status


def run_sf_spy_qqq_btc_capped_offensive(
    panel: pd.DataFrame,
    config: StrategyFactoryConfig,
) -> pd.DataFrame:
    monthly_weights: dict[int, dict[str, float]] = {}
    month_end = _month_end_mask(panel["date"])
    btc_cap = float(config.btc_max_weight)

    for idx in panel.index[month_end]:
        idx_int = int(idx)
        spy_risk_on = bool(
            _trend_positive(panel, "SPY", idx_int, config.trend_lookback_days)
            and np.nan_to_num(
                _momentum(panel, "SPY", idx_int, config.momentum_lookback_days),
                nan=-np.inf,
            )
            > 0
        )
        btc_allowed = bool(
            spy_risk_on
            and np.nan_to_num(
                _momentum(panel, "BTC-USD", idx_int, config.momentum_lookback_days),
                nan=-np.inf,
            )
            > 0
        )
        btc_weight = btc_cap if btc_allowed else 0.0
        base_weight = 1.0 - btc_weight
        monthly_weights[idx_int] = _cash_weight_row(
            SPY=0.60 * base_weight,
            QQQ=0.40 * base_weight,
            **{"BTC-USD": btc_weight},
        )

    weights, rebalance = _next_day_targets(
        panel,
        monthly_weights,
        default_weights={"SPY": 0.60, "QQQ": 0.40},
    )
    return _result_from_weight_targets(
        panel,
        weights,
        rebalance_mask=rebalance,
        strategy_name="sf_spy_qqq_btc_capped_offensive",
        initial_capital=config.initial_capital,
    )


def run_strategy_factory_candidates(
    panel: pd.DataFrame,
    *,
    config: StrategyFactoryConfig | None = None,
    overlay_exposure: pd.Series | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    cfg = config or StrategyFactoryConfig()
    results: dict[str, pd.DataFrame] = {}
    status_rows: list[dict[str, str]] = []

    runners = {
        "sf_spy_buy_hold": lambda: (run_sf_spy_buy_hold(panel, cfg), "implemented"),
        "sf_spy_qqq_60_40_monthly_rebalanced": lambda: (
            run_sf_spy_qqq_60_40_monthly_rebalanced(panel, cfg),
            "implemented",
        ),
        "sf_spy_qqq_tactical_momentum": lambda: (
            run_sf_spy_qqq_tactical_momentum(panel, cfg),
            "implemented_fixed_126d_momentum",
        ),
        "sf_spy_qqq_gld_tlt_risk_off_rotation": lambda: (
            run_sf_spy_qqq_gld_tlt_risk_off_rotation(panel, cfg),
            "implemented_simple_trend_momentum_rotation",
        ),
        "sf_spy_core_phase6_overlay_satellite_qqq": lambda: (
            run_sf_spy_core_phase6_overlay_satellite_qqq(
                panel,
                cfg,
                overlay_exposure=overlay_exposure,
            )
        ),
        "sf_spy_qqq_btc_capped_offensive": lambda: (
            run_sf_spy_qqq_btc_capped_offensive(panel, cfg),
            "implemented_btc_strict_common_date_intersection",
        ),
    }

    for strategy_name in STRATEGY_FACTORY_CANDIDATES:
        try:
            result, status = runners[strategy_name]()
            results[strategy_name] = result
            status_rows.append(
                {
                    "strategy": strategy_name,
                    "implementation_status": status,
                    "failure_reason": "",
                }
            )
        except Exception as exc:  # pragma: no cover - runtime safety report path
            status_rows.append(
                {
                    "strategy": strategy_name,
                    "implementation_status": "not_implemented_cleanly",
                    "failure_reason": str(exc),
                }
            )

    return results, pd.DataFrame(status_rows)
