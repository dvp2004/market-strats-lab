import pandas as pd

from market_strats.analysis.finalist_holdout_validation import (
    create_finalist_holdout_validation_report,
    create_finalist_holdout_validation_summary,
)

def test_create_finalist_holdout_validation_summary_identifies_winners():
    report = pd.DataFrame(
        {
            "period": ["holdout", "holdout", "reference", "reference"],
            "strategy": [
                "A",
                "12-Month Absolute Momentum",
                "A",
                "12-Month Absolute Momentum",
            ],
            "cagr_pct": [10.0, 8.0, 7.0, 9.0],
            "calmar": [0.4, 0.3, 0.2, 0.5],
            "max_drawdown_pct": [-20.0, -30.0, -15.0, -25.0],
        }
    )

    summary = create_finalist_holdout_validation_summary(report)

    assert len(summary) == 2

    holdout = summary[summary["period"] == "holdout"].iloc[0]

    assert holdout["best_cagr_strategy"] == "A"
    assert holdout["best_calmar_strategy"] == "A"
    assert holdout["best_drawdown_strategy"] == "A"
    assert holdout["spy_12m_cagr_pct"] == 8.0

def make_strategy_result(dates: pd.DatetimeIndex, returns: list[float]) -> pd.DataFrame:
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


def test_create_finalist_holdout_validation_report_runs_without_metric_signature_error():
    dates = pd.bdate_range("2010-01-01", "2020-12-31")
    returns = [0.0] + [0.0005] * (len(dates) - 1)

    result = make_strategy_result(dates, returns)

    ticker_outputs = {
        "SPY": {
            "strategy_results": {
                "Buy and Hold": result,
                "12-Month Absolute Momentum": result,
                "60/40 Annual Rebalanced Core-Satellite SPY B&H + 12M Momentum": result,
            }
        },
        "EFA": {
            "strategy_results": {
                "200-Day SMA": result,
            }
        },
        "AGG": {
            "strategy_results": {
                "12-Month Absolute Momentum": result,
            }
        },
    }

    config = {
        "initial_capital": 10_000,
        "finalist_holdout_validation": {
            "enabled": True,
            "reference_end_date": "2015-12-31",
            "holdout_start_date": "2016-01-01",
            "finalist_portfolios": [
                {
                    "name": "Test Portfolio",
                    "components": [
                        {
                            "ticker": "SPY",
                            "strategy": "12-Month Absolute Momentum",
                            "weight": 0.50,
                        },
                        {
                            "ticker": "EFA",
                            "strategy": "200-Day SMA",
                            "weight": 0.30,
                        },
                        {
                            "ticker": "AGG",
                            "strategy": "12-Month Absolute Momentum",
                            "weight": 0.20,
                        },
                    ],
                }
            ],
        },
    }

    report = create_finalist_holdout_validation_report(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not report.empty
    assert {"reference", "holdout"}.issubset(set(report["period"]))