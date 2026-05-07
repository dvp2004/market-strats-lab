import pandas as pd

from market_strats.analysis.strategy_purpose import classify_strategy_purpose


def test_classify_strategy_purpose_marks_spy_momentum_as_wealth_equivalent_risk_reducer():
    metrics = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "cagr_pct": [10.75, 10.77],
            "max_drawdown_pct": [-55.19, -33.72],
            "sharpe": [0.64, 0.78],
            "trade_count": [1, 17],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-6.86, -0.19],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    momentum = result[result["strategy"] == "12-Month Absolute Momentum"].iloc[0]

    assert momentum["purpose_classification"] == "Wealth-equivalent risk reducer"
    assert bool(momentum["wealth_test_pass"]) is True


def test_classify_strategy_purpose_marks_return_enhancing_candidate():
    metrics = pd.DataFrame(
        {
            "ticker": ["TEST", "TEST"],
            "strategy": ["Buy and Hold", "Test Strategy"],
            "cagr_pct": [8.0, 8.5],
            "max_drawdown_pct": [-40.0, -35.0],
            "sharpe": [0.5, 0.6],
            "trade_count": [1, 10],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["TEST", "TEST"],
            "strategy": ["Buy and Hold", "Test Strategy"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-5.0, -4.0],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "Test Strategy"].iloc[0]

    assert strategy["purpose_classification"] == "Return-enhancing candidate"
    assert bool(strategy["wealth_test_pass"]) is True


def test_classify_strategy_purpose_marks_agg_like_result_as_defensive_sleeve_candidate():
    metrics = pd.DataFrame(
        {
            "ticker": ["AGG", "AGG"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "cagr_pct": [3.09, 3.18],
            "max_drawdown_pct": [-18.43, -12.84],
            "sharpe": [0.35, 0.42],
            "trade_count": [1, 12],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["AGG", "AGG"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-2.0, -1.0],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "12-Month Absolute Momentum"].iloc[0]

    assert strategy["purpose_classification"] == "Defensive sleeve candidate"
    assert bool(strategy["wealth_test_pass"]) is True


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


def test_risk_control_candidate_requires_wealth_test_pass():
    metrics = pd.DataFrame(
        {
            "ticker": ["GLD", "GLD"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "cagr_pct": [11.09, 8.69],
            "max_drawdown_pct": [-45.56, -41.58],
            "sharpe": [0.67, 0.63],
            "trade_count": [1, 37],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["GLD", "GLD"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-8.06, -7.74],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "10-Month SMA"].iloc[0]

    assert strategy["purpose_classification"] != "Risk-control candidate"
    assert strategy["purpose_classification"] in {"Risk-control only", "Rejected / weak"}
    assert bool(strategy["wealth_test_pass"]) is False


def test_qqq_like_momentum_can_be_risk_control_candidate_when_wealth_test_passes():
    metrics = pd.DataFrame(
        {
            "ticker": ["QQQ", "QQQ"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "cagr_pct": [10.66, 10.30],
            "max_drawdown_pct": [-82.96, -40.97],
            "sharpe": [0.51, 0.61],
            "trade_count": [1, 19],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["QQQ", "QQQ"],
            "strategy": ["Buy and Hold", "12-Month Absolute Momentum"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-19.54, -6.40],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "12-Month Absolute Momentum"].iloc[0]

    assert strategy["purpose_classification"] == "Risk-control candidate"
    assert bool(strategy["wealth_test_pass"]) is True


def test_classify_strategy_purpose_marks_efa_200d_as_return_enhancing_after_validation():
    metrics = pd.DataFrame(
        {
            "ticker": ["EFA", "EFA"],
            "strategy": ["Buy and Hold", "200-Day SMA"],
            "cagr_pct": [6.38, 7.63],
            "max_drawdown_pct": [-61.04, -26.31],
            "sharpe": [0.35, 0.62],
            "trade_count": [1, 120],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["EFA", "EFA"],
            "strategy": ["Buy and Hold", "200-Day SMA"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-7.0, -2.0],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "200-Day SMA"].iloc[0]

    assert strategy["purpose_classification"] == "Return-enhancing candidate"
    assert strategy["base_purpose_classification"] == "Return-enhancing candidate"
    assert bool(strategy["pending_validation"]) is False


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

def test_classify_strategy_purpose_demotes_efa_10m_after_monthly_robustness():
    metrics = pd.DataFrame(
        {
            "ticker": ["EFA", "EFA"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "cagr_pct": [6.38, 6.27],
            "max_drawdown_pct": [-61.04, -34.73],
            "sharpe": [0.35, 0.55],
            "trade_count": [1, 40],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "ticker": ["EFA", "EFA"],
            "strategy": ["Buy and Hold", "10-Month SMA"],
            "window_years": [5, 5],
            "worst_cagr_pct": [-7.0, -4.53],
        }
    )

    result = classify_strategy_purpose(metrics, rolling_summary)

    strategy = result[result["strategy"] == "10-Month SMA"].iloc[0]

    assert strategy["purpose_classification"] == "Risk-control candidate"
    assert strategy["base_purpose_classification"] == "Wealth-equivalent risk reducer"
    assert bool(strategy["wealth_test_pass"]) is True
    assert bool(strategy["pending_validation"]) is False