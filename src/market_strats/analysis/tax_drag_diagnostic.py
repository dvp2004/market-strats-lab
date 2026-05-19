from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)
from market_strats.analysis.metrics import calculate_metrics


def _phase8a_config(config: dict) -> dict:
    return config.get("phase8a_tax_drag_diagnostic", {})


def _get_spy_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    strategy_name: str,
) -> pd.DataFrame:
    spy_output = ticker_outputs.get("SPY")

    if spy_output is None:
        raise ValueError("SPY output missing from ticker_outputs")

    strategy_results = spy_output.get("strategy_results")

    if not isinstance(strategy_results, dict):
        raise ValueError("SPY strategy_results missing or invalid")

    if strategy_name not in strategy_results:
        raise ValueError(
            f"SPY strategy result missing: {strategy_name}. "
            f"Available: {sorted(strategy_results)}"
        )

    result = strategy_results[strategy_name].copy()
    result["date"] = pd.to_datetime(result["date"])
    return result.sort_values("date").reset_index(drop=True)


def _filter_period(
    result: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    output = result.copy()
    output["date"] = pd.to_datetime(output["date"])
    output = output[
        (output["date"] >= pd.Timestamp(start_date))
        & (output["date"] <= pd.Timestamp(end_date))
    ].copy()
    return output.sort_values("date").reset_index(drop=True)


def _normalise_strategy_result(
    result: pd.DataFrame,
    strategy_label: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    output = _filter_period(
        result=result,
        start_date=start_date,
        end_date=end_date,
    )

    required = {"date", "strategy_return"}
    missing = required - set(output.columns)

    if missing:
        raise ValueError(f"{strategy_label} missing columns: {sorted(missing)}")

    output["strategy_return"] = pd.to_numeric(
        output["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    if "turnover" in output.columns:
        output["taxable_turnover"] = pd.to_numeric(
            output["turnover"],
            errors="coerce",
        ).fillna(0.0)
    elif "overlay_turnover" in output.columns:
        output["taxable_turnover"] = pd.to_numeric(
            output["overlay_turnover"],
            errors="coerce",
        ).fillna(0.0)
    else:
        output["taxable_turnover"] = 0.0

    if "position" in output.columns:
        output["position"] = pd.to_numeric(
            output["position"],
            errors="coerce",
        ).fillna(1.0)
    elif "target_defensive_weight" in output.columns:
        output["position"] = 1.0
    else:
        output["position"] = 1.0

    return output[
        [
            "date",
            "strategy_return",
            "position",
            "taxable_turnover",
        ]
    ].copy()


def _apply_tax_drag(
    result: pd.DataFrame,
    tax_rate: float,
    taxable_turnover_multiplier: float,
    initial_capital: float,
) -> pd.DataFrame:
    output = result.copy()

    output["taxable_turnover"] = pd.to_numeric(
        output["taxable_turnover"],
        errors="coerce",
    ).fillna(0.0)

    output["taxable_turnover"] = output["taxable_turnover"].clip(lower=0.0)

    realised_gain_proxy = (
        output["strategy_return"].clip(lower=0.0)
        * output["taxable_turnover"]
        * taxable_turnover_multiplier
    )

    output["tax_cost_return"] = realised_gain_proxy * tax_rate
    output["pre_tax_strategy_return"] = output["strategy_return"]
    output["strategy_return"] = (
        output["pre_tax_strategy_return"] - output["tax_cost_return"]
    )

    output["turnover"] = output["taxable_turnover"]
    output["equity"] = initial_capital * (1.0 + output["strategy_return"]).cumprod()

    return output[
        [
            "date",
            "strategy_return",
            "pre_tax_strategy_return",
            "tax_cost_return",
            "position",
            "turnover",
            "equity",
        ]
    ].copy()


def _safe_metric(metrics: dict, key: str) -> float:
    value = metrics.get(key, np.nan)

    if pd.isna(value):
        return np.nan

    return float(value)


def _calculate_tax_adjusted_metric_row(
    strategy_label: str,
    tax_rate: float,
    result: pd.DataFrame,
) -> dict:
    metrics = calculate_metrics(
        result=result,
        strategy_name=f"{strategy_label} tax_rate_{tax_rate:.2f}",
    )

    return {
        "strategy": strategy_label,
        "tax_rate": tax_rate,
        "start_date": result["date"].min().date().isoformat(),
        "end_date": result["date"].max().date().isoformat(),
        "end_value": round(_safe_metric(metrics, "end_value"), 2),
        "cagr_pct": round(_safe_metric(metrics, "cagr_pct"), 4),
        "calmar": round(_safe_metric(metrics, "calmar"), 4),
        "max_drawdown_pct": round(_safe_metric(metrics, "max_drawdown_pct"), 4),
        "volatility_pct": round(_safe_metric(metrics, "volatility_pct"), 4),
        "sharpe": round(_safe_metric(metrics, "sharpe"), 4),
        "sortino": round(_safe_metric(metrics, "sortino"), 4),
        "trade_count": int(_safe_metric(metrics, "trade_count")),
        "total_tax_cost_return_pct": round(
            float(result["tax_cost_return"].sum() * 100.0),
            4,
        ),
        "average_annual_tax_drag_pct_points": round(
            float(result["tax_cost_return"].mean() * 252.0 * 100.0),
            4,
        ),
    }


def _create_tax_adjusted_results(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase8a_config(config)

    start_date = str(phase_config.get("pinned_start_date", "2006-04-28"))
    end_date = str(phase_config.get("pinned_end_date", "2026-05-01"))
    initial_capital = float(phase_config.get("initial_capital", 10000.0))
    taxable_turnover_multiplier = float(
        phase_config.get("taxable_turnover_multiplier", 1.0)
    )

    tax_rates = [float(value) for value in phase_config.get("tax_rates", [0.0, 0.2])]

    candidate_result = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    buy_hold_result = _get_spy_strategy_result(
        ticker_outputs=ticker_outputs,
        strategy_name="Buy and Hold",
    )
    spy_12m_result = _get_spy_strategy_result(
        ticker_outputs=ticker_outputs,
        strategy_name="12-Month Absolute Momentum",
    )

    base_results = {
        "final_candidate": _normalise_strategy_result(
            result=candidate_result,
            strategy_label="final_candidate",
            start_date=start_date,
            end_date=end_date,
        ),
        "spy_buy_hold": _normalise_strategy_result(
            result=buy_hold_result,
            strategy_label="spy_buy_hold",
            start_date=start_date,
            end_date=end_date,
        ),
        "spy_12m_momentum": _normalise_strategy_result(
            result=spy_12m_result,
            strategy_label="spy_12m_momentum",
            start_date=start_date,
            end_date=end_date,
        ),
    }

    rows: list[dict] = []
    adjusted_results: list[pd.DataFrame] = []

    for strategy_label, result in base_results.items():
        for tax_rate in tax_rates:
            tax_adjusted = _apply_tax_drag(
                result=result,
                tax_rate=tax_rate,
                taxable_turnover_multiplier=taxable_turnover_multiplier,
                initial_capital=initial_capital,
            )

            row = _calculate_tax_adjusted_metric_row(
                strategy_label=strategy_label,
                tax_rate=tax_rate,
                result=tax_adjusted,
            )
            rows.append(row)

            stored = tax_adjusted.copy()
            stored.insert(0, "strategy", strategy_label)
            stored.insert(1, "tax_rate", tax_rate)
            adjusted_results.append(stored)

    metrics = pd.DataFrame(rows)
    daily = (
        pd.concat(adjusted_results, ignore_index=True)
        if adjusted_results
        else pd.DataFrame()
    )

    return {
        "metrics": metrics,
        "daily": daily,
    }


def _create_tax_drag_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for tax_rate, group in metrics.groupby("tax_rate", sort=True):
        by_strategy = group.set_index("strategy")

        candidate = by_strategy.loc["final_candidate"]
        buy_hold = by_strategy.loc["spy_buy_hold"]
        spy_12m = by_strategy.loc["spy_12m_momentum"]

        rows.append(
            {
                "tax_rate": tax_rate,
                "candidate_cagr_pct": candidate["cagr_pct"],
                "spy_buy_hold_cagr_pct": buy_hold["cagr_pct"],
                "spy_12m_cagr_pct": spy_12m["cagr_pct"],
                "candidate_minus_buy_hold_cagr_pct_points": round(
                    float(candidate["cagr_pct"] - buy_hold["cagr_pct"]),
                    4,
                ),
                "candidate_minus_spy_12m_cagr_pct_points": round(
                    float(candidate["cagr_pct"] - spy_12m["cagr_pct"]),
                    4,
                ),
                "candidate_calmar": candidate["calmar"],
                "spy_buy_hold_calmar": buy_hold["calmar"],
                "spy_12m_calmar": spy_12m["calmar"],
                "candidate_minus_buy_hold_calmar": round(
                    float(candidate["calmar"] - buy_hold["calmar"]),
                    4,
                ),
                "candidate_minus_spy_12m_calmar": round(
                    float(candidate["calmar"] - spy_12m["calmar"]),
                    4,
                ),
                "candidate_max_drawdown_pct": candidate["max_drawdown_pct"],
                "spy_buy_hold_max_drawdown_pct": buy_hold["max_drawdown_pct"],
                "spy_12m_max_drawdown_pct": spy_12m["max_drawdown_pct"],
                "candidate_minus_buy_hold_drawdown_pct_points": round(
                    float(
                        candidate["max_drawdown_pct"]
                        - buy_hold["max_drawdown_pct"]
                    ),
                    4,
                ),
                "candidate_minus_spy_12m_drawdown_pct_points": round(
                    float(
                        candidate["max_drawdown_pct"]
                        - spy_12m["max_drawdown_pct"]
                    ),
                    4,
                ),
                "candidate_average_annual_tax_drag_pct_points": candidate[
                    "average_annual_tax_drag_pct_points"
                ],
                "spy_12m_average_annual_tax_drag_pct_points": spy_12m[
                    "average_annual_tax_drag_pct_points"
                ],
                "buy_hold_average_annual_tax_drag_pct_points": buy_hold[
                    "average_annual_tax_drag_pct_points"
                ],
            }
        )

    return pd.DataFrame(rows)


def _create_tax_drag_gate_report(
    summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = _phase8a_config(config)

    benchmark_tax_rate = float(phase_config.get("benchmark_tax_rate", 0.20))

    matching = summary[np.isclose(summary["tax_rate"], benchmark_tax_rate)]

    if matching.empty:
        raise ValueError(
            f"Benchmark tax rate {benchmark_tax_rate} not found in tax summary"
        )

    row = matching.iloc[0]

    spy_12m_cagr_gate = float(
        phase_config.get("min_after_tax_candidate_cagr_minus_spy_12m_pct_points", 0.0)
    )
    spy_12m_calmar_gate = float(
        phase_config.get("min_after_tax_candidate_calmar_minus_spy_12m", 0.0)
    )
    spy_12m_drawdown_gate = float(
        phase_config.get(
            "min_after_tax_candidate_drawdown_minus_spy_12m_pct_points",
            0.0,
        )
    )
    buy_hold_cagr_max = float(
        phase_config.get(
            "max_allowed_after_tax_candidate_cagr_minus_buy_hold_pct_points",
            0.0,
        )
    )
    buy_hold_calmar_gate = float(
        phase_config.get("min_after_tax_candidate_calmar_minus_buy_hold", 0.0)
    )
    buy_hold_drawdown_gate = float(
        phase_config.get(
            "min_after_tax_candidate_drawdown_minus_buy_hold_pct_points",
            0.0,
        )
    )

    checks = [
        {
            "claim": "Candidate beats SPY 12M after tax on CAGR.",
            "value": float(row["candidate_minus_spy_12m_cagr_pct_points"]),
            "threshold": spy_12m_cagr_gate,
            "operator": ">=",
        },
        {
            "claim": "Candidate beats SPY 12M after tax on Calmar.",
            "value": float(row["candidate_minus_spy_12m_calmar"]),
            "threshold": spy_12m_calmar_gate,
            "operator": ">=",
        },
        {
            "claim": "Candidate has better after-tax max drawdown than SPY 12M.",
            "value": float(row["candidate_minus_spy_12m_drawdown_pct_points"]),
            "threshold": spy_12m_drawdown_gate,
            "operator": ">=",
        },
        {
            "claim": "Candidate is not being promoted as after-tax raw-CAGR winner over Buy & Hold.",
            "value": float(row["candidate_minus_buy_hold_cagr_pct_points"]),
            "threshold": buy_hold_cagr_max,
            "operator": "<=",
        },
        {
            "claim": "Candidate beats Buy & Hold after tax on Calmar.",
            "value": float(row["candidate_minus_buy_hold_calmar"]),
            "threshold": buy_hold_calmar_gate,
            "operator": ">=",
        },
        {
            "claim": "Candidate has better after-tax max drawdown than Buy & Hold.",
            "value": float(row["candidate_minus_buy_hold_drawdown_pct_points"]),
            "threshold": buy_hold_drawdown_gate,
            "operator": ">=",
        },
    ]

    rows: list[dict] = []

    for check in checks:
        if check["operator"] == ">=":
            passed = check["value"] >= check["threshold"]
        elif check["operator"] == "<=":
            passed = check["value"] <= check["threshold"]
        else:
            raise ValueError(f"Unsupported operator: {check['operator']}")

        rows.append(
            {
                "tax_rate": benchmark_tax_rate,
                "claim": check["claim"],
                "status": "Passed" if passed else "Failed",
                "value": round(check["value"], 4),
                "threshold": check["threshold"],
                "operator": check["operator"],
                "interpretation": (
                    "Tax-drag gate passed."
                    if passed
                    else "Tax-drag gate failed."
                ),
            }
        )

    return pd.DataFrame(rows)


def _create_tax_drag_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    failed = gate_report[gate_report["status"] == "Failed"]

    spy_12m_failed = failed[
        failed["claim"].str.contains("SPY 12M", case=False, na=False)
    ]
    buy_hold_failed = failed[
        failed["claim"].str.contains("Buy & Hold", case=False, na=False)
    ]

    return pd.DataFrame(
        [
            {
                "claim": "Final candidate survives the simplified tax-drag diagnostic versus SPY 12M.",
                "status": "Survived" if spy_12m_failed.empty else "Failed",
                "evidence_quality": "Turnover-based realised-gain tax proxy",
                "interpretation": (
                    "Candidate cleared all after-tax SPY 12M gates."
                    if spy_12m_failed.empty
                    else "Candidate failed at least one after-tax SPY 12M gate."
                ),
            },
            {
                "claim": "Final candidate preserves the project hierarchy versus SPY Buy & Hold after tax.",
                "status": "Survived" if buy_hold_failed.empty else "Review needed",
                "evidence_quality": "After-tax raw-CAGR hierarchy and risk gates",
                "interpretation": (
                    "Candidate preserved buy-and-hold raw-CAGR hierarchy while clearing risk gates."
                    if buy_hold_failed.empty
                    else "At least one buy-and-hold after-tax hierarchy/risk gate failed."
                ),
            },
            {
                "claim": "The simplified tax model is production-grade.",
                "status": "Failed",
                "evidence_quality": "No lot accounting, no jurisdiction-specific tax rules, no wash-sale modelling",
                "interpretation": (
                    "This is a rough research diagnostic only, not a production tax engine."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet" if failed.empty else "No",
                "evidence_quality": "Tax-drag results should be documented before new variants",
                "interpretation": (
                    "Document Phase 8A before adding new strategy variants."
                    if failed.empty
                    else "Document or investigate failed tax-drag gates before adding new variants."
                ),
            },
        ]
    )


def write_tax_drag_markdown(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Phase 8A Tax-Drag Diagnostic

This report applies a simplified turnover-based realised-gain tax drag to the final candidate, SPY Buy & Hold, and SPY 12M Momentum.

This is not a production tax engine. It does not model tax lots, wash-sale rules, dividend taxation, jurisdiction-specific treatment, or investor-specific circumstances.

## Tax-Adjusted Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No tax-adjusted metrics available."}

## Tax-Drag Summary

{summary.to_markdown(index=False) if not summary.empty else "No tax-drag summary available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_tax_drag_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase8a_config(config)

    if not phase_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "daily": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    outputs = _create_tax_adjusted_results(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    summary = _create_tax_drag_summary(outputs["metrics"])
    gate_report = _create_tax_drag_gate_report(
        summary=summary,
        config=config,
    )
    conclusion = _create_tax_drag_conclusion(gate_report)

    return {
        "metrics": outputs["metrics"],
        "daily": outputs["daily"],
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def save_tax_drag_diagnostic(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_tax_drag_diagnostic(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if outputs["conclusion"].empty:
        return outputs

    metrics_path = reports_dir / "phase8a_tax_drag_metrics.csv"
    daily_path = reports_dir / "phase8a_tax_drag_daily_returns.csv"
    summary_path = reports_dir / "phase8a_tax_drag_summary.csv"
    gate_path = reports_dir / "phase8a_tax_drag_gate_report.csv"
    conclusion_path = reports_dir / "phase8a_tax_drag_conclusion.csv"
    markdown_path = reports_dir / "phase8a_tax_drag_diagnostic.md"

    outputs["metrics"].to_csv(metrics_path, index=False)
    outputs["daily"].to_csv(daily_path, index=False)
    outputs["summary"].to_csv(summary_path, index=False)
    outputs["gate_report"].to_csv(gate_path, index=False)
    outputs["conclusion"].to_csv(conclusion_path, index=False)

    write_tax_drag_markdown(
        metrics=outputs["metrics"],
        summary=outputs["summary"],
        gate_report=outputs["gate_report"],
        conclusion=outputs["conclusion"],
        output_path=markdown_path,
    )

    print("\nPhase 8A tax-drag metrics:")
    print(outputs["metrics"].to_string(index=False))

    print("\nPhase 8A tax-drag summary:")
    print(outputs["summary"].to_string(index=False))

    print("\nPhase 8A tax-drag gate report:")
    print(outputs["gate_report"].to_string(index=False))

    print("\nPhase 8A tax-drag conclusion:")
    print(outputs["conclusion"].to_string(index=False))

    print(f"\nSaved Phase 8A tax-drag metrics to: {metrics_path}")
    print(f"Saved Phase 8A tax-drag daily returns to: {daily_path}")
    print(f"Saved Phase 8A tax-drag summary to: {summary_path}")
    print(f"Saved Phase 8A tax-drag gate report to: {gate_path}")
    print(f"Saved Phase 8A tax-drag conclusion to: {conclusion_path}")
    print(f"Saved Phase 8A tax-drag markdown to: {markdown_path}")

    return outputs