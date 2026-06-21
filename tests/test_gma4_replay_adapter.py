from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from market_strats.global_multi_asset.gma3a_tournament import _simulate_strategy, strategy_targets
from market_strats.global_multi_asset.gma4_contract import FIXED_GMA4_UNIVERSE
from market_strats.global_multi_asset.gma4_replay_adapter import (
    GMA4ReplayAdapterError,
    run_gma4_replay_adapter,
)


def _minimal_config() -> Any:
    return SimpleNamespace(
        raw={
            "capital": {"account_starting_capital": 100000.0},
            "costs": {"bps_per_notional": 1.0},
            "limits": {
                "minimum_trade_notional": 1.0,
                "maximum_single_asset_weight": 1.0,
                "maximum_bitcoin_weight": 0.0,
            },
            "strategy_universe": {
                "balanced_benchmark_weights": {"SPY": 0.6, "IEF": 0.4},
            },
        }
    )


def _business_dates() -> list[Any]:
    return pd.bdate_range("2026-01-05", "2026-02-06").date.tolist()


def _cash(dates: list[Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "accrual_start": dates[idx - 1],
                "accrual_end": dates[idx],
                "period_return": 0.0,
            }
            for idx in range(1, len(dates))
        ]
    )


def _price_frame(dates: list[Any], offset: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close_raw": [100.0 + offset + idx for idx, _date in enumerate(dates)],
            "total_return_index": [100.0 + offset + idx for idx, _date in enumerate(dates)],
        },
        index=dates,
    )


def _gma3a_prices() -> dict[str, pd.DataFrame]:
    dates = _business_dates()
    return {
        "SPY": _price_frame(dates, 0.0),
        "IEF": _price_frame(dates, 10.0),
    }


def _gma4_prices() -> dict[str, pd.DataFrame]:
    dates = _business_dates()
    return {
        symbol: _price_frame(dates, float(idx)) for idx, symbol in enumerate(FIXED_GMA4_UNIVERSE)
    }


def _spy_resolver(_signal_date: Any, _prices: dict[str, pd.DataFrame]) -> dict[str, float]:
    return {"SPY": 1.0}


def _assert_frame_equal(left: pd.DataFrame, right: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(
        left.reset_index(drop=True),
        right.reset_index(drop=True),
        check_dtype=False,
        check_like=True,
    )


def test_gma3a_default_replay_matches_injected_default_delegate_resolver():
    prices = _gma3a_prices()
    dates = _business_dates()
    cash = _cash(dates)
    config = _minimal_config()
    macro = pd.DataFrame()

    default = _simulate_strategy("gma_spy_benchmark_v0", dates, prices, cash, macro, config)
    injected = _simulate_strategy(
        "gma_spy_benchmark_v0",
        dates,
        prices,
        cash,
        macro,
        config,
        target_resolver=strategy_targets,
    )

    for ledger_name in ["equity", "drawdown", "holdings", "orders", "fills", "costs", "signals"]:
        _assert_frame_equal(default[ledger_name], injected[ledger_name])


def test_gma3a_default_strategy_ids_flags_costs_and_schemas_remain_unchanged():
    prices = _gma3a_prices()
    dates = _business_dates()
    outputs = _simulate_strategy(
        "gma_spy_benchmark_v0",
        dates,
        prices,
        _cash(dates),
        pd.DataFrame(),
        _minimal_config(),
    )

    assert set(outputs) == {"equity", "drawdown", "holdings", "orders", "fills", "costs", "signals"}
    assert set(outputs["equity"]["strategy_id"]) == {"gma_spy_benchmark_v0"}
    assert set(outputs["signals"]["strategy_version"]) == {"v0"}
    assert outputs["orders"]["paper_only"].all()
    assert not outputs["orders"]["live_trading_allowed"].any()
    assert not outputs["orders"]["real_money_allowed"].any()
    assert outputs["costs"]["charged_once"].all()
    assert (outputs["costs"]["transaction_cost"] >= 0).all()


def test_gma4_adapter_uses_shared_path_and_produces_ledgers():
    dates = _business_dates()
    result = run_gma4_replay_adapter(
        prices=_gma4_prices(),
        cash=_cash(dates),
        macro=pd.DataFrame(),
        target_resolver=_spy_resolver,
        rebalance_schedule="weekly_friday_next_open",
    )

    assert not result.equity.empty
    assert not result.drawdown.empty
    assert not result.holdings.empty
    assert not result.orders.empty
    assert not result.fills.empty
    assert not result.costs.empty
    assert not result.signals.empty
    assert set(result.signals["strategy_id"]) == {"gma4_synthetic_adapter_trial"}
    assert set(result.signals["strategy_version"]) == {"test_only_v0"}


def test_gma4_adapter_rejects_missing_fixed_universe_member():
    prices = _gma4_prices()
    prices.pop("DBC")
    with pytest.raises(GMA4ReplayAdapterError, match="missing fixed GMA-4 ETF"):
        run_gma4_replay_adapter(
            prices=prices,
            cash=_cash(_business_dates()),
            macro=pd.DataFrame(),
            target_resolver=_spy_resolver,
            rebalance_schedule="weekly_friday_next_open",
        )


@pytest.mark.parametrize("forbidden", ["BTC-USD", "SHY", "VNQ", "AAPL"])
def test_gma4_adapter_rejects_forbidden_target_symbols(forbidden: str):
    def bad_resolver(_signal_date: Any, _prices: dict[str, pd.DataFrame]) -> dict[str, float]:
        return {forbidden: 1.0}

    with pytest.raises(GMA4ReplayAdapterError, match="forbidden GMA-4 target symbols"):
        run_gma4_replay_adapter(
            prices=_gma4_prices(),
            cash=_cash(_business_dates()),
            macro=pd.DataFrame(),
            target_resolver=bad_resolver,
            rebalance_schedule="weekly_friday_next_open",
        )


def test_gma4_adapter_rejects_duplicate_dates():
    prices = _gma4_prices()
    dates = _business_dates()
    duplicate = pd.DataFrame(
        {
            "date": [dates[0], dates[0]],
            "close_raw": [100.0, 101.0],
            "total_return_index": [100.0, 101.0],
        }
    )
    prices["SPY"] = duplicate
    with pytest.raises(GMA4ReplayAdapterError, match="duplicate dates"):
        run_gma4_replay_adapter(
            prices=prices,
            cash=_cash(dates),
            macro=pd.DataFrame(),
            target_resolver=_spy_resolver,
            rebalance_schedule="weekly_friday_next_open",
        )


def test_gma4_adapter_rejects_null_required_price():
    prices = _gma4_prices()
    prices["SPY"] = prices["SPY"].copy()
    prices["SPY"].iloc[0, prices["SPY"].columns.get_loc("close_raw")] = pd.NA
    with pytest.raises(GMA4ReplayAdapterError, match="null required price"):
        run_gma4_replay_adapter(
            prices=prices,
            cash=_cash(_business_dates()),
            macro=pd.DataFrame(),
            target_resolver=_spy_resolver,
            rebalance_schedule="weekly_friday_next_open",
        )


def test_gma4_adapter_rejects_non_positive_total_return_index():
    prices = _gma4_prices()
    prices["SPY"] = prices["SPY"].copy()
    prices["SPY"].iloc[0, prices["SPY"].columns.get_loc("total_return_index")] = 0.0
    with pytest.raises(GMA4ReplayAdapterError, match="non-positive required price"):
        run_gma4_replay_adapter(
            prices=prices,
            cash=_cash(_business_dates()),
            macro=pd.DataFrame(),
            target_resolver=_spy_resolver,
            rebalance_schedule="weekly_friday_next_open",
        )


def test_weekly_friday_decisions_execute_next_valid_session_open_not_same_close():
    dates = _business_dates()
    result = run_gma4_replay_adapter(
        prices=_gma4_prices(),
        cash=_cash(dates),
        macro=pd.DataFrame(),
        target_resolver=_spy_resolver,
        rebalance_schedule="weekly_friday_next_open",
    )

    assert result.signal_dates
    assert all(pd.Timestamp(date).dayofweek == 4 for date in result.signal_dates)
    for signal_date, execution_date in zip(result.signal_dates, result.execution_dates):
        assert execution_date > signal_date
        assert execution_date != signal_date


def test_monthly_last_session_decisions_execute_next_valid_session_open_not_same_close():
    dates = _business_dates()
    result = run_gma4_replay_adapter(
        prices=_gma4_prices(),
        cash=_cash(dates),
        macro=pd.DataFrame(),
        target_resolver=_spy_resolver,
        rebalance_schedule="monthly_last_session_next_open",
    )

    assert result.signal_dates == [pd.Timestamp("2026-01-30").date()]
    assert result.execution_dates == [pd.Timestamp("2026-02-02").date()]


def test_gma4_adapter_has_no_file_report_packet_broker_or_prospective_side_effects(tmp_path: Path):
    before = set(tmp_path.rglob("*"))
    run_gma4_replay_adapter(
        prices=_gma4_prices(),
        cash=_cash(_business_dates()),
        macro=pd.DataFrame(),
        target_resolver=_spy_resolver,
        rebalance_schedule="weekly_friday_next_open",
    )
    after = set(tmp_path.rglob("*"))
    assert after == before


def test_gma4_adapter_creates_no_candidate_or_strategy_performance_claim():
    result = run_gma4_replay_adapter(
        prices=_gma4_prices(),
        cash=_cash(_business_dates()),
        macro=pd.DataFrame(),
        target_resolver=_spy_resolver,
        rebalance_schedule="weekly_friday_next_open",
    )

    assert "candidate" not in "".join(result.signals.columns).lower()
    assert "performance_claim" not in "".join(result.equity.columns).lower()
