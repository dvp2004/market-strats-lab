import pandas as pd
from market_strats.analysis.metrics import calculate_drawdown, infer_periods_per_year

def test_drawdown_is_zero_at_equity_highs():
    equity = pd.Series([100, 110, 105, 120])
    drawdown = calculate_drawdown(equity)

    assert drawdown.iloc[0] == 0
    assert drawdown.iloc[1] == 0
    assert drawdown.iloc[3] == 0
    assert drawdown.iloc[2] < 0

def test_infer_periods_per_year_detects_business_day_data():
    result = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=252),
            "equity": 10_000,
            "strategy_return": 0.0,
            "position": 1.0,
            "turnover": 0.0,
        }
    )

    periods_per_year = infer_periods_per_year(result)

    assert 240 <= periods_per_year <= 265


def test_infer_periods_per_year_detects_calendar_day_data():
    result = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=365, freq="D"),
            "equity": 10_000,
            "strategy_return": 0.0,
            "position": 1.0,
            "turnover": 0.0,
        }
    )

    periods_per_year = infer_periods_per_year(result)

    assert 350 <= periods_per_year <= 380    