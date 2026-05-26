from pathlib import Path

import pandas as pd

from market_strats.analysis.feature_calculation_prereg_and_readiness_audit import (
    build_phase13g_calculation_registry,
    build_phase13h_formula_registry_lock_check,
    save_phase13g_feature_calculation_preregistration_spec,
    save_phase13h_feature_calculation_readiness_audit,
)


def _write_phase13f_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 13F",
                "verdict": (
                    "Completed — feature schema readiness and visual template "
                    "audit passed"
                ),
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13f_schema_audit_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "dummy",
                "passed": True,
                "result": "Passed",
                "all_gates_passed": True,
            }
        ]
    ).to_csv(tmp_path / "phase13f_schema_audit_gate_report.csv", index=False)

    for name in [
        "phase13e_schema_universal_panel_schema.csv",
        "phase13e_schema_technical_feature_schema.csv",
        "phase13e_schema_macro_feature_schema.csv",
        "phase13e_schema_transform_policy.csv",
        "phase13e_schema_missingness_policy.csv",
        "phase13e_schema_visual_report_templates.csv",
    ]:
        pd.DataFrame([{"x": 1}]).to_csv(tmp_path / name, index=False)


def _calc_registry():
    base = [
        ("technical_trend_state", "technical"),
        ("technical_momentum_state", "technical"),
        ("technical_volatility_state", "technical"),
        ("technical_drawdown_state", "technical"),
        ("macro_short_rate_state", "macro"),
        ("macro_yield_curve_state", "macro"),
        ("macro_inflation_state", "macro"),
        ("macro_labour_state", "macro"),
    ]

    rows = []
    for feature_id, family_id in base:
        rows.append(
            {
                "feature_id": feature_id,
                "family_id": family_id,
                "formula_id": f"{feature_id}_formula",
                "raw_inputs": ["adjusted_close"]
                if family_id == "technical"
                else ["macro_series"],
                "lookback_window": "fixed lookback",
                "formula_description": "exact formula description",
                "threshold_policy": "exact threshold policy",
                "lag_policy": "exact lag policy",
                "revision_policy": "exact revision policy",
                "missingness_policy": "exact missingness policy",
                "output_state_column": feature_id,
                "output_value_column": f"{feature_id}_value",
                "leakage_check_id": "LC_TEST",
                "visual_check_id": "VIS_TEST",
                "calculate_now": False,
            }
        )
    return rows


def _output_schema():
    columns = [
        "as_of_date",
        "observation_date",
        "release_date",
        "availability_date",
        "decision_date",
        "family_id",
        "feature_id",
        "formula_id",
        "source_name",
        "source_version",
        "raw_inputs_available",
        "feature_value",
        "feature_state",
        "state_reason",
        "missingness_state",
        "leakage_flag",
        "contract_version",
    ]
    return [
        {"column_name": column, "dtype": "string", "required": True}
        for column in columns
    ]


def _config(tmp_path: Path):
    return {
        "relative_momentum_allocator": {"enabled": True},
        "phase13e_technical_macro_feature_schema_design_spec": {"enabled": False},
        "phase13f_feature_schema_readiness_visual_template_audit": {
            "enabled": False
        },
        "phase13g_feature_calculation_preregistration_spec": {
            "enabled": True,
            "spec_role": (
                "Technical and macro feature calculation pre-registration spec only"
            ),
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13F",
            "proposed_next_phase": "Phase 13H",
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
                "phase13f_conclusion": str(
                    tmp_path / "phase13f_schema_audit_conclusion.csv"
                ),
                "phase13f_gate_report": str(
                    tmp_path / "phase13f_schema_audit_gate_report.csv"
                ),
                "universal_panel_schema": str(
                    tmp_path / "phase13e_schema_universal_panel_schema.csv"
                ),
                "technical_feature_schema": str(
                    tmp_path / "phase13e_schema_technical_feature_schema.csv"
                ),
                "macro_feature_schema": str(
                    tmp_path / "phase13e_schema_macro_feature_schema.csv"
                ),
                "transform_policy": str(
                    tmp_path / "phase13e_schema_transform_policy.csv"
                ),
                "missingness_policy": str(
                    tmp_path / "phase13e_schema_missingness_policy.csv"
                ),
                "visual_report_templates": str(
                    tmp_path / "phase13e_schema_visual_report_templates.csv"
                ),
            },
            "calculation_registry": _calc_registry(),
            "output_column_schema": _output_schema(),
            "missingness_behaviour": [
                {"rule_id": f"MISS{i}", "rule": "missingness rule", "required": True}
                for i in range(1, 6)
            ],
            "leakage_checks": [
                {"check_id": f"LC{i}", "check": "leakage check", "required": True}
                for i in range(1, 7)
            ],
            "visual_checks": [
                {
                    "visual_check_id": f"VIS{i}",
                    "check": "visual check",
                    "required": True,
                }
                for i in range(1, 6)
            ],
            "ml_feature_engineering_lock": {
                "train_only_scaling_required": True,
                "target_leakage_forbidden": True,
                "posthoc_feature_selection_forbidden": True,
                "outlier_policy_predeclared": True,
                "categorical_state_first": True,
                "numeric_values_allowed_only_in_future_calculation_phase": True,
                "feature_importance_forbidden_until_model_phase": True,
            },
            "phase13h_boundary": {
                "allowed_next_step": "Feature calculation readiness audit only",
                "forbidden_next_step": (
                    "feature calculation, signal creation, allocation rule, "
                    "strategy backtest, model training, paper-trading deployment, "
                    "candidate promotion, or final-candidate change"
                ),
                "phase13h_may_audit_formula_registry": True,
                "phase13h_may_audit_output_schema": True,
                "phase13h_may_calculate_features": False,
                "phase13h_may_train_model": False,
                "phase13h_may_create_signal": False,
                "phase13h_may_run_backtest": False,
                "phase13h_may_deploy_paper_trading": False,
                "phase13h_may_promote_candidate": False,
            },
        },
        "phase13h_feature_calculation_readiness_audit": {
            "enabled": True,
            "audit_role": "Feature calculation readiness audit only",
            "phase_branch": "Phase 13 multi-factor model architecture planning",
            "source_phase": "Phase 13G",
            "proposed_next_phase": "Phase 13I",
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
                "phase13e_technical_macro_feature_schema_design_spec": False,
                "phase13f_feature_schema_readiness_visual_template_audit": False,
                "phase13g_feature_calculation_preregistration_spec": True,
                "phase13h_feature_calculation_readiness_audit": True,
                "relative_momentum_allocator": True,
            },
            "phase13g_reports": {
                "source_report_check": str(
                    tmp_path / "phase13g_prereg_source_report_check.csv"
                ),
                "phase13f_result_check": str(
                    tmp_path / "phase13g_prereg_phase13f_result_check.csv"
                ),
                "calculation_registry": str(
                    tmp_path / "phase13g_prereg_calculation_registry.csv"
                ),
                "output_column_schema": str(
                    tmp_path / "phase13g_prereg_output_column_schema.csv"
                ),
                "missingness_behaviour": str(
                    tmp_path / "phase13g_prereg_missingness_behaviour.csv"
                ),
                "leakage_checks": str(
                    tmp_path / "phase13g_prereg_leakage_checks.csv"
                ),
                "visual_checks": str(
                    tmp_path / "phase13g_prereg_visual_checks.csv"
                ),
                "ml_feature_engineering_lock": str(
                    tmp_path / "phase13g_prereg_ml_feature_engineering_lock.csv"
                ),
                "phase13h_boundary_check": str(
                    tmp_path / "phase13g_prereg_phase13h_boundary_check.csv"
                ),
                "scope_boundary_check": str(
                    tmp_path / "phase13g_prereg_scope_boundary_check.csv"
                ),
                "gate_report": str(tmp_path / "phase13g_prereg_gate_report.csv"),
                "conclusion": str(tmp_path / "phase13g_prereg_conclusion.csv"),
            },
            "readiness_claims": {
                "calculation_registry_locked": True,
                "output_schema_locked": True,
                "missingness_behaviour_locked": True,
                "leakage_checks_locked": True,
                "visual_checks_locked": True,
                "ml_feature_engineering_lock_present": True,
                "feature_ingested": False,
                "feature_calculated": False,
                "signal_created": False,
                "backtest_run": False,
                "model_trained": False,
                "paper_trading_deployed": False,
                "candidate_promoted": False,
                "final_candidate_changed": False,
            },
            "phase13i_boundary": {
                "allowed_next_step": (
                    "Technical and macro feature calculation execution only"
                ),
                "forbidden_next_step": (
                    "signal creation, allocation rule, strategy backtest, "
                    "model training, paper-trading deployment, candidate promotion, "
                    "or final-candidate change"
                ),
                "phase13i_may_calculate_features": True,
                "phase13i_may_create_feature_panels": True,
                "phase13i_may_create_visual_feature_reports": True,
                "phase13i_may_create_signal": False,
                "phase13i_may_train_model": False,
                "phase13i_may_run_backtest": False,
                "phase13i_may_deploy_paper_trading": False,
                "phase13i_may_promote_candidate": False,
            },
        },
    }


def test_phase13g_registry_locks_exact_formulas(tmp_path):
    _write_phase13f_reports(tmp_path)
    config = _config(tmp_path)
    phase_config = config["phase13g_feature_calculation_preregistration_spec"]

    registry = build_phase13g_calculation_registry(phase_config)
    lock_check = build_phase13h_formula_registry_lock_check(registry)

    assert len(registry) == 8
    assert not bool(registry["calculate_now"].any())
    assert bool(lock_check["passed"].all())


def test_phase13g_and_13h_save_reports(tmp_path):
    _write_phase13f_reports(tmp_path)
    config = _config(tmp_path)

    out_g = save_phase13g_feature_calculation_preregistration_spec(
        config=config,
        reports_dir=tmp_path,
    )
    out_h = save_phase13h_feature_calculation_readiness_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert out_g["conclusion"].iloc[0]["all_gates_passed"]
    assert out_h["conclusion"].iloc[0]["all_gates_passed"]
    assert (tmp_path / "phase13g_prereg_conclusion.csv").exists()
    assert (tmp_path / "phase13h_readiness_conclusion.csv").exists()


def test_phase13h_formula_lock_fails_if_feature_calculates_now(tmp_path):
    config = _config(tmp_path)
    registry = build_phase13g_calculation_registry(
        config["phase13g_feature_calculation_preregistration_spec"]
    )
    registry.loc[0, "calculate_now"] = True

    lock_check = build_phase13h_formula_registry_lock_check(registry)

    assert not bool(lock_check["passed"].all())