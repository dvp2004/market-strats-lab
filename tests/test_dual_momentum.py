import pandas as pd

from market_strats.strategies.dual_momentum import run_dual_momentum_strategy


def make_price_frame(prices: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(prices))

    return pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "adj_close": prices,
            "volume": 1_000_000,
        }
    )


def test_dual_momentum_selects_stronger_asset_when_above_cash():
    asset_a_prices = make_price_frame(list(range(100, 600)))
    asset_b_prices = make_price_frame([100.0] * 500)

    result = run_dual_momentum_strategy(
        asset_a_prices=asset_a_prices,
        asset_b_prices=asset_b_prices,
        asset_a_name="AAA",
        asset_b_name="BBB",
        initial_capital=10_000,
        momentum_months=3,
        slippage_bps=0,
        cash_returns=None,
    )

    assert result["target_selected_asset"].iloc[-1] == "AAA"
    assert result["target_weight_AAA"].iloc[-1] == 1.0
    assert result["target_weight_BBB"].iloc[-1] == 0.0


def test_dual_momentum_goes_to_cash_when_winner_does_not_beat_cash():
    asset_a_prices = make_price_frame(list(range(600, 100, -1)))
    asset_b_prices = make_price_frame(list(range(700, 200, -1)))
    cash_returns = pd.Series(
        [0.0001] * 500,
        index=pd.bdate_range("2020-01-01", periods=500),
    )

    result = run_dual_momentum_strategy(
        asset_a_prices=asset_a_prices,
        asset_b_prices=asset_b_prices,
        asset_a_name="AAA",
        asset_b_name="BBB",
        initial_capital=10_000,
        momentum_months=3,
        slippage_bps=0,
        cash_returns=cash_returns,
    )

    assert result["target_selected_asset"].iloc[-1] == "CASH"
    assert result["target_weight_AAA"].iloc[-1] == 0.0
    assert result["target_weight_BBB"].iloc[-1] == 0.0


def test_dual_momentum_starts_at_initial_capital():
    asset_a_prices = make_price_frame(list(range(100, 600)))
    asset_b_prices = make_price_frame([100.0] * 500)

    result = run_dual_momentum_strategy(
        asset_a_prices=asset_a_prices,
        asset_b_prices=asset_b_prices,
        asset_a_name="AAA",
        asset_b_name="BBB",
        initial_capital=10_000,
        momentum_months=3,
        slippage_bps=5,
        cash_returns=None,
    )

    assert result["equity"].iloc[0] == 10_000
    assert result["strategy_return"].iloc[0] == 0.0

def test_dual_momentum_outputs_audit_reason_columns():
    asset_a_prices = make_price_frame(list(range(100, 600)))
    asset_b_prices = make_price_frame([100.0] * 500)

    result = run_dual_momentum_strategy(
        asset_a_prices=asset_a_prices,
        asset_b_prices=asset_b_prices,
        asset_a_name="AAA",
        asset_b_name="BBB",
        initial_capital=10_000,
        momentum_months=3,
        slippage_bps=0,
        cash_returns=None,
    )

    expected_columns = {
        "cash_reason",
        "target_cash_reason",
        "relative_winner",
        "target_relative_winner",
        "relative_winner_return",
        "target_relative_winner_return",
        "trailing_cash_return",
        "target_trailing_cash_return",
        "cash_return",
    }

    assert expected_columns.issubset(set(result.columns))
    assert result["cash_reason"].notna().any()
    assert "cash_return" in result.columns