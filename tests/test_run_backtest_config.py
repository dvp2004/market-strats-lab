import pytest

from market_strats.run_backtest import get_tickers


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