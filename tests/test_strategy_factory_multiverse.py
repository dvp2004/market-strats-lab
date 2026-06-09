from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.strategy_factory_multiverse import (
    add_phase19a_scores,
    build_phase19a_finalist_classifications,
    build_multiverse_price_panel,
    fixed_allocation_candidate_specs,
    parse_universe_config,
    run_inverse_vol_candidate,
    run_top_k_momentum_candidate,
    save_phase19a_strategy_factory_multiverse,
)


def _price_frame(symbol: str, *, periods: int = 900, daily_return: float = 0.0005) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=periods)
    seasonal = np.sin(np.arange(periods) / 31.0) * 0.002
    returns = daily_return + seasonal
    if symbol == "BTC-USD":
        returns = daily_return + np.sin(np.arange(periods) / 19.0) * 0.006
    prices = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame({"date": dates, "adj_close": prices})


def _price_data() -> dict[str, pd.DataFrame]:
    return {
        "SPY": _price_frame("SPY", daily_return=0.00035),
        "QQQ": _price_frame("QQQ", daily_return=0.00055),
        "GLD": _price_frame("GLD", daily_return=0.00015),
        "TLT": _price_frame("TLT", daily_return=0.00005),
        "BTC-USD": _price_frame("BTC-USD", daily_return=0.0010),
    }


def _phase19a_config(tmp_path: Path) -> dict:
    output_dir = tmp_path / "multiverse"
    return {
        "start_date": "2020-01-01",
        "end_date": "2024-12-31",
        "phase19a_strategy_factory_multiverse": {
            "enabled": True,
            "output_dir": str(output_dir),
            "dashboard_dir": str(output_dir / "dashboard"),
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "initial_capital": 10000,
            "universes": {
                "core_us_growth": {
                    "symbols": ["SPY", "QQQ", "CASH"],
                    "allow_btc": False,
                },
                "btc_capped_growth": {
                    "symbols": ["SPY", "QQQ", "BTC-USD", "CASH"],
                    "allow_btc": True,
                    "btc_caps": [0.05],
                },
                "missing_symbol_universe": {
                    "symbols": ["SPY", "QQQ", "IWM", "CASH"],
                    "allow_btc": False,
                },
            },
            "evaluation_periods": {
                "full_common": {"start": None, "end": None},
                "post_2021": {"start": "2021-01-01", "end": None},
            },
            "objective_weights": {
                "cagr_weight": 0.40,
                "calmar_weight": 0.30,
                "max_drawdown_weight": 0.20,
                "turnover_penalty_weight": 0.10,
            },
            "finalist_rules": {
                "require_positive_cagr_edge_vs_spy": True,
                "max_drawdown_worse_than_spy_allowed_pp": 5,
                "min_rolling_3y_beat_spy_pct": 60,
                "require_no_live_flags": True,
            },
        },
    }


def test_universe_config_parsing_adds_cash_and_btc_caps():
    section = {
        "universes": {
            "btc": {
                "symbols": ["SPY", "BTC-USD"],
                "allow_btc": True,
                "btc_caps": [0.05, 0.10],
            }
        }
    }

    parsed = parse_universe_config(section)

    assert parsed["btc"]["symbols"] == ["SPY", "BTC-USD", "CASH"]
    assert parsed["btc"]["allow_btc"] is True
    assert parsed["btc"]["btc_caps"] == [0.05, 0.10]


def test_fixed_allocation_only_uses_available_symbols():
    specs = fixed_allocation_candidate_specs(
        ["SPY", "CASH"],
        allow_btc=False,
        btc_caps=[],
    )

    candidate_ids = {spec["candidate_id"] for spec in specs}

    assert "sf19_spy_buy_hold" in candidate_ids
    assert "sf19_spy_qqq_60_40" not in candidate_ids


def test_top_k_momentum_allocation_sums_to_one_and_respects_btc_cap():
    symbols = ["SPY", "QQQ", "BTC-USD", "CASH"]
    panel = build_multiverse_price_panel(_price_data(), symbols)

    result = run_top_k_momentum_candidate(
        panel,
        symbols=symbols,
        k=3,
        lookback=63,
        trend_filter=False,
        btc_cap=0.05,
        candidate_id="test_topk",
        initial_capital=10000,
    )

    weight_cols = ["spy_weight", "qqq_weight", "btc_usd_weight", "cash_weight"]
    assert np.allclose(result[weight_cols].sum(axis=1), 1.0)
    assert result["btc_usd_weight"].max() <= 0.05 + 1e-9


def test_inverse_vol_allocation_sums_to_one_and_respects_btc_cap():
    symbols = ["SPY", "QQQ", "BTC-USD", "CASH"]
    panel = build_multiverse_price_panel(_price_data(), symbols)

    result = run_inverse_vol_candidate(
        panel,
        symbols=symbols,
        lookback=63,
        max_weight=0.50,
        btc_cap=0.05,
        candidate_id="test_inverse_vol",
        initial_capital=10000,
    )

    weight_cols = ["spy_weight", "qqq_weight", "btc_usd_weight", "cash_weight"]
    assert np.allclose(result[weight_cols].sum(axis=1), 1.0)
    assert result["btc_usd_weight"].max() <= 0.05 + 1e-9


def test_score_columns_are_written():
    metrics = pd.DataFrame(
        {
            "universe_name": ["u", "u"],
            "period_name": ["p", "p"],
            "candidate_id": ["a", "b"],
            "strategy_family": ["x", "x"],
            "CAGR": [10.0, 8.0],
            "Calmar": [0.8, 0.5],
            "max_drawdown": [-20.0, -10.0],
            "turnover": [2.0, 1.0],
            "missing_data_flag": [False, False],
        }
    )

    scored = add_phase19a_scores(
        metrics,
        {
            "cagr_weight": 0.40,
            "calmar_weight": 0.30,
            "max_drawdown_weight": 0.20,
            "turnover_penalty_weight": 0.10,
        },
    )

    assert {"score", "rank_cagr", "rank_score"}.issubset(scored.columns)


def test_finalist_shortlist_excludes_live_real_money_broker_paths():
    leaderboard = pd.DataFrame(
        {
            "universe_name": ["u"],
            "candidate_id": ["candidate"],
            "strategy_family": ["fixed"],
            "periods_tested": [2],
            "average_score": [0.9],
            "best_period_score": [0.9],
            "mean_CAGR": [12.0],
            "best_CAGR": [14.0],
            "mean_CAGR_edge_vs_SPY": [1.5],
            "positive_CAGR_edge_periods": [2],
            "mean_max_drawdown": [-20.0],
            "worst_max_drawdown": [-25.0],
            "worst_drawdown_difference_vs_SPY": [-1.0],
            "mean_Calmar": [0.5],
            "mean_turnover": [2.0],
            "mean_rolling_1y_beat_SPY_pct": [80.0],
            "mean_rolling_3y_beat_SPY_pct": [80.0],
            "BTC_average_weight": [0.0],
            "BTC_max_weight": [0.0],
            "live_trading_allowed": [True],
            "real_money_allowed": [False],
            "broker_api_integration_allowed": [False],
            "rank_score": [1],
        }
    )

    classifications = build_phase19a_finalist_classifications(
        leaderboard,
        rules={
            "max_drawdown_worse_than_spy_allowed_pp": 5,
            "min_rolling_3y_beat_spy_pct": 60,
        },
    )

    row = classifications.iloc[0]
    assert row["classification"] != "finalist_clean_growth"
    assert not bool(row["promotion_allowed"])


def test_phase19a_report_writer_outputs_required_files_and_charts(tmp_path):
    config = _phase19a_config(tmp_path)

    outputs = save_phase19a_strategy_factory_multiverse(
        config=config,
        reports_dir=tmp_path,
        price_data=_price_data(),
    )

    required_keys = {
        "candidate_metrics",
        "leaderboard",
        "finalist_shortlist",
        "rejected_candidates",
        "entity_contribution_summary",
        "gate_report",
        "conclusion",
        "risk_return_scatter",
        "top_candidates_equity",
        "top_candidates_drawdown",
        "entity_usage_by_finalists",
        "dashboard_index",
    }
    assert required_keys.issubset(outputs)
    for key in required_keys:
        assert outputs[key].exists()

    metrics = pd.read_csv(outputs["candidate_metrics"])
    leaderboard = pd.read_csv(outputs["leaderboard"])
    entity_summary = pd.read_csv(outputs["entity_contribution_summary"])
    conclusion = pd.read_csv(outputs["conclusion"])

    assert not metrics.empty
    assert not leaderboard.empty
    assert not entity_summary.empty
    assert not bool(conclusion.loc[0, "live_trading_allowed"])
    assert not bool(conclusion.loc[0, "real_money_allowed"])
    assert not bool(conclusion.loc[0, "broker_api_integration_allowed"])
    assert "missing_symbol_universe" in set(metrics["universe_name"])
