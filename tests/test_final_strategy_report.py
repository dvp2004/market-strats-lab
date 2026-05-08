from pathlib import Path

import pandas as pd

from market_strats.analysis.final_strategy_report import (
    create_final_strategy_decision_report,
    write_final_strategy_decision_markdown,
)


def test_create_final_strategy_decision_report(tmp_path: Path):
    reports_dir = tmp_path

    pd.DataFrame(
        {
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "start_date": ["2000-01-01", "2000-01-01"],
            "end_date": ["2020-01-01", "2020-01-01"],
            "end_value": [100_000, 90_000],
            "cagr_pct": [10.0, 9.5],
            "calmar": [0.2, 0.3],
            "max_drawdown_pct": [-50.0, -30.0],
        }
    ).to_csv(reports_dir / "SPY_strategy_comparison_metrics.csv", index=False)

    pd.DataFrame(
        {
            "strategy": [
                "60/40 Annual Rebalanced Core-Satellite SPY B&H + 12M Momentum"
            ],
            "start_date": ["2000-01-01"],
            "end_date": ["2020-01-01"],
            "end_value": [110_000],
            "cagr_pct": [10.5],
            "calmar": [0.28],
            "max_drawdown_pct": [-38.0],
        }
    ).to_csv(reports_dir / "SPY_core_satellite_diagnostic.csv", index=False)

    for filename, strategy in [
        (
            "candidate_portfolio_validated_signal_portfolio_metrics.csv",
            "Validated Signal Portfolio",
        ),
        (
            "candidate_portfolio_growth_biased_signal_portfolio_metrics.csv",
            "Growth Biased Signal Portfolio",
        ),
        (
            "candidate_portfolio_spy_dominant_signal_portfolio_metrics.csv",
            "SPY Dominant Signal Portfolio",
        ),
    ]:
        pd.DataFrame(
            {
                "strategy": [strategy],
                "start_date": ["2003-01-01"],
                "end_date": ["2020-01-01"],
                "end_value": [70_000],
                "cagr_pct": [8.5],
                "calmar": [0.35],
                "max_drawdown_pct": [-25.0],
            }
        ).to_csv(reports_dir / filename, index=False)

    result = create_final_strategy_decision_report(reports_dir=reports_dir)

    assert len(result) == 6
    assert "final_label" in result.columns
    assert "final_verdict" in result.columns


def test_write_final_strategy_decision_markdown(tmp_path: Path):
    report = pd.DataFrame(
        {
            "strategy": ["Test Strategy"],
            "final_label": ["Test Label"],
            "cagr_pct": [10.0],
            "calmar": [0.4],
            "max_drawdown_pct": [-25.0],
            "final_verdict": ["Test verdict."],
        }
    )

    output_path = tmp_path / "final_report.md"

    write_final_strategy_decision_markdown(report, output_path)

    assert output_path.exists()
    assert "Final Strategy Decision Report" in output_path.read_text()