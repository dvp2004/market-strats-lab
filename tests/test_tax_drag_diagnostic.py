import pandas as pd
import pytest
from market_strats.analysis.tax_drag_diagnostic import (
    _apply_tax_drag,
    _create_tax_drag_gate_report,
    _create_tax_drag_summary,
)


def test_apply_tax_drag_reduces_positive_return_when_turnover_exists():
    result = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=3),
            "strategy_return": [0.10, -0.05, 0.02],
            "position": [1.0, 1.0, 1.0],
            "taxable_turnover": [1.0, 1.0, 0.5],
        }
    )

    taxed = _apply_tax_drag(
        result=result,
        tax_rate=0.20,
        taxable_turnover_multiplier=1.0,
        initial_capital=10000.0,
    )

    assert taxed.loc[0, "strategy_return"] == 0.08
    assert taxed.loc[1, "strategy_return"] == -0.05
    assert taxed.loc[2, "strategy_return"] == pytest.approx(0.018)
    assert taxed["equity"].iloc[-1] > 0


def test_create_tax_drag_summary_compares_strategies():
    metrics = pd.DataFrame(
        {
            "strategy": [
                "final_candidate",
                "spy_buy_hold",
                "spy_12m_momentum",
            ],
            "tax_rate": [0.20, 0.20, 0.20],
            "cagr_pct": [10.0, 11.0, 9.0],
            "calmar": [0.40, 0.20, 0.30],
            "max_drawdown_pct": [-20.0, -50.0, -30.0],
            "average_annual_tax_drag_pct_points": [0.10, 0.01, 0.05],
        }
    )

    summary = _create_tax_drag_summary(metrics)

    row = summary.iloc[0]

    assert row["tax_rate"] == 0.20
    assert row["candidate_minus_buy_hold_cagr_pct_points"] == -1.0
    assert row["candidate_minus_spy_12m_cagr_pct_points"] == 1.0
    assert row["candidate_minus_buy_hold_calmar"] == 0.2


def test_create_tax_drag_gate_report_passes_expected_hierarchy():
    summary = pd.DataFrame(
        {
            "tax_rate": [0.20],
            "candidate_minus_spy_12m_cagr_pct_points": [1.0],
            "candidate_minus_spy_12m_calmar": [0.1],
            "candidate_minus_spy_12m_drawdown_pct_points": [5.0],
            "candidate_minus_buy_hold_cagr_pct_points": [-1.0],
            "candidate_minus_buy_hold_calmar": [0.2],
            "candidate_minus_buy_hold_drawdown_pct_points": [30.0],
        }
    )

    config = {
        "phase8a_tax_drag_diagnostic": {
            "benchmark_tax_rate": 0.20,
            "min_after_tax_candidate_cagr_minus_spy_12m_pct_points": 0.0,
            "min_after_tax_candidate_calmar_minus_spy_12m": 0.0,
            "min_after_tax_candidate_drawdown_minus_spy_12m_pct_points": 0.0,
            "max_allowed_after_tax_candidate_cagr_minus_buy_hold_pct_points": 0.0,
            "min_after_tax_candidate_calmar_minus_buy_hold": 0.0,
            "min_after_tax_candidate_drawdown_minus_buy_hold_pct_points": 0.0,
        }
    }

    gate_report = _create_tax_drag_gate_report(
        summary=summary,
        config=config,
    )

    assert (gate_report["status"] == "Passed").all()
