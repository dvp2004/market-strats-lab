import pandas as pd

from market_strats.analysis.strategy_purpose import classify_strategy_purpose


def test_classify_strategy_purpose_marks_good_momentum_as_wealth_builder():
    metrics = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "cagr_pct": [10.0, 10.1],
            "max_drawdown_pct": [-55.0, -35.0],
            "sharpe": [0.6, 0.8],
            "trade_count": [1, 17],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-7.0, -1.0],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    momentum = result[result["strategy"] == "12-Month Absolute Momentum"].iloc[0]

    assert momentum["purpose_classification"] == "Wealth-builder candidate"
    assert bool(momentum["wealth_test_pass"]) is True


def test_classify_strategy_purpose_marks_large_cagr_sacrifice_as_risk_control_only():
    metrics = pd.DataFrame(
        {
            "ticker": ["IWM", "IWM"],
            "strategy": ["Buy and Hold", "Trend-Filtered Drawdown"],
            "cagr_pct": [8.6, 5.5],
            "max_drawdown_pct": [-58.0, -27.0],
            "sharpe": [0.46, 0.51],
            "trade_count": [1, 211],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["IWM", "IWM"],
            "strategy": ["Buy and Hold", "Trend-Filtered Drawdown"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-6.8, -2.5],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    trend_filtered = result[result["strategy"] == "Trend-Filtered Drawdown"].iloc[0]

    assert trend_filtered["purpose_classification"] == "Risk-control only"
    assert bool(trend_filtered["wealth_test_pass"]) is False


def test_classify_strategy_purpose_quarantines_btc():
    metrics = pd.DataFrame(
        {
            "ticker": ["BTC-USD", "BTC-USD"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "cagr_pct": [56.0, 66.0],
            "max_drawdown_pct": [-83.0, -72.0],
            "sharpe": [1.0, 1.2],
            "trade_count": [1, 14],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["BTC-USD", "BTC-USD"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "window_years": [5, 5],
            "worst_cagr_pct": [3.0, 22.0],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    btc_sma = result[result["strategy"] == "10-Month SMA"].iloc[0]

    assert btc_sma["purpose_classification"] == "Quarantined / separate branch"
    assert bool(btc_sma["wealth_test_pass"]) is False


def test_classify_strategy_purpose_returns_empty_for_empty_metrics():
    result = classify_strategy_purpose(
        metrics=pd.DataFrame(),
        rolling_summary=pd.DataFrame(),
    )

    assert result.empty