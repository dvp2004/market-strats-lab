import pytest

from market_strats.run_backtest import get_dual_momentum_pairs, get_tickers

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