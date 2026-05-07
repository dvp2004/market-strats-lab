from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.plots import plot_drawdowns, plot_equity_curves
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.fixed_weight_portfolio import (
    get_common_strategy_dates,
    rebase_strategy_result_to_dates,
    run_independent_weighted_portfolio,
)
from market_strats.analysis.candidate_portfolio_attribution import (
    create_candidate_portfolio_sleeve_attribution,
    create_candidate_portfolio_sleeve_summary,
    write_candidate_portfolio_attribution_markdown,
)

def _safe_filename(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _get_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    strategy: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"Ticker {ticker} not found in ticker outputs")

    strategy_results = ticker_outputs[ticker].get("strategy_results")

    if strategy_results is None:
        raise ValueError("ticker_outputs is missing strategy_results")

    if strategy not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"Strategy {strategy} not found for {ticker}. Available: {available}"
        )

    return strategy_results[strategy]


def run_candidate_portfolio_report(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: Path,
) -> dict[str, pd.DataFrame]:
    candidate_config = config.get("candidate_portfolio", {})

    if not candidate_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "rolling_summary": pd.DataFrame(),
            "portfolio_result": pd.DataFrame(),
        }

    portfolio_name = str(candidate_config["name"])
    initial_capital = float(config["initial_capital"])
    components = candidate_config["components"]

    component_results: dict[str, pd.DataFrame] = {}
    weights: dict[str, float] = {}

    for component in components:
        ticker = str(component["ticker"]).upper()
        strategy = str(component["strategy"])
        weight = float(component["weight"])
        component_name = f"{ticker} {strategy}"

        component_results[component_name] = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=ticker,
            strategy=strategy,
        )
        weights[component_name] = weight

    portfolio_result = run_independent_weighted_portfolio(
        component_results=component_results,
        weights=weights,
        initial_capital=initial_capital,
        portfolio_name=portfolio_name,
    )

    common_dates = get_common_strategy_dates(component_results)

    sleeve_attribution = create_candidate_portfolio_sleeve_attribution(
        component_results=component_results,
        weights=weights,
        portfolio_result=portfolio_result,
        common_dates=common_dates,
        initial_capital=initial_capital,
    )
    sleeve_summary = create_candidate_portfolio_sleeve_summary(
        attribution=sleeve_attribution,
        portfolio_result=portfolio_result,
        initial_capital=initial_capital,
    )

    benchmark_ticker = str(candidate_config["benchmark_ticker"]).upper()
    benchmark_strategies = [
        str(strategy) for strategy in candidate_config["benchmark_strategies"]
    ]

    comparison_results: dict[str, pd.DataFrame] = {
        portfolio_name: portfolio_result,
    }

    for benchmark_strategy in benchmark_strategies:
        benchmark_result = _get_strategy_result(
            ticker_outputs=ticker_outputs,
            ticker=benchmark_ticker,
            strategy=benchmark_strategy,
        )

        comparison_name = f"{benchmark_ticker} {benchmark_strategy}"
        comparison_results[comparison_name] = rebase_strategy_result_to_dates(
            result=benchmark_result,
            dates=common_dates,
            initial_capital=initial_capital,
        )

    metrics = pd.DataFrame(
        [
            calculate_metrics(result, strategy_name)
            for strategy_name, result in comparison_results.items()
        ]
    )

    rolling_metrics = calculate_rolling_window_metrics(comparison_results)
    rolling_summary = create_rolling_summary(rolling_metrics)

    safe_name = _safe_filename(portfolio_name)

    metrics_path = reports_dir / f"candidate_portfolio_{safe_name}_metrics.csv"
    rolling_summary_path = (
        reports_dir / f"candidate_portfolio_{safe_name}_rolling_summary.csv"
    )
    portfolio_result_path = (
        reports_dir / f"candidate_portfolio_{safe_name}_daily_result.csv"
    )
    markdown_path = reports_dir / f"candidate_portfolio_{safe_name}.md"
    equity_plot_path = reports_dir / f"candidate_portfolio_{safe_name}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"candidate_portfolio_{safe_name}_drawdowns.png"

    sleeve_attribution_path = (
        reports_dir / f"candidate_portfolio_{safe_name}_sleeve_attribution.csv"
    )
    sleeve_summary_path = (
        reports_dir / f"candidate_portfolio_{safe_name}_sleeve_summary.csv"
    )
    sleeve_attribution_markdown_path = (
        reports_dir / f"candidate_portfolio_{safe_name}_sleeve_attribution.md"
    )

    metrics.to_csv(metrics_path, index=False)
    rolling_summary.to_csv(rolling_summary_path, index=False)
    portfolio_result.to_csv(portfolio_result_path, index=False)

    sleeve_attribution.to_csv(sleeve_attribution_path, index=False)
    sleeve_summary.to_csv(sleeve_summary_path, index=False)
    write_candidate_portfolio_attribution_markdown(
        attribution=sleeve_attribution,
        summary=sleeve_summary,
        output_path=sleeve_attribution_markdown_path,
    )

    plot_equity_curves(comparison_results, equity_plot_path)
    plot_drawdowns(comparison_results, drawdown_plot_path)

    write_candidate_portfolio_markdown(
        portfolio_name=portfolio_name,
        components=components,
        metrics=metrics,
        rolling_summary=rolling_summary,
        output_path=markdown_path,
        equity_plot_path=equity_plot_path,
        drawdown_plot_path=drawdown_plot_path,
    )

    print("\nCandidate portfolio comparison:")
    print(metrics.to_string(index=False))

    print("\nCandidate portfolio rolling summary:")
    print(rolling_summary.to_string(index=False))

    print("\nCandidate portfolio sleeve attribution:")
    print(sleeve_attribution.to_string(index=False))

    print("\nCandidate portfolio sleeve summary:")
    print(sleeve_summary.to_string(index=False))

    print(f"\nSaved candidate portfolio metrics to: {metrics_path}")
    print(f"Saved candidate portfolio rolling summary to: {rolling_summary_path}")
    print(f"Saved candidate portfolio daily result to: {portfolio_result_path}")
    print(f"Saved candidate portfolio report to: {markdown_path}")
    print(f"Saved candidate portfolio sleeve attribution to: {sleeve_attribution_path}")
    print(f"Saved candidate portfolio sleeve summary to: {sleeve_summary_path}")
    print("Saved candidate portfolio sleeve attribution report to: "f"{sleeve_attribution_markdown_path}")
    print(f"Saved candidate portfolio equity chart to: {equity_plot_path}")
    print(f"Saved candidate portfolio drawdown chart to: {drawdown_plot_path}")

    return {
        "metrics": metrics,
        "rolling_summary": rolling_summary,
        "portfolio_result": portfolio_result,
        "sleeve_attribution": sleeve_attribution,
        "sleeve_summary": sleeve_summary,
    }


def write_candidate_portfolio_markdown(
    portfolio_name: str,
    components: list[dict],
    metrics: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    output_path: str | Path,
    equity_plot_path: str | Path,
    drawdown_plot_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    component_rows = []

    for component in components:
        component_rows.append(
            {
                "ticker": component["ticker"],
                "strategy": component["strategy"],
                "weight": component["weight"],
            }
        )

    components_df = pd.DataFrame(component_rows)

    metrics_table = metrics.to_markdown(index=False)
    rolling_table = (
        rolling_summary.to_markdown(index=False)
        if not rolling_summary.empty
        else "No rolling summary available."
    )

    content = f"""# Candidate Portfolio: {portfolio_name}

This report tests a fixed-weight portfolio built from validated strategy components.

This is not an optimisation exercise. The purpose is to test whether combining validated signals improves portfolio-level outcomes versus SPY-only benchmarks over the same common date range.

## Components

{components_df.to_markdown(index=False)}

## Full-Period Metrics

{metrics_table}

## Rolling-Window Summary

{rolling_table}

## Charts

![Candidate Portfolio Equity Curves]({Path(equity_plot_path).as_posix()})

![Candidate Portfolio Drawdowns]({Path(drawdown_plot_path).as_posix()})

## Interpretation Notes

- This first version uses independent sleeves with no rebalancing after inception.
- The comparison period is the common overlapping history across all components.
- If the portfolio underperforms SPY-only benchmarks, diversification may still reduce drawdown but fail as a wealth improvement.
- If it improves bad-window behaviour with acceptable CAGR sacrifice, it may be useful as a diversified architecture.
- Future tests can add annual rebalancing only after the independent-sleeve version is understood.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path