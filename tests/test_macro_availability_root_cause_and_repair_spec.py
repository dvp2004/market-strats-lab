from pathlib import Path

import pandas as pd

from market_strats.analysis.macro_availability_root_cause_and_repair_spec import (
    build_phase13o_macro_column_mapping_report,
    build_phase13o_root_cause_report,
    save_phase13o_macro_availability_root_cause_diagnostic,
    save_phase13p_macro_feature_repair_decision_spec,
)


def _write_phase13n_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13N",
                "verdict": "Completed — ML dataset quality and leakage audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13n_quality_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13n_quality_gate_report.csv", index=False)

    for name in [
        "phase13m_dataset_family_usage_report.csv",
        "phase13m_dataset_dataset_metadata.csv",
        "phase13m_ml_feature_dataset_v1.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)

    pd.DataFrame(
        [
            {
                "current_macro_available_ratio": 0.0,
                "repair_attempted": True,
                "repaired_macro_available_ratio": 0.0,
                "repaired_successfully": False,
                "macro_blocked_for_dataset_v1": True,
                "dataset_label": "technical_only_macro_blocked_dataset_v1",
            }
        ]
    ).to_csv(tmp_path / "phase13m_dataset_macro_guard_report.csv", index=False)

    rows = []
    for feature_id in [
        "macro_short_rate_state",
        "macro_yield_curve_state",
        "macro_inflation_state",
        "macro_labour_state",
    ]:
        rows.append(
            {
                "family_id": "macro",
                "feature_id": feature_id,
                "feature_value": "",
                "raw_inputs_available": False,
                "missingness_state": "unavailable",
            }
        )
    pd.DataFrame(rows).to_csv(tmp_path / "phase13m_dataset_macro_repair_panel.csv", index=False)


def _write_macro_source(tmp_path: Path):
    dates = pd.bdate_range("2020-01-01", periods=200)
    pd.DataFrame(
        {
            "date": dates,
            "DGS2": 2.0,
            "DGS10": 3.0,
            "CPIAUCSL": 260.0,
            "UNRATE": 4.5,
        }
    ).to_csv(tmp_path / "phase10c_macro_aligned_series.csv", index=False)


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13m_ml_dataset_assembly_execution": {"enabled": False},
        "phase13n_ml_dataset_quality_leakage_audit": {"enabled": False},
        "phase13o_macro_availability_root_cause_diagnostic": {
            "enabled": True,
            "diagnostic_role": "Macro availability root-cause diagnostic only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13N",
            "proposed_next_phase": "Phase 13P",
            "allow_macro_diagnosis": True,
            "allow_macro_repair_decision": False,
            "allow_macro_feature_repair_execution": False,
            "allow_dataset_reassembly": False,
            "allow_target_recalculation": False,
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_feature_importance": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13n_conclusion": str(tmp_path / "phase13n_quality_conclusion.csv"),
                "phase13n_gate_report": str(tmp_path / "phase13n_quality_gate_report.csv"),
                "macro_guard_report": str(tmp_path / "phase13m_dataset_macro_guard_report.csv"),
                "macro_repair_panel": str(tmp_path / "phase13m_dataset_macro_repair_panel.csv"),
                "family_usage_report": str(tmp_path / "phase13m_dataset_family_usage_report.csv"),
                "dataset_metadata": str(tmp_path / "phase13m_dataset_dataset_metadata.csv"),
                "assembled_dataset": str(tmp_path / "phase13m_ml_feature_dataset_v1.csv"),
            },
            "macro_sources": {
                "macro_aligned_candidates": [
                    str(tmp_path / "phase10c_macro_aligned_series.csv")
                ],
                "date_column_candidates": ["date", "as_of_date"],
                "long_format_series_column_candidates": ["series_id"],
                "long_format_value_column_candidates": ["value"],
                "required_macro_inputs": {
                    "DGS2": {"aliases": ["DGS2"]},
                    "DGS10": {"aliases": ["DGS10"]},
                    "CPIAUCSL": {"aliases": ["CPIAUCSL"]},
                    "UNRATE": {"aliases": ["UNRATE"]},
                },
            },
            "diagnosis_policy": {
                "min_rows_for_source_usable": 100,
                "min_numeric_non_null_per_macro_input": 100,
                "min_repaired_available_ratio_to_accept": 0.20,
            },
            "phase13p_boundary": {
                "allowed_next_step": "Macro feature repair decision and repair spec only",
                "forbidden_next_step": (
                    "macro repair execution, dataset reassembly, target recalculation, "
                    "model training, signal creation, strategy backtest"
                ),
                "phase13p_may_write_repair_decision": True,
                "phase13p_may_write_repair_spec": True,
                "phase13p_may_execute_repair": False,
                "phase13p_may_reassemble_dataset": False,
                "phase13p_may_train_model": False,
                "phase13p_may_create_signal": False,
            },
        },
        "phase13p_macro_feature_repair_decision_spec": {
            "enabled": True,
            "spec_role": "Macro feature repair decision and repair spec only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13O",
            "proposed_next_phase": "Phase 13Q",
            "allow_macro_repair_execution": False,
            "allow_dataset_reassembly": False,
            "allow_target_recalculation": False,
            "allow_model_training": False,
            "allow_model_selection": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_feature_importance": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13m_ml_dataset_assembly_execution": False,
                "phase13n_ml_dataset_quality_leakage_audit": False,
                "phase13o_macro_availability_root_cause_diagnostic": True,
                "phase13p_macro_feature_repair_decision_spec": True,
                "relative_momentum_allocator": True,
            },
            "phase13o_reports": {
                "source_report_check": str(tmp_path / "phase13o_macro_root_cause_source_report_check.csv"),
                "phase13n_result_check": str(tmp_path / "phase13o_macro_root_cause_phase13n_result_check.csv"),
                "macro_source_inventory": str(tmp_path / "phase13o_macro_root_cause_macro_source_inventory.csv"),
                "macro_source_schema_profile": str(tmp_path / "phase13o_macro_root_cause_macro_source_schema_profile.csv"),
                "macro_column_mapping_report": str(tmp_path / "phase13o_macro_root_cause_macro_column_mapping_report.csv"),
                "macro_long_format_diagnostic": str(tmp_path / "phase13o_macro_root_cause_macro_long_format_diagnostic.csv"),
                "existing_repair_panel_profile": str(tmp_path / "phase13o_macro_root_cause_existing_repair_panel_profile.csv"),
                "macro_guard_profile": str(tmp_path / "phase13o_macro_root_cause_macro_guard_profile.csv"),
                "root_cause_report": str(tmp_path / "phase13o_macro_root_cause_root_cause_report.csv"),
                "phase13p_boundary_check": str(tmp_path / "phase13o_macro_root_cause_phase13p_boundary_check.csv"),
                "scope_boundary_check": str(tmp_path / "phase13o_macro_root_cause_scope_boundary_check.csv"),
                "summary": str(tmp_path / "phase13o_macro_root_cause_summary.csv"),
                "gate_report": str(tmp_path / "phase13o_macro_root_cause_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13o_macro_root_cause_conclusion.csv"),
            },
            "decision_policy": {
                "dataset_label_until_repair_validated": "technical_only_macro_blocked_dataset_v1",
                "repaired_dataset_label_only_after_future_audit": "multi_factor_technical_macro_dataset_v1",
                "require_future_phase13q_repair_execution_before_macro_dataset_claim": True,
            },
            "repair_spec_template": {
                "repair_scope": "Macro feature availability repair only",
                "required_inputs": ["DGS2", "DGS10", "CPIAUCSL", "UNRATE"],
                "required_outputs": [
                    "macro_short_rate_state",
                    "macro_yield_curve_state",
                    "macro_inflation_state",
                    "macro_labour_state",
                ],
                "required_checks": [
                    "numeric values parsed",
                    "macro availability ratio exceeds threshold",
                ],
                "forbidden_actions": ["model training", "signal creation"],
            },
            "phase13q_boundary": {
                "allowed_next_step": "Macro feature repair execution and guarded dataset reassembly only",
                "forbidden_next_step": (
                    "model training, model selection, signal creation, strategy backtest"
                ),
                "phase13q_may_execute_macro_repair": True,
                "phase13q_may_reassemble_dataset_with_guard": True,
                "phase13q_may_train_model": False,
                "phase13q_may_select_model": False,
                "phase13q_may_create_signal": False,
                "phase13q_may_run_backtest": False,
                "phase13q_may_promote_candidate": False,
            },
        },
    }


def test_phase13o_detects_numeric_source_but_failed_repair_panel(tmp_path):
    _write_phase13n_reports(tmp_path)
    _write_macro_source(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13o_macro_availability_root_cause_diagnostic"]

    macro_source = pd.read_csv(tmp_path / "phase10c_macro_aligned_series.csv")
    mapping = build_phase13o_macro_column_mapping_report(
        macro_source=macro_source,
        phase_config=phase_config,
    )
    root = build_phase13o_root_cause_report(
        macro_source_inventory=pd.DataFrame([{"present": True}]),
        column_mapping_report=mapping,
        long_format_diagnostic=pd.DataFrame(
            [{"long_format_detected": False}]
        ),
        repair_panel_profile=pd.DataFrame(
            [{"available_ratio": 0.0}]
        ),
        macro_guard_profile=pd.DataFrame(
            [{"macro_blocked_for_dataset_v1": True}]
        ),
    )

    assert bool(mapping["numeric_usable"].all())
    assert root.iloc[0]["root_cause"] == (
        "macro_repair_panel_logic_failed_despite_numeric_source"
    )


def test_phase13o_and_13p_save_reports(tmp_path):
    _write_phase13n_reports(tmp_path)
    _write_macro_source(tmp_path)
    config = _config(tmp_path)

    out_o = save_phase13o_macro_availability_root_cause_diagnostic(
        config=config,
        reports_dir=tmp_path,
    )
    out_p = save_phase13p_macro_feature_repair_decision_spec(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_o["conclusion"].iloc[0]["all_gates_passed"]
    assert out_p["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13o_macro_root_cause_root_cause_report.csv").exists()
    assert (tmp_path / "phase13p_repair_spec_repair_decision.csv").exists()