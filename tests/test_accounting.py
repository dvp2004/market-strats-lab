import pandas as pd

from market_strats.strategies.accounting import calculate_allocation_strategy_returns


def test_allocation_strategy_returns_include_cash_when_out_of_market():
    asset_return = pd.Series([0.0, 0.10])
    held_position = pd.Series([0.0, 0.0])
    turnover = pd.Series([0.0, 0.0])
    cash_returns = pd.Series([0.001, 0.001])

    result = calculate_allocation_strategy_returns(
        asset_return=asset_return,
        held_position=held_position,
        turnover=turnover,
        slippage_bps=0,
        cash_returns=cash_returns,
    )

    assert result.iloc[0] == 0.001
    assert result.iloc[1] == 0.001


def test_allocation_strategy_returns_blend_asset_and_cash_returns():
    asset_return = pd.Series([0.10])
    held_position = pd.Series([0.70])
    turnover = pd.Series([0.0])
    cash_returns = pd.Series([0.02])

    result = calculate_allocation_strategy_returns(
        asset_return=asset_return,
        held_position=held_position,
        turnover=turnover,
        slippage_bps=0,
        cash_returns=cash_returns,
    )

    expected = (0.70 * 0.10) + (0.30 * 0.02)

    assert round(result.iloc[0], 6) == round(expected, 6)


def test_allocation_strategy_returns_subtract_slippage():
    asset_return = pd.Series([0.0])
    held_position = pd.Series([1.0])
    turnover = pd.Series([1.0])
    cash_returns = pd.Series([0.0])

    result = calculate_allocation_strategy_returns(
        asset_return=asset_return,
        held_position=held_position,
        turnover=turnover,
        slippage_bps=5,
        cash_returns=cash_returns,
    )

    assert result.iloc[0] == -0.0005