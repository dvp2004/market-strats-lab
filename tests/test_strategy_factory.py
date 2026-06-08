import numpy as np
import pandas as pd

from market_strats.strategies.strategy_factory import (
    FACTORY_ASSETS,
    STRATEGY_FACTORY_CANDIDATES,
    StrategyFactoryConfig,
    build_strategy_factory_price_panel,
    run_strategy_factory_candidates,
)


def _synthetic_prices() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-02", periods=650)
    specs = {
        "SPY": (0.00045, 0.010),
        "QQQ": (0.00070, 0.014),
        "GLD": (0.00025, 0.008),
        "TLT": (0.00010, 0.007),
        "BTC-USD": (0.00120, 0.030),
    }
    out = {}
    for idx, (ticker, (mean, vol)) in enumerate(specs.items()):
        rng = np.random.default_rng(100 + idx)
        returns = rng.normal(mean, vol, len(dates))
        returns[:220] = abs(returns[:220]) + mean
        prices = 100 * (1 + pd.Series(returns)).cumprod()
        out[ticker] = pd.DataFrame({"date": dates, "adj_close": prices})
    return out


def test_strategy_factory_candidates_return_non_empty_frames():
    panel = build_strategy_factory_price_panel(_synthetic_prices())
    results, status = run_strategy_factory_candidates(
        panel,
        config=StrategyFactoryConfig(initial_capital=10000),
    )

    assert set(results) == set(STRATEGY_FACTORY_CANDIDATES)
    assert set(status["strategy"]) == set(STRATEGY_FACTORY_CANDIDATES)
    for result in results.values():
        assert not result.empty
        assert {"date", "strategy_return", "equity", "position", "cash_position", "turnover"}.issubset(
            result.columns
        )


def test_strategy_factory_weights_are_valid_and_cash_non_negative():
    panel = build_strategy_factory_price_panel(_synthetic_prices())
    results, _status = run_strategy_factory_candidates(panel)
    weight_cols = [f"{asset.lower().replace('-', '_')}_weight" for asset in FACTORY_ASSETS]

    for result in results.values():
        weights = result[weight_cols]
        assert (weights >= -1e-10).all().all()
        assert (result["cash_position"] >= -1e-10).all()
        assert np.allclose(weights.sum(axis=1), 1.0, atol=1e-8)


def test_strategy_factory_btc_cap_is_respected():
    panel = build_strategy_factory_price_panel(_synthetic_prices())
    results, _status = run_strategy_factory_candidates(
        panel,
        config=StrategyFactoryConfig(btc_max_weight=0.10),
    )

    btc = results["sf_spy_qqq_btc_capped_offensive"]["btc_usd_weight"]
    assert (btc <= 0.10 + 1e-10).all()
    assert (btc >= -1e-10).all()
