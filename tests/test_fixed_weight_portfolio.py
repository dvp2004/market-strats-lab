import pandas as pd
import pytest

from market_strats.strategies.fixed_weight_portfolio import (
    get_common_strategy_dates,
    rebase_strategy_result_to_dates,
    run_independent_weighted_portfolio,
)


def make_result(
    dates: pd.DatetimeIndex,
    returns: list[float],
    position: float,
) -> pd.DataFrame:
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": position,
            "cash_position": 1.0 - position,
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def test_get_common_strategy_dates_returns_intersection():
    dates_a = pd.bdate_range("2020-01-01", periods=5)
    dates_b = pd.bdate_range("2020-01-03", periods=5)

    result_a = make_result(dates_a, [0, 0.01, 0.01, 0.01, 0.01], 1.0)
    result_b = make_result(dates_b, [0, 0.01, 0.01, 0.01, 0.01], 1.0)

    common_dates = get_common_strategy_dates(
        {
            "A": result_a,
            "B": result_b,
        }
    )

    assert min(common_dates) == pd.Timestamp("2020-01-03")
    assert max(common_dates) == pd.Timestamp("2020-01-07")


def test_rebase_strategy_result_to_dates_starts_at_initial_capital():
    dates = pd.bdate_range("2020-01-01", periods=5)
    result = make_result(dates, [0, 0.01, 0.01, 0.01, 0.01], 1.0)

    rebased = rebase_strategy_result_to_dates(
        result=result,
        dates=list(dates[2:]),
        initial_capital=10_000,
    )

    assert rebased["equity"].iloc[0] == 10_000
    assert rebased["strategy_return"].iloc[0] == 0.0


def test_run_independent_weighted_portfolio_combines_sleeves():
    dates = pd.bdate_range("2020-01-01", periods=5)

    result_a = make_result(dates, [0, 0.01, 0.01, 0.01, 0.01], 1.0)
    result_b = make_result(dates, [0, 0.00, 0.00, 0.00, 0.00], 0.0)

    portfolio = run_independent_weighted_portfolio(
        component_results={
            "A": result_a,
            "B": result_b,
        },
        weights={
            "A": 0.60,
            "B": 0.40,
        },
        initial_capital=10_000,
        portfolio_name="Test Portfolio",
    )

    assert len(portfolio) == 5
    assert portfolio["equity"].iloc[0] == 10_000
    assert portfolio["equity"].iloc[-1] > 10_000
    assert "a_current_weight" in portfolio.columns
    assert "b_current_weight" in portfolio.columns


def test_run_independent_weighted_portfolio_rejects_bad_weights():
    dates = pd.bdate_range("2020-01-01", periods=5)

    result_a = make_result(dates, [0, 0.01, 0.01, 0.01, 0.01], 1.0)
    result_b = make_result(dates, [0, 0.00, 0.00, 0.00, 0.00], 0.0)

    with pytest.raises(ValueError):
        run_independent_weighted_portfolio(
            component_results={
                "A": result_a,
                "B": result_b,
            },
            weights={
                "A": 0.50,
                "B": 0.40,
            },
            initial_capital=10_000,
            portfolio_name="Test Portfolio",
        )