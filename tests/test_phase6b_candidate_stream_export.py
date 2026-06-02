from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.analysis.phase6b_candidate_stream_export as export_bundle
from market_strats.analysis.phase6b_candidate_stream_export import (
    save_phase14i_phase6b_candidate_daily_stream_export,
    save_phase14j_phase6b_candidate_export_audit,
)


def _mock_candidate():
    dates = pd.bdate_range("2020-01-01", periods=504)
    returns = np.full(len(dates), 0.0005)
    equity = 10000.0 * (1.0 + pd.Series(returns)).cumprod()

    exposure = np.where(np.arange(len(dates)) % 80 < 60, 1.0, 0.0)
    mode = np.where(exposure > 0.5, "offensive_spy", "defensive_allocator")

    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": returns,
            "equity": equity,
            "exposure": exposure,
            "mode": mode,
            "turnover": pd.Series(exposure).diff().abs().fillna(0.0),
            "applied_overlay_slippage_bps": 5.0,
            "overlay_slippage_cost_pct": 0.0,
        }
    )


def _mock_spy():
    dates = pd.bdate_range("2020-01-01", periods=504)
    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": np.full(len(dates), 0.0004),
        }
    )


def _config(tmp_path: Path):
    candidate = _mock_candidate()
    end_value = float(candidate["equity"].iloc[-1])

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase14e_visual_backtest_interpretation_source_identity_audit": {"enabled": False},
        "phase14f_candidate_source_correction_or_workflow_prereg_decision": {"enabled": False},
        "phase14g_candidate_source_correction_visual_rerun": {"enabled": True},
        "phase14h_corrected_visual_backtest_audit_reconciliation_decision": {"enabled": True},
        "phase14i_phase6b_candidate_daily_stream_export": {
            "enabled": True,
            "execution_role": "Phase 6B/6C candidate daily stream export only",
            "implementation_classification": "A/B",
            "intended_candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "output_file": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            "spy_buy_hold_strategy_name": "Buy and Hold",
            "initial_capital": 10000.0,
            "annualisation_days": 252,
            "allow_visual_backtest_generation": False,
            "allow_paper_trading_workflow_preregistration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "required_export_columns": [
                "decision_date",
                "strategy_return",
                "SPY_return",
                "candidate_equity",
                "benchmark_equity",
                "exposure",
                "mode",
                "turnover",
                "applied_overlay_slippage_bps",
                "overlay_slippage_cost_pct",
            ],
            "expected_metrics": {
                "end_value": end_value,
                "cagr": 0.1339,
                "calmar": 100.0,
                "max_drawdown": 0.0,
                "overlay_switch_count": 12,
            },
            "tolerance": {
                "end_value_relative_tolerance": 0.01,
                "cagr_abs_tolerance": 1.0,
                "calmar_abs_tolerance": 1000.0,
                "max_drawdown_abs_tolerance": 1.0,
                "switch_count_abs_tolerance": 20,
            },
            "phase14j_boundary": {
                "allowed_next_step": "Exported candidate stream audit and metric reconciliation only",
                "forbidden_next_step": "paper-trading workflow pre-registration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
        "phase14j_phase6b_candidate_export_audit": {
            "enabled": True,
            "audit_role": "Phase 6B/6C exported candidate stream audit and metric reconciliation only",
            "implementation_classification": "B",
            "exported_daily_file": str(tmp_path / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"),
            "allow_visual_backtest_generation": False,
            "allow_paper_trading_workflow_preregistration": False,
            "allow_paper_trading_deployment": False,
            "allow_live_trading": False,
            "allow_real_money_deployment": False,
            "allow_paper_trading_ready_claim": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "allow_model_training": False,
            "allow_unregistered_ml": False,
            "allow_feature_importance": False,
            "expected_runtime_flags": {
                "phase14e_visual_backtest_interpretation_source_identity_audit": False,
                "phase14f_candidate_source_correction_or_workflow_prereg_decision": False,
                "phase14i_phase6b_candidate_daily_stream_export": True,
                "phase14j_phase6b_candidate_export_audit": True,
                "phase14g_candidate_source_correction_visual_rerun": True,
                "phase14h_corrected_visual_backtest_audit_reconciliation_decision": True,
                "relative_momentum_allocator": True,
            },
            "required_export_columns": [
                "decision_date",
                "strategy_return",
                "SPY_return",
                "candidate_equity",
                "benchmark_equity",
                "exposure",
                "mode",
                "turnover",
                "applied_overlay_slippage_bps",
                "overlay_slippage_cost_pct",
            ],
            "expected_metrics": {
                "end_value": end_value,
                "cagr": 0.1339,
                "calmar": 100.0,
                "max_drawdown": 0.0,
                "overlay_switch_count": 12,
            },
            "tolerance": {
                "end_value_relative_tolerance": 0.01,
                "cagr_abs_tolerance": 1.0,
                "calmar_abs_tolerance": 1000.0,
                "max_drawdown_abs_tolerance": 1.0,
                "switch_count_abs_tolerance": 20,
            },
            "phase14g_rerun_boundary": {
                "allowed_next_step": "Corrected visual backtest re-run against exported Phase 6B/6C stream only",
                "forbidden_next_step": "paper-trading workflow pre-registration, paper-trading deployment, live trading, real-money deployment, candidate promotion",
            },
        },
    }


def test_phase14i_to_14j_exports_and_audits_phase6b_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(
        export_bundle,
        "_find_final_candidate_frame",
        lambda relative_momentum_outputs, ticker_outputs, config: _mock_candidate(),
    )
    monkeypatch.setattr(
        export_bundle,
        "_get_spy_strategy_result",
        lambda ticker_outputs, strategy_name: _mock_spy(),
    )

    config = _config(tmp_path)

    out_i = save_phase14i_phase6b_candidate_daily_stream_export(
        config=config,
        reports_dir=tmp_path,
        relative_momentum_outputs={},
        ticker_outputs={},
    )
    out_j = save_phase14j_phase6b_candidate_export_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert bool(out_i["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(out_j["conclusion"].iloc[0]["all_gates_passed"])

    exported = out_i["exported_daily_stream"]
    assert not exported.empty
    assert "strategy_return" in exported.columns
    assert "SPY_return" in exported.columns
    assert "phase6b_loose_relief_execution_realistic_overlay" in exported["source_system_id"].iloc[0]
    assert not bool(out_j["conclusion"].iloc[0]["paper_trading_ready"])