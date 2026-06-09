from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from market_strats.analysis.metrics import calculate_drawdown, calculate_metrics
from market_strats.data.fetch_yfinance import (
    fetch_daily_prices,
    load_prices_from_parquet,
    save_prices_to_parquet,
)


PHASE19A_SECTION = "phase19a_strategy_factory_multiverse"
CASH = "CASH"
BENCHMARK_ID = "sf19_spy_buy_hold"
DEFAULT_REAL_SYMBOLS = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"]
EXPANDED_SYMBOLS = ["IWM", "EFA", "EEM", "AGG", "VNQ", "DBC"]


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE19A_SECTION, {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _safe_symbol_file(symbol: str) -> str:
    return f"{symbol.upper()}.parquet"


def _asset_col(symbol: str) -> str:
    return f"{symbol.lower().replace('-', '_')}_weight"


def _return_col(symbol: str) -> str:
    return f"{symbol}_return"


def _real_symbols(symbols: list[str]) -> list[str]:
    return [symbol for symbol in symbols if symbol != CASH]


def _normalise_symbols(symbols: list[Any]) -> list[str]:
    out: list[str] = []
    for symbol in symbols:
        normalised = str(symbol).strip().upper()
        if normalised and normalised not in out:
            out.append(normalised)
    return out


def _preferred_data_dir(symbols: list[str], section: dict[str, Any]) -> Path:
    configured = section.get("data_dir")
    if configured:
        return Path(configured)

    fresh_dir = Path("data/fresh/processed")
    if all((fresh_dir / _safe_symbol_file(symbol)).exists() for symbol in _real_symbols(symbols)):
        return fresh_dir

    return Path("data/processed")


def parse_universe_config(section: dict[str, Any]) -> dict[str, dict[str, Any]]:
    universes = section.get("universes", {}) or {}
    parsed: dict[str, dict[str, Any]] = {}

    for universe_name, universe_config in universes.items():
        symbols = _normalise_symbols(list(universe_config.get("symbols", [])))
        if CASH not in symbols and bool(universe_config.get("include_cash", True)):
            symbols.append(CASH)
        parsed[str(universe_name)] = {
            "symbols": symbols,
            "allow_btc": _bool_value(universe_config.get("allow_btc", False)),
            "btc_caps": [
                float(cap)
                for cap in universe_config.get("btc_caps", [])
                if cap is not None
            ],
        }

    return parsed


def _evaluation_periods(section: dict[str, Any]) -> dict[str, dict[str, Any]]:
    periods = section.get("evaluation_periods", {}) or {}
    if periods:
        return {
            str(name): {
                "start": period.get("start"),
                "end": period.get("end"),
            }
            for name, period in periods.items()
        }

    return {
        "full_common": {"start": None, "end": None},
        "post_2014_btc_common": {"start": "2014-09-17", "end": None},
        "covid_inflation": {"start": "2020-01-01", "end": "2023-12-31"},
        "post_2021": {"start": "2021-01-01", "end": None},
    }


def _objective_weights(section: dict[str, Any]) -> dict[str, float]:
    weights = section.get("objective_weights", {}) or {}
    return {
        "cagr_weight": float(weights.get("cagr_weight", 0.40)),
        "calmar_weight": float(weights.get("calmar_weight", 0.30)),
        "max_drawdown_weight": float(weights.get("max_drawdown_weight", 0.20)),
        "turnover_penalty_weight": float(weights.get("turnover_penalty_weight", 0.10)),
    }


def _finalist_rules(section: dict[str, Any]) -> dict[str, Any]:
    rules = section.get("finalist_rules", {}) or {}
    return {
        "require_positive_cagr_edge_vs_spy": _bool_value(
            rules.get("require_positive_cagr_edge_vs_spy", True)
        ),
        "max_drawdown_worse_than_spy_allowed_pp": float(
            rules.get("max_drawdown_worse_than_spy_allowed_pp", 5.0)
        ),
        "min_rolling_3y_beat_spy_pct": float(
            rules.get("min_rolling_3y_beat_spy_pct", 60.0)
        ),
        "require_no_live_flags": _bool_value(rules.get("require_no_live_flags", True)),
    }


def _load_or_fetch_prices(
    symbol: str,
    *,
    config: dict[str, Any],
    data_dir: Path,
) -> pd.DataFrame | None:
    symbol = symbol.upper()
    try:
        return load_prices_from_parquet(symbol, data_dir)
    except FileNotFoundError:
        try:
            prices = fetch_daily_prices(
                ticker=symbol,
                start_date=config.get("start_date", "2000-01-01"),
                end_date=config.get("end_date"),
            )
            save_prices_to_parquet(prices, symbol, data_dir)
            return prices
        except Exception:
            return None


def load_multiverse_price_data(
    *,
    config: dict[str, Any],
    section: dict[str, Any],
    symbols: list[str],
) -> tuple[dict[str, pd.DataFrame], Path, list[str]]:
    data_dir = _preferred_data_dir(symbols, section)
    price_data: dict[str, pd.DataFrame] = {}
    missing_symbols: list[str] = []

    for symbol in _real_symbols(symbols):
        prices = _load_or_fetch_prices(symbol, config=config, data_dir=data_dir)
        if prices is None or prices.empty:
            missing_symbols.append(symbol)
        else:
            price_data[symbol] = prices

    return price_data, data_dir, missing_symbols


def _price_frame(prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    required = {"date", "adj_close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"{symbol} price frame missing columns: {sorted(missing)}")

    frame = prices[["date", "adj_close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["adj_close"] = frame["adj_close"].astype(float)
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame = frame.loc[frame["adj_close"] > 0]
    return frame.rename(columns={"adj_close": symbol})


def build_multiverse_price_panel(
    price_data: dict[str, pd.DataFrame],
    symbols: list[str],
) -> pd.DataFrame:
    real_symbols = [symbol for symbol in _real_symbols(symbols) if symbol in price_data]
    if not real_symbols:
        raise ValueError("No real symbols are available for Phase 19A")

    panel: pd.DataFrame | None = None
    for symbol in real_symbols:
        frame = _price_frame(price_data[symbol], symbol)
        panel = frame if panel is None else panel.merge(frame, on="date", how="inner")

    if panel is None or panel.empty:
        raise ValueError("No common dates across Phase 19A price data")

    panel = panel.sort_values("date").reset_index(drop=True)
    for symbol in real_symbols:
        panel[_return_col(symbol)] = panel[symbol].pct_change().fillna(0.0)
    panel[_return_col(CASH)] = 0.0
    return panel


def _rebalance_mask(dates: pd.Series) -> pd.Series:
    periods = pd.to_datetime(dates).dt.to_period("M")
    return periods.ne(periods.shift(1)).fillna(True).astype(bool)


def _normalise_weight_row(
    weights: dict[str, float],
    symbols: list[str],
    *,
    btc_cap: float | None = None,
) -> dict[str, float]:
    row = {symbol: 0.0 for symbol in symbols}
    for symbol, weight in weights.items():
        if symbol in row:
            row[symbol] = max(0.0, float(weight))

    if "BTC-USD" in row and btc_cap is not None and row["BTC-USD"] > btc_cap:
        overflow = row["BTC-USD"] - btc_cap
        row["BTC-USD"] = btc_cap
        row[CASH] = row.get(CASH, 0.0) + overflow

    total = sum(row.values())
    if total <= 0:
        if CASH in row:
            row[CASH] = 1.0
        else:
            row[symbols[0]] = 1.0
        return row

    for symbol in row:
        row[symbol] = row[symbol] / total
    return row


def _weights_frame_from_static(
    panel: pd.DataFrame,
    symbols: list[str],
    weights: dict[str, float],
    *,
    btc_cap: float | None = None,
) -> pd.DataFrame:
    row = _normalise_weight_row(weights, symbols, btc_cap=btc_cap)
    return pd.DataFrame([row] * len(panel), index=panel.index, columns=symbols).astype(float)


def _assert_valid_weights(weights: pd.DataFrame, symbols: list[str]) -> None:
    if (weights[symbols] < -1e-9).any().any():
        raise ValueError("Phase 19A weights cannot be negative")
    totals = weights[symbols].sum(axis=1)
    if not np.allclose(totals, 1.0, atol=1e-6):
        raise ValueError("Phase 19A weights must sum to 1")


def result_from_weight_targets(
    panel: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    symbols: list[str],
    strategy_id: str,
    initial_capital: float,
    rebalance_mask: pd.Series | None = None,
) -> pd.DataFrame:
    weights = weights.reindex(columns=symbols, fill_value=0.0).astype(float)
    _assert_valid_weights(weights, symbols)

    returns = pd.DataFrame(index=panel.index)
    for symbol in symbols:
        returns[symbol] = panel[_return_col(symbol)] if symbol != CASH else 0.0

    if rebalance_mask is None:
        rebalance_mask = _rebalance_mask(panel["date"])

    effective_weights = weights.shift(1)
    effective_weights.iloc[0] = weights.iloc[0]
    strategy_returns = (effective_weights[symbols] * returns[symbols]).sum(axis=1)
    strategy_returns.iloc[0] = 0.0
    equity = float(initial_capital) * (1.0 + strategy_returns).cumprod()

    turnover = weights[symbols].diff().abs().sum(axis=1).fillna(0.0)
    turnover = turnover.where(rebalance_mask.astype(bool), 0.0)
    turnover.iloc[0] = 1.0

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(panel["date"]),
            "adj_close": panel["SPY"].astype(float).to_numpy()
            if "SPY" in panel
            else equity.to_numpy(),
            "strategy_return": strategy_returns.astype(float).to_numpy(),
            "equity": equity.astype(float).to_numpy(),
            "position": (1.0 - weights.get(CASH, pd.Series(0.0, index=weights.index))).to_numpy(),
            "cash_position": weights.get(CASH, pd.Series(0.0, index=weights.index)).to_numpy(),
            "turnover": turnover.astype(float).to_numpy(),
            "strategy": strategy_id,
        }
    )
    for symbol in symbols:
        out[_asset_col(symbol)] = weights[symbol].astype(float).to_numpy()
    return out


def _monthly_signal_indices(panel: pd.DataFrame) -> pd.Index:
    return panel.index[_rebalance_mask(panel["date"])]


def _momentum(panel: pd.DataFrame, symbol: str, idx: int, lookback: int) -> float:
    if idx < lookback or symbol not in panel:
        return np.nan
    previous = float(panel[symbol].iloc[idx - lookback])
    if previous <= 0:
        return np.nan
    return float(panel[symbol].iloc[idx] / previous - 1.0)


def _trend_positive(panel: pd.DataFrame, symbol: str, idx: int, lookback: int = 200) -> bool:
    if idx < lookback or symbol not in panel:
        return False
    price = float(panel[symbol].iloc[idx])
    sma = float(panel[symbol].iloc[idx - lookback + 1 : idx + 1].mean())
    return bool(price > sma)


def fixed_allocation_candidate_specs(
    symbols: list[str],
    *,
    allow_btc: bool,
    btc_caps: list[float],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    risky = [symbol for symbol in _real_symbols(symbols)]

    if "SPY" in symbols:
        specs.append(
            {
                "candidate_id": "sf19_spy_buy_hold",
                "strategy_family": "baseline",
                "weights": {"SPY": 1.0},
            }
        )

    if risky:
        equal = 1.0 / len(risky)
        specs.append(
            {
                "candidate_id": "sf19_equal_weight_universe",
                "strategy_family": "baseline",
                "weights": {symbol: equal for symbol in risky},
            }
        )

    if "BTC-USD" in symbols:
        no_btc = [symbol for symbol in risky if symbol != "BTC-USD"]
        if no_btc:
            equal_no_btc = 1.0 / len(no_btc)
            specs.append(
                {
                    "candidate_id": "sf19_static_no_btc_equal_weight",
                    "strategy_family": "baseline",
                    "weights": {symbol: equal_no_btc for symbol in no_btc},
                }
            )

    if {"SPY", "QQQ"}.issubset(symbols):
        specs.extend(
            [
                {
                    "candidate_id": "sf19_spy_qqq_60_40",
                    "strategy_family": "fixed_allocation",
                    "weights": {"SPY": 0.60, "QQQ": 0.40},
                },
                {
                    "candidate_id": "sf19_spy_qqq_70_30",
                    "strategy_family": "fixed_allocation",
                    "weights": {"SPY": 0.70, "QQQ": 0.30},
                },
                {
                    "candidate_id": "sf19_spy_qqq_50_50",
                    "strategy_family": "fixed_allocation",
                    "weights": {"SPY": 0.50, "QQQ": 0.50},
                },
            ]
        )

    if {"SPY", "QQQ", "GLD", "TLT"}.issubset(symbols):
        specs.append(
            {
                "candidate_id": "sf19_spy_qqq_gld_tlt_50_30_10_10",
                "strategy_family": "fixed_allocation",
                "weights": {"SPY": 0.50, "QQQ": 0.30, "GLD": 0.10, "TLT": 0.10},
            }
        )

    if allow_btc and "BTC-USD" in symbols and {"SPY", "QQQ"}.issubset(symbols):
        for cap in btc_caps or [0.10]:
            specs.append(
                {
                    "candidate_id": f"sf19_spy_qqq_btc_cap_{int(round(cap * 100)):02d}",
                    "strategy_family": "fixed_allocation_btc_capped",
                    "weights": {
                        "SPY": 0.50,
                        "QQQ": 0.30,
                        "BTC-USD": cap,
                        CASH: max(0.0, 0.20 - cap),
                    },
                    "btc_cap": cap,
                }
            )

    return specs


def run_top_k_momentum_candidate(
    panel: pd.DataFrame,
    *,
    symbols: list[str],
    k: int,
    lookback: int,
    trend_filter: bool,
    btc_cap: float | None,
    candidate_id: str,
    initial_capital: float,
) -> pd.DataFrame:
    tradable = _real_symbols(symbols)
    weight_values = np.zeros((len(panel), len(symbols)), dtype=float)
    symbol_index = {symbol: idx for idx, symbol in enumerate(symbols)}
    signal_indices = [int(idx) for idx in _monthly_signal_indices(panel)]
    if not signal_indices or signal_indices[0] != 0:
        signal_indices = [0, *signal_indices]
    current = _normalise_weight_row({CASH: 1.0}, symbols, btc_cap=btc_cap)

    for position, idx in enumerate(signal_indices):
        momentums = []
        for symbol in tradable:
            value = _momentum(panel, symbol, idx, lookback)
            if np.isfinite(value) and (not trend_filter or _trend_positive(panel, symbol, idx)):
                momentums.append((symbol, value))
        positive = [(symbol, value) for symbol, value in momentums if value > 0]
        selected = [
            symbol
            for symbol, _value in sorted(
                positive,
                key=lambda item: item[1],
                reverse=True,
            )[:k]
        ]
        if selected:
            current = _normalise_weight_row(
                {symbol: 1.0 / len(selected) for symbol in selected},
                symbols,
                btc_cap=btc_cap,
            )
        else:
            current = _normalise_weight_row({CASH: 1.0}, symbols, btc_cap=btc_cap)

        end = signal_indices[position + 1] if position + 1 < len(signal_indices) else len(panel)
        for symbol, value in current.items():
            weight_values[idx:end, symbol_index[symbol]] = value

    weights = pd.DataFrame(weight_values, index=panel.index, columns=symbols)

    return result_from_weight_targets(
        panel,
        weights,
        symbols=symbols,
        strategy_id=candidate_id,
        initial_capital=initial_capital,
        rebalance_mask=_rebalance_mask(panel["date"]),
    )


def run_inverse_vol_candidate(
    panel: pd.DataFrame,
    *,
    symbols: list[str],
    lookback: int,
    max_weight: float,
    btc_cap: float | None,
    candidate_id: str,
    initial_capital: float,
) -> pd.DataFrame:
    tradable = _real_symbols(symbols)
    weight_values = np.zeros((len(panel), len(symbols)), dtype=float)
    symbol_index = {symbol: idx for idx, symbol in enumerate(symbols)}
    signal_indices = [int(idx) for idx in _monthly_signal_indices(panel)]
    if not signal_indices or signal_indices[0] != 0:
        signal_indices = [0, *signal_indices]
    current = _normalise_weight_row({CASH: 1.0}, symbols, btc_cap=btc_cap)

    for position, idx in enumerate(signal_indices):
        vols: dict[str, float] = {}
        for symbol in tradable:
            ret_col = _return_col(symbol)
            if idx >= lookback and ret_col in panel:
                vol = float(panel[ret_col].iloc[idx - lookback + 1 : idx + 1].std(ddof=1))
                if np.isfinite(vol) and vol > 0:
                    vols[symbol] = vol
        if vols:
            inv = {symbol: 1.0 / vol for symbol, vol in vols.items()}
            total_inv = sum(inv.values())
            raw = {symbol: min(max_weight, value / total_inv) for symbol, value in inv.items()}
            leftover = max(0.0, 1.0 - sum(raw.values()))
            if leftover > 0 and CASH in symbols:
                raw[CASH] = leftover
            current = _normalise_weight_row(raw, symbols, btc_cap=btc_cap)
        else:
            current = _normalise_weight_row({CASH: 1.0}, symbols, btc_cap=btc_cap)

        end = signal_indices[position + 1] if position + 1 < len(signal_indices) else len(panel)
        for symbol, value in current.items():
            weight_values[idx:end, symbol_index[symbol]] = value

    weights = pd.DataFrame(weight_values, index=panel.index, columns=symbols)

    return result_from_weight_targets(
        panel,
        weights,
        symbols=symbols,
        strategy_id=candidate_id,
        initial_capital=initial_capital,
        rebalance_mask=_rebalance_mask(panel["date"]),
    )


def run_spy_trend_guard_candidate(
    panel: pd.DataFrame,
    *,
    symbols: list[str],
    base_weights: dict[str, float],
    candidate_id: str,
    initial_capital: float,
) -> pd.DataFrame:
    weight_values = np.zeros((len(panel), len(symbols)), dtype=float)
    symbol_index = {symbol: idx for idx, symbol in enumerate(symbols)}
    signal_indices = [int(idx) for idx in _monthly_signal_indices(panel)]
    if not signal_indices or signal_indices[0] != 0:
        signal_indices = [0, *signal_indices]
    current = _normalise_weight_row(base_weights, symbols)

    for position, idx in enumerate(signal_indices):
        if "SPY" in panel and _trend_positive(panel, "SPY", idx, lookback=200):
            current = _normalise_weight_row(base_weights, symbols)
        else:
            reduced = {symbol: weight * 0.50 for symbol, weight in base_weights.items()}
            reduced[CASH] = reduced.get(CASH, 0.0) + 0.50
            current = _normalise_weight_row(reduced, symbols)

        end = signal_indices[position + 1] if position + 1 < len(signal_indices) else len(panel)
        for symbol, value in current.items():
            weight_values[idx:end, symbol_index[symbol]] = value

    weights = pd.DataFrame(weight_values, index=panel.index, columns=symbols)

    return result_from_weight_targets(
        panel,
        weights,
        symbols=symbols,
        strategy_id=candidate_id,
        initial_capital=initial_capital,
        rebalance_mask=_rebalance_mask(panel["date"]),
    )


def run_multiverse_candidates_for_universe(
    panel: pd.DataFrame,
    *,
    universe_name: str,
    symbols: list[str],
    allow_btc: bool,
    btc_caps: list[float],
    initial_capital: float,
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    for spec in fixed_allocation_candidate_specs(symbols, allow_btc=allow_btc, btc_caps=btc_caps):
        candidate_id = spec["candidate_id"]
        weights = _weights_frame_from_static(
            panel,
            symbols,
            spec["weights"],
            btc_cap=spec.get("btc_cap"),
        )
        result = result_from_weight_targets(
            panel,
            weights,
            symbols=symbols,
            strategy_id=candidate_id,
            initial_capital=initial_capital,
            rebalance_mask=_rebalance_mask(panel["date"]),
        )
        candidates[candidate_id] = {
            "universe_name": universe_name,
            "candidate_id": candidate_id,
            "strategy_family": spec["strategy_family"],
            "result": result,
            "symbols": symbols,
            "btc_cap": spec.get("btc_cap", 0.0),
        }

    btc_cap_values = btc_caps if allow_btc and "BTC-USD" in symbols else [None]
    for lookback in [63, 126, 252]:
        for k in [1, 2, 3]:
            if len(_real_symbols(symbols)) < k:
                continue
            for trend_filter in [False, True]:
                for btc_cap in btc_cap_values:
                    suffix = f"{lookback}d_top{k}"
                    if trend_filter:
                        suffix += "_trend"
                    if btc_cap is not None:
                        suffix += f"_btc{int(round(btc_cap * 100)):02d}"
                    candidate_id = f"sf19_topk_momentum_{suffix}"
                    result = run_top_k_momentum_candidate(
                        panel,
                        symbols=symbols,
                        k=k,
                        lookback=lookback,
                        trend_filter=trend_filter,
                        btc_cap=btc_cap,
                        candidate_id=candidate_id,
                        initial_capital=initial_capital,
                    )
                    candidates[candidate_id] = {
                        "universe_name": universe_name,
                        "candidate_id": candidate_id,
                        "strategy_family": "top_k_momentum",
                        "result": result,
                        "symbols": symbols,
                        "btc_cap": btc_cap or 0.0,
                    }

    for lookback in [63, 126]:
        for btc_cap in btc_cap_values:
            suffix = f"{lookback}d_cap50"
            if btc_cap is not None:
                suffix += f"_btc{int(round(btc_cap * 100)):02d}"
            candidate_id = f"sf19_inverse_vol_{suffix}"
            result = run_inverse_vol_candidate(
                panel,
                symbols=symbols,
                lookback=lookback,
                max_weight=0.50,
                btc_cap=btc_cap,
                candidate_id=candidate_id,
                initial_capital=initial_capital,
            )
            candidates[candidate_id] = {
                "universe_name": universe_name,
                "candidate_id": candidate_id,
                "strategy_family": "volatility_aware",
                "result": result,
                "symbols": symbols,
                "btc_cap": btc_cap or 0.0,
            }

    if {"SPY", "QQQ"}.issubset(symbols):
        result = run_spy_trend_guard_candidate(
            panel,
            symbols=symbols,
            base_weights={"SPY": 0.60, "QQQ": 0.40},
            candidate_id="sf19_spy_qqq_60_40_spy_trend_guard",
            initial_capital=initial_capital,
        )
        candidates["sf19_spy_qqq_60_40_spy_trend_guard"] = {
            "universe_name": universe_name,
            "candidate_id": "sf19_spy_qqq_60_40_spy_trend_guard",
            "strategy_family": "drawdown_guard_overlay",
            "result": result,
            "symbols": symbols,
            "btc_cap": 0.0,
        }

    return candidates


def _slice_result_for_period(
    result: pd.DataFrame,
    *,
    start: str | None,
    end: str | None,
    initial_capital: float,
) -> pd.DataFrame:
    frame = result.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if start:
        frame = frame.loc[frame["date"] >= pd.Timestamp(start)]
    if end:
        frame = frame.loc[frame["date"] <= pd.Timestamp(end)]
    frame = frame.sort_values("date").reset_index(drop=True)
    if frame.empty:
        return frame
    frame["strategy_return"] = frame["strategy_return"].astype(float)
    frame.loc[0, "strategy_return"] = 0.0
    frame["equity"] = float(initial_capital) * (1.0 + frame["strategy_return"]).cumprod()
    return frame


def _rolling_beat_pct(candidate: pd.DataFrame, benchmark: pd.DataFrame, window: int) -> float:
    merged = candidate[["date", "equity"]].merge(
        benchmark[["date", "equity"]],
        on="date",
        how="inner",
        suffixes=("_candidate", "_spy"),
    )
    if len(merged) <= window:
        return float("nan")
    candidate_return = merged["equity_candidate"].pct_change(window)
    benchmark_return = merged["equity_spy"].pct_change(window)
    valid = candidate_return.notna() & benchmark_return.notna()
    if not valid.any():
        return float("nan")
    return round(float((candidate_return[valid] > benchmark_return[valid]).mean() * 100.0), 2)


def _period_metrics(
    *,
    candidates: dict[str, dict[str, Any]],
    periods: dict[str, dict[str, Any]],
    universe_name: str,
    initial_capital: float,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    period_results: dict[tuple[str, str], pd.DataFrame] = {}
    benchmark_result = candidates.get(BENCHMARK_ID, {}).get("result")
    if benchmark_result is None:
        return pd.DataFrame(), period_results

    for period_name, period in periods.items():
        benchmark_slice = _slice_result_for_period(
            benchmark_result,
            start=period.get("start"),
            end=period.get("end"),
            initial_capital=initial_capital,
        )
        if len(benchmark_slice) < 60:
            continue
        benchmark_metrics = calculate_metrics(benchmark_slice, BENCHMARK_ID)

        for candidate in candidates.values():
            result = _slice_result_for_period(
                candidate["result"],
                start=period.get("start"),
                end=period.get("end"),
                initial_capital=initial_capital,
            )
            if len(result) < 60:
                rows.append(
                    {
                        "universe_name": universe_name,
                        "candidate_id": candidate["candidate_id"],
                        "strategy_family": candidate["strategy_family"],
                        "period_name": period_name,
                        "missing_data_flag": True,
                        "missing_data_reason": "fewer_than_60_common_rows",
                    }
                )
                continue

            metrics = calculate_metrics(result, candidate["candidate_id"])
            btc_col = _asset_col("BTC-USD")
            btc_average_weight = float(result[btc_col].mean()) if btc_col in result else 0.0
            btc_max_weight = float(result[btc_col].max()) if btc_col in result else 0.0
            cagr_edge = float(metrics["cagr_pct"]) - float(benchmark_metrics["cagr_pct"])
            drawdown_difference = (
                float(metrics["max_drawdown_pct"]) - float(benchmark_metrics["max_drawdown_pct"])
            )
            row = {
                "universe_name": universe_name,
                "candidate_id": candidate["candidate_id"],
                "strategy_family": candidate["strategy_family"],
                "period_name": period_name,
                "start_date": metrics["start_date"],
                "end_date": metrics["end_date"],
                "end_value": metrics["end_value"],
                "CAGR": metrics["cagr_pct"],
                "max_drawdown": metrics["max_drawdown_pct"],
                "Calmar": metrics["calmar"],
                "Sharpe": metrics["sharpe"],
                "Sortino": metrics["sortino"],
                "volatility": metrics["volatility_pct"],
                "turnover": metrics["total_turnover"],
                "number_of_rebalances": metrics["trade_count"],
                "average_exposure": metrics["exposure_time_pct"],
                "BTC_average_weight": round(btc_average_weight, 4),
                "BTC_max_weight": round(btc_max_weight, 4),
                "CAGR_edge_vs_SPY": round(cagr_edge, 2),
                "max_drawdown_difference_vs_SPY": round(drawdown_difference, 2),
                "rolling_1y_beat_SPY_pct": _rolling_beat_pct(result, benchmark_slice, 252),
                "rolling_3y_beat_SPY_pct": _rolling_beat_pct(result, benchmark_slice, 756),
                "missing_data_flag": False,
                "missing_data_reason": "",
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
            rows.append(row)
            period_results[(candidate["candidate_id"], period_name)] = result

    return pd.DataFrame(rows), period_results


def _normalised_rank(series: pd.Series, *, ascending: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    ranks = values.rank(ascending=ascending, method="min")
    count = int(values.notna().sum())
    if count <= 1:
        return pd.Series(1.0, index=series.index)
    return 1.0 - ((ranks - 1.0) / (count - 1.0))


def add_phase19a_scores(metrics: pd.DataFrame, objective_weights: dict[str, float]) -> pd.DataFrame:
    if metrics.empty:
        return metrics

    scored_groups: list[pd.DataFrame] = []
    valid = metrics.loc[~metrics["missing_data_flag"].astype(bool)].copy()
    missing = metrics.loc[metrics["missing_data_flag"].astype(bool)].copy()

    for _group_key, group in valid.groupby(["universe_name", "period_name"], sort=False):
        out = group.copy()
        out["rank_cagr"] = pd.to_numeric(out["CAGR"], errors="coerce").rank(
            ascending=False,
            method="min",
        )
        out["rank_calmar"] = pd.to_numeric(out["Calmar"], errors="coerce").rank(
            ascending=False,
            method="min",
        )
        out["rank_max_drawdown"] = pd.to_numeric(out["max_drawdown"], errors="coerce").rank(
            ascending=False,
            method="min",
        )
        out["rank_turnover"] = pd.to_numeric(out["turnover"], errors="coerce").rank(
            ascending=True,
            method="min",
        )
        out["normalised_CAGR_rank"] = _normalised_rank(out["CAGR"], ascending=False)
        out["normalised_Calmar_rank"] = _normalised_rank(out["Calmar"], ascending=False)
        out["normalised_drawdown_rank"] = _normalised_rank(out["max_drawdown"], ascending=False)
        out["normalised_turnover_rank"] = 1.0 - _normalised_rank(
            out["turnover"],
            ascending=True,
        )
        out["score"] = (
            objective_weights["cagr_weight"] * out["normalised_CAGR_rank"]
            + objective_weights["calmar_weight"] * out["normalised_Calmar_rank"]
            + objective_weights["max_drawdown_weight"] * out["normalised_drawdown_rank"]
            - objective_weights["turnover_penalty_weight"] * out["normalised_turnover_rank"]
        ).round(4)
        scored_groups.append(out)

    scored = pd.concat(scored_groups, ignore_index=True) if scored_groups else pd.DataFrame()
    if not missing.empty:
        for column in [
            "rank_cagr",
            "rank_calmar",
            "rank_max_drawdown",
            "rank_turnover",
            "normalised_CAGR_rank",
            "normalised_Calmar_rank",
            "normalised_drawdown_rank",
            "normalised_turnover_rank",
            "score",
        ]:
            missing[column] = np.nan
        scored = pd.concat([scored, missing], ignore_index=True)
    if scored.empty:
        return scored
    scored["rank_score"] = scored.groupby(["universe_name", "period_name"])["score"].rank(
        ascending=False,
        method="min",
    )
    return scored


def build_phase19a_leaderboard(metrics: pd.DataFrame) -> pd.DataFrame:
    valid = metrics.loc[~metrics["missing_data_flag"].astype(bool)].copy()
    if valid.empty:
        return pd.DataFrame()

    grouped = valid.groupby(["universe_name", "candidate_id", "strategy_family"], as_index=False)
    leaderboard = grouped.agg(
        periods_tested=("period_name", "nunique"),
        average_score=("score", "mean"),
        best_period_score=("score", "max"),
        mean_CAGR=("CAGR", "mean"),
        best_CAGR=("CAGR", "max"),
        mean_CAGR_edge_vs_SPY=("CAGR_edge_vs_SPY", "mean"),
        positive_CAGR_edge_periods=("CAGR_edge_vs_SPY", lambda value: int((value > 0).sum())),
        mean_max_drawdown=("max_drawdown", "mean"),
        worst_max_drawdown=("max_drawdown", "min"),
        worst_drawdown_difference_vs_SPY=("max_drawdown_difference_vs_SPY", "min"),
        mean_Calmar=("Calmar", "mean"),
        mean_turnover=("turnover", "mean"),
        mean_rolling_1y_beat_SPY_pct=("rolling_1y_beat_SPY_pct", "mean"),
        mean_rolling_3y_beat_SPY_pct=("rolling_3y_beat_SPY_pct", "mean"),
        BTC_average_weight=("BTC_average_weight", "mean"),
        BTC_max_weight=("BTC_max_weight", "max"),
        live_trading_allowed=("live_trading_allowed", "max"),
        real_money_allowed=("real_money_allowed", "max"),
        broker_api_integration_allowed=("broker_api_integration_allowed", "max"),
    )
    leaderboard["average_score"] = leaderboard["average_score"].round(4)
    leaderboard["rank_score"] = leaderboard["average_score"].rank(ascending=False, method="min")
    return leaderboard.sort_values(["rank_score", "candidate_id"]).reset_index(drop=True)


def build_phase19a_finalist_classifications(
    leaderboard: pd.DataFrame,
    *,
    rules: dict[str, Any],
) -> pd.DataFrame:
    if leaderboard.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for row in leaderboard.to_dict("records"):
        positive_edge = int(row.get("positive_CAGR_edge_periods", 0)) > 0
        drawdown_ok = (
            float(row.get("worst_drawdown_difference_vs_SPY", -999.0))
            >= -float(rules["max_drawdown_worse_than_spy_allowed_pp"])
        )
        rolling_value = row.get("mean_rolling_3y_beat_SPY_pct")
        rolling_calculable = pd.notna(rolling_value)
        rolling_ok = (
            True
            if not rolling_calculable
            else float(rolling_value) >= float(rules["min_rolling_3y_beat_spy_pct"])
        )
        safety_ok = not any(
            _bool_value(row.get(flag))
            for flag in [
                "live_trading_allowed",
                "real_money_allowed",
                "broker_api_integration_allowed",
            ]
        )
        high_turnover = float(row.get("mean_turnover", 0.0)) > 20.0
        btc_weight = float(row.get("BTC_max_weight", 0.0))

        finalist = positive_edge and drawdown_ok and rolling_ok and safety_ok and not high_turnover
        if finalist and btc_weight > 0:
            classification = "finalist_high_growth_high_caveat"
        elif finalist and float(row.get("mean_CAGR_edge_vs_SPY", 0.0)) <= 0:
            classification = "finalist_defensive_growth"
        elif finalist:
            classification = "finalist_clean_growth"
        elif positive_edge or drawdown_ok:
            classification = "research_only"
        else:
            classification = "rejected"

        reasons = []
        if not positive_edge:
            reasons.append("no_positive_cagr_edge_vs_spy")
        if not drawdown_ok:
            reasons.append("drawdown_worse_than_spy_limit")
        if not rolling_ok:
            reasons.append("rolling_3y_beat_rate_below_threshold")
        if not safety_ok:
            reasons.append("safety_flag_true")
        if high_turnover:
            reasons.append("high_turnover_penalty")
        if btc_weight > 0:
            reasons.append("btc_high_caveat")

        rows.append(
            {
                **row,
                "classification": classification,
                "positive_cagr_edge_vs_spy_passed": positive_edge,
                "drawdown_limit_passed": drawdown_ok,
                "rolling_3y_beat_spy_reference_threshold": rules[
                    "min_rolling_3y_beat_spy_pct"
                ],
                "rolling_3y_beat_spy_reference_passed": rolling_ok,
                "high_turnover_flag": high_turnover,
                "btc_high_caveat": btc_weight > 0,
                "paper_only": True,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "blocking_reasons": ";".join(reasons),
            }
        )

    return pd.DataFrame(rows)


def build_phase19a_robustness_flags(classifications: pd.DataFrame) -> pd.DataFrame:
    if classifications.empty:
        return pd.DataFrame()

    flag_columns = [
        "positive_cagr_edge_vs_spy_passed",
        "drawdown_limit_passed",
        "rolling_3y_beat_spy_reference_passed",
        "high_turnover_flag",
        "btc_high_caveat",
    ]
    rows: list[dict[str, Any]] = []
    for row in classifications.to_dict("records"):
        for column in flag_columns:
            rows.append(
                {
                    "universe_name": row["universe_name"],
                    "candidate_id": row["candidate_id"],
                    "classification": row["classification"],
                    "flag_name": column,
                    "flag_value": bool(row.get(column, False)),
                    "notes": row.get("blocking_reasons", ""),
                }
            )
    return pd.DataFrame(rows)


def build_phase19a_entity_contribution_summary(
    *,
    leaderboard: pd.DataFrame,
    classifications: pd.DataFrame,
    candidate_results: dict[tuple[str, str], dict[str, Any]],
) -> pd.DataFrame:
    if leaderboard.empty:
        return pd.DataFrame()

    top20 = leaderboard.sort_values("rank_score").head(20)
    finalists = classifications.loc[
        classifications["classification"].astype(str).str.startswith("finalist")
    ].copy()
    finalist_keys = {
        (row["universe_name"], row["candidate_id"])
        for row in finalists.to_dict("records")
    }
    top20_keys = {
        (row["universe_name"], row["candidate_id"])
        for row in top20.to_dict("records")
    }
    all_symbols = sorted(
        {
            symbol
            for key in set(finalist_keys).union(top20_keys)
            for symbol in candidate_results.get(key, {}).get("symbols", [])
            if symbol != CASH
        }
    )

    best = leaderboard.iloc[0]
    best_score = float(best["average_score"])
    best_non_btc = leaderboard.loc[pd.to_numeric(leaderboard["BTC_max_weight"]) <= 0]
    best_non_btc_score = (
        float(best_non_btc["average_score"].max()) if not best_non_btc.empty else np.nan
    )
    btc_necessary_for_top_score = bool(
        float(best.get("BTC_max_weight", 0.0)) > 0
        and pd.notna(best_non_btc_score)
        and best_score > best_non_btc_score
    )
    qqq_useful = bool(
        any(
            "QQQ" in candidate_results.get(key, {}).get("symbols", [])
            for key in finalist_keys or top20_keys
        )
    )
    gld_tlt_rows = leaderboard.loc[
        leaderboard["universe_name"].astype(str).str.contains("defensive|expanded", regex=True)
    ]
    simple_rows = leaderboard.loc[
        leaderboard["universe_name"].astype(str).isin(["core_us_growth", "btc_capped_growth"])
    ]
    gld_tlt_help = bool(
        not gld_tlt_rows.empty
        and not simple_rows.empty
        and float(gld_tlt_rows["worst_max_drawdown"].max())
        > float(simple_rows["worst_max_drawdown"].max())
    )
    expanded_rows = leaderboard.loc[
        leaderboard["universe_name"].astype(str).str.startswith("expanded")
    ]
    core_rows = leaderboard.loc[leaderboard["universe_name"].astype(str) == "core_us_growth"]
    expanded_improves = bool(
        not expanded_rows.empty
        and not core_rows.empty
        and float(expanded_rows["average_score"].max()) > float(core_rows["average_score"].max())
    )

    rows: list[dict[str, Any]] = []
    for symbol in all_symbols:
        top_count = 0
        finalist_count = 0
        weights: list[float] = []
        for key in top20_keys:
            result_info = candidate_results.get(key, {})
            result = result_info.get("result")
            if result is None:
                continue
            col = _asset_col(symbol)
            if col in result and float(result[col].mean()) > 0:
                top_count += 1
        for key in finalist_keys:
            result_info = candidate_results.get(key, {})
            result = result_info.get("result")
            if result is None:
                continue
            col = _asset_col(symbol)
            if col in result and float(result[col].mean()) > 0:
                finalist_count += 1
                weights.append(float(result[col].mean()))
        rows.append(
            {
                "symbol": symbol,
                "appears_in_top20_count": top_count,
                "appears_in_finalist_count": finalist_count,
                "average_weight_among_finalists": round(float(np.mean(weights)), 4)
                if weights
                else 0.0,
                "btc_necessary_for_top_score": btc_necessary_for_top_score,
                "qqq_nasdaq_consistently_useful": qqq_useful,
                "gld_tlt_drawdown_helpful": gld_tlt_help,
                "expanded_universe_improves_over_simple_spy_qqq": expanded_improves,
            }
        )

    return pd.DataFrame(rows)


def _write_csv(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _plot_risk_return(leaderboard: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    if not leaderboard.empty:
        ax.scatter(
            pd.to_numeric(leaderboard["worst_max_drawdown"], errors="coerce"),
            pd.to_numeric(leaderboard["mean_CAGR"], errors="coerce"),
            s=45,
            alpha=0.75,
        )
    ax.set_title("Phase 19A Risk/Return Scatter")
    ax.set_xlabel("Worst max drawdown (%)")
    ax.set_ylabel("Mean CAGR (%)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_top_equity(
    leaderboard: pd.DataFrame,
    candidate_results: dict[tuple[str, str], dict[str, Any]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    for row in leaderboard.sort_values("rank_score").head(5).to_dict("records"):
        key = (row["universe_name"], row["candidate_id"])
        result = candidate_results.get(key, {}).get("result")
        if result is None or result.empty:
            continue
        series = result.copy()
        series["date"] = pd.to_datetime(series["date"])
        ax.plot(series["date"], series["equity"], label=f"{row['universe_name']}:{row['candidate_id']}")
    ax.set_title("Phase 19A Top Candidate Equity Curves")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_top_drawdown(
    leaderboard: pd.DataFrame,
    candidate_results: dict[tuple[str, str], dict[str, Any]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    for row in leaderboard.sort_values("rank_score").head(5).to_dict("records"):
        key = (row["universe_name"], row["candidate_id"])
        result = candidate_results.get(key, {}).get("result")
        if result is None or result.empty:
            continue
        series = result.copy()
        series["date"] = pd.to_datetime(series["date"])
        ax.plot(
            series["date"],
            calculate_drawdown(series["equity"]) * 100.0,
            label=f"{row['universe_name']}:{row['candidate_id']}",
        )
    ax.set_title("Phase 19A Top Candidate Drawdowns")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_entity_usage(entity_summary: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    if not entity_summary.empty:
        plot_frame = entity_summary.sort_values("appears_in_finalist_count", ascending=False)
        ax.bar(plot_frame["symbol"], plot_frame["appears_in_finalist_count"])
    ax.set_title("Phase 19A Entity Usage By Finalists")
    ax.set_ylabel("Finalist count")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    leaderboard: pd.DataFrame,
    finalists: pd.DataFrame,
    entity_summary: pd.DataFrame,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top = leaderboard.head(5)
    lines = [
        "# Phase 19A Multi-Universe Strategy Factory",
        "",
        "Research/model-selection only.",
        "",
        "- NO LIVE TRADING",
        "- NO REAL MONEY",
        "- NO BROKER/API",
        "- No final model is promoted in Phase 19A.",
        "- Phase 18 safety gates remain mandatory before any paper use.",
        "",
        "## Outputs",
        "",
        "- `leaderboard_top20.csv`",
        "- `finalist_shortlist.csv`",
        "- `entity_roster_summary.csv`",
        "- `period_score_summary.csv`",
        "- `risk_return_scatter.png`",
        "- `top_candidates_equity.png`",
        "- `top_candidates_drawdown.png`",
        "- `entity_usage_by_finalists.png`",
        "",
        "## Top Candidates",
        "",
    ]
    if top.empty:
        lines.append("No candidates were available.")
    else:
        for row in top.to_dict("records"):
            lines.append(
                f"- `{row['universe_name']}:{row['candidate_id']}` score "
                f"{float(row['average_score']):.4f}, mean CAGR "
                f"{float(row['mean_CAGR']):.2f}%"
            )
    lines.extend(["", "## Finalists", ""])
    if finalists.empty:
        lines.append("No finalists passed Phase 19A rules.")
    else:
        for row in finalists.to_dict("records"):
            lines.append(
                f"- `{row['universe_name']}:{row['candidate_id']}`: "
                f"{row['classification']} (promotion_allowed=False)"
            )
    lines.extend(["", "## Entity Summary", ""])
    if not entity_summary.empty:
        for row in entity_summary.to_dict("records"):
            lines.append(
                f"- `{row['symbol']}` finalist count: "
                f"{int(row['appears_in_finalist_count'])}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _period_score_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    valid = metrics.loc[~metrics["missing_data_flag"].astype(bool)].copy()
    if valid.empty:
        return pd.DataFrame()
    return (
        valid.groupby("period_name", as_index=False)
        .agg(
            candidates_tested=("candidate_id", "count"),
            average_score=("score", "mean"),
            best_score=("score", "max"),
            best_CAGR=("CAGR", "max"),
            best_Calmar=("Calmar", "max"),
            best_drawdown=("max_drawdown", "max"),
        )
        .round(4)
    )


def _universe_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    valid = metrics.loc[~metrics["missing_data_flag"].astype(bool)].copy()
    if valid.empty:
        return pd.DataFrame()
    return (
        valid.groupby("universe_name", as_index=False)
        .agg(
            candidates_tested=("candidate_id", "nunique"),
            periods_tested=("period_name", "nunique"),
            average_score=("score", "mean"),
            best_score=("score", "max"),
            best_CAGR=("CAGR", "max"),
            best_max_drawdown=("max_drawdown", "max"),
            best_Calmar=("Calmar", "max"),
        )
        .round(4)
    )


def save_phase19a_strategy_factory_multiverse(
    *,
    config: dict[str, Any],
    reports_dir: Path,
    price_data: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Path]:
    section = _phase_config(config)
    output_dir = Path(section.get("output_dir", reports_dir / "strategy_factory/multiverse"))
    dashboard_dir = Path(
        section.get("dashboard_dir", output_dir / "dashboard")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    safety_flags = {
        "paper_only": _bool_value(section.get("paper_only", True)),
        "live_trading_allowed": _bool_value(section.get("live_trading_allowed", False)),
        "real_money_allowed": _bool_value(section.get("real_money_allowed", False)),
        "broker_api_integration_allowed": _bool_value(
            section.get("broker_api_integration_allowed", False)
        ),
    }

    universes = parse_universe_config(section)
    periods = _evaluation_periods(section)
    initial_capital = float(section.get("initial_capital", 10000))
    objective_weights = _objective_weights(section)
    finalist_rules = _finalist_rules(section)

    all_metric_frames: list[pd.DataFrame] = []
    missing_rows: list[dict[str, Any]] = []
    candidate_results: dict[tuple[str, str], dict[str, Any]] = {}

    for universe_name, universe in universes.items():
        symbols = universe["symbols"]
        if "SPY" not in symbols:
            missing_rows.append(
                {
                    "universe_name": universe_name,
                    "candidate_id": BENCHMARK_ID,
                    "strategy_family": "baseline",
                    "period_name": "all",
                    "missing_data_flag": True,
                    "missing_data_reason": "spy_benchmark_missing_from_universe",
                }
            )
            continue

        if price_data is None:
            loaded_data, _data_dir, missing_symbols = load_multiverse_price_data(
                config=config,
                section=section,
                symbols=symbols,
            )
        else:
            loaded_data = {
                symbol: frame
                for symbol, frame in price_data.items()
                if symbol in _real_symbols(symbols)
            }
            missing_symbols = [
                symbol for symbol in _real_symbols(symbols) if symbol not in loaded_data
            ]

        available_symbols = [symbol for symbol in symbols if symbol == CASH or symbol in loaded_data]
        if "SPY" not in available_symbols or len(_real_symbols(available_symbols)) < 1:
            missing_rows.append(
                {
                    "universe_name": universe_name,
                    "candidate_id": BENCHMARK_ID,
                    "strategy_family": "baseline",
                    "period_name": "all",
                    "missing_data_flag": True,
                    "missing_data_reason": f"missing_symbols:{','.join(missing_symbols)}",
                }
            )
            continue

        try:
            panel = build_multiverse_price_panel(loaded_data, available_symbols)
        except ValueError as exc:
            missing_rows.append(
                {
                    "universe_name": universe_name,
                    "candidate_id": BENCHMARK_ID,
                    "strategy_family": "baseline",
                    "period_name": "all",
                    "missing_data_flag": True,
                    "missing_data_reason": str(exc),
                }
            )
            continue

        candidates = run_multiverse_candidates_for_universe(
            panel,
            universe_name=universe_name,
            symbols=available_symbols,
            allow_btc=bool(universe["allow_btc"]),
            btc_caps=list(universe["btc_caps"]),
            initial_capital=initial_capital,
        )
        for candidate in candidates.values():
            candidate_results[(universe_name, candidate["candidate_id"])] = candidate
        metrics, _period_results = _period_metrics(
            candidates=candidates,
            periods=periods,
            universe_name=universe_name,
            initial_capital=initial_capital,
        )
        if not metrics.empty:
            all_metric_frames.append(metrics)

    metrics = (
        pd.concat(all_metric_frames, ignore_index=True)
        if all_metric_frames
        else pd.DataFrame()
    )
    if missing_rows:
        metrics = pd.concat([metrics, pd.DataFrame(missing_rows)], ignore_index=True)
    if not metrics.empty:
        metrics = add_phase19a_scores(metrics, objective_weights)

    leaderboard = build_phase19a_leaderboard(metrics) if not metrics.empty else pd.DataFrame()
    classifications = build_phase19a_finalist_classifications(
        leaderboard,
        rules=finalist_rules,
    )
    finalists = (
        classifications.loc[
            classifications["classification"].astype(str).str.startswith("finalist")
        ].copy()
        if not classifications.empty
        else pd.DataFrame()
    )
    rejected = (
        classifications.loc[classifications["classification"].astype(str) == "rejected"].copy()
        if not classifications.empty
        else pd.DataFrame()
    )
    robustness_flags = build_phase19a_robustness_flags(classifications)
    entity_summary = build_phase19a_entity_contribution_summary(
        leaderboard=leaderboard,
        classifications=classifications,
        candidate_results=candidate_results,
    )
    universe_metrics = _universe_metrics(metrics) if not metrics.empty else pd.DataFrame()
    period_metrics = _period_score_summary(metrics) if not metrics.empty else pd.DataFrame()

    outputs: dict[str, Path] = {}
    outputs["summary"] = _write_csv(
        output_dir / "phase19a_summary.csv",
        pd.DataFrame(
            [
                {
                    "universes_configured": len(universes),
                    "candidates_tested": int(leaderboard["candidate_id"].nunique())
                    if not leaderboard.empty
                    else 0,
                    "period_rows": len(metrics),
                    "finalists": len(finalists),
                    "paper_only": safety_flags["paper_only"],
                    "promotion_allowed": False,
                    "live_trading_allowed": safety_flags["live_trading_allowed"],
                    "real_money_allowed": safety_flags["real_money_allowed"],
                    "broker_api_integration_allowed": safety_flags[
                        "broker_api_integration_allowed"
                    ],
                    "decision": "strategy_factory_multiverse_completed_no_promotion"
                    if not leaderboard.empty
                    and safety_flags["paper_only"]
                    and not safety_flags["live_trading_allowed"]
                    and not safety_flags["real_money_allowed"]
                    and not safety_flags["broker_api_integration_allowed"]
                    else "strategy_factory_multiverse_failed",
                }
            ]
        ),
    )
    outputs["candidate_metrics"] = _write_csv(
        output_dir / "phase19a_candidate_metrics.csv",
        metrics,
    )
    outputs["universe_metrics"] = _write_csv(
        output_dir / "phase19a_universe_metrics.csv",
        universe_metrics,
    )
    outputs["period_metrics"] = _write_csv(
        output_dir / "phase19a_period_metrics.csv",
        period_metrics,
    )
    outputs["leaderboard"] = _write_csv(
        output_dir / "phase19a_leaderboard.csv",
        leaderboard,
    )
    outputs["finalist_shortlist"] = _write_csv(
        output_dir / "phase19a_finalist_shortlist.csv",
        finalists,
    )
    outputs["rejected_candidates"] = _write_csv(
        output_dir / "phase19a_rejected_candidates.csv",
        rejected,
    )
    outputs["robustness_flags"] = _write_csv(
        output_dir / "phase19a_robustness_flags.csv",
        robustness_flags,
    )
    outputs["entity_contribution_summary"] = _write_csv(
        output_dir / "phase19a_entity_contribution_summary.csv",
        entity_summary,
    )

    gate_passed = (
        not leaderboard.empty
        and outputs["candidate_metrics"].exists()
        and outputs["leaderboard"].exists()
        and outputs["finalist_shortlist"].exists()
        and safety_flags["paper_only"]
        and not safety_flags["live_trading_allowed"]
        and not safety_flags["real_money_allowed"]
        and not safety_flags["broker_api_integration_allowed"]
    )
    gate_report = pd.DataFrame(
        [
            {"gate": "candidate_metrics_written", "passed": outputs["candidate_metrics"].exists()},
            {"gate": "leaderboard_written", "passed": outputs["leaderboard"].exists()},
            {
                "gate": "finalist_shortlist_written",
                "passed": outputs["finalist_shortlist"].exists(),
            },
            {"gate": "paper_only_true", "passed": safety_flags["paper_only"]},
            {
                "gate": "live_trading_false",
                "passed": not safety_flags["live_trading_allowed"],
            },
            {"gate": "real_money_false", "passed": not safety_flags["real_money_allowed"]},
            {
                "gate": "broker_api_false",
                "passed": not safety_flags["broker_api_integration_allowed"],
            },
            {"gate": "promotion_allowed_false", "passed": True},
        ]
    )
    outputs["gate_report"] = _write_csv(output_dir / "phase19a_gate_report.csv", gate_report)
    outputs["conclusion"] = _write_csv(
        output_dir / "phase19a_conclusion.csv",
        pd.DataFrame(
            [
                {
                    "phase19a_decision": "strategy_factory_multiverse_completed_no_promotion"
                    if gate_passed
                    else "strategy_factory_multiverse_failed",
                    "final_model_promoted": False,
                    "promotion_allowed": False,
                    "paper_only": True,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                    "notes": "Research/model-selection only. Phase18 safety gates remain mandatory.",
                }
            ]
        ),
    )

    dashboard_top20 = leaderboard.sort_values("rank_score").head(20).copy()
    outputs["dashboard_leaderboard_top20"] = _write_csv(
        dashboard_dir / "leaderboard_top20.csv",
        dashboard_top20,
    )
    outputs["dashboard_finalist_shortlist"] = _write_csv(
        dashboard_dir / "finalist_shortlist.csv",
        finalists,
    )
    outputs["dashboard_entity_roster_summary"] = _write_csv(
        dashboard_dir / "entity_roster_summary.csv",
        entity_summary,
    )
    outputs["dashboard_period_score_summary"] = _write_csv(
        dashboard_dir / "period_score_summary.csv",
        period_metrics,
    )

    _plot_risk_return(leaderboard, dashboard_dir / "risk_return_scatter.png")
    _plot_top_equity(leaderboard, candidate_results, dashboard_dir / "top_candidates_equity.png")
    _plot_top_drawdown(
        leaderboard,
        candidate_results,
        dashboard_dir / "top_candidates_drawdown.png",
    )
    _plot_entity_usage(entity_summary, dashboard_dir / "entity_usage_by_finalists.png")
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        leaderboard=leaderboard,
        finalists=finalists,
        entity_summary=entity_summary,
    )
    outputs["dashboard_index"] = dashboard_dir / "index.md"
    outputs["risk_return_scatter"] = dashboard_dir / "risk_return_scatter.png"
    outputs["top_candidates_equity"] = dashboard_dir / "top_candidates_equity.png"
    outputs["top_candidates_drawdown"] = dashboard_dir / "top_candidates_drawdown.png"
    outputs["entity_usage_by_finalists"] = dashboard_dir / "entity_usage_by_finalists.png"

    return outputs
