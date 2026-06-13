from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.frozen_cost_aware_portfolio import (
    CostScenario,
    DEFAULT_PHASE23I_CONFIG,
    PortfolioSpec,
    build_phase23i_model_freeze,
    build_phase23i_targets_for_signal,
    save_phase23i_frozen_cost_aware_portfolio,
    save_phase23i_prospective_shadow_runner,
    simulate_phase23i_portfolio,
)


def _membership() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "sector": "Tech",
                "price_file": "AAA.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
            {
                "ticker": "BBB",
                "sector": "Tech",
                "price_file": "BBB.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
            {
                "ticker": "CCC",
                "sector": "Tech",
                "price_file": "CCC.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
            {
                "ticker": "DDD",
                "sector": "Health",
                "price_file": "DDD.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
            {
                "ticker": "EEE",
                "sector": "Finance",
                "price_file": "EEE.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
            {
                "ticker": "FFF",
                "sector": "Energy",
                "price_file": "FFF.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            },
        ]
    )


def _predictions() -> pd.DataFrame:
    rows = []
    for signal_date in ["2024-01-05", "2024-01-12", "2024-01-19"]:
        for rank, ticker in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"], start=1):
            rows.append(
                {
                    "decision_timestamp_utc": f"{signal_date}T22:00:00+00:00",
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "permanent_security_id": f"SEC_{ticker}",
                    "model_version": "phase23g_ridge_ranker_v1",
                    "predicted_rank": rank,
                    "predicted_20d_excess_return_or_ranking_score": 7 - rank,
                    "actual_20d_excess_return": 0.01,
                }
            )
    return pd.DataFrame(rows)


def _prices() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-05", periods=20)
    frames = {}
    for idx, ticker in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "SPY"]):
        base = 10.0 + idx
        frames[ticker] = pd.DataFrame(
            {
                "date": dates,
                "open": [base + i * 0.2 for i in range(len(dates))],
                "high": [base + i * 0.2 + 0.1 for i in range(len(dates))],
                "low": [base + i * 0.2 - 0.1 for i in range(len(dates))],
                "close": [base + i * 0.2 + 0.05 for i in range(len(dates))],
                "adj_close": [base + i * 0.2 + 0.05 for i in range(len(dates))],
                "volume": 100000,
            }
        )
    return frames


def test_model_freeze_is_deterministic() -> None:
    registry = pd.DataFrame(
        [
            {
                "model_version": "phase23g_ridge_ranker_v1",
                "primary_target": "forward_20d_excess_return_vs_universe",
                "feature_set": "momentum_21d;realized_volatility_21d",
                "ridge_alpha": 1.0,
                "preprocessing": "cross sectional z score",
                "purge_window_trading_days": 63,
                "embargo_window_trading_days": 63,
            }
        ]
    )
    features = pd.DataFrame({"feature_name": ["momentum_21d", "realized_volatility_21d"]})
    first, first_hashes = build_phase23i_model_freeze(
        config=DEFAULT_PHASE23I_CONFIG,
        model_registry=registry,
        feature_registry=features,
        git_commit="abc123",
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    second, second_hashes = build_phase23i_model_freeze(
        config=DEFAULT_PHASE23I_CONFIG,
        model_registry=registry,
        feature_registry=features,
        git_commit="abc123",
        generated_at_utc="2026-01-02T00:00:00+00:00",
    )
    assert first.iloc[0]["phase23i_freeze_hash"] == second.iloc[0]["phase23i_freeze_hash"]
    assert first_hashes.set_index("hash_name").loc["model_spec_hash", "hash_value"] == second_hashes.set_index("hash_name").loc["model_spec_hash", "hash_value"]
    assert bool(first.iloc[0]["research_pilot_only"])
    assert not bool(first.iloc[0]["promotion_allowed"])


def test_sector_replacement_and_stock_caps_are_enforced() -> None:
    weights, audit = build_phase23i_targets_for_signal(
        predictions=_predictions(),
        membership=_membership(),
        signal_date=pd.Timestamp("2024-01-05"),
        spec=PortfolioSpec("ridge_top5_equal_weight", "phase23g_ridge_ranker_v1", 5, "equal"),
        config=DEFAULT_PHASE23I_CONFIG,
    )
    assert "CCC" not in weights
    assert "FFF" in weights
    assert max(weights.values()) <= 0.20
    assert any(row["action"] == "excluded_and_next_rank_considered" for row in audit)


def test_next_open_integer_rounding_cash_and_costs() -> None:
    no_cost = simulate_phase23i_portfolio(
        predictions=_predictions(),
        membership=_membership(),
        prices=_prices(),
        spec=PortfolioSpec("ridge_top5_equal_weight", "phase23g_ridge_ranker_v1", 5, "equal"),
        cost=CostScenario("zero_cost", 0.0, 0.0, 0.0),
        config={**DEFAULT_PHASE23I_CONFIG, "initial_capital": 10000, "min_order_notional": 0},
    )
    with_cost = simulate_phase23i_portfolio(
        predictions=_predictions(),
        membership=_membership(),
        prices=_prices(),
        spec=PortfolioSpec("ridge_top5_equal_weight", "phase23g_ridge_ranker_v1", 5, "equal"),
        cost=CostScenario("cost_25bps", 25.0, 0.0, 0.0),
        config={**DEFAULT_PHASE23I_CONFIG, "initial_capital": 10000, "min_order_notional": 0},
    )
    fills = no_cost["fill_blotter"]
    assert not fills.empty
    assert not fills["same_close_execution_used"].any()
    assert (fills["order_shares"] % 1 == 0).all()
    assert no_cost["cash_ledger"]["cash_balance"].iloc[-1] >= 0
    assert with_cost["daily_equity"]["net_equity"].iloc[-1] <= no_cost["daily_equity"]["net_equity"].iloc[-1]
    assert with_cost["turnover"]["turnover"].sum() > 0


def _write_phase23_sources(root: Path) -> None:
    reports = root / "reports"
    phase23f = reports / "phase23f"
    phase23g = reports / "phase23g"
    phase23h = reports / "phase23h"
    data_dir = root / "data" / "individual_equity_pilot"
    phase23f.mkdir(parents=True)
    phase23g.mkdir(parents=True)
    phase23h.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    _membership().assign(
        universe_id="PILOT",
        permanent_security_id=lambda df: "SEC_" + df["ticker"],
        permanent_company_id=lambda df: "CO_" + df["ticker"],
        industry="Test",
        membership_start_date="2023-01-01",
        membership_end_date="",
        membership_known_timestamp_utc="2023-01-01T00:00:00Z",
    ).to_csv(data_dir / "pilot_membership_manifest.csv", index=False)
    for ticker, frame in _prices().items():
        filename = "benchmark_SPY.csv" if ticker == "SPY" else f"{ticker}.csv"
        frame.to_csv(data_dir / filename, index=False)
    pd.DataFrame(
        [
            {
                "phase": "Phase 23F",
                "phase23f_decision": "ready",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(phase23f / "phase23f_summary.csv", index=False)
    pd.DataFrame({"feature_name": ["momentum_21d", "realized_volatility_21d"]}).to_csv(
        phase23f / "phase23f_calculated_feature_registry.csv", index=False
    )
    pd.DataFrame({"panel_row_id": [1], "ticker": ["AAA"]}).to_csv(
        phase23f / "phase23f_pilot_feature_panel.csv", index=False
    )
    pd.DataFrame({"ticker": ["AAA"], "validation_passed": [True]}).to_csv(
        phase23f / "phase23f_source_inventory.csv", index=False
    )
    _predictions().to_csv(phase23g / "phase23g_oos_predictions.csv", index=False)
    pd.DataFrame(
        [
            {
                "model_version": "phase23g_ridge_ranker_v1",
                "primary_target": "forward_20d_excess_return_vs_universe",
                "feature_set": "momentum_21d;realized_volatility_21d",
                "ridge_alpha": 1.0,
                "preprocessing": "cross sectional z score",
                "purge_window_trading_days": 63,
                "embargo_window_trading_days": 63,
            }
        ]
    ).to_csv(phase23g / "phase23g_model_registry.csv", index=False)
    pd.DataFrame([{"gate": "phase23g", "passed": True}]).to_csv(
        phase23g / "phase23g_gate_report.csv", index=False
    )
    pd.DataFrame([{"gate": "phase23h", "passed": True}]).to_csv(
        phase23h / "phase23h_gate_report.csv", index=False
    )
    pd.DataFrame({"regime_bucket": ["pilot_2024"]}).to_csv(
        phase23h / "phase23h_regime_diagnostics.csv", index=False
    )


def _phase23i_config(tmp_path: Path) -> dict:
    return {
        "phase23i_frozen_cost_aware_portfolio": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23i"),
            "dashboard_status_path": str(tmp_path / "reports" / "dashboard" / "phase23i.csv"),
            "source_phase23f_dir": str(tmp_path / "reports" / "phase23f"),
            "source_phase23g_dir": str(tmp_path / "reports" / "phase23g"),
            "source_phase23h_dir": str(tmp_path / "reports" / "phase23h"),
            "pilot_input_dir": str(tmp_path / "data" / "individual_equity_pilot"),
            "initial_capital": 10000,
            "portfolio_specs": ["ridge_top5_equal_weight", "spy_benchmark"],
            "cost_scenarios": {
                "zero_cost": {"bps_per_one_way_notional": 0},
                "cost_25bps": {"bps_per_one_way_notional": 25},
            },
            "min_order_notional": 0,
        }
    }


def test_save_phase23i_writes_required_outputs_without_broker_files(tmp_path: Path) -> None:
    _write_phase23_sources(tmp_path)
    outputs = save_phase23i_frozen_cost_aware_portfolio(
        config=_phase23i_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    output_dir = tmp_path / "reports" / "phase23i"
    assert outputs["summary"].iloc[0]["phase23i_decision"] == "phase23i_cost_aware_portfolio_diagnostics_completed_research_only"
    for filename in [
        "phase23i_model_freeze.csv",
        "phase23i_historical_metrics.csv",
        "phase23i_cost_sensitivity.csv",
        "phase23i_daily_equity.csv",
        "phase23i_order_blotter.csv",
        "phase23i_fill_blotter.csv",
        "phase23i_cash_ledger.csv",
        "phase23i_constraint_audit.csv",
        "phase23i_execution_audit.csv",
        "phase23i_conclusion.csv",
    ]:
        assert (output_dir / filename).exists()
    metrics = pd.read_csv(output_dir / "phase23i_cost_sensitivity.csv")
    primary = metrics.loc[metrics["portfolio_id"].eq("ridge_top5_equal_weight")]
    assert primary.sort_values("total_costs")["end_value"].is_monotonic_decreasing
    assert not bool(outputs["summary"].iloc[0]["live_trading_allowed"])
    assert not list(output_dir.glob("*broker*"))


def test_shadow_runner_blocks_without_post_endpoint_data_and_separates_proposed_from_entered(tmp_path: Path) -> None:
    _write_phase23_sources(tmp_path)
    save_phase23i_frozen_cost_aware_portfolio(
        config=_phase23i_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    config = {
        "phase23i_prospective_shadow_runner": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "shadow"),
            "dashboard_status_path": str(tmp_path / "reports" / "dashboard" / "shadow.csv"),
            "source_phase23i_dir": str(tmp_path / "reports" / "phase23i"),
            "source_phase23g_dir": str(tmp_path / "reports" / "phase23g"),
            "pilot_input_dir": str(tmp_path / "data" / "individual_equity_pilot"),
            "canonical_research_endpoint": "2026-05-01",
        }
    }
    outputs = save_phase23i_prospective_shadow_runner(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    status = outputs["summary"].iloc[0]
    assert status["phase23i_shadow_decision"] == "phase23i_shadow_session_written_but_blocked"
    assert not bool(status["shadow_readiness_passed"])
    assert "post_endpoint_data_missing" in status["blocking_reasons"]
    assert outputs["positions"].iloc[0]["position_status"] == "initial_shadow_cash_only"
    assert (tmp_path / "reports" / "shadow" / "current_manual_session_template.csv").exists()

