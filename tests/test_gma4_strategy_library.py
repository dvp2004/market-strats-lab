from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    load_gma4_trial_registry,
)
from market_strats.global_multi_asset.gma4_strategy_library import build_gma4_trial_rules

REGISTRY_PATH = Path("configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml")


def _dates() -> list[Any]:
    return pd.bdate_range("2024-01-02", periods=320).date.tolist()


def _price_frame(dates: list[Any], daily_return: float, base: float = 100.0) -> pd.DataFrame:
    values = [base]
    for _idx in range(1, len(dates)):
        values.append(values[-1] * (1.0 + daily_return))
    return pd.DataFrame({"close_raw": values, "total_return_index": values}, index=dates)


def _mixed_prices() -> dict[str, pd.DataFrame]:
    dates = _dates()
    prices: dict[str, pd.DataFrame] = {}
    for idx, symbol in enumerate(FIXED_GMA4_UNIVERSE):
        drift = 0.00005 + idx * 0.00001
        if symbol in {"SPY", "QQQ", "XLK", "XLY", "EFA"}:
            drift = 0.001 + idx * 0.00002
        if symbol == "BIL":
            drift = 0.00015
        prices[symbol] = _price_frame(dates, drift, 100.0 + idx)
    return prices


def _risk_assets_flat_bil_positive() -> dict[str, pd.DataFrame]:
    dates = _dates()
    prices = {symbol: _price_frame(dates, -0.0002, 100.0) for symbol in FIXED_GMA4_UNIVERSE}
    prices["BIL"] = _price_frame(dates, 0.0002, 100.0)
    return prices


def _declining_prices_for_trend_filter() -> dict[str, pd.DataFrame]:
    dates = _dates()
    prices = {
        symbol: _price_frame(dates, -0.001, 100.0 + idx)
        for idx, symbol in enumerate(FIXED_GMA4_UNIVERSE)
    }
    prices["BIL"] = _price_frame(dates, 0.0001, 100.0)
    return prices


def test_registered_strategy_library_covers_all_twenty_trials():
    registry = load_gma4_trial_registry(REGISTRY_PATH)
    rules = build_gma4_trial_rules()

    assert set(rules) == {trial["trial_id"] for trial in registry.trials}
    assert len(rules) == 20


def test_all_trial_resolvers_return_long_only_fixed_universe_weights():
    prices = _mixed_prices()
    decision_date = _dates()[-1]

    for trial_id, rule in build_gma4_trial_rules().items():
        weights = rule.resolver(decision_date, prices)
        assert weights, trial_id
        assert set(weights) <= set(FIXED_GMA4_UNIVERSE)
        assert all(weight >= 0.0 for weight in weights.values())
        assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_trial_resolvers_do_not_look_past_decision_date():
    prices = _mixed_prices()
    decision_date = _dates()[-20]
    mutated = {symbol: frame.copy() for symbol, frame in prices.items()}
    for frame in mutated.values():
        frame.loc[frame.index > decision_date, "total_return_index"] *= 100.0
        frame.loc[frame.index > decision_date, "close_raw"] *= 100.0

    for trial_id, rule in build_gma4_trial_rules().items():
        assert rule.resolver(decision_date, mutated) == rule.resolver(decision_date, prices), (
            trial_id
        )


def test_trend_and_momentum_trials_fall_back_to_bil_when_no_risk_asset_qualifies():
    prices = _risk_assets_flat_bil_positive()
    decision_date = _dates()[-1]
    rules = build_gma4_trial_rules()

    for trial_id in [
        "gma4_abs_trend_10m_equal_weight_v1",
        "gma4_abs_trend_12m_equal_weight_v1",
        "gma4_xsmom_6m_top3_equal_weight_v1",
        "gma4_xsmom_12m_top3_equal_weight_v1",
    ]:
        assert rules[trial_id].resolver(decision_date, prices) == {"BIL": 1.0}


def test_mean_reversion_long_trend_filter_excludes_assets_below_long_average():
    prices = _declining_prices_for_trend_filter()
    decision_date = _dates()[-1]
    rule = build_gma4_trial_rules()["gma4_meanrev_5d_bottom3_long_trend_filter_v1"]

    assert rule.resolver(decision_date, prices) == {"BIL": 1.0}


def test_simple_blends_reference_declared_non_blend_components():
    registry = load_gma4_trial_registry(REGISTRY_PATH)
    trial_by_id = {trial["trial_id"]: trial for trial in registry.trials}
    rules = build_gma4_trial_rules()

    for trial in registry.trials:
        if trial["family"] != "simple_blend":
            continue
        assert trial["trial_id"] in rules
        for component_id in trial["parameters"]["component_trial_ids"]:
            assert component_id in rules
            assert trial_by_id[component_id]["family"] != "simple_blend"
