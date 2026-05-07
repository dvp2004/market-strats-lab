from __future__ import annotations

from pathlib import Path

import pandas as pd


def _get_metric_row(metrics: pd.DataFrame, strategy: str) -> pd.Series:
    row = metrics[metrics["strategy"] == strategy]

    if row.empty:
        available = sorted(metrics["strategy"].unique())
        raise ValueError(
            f"Strategy '{strategy}' not found in metrics. Available: {available}"
        )

    return row.iloc[0]


def create_candidate_portfolio_decision_report(
    metrics: pd.DataFrame,
    portfolio_strategy: str,
    benchmark_strategy: str,
    min_cagr_pct: float,
    max_drawdown_floor_pct: float,
    require_calmar_above_benchmark: bool = True,
) -> pd.DataFrame:
    """
    Create a pass/fail decision report for a candidate portfolio.

    This prevents after-the-fact interpretation.

    For this project, the key question is:
    Does the candidate portfolio improve the risk-adjusted outcome versus
    SPY 12M momentum enough to justify lower SPY concentration?
    """
    if metrics.empty:
        return pd.DataFrame()

    portfolio = _get_metric_row(metrics, portfolio_strategy)
    benchmark = _get_metric_row(metrics, benchmark_strategy)

    portfolio_cagr = float(portfolio["cagr_pct"])
    benchmark_cagr = float(benchmark["cagr_pct"])

    portfolio_drawdown = float(portfolio["max_drawdown_pct"])
    benchmark_drawdown = float(benchmark["max_drawdown_pct"])

    portfolio_calmar = float(portfolio["calmar"])
    benchmark_calmar = float(benchmark["calmar"])

    cagr_gate_pass = portfolio_cagr >= min_cagr_pct
    drawdown_gate_pass = portfolio_drawdown >= max_drawdown_floor_pct

    if require_calmar_above_benchmark:
        calmar_gate_pass = portfolio_calmar > benchmark_calmar
    else:
        calmar_gate_pass = True

    overall_pass = cagr_gate_pass and drawdown_gate_pass and calmar_gate_pass

    if overall_pass:
        verdict = (
            "Pass: candidate portfolio improves the return/drawdown trade-off "
            "enough to justify further development."
        )
    else:
        verdict = (
            "Fail: candidate portfolio does not clear the pre-declared gates. "
            "Treat as defensive or reject for wealth-growth use."
        )

    output = pd.DataFrame(
        [
            {
                "portfolio_strategy": portfolio_strategy,
                "benchmark_strategy": benchmark_strategy,
                "portfolio_cagr_pct": portfolio_cagr,
                "benchmark_cagr_pct": benchmark_cagr,
                "cagr_delta_vs_benchmark_pct_points": (
                    portfolio_cagr - benchmark_cagr
                ),
                "min_required_cagr_pct": min_cagr_pct,
                "cagr_gate_pass": cagr_gate_pass,
                "portfolio_max_drawdown_pct": portfolio_drawdown,
                "benchmark_max_drawdown_pct": benchmark_drawdown,
                "drawdown_improvement_vs_benchmark_pct_points": (
                    portfolio_drawdown - benchmark_drawdown
                ),
                "max_drawdown_floor_pct": max_drawdown_floor_pct,
                "drawdown_gate_pass": drawdown_gate_pass,
                "portfolio_calmar": portfolio_calmar,
                "benchmark_calmar": benchmark_calmar,
                "calmar_delta_vs_benchmark": portfolio_calmar - benchmark_calmar,
                "calmar_gate_pass": calmar_gate_pass,
                "overall_pass": overall_pass,
                "verdict": verdict,
            }
        ]
    )

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output


def write_candidate_portfolio_decision_markdown(
    decision_report: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if decision_report.empty:
        output_path.write_text(
            "# Candidate Portfolio Decision Report\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    table = decision_report.to_markdown(index=False)
    verdict = str(decision_report.iloc[0]["verdict"])

    content = f"""# Candidate Portfolio Decision Report

This report applies pre-declared gates to the candidate portfolio.

It is designed to prevent after-the-fact rationalisation.

## Decision Table

{table}

## Verdict

{verdict}

## Interpretation Rules

- The candidate portfolio should be judged against SPY 12M momentum over the same common period.
- CAGR must clear the minimum pre-declared threshold.
- Max drawdown must clear the pre-declared drawdown floor.
- Calmar should exceed the benchmark if the objective is return per unit of drawdown.
- If the portfolio fails the gates, it may still be useful defensively, but it should not be treated as a wealth-growth replacement.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path