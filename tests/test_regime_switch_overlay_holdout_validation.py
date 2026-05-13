import pandas as pd

from market_strats.analysis.regime_switch_overlay_holdout_validation import (
    create_regime_switch_overlay_holdout_validation_report,
    create_regime_switch_overlay_holdout_validation_summary,
)


def make_result(
    dates: pd.DatetimeIndex,
    daily_return: float,
) -> pd.DataFrame:
    returns = [0.0] + [daily_return] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0] * len(dates),
            "cash_position": [0.0] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def test_create_regime_switch_overlay_holdout_validation_report_runs():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    overlay_result = make_result(dates, 0.0006)
    spy_result = make_result(dates, 0.0005)
    allocator_result = make_result(dates, 0.0004)

    overlay_outputs = {
        "overlay_result": overlay_result,
    }

    relative_momentum_outputs = {
        "Allocator": {
            "allocator_result": allocator_result,
        }
    }

    ticker_outputs = {
        "SPY": {
            "strategy_results": {
                "Buy and Hold": spy_result,
                "12-Month Absolute Momentum": spy_result,
            }
        }
    }

    config = {
        "initial_capital": 10_000,
        "regime_switch_overlay": {
            "enabled": True,
            "name": "Test Regime Switch Overlay",
            "benchmarks": [
                {
                    "ticker": "SPY",
                    "strategy": "Buy and Hold",
                },
                {
                    "ticker": "SPY",
                    "strategy": "12-Month Absolute Momentum",
                },
            ],
            "comparison_allocators": ["Allocator"],
        },
        "regime_switch_overlay_holdout_validation": {
            "enabled": True,
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
        },
    }

    report = create_regime_switch_overlay_holdout_validation_report(
        overlay_outputs=overlay_outputs,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not report.empty
    assert {"reference", "holdout"}.issubset(set(report["period"]))
    assert "Test Regime Switch Overlay" in set(report["strategy"])
    assert "SPY Buy and Hold" in set(report["strategy"])
    assert "SPY 12-Month Absolute Momentum" in set(report["strategy"])


def test_create_regime_switch_overlay_holdout_validation_summary_gates():
    report = pd.DataFrame(
        {
            "period": ["holdout", "holdout", "reference", "reference"],
            "strategy": [
                "Test Regime Switch Overlay",
                "SPY 12-Month Absolute Momentum",
                "Test Regime Switch Overlay",
                "SPY 12-Month Absolute Momentum",
            ],
            "cagr_pct": [10.0, 8.0, 7.0, 9.0],
            "calmar": [0.4, 0.3, 0.2, 0.5],
            "max_drawdown_pct": [-20.0, -30.0, -15.0, -25.0],
            "volatility_pct": [12.0, 14.0, 10.0, 16.0],
        }
    )

    summary = create_regime_switch_overlay_holdout_validation_summary(report)

    holdout = summary[summary["period"] == "holdout"].iloc[0]
    reference = summary[summary["period"] == "reference"].iloc[0]

    assert bool(holdout["overlay_passes_spy_12m_triple_gate"])
    assert not bool(reference["overlay_passes_spy_12m_triple_gate"])