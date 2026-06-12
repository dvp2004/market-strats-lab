from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PHASE22A_SECTION = "phase22a_dynamic_multi_asset_opportunity_engine"
DEFAULT_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
    "IEF",
    "AGG",
    "GLD",
    "SLV",
    "DBC",
    "USO",
    "VNQ",
    "UUP",
    "BTC-USD",
    "CASH",
]
COMMODITY_ASSETS = {"GLD", "SLV", "DBC", "USO"}
PLACEHOLDER_FEATURES = [
    "macro_score",
    "fundamental_score",
    "sentiment_score",
    "valuation_score",
    "liquidity_score",
]
ACTIVE_FEATURES = [
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    "volatility_21d",
    "volatility_63d",
    "drawdown_from_252d_high",
    "price_above_200d_ma",
    "price_above_50d_ma",
    "trend_strength_50_200",
    "risk_adjusted_momentum",
    "correlation_to_spy_63d",
    "asset_realized_volatility",
    "asset_drawdown_penalty",
    "market_risk_on_flag",
    "cash_filter",
]


@dataclass(frozen=True)
class StrategySpec:
    strategy_name: str
    top_n: int
    max_single_asset_weight: float
    max_btc_weight: float
    max_oil_weight: float
    max_commodity_weight: float
    defensive: bool = False


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE22A_SECTION, {}) or {}


def _resolve_path(value: object, default: Path) -> Path:
    return Path(value) if value else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _price_path(root: Path, symbol: str) -> Path:
    fresh = root / "data" / "fresh" / "processed" / f"{symbol}.parquet"
    if fresh.exists():
        return fresh
    return root / "data" / "processed" / f"{symbol}.parquet"


def load_asset_prices(root: Path, symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    availability_rows: list[dict[str, Any]] = []
    price_frames: list[pd.Series] = []
    for symbol in symbols:
        if symbol == "CASH":
            availability_rows.append(
                {
                    "symbol": symbol,
                    "available": True,
                    "source_path": "synthetic_cash_zero_return",
                    "start_date": "",
                    "end_date": "",
                    "row_count": 0,
                    "availability_reason": "synthetic cash proxy",
                }
            )
            continue
        path = _price_path(root, symbol)
        if not path.exists():
            availability_rows.append(
                {
                    "symbol": symbol,
                    "available": False,
                    "source_path": str(path),
                    "start_date": "",
                    "end_date": "",
                    "row_count": 0,
                    "availability_reason": "local_price_file_missing",
                }
            )
            continue
        frame = pd.read_parquet(path)
        price_col = "adj_close" if "adj_close" in frame.columns else "close"
        if "date" not in frame.columns or price_col not in frame.columns:
            availability_rows.append(
                {
                    "symbol": symbol,
                    "available": False,
                    "source_path": str(path),
                    "start_date": "",
                    "end_date": "",
                    "row_count": len(frame),
                    "availability_reason": "required_date_or_price_column_missing",
                }
            )
            continue
        data = frame[["date", price_col]].copy()
        data["date"] = pd.to_datetime(data["date"])
        data[price_col] = pd.to_numeric(data[price_col], errors="coerce")
        data = (
            data.dropna(subset=["date", price_col])
            .drop_duplicates("date")
            .sort_values("date")
        )
        data = data.loc[data[price_col] > 0]
        if data.empty:
            availability_rows.append(
                {
                    "symbol": symbol,
                    "available": False,
                    "source_path": str(path),
                    "start_date": "",
                    "end_date": "",
                    "row_count": 0,
                    "availability_reason": "no_positive_prices",
                }
            )
            continue
        series = data.set_index("date")[price_col].astype(float).rename(symbol)
        price_frames.append(series)
        availability_rows.append(
            {
                "symbol": symbol,
                "available": True,
                "source_path": str(path),
                "start_date": series.index.min().date().isoformat(),
                "end_date": series.index.max().date().isoformat(),
                "row_count": len(series),
                "availability_reason": "available",
            }
        )
    if price_frames:
        prices = pd.concat(price_frames, axis=1).sort_index()
    else:
        prices = pd.DataFrame()
    if not prices.empty:
        prices["CASH"] = 1.0
    return prices, pd.DataFrame(availability_rows)


def _zscore(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    std = values.std(skipna=True)
    if not np.isfinite(std) or std == 0:
        return pd.Series(0.0, index=values.index)
    return (values - values.mean(skipna=True)) / std


def build_feature_store(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()
    price_only = prices.drop(columns=["CASH"], errors="ignore").dropna(how="all")
    returns = price_only.pct_change()
    spy_returns = returns["SPY"] if "SPY" in returns.columns else pd.Series(dtype=float)
    rows: list[pd.DataFrame] = []
    for symbol in price_only.columns:
        price = price_only[symbol].dropna()
        asset_returns = price.pct_change()
        frame = pd.DataFrame(index=price.index)
        frame["symbol"] = symbol
        frame["price"] = price
        frame["return_21d"] = price.pct_change(21)
        frame["return_63d"] = price.pct_change(63)
        frame["return_126d"] = price.pct_change(126)
        frame["return_252d"] = price.pct_change(252)
        frame["volatility_21d"] = asset_returns.rolling(21).std() * np.sqrt(252)
        frame["volatility_63d"] = asset_returns.rolling(63).std() * np.sqrt(252)
        rolling_high = price.rolling(252).max()
        frame["drawdown_from_252d_high"] = price / rolling_high - 1.0
        ma50 = price.rolling(50).mean()
        ma200 = price.rolling(200).mean()
        frame["price_above_200d_ma"] = (price > ma200).astype(float)
        frame["price_above_50d_ma"] = (price > ma50).astype(float)
        frame["trend_strength_50_200"] = ma50 / ma200 - 1.0
        frame["risk_adjusted_momentum"] = frame["return_126d"] / frame["volatility_63d"]
        if not spy_returns.empty and symbol in returns.columns:
            frame["correlation_to_spy_63d"] = returns[symbol].rolling(63).corr(spy_returns)
        else:
            frame["correlation_to_spy_63d"] = np.nan
        frame["correlation_to_portfolio_proxy_63d"] = frame["correlation_to_spy_63d"]
        frame["asset_realized_volatility"] = frame["volatility_63d"]
        frame["asset_drawdown_penalty"] = frame["drawdown_from_252d_high"].abs()
        if "SPY" in price_only.columns:
            spy_price = price_only["SPY"].reindex(frame.index).ffill()
            frame["market_risk_on_flag"] = (
                spy_price > spy_price.rolling(200).mean()
            ).astype(float)
        else:
            frame["market_risk_on_flag"] = 1.0
        frame["cash_filter"] = 1.0 - frame["market_risk_on_flag"]
        for placeholder in PLACEHOLDER_FEATURES:
            frame[placeholder] = np.nan
        rows.append(frame.reset_index(names="date"))
    panel = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return panel


def compute_opportunity_scores(feature_store: pd.DataFrame) -> pd.DataFrame:
    if feature_store.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    required = [
        "return_63d",
        "return_126d",
        "return_252d",
        "trend_strength_50_200",
        "risk_adjusted_momentum",
        "volatility_63d",
        "asset_drawdown_penalty",
    ]
    for date, group in feature_store.groupby("date", sort=True):
        score_frame = group.copy()
        if not set(required).issubset(score_frame.columns):
            continue
        score_frame["score_return_63d"] = _zscore(score_frame["return_63d"])
        score_frame["score_return_126d"] = _zscore(score_frame["return_126d"])
        score_frame["score_return_252d"] = _zscore(score_frame["return_252d"])
        score_frame["score_trend"] = _zscore(score_frame["trend_strength_50_200"])
        score_frame["score_risk_adjusted_momentum"] = _zscore(
            score_frame["risk_adjusted_momentum"]
        )
        score_frame["score_volatility_penalty"] = _zscore(score_frame["volatility_63d"])
        score_frame["score_drawdown_penalty"] = _zscore(
            score_frame["asset_drawdown_penalty"]
        )
        score_frame["opportunity_score"] = (
            0.25 * score_frame["score_return_63d"]
            + 0.25 * score_frame["score_return_126d"]
            + 0.20 * score_frame["score_return_252d"]
            + 0.15 * score_frame["score_trend"]
            + 0.10 * score_frame["score_risk_adjusted_momentum"]
            - 0.20 * score_frame["score_volatility_penalty"]
            - 0.20 * score_frame["score_drawdown_penalty"]
        )
        score_frame["score_formula"] = (
            "0.25*z(return_63d)+0.25*z(return_126d)+0.20*z(return_252d)"
            "+0.15*z(trend_strength_50_200)+0.10*z(risk_adjusted_momentum)"
            "-0.20*z(volatility_63d)-0.20*z(drawdown_penalty)"
        )
        rows.append(score_frame)
    scores = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    scores = scores.dropna(subset=["opportunity_score", "volatility_63d"])
    return scores


def _rebalance_execution_dates(index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if len(index) < 2:
        return []
    series = pd.Series(index, index=index)
    signal_dates = pd.DatetimeIndex(series.groupby(index.to_period("M")).last().values)
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for signal_date in signal_dates:
        future = index[index > signal_date]
        if len(future) == 0:
            continue
        pairs.append((signal_date, future[0]))
    return pairs


def _cap_and_redistribute(
    raw_weights: pd.Series,
    *,
    max_single_asset_weight: float,
    max_btc_weight: float,
    max_oil_weight: float,
    max_commodity_weight: float,
) -> pd.Series:
    raw_weights = raw_weights[raw_weights > 0].astype(float)
    if raw_weights.empty:
        return pd.Series(dtype=float)
    weights = raw_weights / raw_weights.sum()
    caps = pd.Series(max_single_asset_weight, index=weights.index, dtype=float)
    if "BTC-USD" in caps.index:
        caps.loc["BTC-USD"] = min(caps.loc["BTC-USD"], max_btc_weight)
    if "USO" in caps.index:
        caps.loc["USO"] = min(caps.loc["USO"], max_oil_weight)
    capped = pd.Series(0.0, index=weights.index)
    remaining = list(weights.index)
    remaining_weight = 1.0
    for _ in range(len(weights) + 3):
        if not remaining:
            break
        tentative = weights.loc[remaining] / weights.loc[remaining].sum() * remaining_weight
        over = tentative[tentative > caps.loc[tentative.index]]
        if over.empty:
            capped.loc[tentative.index] = tentative
            break
        for asset in over.index:
            capped.loc[asset] = caps.loc[asset]
            remaining_weight -= caps.loc[asset]
            remaining.remove(asset)
    commodity_assets = [asset for asset in capped.index if asset in COMMODITY_ASSETS]
    commodity_weight = float(capped.loc[commodity_assets].sum()) if commodity_assets else 0.0
    if commodity_weight > max_commodity_weight and commodity_weight > 0:
        scale = max_commodity_weight / commodity_weight
        released = commodity_weight - max_commodity_weight
        capped.loc[commodity_assets] *= scale
        receivers = [asset for asset in capped.index if asset not in commodity_assets]
        receivers = [asset for asset in receivers if capped.loc[asset] < caps.loc[asset] - 1e-9]
        if receivers:
            capped.loc[receivers] += released / len(receivers)
        else:
            capped["CASH"] = capped.get("CASH", 0.0) + released
    total = float(capped.sum())
    if total < 1.0:
        capped["CASH"] = capped.get("CASH", 0.0) + (1.0 - total)
    elif total > 1.0:
        capped = capped / total
    return capped.sort_index()


def _weights_for_signal(
    *,
    scores_for_signal: pd.DataFrame,
    spec: StrategySpec,
) -> pd.Series:
    market_risk_on = bool(scores_for_signal["market_risk_on_flag"].fillna(1.0).median() >= 0.5)
    scores = scores_for_signal.copy()
    scores = scores.loc[scores["symbol"] != "CASH"]
    if spec.defensive:
        if not market_risk_on:
            defensive_assets = ["TLT", "GLD"]
            chosen = scores.loc[scores["symbol"].isin(defensive_assets)].nlargest(
                spec.top_n,
                "opportunity_score",
            )
        else:
            chosen = scores.nlargest(spec.top_n, "opportunity_score")
        if chosen.empty:
            return pd.Series({"CASH": 1.0})
    elif not market_risk_on:
        defensive = scores.loc[scores["symbol"].isin(["TLT", "GLD"])].nlargest(
            2,
            "opportunity_score",
        )
        raw = pd.Series({"CASH": 0.50})
        if not defensive.empty:
            inv_vol = 1.0 / defensive.set_index("symbol")["volatility_63d"].clip(lower=1e-6)
            inv_vol = inv_vol / inv_vol.sum() * 0.50
            raw = pd.concat([raw, inv_vol])
        return _cap_and_redistribute(
            raw,
            max_single_asset_weight=spec.max_single_asset_weight,
            max_btc_weight=spec.max_btc_weight,
            max_oil_weight=spec.max_oil_weight,
            max_commodity_weight=spec.max_commodity_weight,
        )
    else:
        chosen = scores.nlargest(spec.top_n, "opportunity_score")
    if spec.defensive and "BTC-USD" in chosen["symbol"].values and spec.max_btc_weight <= 0:
        chosen = chosen.loc[chosen["symbol"] != "BTC-USD"]
    if chosen.empty:
        return pd.Series({"CASH": 1.0})
    inv_vol = 1.0 / chosen.set_index("symbol")["volatility_63d"].clip(lower=1e-6)
    return _cap_and_redistribute(
        inv_vol,
        max_single_asset_weight=spec.max_single_asset_weight,
        max_btc_weight=spec.max_btc_weight,
        max_oil_weight=spec.max_oil_weight,
        max_commodity_weight=spec.max_commodity_weight,
    )


def _returns_with_cash(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change().fillna(0.0)
    if "CASH" not in returns.columns:
        returns["CASH"] = 0.0
    return returns.fillna(0.0)


def simulate_dynamic_strategy(
    *,
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    spec: StrategySpec,
    starting_cash: float,
    transaction_cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if prices.empty or scores.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    returns = _returns_with_cash(prices)
    common_dates = pd.DatetimeIndex(sorted(set(returns.index) & set(pd.to_datetime(scores["date"]))))
    common_dates = common_dates[common_dates >= common_dates.min() + pd.Timedelta(days=252)]
    if len(common_dates) < 30:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    pairs = _rebalance_execution_dates(common_dates)
    current_weights = pd.Series({"CASH": 1.0})
    current_value = starting_cash
    equity_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    score_by_date = {
        pd.Timestamp(date): group.copy()
        for date, group in scores.groupby(pd.to_datetime(scores["date"]))
    }
    for index, (signal_date, execution_date) in enumerate(pairs):
        signal_scores = score_by_date.get(pd.Timestamp(signal_date), pd.DataFrame())
        if signal_scores.empty:
            continue
        target_weights = _weights_for_signal(scores_for_signal=signal_scores, spec=spec)
        turnover_index = sorted(set(target_weights.index) | set(current_weights.index))
        turnover = float(
            (
                target_weights.reindex(turnover_index).fillna(0.0)
                - current_weights.reindex(turnover_index).fillna(0.0)
            )
            .abs()
            .sum()
        )
        cost = current_value * turnover * transaction_cost_bps / 10_000.0
        current_value -= cost
        event_rows.append(
            {
                "strategy_name": spec.strategy_name,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution_date.date().isoformat(),
                "selected_assets": ",".join([asset for asset in target_weights.index if asset != "CASH"]),
                "target_weights": ";".join(
                    f"{asset}:{weight:.6f}" for asset, weight in target_weights.items()
                ),
                "turnover": turnover,
                "transaction_cost_bps": transaction_cost_bps,
                "transaction_cost_usd": cost,
                "market_risk_on_flag": bool(
                    signal_scores["market_risk_on_flag"].fillna(1.0).median() >= 0.5
                ),
            }
        )
        current_weights = target_weights
        next_execution = pairs[index + 1][1] if index + 1 < len(pairs) else returns.index[-1]
        period_dates = returns.index[
            (returns.index >= execution_date) & (returns.index < next_execution)
        ]
        for date in period_dates:
            daily_return = float(
                (
                    current_weights.reindex(returns.columns).fillna(0.0)
                    * returns.loc[date].fillna(0.0)
                ).sum()
            )
            current_value *= 1.0 + daily_return
            equity_rows.append(
                {
                    "date": date.date().isoformat(),
                    "strategy_name": spec.strategy_name,
                    "portfolio_value": current_value,
                    "transaction_cost_bps": transaction_cost_bps,
                }
            )
            for asset, weight in current_weights.items():
                weight_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "strategy_name": spec.strategy_name,
                        "asset": asset,
                        "weight": weight,
                        "transaction_cost_bps": transaction_cost_bps,
                    }
                )
    return (
        pd.DataFrame(equity_rows),
        pd.DataFrame(weight_rows),
        pd.DataFrame(event_rows),
    )


def _drawdown(values: pd.Series) -> pd.Series:
    return values / values.cummax() - 1.0


def _metrics(equity: pd.DataFrame, events: pd.DataFrame, weights: pd.DataFrame) -> dict[str, Any]:
    if equity.empty:
        return {}
    series = equity.sort_values("date").set_index(pd.to_datetime(equity["date"]))[
        "portfolio_value"
    ].astype(float)
    years = max((series.index.max() - series.index.min()).days / 365.25, 1 / 365.25)
    final_value = float(series.iloc[-1])
    cagr = (final_value / float(series.iloc[0])) ** (1 / years) - 1
    max_dd = float(_drawdown(series).min())
    turnover_value = pd.to_numeric(
        events.get("turnover", pd.Series(dtype=float)),
        errors="coerce",
    ).mean()
    turnover = float(turnover_value) if pd.notna(turnover_value) else 0.0
    btc_max = 0.0
    oil_max = 0.0
    if not weights.empty:
        btc_rows = weights.loc[weights["asset"] == "BTC-USD", "weight"]
        oil_rows = weights.loc[weights["asset"] == "USO", "weight"]
        btc_value = pd.to_numeric(btc_rows, errors="coerce").max()
        oil_value = pd.to_numeric(oil_rows, errors="coerce").max()
        btc_max = float(btc_value) if pd.notna(btc_value) else 0.0
        oil_max = float(oil_value) if pd.notna(oil_value) else 0.0
    return {
        "start_date": series.index.min().date().isoformat(),
        "end_date": series.index.max().date().isoformat(),
        "initial_value": float(series.iloc[0]),
        "final_value": final_value,
        "total_return_pct": (final_value / float(series.iloc[0]) - 1) * 100,
        "CAGR": cagr * 100,
        "max_drawdown": max_dd * 100,
        "Calmar": cagr / abs(max_dd) if max_dd else np.nan,
        "turnover": turnover,
        "number_of_rebalances": len(events),
        "BTC_max_actual_weight": btc_max,
        "oil_max_actual_weight": oil_max,
    }


def _daily_drawdowns(equity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in equity.groupby("strategy_name"):
        series = group.sort_values("date").set_index(pd.to_datetime(group["date"]))[
            "portfolio_value"
        ].astype(float)
        drawdowns = _drawdown(series)
        rows.append(
            pd.DataFrame(
                {
                    "date": drawdowns.index.date.astype(str),
                    "strategy_name": strategy,
                    "drawdown": drawdowns.values,
                    "drawdown_pct": drawdowns.values * 100,
                }
            )
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _strategy_specs(section: dict[str, Any]) -> list[StrategySpec]:
    return [
        StrategySpec(
            "dynamic_top3_technical_opportunity_v0",
            top_n=3,
            max_single_asset_weight=float(section.get("max_single_asset_weight", 0.50)),
            max_btc_weight=float(section.get("max_btc_weight", 0.05)),
            max_oil_weight=float(section.get("max_oil_weight", 0.10)),
            max_commodity_weight=float(section.get("max_commodity_weight", 0.20)),
        ),
        StrategySpec(
            "dynamic_top5_technical_opportunity_v0",
            top_n=5,
            max_single_asset_weight=0.35,
            max_btc_weight=float(section.get("max_btc_weight", 0.05)),
            max_oil_weight=float(section.get("max_oil_weight", 0.10)),
            max_commodity_weight=float(section.get("max_commodity_weight", 0.20)),
        ),
        StrategySpec(
            "dynamic_defensive_opportunity_v0",
            top_n=3,
            max_single_asset_weight=0.40,
            max_btc_weight=0.0,
            max_oil_weight=float(section.get("max_oil_weight", 0.10)),
            max_commodity_weight=float(section.get("max_commodity_weight", 0.20)),
            defensive=True,
        ),
    ]


def _common_comparison(
    *,
    dynamic_equity: pd.DataFrame,
    benchmark_equity_path: Path,
    starting_cash: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    benchmark_equity = _read_csv(benchmark_equity_path)
    rows: list[pd.DataFrame] = []
    if not benchmark_equity.empty and {"date", "canonical_candidate_id", "portfolio_value"}.issubset(benchmark_equity.columns):
        bench = benchmark_equity.rename(columns={"canonical_candidate_id": "strategy_name"})
        rows.append(bench[["date", "strategy_name", "portfolio_value"]])
    if not dynamic_equity.empty:
        rows.append(dynamic_equity[["date", "strategy_name", "portfolio_value"]])
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    all_equity = pd.concat(rows, ignore_index=True)
    all_equity["date"] = pd.to_datetime(all_equity["date"])
    date_sets = [
        set(group["date"])
        for _strategy, group in all_equity.groupby("strategy_name")
        if not group.empty
    ]
    common_dates = sorted(set.intersection(*date_sets)) if date_sets else []
    if len(common_dates) < 2:
        return pd.DataFrame(), all_equity
    summary_rows = []
    common_frames = []
    common_start = common_dates[0]
    common_end = common_dates[-1]
    for strategy, group in all_equity.groupby("strategy_name"):
        series = (
            group.sort_values("date")
            .drop_duplicates("date")
            .set_index("date")["portfolio_value"]
            .reindex(common_dates)
            .dropna()
        )
        normalized = series / float(series.iloc[0]) * starting_cash
        years = max((normalized.index.max() - normalized.index.min()).days / 365.25, 1 / 365.25)
        final_value = float(normalized.iloc[-1])
        cagr = (final_value / starting_cash) ** (1 / years) - 1
        max_dd = float(_drawdown(normalized).min())
        summary_rows.append(
            {
                "strategy_name": strategy,
                "common_start_date": common_start.date().isoformat(),
                "common_end_date": common_end.date().isoformat(),
                "restriction_reason": "common overlap across dynamic candidates and current benchmark table; BTC/local data availability may restrict start",
                "final_value": final_value,
                "CAGR": cagr * 100,
                "max_drawdown": max_dd * 100,
                "Calmar": cagr / abs(max_dd) if max_dd else np.nan,
            }
        )
        common_frames.append(
            pd.DataFrame(
                {
                    "date": normalized.index.date.astype(str),
                    "strategy_name": strategy,
                    "portfolio_value": normalized.values,
                }
            )
        )
    return pd.DataFrame(summary_rows), pd.concat(common_frames, ignore_index=True)


def _placeholder_chart(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_lines(frame: pd.DataFrame, value_col: str, path: Path, title: str, ylabel: str) -> None:
    if frame.empty or not {"date", "strategy_name", value_col}.issubset(frame.columns):
        _placeholder_chart(path, title, f"Missing {value_col} data")
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for strategy, group in frame.groupby("strategy_name"):
        ax.plot(group["date"], group[value_col], label=strategy)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_bar(frame: pd.DataFrame, label_col: str, value_col: str, path: Path, title: str) -> None:
    if frame.empty or label_col not in frame.columns or value_col not in frame.columns:
        _placeholder_chart(path, title, "Missing bar chart data")
        return
    plot_frame = frame[[label_col, value_col]].copy()
    plot_frame[value_col] = pd.to_numeric(plot_frame[value_col], errors="coerce")
    plot_frame = plot_frame.dropna(subset=[value_col])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(plot_frame[label_col], plot_frame[value_col])
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_charts(
    *,
    visuals_dir: Path,
    common_equity: pd.DataFrame,
    drawdowns: pd.DataFrame,
    comparison: pd.DataFrame,
    latest_scores: pd.DataFrame,
    latest_weights: pd.DataFrame,
    metrics: pd.DataFrame,
    tc: pd.DataFrame,
) -> None:
    visuals_dir.mkdir(parents=True, exist_ok=True)
    _plot_lines(common_equity, "portfolio_value", visuals_dir / "phase22a_equity_curves.png", "Phase22A Equity Curves", "Portfolio value")
    _plot_lines(drawdowns, "drawdown_pct", visuals_dir / "phase22a_drawdowns.png", "Phase22A Drawdowns", "Drawdown (%)")
    _plot_bar(comparison, "strategy_name", "final_value", visuals_dir / "phase22a_final_value_bar.png", "Final Value")
    if not comparison.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.scatter(comparison["max_drawdown"], comparison["CAGR"])
        for row in comparison.itertuples(index=False):
            ax.annotate(str(row.strategy_name)[:24], (row.max_drawdown, row.CAGR), fontsize=8)
        ax.set_xlabel("Max drawdown (%)")
        ax.set_ylabel("CAGR (%)")
        ax.set_title("Risk/Return Scatter")
        fig.tight_layout()
        fig.savefig(visuals_dir / "phase22a_risk_return_scatter.png", dpi=140)
        plt.close(fig)
    else:
        _placeholder_chart(visuals_dir / "phase22a_risk_return_scatter.png", "Risk/Return Scatter", "No comparison data")
    _plot_bar(latest_scores.head(15), "symbol", "opportunity_score", visuals_dir / "phase22a_latest_scores_bar.png", "Latest Opportunity Scores")
    _plot_bar(latest_weights, "asset", "weight", visuals_dir / "phase22a_latest_weights_bar.png", "Latest Dynamic Weights")
    _plot_bar(metrics, "strategy_name", "turnover", visuals_dir / "phase22a_turnover_by_strategy.png", "Average Turnover")
    _plot_bar(tc, "strategy_cost_case", "final_value", visuals_dir / "phase22a_transaction_cost_sensitivity.png", "Transaction Cost Sensitivity")


def _research_summary(
    *,
    path: Path,
    availability: pd.DataFrame,
    metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    tc: pd.DataFrame,
    decision: str,
) -> None:
    available_assets = availability.loc[availability["available"].map(_bool_value), "symbol"].astype(str).tolist()
    unavailable_assets = availability.loc[~availability["available"].map(_bool_value), "symbol"].astype(str).tolist()
    lines = [
        "# Phase 22A Dynamic Multi-Asset Opportunity Engine v0",
        "",
        "NO LIVE TRADING",
        "NO REAL MONEY",
        "NO BROKER/API",
        "NO STRATEGY PROMOTION",
        "RESEARCH ONLY",
        "NOT ADDED TO DAILY PAPER RUNNER",
        "",
        f"Decision: `{decision}`",
        "",
        f"Available assets: {', '.join(available_assets)}",
        f"Unavailable assets: {', '.join(unavailable_assets) if unavailable_assets else 'none'}",
        "",
        "Feature formula:",
        "`0.25*z(return_63d)+0.25*z(return_126d)+0.20*z(return_252d)+0.15*z(trend_strength_50_200)+0.10*z(risk_adjusted_momentum)-0.20*z(volatility_63d)-0.20*z(drawdown_penalty)`",
        "",
        "Macro, fundamental, sentiment, valuation, and liquidity scores are not active in Phase22A. Requires point-in-time/vintage-safe data audit.",
        "",
        "Strategy metrics:",
        metrics.to_markdown(index=False) if not metrics.empty else "No dynamic strategy metrics available.",
        "",
        "Comparison vs current table:",
        comparison.to_markdown(index=False) if not comparison.empty else "No benchmark comparison available.",
        "",
        "Transaction cost sensitivity:",
        tc.to_markdown(index=False) if not tc.empty else "No transaction cost sensitivity available.",
        "",
        "Limitations: technical/risk-only v0, monthly rebalancing, local adjusted-close data, report-only transaction costs, no paper integration.",
        "",
        "Next step: inspect robustness before considering any separate paper-watchlist adoption gate.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_phase22a_dynamic_multi_asset_opportunity_engine(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not _bool_value(section.get("enabled", False)):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}
    reports_path = Path(reports_dir)
    root = reports_path.parent if reports_path.name == "reports" else Path.cwd()
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "strategy_factory" / "dynamic_opportunity_engine",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    visuals_dir = output_dir / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)

    starting_cash = float(section.get("starting_cash", 10_000))
    transaction_cost_cases = list(section.get("transaction_cost_bps_cases", [0, 10, 25]))
    prices, availability = load_asset_prices(root, DEFAULT_UNIVERSE)
    feature_store = build_feature_store(prices)
    scores = compute_opportunity_scores(feature_store)
    specs = _strategy_specs(section)

    all_equity = []
    all_weights = []
    all_events = []
    metrics_rows = []
    tc_rows = []
    for spec in specs:
        for cost_bps in transaction_cost_cases:
            equity, weights, events = simulate_dynamic_strategy(
                prices=prices,
                scores=scores,
                spec=spec,
                starting_cash=starting_cash,
                transaction_cost_bps=float(cost_bps),
            )
            if equity.empty:
                continue
            metric = _metrics(equity, events, weights)
            metric.update(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost_bps,
                    "paper_only": True,
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            )
            tc_rows.append(
                {
                    "strategy_name": spec.strategy_name,
                    "transaction_cost_bps": cost_bps,
                    "strategy_cost_case": f"{spec.strategy_name}_{cost_bps}bps",
                    "final_value": metric["final_value"],
                    "CAGR": metric["CAGR"],
                    "max_drawdown": metric["max_drawdown"],
                }
            )
            if float(cost_bps) == 0:
                metrics_rows.append(metric)
                all_equity.append(equity)
                all_weights.append(weights)
                all_events.append(events)
    dynamic_equity = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame()
    dynamic_weights = pd.concat(all_weights, ignore_index=True) if all_weights else pd.DataFrame()
    rebalance_log = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    metrics = pd.DataFrame(metrics_rows)
    tc = pd.DataFrame(tc_rows)
    drawdowns = _daily_drawdowns(dynamic_equity) if not dynamic_equity.empty else pd.DataFrame()
    benchmark_path = root / "reports" / "paper_trading" / "regime_informed_tracking" / "performance" / "regime_informed_historical_daily_equity.csv"
    comparison, common_equity = _common_comparison(
        dynamic_equity=dynamic_equity,
        benchmark_equity_path=benchmark_path,
        starting_cash=starting_cash,
    )
    if not scores.empty:
        score_counts = scores.groupby("date")["symbol"].nunique()
        usable_score_dates = score_counts.loc[score_counts >= 3]
        latest_date = (
            usable_score_dates.index.max()
            if not usable_score_dates.empty
            else scores["date"].max()
        )
    else:
        latest_date = ""
    latest_scores = (
        scores.loc[scores["date"] == latest_date]
        .sort_values("opportunity_score", ascending=False)
        .head(25)
        if not scores.empty
        else pd.DataFrame()
    )
    latest_weights = (
        dynamic_weights.loc[
            dynamic_weights["date"] == dynamic_weights["date"].max()
        ].copy()
        if not dynamic_weights.empty
        else pd.DataFrame()
    )
    if not latest_weights.empty:
        latest_weights = latest_weights.loc[
            latest_weights["strategy_name"] == "dynamic_top3_technical_opportunity_v0"
        ]

    feature_latest = latest_scores.copy()
    inactive_note = "Not active in Phase22A. Requires point-in-time/vintage-safe data audit."
    for placeholder in PLACEHOLDER_FEATURES:
        if placeholder not in feature_store.columns:
            feature_store[placeholder] = np.nan
        feature_store[f"{placeholder}_status"] = inactive_note
        feature_latest[f"{placeholder}_status"] = inactive_note

    _write_csv(availability, output_dir / "phase22a_asset_universe_availability.csv")
    _write_csv(feature_latest, output_dir / "phase22a_feature_store_latest.csv")
    _write_csv(feature_store, output_dir / "phase22a_feature_store_panel.csv")
    _write_csv(scores, output_dir / "phase22a_opportunity_scores.csv")
    _write_csv(metrics, output_dir / "phase22a_dynamic_strategy_metrics.csv")
    _write_csv(dynamic_equity, output_dir / "phase22a_dynamic_strategy_daily_equity.csv")
    _write_csv(drawdowns, output_dir / "phase22a_dynamic_strategy_daily_drawdowns.csv")
    _write_csv(dynamic_weights, output_dir / "phase22a_dynamic_strategy_daily_weights.csv")
    _write_csv(rebalance_log, output_dir / "phase22a_rebalance_event_log.csv")
    _write_csv(tc, output_dir / "phase22a_transaction_cost_sensitivity.csv")
    _write_csv(comparison, output_dir / "phase22a_benchmark_comparison.csv")
    _write_csv(comparison, output_dir / "phase22a_candidate_comparison_vs_current_table.csv")

    _write_charts(
        visuals_dir=visuals_dir,
        common_equity=common_equity,
        drawdowns=drawdowns,
        comparison=comparison,
        latest_scores=latest_scores,
        latest_weights=latest_weights,
        metrics=metrics,
        tc=tc,
    )

    if metrics.empty:
        decision = "phase22a_dynamic_opportunity_engine_failed_missing_data"
    elif comparison.empty or (
        "SPY Buy & Hold Benchmark" in set(comparison["strategy_name"])
        and comparison["final_value"].max()
        <= float(
            comparison.loc[
                comparison["strategy_name"] == "SPY Buy & Hold Benchmark",
                "final_value",
            ].iloc[0]
        )
    ):
        decision = "phase22a_dynamic_opportunity_engine_completed_no_candidate_beats_benchmark"
    else:
        decision = "phase22a_dynamic_opportunity_engine_completed_research_only"

    summary_md_path = output_dir / "phase22a_research_summary.md"
    _research_summary(
        path=summary_md_path,
        availability=availability,
        metrics=metrics,
        comparison=comparison,
        tc=tc,
        decision=decision,
    )
    chart_paths = [
        visuals_dir / name
        for name in [
            "phase22a_equity_curves.png",
            "phase22a_drawdowns.png",
            "phase22a_final_value_bar.png",
            "phase22a_risk_return_scatter.png",
            "phase22a_latest_scores_bar.png",
            "phase22a_latest_weights_bar.png",
            "phase22a_turnover_by_strategy.png",
            "phase22a_transaction_cost_sensitivity.png",
        ]
    ]
    gates = pd.DataFrame(
        [
            {"gate_id": "asset_universe_availability_written", "passed": True},
            {"gate_id": "feature_store_written", "passed": not feature_store.empty},
            {"gate_id": "opportunity_scores_written", "passed": not scores.empty},
            {"gate_id": "dynamic_strategy_evaluated", "passed": not metrics.empty},
            {"gate_id": "benchmark_comparison_written", "passed": not comparison.empty},
            {"gate_id": "transaction_cost_sensitivity_written", "passed": not tc.empty},
            {"gate_id": "charts_generated", "passed": all(path.exists() for path in chart_paths)},
            {"gate_id": "research_summary_written", "passed": summary_md_path.exists()},
            {"gate_id": "not_added_to_daily_paper_runner", "passed": True},
            {"gate_id": "promotion_disabled", "passed": True},
            {"gate_id": "live_trading_disabled", "passed": True},
            {"gate_id": "real_money_disabled", "passed": True},
            {"gate_id": "broker_api_integration_disabled", "passed": True},
        ]
    )
    all_gates_passed = bool(gates["passed"].map(_bool_value).all())
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 22A",
                "phase22a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "available_assets": ",".join(
                    availability.loc[availability["available"].map(_bool_value), "symbol"].astype(str)
                ),
                "unavailable_assets": ",".join(
                    availability.loc[~availability["available"].map(_bool_value), "symbol"].astype(str)
                ),
                "dynamic_strategy_count": len(metrics),
                "latest_feature_date": str(latest_date)[:10] if latest_date != "" else "",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 22A",
                "phase22a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "diagnostic": "Dynamic multi-asset opportunity engine v0 research prototype",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research only. Not added to daily paper runner.",
            }
        ]
    )
    dashboard = pd.DataFrame(
        [
            {
                "phase22a_decision": decision,
                "dynamic_strategy_count": len(metrics),
                "latest_feature_date": str(latest_date)[:10] if latest_date != "" else "",
                "dashboard_status": "phase22a_dynamic_opportunity_status_written",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": "Research-only engine not connected to daily paper runner.",
            }
        ]
    )
    _write_csv(summary, output_dir / "phase22a_summary.csv")
    _write_csv(gates, output_dir / "phase22a_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase22a_conclusion.csv")
    _write_csv(dashboard, dashboard_dir / "phase22a_dynamic_opportunity_status.csv")
    print("Wrote Phase 22A dynamic multi-asset opportunity engine reports.")
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "availability": availability,
        "feature_store": feature_store,
        "latest_scores": latest_scores,
        "metrics": metrics,
        "comparison": comparison,
        "transaction_cost_sensitivity": tc,
        "dashboard": dashboard,
    }
