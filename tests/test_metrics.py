import pandas as pd

from market_strats.analysis.metrics import calculate_drawdown


def test_drawdown_is_zero_at_equity_highs():
    equity = pd.Series([100, 110, 105, 120])
    drawdown = calculate_drawdown(equity)

    assert drawdown.iloc[0] == 0
    assert drawdown.iloc[1] == 0
    assert drawdown.iloc[3] == 0
    assert drawdown.iloc[2] < 0