import pandas as pd

from market_strats.analysis.relative_momentum_holdout_validation import (
    create_relative_momentum_holdout_validation_report,
    create_relative_momentum_holdout_validation_summary,
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


def test_create_relative_momentum_holdout_validation_report_runs():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    allocator_result = make_result(dates, 0.0004)
    benchmark_result = make_result(dates, 0.0005)

    relative_momentum_outputs = {
        "Allocator": {
            "allocator_result": allocator_result,
        }
    }

    ticker_outputs = {
        "SPY": {
            "strategy_results": {
                "Buy and Hold": benchmark_result,
                "12-Month Absolute Momentum": benchmark_result,
            }
        }
    }

    config = {
        "initial_capital": 10_000,
        "relative_momentum_allocator": {
            "benchmarks": [
                {
                    "ticker": "SPY",
                    "strategy": "Buy and Hold",
                },
                {
                    "ticker": "SPY",
                    "strategy": "12-Month Absolute Momentum",
                },
            ]
        },
        "relative_momentum_holdout_validation": {
            "enabled": True,
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
        },
    }

    report = create_relative_momentum_holdout_validation_report(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not report.empty
    assert {"reference", "holdout"}.issubset(set(report["period"]))
    assert "Allocator" in set(report["strategy"])
    assert "SPY Buy and Hold" in set(report["strategy"])
    assert "SPY 12-Month Absolute Momentum" in set(report["strategy"])


def test_create_relative_momentum_holdout_validation_summary_identifies_winners():
    report = pd.DataFrame(
        {
            "period": ["holdout", "holdout", "reference", "reference"],
            "strategy": [
                "A",
                "SPY 12-Month Absolute Momentum",
                "A",
                "SPY 12-Month Absolute Momentum",
            ],
            "cagr_pct": [10.0, 8.0, 7.0, 9.0],
            "calmar": [0.4, 0.3, 0.2, 0.5],
            "max_drawdown_pct": [-20.0, -30.0, -15.0, -25.0],
            "volatility_pct": [12.0, 14.0, 10.0, 16.0],
        }
    )

    summary = create_relative_momentum_holdout_validation_summary(report)

    assert len(summary) == 2

    holdout = summary[summary["period"] == "holdout"].iloc[0]

    assert holdout["best_cagr_strategy"] == "A"
    assert holdout["best_calmar_strategy"] == "A"
    assert holdout["best_drawdown_strategy"] == "A"
    assert holdout["spy_12m_cagr_pct"] == 8.0