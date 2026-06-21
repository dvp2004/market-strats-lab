"""GMA-4 historical strategy tournament runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    GMA4_CANONICAL_RESEARCH_END_DATE,
    GMA4_EVIDENCE_CLASS,
    REQUIRED_SCOREBOARD_COLUMNS,
    GMA4TournamentConfig,
    GMA4TrialRegistry,
    load_gma4_tournament_config,
    load_gma4_trial_registry,
    validate_gma4_contract,
)
from market_strats.global_multi_asset.gma4_data_bundle import (
    DATA_BUNDLE_ROOT,
    REPORT_BUNDLE_ROOT,
    GMA4DataBundleError,
    load_gma4_bundle_prices_cash,
)
from market_strats.global_multi_asset.gma4_replay_adapter import (
    GMA4ReplayConfig,
    run_gma4_replay_adapter,
    validate_gma4_price_inputs,
)
from market_strats.global_multi_asset.gma4_strategy_library import build_gma4_trial_rules

OUTPUT_ROOT = Path("reports/global_multi_asset_alpha/gma4_cross_asset_tournament_v1/runs")
TRIAL_REGISTRY_PATH = Path("configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml")
BUNDLE_INVENTORY_PATH = REPORT_BUNDLE_ROOT / "gma4_market_bundle_inventory.csv"
BUNDLE_CASH_PATH = DATA_BUNDLE_ROOT / "cash" / "canonical_cash_accrual.csv"
RUN_HISTORY_FILENAME = "gma4_tournament_run_history_v1.csv"
LATEST_RESULTS_CSV = "gma4_latest_results_v1.csv"
LATEST_RESULTS_MD = "gma4_latest_results_v1.md"


@dataclass(frozen=True)
class GMA4TournamentResult:
    status: str
    run_id: str
    run_dir: Path
    compact_scoreboard: pd.DataFrame
    coverage: pd.DataFrame
    blockers: list[str]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _new_run_dir(base: Path = OUTPUT_ROOT, run_id_override: str | None = None) -> tuple[str, Path]:
    base.mkdir(parents=True, exist_ok=True)
    if run_id_override:
        run_dir = base / run_id_override
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_id_override, run_dir
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in ["", *[f"_{idx:02d}" for idx in range(1, 100)]]:
        run_id = f"gma4_{stamp}{suffix}"
        run_dir = base / run_id
        if not run_dir.exists():
            run_dir.mkdir(parents=False)
            return run_id, run_dir
    raise RuntimeError("Unable to create unique GMA-4 run directory")


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _coverage_markdown(coverage: pd.DataFrame, blockers: list[str]) -> list[str]:
    lines = [
        "Status: `blocked_data_coverage`" if blockers else "Status: `coverage_passed`",
        "",
        "This is a historical research preflight only.",
        "No operational action path is active.",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Coverage Rows", ""])
    for row in coverage.to_dict("records"):
        lines.append(
            f"- {row['symbol']}: {row['status']} "
            f"({row.get('first_date', '')} through {row.get('last_date', '')}, "
            f"sessions={row.get('session_count', 0)})"
        )
    return lines


def _load_gma4_bundle() -> tuple[
    dict[str, pd.DataFrame] | None, pd.DataFrame | None, pd.DataFrame, list[str]
]:
    try:
        prices, cash, inventory = load_gma4_bundle_prices_cash(
            inventory_path=BUNDLE_INVENTORY_PATH,
            cash_path=BUNDLE_CASH_PATH,
        )
    except GMA4DataBundleError as exc:
        return (
            None,
            None,
            pd.DataFrame([{"symbol": "ALL", "status": "blocked", "reason": str(exc)}]),
            [str(exc)],
        )
    coverage = pd.DataFrame(
        [
            {
                "symbol": row["instrument_id"],
                "status": "inventory_available",
                "reason": "",
                "first_date": row["first_available_date"],
                "last_date": row["last_available_date"],
                "session_count": row["session_count"],
            }
            for row in inventory.to_dict("records")
        ]
    )
    return prices, cash, coverage, []


def preflight_gma4_data(
    prices: dict[str, pd.DataFrame],
    cash: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame] | None, pd.DataFrame, list[str], list[Any]]:
    coverage_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    endpoint = GMA4_CANONICAL_RESEARCH_END_DATE
    try:
        validated = validate_gma4_price_inputs(prices)
    except Exception as exc:
        return (
            None,
            pd.DataFrame([{"symbol": "ALL", "status": "blocked", "reason": str(exc)}]),
            [str(exc)],
            [],
        )

    truncated: dict[str, pd.DataFrame] = {}
    for symbol in FIXED_GMA4_UNIVERSE:
        frame = validated[symbol].loc[validated[symbol].index <= endpoint].copy()
        status = "passed"
        reason = ""
        if endpoint not in frame.index:
            status = "blocked"
            reason = "canonical_endpoint_missing"
            blockers.append(f"{symbol}: {reason}")
        truncated[symbol] = frame
        coverage_rows.append(
            {
                "symbol": symbol,
                "status": status,
                "reason": reason,
                "first_date": "" if frame.empty else str(frame.index.min()),
                "last_date": "" if frame.empty else str(frame.index.max()),
                "session_count": int(len(frame)),
            }
        )

    if blockers:
        return None, pd.DataFrame(coverage_rows), blockers, []

    common_dates = set(truncated[FIXED_GMA4_UNIVERSE[0]].index)
    for symbol in FIXED_GMA4_UNIVERSE[1:]:
        common_dates &= set(truncated[symbol].index)
    dates = sorted(common_dates)
    if endpoint not in dates:
        blockers.append("incomplete 22-ETF common universe at canonical endpoint")
    cash_pairs = set(zip(cash["accrual_start"], cash["accrual_end"]))
    missing_cash = [
        (dates[idx - 1], dates[idx])
        for idx in range(1, len(dates))
        if (dates[idx - 1], dates[idx]) not in cash_pairs
    ]
    if missing_cash:
        blockers.append(f"cash accrual missing {len(missing_cash)} common-session periods")
    if blockers:
        return None, pd.DataFrame(coverage_rows), blockers, dates
    return truncated, pd.DataFrame(coverage_rows), [], dates


def trial_eligible_start_dates(dates: list[Any], registry: GMA4TrialRegistry) -> dict[str, Any]:
    rules = build_gma4_trial_rules()
    starts: dict[str, Any] = {}
    for trial in registry.trials:
        trial_id = str(trial["trial_id"])
        lookback = rules[trial_id].required_lookback_sessions
        idx = 0 if lookback == 0 else min(lookback, len(dates) - 1)
        starts[trial_id] = dates[idx]
    return starts


def _window_years(start: Any, end: Any) -> float:
    return max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)


def _session_count_between(
    dates: list[Any], start: Any, end: Any, *, include_start: bool = True
) -> int:
    return sum((date >= start if include_start else date > start) and date <= end for date in dates)


def _slice_result_frames(result: Any, start: Any, end: Any) -> dict[str, pd.DataFrame]:
    return {
        "equity": result.equity.loc[
            (pd.to_datetime(result.equity["valuation_date"]) >= pd.Timestamp(start))
            & (pd.to_datetime(result.equity["valuation_date"]) <= pd.Timestamp(end))
        ].copy(),
        "holdings": result.holdings.loc[
            (pd.to_datetime(result.holdings["valuation_date"]) >= pd.Timestamp(start))
            & (pd.to_datetime(result.holdings["valuation_date"]) <= pd.Timestamp(end))
        ].copy(),
        "orders": result.orders.loc[
            (
                pd.to_datetime(result.orders.get("execution_date", pd.Series(dtype=object)))
                >= pd.Timestamp(start)
            )
            & (
                pd.to_datetime(result.orders.get("execution_date", pd.Series(dtype=object)))
                <= pd.Timestamp(end)
            )
        ].copy()
        if not result.orders.empty
        else result.orders.copy(),
        "costs": result.costs.loc[
            (
                pd.to_datetime(result.costs.get("execution_date", pd.Series(dtype=object)))
                >= pd.Timestamp(start)
            )
            & (
                pd.to_datetime(result.costs.get("execution_date", pd.Series(dtype=object)))
                <= pd.Timestamp(end)
            )
        ].copy()
        if not result.costs.empty
        else result.costs.copy(),
    }


def _empty_metric_row(
    *,
    run_id: str,
    trial: dict[str, Any],
    cost_scenario: str,
    evaluation_scope: str,
    window_id: str,
    regime_id: str,
    start: Any,
    end: Any,
    eligible_start: Any,
    effective_start: Any,
    excluded_sessions: int,
    regime_coverage_status: str,
    rejection_reason: str,
) -> dict[str, Any]:
    row = {column: "" for column in REQUIRED_SCOREBOARD_COLUMNS}
    row.update(
        {
            "run_id": run_id,
            "trial_id": trial["trial_id"],
            "strategy_id": trial["strategy_id"],
            "family": trial["family"],
            "cost_scenario": cost_scenario,
            "evaluation_scope": evaluation_scope,
            "window_id": window_id,
            "regime_id": regime_id,
            "start_date": start,
            "end_date": end,
            "trial_decision_eligible_start_date": eligible_start,
            "evaluation_effective_start_date": effective_start,
            "excluded_pre_decision_sessions": excluded_sessions,
            "regime_coverage_status": regime_coverage_status,
            "evidence_class": GMA4_EVIDENCE_CLASS,
            "status": "rejected",
            "rejection_reason": rejection_reason,
        }
    )
    return row


def _metrics_for_window(
    *,
    run_id: str,
    trial: dict[str, Any],
    cost_scenario: str,
    evaluation_scope: str,
    window_id: str,
    regime_id: str,
    start: Any,
    end: Any,
    eligible_start: Any,
    dates: list[Any],
    frames: dict[str, pd.DataFrame],
    benchmark_terminal_return: float,
    hashes: dict[str, str],
) -> dict[str, Any]:
    effective_start = max(start, eligible_start)
    excluded_sessions = (
        _session_count_between(dates, start, min(effective_start, end), include_start=True)
        if effective_start > start
        else 0
    )
    regime_coverage_status = (
        "partial_pre_decision_coverage"
        if effective_start > start
        else "full_decision_eligible_coverage"
    )
    if effective_start > end:
        return _empty_metric_row(
            run_id=run_id,
            trial=trial,
            cost_scenario=cost_scenario,
            evaluation_scope=evaluation_scope,
            window_id=window_id,
            regime_id=regime_id,
            start=start,
            end=end,
            eligible_start=eligible_start,
            effective_start=effective_start,
            excluded_sessions=excluded_sessions,
            regime_coverage_status="no_decision_eligible_overlap",
            rejection_reason="window_before_trial_decision_eligible_start",
        )
    equity = frames["equity"].sort_values("valuation_date")
    holdings = frames["holdings"]
    costs = frames["costs"]
    orders = frames["orders"]
    if equity.empty:
        return _empty_metric_row(
            run_id=run_id,
            trial=trial,
            cost_scenario=cost_scenario,
            evaluation_scope=evaluation_scope,
            window_id=window_id,
            regime_id=regime_id,
            start=start,
            end=end,
            eligible_start=eligible_start,
            effective_start=effective_start,
            excluded_sessions=excluded_sessions,
            regime_coverage_status=regime_coverage_status,
            rejection_reason="empty_window",
        )
    years = _window_years(equity.iloc[0]["valuation_date"], equity.iloc[-1]["valuation_date"])
    terminal_wealth = float(equity.iloc[-1]["portfolio_value"])
    start_wealth = float(equity.iloc[0]["portfolio_value"])
    total_return = terminal_wealth / start_wealth - 1.0
    returns = pd.to_numeric(equity["daily_return"], errors="coerce").fillna(0.0)
    downside = returns[returns < 0]
    vol = float(returns.std(ddof=0) * (252**0.5))
    downside_vol = float(downside.std(ddof=0) * (252**0.5)) if not downside.empty else 0.0
    net_cagr = (terminal_wealth / start_wealth) ** (1.0 / years) - 1.0
    max_drawdown = float(pd.to_numeric(equity["drawdown"], errors="coerce").min())
    cost_sum = float(
        pd.to_numeric(costs.get("transaction_cost", pd.Series(dtype=float)), errors="coerce").sum()
    )
    trade_abs = float(
        pd.to_numeric(
            costs.get("trade_notional_abs", pd.Series(dtype=float)), errors="coerce"
        ).sum()
    )
    holding_weights = holdings.pivot_table(
        index="valuation_date", columns="symbol", values="weight", aggfunc="sum"
    ).fillna(0.0)
    non_cash = [column for column in holding_weights.columns if column != "CASH"]
    max_single = float(holding_weights[non_cash].max().max()) if non_cash else 0.0
    bil_cash = holding_weights.get("BIL", 0.0) + holding_weights.get("CASH", 0.0)
    hhi = (holding_weights[non_cash] ** 2).sum(axis=1) if non_cash else pd.Series([0.0])
    return {
        "run_id": run_id,
        "trial_id": trial["trial_id"],
        "strategy_id": trial["strategy_id"],
        "family": trial["family"],
        "cost_scenario": cost_scenario,
        "evaluation_scope": evaluation_scope,
        "window_id": window_id,
        "regime_id": regime_id,
        "start_date": str(start),
        "end_date": str(end),
        "trial_decision_eligible_start_date": str(eligible_start),
        "evaluation_effective_start_date": str(effective_start),
        "excluded_pre_decision_sessions": excluded_sessions,
        "regime_coverage_status": regime_coverage_status,
        "session_count": int(len(equity)),
        "terminal_wealth": terminal_wealth,
        "net_cagr": net_cagr,
        "annualised_volatility": vol,
        "sharpe_0rf": 0.0 if vol == 0 else float(returns.mean() * 252 / vol),
        "sortino_0rf": 0.0 if downside_vol == 0 else float(returns.mean() * 252 / downside_vol),
        "max_drawdown": max_drawdown,
        "calmar": 0.0 if max_drawdown == 0 else net_cagr / abs(max_drawdown),
        "time_underwater_days": int((pd.to_numeric(equity["drawdown"], errors="coerce") < 0).sum()),
        "trade_count": int(len(orders)),
        "cumulative_turnover": 0.0 if start_wealth == 0 else trade_abs / start_wealth,
        "annualised_turnover": 0.0 if start_wealth == 0 else (trade_abs / start_wealth) / years,
        "cost_drag": 0.0 if start_wealth == 0 else cost_sum / start_wealth,
        "average_rebalance_turnover": 0.0
        if len(orders) == 0 or start_wealth == 0
        else (trade_abs / start_wealth) / len(orders),
        "max_single_asset_weight_observed": max_single,
        "average_cash_weight": float(pd.Series(bil_cash).mean()),
        "maximum_cash_weight": float(pd.Series(bil_cash).max()),
        "maximum_hhi_concentration": float(hhi.max()),
        "benchmark_relative_return": total_return - benchmark_terminal_return,
        "data_hash": hashes["data_hash"],
        "config_hash": hashes["config_hash"],
        "trial_hash": _sha256_text(_stable_json(trial)),
        "evidence_class": GMA4_EVIDENCE_CLASS,
        "status": "evaluated",
        "rejection_reason": "",
    }


def _evaluation_windows(
    config: GMA4TournamentConfig, dates: list[Any]
) -> list[tuple[str, str, str, Any, Any]]:
    start = dates[0]
    end = dates[-1]
    windows = [("full_common_history", "full_common_history", "", start, end)]
    for years, scope in [(3, "rolling_3_year"), (5, "rolling_5_year")]:
        for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
            w_start = pd.Timestamp(year=year, month=1, day=1).date()
            w_end = (pd.Timestamp(year=year + years, month=1, day=1) - pd.Timedelta(days=1)).date()
            if w_start >= start and w_end <= end:
                windows.append((scope, f"{year}_{year + years - 1}", "", w_start, w_end))
    for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        w_start = max(pd.Timestamp(year=year, month=1, day=1).date(), start)
        w_end = min(pd.Timestamp(year=year, month=12, day=31).date(), end)
        if w_start <= w_end:
            windows.append(("sequential_walk_forward", str(year), "", w_start, w_end))
    for regime in config.regimes:
        r_start = max(pd.Timestamp(regime["start_date"]).date(), start)
        r_end = min(pd.Timestamp(regime["end_date"]).date(), end)
        if r_start <= r_end:
            windows.append(
                (
                    "predefined_regime",
                    str(regime["regime_id"]),
                    str(regime["regime_id"]),
                    r_start,
                    r_end,
                )
            )
    return windows


def _run_trials(
    *,
    run_id: str,
    config: GMA4TournamentConfig,
    registry: GMA4TrialRegistry,
    prices: dict[str, pd.DataFrame],
    cash: pd.DataFrame,
    dates: list[Any],
    hashes: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rules = build_gma4_trial_rules()
    eligible_starts = trial_eligible_start_dates(dates, registry)
    windows = _evaluation_windows(config, dates)
    details: list[dict[str, Any]] = []
    scoreboard_rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    benchmark_return = 0.0
    trial_lookup = {trial["trial_id"]: trial for trial in registry.trials}
    for cost_scenario in config.cost_scenarios:
        bps = {
            "baseline_1bps": 1.0,
            "stressed_10bps": 10.0,
            "stressed_25bps": 25.0,
            "severe_50bps": 50.0,
        }[cost_scenario]
        trial_results: dict[str, Any] = {}
        for trial in registry.trials:
            trial_id = trial["trial_id"]
            rule = rules[trial_id]
            try:
                result = run_gma4_replay_adapter(
                    prices=prices,
                    cash=cash,
                    macro=pd.DataFrame(),
                    target_resolver=rule.resolver,
                    rebalance_schedule=rule.rebalance_schedule,
                    strategy_id=trial_id,
                    strategy_version=str(trial["version"]),
                    config=GMA4ReplayConfig(
                        cost_bps_per_notional=bps, maximum_single_asset_weight=0.35
                    ),
                    minimum_signal_date=eligible_starts[trial_id],
                )
                trial_results[trial_id] = result
                if trial_id == "gma4_benchmark_spy_buy_hold_v1":
                    equity = result.equity.sort_values("valuation_date")
                    benchmark_return = float(
                        equity.iloc[-1]["portfolio_value"] / equity.iloc[0]["portfolio_value"] - 1.0
                    )
                details.append(
                    {
                        "trial_id": trial_id,
                        "cost_scenario": cost_scenario,
                        "trial_decision_eligible_start_date": eligible_starts[trial_id],
                        "evaluation_effective_start_date": eligible_starts[trial_id],
                        "excluded_pre_decision_sessions": dates.index(eligible_starts[trial_id]),
                        "regime_coverage_status": "trial_level_not_window_specific",
                        "equity_rows": len(result.equity),
                        "order_rows": len(result.orders),
                        "fill_rows": len(result.fills),
                        "signal_rows": len(result.signals),
                    }
                )
            except Exception as exc:
                rejections.append(
                    {
                        "trial_id": trial_id,
                        "cost_scenario": cost_scenario,
                        "rejection_reason": str(exc),
                    }
                )
        for trial_id, result in trial_results.items():
            trial = trial_lookup[trial_id]
            eligible_start = eligible_starts[trial_id]
            for scope, window_id, regime_id, start, end in windows:
                effective_start = max(start, eligible_start)
                frames = _slice_result_frames(result, effective_start, end)
                scoreboard_rows.append(
                    _metrics_for_window(
                        run_id=run_id,
                        trial=trial,
                        cost_scenario=cost_scenario,
                        evaluation_scope=scope,
                        window_id=window_id,
                        regime_id=regime_id,
                        start=start,
                        end=end,
                        eligible_start=eligible_start,
                        dates=dates,
                        frames=frames,
                        benchmark_terminal_return=benchmark_return,
                        hashes=hashes,
                    )
                )
    scoreboard = pd.DataFrame(scoreboard_rows)
    for column in REQUIRED_SCOREBOARD_COLUMNS:
        if column not in scoreboard.columns:
            scoreboard[column] = ""
    return scoreboard[REQUIRED_SCOREBOARD_COLUMNS], pd.DataFrame(details), pd.DataFrame(rejections)


def _write_scoreboard_markdown(path: Path, scoreboard: pd.DataFrame) -> None:
    full = scoreboard.loc[
        (scoreboard["evaluation_scope"] == "full_common_history")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["status"] == "evaluated")
    ].copy()
    full["net_cagr"] = pd.to_numeric(full["net_cagr"], errors="coerce")
    full = full.sort_values("net_cagr", ascending=False).head(10)
    lines = [
        "Evidence class: `observed_development_evidence`.",
        "Endpoint interpretation: `not_a_pristine_final_holdout`.",
        "Warning: highest historical Sharpe or CAGR alone is not a selection rule.",
        "Historical research table only; no operational action is produced.",
        "",
        "## Compact Full-History Table",
        "",
        "| trial_id | net_cagr | sharpe_0rf | max_drawdown | annualised_turnover | effective_start |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in full.to_dict("records"):
        lines.append(
            f"| {row['trial_id']} | {float(row['net_cagr']):.6f} | {float(row['sharpe_0rf']):.6f} | "
            f"{float(row['max_drawdown']):.6f} | {float(row['annualised_turnover']):.6f} | {row['evaluation_effective_start_date']} |"
        )
    robust_source = scoreboard.copy()
    robust_source["net_cagr"] = pd.to_numeric(robust_source["net_cagr"], errors="coerce")
    robust_source["max_drawdown"] = pd.to_numeric(robust_source["max_drawdown"], errors="coerce")
    robust = robust_source.groupby("trial_id", as_index=False).agg(
        evaluated_rows=("status", lambda values: int((values == "evaluated").sum())),
        min_net_cagr=("net_cagr", "min"),
        max_drawdown=("max_drawdown", "min"),
    )
    lines.extend(
        [
            "",
            "## Robustness Table",
            "",
            "| trial_id | evaluated_rows | min_net_cagr | worst_drawdown |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in robust.to_dict("records"):
        lines.append(
            f"| {row['trial_id']} | {int(row['evaluated_rows'])} | {float(row['min_net_cagr']):.6f} | {float(row['max_drawdown']):.6f} |"
        )
    _write_markdown(path, "GMA-4 Historical Tournament Scoreboard", lines)


HISTORY_COLUMNS = [
    "run_id",
    "run_timestamp_utc",
    "git_commit",
    "tournament_status",
    "evidence_class",
    "canonical_endpoint",
    "fixed_universe_count",
    "common_history_start",
    "common_history_end",
    "common_session_count",
    "cash_source_id",
    "cash_source_hash",
    "bundle_manifest_hash",
    "config_hash",
    "trial_registry_hash",
    "data_hash",
    "scoreboard_created",
    "scoreboard_row_count",
    "notes",
]

LATEST_RESULT_COLUMNS = [
    "run_id",
    "trial_id",
    "strategy_id",
    "family",
    "net_cagr",
    "terminal_wealth",
    "max_drawdown",
    "sharpe_0rf",
    "sortino_0rf",
    "annualised_turnover",
    "cost_drag",
    "max_single_asset_weight_observed",
    "average_cash_weight",
    "maximum_cash_weight",
    "benchmark_relative_return",
    "evaluation_effective_start_date",
    "status",
]


def _run_timestamp_utc(run_id: str) -> str:
    prefix = "gma4_"
    stamp = run_id[len(prefix) : len(prefix) + 16] if run_id.startswith(prefix) else ""
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _read_bundle_manifest() -> dict[str, Any]:
    path = REPORT_BUNDLE_ROOT / "gma4_data_bundle_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _history_common_from_manifest(manifest: dict[str, Any]) -> tuple[str, str, int]:
    start = str(manifest.get("common_history_start", ""))
    end = str(manifest.get("common_history_end", ""))
    if not start or not end:
        return start, end, 0
    try:
        inventory = pd.read_csv(REPORT_BUNDLE_ROOT / "gma4_market_bundle_inventory.csv")
        common: set[Any] | None = None
        for row in inventory.to_dict("records"):
            frame = pd.read_csv(Path(str(row["canonical_file_path"])))
            dates = set(pd.to_datetime(frame["date"]).dt.date)
            common = dates if common is None else common & dates
        return start, end, len(common or [])
    except Exception:
        return start, end, 0


def _append_run_history(comparison_root: Path, row: dict[str, Any]) -> None:
    comparison_root.mkdir(parents=True, exist_ok=True)
    path = comparison_root / RUN_HISTORY_FILENAME
    new_row = pd.DataFrame([{column: row.get(column, "") for column in HISTORY_COLUMNS}])
    if path.exists():
        existing = pd.read_csv(path)
        for column in HISTORY_COLUMNS:
            if column not in existing.columns:
                existing[column] = ""
        if str(row["run_id"]) in set(existing["run_id"].astype(str)):
            existing[HISTORY_COLUMNS].to_csv(path, index=False)
            return
        output = pd.concat([existing[HISTORY_COLUMNS], new_row], ignore_index=True)
    else:
        output = new_row
    output.to_csv(path, index=False)


def _write_latest_blocked(comparison_root: Path, *, run_id: str, blockers: list[str]) -> None:
    comparison_root.mkdir(parents=True, exist_ok=True)
    rows = [
        {"run_id": run_id, "tournament_status": "blocked_data_coverage", "blocker": blocker}
        for blocker in blockers
    ] or [{"run_id": run_id, "tournament_status": "blocked_data_coverage", "blocker": "unknown"}]
    pd.DataFrame(rows).to_csv(comparison_root / LATEST_RESULTS_CSV, index=False)
    lines = [
        "# GMA-4 Latest Tournament Results",
        "",
        f"Run ID: `{run_id}`",
        "Status: `blocked_data_coverage`",
        "",
        "No performance rows were written because the tournament did not pass data coverage.",
        "",
        "## Blockers",
        "",
        *(f"- {blocker}" for blocker in blockers),
    ]
    (comparison_root / LATEST_RESULTS_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_latest_success(comparison_root: Path, *, run_id: str, scoreboard: pd.DataFrame) -> None:
    comparison_root.mkdir(parents=True, exist_ok=True)
    latest = scoreboard.loc[
        (scoreboard["evaluation_scope"] == "full_common_history")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["status"] == "evaluated")
    ].copy()
    latest["net_cagr"] = pd.to_numeric(latest["net_cagr"], errors="coerce")
    latest = latest.sort_values("net_cagr", ascending=False)
    latest[LATEST_RESULT_COLUMNS].to_csv(comparison_root / LATEST_RESULTS_CSV, index=False)
    lines = [
        "# GMA-4 Latest Tournament Results",
        "",
        f"Run ID: `{run_id}`",
        "Period: `full_common_history`",
        "Cost scenario: `baseline_1bps`",
        "Warning: highest historical CAGR or Sharpe alone is not a selection rule.",
        "Historical research table only; no operational action is produced.",
        "",
        "| trial_id | family | net_cagr | terminal_wealth | max_drawdown | sharpe_0rf | sortino_0rf | turnover | effective_start |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in latest.to_dict("records"):
        lines.append(
            f"| {row['trial_id']} | {row['family']} | {float(row['net_cagr']):.6f} | "
            f"{float(row['terminal_wealth']):.2f} | {float(row['max_drawdown']):.6f} | "
            f"{float(row['sharpe_0rf']):.6f} | {float(row['sortino_0rf']):.6f} | "
            f"{float(row['annualised_turnover']):.6f} | {row['evaluation_effective_start_date']} |"
        )
    (comparison_root / LATEST_RESULTS_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_persistent_comparison_outputs(
    *,
    comparison_root: Path,
    run_id: str,
    status: str,
    config_path: Path,
    registry_path: Path,
    data_hash: str,
    scoreboard: pd.DataFrame | None,
    blockers: list[str],
    dates: list[Any],
) -> None:
    bundle_manifest = _read_bundle_manifest()
    cash_source = bundle_manifest.get("cash_source") or {}
    common_start, common_end, common_count = (
        (str(dates[0]), str(dates[-1]), len(dates))
        if dates
        else _history_common_from_manifest(bundle_manifest)
    )
    bundle_manifest_path = REPORT_BUNDLE_ROOT / "gma4_data_bundle_manifest.json"
    scoreboard_created = scoreboard is not None and not scoreboard.empty
    row = {
        "run_id": run_id,
        "run_timestamp_utc": _run_timestamp_utc(run_id),
        "git_commit": _git_commit(),
        "tournament_status": status,
        "evidence_class": GMA4_EVIDENCE_CLASS,
        "canonical_endpoint": str(GMA4_CANONICAL_RESEARCH_END_DATE),
        "fixed_universe_count": len(FIXED_GMA4_UNIVERSE),
        "common_history_start": common_start,
        "common_history_end": common_end,
        "common_session_count": common_count,
        "cash_source_id": cash_source.get("cash_source_id", ""),
        "cash_source_hash": cash_source.get("cash_source_hash", ""),
        "bundle_manifest_hash": _sha256_file(bundle_manifest_path)
        if bundle_manifest_path.exists()
        else "",
        "config_hash": _sha256_file(config_path),
        "trial_registry_hash": _sha256_file(registry_path),
        "data_hash": data_hash,
        "scoreboard_created": bool(scoreboard_created),
        "scoreboard_row_count": 0 if scoreboard is None else int(len(scoreboard)),
        "notes": "; ".join(blockers),
    }
    _append_run_history(comparison_root, row)
    if scoreboard_created and scoreboard is not None:
        _write_latest_success(comparison_root, run_id=run_id, scoreboard=scoreboard)
    else:
        _write_latest_blocked(comparison_root, run_id=run_id, blockers=blockers)


def run_gma4_tournament(
    *,
    config_path: Path,
    registry_path: Path = TRIAL_REGISTRY_PATH,
    prices: dict[str, pd.DataFrame] | None = None,
    cash: pd.DataFrame | None = None,
    output_root: Path = OUTPUT_ROOT,
    run_id_override: str | None = None,
) -> GMA4TournamentResult:
    config = load_gma4_tournament_config(config_path)
    registry = load_gma4_trial_registry(registry_path)
    validate_gma4_contract(config, registry)
    run_id, run_dir = _new_run_dir(output_root, run_id_override)
    loaded_prices = prices
    loaded_cash = cash
    initial_coverage = pd.DataFrame()
    blockers: list[str] = []
    if loaded_prices is None or loaded_cash is None:
        loaded_prices, loaded_cash, initial_coverage, blockers = _load_gma4_bundle()
    if blockers or loaded_prices is None or loaded_cash is None:
        coverage = initial_coverage
        coverage.to_csv(run_dir / "gma4_data_coverage.csv", index=False)
        _write_markdown(
            run_dir / "gma4_data_coverage.md",
            "GMA-4 Data Coverage",
            _coverage_markdown(coverage, blockers),
        )
        _write_persistent_comparison_outputs(
            comparison_root=output_root.parent,
            run_id=run_id,
            status="blocked_data_coverage",
            config_path=config_path,
            registry_path=registry_path,
            data_hash="",
            scoreboard=None,
            blockers=blockers,
            dates=[],
        )
        return GMA4TournamentResult(
            "blocked_data_coverage", run_id, run_dir, pd.DataFrame(), coverage, blockers
        )
    valid_prices, coverage, blockers, dates = preflight_gma4_data(loaded_prices, loaded_cash)
    coverage.to_csv(run_dir / "gma4_data_coverage.csv", index=False)
    _write_markdown(
        run_dir / "gma4_data_coverage.md",
        "GMA-4 Data Coverage",
        _coverage_markdown(coverage, blockers),
    )
    if blockers or valid_prices is None:
        _write_persistent_comparison_outputs(
            comparison_root=output_root.parent,
            run_id=run_id,
            status="blocked_data_coverage",
            config_path=config_path,
            registry_path=registry_path,
            data_hash="",
            scoreboard=None,
            blockers=blockers,
            dates=dates,
        )
        return GMA4TournamentResult(
            "blocked_data_coverage", run_id, run_dir, pd.DataFrame(), coverage, blockers
        )

    hashes = {
        "config_hash": _sha256_file(config_path),
        "trial_registry_hash": _sha256_file(registry_path),
        "data_hash": _sha256_text(
            _stable_json(
                {
                    symbol: [
                        str(valid_prices[symbol].index.min()),
                        str(valid_prices[symbol].index.max()),
                        len(valid_prices[symbol]),
                    ]
                    for symbol in FIXED_GMA4_UNIVERSE
                }
            )
        ),
    }
    pd.DataFrame(registry.trials).to_csv(run_dir / "gma4_trial_registry_snapshot.csv", index=False)
    scoreboard, detail, rejections = _run_trials(
        run_id=run_id,
        config=config,
        registry=registry,
        prices=valid_prices,
        cash=loaded_cash,
        dates=dates,
        hashes=hashes,
    )
    scoreboard.to_csv(run_dir / "gma4_tournament_scoreboard.csv", index=False)
    _write_scoreboard_markdown(run_dir / "gma4_tournament_scoreboard.md", scoreboard)
    detail.to_csv(run_dir / "gma4_evaluation_detail.csv", index=False)
    rejections.to_csv(run_dir / "gma4_rejections.csv", index=False)
    eligible_starts = {
        key: str(value) for key, value in trial_eligible_start_dates(dates, registry).items()
    }
    manifest = {
        "run_id": run_id,
        "git_commit": _git_commit(),
        "config_hash": hashes["config_hash"],
        "trial_registry_hash": hashes["trial_registry_hash"],
        "data_hash": hashes["data_hash"],
        "common_history_start": str(dates[0]),
        "common_history_end": str(dates[-1]),
        "canonical_endpoint": str(GMA4_CANONICAL_RESEARCH_END_DATE),
        "trial_decision_eligible_start_dates": eligible_starts,
        "cost_scenarios": config.cost_scenarios,
        "evidence_class": GMA4_EVIDENCE_CLASS,
        "holdout_status": "not_a_pristine_final_holdout",
        "candidate_selection": "not_performed",
    }
    (run_dir / "gma4_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    compact = scoreboard.loc[
        (scoreboard["evaluation_scope"] == "full_common_history")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["status"] == "evaluated")
    ].copy()
    compact["net_cagr"] = pd.to_numeric(compact["net_cagr"], errors="coerce")
    compact = compact.sort_values("net_cagr", ascending=False)
    _write_persistent_comparison_outputs(
        comparison_root=output_root.parent,
        run_id=run_id,
        status="completed",
        config_path=config_path,
        registry_path=registry_path,
        data_hash=hashes["data_hash"],
        scoreboard=scoreboard,
        blockers=[],
        dates=dates,
    )
    return GMA4TournamentResult("completed", run_id, run_dir, compact, coverage, [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma4_tournament"
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_gma4_tournament(config_path=args.config)
    print(f"status: {result.status}")
    print(f"run_id: {result.run_id}")
    print(f"run_dir: {result.run_dir}")
    if result.blockers:
        print("coverage_blockers:")
        for blocker in result.blockers:
            print(f"  {blocker}")
    elif not result.compact_scoreboard.empty:
        print("compact_scoreboard:")
        for row in result.compact_scoreboard.head(10).to_dict("records"):
            print(
                f"  {row['trial_id']} net_cagr={row['net_cagr']} sharpe={row['sharpe_0rf']} effective_start={row['evaluation_effective_start_date']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
