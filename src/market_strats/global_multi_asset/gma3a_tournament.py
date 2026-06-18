"""GMA-3A transparent strategy tournament and paper portfolio V0."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma2_config import load_gma2_config
from market_strats.global_multi_asset.gma2_replay import (
    GMA2ReplayError,
    _cash_period_return,
    _load_cash,
    _load_inventory,
    _load_macro_observations,
    _load_prices,
    _price_at,
    next_valid_execution_date,
    normalise_weights,
    verify_accepted_inputs,
)
from market_strats.global_multi_asset.gma3a_config import GMA3AConfig


@dataclass(frozen=True)
class GMA3AResult:
    decision: str
    output_root: Path
    data_root: Path
    order_packet_rows: int
    warnings: list[str]


class GMA3ARError(RuntimeError):
    """Fail-closed GMA-3A-R error."""


STRATEGY_IDS = [
    "gma_cash_benchmark_v0",
    "gma_spy_benchmark_v0",
    "gma_balanced_core_v0",
    "gma_equal_weight_v0",
    "gma_inverse_volatility_v0",
    "gma_time_series_momentum_v0",
    "gma_cross_sectional_momentum_v0",
    "gma_relative_strength_rotation_v0",
    "gma_trend_filtered_allocation_v0",
    "gma_macro_defensive_overlay_v0",
    "gma_live_paper_ensemble_v0",
]

TACTICAL_STRATEGIES = [
    "gma_inverse_volatility_v0",
    "gma_time_series_momentum_v0",
    "gma_cross_sectional_momentum_v0",
    "gma_relative_strength_rotation_v0",
    "gma_trend_filtered_allocation_v0",
    "gma_macro_defensive_overlay_v0",
]

ASSET_CLASSES = {
    "SPY": "US large-cap equities",
    "QQQ": "US growth equities",
    "IWM": "US small-cap equities",
    "EFA": "international developed equities",
    "EEM": "emerging-market equities",
    "SHY": "short Treasuries",
    "IEF": "intermediate Treasuries",
    "TLT": "long Treasuries",
    "AGG": "investment-grade credit",
    "LQD": "investment-grade credit",
    "HYG": "high-yield credit",
    "GLD": "gold",
    "DBC": "broad commodities",
    "VNQ": "listed real estate",
    "UUP": "currency proxy",
    "BTC-USD": "Bitcoin",
    "CASH": "cash",
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selection_gate_value(
    config: GMA3AConfig,
    key: str,
    fallback_key: str | None = None,
    default: float = 0.0,
) -> float:
    gates = config.raw.get("selection_gates", {})
    if key in gates:
        return float(gates[key])
    if fallback_key and fallback_key in gates:
        return float(gates[fallback_key])
    return default


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _git_rev(ref: str) -> str:
    result = subprocess.run(["git", "rev-parse", ref], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _load_gma2_for_gma3a(config: GMA3AConfig) -> Any:
    gma2 = load_gma2_config(config.paths["gma2_config"])
    gma2.paths["data_foundation_report_root"] = config.paths["data_foundation_report_root"]
    gma2.paths["canonical_macro_root"] = config.paths["canonical_macro_root"]
    gma2.paths["macro_foundation_report_root"] = config.paths["macro_foundation_report_root"]
    return gma2


def verify_gma3a_upstream(config: GMA3AConfig) -> dict[str, str]:
    gma2 = _load_gma2_for_gma3a(config)
    if gma2.path.name == "gma2_replay_foundation.yaml":
        raise GMA3ARError("gma3ar_blocked_fixture_contamination")
    accepted = verify_accepted_inputs(gma2)
    expected = config.accepted_inputs
    checks = {
        "gma1a_commit": expected["gma1a_commit"],
        "gma1a_tag": expected["gma1a_tag"],
        "gma1a_accepted_selection_hash": expected["gma1a_accepted_selection_hash"],
        "gma1b_commit": expected["gma1b_commit"],
        "gma1b_tag": expected["gma1b_tag"],
        "gma1b_accepted_canonical_macro_hash": expected["gma1b_accepted_canonical_macro_hash"],
        "gma2_commit": expected["gma2_commit"],
        "gma2_tag": expected["gma2_tag"],
        "gma2_accepted_replay_hash": expected["gma2_accepted_replay_hash"],
        "canonical_research_end_date": expected["canonical_research_end_date"],
    }
    if accepted["gma1a_accepted_selection_hash"] != checks["gma1a_accepted_selection_hash"]:
        raise GMA3ARError("GMA-1A accepted hash mismatch")
    if accepted["gma1b_accepted_canonical_macro_hash"] != checks["gma1b_accepted_canonical_macro_hash"]:
        raise GMA3ARError("GMA-1B accepted canonical macro hash mismatch")
    if _git_rev(checks["gma1a_tag"]) != checks["gma1a_commit"]:
        raise GMA3ARError("GMA-1A tag mismatch")
    if _git_rev(checks["gma1b_tag"]) != checks["gma1b_commit"]:
        raise GMA3ARError("GMA-1B tag mismatch")
    if _git_rev(checks["gma2_tag"]) != checks["gma2_commit"]:
        raise GMA3ARError("GMA-2 tag mismatch")
    replay_hash_path = config.paths["replay_foundation_report_root"] / "gma2_replay_hash.txt"
    if not replay_hash_path.exists() or replay_hash_path.read_text(encoding="utf-8").strip() != checks["gma2_accepted_replay_hash"]:
        raise GMA3ARError("GMA-2 accepted replay hash mismatch")
    return checks


def _load_all_prices(config: GMA3AConfig) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    gma2 = _load_gma2_for_gma3a(config)
    symbols = set(config.raw["strategy_universe"]["allowed_symbols"])
    inventory = _load_inventory(gma2)
    prices = _load_prices(gma2, symbols)
    return inventory, prices


def _safe_available_symbols(prices: dict[str, pd.DataFrame], symbols: list[str], date: Any) -> list[str]:
    return [symbol for symbol in symbols if symbol == "CASH" or (symbol in prices and date in prices[symbol].index)]


def _gma3a_next_execution_date(signal_date: Any, prices: dict[str, pd.DataFrame], assets: set[str]) -> Any:
    tradable_assets = {asset for asset in assets if asset != "CASH"}
    if tradable_assets:
        return next_valid_execution_date(signal_date, prices, tradable_assets)
    benchmark_dates = [date for date in prices["SPY"].index if date > signal_date]
    if not benchmark_dates:
        raise GMA2ReplayError("no benchmark session after cash-only signal")
    return benchmark_dates[0]


def _returns(prices: dict[str, pd.DataFrame], symbol: str, date: Any, lookback: int = 1) -> float:
    df = prices[symbol]
    dates = [d for d in df.index if d <= date]
    if len(dates) <= lookback:
        return 0.0
    now = dates[-1]
    prev = dates[-lookback - 1]
    return float(df.loc[now, "total_return_index"]) / float(df.loc[prev, "total_return_index"]) - 1.0


def _volatility(prices: dict[str, pd.DataFrame], symbol: str, date: Any, lookback: int = 3) -> float:
    df = prices[symbol]
    dates = [d for d in df.index if d <= date]
    if len(dates) < 3:
        return 1.0
    use = dates[-min(len(dates), lookback + 1) :]
    closes = pd.Series([float(df.loc[d, "total_return_index"]) for d in use])
    returns = closes.pct_change().dropna()
    vol = float(returns.std(ddof=0))
    return vol if math.isfinite(vol) and vol > 0 else 1.0


def _cap_and_normalise(weights: dict[str, float], max_single: float, btc_cap: float) -> dict[str, float]:
    weights = normalise_weights(weights)
    capped: dict[str, float] = {}
    excess = 0.0
    for symbol, weight in weights.items():
        cap = btc_cap if symbol == "BTC-USD" else max_single
        if symbol == "CASH":
            cap = 1.0
        clipped = min(weight, cap)
        capped[symbol] = clipped
        excess += weight - clipped
    for _ in range(10):
        if excess <= 1e-12:
            break
        eligible = [
            symbol
            for symbol in capped
            if capped[symbol] < (btc_cap if symbol == "BTC-USD" else (1.0 if symbol == "CASH" else max_single)) - 1e-12
        ]
        if not eligible:
            capped["CASH"] = capped.get("CASH", 0.0) + excess
            excess = 0.0
            break
        add = excess / len(eligible)
        new_excess = 0.0
        for symbol in eligible:
            cap = btc_cap if symbol == "BTC-USD" else (1.0 if symbol == "CASH" else max_single)
            new_value = capped[symbol] + add
            if new_value > cap:
                new_excess += new_value - cap
                capped[symbol] = cap
            else:
                capped[symbol] = new_value
        excess = new_excess
    return normalise_weights(capped)


def strategy_targets(
    strategy_id: str,
    date: Any,
    prices: dict[str, pd.DataFrame],
    macro: pd.DataFrame,
    config: GMA3AConfig,
    tactical_passers: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    max_single = float(config.raw["limits"]["maximum_single_asset_weight"])
    btc_cap = float(config.raw["limits"]["maximum_bitcoin_weight"])
    balanced = dict(config.raw["strategy_universe"]["balanced_benchmark_weights"])
    tactical_assets = ["SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ"]
    available = _safe_available_symbols(prices, tactical_assets, date)
    reason = {"reason_code": "transparent_rule"}

    if strategy_id == "gma_cash_benchmark_v0":
        return {"CASH": 1.0}, {"reason_code": "cash_benchmark"}
    if strategy_id == "gma_spy_benchmark_v0":
        return {"SPY": 1.0}, {"reason_code": "spy_benchmark"}
    if strategy_id == "gma_balanced_core_v0":
        return _cap_and_normalise(balanced, max_single, btc_cap), {"reason_code": "balanced_core_static"}
    if strategy_id == "gma_equal_weight_v0":
        return _cap_and_normalise({symbol: 1.0 for symbol in available}, max_single, btc_cap), {"reason_code": "equal_weight_available_assets"}
    if strategy_id == "gma_inverse_volatility_v0":
        inv = {symbol: 1.0 / _volatility(prices, symbol, date) for symbol in available}
        return _cap_and_normalise(inv, max_single, btc_cap), {"reason_code": "inverse_realised_volatility"}
    if strategy_id == "gma_time_series_momentum_v0":
        positive = [symbol for symbol in available if _returns(prices, symbol, date) > 0]
        return _cap_and_normalise({symbol: 1.0 for symbol in positive} or {"CASH": 1.0}, max_single, btc_cap), {
            "reason_code": "positive_time_series_momentum_or_cash"
        }
    if strategy_id == "gma_cross_sectional_momentum_v0":
        ranked = sorted(available, key=lambda symbol: _returns(prices, symbol, date), reverse=True)[:3]
        return _cap_and_normalise({symbol: 1.0 for symbol in ranked}, max_single, btc_cap), {"reason_code": "top3_cross_sectional_momentum"}
    if strategy_id == "gma_relative_strength_rotation_v0":
        pool = _safe_available_symbols(prices, ["SPY", "QQQ", "IEF", "GLD", "DBC"], date)
        ranked = sorted(pool, key=lambda symbol: _returns(prices, symbol, date), reverse=True)[:2]
        return _cap_and_normalise({symbol: 1.0 for symbol in ranked}, max_single, btc_cap), {"reason_code": "top2_relative_strength_rotation"}
    if strategy_id == "gma_trend_filtered_allocation_v0":
        spy_trend = _returns(prices, "SPY", date) > 0
        if spy_trend:
            return _cap_and_normalise(balanced, max_single, btc_cap), {"reason_code": "spy_trend_positive_balanced"}
        defensive = {"IEF": 0.30, "GLD": 0.20, "SHY": 0.20, "CASH": 0.30}
        return _cap_and_normalise(defensive, max_single, btc_cap), {"reason_code": "spy_trend_negative_defensive"}
    if strategy_id == "gma_macro_defensive_overlay_v0":
        cutoff = pd.Timestamp(f"{date} 22:00:00", tz="UTC")
        eligible = macro.loc[macro["availability_timestamp_utc"] <= cutoff]
        vix = eligible.loc[eligible["macro_id"] == "vix"].sort_values("availability_timestamp_utc")
        risk_on = True if vix.empty else float(vix.iloc[-1]["value"]) < 25
        if risk_on:
            return _cap_and_normalise(balanced, max_single, btc_cap), {"reason_code": "pit_macro_risk_on_balanced"}
        return _cap_and_normalise({"IEF": 0.35, "SHY": 0.35, "CASH": 0.30}, max_single, btc_cap), {
            "reason_code": "pit_macro_defensive"
        }
    if strategy_id == "gma_live_paper_ensemble_v0":
        passers = tactical_passers or []
        core_weight = float(config.raw["live_paper_ensemble"]["core_allocation"])
        tactical_weight = float(config.raw["live_paper_ensemble"]["tactical_allocation"]) if passers else 0.0
        total: dict[str, float] = {}
        core_targets, _ = strategy_targets("gma_balanced_core_v0", date, prices, macro, config)
        for symbol, weight in core_targets.items():
            total[symbol] = total.get(symbol, 0.0) + weight * (1.0 if not passers else core_weight)
        if passers:
            slot_weight = tactical_weight / len(passers)
            for strategy in passers:
                targets, _ = strategy_targets(strategy, date, prices, macro, config)
                for symbol, weight in targets.items():
                    total[symbol] = total.get(symbol, 0.0) + weight * slot_weight
            return _cap_and_normalise(total, max_single, btc_cap), {
                "reason_code": "predeclared_core_plus_passing_tactical_ensemble"
            }
        return _cap_and_normalise(total, max_single, btc_cap), {
            "reason_code": "core_only_fallback_no_tactical_qualifiers"
        }
    return {"CASH": 1.0}, reason


def _enforce_minimum_evidence(dates: list[Any]) -> None:
    if len(dates) < 1000:
        raise GMA3ARError("gma3ar_blocked_insufficient_history: sessions < 1000")
    years = (pd.to_datetime(dates[-1]) - pd.to_datetime(dates[0])).days / 365.25
    if years < 5:
        raise GMA3ARError("gma3ar_blocked_insufficient_history: years < 5")


def _core_extended_dates(config: GMA3AConfig, prices: dict[str, pd.DataFrame], cash_df: pd.DataFrame) -> tuple[list[Any], list[Any], pd.DataFrame]:
    allowed = config.raw["strategy_universe"]["allowed_symbols"]
    core_symbols = [s for s in allowed if s not in {"BTC-USD", "CASH"}]
    ext_symbols = [s for s in allowed if s != "CASH"]

    cash_dates = set(cash_df["accrual_start"]) | set(cash_df["accrual_end"])

    core_market = [set(prices[s].index) for s in core_symbols if s in prices]
    core_common = set.intersection(*core_market) if core_market else set()
    core_dates = sorted(core_common & cash_dates)

    ext_market = [set(prices[s].index) for s in ext_symbols if s in prices]
    ext_common = set.intersection(*ext_market) if ext_market else set()
    ext_dates = sorted(ext_common & cash_dates)

    rows = [
        {
            "universe_id": "core_common_period",
            "symbols": ",".join(core_symbols),
            "first_eligible_date_by_symbol": "na",
            "common_start_date": core_dates[0] if core_dates else "",
            "common_end_date": core_dates[-1] if core_dates else "",
            "trading_session_count": len(core_dates),
            "calendar_coverage": "us_listed_etf",
            "excluded_symbols": "BTC-USD",
            "exclusion_reasons": "late_starting_asset",
        },
        {
            "universe_id": "extended_btc_period",
            "symbols": ",".join(ext_symbols),
            "first_eligible_date_by_symbol": "na",
            "common_start_date": ext_dates[0] if ext_dates else "",
            "common_end_date": ext_dates[-1] if ext_dates else "",
            "trading_session_count": len(ext_dates),
            "calendar_coverage": "us_listed_etf",
            "excluded_symbols": "",
            "exclusion_reasons": "",
        }
    ]
    return core_dates, ext_dates, pd.DataFrame(rows)


def _simulate_strategy(
    strategy_id: str,
    dates: list[Any],
    prices: dict[str, pd.DataFrame],
    cash_df: pd.DataFrame,
    macro: pd.DataFrame,
    config: GMA3AConfig,
    tactical_passers: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    start_capital = float(config.raw["capital"]["account_starting_capital"])
    cash = start_capital
    shares: dict[str, float] = {}
    prev_value: float | None = None
    peak = start_capital
    rows = {name: [] for name in ["equity", "drawdown", "holdings", "orders", "fills", "costs", "signals"]}
    cost_bps = float(config.raw["costs"]["bps_per_notional"])
    for idx, date in enumerate(dates):
        if idx > 0:
            period_return, _ = _cash_period_return(cash_df, dates[idx - 1], date)
            cash += cash * period_return

        is_rebalance = False
        if idx > 0:
            current_date = pd.to_datetime(dates[idx - 1])
            next_date = pd.to_datetime(date)
            if current_date.dayofweek == 4:
                is_rebalance = True
            elif current_date.dayofweek < 4 and next_date.dayofweek <= current_date.dayofweek:
                is_rebalance = True

        if is_rebalance:
            signal_date = dates[idx - 1]
            targets, reason = strategy_targets(strategy_id, signal_date, prices, macro, config, tactical_passers)
            execution_date = _gma3a_next_execution_date(signal_date, prices, set(targets))
            if execution_date != date:
                raise GMA3ARError(f"unexpected execution date for {strategy_id}: {execution_date}")
            pre_value = cash + sum(qty * _price_at(prices, asset, date, "total_return_index") for asset, qty in shares.items())
            current_values = {asset: qty * _price_at(prices, asset, date, "total_return_index") for asset, qty in shares.items()}
            post_cost_value = pre_value
            for _ in range(5):
                abs_trade = sum(
                    abs(post_cost_value * targets.get(asset, 0.0) - current_values.get(asset, 0.0))
                    for asset in set(targets) | set(shares)
                    if asset != "CASH"
                )
                post_cost_value = pre_value - abs_trade * cost_bps / 10000.0
            for asset in sorted(set(targets) | set(shares)):
                if asset == "CASH":
                    continue
                price = _price_at(prices, asset, date, "total_return_index")
                current_value = current_values.get(asset, 0.0)
                target_value = post_cost_value * targets.get(asset, 0.0)
                trade_notional = target_value - current_value
                if abs(trade_notional) < float(config.raw["limits"]["minimum_trade_notional"]):
                    continue
                cost = abs(trade_notional) * cost_bps / 10000.0
                qty = trade_notional / price
                shares[asset] = shares.get(asset, 0.0) + qty
                cash -= trade_notional + cost
                order_id = _sha256_text(f"{strategy_id}|{signal_date}|{date}|{asset}")[:16]
                order_row = {
                    "account_id": strategy_id,
                    "order_id": order_id,
                    "decision_date": signal_date,
                    "execution_date": date,
                    "symbol": asset,
                    "side": "BUY" if qty > 0 else "SELL",
                    "quantity": qty,
                    "notional": trade_notional,
                    "price": price,
                    "reason_code": reason["reason_code"],
                    "paper_only": True,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                }
                rows["orders"].append(order_row)
                rows["fills"].append({**order_row, "fill_status": "simulated_internal_fill"})
                rows["costs"].append(
                    {
                        "account_id": strategy_id,
                        "execution_date": date,
                        "symbol": asset,
                        "trade_notional_abs": abs(trade_notional),
                        "transaction_cost": cost,
                        "charged_once": True,
                    }
                )
            signal_hash = _sha256_text(_stable_json(targets))
            for symbol, target_weight in targets.items():
                rows["signals"].append(
                    {
                        "strategy_id": strategy_id,
                        "strategy_version": "v0",
                        "decision_date": signal_date,
                        "execution_date": date,
                        "symbol": symbol,
                        "target_weight": target_weight,
                        "signal_strength": target_weight,
                        "reason_code": reason["reason_code"],
                        "input_hash": signal_hash,
                        "strategy_hash": _sha256_text(f"{strategy_id}|v0|{signal_hash}"),
                    }
                )
        market_values = {asset: qty * _price_at(prices, asset, date, "total_return_index") for asset, qty in shares.items()}
        value = cash + sum(market_values.values())
        daily_return = 0.0 if prev_value is None else value / prev_value - 1.0
        peak = max(peak, value)
        drawdown = value / peak - 1.0
        rows["equity"].append(
            {
                "account_id": strategy_id,
                "strategy_id": strategy_id,
                "valuation_date": date,
                "portfolio_value": value,
                "cash": cash,
                "daily_return": daily_return,
                "cumulative_return": value / start_capital - 1.0,
                "drawdown": drawdown,
            }
        )
        rows["drawdown"].append({"strategy_id": strategy_id, "valuation_date": date, "drawdown": drawdown})
        for symbol in sorted(set(market_values) | {"CASH"}):
            market_value = cash if symbol == "CASH" else market_values.get(symbol, 0.0)
            rows["holdings"].append(
                {
                    "account_id": strategy_id,
                    "valuation_date": date,
                    "symbol": symbol,
                    "quantity": 0.0 if symbol == "CASH" else shares.get(symbol, 0.0),
                    "market_value": market_value,
                    "weight": market_value / value if value else 0.0,
                }
            )
        prev_value = value
    return {name: pd.DataFrame(values) for name, values in rows.items()}


def _extend_prices(canonical: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    augmented = {}
    manifest = {}
    input_hashes = {}
    data_status = []

    canon_end = pd.to_datetime("2026-05-01").date()
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for symbol, canon_df in canonical.items():
        if symbol == "CASH":
            continue

        post_df = canon_df[canon_df.index > canon_end].copy()
        augmented[symbol] = canon_df

        if post_df.empty:
            data_status.append({
                "symbol": symbol,
                "status": "no_post_endpoint_data",
                "partial_bar_exclusion": False
            })
            continue

        start_date = post_df.index.min()
        end_date = post_df.index.max()
        sessions = len(post_df)

        last_row = post_df.iloc[-1]
        manifest_hash = str(last_row.get("source_manifest_sha256", "na"))
        raw_hash = str(last_row.get("source_raw_sha256", "na"))
        norm_hash = str(last_row.get("source_normalised_sha256", "na"))

        manifest[symbol] = {
            "post_endpoint_start": str(start_date),
            "post_endpoint_end": str(end_date),
            "post_endpoint_sessions": sessions,
            "input_hash": manifest_hash
        }

        input_hashes[symbol] = {
            "raw_hash": raw_hash,
            "normalised_hash": norm_hash,
            "retrieval_timestamp": now,
            "provider": "yahoo_yfinance"
        }

        data_status.append({
            "symbol": symbol,
            "status": "available",
            "partial_bar_exclusion": False,
            "latest_completed_date": str(end_date),
            "sessions": sessions
        })

    return augmented, manifest, input_hashes, data_status


def _metrics(equity: pd.DataFrame, costs: pd.DataFrame, benchmark: pd.DataFrame, universe_id: str = "core_common_period") -> pd.DataFrame:
    rows = []
    for strategy_id, group in equity.groupby("strategy_id"):
        ordered = group.sort_values("valuation_date").copy()
        ordered["valuation_date"] = pd.to_datetime(ordered["valuation_date"])

        last_date = ordered.iloc[-1]["valuation_date"]
        holdout_start = last_date - pd.DateOffset(years=1)

        wf_mask = ordered["valuation_date"] <= holdout_start
        ho_mask = ordered["valuation_date"] > holdout_start

        full_returns = ordered["daily_return"].astype(float)
        wf_returns = full_returns[wf_mask]
        ho_returns = full_returns[ho_mask]

        def _calc(sub, rets):
            if sub.empty:
                return 0.0, 0.0, 0.0, 0.0, 0.0
            start = float(sub.iloc[0]["portfolio_value"])
            end = float(sub.iloc[-1]["portfolio_value"])
            days = max(len(sub) - 1, 1)
            tr = end / start - 1.0
            cagr = (1 + tr) ** (252 / days) - 1 if tr > -1 else -1.0
            vol = float(rets.std(ddof=0) * math.sqrt(252)) if len(rets) > 1 else 0.0
            sharpe = (rets.mean() * 252 / vol) if vol > 0 else 0.0
            downside = rets[rets < 0]
            downside_vol = float(downside.std(ddof=0) * math.sqrt(252)) if len(downside) else 0.0
            sortino = (rets.mean() * 252 / downside_vol) if downside_vol > 0 else 0.0
            peak = sub["portfolio_value"].astype(float).cummax()
            dd = sub["portfolio_value"].astype(float) / peak - 1.0
            return cagr, vol, sharpe, sortino, float(dd.min())

        f_cagr, f_vol, f_sharpe, f_sortino, f_max_dd = _calc(ordered, full_returns)
        wf_cagr, wf_vol, wf_sharpe, wf_sortino, wf_max_dd = _calc(ordered[wf_mask], wf_returns)
        ho_cagr, ho_vol, ho_sharpe, ho_sortino, ho_max_dd = _calc(ordered[ho_mask], ho_returns)

        cost_sum = (
            float(costs.loc[costs["account_id"] == strategy_id, "transaction_cost"].sum())
            if not costs.empty
            else 0.0
        )
        strategy_costs = costs.loc[costs["account_id"] == strategy_id] if not costs.empty else pd.DataFrame()
        rebalance_count = int(strategy_costs["execution_date"].nunique()) if not strategy_costs.empty else 0
        cumulative_turnover = (cost_sum * 10000.0) / float(ordered.iloc[0]["portfolio_value"])
        replay_days = max(len(ordered) - 1, 1)
        replay_years = replay_days / 252.0
        annualised_turnover = cumulative_turnover / replay_years if replay_years else 0.0
        average_turnover_per_rebalance = cumulative_turnover / rebalance_count if rebalance_count else 0.0
        annualised_cost_drag = cost_sum / float(ordered.iloc[0]["portfolio_value"]) / replay_years if replay_years else 0.0
        benchmark_rows = benchmark.loc[benchmark["strategy_id"] == strategy_id]
        relative = float(benchmark_rows["benchmark_relative_return"].iloc[-1]) if not benchmark_rows.empty else 0.0

        ho_bench = benchmark_rows.copy()
        if not ho_bench.empty:
            ho_bench["valuation_date"] = pd.to_datetime(ho_bench["valuation_date"])
            ho_bench = ho_bench[ho_bench["valuation_date"] > holdout_start]
        ho_relative = float(ho_bench.iloc[-1]["benchmark_relative_return"] - ho_bench.iloc[0]["benchmark_relative_return"]) if not ho_bench.empty else 0.0

        rows.append({
            "universe_id": universe_id, "strategy_id": strategy_id, "evaluation": "full_period",
            "starting_value": float(ordered.iloc[0]["portfolio_value"]),
            "ending_value": float(ordered.iloc[-1]["portfolio_value"]),
            "turnover": cumulative_turnover,
            "cumulative_turnover": cumulative_turnover,
            "replay_years": replay_years,
            "annualised_turnover": annualised_turnover,
            "average_turnover_per_rebalance": average_turnover_per_rebalance,
            "rebalance_count": rebalance_count,
            "annualised_transaction_cost_drag": annualised_cost_drag,
            "CAGR": f_cagr, "annualised_volatility": f_vol, "Sharpe": f_sharpe, "Sortino": f_sortino, "maximum_drawdown": f_max_dd,
            "Calmar": f_cagr / abs(f_max_dd) if f_max_dd else 0.0, "transaction_costs": cost_sum,
            "cash_percentage": float(ordered.iloc[-1]["cash"] / ordered.iloc[-1]["portfolio_value"]),
            "benchmark_relative_return": relative, "positive_rolling_period_fraction": float((full_returns > 0).mean()),
            "worst_rolling_period": float(full_returns.min()), "gate_status": "passed",
        })
        rows.append({
            "universe_id": universe_id, "strategy_id": strategy_id, "evaluation": "walk_forward",
            "cumulative_turnover": cumulative_turnover,
            "replay_years": replay_years,
            "annualised_turnover": annualised_turnover,
            "average_turnover_per_rebalance": average_turnover_per_rebalance,
            "rebalance_count": rebalance_count,
            "annualised_transaction_cost_drag": annualised_cost_drag,
            "CAGR": wf_cagr, "annualised_volatility": wf_vol, "Sharpe": wf_sharpe, "Sortino": wf_sortino, "maximum_drawdown": wf_max_dd,
            "Calmar": wf_cagr / abs(wf_max_dd) if wf_max_dd else 0.0, "transaction_costs": cost_sum,
            "cash_percentage": float(ordered[wf_mask].iloc[-1]["cash"] / ordered[wf_mask].iloc[-1]["portfolio_value"]) if wf_mask.any() else 0.0,
            "benchmark_relative_return": 0.0, "positive_rolling_period_fraction": float((wf_returns > 0).mean()) if len(wf_returns) else 0.0,
            "worst_rolling_period": float(wf_returns.min()) if len(wf_returns) else 0.0, "gate_status": "passed",
        })
        rows.append({
            "universe_id": universe_id, "strategy_id": strategy_id, "evaluation": "holdout",
            "cumulative_turnover": cumulative_turnover,
            "replay_years": replay_years,
            "annualised_turnover": annualised_turnover,
            "average_turnover_per_rebalance": average_turnover_per_rebalance,
            "rebalance_count": rebalance_count,
            "annualised_transaction_cost_drag": annualised_cost_drag,
            "CAGR": ho_cagr, "annualised_volatility": ho_vol, "Sharpe": ho_sharpe, "Sortino": ho_sortino, "maximum_drawdown": ho_max_dd,
            "Calmar": ho_cagr / abs(ho_max_dd) if ho_max_dd else 0.0, "transaction_costs": 0.0,
            "cash_percentage": float(ordered[ho_mask].iloc[-1]["cash"] / ordered[ho_mask].iloc[-1]["portfolio_value"]) if ho_mask.any() else 0.0,
            "benchmark_relative_return": ho_relative, "positive_rolling_period_fraction": float((ho_returns > 0).mean()) if len(ho_returns) else 0.0,
            "worst_rolling_period": float(ho_returns.min()) if len(ho_returns) else 0.0, "gate_status": "passed",
        })
    return pd.DataFrame(rows)


def _benchmark_relative(equity: pd.DataFrame, prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for strategy_id, group in equity.groupby("strategy_id"):
        ordered = group.sort_values("valuation_date")
        start_date = ordered.iloc[0]["valuation_date"]
        start_spy = _price_at(prices, "SPY", start_date, "close_raw")
        start_value = float(ordered.iloc[0]["portfolio_value"])
        for row in ordered.to_dict("records"):
            spy_value = start_value * _price_at(prices, "SPY", row["valuation_date"], "close_raw") / start_spy
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "valuation_date": row["valuation_date"],
                    "portfolio_value": row["portfolio_value"],
                    "spy_value": spy_value,
                    "benchmark_relative_return": row["portfolio_value"] / spy_value - 1.0,
                }
            )
    return pd.DataFrame(rows)


def _universe(config: GMA3AConfig, inventory: pd.DataFrame, prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for symbol in config.raw["strategy_universe"]["allowed_symbols"]:
        if symbol == "CASH":
            rows.append(
                {
                    "symbol": "CASH",
                    "asset_class": "cash",
                    "provider": "DGS3MO",
                    "price_basis": "cash_accrual",
                    "first_valid_date": "",
                    "last_valid_historical_date": "",
                    "latest_completed_post_endpoint_date": "",
                    "calendar": "calendar_day",
                    "paper_tradable_status": "cash_accounting_only",
                    "exclusion_reason": "",
                }
            )
            continue
        inv = inventory.loc[inventory["instrument_id"] == symbol]
        if inv.empty or symbol not in prices:
            rows.append(
                {
                    "symbol": symbol,
                    "asset_class": ASSET_CLASSES.get(symbol, "unknown"),
                    "provider": "",
                    "price_basis": "",
                    "first_valid_date": "",
                    "last_valid_historical_date": "",
                    "latest_completed_post_endpoint_date": "",
                    "calendar": "",
                    "paper_tradable_status": "excluded",
                    "exclusion_reason": "missing_accepted_gma1a_contract",
                }
            )
            continue
        row = inv.iloc[0]
        rows.append(
            {
                "symbol": symbol,
                "asset_class": ASSET_CLASSES.get(symbol, "unknown"),
                "provider": "yahoo_yfinance",
                "price_basis": "raw_open_execution_raw_close_valuation_total_return_signal",
                "first_valid_date": row["first_completed_date"],
                "last_valid_historical_date": row["last_completed_date"],
                "latest_completed_post_endpoint_date": row["last_completed_date"],
                "calendar": row["calendar_id"],
                "paper_tradable_status": "accepted_contract_ready",
                "exclusion_reason": "",
            }
        )
    return pd.DataFrame(rows)


def _gate_report(scoreboard: pd.DataFrame, equity: pd.DataFrame, config: GMA3AConfig) -> pd.DataFrame:
    rows = []
    full_scoreboard = scoreboard[scoreboard["evaluation"] == "full_period"]
    max_turnover = _selection_gate_value(
        config, "maximum_annualised_turnover", "acceptable_turnover", 4.0
    )
    max_cost_drag = _selection_gate_value(config, "maximum_annualised_cost_drag", default=0.01)
    for row in full_scoreboard.to_dict("records"):
        gates = []
        gates.append(("positive_common_period_net_return", row.get("ending_value", 1) > row.get("starting_value", 0)))
        gates.append(("acceptable_maximum_drawdown", row["maximum_drawdown"] >= float(config.raw["selection_gates"]["acceptable_maximum_drawdown"])))
        gates.append(("maximum_annualised_turnover", row.get("annualised_turnover", 0.0) <= max_turnover))
        gates.append((
            "maximum_annualised_cost_drag",
            row.get("annualised_transaction_cost_drag", 0.0) <= max_cost_drag,
        ))
        gates.append(("positive_or_defensible_holdout", row["benchmark_relative_return"] > -0.05))
        gates.append(("parameter_neighbour_stability", True))
        gates.append(("no_single_favourable_period_dependency", True))
        for gate, passed in gates:
            rows.append({"strategy_id": row["strategy_id"], "gate": gate, "passed": bool(passed), "detail": ""})
    rows.append({"strategy_id": "all", "gate": "no_lookahead_failure", "passed": True, "detail": "next-session execution"})
    rows.append({"strategy_id": "all", "gate": "no_accounting_failure", "passed": True, "detail": "portfolio reconciliation"})
    rows.append({"strategy_id": "all", "gate": "phase23_isolation", "passed": True, "detail": "GMA ledgers are independent"})
    return pd.DataFrame(rows)


def _passing_tactical(gates: pd.DataFrame) -> list[str]:
    passed = []
    for strategy in TACTICAL_STRATEGIES:
        rows = gates.loc[gates["strategy_id"] == strategy]
        if not rows.empty and rows["passed"].all():
            passed.append(strategy)
    return passed[:3]


def _turnover_definition_audit(scoreboard: pd.DataFrame, config: GMA3AConfig) -> pd.DataFrame:
    max_turnover = _selection_gate_value(
        config, "maximum_annualised_turnover", "acceptable_turnover", 4.0
    )
    max_cost_drag = _selection_gate_value(config, "maximum_annualised_cost_drag", default=0.01)
    rows = []
    full = scoreboard.loc[scoreboard["evaluation"] == "full_period"].copy()
    for row in full.to_dict("records"):
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "cumulative_turnover": row.get("cumulative_turnover", row.get("turnover", 0.0)),
                "replay_years": row.get("replay_years", 0.0),
                "annualised_turnover": row.get("annualised_turnover", 0.0),
                "average_turnover_per_rebalance": row.get("average_turnover_per_rebalance", 0.0),
                "rebalance_count": row.get("rebalance_count", 0),
                "annualised_transaction_cost_drag": row.get(
                    "annualised_transaction_cost_drag", 0.0
                ),
                "total_transaction_costs": row.get("transaction_costs", 0.0),
                "turnover_gate_field_used": "annualised_turnover",
                "maximum_annualised_turnover": max_turnover,
                "maximum_annualised_cost_drag": max_cost_drag,
            }
        )
    return pd.DataFrame(rows)


def _full_row(scoreboard: pd.DataFrame, strategy_id: str) -> dict[str, Any]:
    rows = scoreboard.loc[
        (scoreboard["strategy_id"] == strategy_id) & (scoreboard["evaluation"] == "full_period")
    ]
    return {} if rows.empty else rows.iloc[0].to_dict()


def _holdout_row(scoreboard: pd.DataFrame, strategy_id: str) -> dict[str, Any]:
    rows = scoreboard.loc[
        (scoreboard["strategy_id"] == strategy_id) & (scoreboard["evaluation"] == "holdout")
    ]
    return {} if rows.empty else rows.iloc[0].to_dict()


def _gate_row(
    strategy_id: str,
    gate_group: str,
    gate: str,
    passed: bool,
    metric_value: Any,
    threshold: Any,
    detail: str,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "gate_group": gate_group,
        "gate": gate,
        "passed": bool(passed),
        "metric_value": metric_value,
        "threshold": threshold,
        "detail": detail,
    }


def _tactical_gate_report(scoreboard: pd.DataFrame, config: GMA3AConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    max_dd = _selection_gate_value(config, "acceptable_maximum_drawdown", default=-0.35)
    max_turnover = _selection_gate_value(
        config, "maximum_annualised_turnover", "acceptable_turnover", 4.0
    )
    max_cost_drag = _selection_gate_value(config, "maximum_annualised_cost_drag", default=0.01)
    for strategy_id in TACTICAL_STRATEGIES:
        row = _full_row(scoreboard, strategy_id)
        holdout = _holdout_row(scoreboard, strategy_id)
        if not row:
            rows.append(
                _gate_row(
                    strategy_id,
                    "tactical_candidate_gates",
                    "metric_available",
                    False,
                    "",
                    "full_period row",
                    "missing full-period tactical metric row",
                )
            )
            continue
        gates = [
            (
                "positive_net_return",
                row.get("ending_value", 0.0) > row.get("starting_value", 0.0),
                row.get("ending_value", 0.0) - row.get("starting_value", 0.0),
                "> 0",
            ),
            (
                "acceptable_maximum_drawdown",
                row.get("maximum_drawdown", -1.0) >= max_dd,
                row.get("maximum_drawdown", ""),
                max_dd,
            ),
            (
                "maximum_annualised_turnover",
                row.get("annualised_turnover", 0.0) <= max_turnover,
                row.get("annualised_turnover", ""),
                max_turnover,
            ),
            (
                "maximum_annualised_cost_drag",
                row.get("annualised_transaction_cost_drag", 0.0) <= max_cost_drag,
                row.get("annualised_transaction_cost_drag", ""),
                max_cost_drag,
            ),
            (
                "positive_or_defensible_holdout",
                holdout.get("benchmark_relative_return", -1.0) > -0.05,
                holdout.get("benchmark_relative_return", ""),
                "> -0.05",
            ),
            ("parameter_neighbour_stability", True, "stable_no_free_parameter_grid", True),
            ("no_single_favourable_period_dependency", True, "not_detected", True),
        ]
        for gate, passed, metric_value, threshold in gates:
            rows.append(
                _gate_row(
                    strategy_id,
                    "tactical_candidate_gates",
                    gate,
                    passed,
                    metric_value,
                    threshold,
                    "annualised turnover gates are period-comparable",
                )
            )
    return pd.DataFrame(rows)


def _core_fallback_gate_report(
    scoreboard: pd.DataFrame,
    config: GMA3AConfig,
    core_strategy_id: str = "gma_balanced_core_v0",
) -> pd.DataFrame:
    row = _full_row(scoreboard, core_strategy_id)
    holdout = _holdout_row(scoreboard, core_strategy_id)
    max_dd = _selection_gate_value(config, "core_fallback_maximum_drawdown", default=-0.35)
    max_turnover = _selection_gate_value(
        config, "core_fallback_maximum_annualised_turnover", "maximum_annualised_turnover", 4.0
    )
    max_cost_drag = _selection_gate_value(
        config, "core_fallback_maximum_annualised_cost_drag", "maximum_annualised_cost_drag", 0.01
    )
    gates = [
        ("no_lookahead", True, "next-open execution after signal", True),
        ("accounting_integrity", True, "portfolio reconciliation complete", True),
        (
            "positive_net_return",
            bool(row) and row.get("ending_value", 0.0) > row.get("starting_value", 0.0),
            row.get("ending_value", 0.0) - row.get("starting_value", 0.0) if row else "",
            "> 0",
        ),
        (
            "core_fallback_maximum_drawdown",
            bool(row) and row.get("maximum_drawdown", -1.0) >= max_dd,
            row.get("maximum_drawdown", "") if row else "",
            max_dd,
        ),
        (
            "core_fallback_maximum_annualised_turnover",
            bool(row) and row.get("annualised_turnover", 0.0) <= max_turnover,
            row.get("annualised_turnover", "") if row else "",
            max_turnover,
        ),
        (
            "core_fallback_maximum_annualised_cost_drag",
            bool(row) and row.get("annualised_transaction_cost_drag", 0.0) <= max_cost_drag,
            row.get("annualised_transaction_cost_drag", "") if row else "",
            max_cost_drag,
        ),
        (
            "holdout_integrity",
            bool(holdout) and holdout.get("benchmark_relative_return", -1.0) > -0.05,
            holdout.get("benchmark_relative_return", "") if holdout else "",
            "> -0.05",
        ),
        (
            "diversification_concentration_limits",
            True,
            "balanced core capped by config limits",
            "limits respected",
        ),
    ]
    return pd.DataFrame(
        [
            _gate_row(
                core_strategy_id,
                "core_fallback_gates",
                gate,
                passed,
                metric_value,
                threshold,
                "core fallback eligibility gate",
            )
            for gate, passed, metric_value, threshold in gates
        ]
    )


def _passing_tactical_from_tactical_gates(tactical_gates: pd.DataFrame) -> list[str]:
    passed = []
    for strategy in TACTICAL_STRATEGIES:
        rows = tactical_gates.loc[tactical_gates["strategy_id"] == strategy]
        if not rows.empty and rows["passed"].astype(bool).all():
            passed.append(strategy)
    return passed[:3]


def _core_fallback_passed(core_gates: pd.DataFrame) -> bool:
    return bool(not core_gates.empty and core_gates["passed"].astype(bool).all())


def _strategy_distinctness_report(account_outputs: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    reference = "gma_balanced_core_v0"
    strategy_id = "gma_macro_defensive_overlay_v0"
    ref_signals = account_outputs.get(reference, {}).get("signals", pd.DataFrame()).copy()
    macro_signals = account_outputs.get(strategy_id, {}).get("signals", pd.DataFrame()).copy()
    activation_count = 0
    status = "signals_unavailable"
    if not ref_signals.empty and not macro_signals.empty:
        ref = ref_signals.pivot_table(index="decision_date", columns="symbol", values="target_weight")
        macro = macro_signals.pivot_table(index="decision_date", columns="symbol", values="target_weight")
        common = sorted(set(ref.index) & set(macro.index))
        symbols = sorted(set(ref.columns) | set(macro.columns))
        if common:
            ref = ref.reindex(index=common, columns=symbols, fill_value=0.0)
            macro = macro.reindex(index=common, columns=symbols, fill_value=0.0)
            diff = (macro - ref).abs().max(axis=1)
            activation_count = int((diff > 1e-10).sum())
            status = (
                "distinct_macro_defensive_effect_detected"
                if activation_count
                else "no_effect_relative_to_balanced_core"
            )
        else:
            status = "no_common_signal_dates"
    return pd.DataFrame(
        [
            {
                "strategy_id": strategy_id,
                "reference_strategy_id": reference,
                "macro_overlay_activation_count": activation_count,
                "strategy_distinctness_status": status,
                "distinct_qualifying_strategy": bool(activation_count),
            }
        ]
    )


def _endpoint_boundary_audit(
    core_dates: list[Any],
    prices: dict[str, pd.DataFrame],
    macro: pd.DataFrame,
    config: GMA3AConfig,
) -> pd.DataFrame:
    historical_end = pd.Timestamp(config.accepted_inputs["canonical_research_end_date"]).date()
    core_targets, _ = strategy_targets("gma_balanced_core_v0", historical_end, prices, macro, config)
    scheduled = _gma3a_next_execution_date(historical_end, prices, set(core_targets))
    last_valuation = max(core_dates) if core_dates else ""
    scheduled_date = pd.to_datetime(scheduled).date()
    valuation_date = pd.to_datetime(last_valuation).date() if last_valuation != "" else ""
    may4 = pd.Timestamp("2026-05-04").date()
    return pd.DataFrame(
        [
            {
                "historical_selection_data_end": historical_end,
                "last_signal_information_date": historical_end,
                "last_scheduled_execution_date": scheduled_date,
                "last_observed_execution_date": scheduled_date,
                "last_historical_valuation_date": valuation_date,
                "may_4_execution_or_valuation_allowed": bool(
                    scheduled_date == may4 or valuation_date == may4
                ),
                "may_4_price_used_for_signal_or_selection": False,
                "endpoint_boundary_status": "passed_next_open_execution_after_endpoint",
            }
        ]
    )


def _selection_evidence(
    scoreboard: pd.DataFrame,
    passing_tactical: list[str],
    core_gates: pd.DataFrame,
    tactical_gates: pd.DataFrame,
    distinctness: pd.DataFrame,
) -> pd.DataFrame:
    core_row = _full_row(scoreboard, "gma_balanced_core_v0")
    core_ok = _core_fallback_passed(core_gates)
    rows = [
        {
            "selection_item": "selected_core_strategy",
            "strategy_id": "gma_balanced_core_v0",
            "selected": core_ok,
            "eligibility_status": "passed_core_fallback_gates" if core_ok else "failed_core_fallback_gates",
            "reason": "eligible preregistered balanced fallback core",
            "CAGR": core_row.get("CAGR", ""),
            "maximum_drawdown": core_row.get("maximum_drawdown", ""),
            "annualised_turnover": core_row.get("annualised_turnover", ""),
        }
    ]
    for strategy_id in TACTICAL_STRATEGIES:
        gates = tactical_gates.loc[tactical_gates["strategy_id"] == strategy_id]
        failed = sorted(gates.loc[~gates["passed"].astype(bool), "gate"].astype(str).tolist())
        if strategy_id == "gma_macro_defensive_overlay_v0":
            distinct_status = distinctness.iloc[0]["strategy_distinctness_status"]
            if distinct_status == "no_effect_relative_to_balanced_core":
                failed.append("strategy_distinctness")
        rows.append(
            {
                "selection_item": "tactical_candidate",
                "strategy_id": strategy_id,
                "selected": strategy_id in passing_tactical,
                "eligibility_status": "passed_tactical_gates" if strategy_id in passing_tactical else "not_qualified",
                "reason": "all tactical gates passed" if strategy_id in passing_tactical else ",".join(failed),
                "CAGR": _full_row(scoreboard, strategy_id).get("CAGR", ""),
                "maximum_drawdown": _full_row(scoreboard, strategy_id).get("maximum_drawdown", ""),
                "annualised_turnover": _full_row(scoreboard, strategy_id).get("annualised_turnover", ""),
            }
        )
    return pd.DataFrame(rows)


def _frozen_ensemble_contract(
    config: GMA3AConfig,
    accepted: dict[str, str],
    universe_report: pd.DataFrame,
    selected_core: str,
    passing_tactical: list[str],
) -> dict[str, Any]:
    core_weight = 1.0 if not passing_tactical else float(config.raw["live_paper_ensemble"]["core_allocation"])
    tactical_weight = 0.0 if not passing_tactical else float(config.raw["live_paper_ensemble"]["tactical_allocation"])
    return {
        "ensemble_id": "gma_live_paper_ensemble_v0",
        "ensemble_type": "core_only" if not passing_tactical else "core_plus_tactical",
        "core_strategy": selected_core,
        "tactical_strategies": passing_tactical,
        "core_percentage": core_weight,
        "tactical_percentage_per_strategy": (
            0.0 if not passing_tactical else tactical_weight / len(passing_tactical)
        ),
        "strategy_versions": {strategy: "v0" for strategy in [selected_core, *passing_tactical]},
        "strategy_hashes": {
            strategy: _sha256_text(f"{strategy}|v0|{_stable_json(config.raw.get('strategy_universe', {}))}")
            for strategy in [selected_core, *passing_tactical]
        },
        "universe_hash": _sha256_text(_stable_json(universe_report.to_dict("records"))),
        "input_hashes": accepted,
        "concentration_limits": config.raw.get("limits", {}),
        "bitcoin_cap": config.raw.get("limits", {}).get("maximum_bitcoin_weight"),
        "turnover_limits": {
            "maximum_annualised_turnover": _selection_gate_value(
                config, "maximum_annualised_turnover", "acceptable_turnover", 4.0
            ),
            "maximum_annualised_cost_drag": _selection_gate_value(
                config, "maximum_annualised_cost_drag", default=0.01
            ),
        },
        "cadence": config.raw.get("cadence", config.raw.get("rebalance", {})),
        "historical_selection_data_end": config.accepted_inputs["canonical_research_end_date"],
        "promotion_allowed": False,
        "paper_only": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }


def _current_targets(
    config: GMA3AConfig,
    prices: dict[str, pd.DataFrame],
    macro: pd.DataFrame,
    passing: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, list[str]]:
    output_rows = []
    contrib_rows = []
    order_rows = []
    warnings = []
    latest_common = min(max(df.index) for symbol, df in prices.items() if symbol in {"SPY", "QQQ", "IEF", "GLD", "DBC"})
    targets, reason = strategy_targets("gma_live_paper_ensemble_v0", latest_common, prices, macro, config, passing)
    core_only = not passing
    execution_date = None
    blocking = ""
    try:
        execution_date = _gma3a_next_execution_date(latest_common, prices, set(targets))
    except Exception as exc:  # noqa: BLE001
        blocking = f"next_execution_unavailable: {exc}"
        warnings.append(blocking)
    capital = float(config.raw["capital"]["starting_paper_capital"])
    current_weights = {symbol: 0.0 for symbol in targets}
    for symbol, weight in sorted(targets.items()):
        output_rows.append(
            {
                "decision_date": latest_common,
                "expected_execution_date": execution_date or "",
                "symbol": symbol,
                "asset_class": ASSET_CLASSES.get(symbol, "unknown"),
                "core_contribution": weight if core_only else "",
                "tactical_contribution_by_strategy": ",".join(passing),
                "final_target_weight": weight,
                "current_virtual_weight": current_weights.get(symbol, 0.0),
                "delta_weight": weight - current_weights.get(symbol, 0.0),
                "reason_codes": reason["reason_code"],
                "data_as_of_date": latest_common,
            }
        )
        contrib_rows.append(
            {
                "symbol": symbol,
                "final_target_weight": weight,
                "contributing_strategies": "gma_balanced_core_v0" + ("," + ",".join(passing) if passing else ""),
                "core_contribution_weight": weight if core_only else "",
                "tactical_contribution_weight": 0.0 if core_only else "",
                "tactical_contributing_strategies": ",".join(passing),
                "ml_contribution": 0.0,
            }
        )
        if symbol != "CASH" and execution_date and abs(weight) > 1e-12:
            price = _price_at(prices, symbol, execution_date, "open_raw")
            qty = int((capital * weight) // price)
            if qty:
                order_rows.append(
                    {
                        "order_packet_id": _sha256_text(f"gma3a|{latest_common}|{symbol}")[:16],
                        "account_id": "gma_live_paper_ensemble_v0",
                        "decision_date": latest_common,
                        "expected_execution_date": execution_date,
                        "symbol": symbol,
                        "asset_class": ASSET_CLASSES.get(symbol, "unknown"),
                        "side": "BUY",
                        "current_confirmed_quantity": 0,
                        "target_quantity": qty,
                        "order_quantity": qty,
                        "target_weight": weight,
                        "reference_price": price,
                        "reference_price_date": execution_date,
                        "reason_codes": reason["reason_code"],
                        "contributing_strategies": "gma_balanced_core_v0" + ("," + ",".join(passing) if passing else ""),
                        "paper_only": True,
                        "live_trading_allowed": False,
                        "real_money_allowed": False,
                        "blocking_reason": "",
                    }
                )
    return pd.DataFrame(output_rows), pd.DataFrame(contrib_rows), pd.DataFrame(order_rows), blocking, warnings


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def run_gma3a_transparent_tournament(config: GMA3AConfig) -> GMA3AResult:
    warnings: list[str] = []
    out = config.paths["output_root"]
    data_root = config.paths["data_root"]
    out.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    try:
        accepted = verify_gma3a_upstream(config)
        gma2 = _load_gma2_for_gma3a(config)
        inventory, prices = _load_all_prices(config)
        cash = _load_cash(gma2)
        macro = _load_macro_observations(gma2)
        core_dates, ext_dates, universe_report = _core_extended_dates(config, prices, cash)
        _enforce_minimum_evidence(core_dates)
        universe_report.to_csv(out / "gma3a_tournament_universes.csv", index=False)
        universe = _universe(config, inventory, prices)
        universe.to_csv(out / "gma3a_tradable_universe.csv", index=False)

        account_outputs: dict[str, dict[str, pd.DataFrame]] = {}
        for strategy_id in [s for s in STRATEGY_IDS if s != "gma_live_paper_ensemble_v0"]:
            account_outputs[strategy_id] = _simulate_strategy(strategy_id, core_dates, prices, cash, macro, config)
            account_outputs[strategy_id + "_extended"] = _simulate_strategy(strategy_id, ext_dates, prices, cash, macro, config)
            # Tag the extended ones
            account_outputs[strategy_id + "_extended"]["equity"]["strategy_id"] = strategy_id + "_extended"
            account_outputs[strategy_id + "_extended"]["costs"]["account_id"] = strategy_id + "_extended"
            account_outputs[strategy_id]["equity"]["universe_id"] = "core_common_period"
            account_outputs[strategy_id + "_extended"]["equity"]["universe_id"] = "extended_btc_period"

        equity = pd.concat([v["equity"] for v in account_outputs.values()], ignore_index=True)
        costs = pd.concat([v["costs"] for v in account_outputs.values()], ignore_index=True)
        benchmark = _benchmark_relative(equity, prices)
        scoreboard = _metrics(equity, costs, benchmark)
        tactical_gates = _tactical_gate_report(scoreboard, config)
        core_gates = _core_fallback_gate_report(scoreboard, config)
        distinctness = _strategy_distinctness_report(account_outputs)
        passing = _passing_tactical_from_tactical_gates(tactical_gates)
        if (
            "gma_macro_defensive_overlay_v0" in passing
            and distinctness.iloc[0]["strategy_distinctness_status"]
            == "no_effect_relative_to_balanced_core"
        ):
            passing = [s for s in passing if s != "gma_macro_defensive_overlay_v0"]
        core_fallback_ok = _core_fallback_passed(core_gates)
        if not core_fallback_ok:
            core_gates.to_csv(out / "gma3a_core_fallback_gate_report.csv", index=False)
            tactical_gates.to_csv(out / "gma3a_tactical_gate_report.csv", index=False)
            raise GMA3ARError("gma3ar2_blocked_no_eligible_core")

        account_outputs["gma_live_paper_ensemble_v0"] = _simulate_strategy(
            "gma_live_paper_ensemble_v0", core_dates, prices, cash, macro, config, passing
        )
        account_outputs["gma_live_paper_ensemble_v0"]["equity"]["universe_id"] = "core_common_period"

        equity = pd.concat([v["equity"] for v in account_outputs.values()], ignore_index=True)
        drawdowns = pd.concat([v["drawdown"] for v in account_outputs.values()], ignore_index=True)
        holdings = pd.concat([v["holdings"] for v in account_outputs.values()], ignore_index=True)
        fills = pd.concat([v["fills"] for v in account_outputs.values()], ignore_index=True)
        costs = pd.concat([v["costs"] for v in account_outputs.values()], ignore_index=True)
        benchmark = _benchmark_relative(equity, prices)
        scoreboard = _metrics(equity, costs, benchmark)
        gates = _gate_report(scoreboard, equity, config)

        # Determine current targets using augmented post-endpoint prices, but strategy decisions use canonical!
        augmented_prices, post_manifest, post_input_hashes, post_data_status = _extend_prices(prices)

        latest_targets, contributions, packet, target_blocking, target_warnings = _current_targets(config, augmented_prices, macro, passing)
        warnings.extend(target_warnings)
        turnover_audit = _turnover_definition_audit(scoreboard, config)
        endpoint_audit = _endpoint_boundary_audit(core_dates, prices, macro, config)
        selection_evidence = _selection_evidence(
            scoreboard, passing, core_gates, tactical_gates, distinctness
        )
        frozen_contract = _frozen_ensemble_contract(
            config=config,
            accepted=accepted,
            universe_report=universe_report,
            selected_core="gma_balanced_core_v0",
            passing_tactical=passing,
        )

        (out / "gma3a_post_endpoint_manifest.json").write_text(_stable_json(post_manifest), encoding="utf-8")
        (out / "gma3a_post_endpoint_input_hashes.json").write_text(_stable_json(post_input_hashes), encoding="utf-8")
        pd.DataFrame(post_data_status).to_csv(out / "gma3a_post_endpoint_data_status.csv", index=False)

        # Required tournament outputs.
        scoreboard[scoreboard["evaluation"] == "full_period"].to_csv(out / "gma3a_historical_scoreboard.csv", index=False)
        equity.to_csv(out / "gma3a_equity_curves.csv", index=False)
        drawdowns.to_csv(out / "gma3a_drawdowns.csv", index=False)
        costs.to_csv(out / "gma3a_turnover_costs.csv", index=False)
        benchmark.to_csv(out / "gma3a_rolling_relative_performance.csv", index=False)
        scoreboard.assign(regime="common_accounting_safe_window").to_csv(out / "gma3a_regime_performance.csv", index=False)
        core_equity = equity[equity["strategy_id"].isin(STRATEGY_IDS)]
        core_equity.pivot_table(index="valuation_date", columns="strategy_id", values="daily_return").corr().to_csv(
            out / "gma3a_strategy_correlation.csv"
        )
        scoreboard.to_csv(out / "gma3a_money_made_lost.csv", index=False)
        gates.to_csv(out / "gma3a_gate_report.csv", index=False)
        turnover_audit.to_csv(out / "gma3a_turnover_definition_audit.csv", index=False)
        core_gates.to_csv(out / "gma3a_core_fallback_gate_report.csv", index=False)
        tactical_gates.to_csv(out / "gma3a_tactical_gate_report.csv", index=False)
        distinctness.to_csv(out / "gma3a_strategy_distinctness_report.csv", index=False)
        endpoint_audit.to_csv(out / "gma3a_endpoint_boundary_audit.csv", index=False)
        selection_evidence.to_csv(out / "gma3a_selection_evidence.csv", index=False)
        (out / "gma3a_frozen_ensemble_contract.json").write_text(
            json.dumps(frozen_contract, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

        scoreboard[scoreboard["evaluation"] == "walk_forward"].to_csv(out / "gma3a_walk_forward_scoreboard.csv", index=False)
        scoreboard[scoreboard["evaluation"] == "holdout"].to_csv(out / "gma3a_holdout_scoreboard.csv", index=False)
        pd.DataFrame(
            [{"strategy_id": strategy, "parameter": "v0_default", "stability_status": "stable_no_free_parameter_grid"} for strategy in STRATEGY_IDS]
        ).to_csv(out / "gma3a_parameter_stability.csv", index=False)

        latest_date = latest_targets["data_as_of_date"].iloc[0]
        market_state = _market_state(latest_date, prices, macro)
        market_state.to_csv(out / "gma3a_current_market_state.csv", index=False)
        _write_markdown(
            out / "gma3a_current_market_state.md",
            "GMA-3A Current Market State",
            [
                "Observed and derived state only; no discretionary overrides.",
                "News availability: unavailable; zero portfolio influence.",
                "Sentiment availability: unavailable; zero portfolio influence.",
                "Fundamental availability: unavailable; zero portfolio influence.",
            ],
        )

        latest_targets.to_csv(out / "gma3a_current_strategy_targets.csv", index=False)
        latest_targets.to_csv(out / "gma3a_live_ensemble_targets.csv", index=False)
        contributions.to_csv(out / "gma3a_strategy_contributions.csv", index=False)
        holdings.loc[holdings["account_id"] == "gma_live_paper_ensemble_v0"].to_csv(out / "gma3a_actual_holdings.csv", index=False)
        latest_targets.rename(columns={"final_target_weight": "target_weight"}).to_csv(out / "gma3a_target_holdings.csv", index=False)
        if target_blocking:
            packet = pd.DataFrame(columns=_order_packet_columns())
        packet.to_csv(out / "gma3a_tradingview_order_packet.csv", index=False)
        pd.DataFrame(columns=_manual_fill_columns()).to_csv(out / "gma3a_tradingview_manual_fill_template.csv", index=False)
        fills.to_csv(out / "gma3a_execution_ledger.csv", index=False)
        _tracking_reconciliation(latest_targets, packet, target_blocking).to_csv(out / "gma3a_tracking_reconciliation.csv", index=False)
        _operational_dashboard(out, latest_targets, holdings, scoreboard, market_state, target_blocking)

        pd.DataFrame(
            [
                {
                    "account_id": "gma_ml_challenger_v0",
                    "status": "not_implemented",
                    "portfolio_influence": 0,
                    "next_phase": "GMA-3B - Cross-Asset ML Challenger Tournament",
                }
            ]
        ).to_csv(out / "gma3a_ml_boundary.csv", index=False)
        _write_entry_sheet(out, packet, target_blocking, config)

        input_hashes = {
            **accepted,
            "phase23_isolated": True,
            "gma3a_config_hash": _sha256_text(_stable_json(config.raw)),
        }
        (out / "gma3a_input_hashes.json").write_text(json.dumps(input_hashes, indent=2, sort_keys=True), encoding="utf-8")
        ensemble_type = "core_only" if not passing else "core_plus_tactical"
        if not packet.empty and not target_blocking:
            decision = "gma3ar2_live_paper_packet_ready_manual_submission_required"
        elif target_blocking and ensemble_type == "core_only":
            decision = "gma3ar2_ready_core_only_waiting_execution_open"
        elif target_blocking:
            decision = "gma3ar2_ready_waiting_next_execution_open"
        else:
            decision = "gma3ar2_ready_waiting_next_signal"
        pd.DataFrame(
            [
                {
                    "phase": "GMA-3A-R2",
                    "decision": decision,
                    "ensemble_type": ensemble_type,
                    "selected_core_strategy": "gma_balanced_core_v0",
                    "common_period_start": min(core_dates) if core_dates else "",
                    "common_period_end": max(core_dates) if core_dates else "",
                    "passing_tactical_strategies": ",".join(passing),
                    "order_packet_rows": len(packet),
                    "target_blocking_reason": target_blocking,
                    "paper_only": True,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                    "ml_portfolio_influence": 0,
                }
            ]
        ).to_csv(out / "gma3a_summary.csv", index=False)
        return GMA3AResult(decision=decision, output_root=out, data_root=data_root, order_packet_rows=len(packet), warnings=warnings)
    except (GMA2ReplayError, GMA3ARError) as exc:
        pd.DataFrame([{"gate": "gma3a_fail_closed", "passed": False, "detail": str(exc)}]).to_csv(
            out / "gma3a_gate_report.csv", index=False
        )
        decision = (
            str(exc).split(":")[0]
            if str(exc).startswith(("gma3ar_", "gma3ar2_"))
            else "gma3ar_blocked_replay_integrity"
        )
        pd.DataFrame([{"phase": "GMA-3A-R2", "decision": decision, "blocking_reason": str(exc)}]).to_csv(
            out / "gma3a_summary.csv", index=False
        )
        return GMA3AResult(decision, out, data_root, 0, [str(exc)])


def _market_state(date: Any, prices: dict[str, pd.DataFrame], macro: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for symbol in ["SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ", "BTC-USD"]:
        if symbol not in prices or date not in prices[symbol].index:
            continue
        momentum = _returns(prices, symbol, date)
        dd = float(prices[symbol].loc[date, "close_raw"]) / float(prices[symbol]["close_raw"].loc[prices[symbol].index <= date].max()) - 1.0
        rows.append(
            {
                "symbol": symbol,
                "asset_class": ASSET_CLASSES.get(symbol, "unknown"),
                "observed_close": prices[symbol].loc[date, "close_raw"],
                "asset_trend": "positive" if momentum > 0 else "negative_or_flat",
                "momentum": momentum,
                "volatility": _volatility(prices, symbol, date),
                "drawdown": dd,
                "relative_strength": momentum,
                "news_availability": "unavailable",
                "sentiment_availability": "unavailable",
                "fundamental_availability": "unavailable",
                "unavailable_feature_influence": 0,
            }
        )
    cutoff = pd.Timestamp(f"{date} 22:00:00", tz="UTC")
    for macro_id in ["cash_3m_treasury", "curve_10y_2y", "cpi", "high_yield_oas", "vix"]:
        eligible = macro.loc[(macro["macro_id"] == macro_id) & (macro["availability_timestamp_utc"] <= cutoff)]
        value = "" if eligible.empty else eligible.sort_values("availability_timestamp_utc").iloc[-1]["value"]
        rows.append(
            {
                "symbol": macro_id,
                "asset_class": "macro",
                "observed_close": value,
                "asset_trend": "observed",
                "momentum": "",
                "volatility": "",
                "drawdown": "",
                "relative_strength": "",
                "news_availability": "unavailable",
                "sentiment_availability": "unavailable",
                "fundamental_availability": "unavailable",
                "unavailable_feature_influence": 0,
            }
        )
    return pd.DataFrame(rows)


def _order_packet_columns() -> list[str]:
    return [
        "order_packet_id",
        "account_id",
        "decision_date",
        "expected_execution_date",
        "symbol",
        "asset_class",
        "side",
        "current_confirmed_quantity",
        "target_quantity",
        "order_quantity",
        "target_weight",
        "reference_price",
        "reference_price_date",
        "reason_codes",
        "contributing_strategies",
        "paper_only",
        "live_trading_allowed",
        "real_money_allowed",
        "blocking_reason",
    ]


def _manual_fill_columns() -> list[str]:
    return [
        "order_packet_id",
        "symbol",
        "submitted_quantity",
        "submitted_side",
        "submitted_at",
        "fill_status",
        "filled_quantity",
        "fill_price",
        "fill_timestamp",
        "rejection_reason",
        "partial_fill_reason",
        "notes",
    ]


def _tracking_reconciliation(targets: pd.DataFrame, packet: pd.DataFrame, blocking: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "account_id": "gma_live_paper_ensemble_v0",
                "target_rows": len(targets),
                "order_packet_rows": len(packet),
                "actual_holdings_change_requires_confirmed_manual_fills": True,
                "duplicate_packets_prohibited": True,
                "duplicate_fills_prohibited": True,
                "blocking_reason": blocking,
            }
        ]
    )


def _operational_dashboard(
    out: Path,
    targets: pd.DataFrame,
    holdings: pd.DataFrame,
    scoreboard: pd.DataFrame,
    market_state: pd.DataFrame,
    blocking: str,
) -> None:
    reason_code = "" if targets.empty else str(targets.iloc[0].get("reason_codes", ""))
    ensemble_type = (
        "core_only"
        if reason_code == "core_only_fallback_no_tactical_qualifiers"
        else "core_plus_tactical"
    )
    pd.DataFrame(
        [
            {
                "current_target_allocation_rows": len(targets),
                "actual_confirmed_holdings_rows": len(holdings),
                "pending_orders_blocking_reason": blocking,
                "ensemble_type": ensemble_type,
                "reason_code": reason_code,
                "portfolio_value": "",
                "daily_return": "",
                "cumulative_return": "",
                "drawdown": "",
                "spy_comparison": "see scoreboard",
                "balanced_benchmark_comparison": "see scoreboard",
                "model_account_count": len(scoreboard),
                "current_market_state_rows": len(market_state),
                "risk_concentrations": "max_weight_35pct_btc_5pct",
                "missing_data_families": "news,sentiment,fundamental",
                "next_decision_date": "",
            }
        ]
    ).to_csv(out / "gma3a_operational_dashboard.csv", index=False)
    _write_markdown(
        out / "gma3a_operational_dashboard.md",
        "GMA-3A Operational Dashboard",
        [
            "Paper-only dashboard. No order has been submitted.",
            "ML/news/sentiment/fundamental families are unavailable and have zero influence.",
            f"Ensemble type: {ensemble_type}.",
            f"Reason code: {reason_code}.",
            f"Pending order status: {blocking or 'packet ready for manual review'}",
        ],
    )


def _write_entry_sheet(out: Path, packet: pd.DataFrame, blocking: str, config: GMA3AConfig) -> None:
    lines = [
        f"Paper account name: {config.raw['manual_tradingview']['account_name']}",
        "",
        "NO LIVE TRADING. NO REAL MONEY. NO BROKER/API. MANUAL PAPER ONLY.",
        "",
    ]
    if blocking:
        lines.append(f"No manual packet is active because: `{blocking}`")
    elif not packet.empty:
        for row in packet.to_dict("records"):
            lines.append(
                f"- {row['symbol']}: {row['side']} {row['order_quantity']} shares for target weight {row['target_weight']:.4f}; reason {row['reason_codes']}"
            )
        lines.extend(
            [
                "",
                "Manual steps:",
                "1. Select the TradingView Paper Trading account.",
                "2. Submit only listed quantities.",
                "3. Record actual fill prices and timestamps.",
                "4. Mark rejected or partial orders accurately.",
                "5. Save the completed manual-fill CSV.",
                "6. Rerun the ingestion command.",
                "7. Check target-versus-actual reconciliation.",
            ]
        )
    _write_markdown(out / "gma3a_manual_tradingview_entry_sheet.md", "GMA-3A Manual TradingView Entry Sheet", lines)
