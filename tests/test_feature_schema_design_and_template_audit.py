from pathlib import Path

import pandas as pd

from market_strats.analysis.feature_schema_design_and_template_audit import (
    build_phase13e_feature_schema,
    build_phase13e_transform_policy,
    build_phase13f_ml_policy_check,
    save_phase13e_technical_macro_feature_schema_design_spec,
    save_phase13f_feature_schema_readiness_visual_template_audit,
)


def _write_phase13d_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13D",
                "verdict": "Completed — feature contract readiness audit passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13d_contract_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13d_contract_gate_report.csv", index=False)

    for name in [
        "phase13c_inventory_feature_source_inventory.csv",
        "phase13c_inventory_feature_contract_requirements.csv",
        "phase13c_inventory_leakage_control_policy.csv",
        "phase13d_contract_contract_coverage_check.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _config(tmp_path: Path):
    universal_schema = [
        {"column_name": "as_of_date", "dtype": "date", "required": True, "description": "row date"},
        {"column_name": "observation_date", "dtype": "date", "required": True, "description": "observation date"},
        {"column_name": "release_date", "dtype": "date_or_null", "required": True, "description": "release date"},
        {"column_name": "availability_date", "dtype": "date", "required": True, "description": "availability date"},
        {"column_name": "decision_date", "dtype": "date", "required": True, "description": "decision date"},
        {"column_name": "family_id", "dtype": "string", "required": True, "description": "family"},
        {"column_name": "feature_id", "dtype": "string", "required": True, "description": "feature"},
        {"column_name": "feature_state", "dtype": "enum", "required": True, "description": "state"},
        {"column_name": "missingness_state", "dtype": "enum", "required": True, "description": "missingness"},
        {"column_name": "leakage_flag", "dtype": "bool", "required": True, "description": "leakage"},
        {"column_name": "contract_version", "dtype": "string", "required": True, "description": "contract"},
    ]

    technical_features = [
        {
            "feature_id": f"technical_feature_{i}",
            "family_id": "technical",
            "source_basis": "OHLCV",
            "raw_inputs": ["adjusted_close"],
            "transform_type": "state",
            "timestamp_policy": "after close",
            "lag_policy": "one-day lag",
            "revision_policy": "source version",
            "missingness_policy": "unavailable if insufficient history",
            "allowed_states": ["supportive", "neutral", "fragile", "unavailable"],
            "ml_feature_engineering_role": "candidate technical feature",
            "calculate_now": False,
        }
        for i in range(4)
    ]

    macro_features = [
        {
            "feature_id": f"macro_feature_{i}",
            "family_id": "macro",
            "source_basis": "FRED",
            "raw_inputs": ["macro_series"],
            "transform_type": "state",
            "timestamp_policy": "release-date policy",
            "lag_policy": "conservative lag",
            "revision_policy": "vintage policy",
            "missingness_policy": "unavailable before release",
            "allowed_states": ["supportive", "neutral", "fragile", "unavailable"],
            "ml_feature_engineering_role": "candidate macro feature",
            "calculate_now": False,
        }
        for i in range(4)
    ]

    transform_policy = [
        {"transform_id": "TE1", "policy": "train only", "ml_principle": "avoid train-test leakage", "required": True},
        {"transform_id": "TE2", "policy": "no return selection", "ml_principle": "avoid overfitting", "required": True},
        {"transform_id": "TE3", "policy": "interpretable first", "ml_principle": "interpretability", "required": True},
        {"transform_id": "TE4", "policy": "separate calculation", "ml_principle": "schema before calculation", "required": True},
        {"transform_id": "TE5", "policy": "outlier policy", "ml_principle": "stable preprocessing contract", "required": True},
        {"transform_id": "TE6", "policy": "no target leakage", "ml_principle": "target leakage prevention", "required": True},
    ]

    missingness_policy = [
        {"missingness_id": f"M{i}", "policy": "missingness policy", "required": True}
        for i in range(5)
    ]

    visual_templates = [
        {
            "template_id": "feature_availability_heatmap",
            "purpose": "availability",
            "required_columns": ["as_of_date", "family_id", "feature_id"],
            "calculate_now": False,
        },
        {
            "template_id": "feature_state_timeline",
            "purpose": "timeline",
            "required_columns": ["as_of_date", "feature_id", "feature_state"],
            "calculate_now": False,
        },
        {
            "template_id": "leakage_audit_panel",
            "purpose": "leakage",
            "required_columns": ["observation_date", "release_date", "availability_date"],
            "calculate_now": False,
        },
        {
            "template_id": "model_feature_matrix_preview",
            "purpose": "future matrix schema",
            "required_columns": ["as_of_date", "feature_id", "feature_state"],
            "calculate_now": False,
        },
        {
            "template_id": "decision_rationale_template",
            "purpose": "rationale",
            "required_columns": ["decision_date", "feature_id", "feature_state"],
            "calculate_now": False,
        },
    ]

    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13c_multifactor_feature_source_inventory_spec": {"enabled": False},
        "phase13d_feature_contract_readiness_audit": {"enabled": False},
        "phase13e_technical_macro_feature_schema_design_spec": {
            "enabled": True,
            "spec_role": "Technical and macro feature-contract schema design spec only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13D",
            "proposed_next_phase": "Phase 13F",
            "allow_feature_ingestion": False,
            "allow_feature_calculation": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "source_reports": {
                "phase13d_conclusion": str(tmp_path / "phase13d_contract_conclusion.csv"),
                "phase13d_gate_report": str(tmp_path / "phase13d_contract_gate_report.csv"),
                "phase13c_feature_source_inventory": str(tmp_path / "phase13c_inventory_feature_source_inventory.csv"),
                "phase13c_feature_contract_requirements": str(tmp_path / "phase13c_inventory_feature_contract_requirements.csv"),
                "phase13c_leakage_control_policy": str(tmp_path / "phase13c_inventory_leakage_control_policy.csv"),
                "phase13d_contract_coverage_check": str(tmp_path / "phase13d_contract_contract_coverage_check.csv"),
            },
            "universal_panel_schema": universal_schema,
            "technical_feature_schema": technical_features,
            "macro_feature_schema": macro_features,
            "transform_policy": transform_policy,
            "missingness_policy": missingness_policy,
            "feature_state_policy": {
                "allowed_feature_states": ["supportive", "neutral", "fragile", "unavailable", "blocked"],
                "state_direction_required": True,
                "state_reason_required": True,
                "no_state_may_directly_create_trade": True,
                "no_state_may_be_tuned_on_returns_now": True,
            },
            "visual_report_templates": visual_templates,
            "phase13f_boundary": {
                "allowed_next_step": "Feature schema readiness and visual report template audit only",
                "forbidden_next_step": "feature ingestion, feature calculation, signal creation, allocation rule, strategy backtest, model training, paper-trading deployment, candidate promotion, or final-candidate change",
                "phase13f_may_audit_schema": True,
                "phase13f_may_audit_visual_templates": True,
                "phase13f_may_audit_ml_feature_engineering_policy": True,
                "phase13f_may_ingest_features": False,
                "phase13f_may_calculate_features": False,
                "phase13f_may_train_model": False,
                "phase13f_may_create_signal": False,
                "phase13f_may_run_backtest": False,
                "phase13f_may_deploy_paper_trading": False,
                "phase13f_may_promote_candidate": False,
            },
        },
        "phase13f_feature_schema_readiness_visual_template_audit": {
            "enabled": True,
            "audit_role": "Feature schema readiness and visual report template audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13E",
            "proposed_next_phase": "Phase 13G",
            "allow_feature_ingestion": False,
            "allow_feature_calculation": False,
            "allow_signal_creation": False,
            "allow_allocation_rule_creation": False,
            "allow_strategy_backtest": False,
            "allow_empirical_return_weights": False,
            "allow_model_training": False,
            "allow_paper_trading_deployment": False,
            "allow_candidate_promotion": False,
            "allow_final_candidate_change": False,
            "expected_runtime_flags": {
                "phase13c_multifactor_feature_source_inventory_spec": False,
                "phase13d_feature_contract_readiness_audit": False,
                "phase13e_technical_macro_feature_schema_design_spec": True,
                "phase13f_feature_schema_readiness_visual_template_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13e_reports": {
                "universal_panel_schema": str(tmp_path / "phase13e_schema_universal_panel_schema.csv"),
                "technical_feature_schema": str(tmp_path / "phase13e_schema_technical_feature_schema.csv"),
                "macro_feature_schema": str(tmp_path / "phase13e_schema_macro_feature_schema.csv"),
                "transform_policy": str(tmp_path / "phase13e_schema_transform_policy.csv"),
                "missingness_policy": str(tmp_path / "phase13e_schema_missingness_policy.csv"),
                "visual_report_templates": str(tmp_path / "phase13e_schema_visual_report_templates.csv"),
                "gate_report": str(tmp_path / "phase13e_schema_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13e_schema_conclusion.csv"),
            },
            "readiness_claims": {
                "schema_defined": True,
                "technical_schema_defined": True,
                "macro_schema_defined": True,
                "timestamp_fields_defined": True,
                "lag_revision_policy_defined": True,
                "missingness_policy_defined": True,
                "transform_policy_defined": True,
                "ml_feature_engineering_policy_defined": True,
                "visual_templates_defined": True,
                "feature_ingested": False,
                "feature_calculated": False,
                "signal_created": False,
                "backtest_run": False,
                "model_trained": False,
                "paper_trading_deployed": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            },
            "phase13g_boundary": {
                "allowed_next_step": "Technical and macro feature calculation pre-registration spec only",
                "forbidden_next_step": "direct feature calculation, signal creation, allocation rule, strategy backtest, model training, paper-trading deployment, candidate promotion, or final-candidate change",
                "phase13g_may_preregister_feature_calculation": True,
                "phase13g_may_calculate_features_immediately": False,
                "phase13g_may_train_model": False,
                "phase13g_may_create_signal": False,
                "phase13g_may_run_backtest": False,
                "phase13g_may_deploy_paper_trading": False,
                "phase13g_may_promote_candidate": False,
            },
        },
    }


def test_phase13e_schema_contains_ml_feature_engineering_policy(tmp_path):
    _write_phase13d_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13e_technical_macro_feature_schema_design_spec"]

    technical_schema = build_phase13e_feature_schema(
        phase_config,
        "technical_feature_schema",
    )
    transform_policy = build_phase13e_transform_policy(phase_config)
    ml_check = build_phase13f_ml_policy_check(transform_policy)

    assert len(technical_schema) == 4
    assert not bool(technical_schema["calculate_now"].any())
    assert bool(ml_check["passed"].all())


def test_phase13e_and_13f_save_reports(tmp_path):
    _write_phase13d_reports(tmp_path)
    config = _config(tmp_path)

    out_e = save_phase13e_technical_macro_feature_schema_design_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_f = save_phase13f_feature_schema_readiness_visual_template_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_e["conclusion"].iloc[0]["all_gates_passed"]
    assert out_f["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13e_schema_conclusion.csv").exists()
    assert (tmp_path / "phase13f_schema_audit_conclusion.csv").exists()


def test_phase13f_ml_policy_fails_without_target_leakage_rule(tmp_path):
    transform_policy = pd.DataFrame(
        [
            {"ml_principle": "avoid train-test leakage"},
            {"ml_principle": "avoid overfitting"},
            {"ml_principle": "stable preprocessing contract"},
        ]
    )

    ml_check = build_phase13f_ml_policy_check(transform_policy)

    assert not bool(ml_check["passed"].all())