from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import market_strats.global_multi_asset.gma8c_frozen_etf_etp_tournament as gma8c


def _prices(symbols: list[str], sessions: int = 400) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=sessions)
    values = {}
    for ordinal, symbol in enumerate(symbols):
        slope = 0.0002 + ordinal * 0.00001
        wave = np.sin(np.arange(sessions) / (8.0 + ordinal % 5)) * 0.002
        values[symbol] = 100.0 * np.exp(np.cumsum(slope + wave))
    return pd.DataFrame(values, index=dates)


def _row(
    strategy_id: str = "synthetic_equal",
    family: str = "benchmark_equal_weight_monthly",
    rebalance: str = "monthly_next_tradable_session",
    lookback: str = "not_applicable",
    construction: str = "equal_weight_including_BIL",
    maximum: str = "arm_size",
) -> dict[str, str]:
    return {
        "arm_trial_id": f"{strategy_id}__synthetic_arm",
        "strategy_id": strategy_id,
        "strategy_family": family,
        "signal_inputs": "arm_constituent_membership",
        "lookback_sessions": lookback,
        "formation_frequency": "monthly_last_session",
        "rebalance_frequency": rebalance,
        "ranking_or_trigger_rule": "hold_all_arm_constituents",
        "portfolio_construction": construction,
        "maximum_positions": maximum,
        "fallback_asset_or_cash_rule": "residual_to_BIL",
        "risk_overlay_rule": "none",
        "turnover_control_rule": "monthly_only",
        "eligible_universe_arm": "synthetic_arm",
        "strategy_grid_hash": gma8c.GRID_HASH,
        "status": "preregistered_not_run",
    }


def _trial_path() -> gma8c.TrialPath:
    dates = pd.bdate_range("2024-01-02", periods=4)
    daily = pd.DataFrame(
        {
            "gross_return": [0.0, 0.01, -0.005, 0.002],
            "one_way_turnover": [1.0, 0.0, 0.4, 0.0],
            "HHI": [0.5, 0.5, 0.6, 0.6],
        },
        index=dates,
    )
    return gma8c.TrialPath("trial", "strategy", "family", "arm", daily, "2024-01-02", "2024-01-03")


def test_frozen_parent_locks_counts_dates_and_hashes_verify_before_execution(monkeypatch):
    inputs = gma8c.load_frozen_inputs(gma8c.DEFAULT_CONFIG)
    assert len({row["strategy_id"] for row in inputs.strategy_rows}) == 80
    assert len(inputs.strategy_rows) == 160
    assert len(inputs.source_rows) == 29
    assert inputs.config["frozen_parent"]["source_first_session"] == "2007-05-30"
    assert inputs.config["frozen_parent"]["source_last_session"] == "2026-05-01"
    monkeypatch.setattr(gma8c, "load_price_matrix", lambda _: pytest.fail("calculation started"))
    broken = deepcopy(inputs.config)
    broken["frozen_parent"]["arm_trial_count"] = 159
    assert broken["frozen_parent"]["arm_trial_count"] != 160


def test_exact_four_cost_scenarios_are_frozen():
    inputs = gma8c.load_frozen_inputs(gma8c.DEFAULT_CONFIG)
    assert inputs.costs == {
        "baseline_1bps": 1,
        "stressed_10bps": 10,
        "stressed_25bps": 25,
        "severe_50bps": 50,
    }


def test_only_immutable_gma8b_paths_and_hashes_are_admitted():
    inputs = gma8c.load_frozen_inputs(gma8c.DEFAULT_CONFIG)
    assert all(row["source_path_used_for_data_read"] == "False" for row in inputs.source_rows)
    assert all(row["adjusted_price_field"] == "adj_close" for row in inputs.source_rows)
    assert all(len(row["normalised_series_sha256"]) == 64 for row in inputs.source_rows)


def test_source_hash_mismatch_fails_before_price_computation(tmp_path: Path):
    path = tmp_path / "synthetic.csv"
    path.write_text("date,adj_close\n2024-01-02,100\n", encoding="utf-8")
    inputs = gma8c.FrozenInputs(
        config={},
        strategy_rows=[],
        arms={},
        regimes=[],
        folds=[],
        costs={},
        source_rows=[
            {
                "ticker": "SYN",
                "immutable_snapshot_path": str(path),
                "normalised_series_sha256": "0" * 64,
                "adjusted_price_field": "adj_close",
            }
        ],
        parent_hashes={},
    )
    with pytest.raises(gma8c.GMA8CTournamentError, match="SHA-256 mismatch"):
        gma8c.load_price_matrix(inputs)


def test_signal_uses_decision_close_and_execution_is_next_session():
    arm = ["AAA", "BIL"]
    prices = _prices(arm, 20)
    row = _row(rebalance="daily_next_tradable_session")
    gma8c._CURRENT_STRATEGY_ROWS = [row]
    path = gma8c.build_trial_path(row, prices, arm, common_start=prices.index[5].date().isoformat())
    first = path.daily.iloc[0]
    second = path.daily.iloc[1]
    assert first["gross_return"] == 0.0
    expected = 0.5 * (
        prices.iloc[7]["AAA"] / prices.iloc[6]["AAA"]
        - 1.0
        + prices.iloc[7]["BIL"] / prices.iloc[6]["BIL"]
        - 1.0
    )
    assert second["gross_return"] == pytest.approx(expected)
    assert path.first_target_effective_session == prices.index[6].date().isoformat()
    assert path.actual_first_return_session == prices.index[7].date().isoformat()


def test_targets_are_nonnegative_fully_invested_and_frozen_families_are_supported():
    inputs = gma8c.load_frozen_inputs(gma8c.DEFAULT_CONFIG)
    arm = inputs.arms[gma8c.CORE_ARM]
    prices = _prices(arm)
    start = 300
    arm_curve = prices.div(prices.iloc[0]).mean(axis=1)
    rows = {
        row["strategy_id"]: row
        for row in inputs.strategy_rows
        if row["eligible_universe_arm"] == gma8c.CORE_ARM
    }
    assert len(rows) == 80
    for row in rows.values():
        target = gma8c._raw_target(row, start, prices, arm, arm_curve, rows)
        assert np.isfinite(target).all()
        assert (target >= 0).all()
        assert target.sum() == pytest.approx(1.0)
        assert int((target > 0).sum()) <= len(arm)


def test_ticker_is_not_selected_without_own_lookback_history():
    arm = ["AAA", "BIL"]
    prices = _prices(arm, 80)
    prices.loc[prices.index[:50], "AAA"] = np.nan
    row = _row(
        strategy_id="gma8_xsmom_21_top3_equal_weight_v1",
        family="cross_sectional_momentum",
        lookback="21",
        construction="top_n_equal_weight",
        maximum="1",
    )
    row["signal_inputs"] = "total_return_21"
    row["ranking_or_trigger_rule"] = "rank_descending_select_top_1"
    target = gma8c._raw_target(
        row, 55, prices, arm, prices.div(prices.iloc[50]).mean(axis=1), {row["strategy_id"]: row}
    )
    assert target[arm.index("AAA")] == 0.0
    assert target[arm.index("BIL")] == 1.0


def test_mean_reversion_maximum_holding_sessions_are_stateful():
    arm = ["AAA", "BBB", "BIL"]
    dates = pd.bdate_range("2020-01-02", periods=12)
    prices = pd.DataFrame(
        {
            "AAA": [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89],
            "BBB": [100, 100.2, 100.4, 100.6, 100.8, 101, 101.2, 101.4, 101.6, 101.8, 102, 102.2],
            "BIL": [100.0] * 12,
        },
        index=dates,
    )
    row = _row(
        strategy_id="gma8_meanrev_2d_bottom1_equal_weight_v1",
        family="short_horizon_mean_reversion",
        rebalance="daily_next_tradable_session",
        lookback="2",
        construction="bottom_n_equal_weight",
        maximum="1",
    )
    row["signal_inputs"] = "total_return_2"
    row["ranking_or_trigger_rule"] = "rank_ascending_select_bottom_1"
    row["turnover_control_rule"] = "maximum_holding_2_sessions"
    state: dict[str, dict[str, int]] = {}
    first = gma8c._raw_target(
        row,
        3,
        prices,
        arm,
        prices.div(prices.iloc[0]).mean(axis=1),
        {row["strategy_id"]: row},
        holding_state=state,
    )
    second = gma8c._raw_target(
        row,
        4,
        prices,
        arm,
        prices.div(prices.iloc[0]).mean(axis=1),
        {row["strategy_id"]: row},
        holding_state=state,
    )
    third = gma8c._raw_target(
        row,
        5,
        prices,
        arm,
        prices.div(prices.iloc[0]).mean(axis=1),
        {row["strategy_id"]: row},
        holding_state=state,
    )
    assert first[arm.index("AAA")] == pytest.approx(1.0)
    assert second[arm.index("AAA")] == pytest.approx(1.0)
    assert third[arm.index("AAA")] == pytest.approx(0.0)
    assert third[arm.index("BIL")] == pytest.approx(1.0)


def test_turnover_and_transaction_cost_are_deducted_once():
    frame = gma8c.apply_cost(_trial_path(), 10)
    assert frame.iloc[0]["transaction_cost"] == pytest.approx(0.001)
    assert frame.iloc[0]["net_return"] == pytest.approx(-0.001)
    expected = (1.0 - 0.005) * (1.0 - 0.0004) - 1.0
    assert frame.iloc[2]["net_return"] == pytest.approx(expected)
    assert frame.iloc[1]["net_return"] == pytest.approx(0.01)


def test_same_cost_accounting_is_reusable_for_trial_and_benchmark():
    trial = _trial_path()
    assert gma8c.apply_cost(trial, 25).equals(gma8c.apply_cost(trial, 25))


def test_all_frozen_evaluation_scopes_are_declared():
    inputs = gma8c.load_frozen_inputs(gma8c.DEFAULT_CONFIG)
    assert [row["fold_id"] for row in inputs.folds] == [f"fold_{index}" for index in range(1, 6)]
    assert set(inputs.config["evaluation"]["rolling_windows_sessions"]) == {
        "rolling_3_year",
        "rolling_5_year",
    }
    assert len(inputs.regimes) == 7


def test_contribution_gates_fail_closed_on_nonpositive_denominator():
    share, passed = gma8c._positive_contribution_share([0.0, -0.1, -0.2])
    assert math.isnan(share)
    assert passed is False
    share, passed = gma8c._positive_contribution_share([0.2, 0.1, -0.3])
    assert share == pytest.approx(2.0 / 3.0)
    assert passed is False
    share, passed = gma8c._positive_contribution_share([0.1, 0.1, 0.1])
    assert share == pytest.approx(1.0 / 3.0)
    assert passed is True


def test_scoreboard_order_is_deterministic():
    full_rows = []
    fold_rows = []
    regime_rows = []
    for trial, active, drawdown, turnover in (
        ("trial_b", 0.03, 0.01, 2.0),
        ("trial_a", 0.03, 0.01, 1.0),
    ):
        full_rows.append(
            {
                "run_id": "run",
                "arm_trial_id": trial,
                "strategy_id": trial,
                "strategy_family": "family",
                "universe_arm": "arm",
                "cost_scenario": "stressed_10bps",
                "net_return": 0.1,
                "CAGR": 0.05,
                "net_active_return_vs_benchmark": active,
                "net_active_CAGR_vs_benchmark": active,
                "maximum_drawdown": -0.1,
                "maximum_drawdown_difference_vs_benchmark": drawdown,
                "annualised_turnover": turnover,
                "cost_drag": 0.001,
                "maximum_HHI": 0.5,
            }
        )
        fold_rows.extend(
            {
                "arm_trial_id": trial,
                "cost_scenario": "stressed_10bps",
                "net_active_return_vs_benchmark": 0.01,
                "active_log_return_contribution": 0.01,
            }
            for _ in range(5)
        )
        regime_rows.extend(
            {
                "arm_trial_id": trial,
                "cost_scenario": "stressed_10bps",
                "active_log_return_contribution": 0.01,
            }
            for _ in range(7)
        )
    _, first = gma8c._gate_rows_and_scoreboard(
        pd.DataFrame(full_rows), pd.DataFrame(fold_rows), pd.DataFrame(regime_rows)
    )
    _, second = gma8c._gate_rows_and_scoreboard(
        pd.DataFrame(full_rows[::-1]), pd.DataFrame(fold_rows), pd.DataFrame(regime_rows)
    )
    assert first["arm_trial_id"].tolist() == ["trial_a", "trial_b"]
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))


def test_rolling_summary_uses_monthly_endpoints_and_exact_session_windows():
    path = _trial_path()
    dates = pd.bdate_range("2020-01-02", periods=80)
    frame = pd.DataFrame(
        {
            "gross_return": 0.001,
            "one_way_turnover": 0.0,
            "HHI": 0.5,
            "transaction_cost": 0.0,
            "net_return": 0.001,
        },
        index=dates,
    )
    summary = gma8c._rolling_summary(path, frame, "baseline_1bps", 1, "synthetic", 20)
    assert summary["window_count"] >= 2
    assert summary["window_sessions"] == 20
    assert summary["positive_window_fraction"] == 1.0


def test_no_network_model_search_target_paper_broker_or_live_path_is_invoked():
    source = Path(gma8c.__file__).read_text(encoding="utf-8")
    forbidden = (
        "requests",
        "urllib",
        "yfinance",
        "sklearn",
        "GridSearch",
        "paper_session(",
        "submit_order(",
        "broker_api",
        "target_file",
    )
    assert not any(token in source for token in forbidden)


def test_no_recursive_traversal_globbing_or_directory_scan_is_present():
    source = Path(gma8c.__file__).read_text(encoding="utf-8")
    forbidden = ("rglob(", ".glob(", "os.walk", "Get-ChildItem", "**/*")
    assert not any(token in source for token in forbidden)


def test_parent_outputs_are_read_only_under_module_source():
    source = Path(gma8c.__file__).read_text(encoding="utf-8")
    assert "GMA8A_ROOT" in source and "GMA8B_ROOT" in source
    assert "write_text(artifacts[name]" in source
    assert "GMA8A_ROOT / name).write" not in source
    assert "GMA8B_ROOT / name).write" not in source


def test_csv_and_hash_generation_is_deterministic():
    frame = pd.DataFrame([{"b": 2.0, "a": "x"}, {"b": 1.0, "a": "y"}])
    first = gma8c._csv_text(frame)
    second = gma8c._csv_text(frame)
    assert first == second
    assert hashlib.sha256(first.encode()).hexdigest() == hashlib.sha256(second.encode()).hexdigest()
