from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge

from market_strats.global_multi_asset import gma7c_development_models as gma7c


def _price_panel(start: str = "2020-09-01", periods: int = 80) -> pd.DataFrame:
    sessions = pd.bdate_range(start, periods=periods)
    data = {}
    for idx, ticker in enumerate(gma7c.gma7b.CORE_22_UNIVERSE):
        drift = 0.001 + idx * 0.0002
        data[ticker] = [100.0 + idx + step * drift * 100.0 for step in range(periods)]
    panel = pd.DataFrame(data, index=sessions.date)
    return panel


def _feature_rows(decision: date, target_start: date) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "asset_ticker": gma7c.gma7b.PREDICTION_ASSETS,
            "decision_session_date": [decision] * len(gma7c.gma7b.PREDICTION_ASSETS),
            "target_start_session_date": [target_start] * len(gma7c.gma7b.PREDICTION_ASSETS),
        }
    )


def _regime_frame(decision: date = date(2020, 1, 31)) -> pd.DataFrame:
    rows = []
    for idx, ticker in enumerate(gma7c.gma7b.PREDICTION_ASSETS):
        row = {
            "asset_ticker": ticker,
            "decision_session_date": decision,
            "return_63d": float(idx),
            "return_126d": float(idx) * 0.5,
            "return_252d": float(idx) * 0.25,
            "realised_volatility_63d": float(len(gma7c.gma7b.PREDICTION_ASSETS) - idx),
            "drawdown_63d": -0.01 * idx,
            "correlation_to_spy_63d": 0.01 * idx,
            "spy_above_ma200": 1,
            "equity_breadth_above_ma200": 0.75,
            "credit_duration_spread_63d": 0.01,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def test_labels_use_next_session_start_and_twentieth_session_end():
    prices = _price_panel()
    sessions = list(prices.index)
    decision = sessions[5]
    features = _feature_rows(decision, sessions[6])

    labels = gma7c.build_development_labels(features, prices)

    assert labels["target_start_session"].nunique() == 1
    assert labels["target_start_session"].iloc[0] == sessions[6].isoformat()
    assert labels["target_end_session"].iloc[0] == sessions[26].isoformat()
    assert labels["future_downside_risk_20d"].notna().all()


def test_labels_are_development_only_and_do_not_enter_2021_targets():
    prices = _price_panel()
    sessions = list(prices.index)
    decision = sessions[10]
    labels = gma7c.build_development_labels(_feature_rows(decision, sessions[11]), prices)

    assert pd.to_datetime(labels["decision_session_date"]).dt.date.max() < gma7c.LOCKBOX_START
    assert pd.to_datetime(labels["target_end_session"]).dt.date.max() < date(2021, 1, 1)


def test_latest_eligible_decision_guard_prevents_2021_target_intervals():
    prices = _price_panel("2020-11-16", 50)
    sessions = list(prices.index)
    decision = sessions[20]

    assert decision > gma7c.LATEST_ELIGIBLE_DECISION
    with pytest.raises(gma7c.GMA7CDevelopmentError, match="development-only"):
        gma7c.build_development_labels(_feature_rows(decision, sessions[21]), prices)


def test_outer_and_inner_folds_have_at_least_twenty_session_embargo():
    prices = _price_panel("2008-05-01", 3300)
    outer = gma7c.outer_fold_registry(prices)
    assert outer["embargo_trading_sessions"].min() >= 20

    training_months = pd.period_range("2008-05", "2014-11", freq="M").astype(str).tolist()
    inner = gma7c.build_inner_folds(training_months, pd.DataFrame(), prices)
    assert inner
    assert min(fold["embargo_trading_sessions"] for fold in inner) >= 20
    assert all(len(fold["test_months"]) == 12 for fold in inner)


def test_model_grids_and_estimators_are_exact():
    assert gma7c._ridge_candidates() == [
        {"ridge_alpha": 0.1},
        {"ridge_alpha": 1.0},
        {"ridge_alpha": 10.0},
    ]
    assert len(gma7c._gbdt_candidates()) == 32

    ridge = gma7c._build_candidate_model(
        "regularised_linear_return_rank_model", {"ridge_alpha": 1.0}
    )
    tree = gma7c._build_candidate_model(
        "bounded_gradient_boosted_tree_return_rank_model",
        {
            "max_depth": 2,
            "learning_rate": 0.03,
            "n_estimators": 100,
            "min_samples_leaf": 10,
            "subsample": 0.7,
        },
    )
    assert isinstance(ridge, Ridge)
    assert isinstance(tree, GradientBoostingRegressor)
    assert tree.loss == "squared_error"
    assert tree.random_state == 7


def test_deterministic_regime_scores_use_formula_without_fit_parameters():
    frame = _regime_frame()
    scores = gma7c.deterministic_regime_scores(frame)

    assert scores["model_id"].unique().tolist() == ["deterministic_cross_asset_regime_model"]
    assert scores["risk_on_regime"].eq(True).all()
    assert scores["score"].nunique() > 1


def test_risk_model_is_not_a_return_model_component():
    assert "risk_downside_model" not in gma7c.RETURN_MODEL_IDS
    assert gma7c.RETURN_MODEL_IDS == [
        "regularised_linear_return_rank_model",
        "bounded_gradient_boosted_tree_return_rank_model",
        "deterministic_cross_asset_regime_model",
    ]


def test_portfolio_mapping_selects_top_five_positive_z_scores_and_bil_residual():
    decision = date(2020, 1, 31)
    scores = pd.DataFrame(
        {
            "decision_session_date": [decision] * len(gma7c.gma7b.PREDICTION_ASSETS),
            "asset_ticker": gma7c.gma7b.PREDICTION_ASSETS,
            "score": list(range(len(gma7c.gma7b.PREDICTION_ASSETS))),
        }
    )

    weights = gma7c.weights_from_scores(scores)[decision]

    selected = [ticker for ticker, weight in weights.items() if ticker != "BIL" and weight > 0]
    assert len(selected) == 5
    assert all(weights[ticker] == pytest.approx(0.2) for ticker in selected)
    assert weights["BIL"] == pytest.approx(0.0)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_benchmark_mapping_equal_weights_all_core22_including_bil():
    decision = date(2020, 1, 31)
    weights = gma7c.benchmark_equal_weight_mapping([decision])[decision]

    assert set(weights) == set(gma7c.gma7b.CORE_22_UNIVERSE)
    assert weights["BIL"] == pytest.approx(1.0 / 22.0)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_gate_board_handles_zero_positive_denominator_and_benchmark_drawdown():
    rows = []
    for fold_id in ["fold_1", "fold_2", "fold_3", "fold_4", "aggregate_outer_tests"]:
        rows.append(
            {
                "model_id": "regularised_linear_return_rank_model",
                "cost_scenario": "stressed_10bps",
                "outer_fold_id": fold_id,
                "net_active_return_vs_benchmark": -0.01,
                "maximum_drawdown": -0.12,
                "benchmark_maximum_drawdown": -0.10,
            }
        )

    gates = gma7c.component_gate_board(pd.DataFrame(rows))

    assert not gates.empty
    assert "denominator_zero" in set(gates["single_fold_share"])
    denominator_gate = gates[
        gates["gate_name"] == "maximum_single_fold_share_of_total_active_return_lte_0_50"
    ].iloc[0]
    assert denominator_gate["gate_status"] == "fail"


def test_metric_row_includes_benchmark_drawdown():
    equity = pd.DataFrame(
        {
            "valuation_date": [date(2020, 1, 1), date(2020, 1, 2)],
            "portfolio_value": [100.0, 101.0],
            "daily_return": [0.0, 0.01],
            "drawdown": [0.0, -0.01],
        }
    )
    result = type("Result", (), {"equity": equity, "costs": pd.DataFrame()})()
    benchmark = type("Result", (), {"equity": equity.copy(), "costs": pd.DataFrame()})()
    scores = pd.DataFrame(
        {
            "model_id": ["regularised_linear_return_rank_model"] * 2,
            "decision_session_date": [date(2020, 1, 1)] * 2,
            "score": [0.1, 0.2],
            "future_return_rank_20d": [0.0, 1.0],
        }
    )

    row = gma7c._metric_row(
        "regularised_linear_return_rank_model",
        "stressed_10bps",
        "fold_1",
        result,
        benchmark,
        date(2020, 1, 1),
        date(2020, 1, 2),
        scores,
    )

    assert row["benchmark_maximum_drawdown"] == pytest.approx(-0.01)


def test_source_imports_only_gma4_shared_replay_not_gma5_or_gma6_replay():
    source = Path(gma7c.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert any("gma4_replay_adapter" in module for module in imported)
    assert not any("gma5" in module or "gma6" in module for module in imported)
    assert not any(
        forbidden in module
        for module in imported
        for forbidden in ["yfinance", "broker", "live", "paper"]
    )


def test_contract_declares_no_equal_weight_ensemble_or_execution_decision():
    contract = gma7c.build_contract_yaml()

    assert contract["scope_boundaries"]["equal_weight_ensemble_built"] is False
    assert contract["scope_boundaries"]["candidate_or_promotion_decision_produced"] is False
    assert contract["scope_boundaries"]["paper_broker_or_live_path_created"] is False
    assert contract["model_blocks"]["risk_downside_model"]["risk_model_ridge_alpha"] == 1.0
