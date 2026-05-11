import pandas as pd

from market_strats.analysis.regime_switch_overlay_report import (
    run_regime_switch_overlay_report,
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


def test_run_regime_switch_overlay_report_runs(tmp_path):
    dates = pd.bdate_range("2010-01-01", "2020-12-31")

    allocator_result = make_result(dates, 0.0004)
    spy_result = make_result(dates, 0.0005)

    relative_momentum_outputs = {
        "Defensive Allocator": {
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
        "slippage_bps": 0.0,
        "regime_switch_overlay": {
            "enabled": True,
            "name": "Test Overlay",
            "benchmark_ticker": "SPY",
            "offensive_strategy": "Buy and Hold",
            "defensive_allocator_name": "Defensive Allocator",
            "trend_sma_days": 200,
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
            "comparison_allocators": ["Defensive Allocator"],
        },
    }

    output = run_regime_switch_overlay_report(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
        reports_dir=tmp_path,
    )

    assert not output["overlay_result"].empty
    assert not output["metrics"].empty
    assert not output["mode_summary"].empty