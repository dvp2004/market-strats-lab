from pathlib import Path

import pandas as pd

from market_strats.analysis.relative_momentum_decision_report import (
    create_relative_momentum_variant_decision_report,
    write_relative_momentum_variant_decision_markdown,
)


def _write_metrics_file(path: Path, strategy_name: str) -> None:
    pd.DataFrame(
        {
            "strategy": [
                strategy_name,
                "SPY Buy and Hold",
                "SPY 12-Month Absolute Momentum",
            ],
            "start_date": ["2006-01-01", "2006-01-01", "2006-01-01"],
            "end_date": ["2020-01-01", "2020-01-01", "2020-01-01"],
            "end_value": [50_000, 80_000, 60_000],
            "cagr_pct": [8.0, 10.0, 9.0],
            "calmar": [0.3, 0.2, 0.25],
            "volatility_pct": [15.0, 19.0, 14.0],
            "sharpe": [0.6, 0.65, 0.7],
            "sortino": [0.7, 0.75, 0.8],
            "max_drawdown_pct": [-28.0, -55.0, -33.0],
            "worst_month_pct": [-8.0, -16.0, -12.0],
            "exposure_time_pct": [90.0, 100.0, 80.0],
            "trade_count": [100, 1, 20],
        }
    ).to_csv(path, index=False)


def test_create_relative_momentum_variant_decision_report(tmp_path: Path):
    files = [
        (
            "relative_momentum_top_3_equal_weight_relative_momentum_allocator_metrics.csv",
            "Top 3 Equal Weight Relative Momentum Allocator",
        ),
        (
            "relative_momentum_top_3_inverse_volatility_relative_momentum_allocator_metrics.csv",
            "Top 3 Inverse Volatility Relative Momentum Allocator",
        ),
        (
            "relative_momentum_top_3_equal_weight_trend_confirmed_relative_momentum_allocator_metrics.csv",
            "Top 3 Equal Weight Trend Confirmed Relative Momentum Allocator",
        ),
        (
            "relative_momentum_top_3_inverse_volatility_trend_confirmed_relative_momentum_allocator_metrics.csv",
            "Top 3 Inverse Volatility Trend Confirmed Relative Momentum Allocator",
        ),
        (
            "relative_momentum_top_3_equal_weight_trend_confirmed_constrained_relative_momentum_allocator_metrics.csv",
            "Top 3 Equal Weight Trend Confirmed Constrained Relative Momentum Allocator",
        ),
    ]

    for filename, strategy in files:
        _write_metrics_file(tmp_path / filename, strategy)

    report = create_relative_momentum_variant_decision_report(reports_dir=tmp_path)

    assert len(report) == 7
    assert "classification" in report.columns
    assert "verdict" in report.columns
    assert "calmar_delta_vs_spy_12m" in report.columns


def test_write_relative_momentum_variant_decision_markdown(tmp_path: Path):
    report = pd.DataFrame(
        {
            "strategy": ["Test Strategy"],
            "classification": ["Test Classification"],
            "cagr_pct": [9.0],
            "calmar": [0.3],
            "max_drawdown_pct": [-30.0],
            "verdict": ["Test verdict."],
        }
    )

    output_path = tmp_path / "relative_momentum_variant_decision_report.md"

    write_relative_momentum_variant_decision_markdown(report, output_path)

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Relative Momentum Variant Decision Report" in text
    assert "Decision Table" in text