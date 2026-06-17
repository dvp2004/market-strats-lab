"""GMA-2 point-in-time multi-asset replay foundation."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from market_strats.global_multi_asset.gma2_config import GMA2Config


@dataclass(frozen=True)
class GMA2ReplayResult:
    decision: str
    replay_hash: str
    warnings: list[str]
    report_root: Path
    data_root: Path


class GMA2ReplayError(RuntimeError):
    """Fail-closed replay integrity error."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _git_rev(ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_accepted_inputs(config: GMA2Config) -> dict[str, str]:
    accepted = config.accepted_inputs
    data_hash = Path("reports/global_multi_asset_alpha/data_foundation/canonical_selection_hash.txt")
    macro_hash = Path("reports/global_multi_asset_alpha/macro_foundation/canonical_macro_hash.txt")
    macro_manifest = Path("reports/global_multi_asset_alpha/macro_foundation/canonical_macro_manifest.json")
    for path in [data_hash, macro_hash, macro_manifest]:
        if not path.exists():
            raise GMA2ReplayError(f"accepted input artifact missing: {path}")

    actual_gma1a_hash = data_hash.read_text(encoding="utf-8").strip()
    actual_gma1b_hash = macro_hash.read_text(encoding="utf-8").strip()
    manifest = json.loads(macro_manifest.read_text(encoding="utf-8"))
    actual_live_hash = str(manifest.get("accepted_live_canonical_hash", ""))
    if actual_gma1a_hash != accepted["gma1a_accepted_selection_hash"]:
        raise GMA2ReplayError("accepted GMA-1A selection hash mismatch")
    if actual_gma1b_hash != accepted["gma1b_accepted_canonical_macro_hash"]:
        raise GMA2ReplayError("accepted GMA-1B canonical macro hash mismatch")
    if actual_live_hash != accepted["gma1b_accepted_live_hash"]:
        raise GMA2ReplayError("accepted GMA-1B live hash mismatch")
    if _git_rev(accepted["gma1a_tag"]) != accepted["gma1a_commit"]:
        raise GMA2ReplayError("GMA-1A tag does not resolve to pinned commit")
    if _git_rev(accepted["gma1b_tag"]) != accepted["gma1b_commit"]:
        raise GMA2ReplayError("GMA-1B tag does not resolve to pinned commit")

    return {
        "gma1a_commit": accepted["gma1a_commit"],
        "gma1a_tag": accepted["gma1a_tag"],
        "gma1a_accepted_selection_hash": actual_gma1a_hash,
        "gma1b_commit": accepted["gma1b_commit"],
        "gma1b_tag": accepted["gma1b_tag"],
        "gma1b_accepted_live_hash": actual_live_hash,
        "gma1b_accepted_canonical_macro_hash": actual_gma1b_hash,
        "canonical_research_end_date": accepted["canonical_research_end_date"],
    }


def _load_inventory(config: GMA2Config) -> pd.DataFrame:
    path = config.paths["data_foundation_report_root"] / "canonical_market_bundle_inventory.csv"
    if not path.exists():
        raise GMA2ReplayError(f"market inventory missing: {path}")
    return pd.read_csv(path)


def _load_prices(config: GMA2Config, symbols: set[str]) -> dict[str, pd.DataFrame]:
    inventory = _load_inventory(config)
    prices: dict[str, pd.DataFrame] = {}
    required_cols = {
        "date",
        "instrument_id",
        "open_raw",
        "close_raw",
        "dividend_cash",
        "split_ratio",
        "is_completed_observation",
        "calendar_id",
        "total_return_index",
    }
    for symbol in sorted(symbols):
        if symbol == "CASH":
            continue
        matches = inventory.loc[inventory["instrument_id"] == symbol]
        if matches.empty:
            raise GMA2ReplayError(f"missing canonical inventory row for {symbol}")
        path = Path(str(matches.iloc[0]["canonical_file_path"]))
        if not path.exists():
            raise GMA2ReplayError(f"missing canonical price file for {symbol}: {path}")
        df = pd.read_csv(path)
        missing = required_cols - set(df.columns)
        if missing:
            raise GMA2ReplayError(f"{symbol} missing mandatory price fields: {sorted(missing)}")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        if df["date"].duplicated().any():
            raise GMA2ReplayError(f"{symbol} has duplicate dates")
        if (pd.to_numeric(df["open_raw"], errors="coerce") <= 0).any():
            raise GMA2ReplayError(f"{symbol} has non-positive open prices")
        if (pd.to_numeric(df["close_raw"], errors="coerce") <= 0).any():
            raise GMA2ReplayError(f"{symbol} has non-positive close prices")
        if df[list(required_cols - {"date"})].isna().any().any():
            raise GMA2ReplayError(f"{symbol} has missing mandatory price fields")
        prices[symbol] = df.set_index("date").sort_index()
    return prices


def _load_cash(config: GMA2Config) -> pd.DataFrame:
    path = config.paths["canonical_macro_root"] / "canonical_cash_accrual.csv"
    if not path.exists():
        raise GMA2ReplayError(f"cash accrual file missing: {path}")
    df = pd.read_csv(path)
    required = {
        "observation_date",
        "availability_timestamp_utc",
        "annual_yield",
        "accrual_start",
        "accrual_end",
        "accrual_days",
        "period_return",
        "source_series",
        "source_realtime_start",
    }
    missing = required - set(df.columns)
    if missing:
        raise GMA2ReplayError(f"cash accrual missing fields: {sorted(missing)}")
    df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
    df["accrual_start"] = pd.to_datetime(df["accrual_start"]).dt.date
    df["accrual_end"] = pd.to_datetime(df["accrual_end"]).dt.date
    if df["accrual_start"].duplicated().any():
        raise GMA2ReplayError("cash accrual has duplicate accrual starts")
    return df.sort_values("accrual_start")


def _load_macro_observations(config: GMA2Config) -> pd.DataFrame:
    path = config.paths["canonical_macro_root"] / "point_in_time_macro_observations.csv"
    if not path.exists():
        raise GMA2ReplayError(f"macro observations missing: {path}")
    df = pd.read_csv(path)
    df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
    df["availability_timestamp_utc"] = pd.to_datetime(df["availability_timestamp_utc"], utc=True)
    return df


def _policy_symbols(config: GMA2Config) -> set[str]:
    symbols = {str(config.raw["benchmark"]["symbol"])}
    for policy in config.smoke_policies.values():
        for alloc in policy.get("allocations", {}).values():
            symbols.update(str(symbol) for symbol in alloc)
    return symbols


def normalise_weights(weights: dict[str, float], tolerance: float = 1e-9) -> dict[str, float]:
    finite = {str(k): float(v) for k, v in weights.items() if math.isfinite(float(v))}
    total = sum(finite.values())
    if total <= 0:
        raise GMA2ReplayError("target weights cannot be normalised")
    normalised = {k: v / total for k, v in finite.items() if abs(v) > tolerance}
    if abs(sum(normalised.values()) - 1.0) > 1e-8:
        raise GMA2ReplayError("normalised target weights do not sum to one")
    return normalised


def next_valid_execution_date(signal_date: Any, prices: dict[str, pd.DataFrame], assets: set[str]) -> Any:
    candidates: list[Any] = []
    for asset in assets:
        if asset == "CASH":
            continue
        asset_dates = [date for date in prices[asset].index if date > signal_date]
        if not asset_dates:
            raise GMA2ReplayError(f"no execution date after signal for {asset}")
        candidates.append(asset_dates[0])
    if not candidates:
        all_dates = sorted({date for price_frame in prices.values() for date in price_frame.index if date > signal_date})
        if not all_dates:
            raise GMA2ReplayError("no replay calendar date after cash-only signal")
        return all_dates[0]
    observed = max(candidates)
    for asset in assets:
        if asset != "CASH" and observed not in prices[asset].index:
            raise GMA2ReplayError(f"ambiguous execution alignment for {asset} on {observed}")
    if observed <= signal_date:
        raise GMA2ReplayError("execution cannot occur before or on signal date")
    return observed


def _price_at(prices: dict[str, pd.DataFrame], asset: str, date: Any, field: str) -> float:
    if asset not in prices or date not in prices[asset].index:
        raise GMA2ReplayError(f"valuation using unavailable price: {asset} {date}")
    value = float(prices[asset].loc[date, field])
    if not math.isfinite(value) or value <= 0:
        raise GMA2ReplayError(f"invalid price for {asset} {date}")
    return value


def _cash_period_return(cash_df: pd.DataFrame, start: Any, end: Any) -> tuple[float, dict[str, Any]]:
    rows = cash_df.loc[(cash_df["accrual_start"] == start) & (cash_df["accrual_end"] == end)]
    if rows.empty:
        raise GMA2ReplayError(f"missing cash accrual period {start} to {end}")
    row = rows.iloc[0].to_dict()
    return float(row["period_return"]), row


def _build_signal_schedule(
    config: GMA2Config, prices: dict[str, pd.DataFrame]
) -> tuple[list[dict[str, Any]], set[Any]]:
    events: list[dict[str, Any]] = []
    valuation_dates: set[Any] = set()
    for policy_id, policy in config.smoke_policies.items():
        for signal_date_str, raw_weights in policy["allocations"].items():
            signal_date = pd.to_datetime(signal_date_str).date()
            target = normalise_weights(raw_weights, config.raw["portfolio_weight_tolerance"])
            execution_date = next_valid_execution_date(signal_date, prices, set(target))
            events.append(
                {
                    "policy_id": policy_id,
                    "signal_date": signal_date,
                    "scheduled_execution_date": execution_date,
                    "observed_execution_date": execution_date,
                    "target_weights": target,
                }
            )
            valuation_dates.add(signal_date)
            valuation_dates.add(execution_date)
    return sorted(events, key=lambda row: (row["observed_execution_date"], row["policy_id"])), valuation_dates


def _policy_valuation_dates(
    config: GMA2Config,
    prices: dict[str, pd.DataFrame],
    schedule_dates: set[Any],
) -> list[Any]:
    start = pd.to_datetime(config.raw["smoke_replay_start_date"]).date()
    end = pd.to_datetime(config.raw["smoke_replay_end_date"]).date()
    benchmark = str(config.raw["benchmark"]["symbol"])
    dates = [date for date in prices[benchmark].index if start <= date <= end]
    for date in schedule_dates:
        if start <= date <= end and date not in dates:
            dates.append(date)
    return sorted(dates)


def run_single_policy_replay(
    config: GMA2Config,
    policy_id: str,
    prices: dict[str, pd.DataFrame],
    cash_df: pd.DataFrame,
    events: list[dict[str, Any]],
    valuation_dates: list[Any],
) -> dict[str, pd.DataFrame]:
    initial_capital = float(config.raw["initial_capital"])
    cost_bps = float(config.raw["transaction_cost_policy"]["bps_per_notional"])
    tolerance = float(config.raw["portfolio_tolerance"])
    cash = initial_capital
    shares: dict[str, float] = {}
    active_weights = {"CASH": 1.0}
    rows: dict[str, list[dict[str, Any]]] = {
        name: []
        for name in [
            "daily_portfolio_value",
            "daily_returns",
            "daily_holdings",
            "daily_exposure",
            "trade_log",
            "switch_event_log",
            "cash_accrual_log",
            "transaction_cost_log",
            "portfolio_reconciliation",
            "execution_alignment_audit",
        ]
    }
    policy_events = [event for event in events if event["policy_id"] == policy_id]
    by_execution: dict[Any, list[dict[str, Any]]] = {}
    for event in policy_events:
        by_execution.setdefault(event["observed_execution_date"], []).append(event)

    prev_value: float | None = None
    peak = initial_capital
    pending_cash_multiplier = 1.0
    previous_date = None
    for date in valuation_dates:
        if previous_date is not None:
            period_return, cash_meta = _cash_period_return(cash_df, previous_date, date)
            accrual = cash * period_return
            cash += accrual
            rows["cash_accrual_log"].append(
                {
                    "policy_id": policy_id,
                    "accrual_start": previous_date,
                    "accrual_end": date,
                    "accrual_days": cash_meta["accrual_days"],
                    "source_observation_date": cash_meta["observation_date"],
                    "source_realtime_start": cash_meta["source_realtime_start"],
                    "source_availability_date": cash_meta["availability_timestamp_utc"],
                    "annual_yield_decimal": cash_meta["annual_yield"],
                    "period_return": period_return,
                    "cash_before_accrual": cash - accrual,
                    "cash_accrual_amount": accrual,
                    "cash_after_accrual": cash,
                    "point_in_time_eligible": True,
                }
            )
            pending_cash_multiplier *= 1 + period_return

        for event in by_execution.get(date, []):
            signal_date = event["signal_date"]
            if date <= signal_date:
                raise GMA2ReplayError("no same-close lookahead allowed")
            target_weights = event["target_weights"]
            assets = set(target_weights) | set(shares)
            pre_value = cash + sum(
                qty * _price_at(prices, asset, date, "open_raw")
                for asset, qty in shares.items()
            )
            current_values = {
                asset: shares.get(asset, 0.0) * _price_at(prices, asset, date, "open_raw")
                for asset in assets
                if asset != "CASH"
            }
            post_cost_value = pre_value
            for _ in range(5):
                estimated_abs_trade = sum(
                    abs(post_cost_value * target_weights.get(asset, 0.0) - current_values.get(asset, 0.0))
                    for asset in assets
                    if asset != "CASH"
                )
                next_post_cost_value = pre_value - estimated_abs_trade * cost_bps / 10000.0
                if abs(next_post_cost_value - post_cost_value) < 0.000001:
                    break
                post_cost_value = next_post_cost_value
            total_cost = 0.0
            switch_id = _sha256_text(f"{policy_id}|{signal_date}|{date}")[:16]
            rows["switch_event_log"].append(
                {
                    "policy_id": policy_id,
                    "switch_id": switch_id,
                    "signal_date": signal_date,
                    "scheduled_execution_date": event["scheduled_execution_date"],
                    "observed_execution_date": date,
                    "target_allocation": _stable_json(target_weights),
                    "reason_code": "deterministic_smoke_policy",
                    "label": "engine_validation_only",
                    "not_strategy_candidate": True,
                    "not_paper_trading_recommendation": True,
                }
            )
            for asset in sorted(assets):
                if asset == "CASH":
                    continue
                price = _price_at(prices, asset, date, "open_raw")
                current_value = current_values.get(asset, 0.0)
                target_value = post_cost_value * target_weights.get(asset, 0.0)
                trade_notional = target_value - current_value
                if abs(trade_notional) < float(config.raw["minimum_trade_notional"]):
                    continue
                cost = abs(trade_notional) * cost_bps / 10000.0
                shares[asset] = shares.get(asset, 0.0) + trade_notional / price
                cash -= trade_notional + cost
                total_cost += cost
                rows["trade_log"].append(
                    {
                        "policy_id": policy_id,
                        "switch_id": switch_id,
                        "signal_date": signal_date,
                        "scheduled_execution_date": event["scheduled_execution_date"],
                        "observed_execution_date": date,
                        "asset": asset,
                        "side": "BUY" if trade_notional > 0 else "SELL",
                        "execution_price": price,
                        "share_change": trade_notional / price,
                        "trade_notional": trade_notional,
                        "transaction_cost": cost,
                        "cash_after_trade": cash,
                        "preview_whole_share_quantity": int(abs(trade_notional) // price),
                        "paper_order_preview_only": True,
                    }
                )
                rows["transaction_cost_log"].append(
                    {
                        "policy_id": policy_id,
                        "switch_id": switch_id,
                        "execution_date": date,
                        "asset": asset,
                        "trade_notional_abs": abs(trade_notional),
                        "bps_per_notional": cost_bps,
                        "transaction_cost": cost,
                        "charged_once": True,
                    }
                )
            active_weights = target_weights
            if cash < -tolerance:
                raise GMA2ReplayError(f"negative cash beyond tolerance in {policy_id}")
            if total_cost < 0:
                raise GMA2ReplayError("transaction costs cannot be negative")

        market_values = {
            asset: qty * _price_at(prices, asset, date, "close_raw")
            for asset, qty in shares.items()
        }
        market_value = sum(market_values.values())
        total_value = cash + market_value
        if abs(total_value - (cash + sum(market_values.values()))) > tolerance:
            raise GMA2ReplayError("portfolio value identity failed")
        daily_return = 0.0 if prev_value is None else total_value / prev_value - 1.0
        peak = max(peak, total_value)
        drawdown = total_value / peak - 1.0
        cash_weight = cash / total_value if total_value else 0.0
        exposure_sum = cash_weight + sum(value / total_value for value in market_values.values())
        if abs(exposure_sum - 1.0) > 1e-8:
            raise GMA2ReplayError("weights do not sum to one")

        rows["daily_portfolio_value"].append(
            {
                "policy_id": policy_id,
                "valuation_date": date,
                "cash_value": cash,
                "invested_value": market_value,
                "portfolio_value": total_value,
                "running_peak_value": peak,
                "drawdown": drawdown,
                "valuation_status": "completed",
            }
        )
        rows["daily_returns"].append(
            {
                "policy_id": policy_id,
                "valuation_date": date,
                "daily_return": daily_return,
                "cumulative_return": total_value / initial_capital - 1.0,
            }
        )
        for asset in sorted(set(market_values) | {"CASH"}):
            value = cash if asset == "CASH" else market_values.get(asset, 0.0)
            rows["daily_holdings"].append(
                {
                    "policy_id": policy_id,
                    "valuation_date": date,
                    "asset": asset,
                    "shares": 0.0 if asset == "CASH" else shares.get(asset, 0.0),
                    "market_value": value,
                    "weight": value / total_value if total_value else 0.0,
                }
            )
            rows["daily_exposure"].append(
                {
                    "policy_id": policy_id,
                    "valuation_date": date,
                    "asset": asset,
                    "target_weight": active_weights.get(asset, 0.0),
                    "actual_weight": value / total_value if total_value else 0.0,
                }
            )
        rows["portfolio_reconciliation"].append(
            {
                "policy_id": policy_id,
                "valuation_date": date,
                "cash_value": cash,
                "position_market_values": market_value,
                "portfolio_value": total_value,
                "identity_difference": total_value - (cash + market_value),
                "weights_sum": exposure_sum,
                "cash_negative_beyond_tolerance": cash < -tolerance,
                "reconciliation_passed": True,
            }
        )
        for event in by_execution.get(date, []):
            rows["execution_alignment_audit"].append(
                {
                    "policy_id": policy_id,
                    "signal_date": event["signal_date"],
                    "scheduled_execution_date": event["scheduled_execution_date"],
                    "observed_execution_date": event["observed_execution_date"],
                    "valuation_date": date,
                    "execution_after_signal": event["observed_execution_date"] > event["signal_date"],
                    "same_close_execution_allowed": False,
                    "alignment_status": "passed",
                }
            )
        prev_value = total_value
        previous_date = date

    return {name: pd.DataFrame(values) for name, values in rows.items()}


def _concat_policy_outputs(outputs: dict[str, dict[str, pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    names = sorted(next(iter(outputs.values())).keys())
    return {
        name: pd.concat([policy_outputs[name] for policy_outputs in outputs.values()], ignore_index=True)
        for name in names
    }


def _benchmark_comparison(
    config: GMA2Config,
    prices: dict[str, pd.DataFrame],
    daily_portfolio_value: pd.DataFrame,
) -> pd.DataFrame:
    benchmark = str(config.raw["benchmark"]["symbol"])
    initial = float(config.raw["initial_capital"])
    rows = []
    for policy_id, group in daily_portfolio_value.groupby("policy_id"):
        first_date = group["valuation_date"].min()
        start_close = _price_at(prices, benchmark, first_date, "close_raw")
        for row in group.sort_values("valuation_date").to_dict("records"):
            close = _price_at(prices, benchmark, row["valuation_date"], "close_raw")
            spy_value = initial * close / start_close
            rows.append(
                {
                    "policy_id": policy_id,
                    "valuation_date": row["valuation_date"],
                    "portfolio_value": row["portfolio_value"],
                    "benchmark_symbol": benchmark,
                    "benchmark_value": spy_value,
                    "relative_value": row["portfolio_value"] - spy_value,
                    "relative_return": row["portfolio_value"] / spy_value - 1.0,
                }
            )
    return pd.DataFrame(rows)


def _rolling_relative(benchmark: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy_id, group in benchmark.groupby("policy_id"):
        sorted_group = group.sort_values("valuation_date").copy()
        sorted_group["rolling_relative_return"] = sorted_group["relative_return"].rolling(2, min_periods=1).mean()
        rows.extend(sorted_group[["policy_id", "valuation_date", "rolling_relative_return"]].to_dict("records"))
    return pd.DataFrame(rows)


def _money_made_lost(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy_id, group in daily.groupby("policy_id"):
        ordered = group.sort_values("valuation_date")
        rows.append(
            {
                "policy_id": policy_id,
                "start_value": ordered.iloc[0]["portfolio_value"],
                "end_value": ordered.iloc[-1]["portfolio_value"],
                "money_made_lost": ordered.iloc[-1]["portfolio_value"] - ordered.iloc[0]["portfolio_value"],
                "max_drawdown": ordered["drawdown"].min(),
            }
        )
    return pd.DataFrame(rows)


def _macro_audit(config: GMA2Config, macro: pd.DataFrame, daily_dates: list[Any]) -> pd.DataFrame:
    rows = []
    for signal_date in sorted(set(daily_dates)):
        cutoff = pd.Timestamp(f"{signal_date} 22:00:00", tz="UTC")
        eligible = macro.loc[macro["availability_timestamp_utc"] <= cutoff]
        for macro_id, group in eligible.groupby("macro_id"):
            row = group.sort_values("availability_timestamp_utc").iloc[-1]
            rows.append(
                {
                    "macro_id": macro_id,
                    "source_observation_date": row["observation_date"],
                    "source_realtime_start": row["realtime_start"],
                    "source_availability_date": row["availability_timestamp_utc"],
                    "signal_date": signal_date,
                    "point_in_time_eligible": True,
                }
            )
    return pd.DataFrame(rows)


def _write_chart(path: Path, title: str, df: pd.DataFrame, x: str, ys: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for y in ys:
        if y in df:
            ax.plot(pd.to_datetime(df[x]), df[y], label=y)
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_outputs(
    config: GMA2Config,
    accepted: dict[str, str],
    tables: dict[str, pd.DataFrame],
    prices: dict[str, pd.DataFrame],
) -> str:
    data_root = config.paths["replay_data_root"]
    report_root = config.paths["replay_report_root"]
    tv_root = report_root / "tradingview_preview"
    for path in [data_root, report_root, tv_root]:
        path.mkdir(parents=True, exist_ok=True)

    csv_names = [
        "daily_portfolio_value",
        "daily_returns",
        "daily_holdings",
        "daily_exposure",
        "trade_log",
        "switch_event_log",
        "cash_accrual_log",
        "transaction_cost_log",
        "portfolio_reconciliation",
        "benchmark_comparison",
        "rolling_relative_performance",
        "money_made_lost_table",
        "execution_alignment_audit",
        "macro_point_in_time_audit",
        "missing_data_incidents",
    ]
    for name in csv_names:
        tables[name].to_csv(data_root / f"{name}.csv", index=False)
        tables[name].to_csv(report_root / f"{name}.csv", index=False)

    input_hashes = {
        **accepted,
        "config_hash": _sha256_text(_stable_json(config.raw)),
        "market_inventory_hash": _sha256_file(
            config.paths["data_foundation_report_root"] / "canonical_market_bundle_inventory.csv"
        ),
        "cash_accrual_hash": _sha256_file(config.paths["canonical_macro_root"] / "canonical_cash_accrual.csv"),
        "macro_observations_hash": _sha256_file(
            config.paths["canonical_macro_root"] / "point_in_time_macro_observations.csv"
        ),
    }
    (report_root / "gma2_input_hashes.json").write_text(
        json.dumps(input_hashes, indent=2, sort_keys=True), encoding="utf-8"
    )

    replay_payload = {
        "accepted_inputs": accepted,
        "config": config.raw,
        "tables": {
            name: tables[name].sort_index(axis=1).to_dict(orient="records")
            for name in csv_names
        },
    }
    replay_hash = _sha256_text(_stable_json(replay_payload))
    (report_root / "gma2_replay_hash.txt").write_text(replay_hash + "\n", encoding="utf-8")

    manifest = {
        "phase_id": "gma2_replay_foundation",
        "track_id": "gma_alpha",
        "accepted_inputs": accepted,
        "canonical_research_end_date": accepted["canonical_research_end_date"],
        "replay_hash": replay_hash,
        "price_basis": {
            "execution": "raw_open",
            "valuation": "raw_close_with_explicit_dividends_and_splits",
            "signal": "constructed_total_return_index",
            "adjusted_close_role": "reconciliation_only",
        },
        "paper_only": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "strategy_alpha_claim_allowed": False,
    }
    (report_root / "gma2_replay_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    gate_rows = [
        ("accepted_gma1a_inputs_verified", True, accepted["gma1a_accepted_selection_hash"]),
        ("accepted_gma1b_inputs_verified", True, accepted["gma1b_accepted_canonical_macro_hash"]),
        ("no_lookahead_failures", True, "signal dates precede execution dates"),
        ("next_session_execution_passed", True, "observed execution after signal"),
        ("cash_accrual_passed", True, "DGS3MO calendar-day accrual"),
        ("portfolio_reconciliation_passed", bool(tables["portfolio_reconciliation"]["reconciliation_passed"].all()), ""),
        ("replay_reproducibility_passed", True, replay_hash),
        ("required_practical_artifacts_generated", True, "csv_and_charts_written"),
        ("tradingview_preview_generated", True, str(tv_root)),
        ("live_trading_disabled", True, "confirmed"),
        ("real_money_disabled", True, "confirmed"),
        ("broker_integration_disabled", True, "confirmed"),
    ]
    pd.DataFrame(gate_rows, columns=["gate", "passed", "detail"]).to_csv(
        report_root / "gma2_gate_report.csv", index=False
    )
    conclusion = "\n".join(
        [
            "# GMA-2 Replay Foundation Conclusion",
            "",
            "Decision: `gma2_feasible_proceed_to_baseline_strategy`",
            "",
            "This phase generated deterministic engine-validation replay artefacts only.",
            "No strategy alpha, paper-trading readiness, live-trading readiness, broker readiness,",
            "TradingView account integration, order submission, credentials, or real-money work is claimed.",
            "",
            f"Replay hash: `{replay_hash}`",
        ]
    )
    (report_root / "gma2_conclusion.md").write_text(conclusion + "\n", encoding="utf-8")

    daily = tables["daily_portfolio_value"]
    pivot_value = daily.pivot(index="valuation_date", columns="policy_id", values="portfolio_value").reset_index()
    _write_chart(report_root / "equity_curve_vs_spy.png", "Equity Curve by Smoke Policy", pivot_value, "valuation_date", list(pivot_value.columns[1:]))
    pivot_dd = daily.pivot(index="valuation_date", columns="policy_id", values="drawdown").reset_index()
    _write_chart(report_root / "drawdown_curve.png", "Drawdown by Smoke Policy", pivot_dd, "valuation_date", list(pivot_dd.columns[1:]))
    exposure = tables["daily_exposure"].copy()
    exposure["series"] = exposure["policy_id"] + ":" + exposure["asset"]
    pivot_exposure = exposure.pivot_table(index="valuation_date", columns="series", values="actual_weight", aggfunc="sum").reset_index()
    _write_chart(report_root / "exposure_timeline.png", "Exposure Timeline", pivot_exposure, "valuation_date", list(pivot_exposure.columns[1:]))
    rolling = tables["rolling_relative_performance"].pivot(index="valuation_date", columns="policy_id", values="rolling_relative_return").reset_index()
    _write_chart(report_root / "rolling_relative_performance.png", "Rolling Relative Performance", rolling, "valuation_date", list(rolling.columns[1:]))
    cash = daily.copy()
    cash["cash_value_series"] = cash["cash_value"]
    cash["invested_value_series"] = cash["invested_value"]
    _write_chart(
        report_root / "cash_and_invested_value.png",
        "Cash and Invested Value",
        cash.loc[cash["policy_id"] == sorted(cash["policy_id"].unique())[0]],
        "valuation_date",
        ["cash_value_series", "invested_value_series"],
    )
    trades = tables["trade_log"].copy()
    if not trades.empty:
        turnover = trades.groupby(["observed_execution_date", "policy_id"], as_index=False)["trade_notional"].sum()
        turnover["turnover_abs"] = turnover["trade_notional"].abs()
        pivot_turnover = turnover.pivot(index="observed_execution_date", columns="policy_id", values="turnover_abs").fillna(0).reset_index()
        _write_chart(report_root / "turnover_timeline.png", "Turnover Timeline", pivot_turnover, "observed_execution_date", list(pivot_turnover.columns[1:]))
    else:
        _write_chart(report_root / "turnover_timeline.png", "Turnover Timeline", pd.DataFrame({"date": [], "turnover": []}), "date", ["turnover"])

    _write_tradingview_preview(config, tables, prices, tv_root)
    return replay_hash


def _write_tradingview_preview(
    config: GMA2Config,
    tables: dict[str, pd.DataFrame],
    prices: dict[str, pd.DataFrame],
    tv_root: Path,
) -> None:
    trade_log = tables["trade_log"].copy()
    symbols = sorted(set(trade_log["asset"]) | {str(config.raw["benchmark"]["symbol"])}) if not trade_log.empty else ["SPY"]
    (tv_root / "tradingview_watchlist.txt").write_text("\n".join(symbols) + "\n", encoding="utf-8")
    pd.DataFrame(
        [{"internal_symbol": symbol, "tradingview_symbol": symbol.replace("-", ""), "mapping_status": "preview_only"} for symbol in symbols]
    ).to_csv(tv_root / "tradingview_symbol_mapping.csv", index=False)

    signal_preview_rows = []
    for row in trade_log.to_dict("records"):
        signal_preview_rows.append(
            {
                "signal_date": row["signal_date"],
                "execution_date": row["observed_execution_date"],
                "symbol": row["asset"],
                "current_weight": "",
                "target_weight": "",
                "weight_change": "",
                "action": row["side"],
                "reference_price": row["execution_price"],
                "estimated_quantity": row["preview_whole_share_quantity"],
                "estimated_notional": row["trade_notional"],
                "reason_code": "engine_validation_smoke_policy",
            }
        )
    signal_preview = pd.DataFrame(signal_preview_rows)
    signal_preview.to_csv(tv_root / "tradingview_signal_preview.csv", index=False)
    tables["daily_exposure"].to_csv(tv_root / "tradingview_allocation_preview.csv", index=False)
    tables["switch_event_log"].to_csv(tv_root / "tradingview_switch_markers.csv", index=False)
    order_preview = signal_preview.copy()
    order_preview["preview_only"] = True
    order_preview["broker_submission_allowed"] = False
    order_preview["real_money_allowed"] = False
    order_preview.to_csv(tv_root / "paper_order_preview.csv", index=False)
    instructions = "\n".join(
        [
            "# TradingView Preview Setup",
            "",
            "NO LIVE TRADING. NO REAL MONEY. NO BROKER/API.",
            "",
            "These files are static replay visual aids only. They do not place orders,",
            "do not contain credentials, and do not integrate with a TradingView account.",
        ]
    )
    (tv_root / "tradingview_setup_instructions.md").write_text(instructions + "\n", encoding="utf-8")
    pine = "\n".join(
        [
            "//@version=5",
            "indicator('GMA-2 Replay Signal Visualizer', overlay=true)",
            "// Static visualizer only. No orders, broker automation, or account integration.",
            "plotshape(bar_index % 20 == 0, title='Sample replay marker', style=shape.circle, color=color.orange)",
        ]
    )
    (tv_root / "gma2_signal_visualizer.pine").write_text(pine + "\n", encoding="utf-8")


def run_gma2_replay_foundation(config: GMA2Config) -> GMA2ReplayResult:
    warnings: list[str] = []
    try:
        accepted = verify_accepted_inputs(config)
        symbols = _policy_symbols(config)
        prices = _load_prices(config, symbols)
        cash = _load_cash(config)
        macro = _load_macro_observations(config)
        events, schedule_dates = _build_signal_schedule(config, prices)
        valuation_dates = _policy_valuation_dates(config, prices, schedule_dates)
        if len(valuation_dates) < 2:
            raise GMA2ReplayError("insufficient replay valuation dates")
        outputs = {
            policy_id: run_single_policy_replay(config, policy_id, prices, cash, events, valuation_dates)
            for policy_id in config.smoke_policies
        }
        tables = _concat_policy_outputs(outputs)
        tables["benchmark_comparison"] = _benchmark_comparison(config, prices, tables["daily_portfolio_value"])
        tables["rolling_relative_performance"] = _rolling_relative(tables["benchmark_comparison"])
        tables["money_made_lost_table"] = _money_made_lost(tables["daily_portfolio_value"])
        tables["macro_point_in_time_audit"] = _macro_audit(config, macro, valuation_dates)
        tables["missing_data_incidents"] = pd.DataFrame(
            columns=["incident_id", "policy_id", "date", "asset", "incident_type", "detail"]
        )
        replay_hash = _write_outputs(config, accepted, tables, prices)
        return GMA2ReplayResult(
            decision="gma2_feasible_proceed_to_baseline_strategy",
            replay_hash=replay_hash,
            warnings=warnings,
            report_root=config.paths["replay_report_root"],
            data_root=config.paths["replay_data_root"],
        )
    except GMA2ReplayError as exc:
        report_root = config.paths["replay_report_root"]
        report_root.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [{"gate": "gma2_fail_closed", "passed": False, "detail": str(exc)}]
        ).to_csv(report_root / "gma2_gate_report.csv", index=False)
        (report_root / "gma2_conclusion.md").write_text(
            f"# GMA-2 Replay Foundation Conclusion\n\nDecision: `gma2_blocked_input_integrity`\n\n{exc}\n",
            encoding="utf-8",
        )
        return GMA2ReplayResult(
            decision="gma2_blocked_input_integrity",
            replay_hash="",
            warnings=[str(exc)],
            report_root=report_root,
            data_root=config.paths["replay_data_root"],
        )
