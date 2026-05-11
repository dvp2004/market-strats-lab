import pandas as pd
import pytest

from market_strats.strategies.relative_momentum_allocator import (
    create_price_panel,
    run_relative_momentum_allocator,
)


def make_prices(
    dates: pd.DatetimeIndex,
    start_price: float,
    daily_return: float,
) -> pd.DataFrame:
    prices = [start_price]

    for _ in range(1, len(dates)):
        prices.append(prices[-1] * (1.0 + daily_return))

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
        }
    )


def test_create_price_panel_uses_common_dates():
    dates_a = pd.bdate_range("2020-01-01", periods=5)
    dates_b = pd.bdate_range("2020-01-03", periods=5)

    panel = create_price_panel(
        {
            "AAA": make_prices(dates_a, 100.0, 0.001),
            "BBB": make_prices(dates_b, 100.0, 0.001),
        }
    )

    assert panel.index.min() == pd.Timestamp("2020-01-03")
    assert set(panel.columns) == {"AAA", "BBB"}


def test_relative_momentum_allocator_runs_and_outputs_weights():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    result = run_relative_momentum_allocator(
        price_data_by_ticker={
            "AAA": make_prices(dates, 100.0, 0.0010),
            "BBB": make_prices(dates, 100.0, 0.0005),
            "CCC": make_prices(dates, 100.0, -0.0002),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=2,
        slippage_bps=0.0,
        min_momentum=0.0,
    )

    assert not result.empty
    assert "AAA_weight" in result.columns
    assert "BBB_weight" in result.columns
    assert "CCC_weight" in result.columns
    assert "cash_position" in result.columns
    assert result["equity"].iloc[-1] > 0


def test_relative_momentum_allocator_rejects_invalid_top_n():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    with pytest.raises(ValueError):
        run_relative_momentum_allocator(
            price_data_by_ticker={
                "AAA": make_prices(dates, 100.0, 0.0010),
            },
            initial_capital=10_000,
            lookback_months=12,
            top_n=2,
            slippage_bps=0.0,
            min_momentum=0.0,
        )

def test_relative_momentum_allocator_persists_weights_between_monthly_rebalances():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    result = run_relative_momentum_allocator(
        price_data_by_ticker={
            "AAA": make_prices(dates, 100.0, 0.0010),
            "BBB": make_prices(dates, 100.0, 0.0007),
            "CCC": make_prices(dates, 100.0, 0.0005),
            "DDD": make_prices(dates, 100.0, -0.0002),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=3,
        slippage_bps=0.0,
        min_momentum=0.0,
    )

    post_warmup = result[pd.to_datetime(result["date"]) > pd.Timestamp("2019-06-01")]

    assert post_warmup["position"].mean() > 0.75
    assert post_warmup["AAA_weight"].max() > 0.0
    assert post_warmup["BBB_weight"].max() > 0.0
    assert post_warmup["CCC_weight"].max() > 0.0

def make_prices_from_returns(
    dates: pd.DatetimeIndex,
    start_price: float,
    returns: list[float],
) -> pd.DataFrame:
    prices = [start_price]

    for return_value in returns[1:]:
        prices.append(prices[-1] * (1.0 + return_value))

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
        }
    )

def test_inverse_volatility_weighting_allocates_less_to_high_vol_asset():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    low_vol_returns = [0.0]
    high_vol_returns = [0.0]

    for index in range(1, len(dates)):
        low_vol_returns.append(0.0004 + (0.0001 if index % 2 == 0 else -0.0001))
        high_vol_returns.append(0.0006 + (0.015 if index % 2 == 0 else -0.014))

    result = run_relative_momentum_allocator(
        price_data_by_ticker={
            "LOW": make_prices_from_returns(dates, 100.0, low_vol_returns),
            "HIGH": make_prices_from_returns(dates, 100.0, high_vol_returns),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=2,
        slippage_bps=0.0,
        min_momentum=0.0,
        weighting="inverse_volatility",
        volatility_lookback_days=63,
    )

    post_warmup = result[pd.to_datetime(result["date"]) > pd.Timestamp("2019-06-01")]
    invested = post_warmup[post_warmup["position"] > 0.99]

    assert not invested.empty
    assert invested["LOW_weight"].mean() > invested["HIGH_weight"].mean()

def test_relative_momentum_allocator_rejects_invalid_weighting():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    with pytest.raises(ValueError):
        run_relative_momentum_allocator(
            price_data_by_ticker={
                "AAA": make_prices(dates, 100.0, 0.0010),
                "BBB": make_prices(dates, 100.0, 0.0005),
            },
            initial_capital=10_000,
            lookback_months=12,
            top_n=2,
            slippage_bps=0.0,
            min_momentum=0.0,
            weighting="bad_weighting",
        )

def test_trend_filter_reduces_exposure_when_asset_breaks_below_sma():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    trend_ok_returns = [0.0]
    trend_broken_returns = [0.0]

    for index in range(1, len(dates)):
        trend_ok_returns.append(0.0005)

        if index < 650:
            trend_broken_returns.append(0.0008)
        else:
            trend_broken_returns.append(-0.0020)

    result_without_filter = run_relative_momentum_allocator(
        price_data_by_ticker={
            "TREND_OK": make_prices_from_returns(dates, 100.0, trend_ok_returns),
            "BROKEN": make_prices_from_returns(dates, 100.0, trend_broken_returns),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=2,
        slippage_bps=0.0,
        min_momentum=0.0,
        weighting="equal",
        trend_filter_enabled=False,
        trend_sma_days=200,
    )

    result_with_filter = run_relative_momentum_allocator(
        price_data_by_ticker={
            "TREND_OK": make_prices_from_returns(dates, 100.0, trend_ok_returns),
            "BROKEN": make_prices_from_returns(dates, 100.0, trend_broken_returns),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=2,
        slippage_bps=0.0,
        min_momentum=0.0,
        weighting="equal",
        trend_filter_enabled=True,
        trend_sma_days=200,
    )

    late_without_filter = result_without_filter[
        pd.to_datetime(result_without_filter["date"]) > pd.Timestamp("2020-10-01")
    ]
    late_with_filter = result_with_filter[
        pd.to_datetime(result_with_filter["date"]) > pd.Timestamp("2020-10-01")
    ]

    assert late_with_filter["BROKEN_weight"].mean() < late_without_filter[
        "BROKEN_weight"
    ].mean()

def test_max_asset_weight_caps_selected_asset_weight():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    result = run_relative_momentum_allocator(
        price_data_by_ticker={
            "AAA": make_prices(dates, 100.0, 0.0010),
            "BBB": make_prices(dates, 100.0, 0.0008),
            "CCC": make_prices(dates, 100.0, 0.0006),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=3,
        slippage_bps=0.0,
        min_momentum=0.0,
        weighting="equal",
        max_asset_weight=0.25,
    )

    post_warmup = result[pd.to_datetime(result["date"]) > pd.Timestamp("2019-06-01")]

    assert post_warmup["AAA_weight"].max() <= 0.250001
    assert post_warmup["BBB_weight"].max() <= 0.250001
    assert post_warmup["CCC_weight"].max() <= 0.250001
    assert post_warmup["cash_position"].mean() > 0.20


def test_asset_group_cap_limits_group_exposure():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")

    result = run_relative_momentum_allocator(
        price_data_by_ticker={
            "GLD": make_prices(dates, 100.0, 0.0010),
            "SLV": make_prices(dates, 100.0, 0.0009),
            "DBC": make_prices(dates, 100.0, 0.0008),
        },
        initial_capital=10_000,
        lookback_months=12,
        top_n=3,
        slippage_bps=0.0,
        min_momentum=0.0,
        weighting="equal",
        asset_groups={"commodities": ["GLD", "SLV", "DBC"]},
        asset_group_caps={"commodities": 0.50},
    )

    post_warmup = result[pd.to_datetime(result["date"]) > pd.Timestamp("2019-06-01")]

    commodity_weight = (
        post_warmup["GLD_weight"]
        + post_warmup["SLV_weight"]
        + post_warmup["DBC_weight"]
    )

    assert commodity_weight.max() <= 0.500001
    assert post_warmup["cash_position"].mean() > 0.45