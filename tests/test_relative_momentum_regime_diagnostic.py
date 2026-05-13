import pandas as pd

from market_strats.analysis.relative_momentum_regime_diagnostic import (
    create_relative_momentum_regime_diagnostic,
    create_relative_momentum_regime_summary,
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


def test_create_relative_momentum_regime_diagnostic_runs():
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
        "relative_momentum_regime_diagnostic": {
            "enabled": True,
            "benchmark_ticker": "SPY",
            "benchmark_strategy": "Buy and Hold",
            "benchmark_momentum_strategy": "12-Month Absolute Momentum",
            "trend_sma_days": 200,
            "momentum_lookback_days": 252,
        },
    }

    diagnostic = create_relative_momentum_regime_diagnostic(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    assert not diagnostic.empty
    assert "regime_dimension" in diagnostic.columns
    assert "regime_value" in diagnostic.columns
    assert "strategy" in diagnostic.columns
    assert "conditional_annualized_return_pct" in diagnostic.columns


def test_create_relative_momentum_regime_summary_identifies_best_rows():
    diagnostic = pd.DataFrame(
        {
            "regime_dimension": ["trend", "trend", "trend"],
            "regime_value": ["up", "up", "up"],
            "strategy": ["A", "B", "SPY 12-Month Absolute Momentum"],
            "days": [100, 100, 100],
            "conditional_annualized_return_pct": [10.0, 8.0, 9.0],
            "conditional_sharpe": [0.5, 0.7, 0.6],
            "conditional_volatility_pct": [15.0, 10.0, 12.0],
            "avg_exposure_pct": [80.0, 60.0, 70.0],
        }
    )

    summary = create_relative_momentum_regime_summary(diagnostic)

    assert len(summary) == 1
    row = summary.iloc[0]

    assert row["best_return_strategy"] == "A"
    assert row["best_sharpe_strategy"] == "B"
    assert row["lowest_volatility_strategy"] == "B"
    assert row["spy_12m_return_pct"] == 9.0