import pandas as pd

from market_strats.analysis.candidate_portfolio_decision import (
    create_candidate_portfolio_decision_report,
)


def test_candidate_portfolio_decision_report_passes_when_gates_pass():
    metrics = pd.DataFrame(
        {
            "strategy": ["Portfolio", "Benchmark"],
            "cagr_pct": [9.7, 10.0],
            "max_drawdown_pct": [-25.0, -34.0],
            "calmar": [0.388, 0.294],
        }
    )

    result = create_candidate_portfolio_decision_report(
        metrics=metrics,
        portfolio_strategy="Portfolio",
        benchmark_strategy="Benchmark",
        min_cagr_pct=9.5,
        max_drawdown_floor_pct=-28.0,
        require_calmar_above_benchmark=True,
    )

    assert bool(result.iloc[0]["overall_pass"]) is True
    assert bool(result.iloc[0]["cagr_gate_pass"]) is True
    assert bool(result.iloc[0]["drawdown_gate_pass"]) is True
    assert bool(result.iloc[0]["calmar_gate_pass"]) is True


def test_candidate_portfolio_decision_report_fails_when_cagr_gate_fails():
    metrics = pd.DataFrame(
        {
            "strategy": ["Portfolio", "Benchmark"],
            "cagr_pct": [8.5, 10.0],
            "max_drawdown_pct": [-23.0, -34.0],
            "calmar": [0.369, 0.294],
        }
    )

    result = create_candidate_portfolio_decision_report(
        metrics=metrics,
        portfolio_strategy="Portfolio",
        benchmark_strategy="Benchmark",
        min_cagr_pct=9.5,
        max_drawdown_floor_pct=-28.0,
        require_calmar_above_benchmark=True,
    )

    assert bool(result.iloc[0]["overall_pass"]) is False
    assert bool(result.iloc[0]["cagr_gate_pass"]) is False