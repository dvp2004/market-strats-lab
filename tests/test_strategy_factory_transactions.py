from pathlib import Path

import pandas as pd

from scripts.build_strategy_factory_transaction_notebook import build_notebook
from market_strats.analysis.strategy_factory_transactions import (
    create_drift_rebalance_ledger,
    create_transaction_ledger,
    save_strategy_factory_transaction_reports,
)


def _sample_allocation() -> pd.DataFrame:
    rows = []
    weights_by_date = {
        "2020-01-01": {"SPY": 0.0, "QQQ": 0.0, "CASH": 1.0},
        "2020-01-02": {"SPY": 0.5, "QQQ": 0.0, "CASH": 0.5},
        "2020-01-03": {"SPY": 0.7, "QQQ": 0.2, "CASH": 0.1},
        "2020-01-04": {"SPY": 0.3, "QQQ": 0.2, "CASH": 0.5},
        "2020-01-05": {"SPY": 0.0, "QQQ": 0.2, "CASH": 0.8},
    }
    for date, weights in weights_by_date.items():
        for asset, weight in weights.items():
            rows.append(
                {
                    "date": date,
                    "strategy": "test_strategy",
                    "asset": asset,
                    "weight": weight,
                }
            )
    return pd.DataFrame(rows)


def _constant_6040_allocation() -> pd.DataFrame:
    rows = []
    for date in ["2020-01-02", "2020-02-03"]:
        for asset, weight in {"SPY": 0.6, "QQQ": 0.4, "CASH": 0.0}.items():
            rows.append(
                {
                    "date": date,
                    "strategy": "sf_spy_qqq_60_40_monthly_rebalanced",
                    "asset": asset,
                    "weight": weight,
                }
            )
    return pd.DataFrame(rows)


def _constant_6040_returns() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2020-01-02", "SPY": 0.0, "QQQ": 0.0, "CASH": 0.0},
            {"date": "2020-02-03", "SPY": 0.0, "QQQ": 0.10, "CASH": 0.0},
        ]
    )


def test_transaction_ledger_classifies_weight_changes():
    ledger = create_transaction_ledger(_sample_allocation())

    assert "BUY_ENTRY" in set(ledger["transaction_direction"])
    assert "BUY_INCREASE" in set(ledger["transaction_direction"])
    assert "SELL_REDUCE" in set(ledger["transaction_direction"])
    assert "SELL_EXIT" in set(ledger["transaction_direction"])
    assert "CASH_ALLOCATION_CHANGE" in set(ledger["transaction_direction"])

    spy_entry = ledger.loc[
        (ledger["rebalance_date"] == "2020-01-02") & (ledger["asset"] == "SPY")
    ].iloc[0]
    assert spy_entry["transaction_direction"] == "BUY_ENTRY"
    assert bool(spy_entry["is_entry"])
    assert bool(spy_entry["is_buy"])

    spy_exit = ledger.loc[
        (ledger["rebalance_date"] == "2020-01-05") & (ledger["asset"] == "SPY")
    ].iloc[0]
    assert spy_exit["transaction_direction"] == "SELL_EXIT"
    assert bool(spy_exit["is_exit"])
    assert bool(spy_exit["is_sell"])


def test_transaction_ledger_skips_unchanged_weights():
    ledger = create_transaction_ledger(_sample_allocation())

    unchanged_qqq = ledger.loc[
        (ledger["rebalance_date"] == "2020-01-04") & (ledger["asset"] == "QQQ")
    ]
    assert unchanged_qqq.empty


def test_transaction_ledger_uses_signed_notional_per_10000():
    ledger = create_transaction_ledger(_sample_allocation(), notional=10000)

    buy_spy = ledger.loc[
        (ledger["rebalance_date"] == "2020-01-02") & (ledger["asset"] == "SPY")
    ].iloc[0]
    reduce_spy = ledger.loc[
        (ledger["rebalance_date"] == "2020-01-04") & (ledger["asset"] == "SPY")
    ].iloc[0]

    assert buy_spy["estimated_notional_change_per_10000"] == 5000.0
    assert reduce_spy["estimated_notional_change_per_10000"] == -4000.0


def test_cash_allocation_changes_are_labelled_separately():
    ledger = create_transaction_ledger(_sample_allocation())
    cash_rows = ledger.loc[ledger["asset"] == "CASH"]

    assert not cash_rows.empty
    assert set(cash_rows["transaction_direction"]) == {"CASH_ALLOCATION_CHANGE"}
    assert set(cash_rows["transaction_type"]) == {"cash_allocation_change"}
    assert not bool(cash_rows["is_buy"].any())
    assert not bool(cash_rows["is_sell"].any())


def test_constant_target_6040_creates_drift_rebalance_trades():
    drift = create_drift_rebalance_ledger(
        _constant_6040_allocation(),
        _constant_6040_returns(),
    )

    assert len(drift) == 2
    spy = drift.loc[drift["asset"] == "SPY"].iloc[0]
    qqq = drift.loc[drift["asset"] == "QQQ"].iloc[0]
    assert spy["transaction_direction"] == "BUY_TO_TARGET"
    assert qqq["transaction_direction"] == "SELL_TO_TARGET"
    assert spy["estimated_trade_notional_per_10000"] == 230.77
    assert qqq["estimated_trade_notional_per_10000"] == -230.77


def test_no_drift_rebalance_trade_below_tolerance():
    returns = pd.DataFrame(
        [
            {"date": "2020-01-02", "SPY": 0.0, "QQQ": 0.0, "CASH": 0.0},
            {"date": "2020-02-03", "SPY": 0.0, "QQQ": 0.0, "CASH": 0.0},
        ]
    )
    drift = create_drift_rebalance_ledger(
        _constant_6040_allocation(),
        returns,
        tolerance=1e-6,
    )

    assert drift.empty


def test_cash_drift_rebalance_changes_are_labelled():
    allocation = pd.DataFrame(
        [
            {"date": "2020-01-02", "strategy": "cash_test", "asset": "SPY", "weight": 0.5},
            {"date": "2020-01-02", "strategy": "cash_test", "asset": "CASH", "weight": 0.5},
            {"date": "2020-02-03", "strategy": "cash_test", "asset": "SPY", "weight": 0.5},
            {"date": "2020-02-03", "strategy": "cash_test", "asset": "CASH", "weight": 0.5},
        ]
    )
    returns = pd.DataFrame(
        [
            {"date": "2020-01-02", "SPY": 0.0, "CASH": 0.0},
            {"date": "2020-02-03", "SPY": 0.10, "CASH": 0.0},
        ]
    )

    drift = create_drift_rebalance_ledger(allocation, returns)
    cash = drift.loc[drift["asset"] == "CASH"].iloc[0]

    assert cash["transaction_direction"] == "CASH_REBALANCE_CHANGE"
    assert cash["estimated_trade_notional_per_10000"] == 238.1
    assert not bool(cash["is_buy"])
    assert not bool(cash["is_sell"])


def test_drift_ledger_is_separate_from_target_weight_change_ledger():
    target = create_transaction_ledger(_constant_6040_allocation())
    drift = create_drift_rebalance_ledger(
        _constant_6040_allocation(),
        _constant_6040_returns(),
    )

    assert set(target["transaction_direction"]) == {"BUY_ENTRY"}
    assert set(drift["transaction_direction"]) == {"BUY_TO_TARGET", "SELL_TO_TARGET"}
    assert "pre_rebalance_weight" in drift.columns
    assert "previous_weight" in target.columns


def test_save_strategy_factory_transaction_reports_writes_outputs(tmp_path: Path):
    allocation_file = tmp_path / "allocation_timeline.csv"
    output_dir = tmp_path / "reports" / "strategy_factory" / "transactions"
    watchlist_file = tmp_path / "watchlist.csv"
    allocation = pd.concat(
        [
            _sample_allocation(),
            _sample_allocation().assign(strategy="second_strategy"),
        ],
        ignore_index=True,
    )
    allocation.to_csv(allocation_file, index=False)
    pd.DataFrame({"candidate_id": ["test_strategy"]}).to_csv(watchlist_file, index=False)

    outputs = save_strategy_factory_transaction_reports(
        allocation_file=allocation_file,
        output_dir=output_dir,
        watchlist_file=watchlist_file,
        asset_returns=pd.DataFrame(
            [
                {"date": "2020-01-01", "SPY": 0.0, "QQQ": 0.0, "CASH": 0.0},
                {"date": "2020-01-02", "SPY": 0.01, "QQQ": 0.0, "CASH": 0.0},
                {"date": "2020-01-03", "SPY": 0.01, "QQQ": 0.02, "CASH": 0.0},
                {"date": "2020-01-04", "SPY": -0.01, "QQQ": 0.0, "CASH": 0.0},
                {"date": "2020-01-05", "SPY": 0.0, "QQQ": 0.0, "CASH": 0.0},
            ]
        ),
    )

    assert not outputs["ledger"].empty
    assert "drift_rebalance_ledger" in outputs
    for path in [
        output_dir / "strategy_transaction_ledger.csv",
        output_dir / "strategy_rebalance_summary.csv",
        output_dir / "strategy_weight_change_events.csv",
        output_dir / "strategy_turnover_timeline.csv",
        output_dir / "strategy_asset_allocation_long.csv",
        output_dir / "strategy_latest_allocations.csv",
        output_dir / "strategy_drift_rebalance_ledger.csv",
        output_dir / "strategy_drift_rebalance_summary.csv",
        output_dir / "strategy_rebalance_trade_matrix.csv",
        output_dir / "strategy_transaction_dashboard_index.md",
        output_dir / "charts" / "allocation_timeline_by_strategy.png",
        output_dir / "charts" / "turnover_timeline_by_strategy.png",
        output_dir / "charts" / "transaction_count_by_asset.png",
        output_dir / "charts" / "latest_allocation_snapshot.png",
        output_dir / "charts" / "btc_weight_timeline.png",
        output_dir / "charts" / "drift_rebalance_trades_by_strategy.png",
        output_dir / "charts" / "drift_rebalance_trades_by_asset.png",
        output_dir / "charts" / "drift_rebalance_notional_by_asset.png",
        output_dir / "charts" / "spy_qqq_60_40_rebalance_timeline.png",
    ]:
        assert path.exists()

    index_text = (output_dir / "strategy_transaction_dashboard_index.md").read_text(
        encoding="utf-8"
    )
    assert "Live trading allowed: False" in index_text
    assert "Real money allowed: False" in index_text
    assert "Broker/API integration allowed: False" in index_text


def test_notebook_builder_writes_valid_ipynb(tmp_path: Path):
    notebook_path = build_notebook(tmp_path / "phase17c_strategy_factory_transaction_visuals.ipynb")

    assert notebook_path.exists()
    text = notebook_path.read_text(encoding="utf-8")
    assert '"nbformat": 4' in text
    assert "Target-weight changes vs actual rebalance trades" in text
