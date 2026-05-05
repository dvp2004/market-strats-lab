import pytest

from market_strats.run_backtest import (
    get_core_satellite_config,
    get_dual_momentum_pairs,
    get_tickers,
)

def test_get_tickers_uses_tickers_list_when_available():
    config = {"tickers": ["spy", "qqq"]}

    assert get_tickers(config) == ["SPY", "QQQ"]


def test_get_tickers_falls_back_to_single_ticker():
    config = {"ticker": "spy"}

    assert get_tickers(config) == ["SPY"]


def test_get_tickers_rejects_missing_ticker_config():
    config = {}

    with pytest.raises(ValueError):
        get_tickers(config)

def test_get_dual_momentum_pairs_validates_pair_config():
    config = {
        "dual_momentum_pairs": [
            {
                "name": "US_vs_International",
                "assets": ["spy", "efa"],
            }
        ]
    }

    result = get_dual_momentum_pairs(config)

    assert result == [{"name": "US_vs_International", "assets": ["SPY", "EFA"]}]


def test_get_dual_momentum_pairs_rejects_invalid_pair_length():
    config = {
        "dual_momentum_pairs": [
            {
                "name": "Invalid",
                "assets": ["SPY", "EFA", "TLT"],
            }
        ]
    }

    with pytest.raises(ValueError):
        get_dual_momentum_pairs(config)        

def test_get_core_satellite_config_returns_enabled_config():
    config = {
        "core_satellite": {
            "enabled": True,
            "ticker": "spy",
            "core_weight": 0.60,
            "satellite_weight": 0.40,
            "satellite_strategy": "12_month_absolute_momentum",
            "rebalance_mode": "independent_sleeves",
        }
    }

    result = get_core_satellite_config(config)

    assert result == {
        "ticker": "SPY",
        "core_weight": 0.60,
        "satellite_weight": 0.40,
        "satellite_strategy": "12_month_absolute_momentum",
        "rebalance_mode": "independent_sleeves",
    }


def test_get_core_satellite_config_returns_none_when_disabled():
    config = {
        "core_satellite": {
            "enabled": False,
            "ticker": "SPY",
            "core_weight": 0.60,
            "satellite_weight": 0.40,
            "satellite_strategy": "12_month_absolute_momentum",
            "rebalance_mode": "independent_sleeves",
        }
    }

    assert get_core_satellite_config(config) is None


def test_get_core_satellite_config_rejects_non_independent_mode():
    config = {
        "core_satellite": {
            "enabled": True,
            "ticker": "SPY",
            "core_weight": 0.60,
            "satellite_weight": 0.40,
            "satellite_strategy": "12_month_absolute_momentum",
            "rebalance_mode": "annual",
        }
    }

    with pytest.raises(ValueError):
        get_core_satellite_config(config)