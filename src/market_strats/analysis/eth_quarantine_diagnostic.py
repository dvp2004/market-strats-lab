from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.asset_expansion_diagnostic import (
    _build_close_panel,
    _get_strategy_result,
    _run_constrained_trend_confirmed_allocator,
    _slice_and_rebase_result,
)
from market_strats.analysis.metrics import calculate_metrics
from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _create_metric_rows(
    results: dict[str, pd.DataFrame],
    initial_capital: float,
) -> pd.DataFrame:
    rows: list[dict] = []

    for strategy_name, result in results.items():
        sliced = _slice_and_rebase_result(
            result=result,
            start_date=None,
            end_date=None,
            initial_capital=initial_capital,
        )

        if sliced.empty:
            continue

        metrics = calculate_metrics(sliced, strategy_name)

        rows.append(
            {
                "strategy": strategy_name,
                "start_date": metrics["start_date"],
                "end_date": metrics["end_date"],
                "end_value": metrics["end_value"],
                "cagr_pct": metrics["cagr_pct"],
                "calmar": metrics["calmar"],
                "volatility_pct": metrics["volatility_pct"],
                "sharpe": metrics["sharpe"],
                "sortino": metrics["sortino"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "worst_month_pct": metrics["worst_month_pct"],
                "exposure_time_pct": metrics["exposure_time_pct"],
                "trade_count": metrics["trade_count"],
            }
        )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def _get_row(metrics: pd.DataFrame, strategy: str) -> pd.Series | None:
    rows = metrics[metrics["strategy"] == strategy]

    if rows.empty:
        return None

    return rows.iloc[0]


def _safe_float(row: pd.Series | None, column: str) -> float | None:
    if row is None or column not in row.index:
        return None

    value = row[column]

    if pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(
    expanded: pd.Series | None,
    baseline: pd.Series | None,
    column: str,
) -> float | None:
    expanded_value = _safe_float(expanded, column)
    baseline_value = _safe_float(baseline, column)

    if expanded_value is None or baseline_value is None:
        return None

    return round(expanded_value - baseline_value, 3)


def _asset_allocation_stats(
    allocation_summary: pd.DataFrame,
    universe_name: str,
    asset: str,
) -> dict:
    rows = allocation_summary[
        (allocation_summary["universe"] == universe_name)
        & (allocation_summary["asset"] == asset)
    ]

    if rows.empty:
        return {
            "avg_weight_pct": 0.0,
            "max_weight_pct": 0.0,
            "days_held": 0,
            "pct_days_held": 0.0,
            "final_weight_pct": 0.0,
        }

    row = rows.iloc[0]

    return {
        "avg_weight_pct": float(row["avg_weight_pct"]),
        "max_weight_pct": float(row["max_weight_pct"]),
        "days_held": int(row["days_held"]),
        "pct_days_held": float(row["pct_days_held"]),
        "final_weight_pct": float(row["final_weight_pct"]),
    }


def _create_decision(
    metrics: pd.DataFrame,
    allocation_summary: pd.DataFrame,
    baseline_name: str,
    eth_name: str,
    oil_eth_name: str,
) -> pd.DataFrame:
    base_overlay = _get_row(metrics, f"{baseline_name} 3D Overlay")
    eth_overlay = _get_row(metrics, f"{eth_name} 3D Overlay")
    oil_eth_overlay = _get_row(metrics, f"{oil_eth_name} 3D Overlay")

    base_allocator = _get_row(metrics, f"{baseline_name} Allocator")
    eth_allocator = _get_row(metrics, f"{eth_name} Allocator")
    oil_eth_allocator = _get_row(metrics, f"{oil_eth_name} Allocator")

    eth_stats = _asset_allocation_stats(
        allocation_summary=allocation_summary,
        universe_name=eth_name,
        asset="ETH-USD",
    )
    oil_eth_eth_stats = _asset_allocation_stats(
        allocation_summary=allocation_summary,
        universe_name=oil_eth_name,
        asset="ETH-USD",
    )
    oil_eth_uso_stats = _asset_allocation_stats(
        allocation_summary=allocation_summary,
        universe_name=oil_eth_name,
        asset="USO",
    )

    eth_overlay_cagr_delta = _delta(eth_overlay, base_overlay, "cagr_pct")
    eth_overlay_calmar_delta = _delta(eth_overlay, base_overlay, "calmar")
    eth_overlay_drawdown_delta = _delta(
        eth_overlay,
        base_overlay,
        "max_drawdown_pct",
    )
    eth_overlay_volatility_delta = _delta(
        eth_overlay,
        base_overlay,
        "volatility_pct",
    )

    oil_eth_overlay_cagr_delta = _delta(
        oil_eth_overlay,
        base_overlay,
        "cagr_pct",
    )
    oil_eth_overlay_calmar_delta = _delta(
        oil_eth_overlay,
        base_overlay,
        "calmar",
    )
    oil_eth_overlay_drawdown_delta = _delta(
        oil_eth_overlay,
        base_overlay,
        "max_drawdown_pct",
    )
    oil_eth_overlay_volatility_delta = _delta(
        oil_eth_overlay,
        base_overlay,
        "volatility_pct",
    )

    eth_allocator_cagr_delta = _delta(eth_allocator, base_allocator, "cagr_pct")
    oil_eth_allocator_cagr_delta = _delta(
        oil_eth_allocator,
        base_allocator,
        "cagr_pct",
    )

    eth_used = eth_stats["avg_weight_pct"] >= 0.5 and eth_stats["days_held"] > 30
    eth_dominates = eth_stats["avg_weight_pct"] > 5.0 or eth_stats["pct_days_held"] > 25.0

    eth_overlay_pass = (
        eth_overlay_cagr_delta is not None
        and eth_overlay_calmar_delta is not None
        and eth_overlay_drawdown_delta is not None
        and eth_overlay_volatility_delta is not None
        and eth_overlay_cagr_delta > 0.25
        and eth_overlay_calmar_delta > 0.02
        and eth_overlay_drawdown_delta >= -2.0
        and eth_overlay_volatility_delta <= 2.0
    )

    oil_eth_overlay_pass = (
        oil_eth_overlay_cagr_delta is not None
        and oil_eth_overlay_calmar_delta is not None
        and oil_eth_overlay_drawdown_delta is not None
        and oil_eth_overlay_volatility_delta is not None
        and oil_eth_overlay_cagr_delta > 0.25
        and oil_eth_overlay_calmar_delta > 0.02
        and oil_eth_overlay_drawdown_delta >= -2.0
        and oil_eth_overlay_volatility_delta <= 2.0
    )

    if eth_overlay_pass and not eth_dominates:
        eth_classification = "Quarantined candidate"
        eth_verdict = (
            "ETH improved the capped quarantine overlay without dominating the portfolio. "
            "Keep for deeper validation."
        )
    elif eth_overlay_pass and eth_dominates:
        eth_classification = "Return-improving but unstable"
        eth_verdict = (
            "ETH improved headline metrics but took too much portfolio influence. "
            "Do not promote without stricter caps and deeper validation."
        )
    elif not eth_used:
        eth_classification = "Ignored"
        eth_verdict = "ETH was barely selected under the current rules."
    else:
        eth_classification = "Rejected"
        eth_verdict = (
            "ETH did not improve the capped overlay enough to justify inclusion."
        )

    if oil_eth_overlay_pass:
        oil_eth_classification = "Combined expansion candidate"
    else:
        oil_eth_classification = "Combined expansion not validated"

    return pd.DataFrame(
        [
            {
                "comparison": f"{eth_name} vs {baseline_name}",
                "added_asset": "ETH-USD",
                "baseline_overlay_cagr_pct": _safe_float(base_overlay, "cagr_pct"),
                "expanded_overlay_cagr_pct": _safe_float(eth_overlay, "cagr_pct"),
                "overlay_cagr_delta_pct_points": eth_overlay_cagr_delta,
                "baseline_overlay_calmar": _safe_float(base_overlay, "calmar"),
                "expanded_overlay_calmar": _safe_float(eth_overlay, "calmar"),
                "overlay_calmar_delta": eth_overlay_calmar_delta,
                "baseline_overlay_max_drawdown_pct": _safe_float(
                    base_overlay,
                    "max_drawdown_pct",
                ),
                "expanded_overlay_max_drawdown_pct": _safe_float(
                    eth_overlay,
                    "max_drawdown_pct",
                ),
                "overlay_drawdown_delta_pct_points": eth_overlay_drawdown_delta,
                "overlay_volatility_delta_pct_points": eth_overlay_volatility_delta,
                "allocator_cagr_delta_pct_points": eth_allocator_cagr_delta,
                "eth_avg_weight_pct": round(eth_stats["avg_weight_pct"], 3),
                "eth_max_weight_pct": round(eth_stats["max_weight_pct"], 3),
                "eth_days_held": eth_stats["days_held"],
                "eth_pct_days_held": round(eth_stats["pct_days_held"], 3),
                "eth_final_weight_pct": round(eth_stats["final_weight_pct"], 3),
                "eth_used": eth_used,
                "eth_dominates": eth_dominates,
                "final_classification": eth_classification,
                "final_verdict": eth_verdict,
            },
            {
                "comparison": f"{oil_eth_name} vs {baseline_name}",
                "added_asset": "USO + ETH-USD",
                "baseline_overlay_cagr_pct": _safe_float(base_overlay, "cagr_pct"),
                "expanded_overlay_cagr_pct": _safe_float(
                    oil_eth_overlay,
                    "cagr_pct",
                ),
                "overlay_cagr_delta_pct_points": oil_eth_overlay_cagr_delta,
                "baseline_overlay_calmar": _safe_float(base_overlay, "calmar"),
                "expanded_overlay_calmar": _safe_float(oil_eth_overlay, "calmar"),
                "overlay_calmar_delta": oil_eth_overlay_calmar_delta,
                "baseline_overlay_max_drawdown_pct": _safe_float(
                    base_overlay,
                    "max_drawdown_pct",
                ),
                "expanded_overlay_max_drawdown_pct": _safe_float(
                    oil_eth_overlay,
                    "max_drawdown_pct",
                ),
                "overlay_drawdown_delta_pct_points": oil_eth_overlay_drawdown_delta,
                "overlay_volatility_delta_pct_points": (
                    oil_eth_overlay_volatility_delta
                ),
                "allocator_cagr_delta_pct_points": oil_eth_allocator_cagr_delta,
                "eth_avg_weight_pct": round(oil_eth_eth_stats["avg_weight_pct"], 3),
                "eth_max_weight_pct": round(oil_eth_eth_stats["max_weight_pct"], 3),
                "eth_days_held": oil_eth_eth_stats["days_held"],
                "eth_pct_days_held": round(oil_eth_eth_stats["pct_days_held"], 3),
                "eth_final_weight_pct": round(
                    oil_eth_eth_stats["final_weight_pct"],
                    3,
                ),
                "uso_avg_weight_pct": round(oil_eth_uso_stats["avg_weight_pct"], 3),
                "uso_days_held": oil_eth_uso_stats["days_held"],
                "eth_used": oil_eth_eth_stats["avg_weight_pct"] >= 0.5,
                "eth_dominates": (
                    oil_eth_eth_stats["avg_weight_pct"] > 5.0
                    or oil_eth_eth_stats["pct_days_held"] > 25.0
                ),
                "final_classification": oil_eth_classification,
                "final_verdict": (
                    "Combined oil + ETH expansion passed initial gates."
                    if oil_eth_overlay_pass
                    else (
                        "Combined oil + ETH expansion did not improve the overlay "
                        "enough to validate inclusion."
                    )
                ),
            },
        ]
    )


def create_eth_quarantine_diagnostic(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    diagnostic_config = config.get("eth_quarantine_diagnostic", {})

    if not diagnostic_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "allocation_summary": pd.DataFrame(),
            "decision": pd.DataFrame(),
        }

    initial_capital = float(config["initial_capital"])

    baseline_name = str(diagnostic_config.get("baseline_universe_name", "Base"))
    eth_name = str(
        diagnostic_config.get("eth_universe_name", "Base + ETH Quarantine")
    )
    oil_eth_name = str(
        diagnostic_config.get(
            "oil_eth_universe_name",
            "Base + Oil + ETH Quarantine",
        )
    )

    baseline_assets = [
        str(asset).upper() for asset in diagnostic_config["baseline_assets"]
    ]
    eth_assets = [str(asset).upper() for asset in diagnostic_config["eth_assets"]]
    oil_eth_assets = [
        str(asset).upper() for asset in diagnostic_config["oil_eth_assets"]
    ]

    top_n = int(diagnostic_config.get("top_n", 3))
    lookback_months = int(diagnostic_config.get("lookback_months", 12))
    trend_sma_days = int(diagnostic_config.get("trend_sma_days", 200))
    confirmation_days = int(diagnostic_config.get("confirmation_days", 3))
    max_asset_weight = float(diagnostic_config.get("max_asset_weight", 1.0 / top_n))

    group_caps = {
        str(group): float(cap)
        for group, cap in diagnostic_config.get("group_caps", {}).items()
    }
    asset_groups = {
        str(asset).upper(): str(group)
        for asset, group in diagnostic_config.get("asset_groups", {}).items()
    }

    baseline_panel = _build_close_panel(ticker_outputs, baseline_assets)
    eth_panel = _build_close_panel(ticker_outputs, eth_assets)
    oil_eth_panel = _build_close_panel(ticker_outputs, oil_eth_assets)

    common_dates = sorted(
        set(baseline_panel.index)
        .intersection(eth_panel.index)
        .intersection(oil_eth_panel.index)
    )

    if not common_dates:
        raise ValueError("No common dates for ETH quarantine diagnostic.")

    cash_returns = ticker_outputs["SPY"].get("cash_returns")

    baseline_allocator, baseline_allocation = _run_constrained_trend_confirmed_allocator(
        ticker_outputs=ticker_outputs,
        assets=baseline_assets,
        universe_name=baseline_name,
        initial_capital=initial_capital,
        top_n=top_n,
        lookback_months=lookback_months,
        trend_sma_days=trend_sma_days,
        max_asset_weight=max_asset_weight,
        group_caps=group_caps,
        asset_groups=asset_groups,
        cash_returns=cash_returns,
    )
    eth_allocator, eth_allocation = _run_constrained_trend_confirmed_allocator(
        ticker_outputs=ticker_outputs,
        assets=eth_assets,
        universe_name=eth_name,
        initial_capital=initial_capital,
        top_n=top_n,
        lookback_months=lookback_months,
        trend_sma_days=trend_sma_days,
        max_asset_weight=max_asset_weight,
        group_caps=group_caps,
        asset_groups=asset_groups,
        cash_returns=cash_returns,
    )
    oil_eth_allocator, oil_eth_allocation = _run_constrained_trend_confirmed_allocator(
        ticker_outputs=ticker_outputs,
        assets=oil_eth_assets,
        universe_name=oil_eth_name,
        initial_capital=initial_capital,
        top_n=top_n,
        lookback_months=lookback_months,
        trend_sma_days=trend_sma_days,
        max_asset_weight=max_asset_weight,
        group_caps=group_caps,
        asset_groups=asset_groups,
        cash_returns=cash_returns,
    )

    baseline_allocator = baseline_allocator[
        pd.to_datetime(baseline_allocator["date"]).isin(common_dates)
    ].copy()
    eth_allocator = eth_allocator[
        pd.to_datetime(eth_allocator["date"]).isin(common_dates)
    ].copy()
    oil_eth_allocator = oil_eth_allocator[
        pd.to_datetime(oil_eth_allocator["date"]).isin(common_dates)
    ].copy()

    spy_buy_hold = rebase_strategy_result_to_dates(
        result=_get_strategy_result(ticker_outputs, "SPY", "Buy and Hold"),
        dates=common_dates,
        initial_capital=initial_capital,
    )

    baseline_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=spy_buy_hold,
        defensive_result=baseline_allocator,
        initial_capital=initial_capital,
        trend_sma_days=int(
            config.get("regime_switch_overlay", {}).get("trend_sma_days", 200)
        ),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=confirmation_days,
    )
    eth_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=spy_buy_hold,
        defensive_result=eth_allocator,
        initial_capital=initial_capital,
        trend_sma_days=int(
            config.get("regime_switch_overlay", {}).get("trend_sma_days", 200)
        ),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=confirmation_days,
    )
    oil_eth_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=spy_buy_hold,
        defensive_result=oil_eth_allocator,
        initial_capital=initial_capital,
        trend_sma_days=int(
            config.get("regime_switch_overlay", {}).get("trend_sma_days", 200)
        ),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=confirmation_days,
    )

    results = {
        f"{baseline_name} Allocator": baseline_allocator,
        f"{eth_name} Allocator": eth_allocator,
        f"{oil_eth_name} Allocator": oil_eth_allocator,
        f"{baseline_name} 3D Overlay": baseline_overlay,
        f"{eth_name} 3D Overlay": eth_overlay,
        f"{oil_eth_name} 3D Overlay": oil_eth_overlay,
        "SPY Buy and Hold": spy_buy_hold,
    }

    metrics = _create_metric_rows(results, initial_capital=initial_capital)

    allocation_summary = pd.concat(
        [baseline_allocation, eth_allocation, oil_eth_allocation],
        ignore_index=True,
    )

    decision = _create_decision(
        metrics=metrics,
        allocation_summary=allocation_summary,
        baseline_name=baseline_name,
        eth_name=eth_name,
        oil_eth_name=oil_eth_name,
    )

    return {
        "metrics": metrics,
        "allocation_summary": allocation_summary,
        "decision": decision,
    }


def write_eth_quarantine_diagnostic_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    allocation_summary = outputs.get("allocation_summary", pd.DataFrame())
    decision = outputs.get("decision", pd.DataFrame())

    content = f"""# ETH Quarantine Diagnostic

This report tests whether ETH adds tactical value under a strict crypto exposure cap.

## Scope

ETH is not treated as a normal ETF.

It is quarantined because it has:

- shorter history,
- 24/7 trading,
- extreme volatility,
- crypto-specific regime behaviour,
- major selection bias.

## Decision

{decision.to_markdown(index=False) if not decision.empty else "No decision available."}

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Allocation Summary

{allocation_summary.to_markdown(index=False) if not allocation_summary.empty else "No allocation summary available."}

## Interpretation Notes

- ETH is capped through the `crypto` group cap.
- A return improvement is not enough.
- ETH must improve Calmar without materially worsening drawdown or volatility.
- If ETH dominates allocation behaviour, reject or tighten the cap.
- This diagnostic uses the common ETH-era sample, so it should not be compared casually with the longer ETF-only results.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_eth_quarantine_diagnostic(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_eth_quarantine_diagnostic(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    allocation_summary = outputs["allocation_summary"]
    decision = outputs["decision"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "eth_quarantine_diagnostic_metrics.csv"
    allocation_path = reports_dir / "eth_quarantine_diagnostic_allocation_summary.csv"
    decision_path = reports_dir / "eth_quarantine_diagnostic_decision.csv"
    markdown_path = reports_dir / "eth_quarantine_diagnostic.md"

    metrics.to_csv(metrics_path, index=False)
    allocation_summary.to_csv(allocation_path, index=False)
    decision.to_csv(decision_path, index=False)

    write_eth_quarantine_diagnostic_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nETH quarantine diagnostic metrics:")
    print(metrics.to_string(index=False))

    print("\nETH quarantine diagnostic decision:")
    print(decision.to_string(index=False))

    print(f"\nSaved ETH quarantine diagnostic metrics to: {metrics_path}")
    print(f"Saved ETH quarantine diagnostic allocation summary to: {allocation_path}")
    print(f"Saved ETH quarantine diagnostic decision to: {decision_path}")
    print(f"Saved ETH quarantine diagnostic markdown to: {markdown_path}")

    return outputs