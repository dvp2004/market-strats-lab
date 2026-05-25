from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_scoring_diagnostic_panel_content_audit import (
    build_phase11f_blocked_family_content_check,
    build_phase11f_boundary_content_check,
    build_phase11f_component_content_check,
    build_phase11f_conclusion,
    build_phase11f_direction_content_check,
    build_phase11f_gate_report,
    build_phase11f_missingness_content_check,
    build_phase11f_phase11e_result_check,
    build_phase11f_phase11g_boundary_check,
    build_phase11f_scope_boundary_check,
    build_phase11f_source_template_inventory,
    build_phase11f_summary,
    build_phase11f_weighting_content_check,
    save_phase11f_regime_scoring_diagnostic_panel_content_audit,
)


def _phase_config(tmp_path: Path):
    return {
        "audit_role": "Regime scoring diagnostic panel content audit only",
        "phase_branch": "Phase 11 architecture review",
        "source_phase": "Phase 11E",
        "proposed_next_phase": "Phase 11G",
        "source_template_reports": {
            "component_availability_report": str(
                tmp_path / "phase11e_template_component_availability_report.csv"
            ),
            "component_direction_report": str(
                tmp_path / "phase11e_template_component_direction_report.csv"
            ),
            "missingness_report": str(
                tmp_path / "phase11e_template_missingness_report.csv"
            ),
            "weighting_policy_report": str(
                tmp_path / "phase11e_template_weighting_policy_report.csv"
            ),
            "blocked_family_report": str(
                tmp_path / "phase11e_template_blocked_family_report.csv"
            ),
            "boundary_report": str(tmp_path / "phase11e_template_boundary_report.csv"),
            "schema_compliance": str(
                tmp_path / "phase11e_template_schema_compliance.csv"
            ),
            "template_inventory": str(tmp_path / "phase11e_template_inventory.csv"),
            "phase11e_conclusion": str(
                tmp_path / "phase11e_template_conclusion.csv"
            ),
        },
        "allow_score_calculation": False,
        "allow_numeric_score_weights": False,
        "allow_empirical_return_weights": False,
        "allow_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_strategy_backtest": False,
        "allow_model_training": False,
        "allow_new_data_ingestion": False,
        "allow_candidate_promotion": False,
        "expected_components": [
            "technical_regime_context",
            "macro_regime_context",
            "validation_risk_context",
            "future_fundamental_context",
            "future_sentiment_context",
        ],
        "expected_active_components": [
            "technical_regime_context",
            "macro_regime_context",
            "validation_risk_context",
        ],
        "expected_blocked_families": [
            "fundamental_valuation",
            "sentiment_narrative",
        ],
        "expected_directions": ["supportive", "neutral", "fragile"],
        "expected_boundary_items": [
            "score_calculation",
            "numeric_score_weights",
            "empirical_return_weights",
            "signal_creation",
            "allocation_rule_creation",
            "strategy_backtest",
            "model_training",
            "new_data_ingestion",
            "candidate_promotion",
        ],
        "phase11g_boundary": {
            "allowed_next_step": (
                "Regime scoring diagnostic panel closeout audit only"
            ),
            "forbidden_next_step": (
                "score calculation, signal creation, strategy backtest, "
                "model training, new data ingestion, or candidate promotion"
            ),
            "phase11g_may_close_diagnostic_panel_branch": True,
            "phase11g_may_calculate_scores": False,
            "phase11g_may_assign_weights": False,
            "phase11g_may_create_signal": False,
            "phase11g_may_test_strategy": False,
            "phase11g_may_train_model": False,
            "phase11g_may_ingest_new_data": False,
            "phase11g_may_promote_candidate": False,
        },
        "gates": {
            "require_source_templates_present": True,
            "require_phase11e_passed": True,
            "require_schema_compliance_passed": True,
            "require_component_content_consistency": True,
            "require_direction_content_consistency": True,
            "require_missingness_content_consistency": True,
            "require_weighting_content_consistency": True,
            "require_blocked_family_content_consistency": True,
            "require_boundary_content_consistency": True,
            "require_phase11g_boundary_closeout_only": True,
            "require_no_score_calculation": True,
            "require_no_numeric_score_weights": True,
            "require_no_empirical_return_weights": True,
            "require_no_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_strategy_backtest": True,
            "require_no_model_training": True,
            "require_no_new_data_ingestion": True,
            "require_no_candidate_promotion": True,
            "required_audit_role": (
                "Regime scoring diagnostic panel content audit only"
            ),
        },
    }


def _write_phase11e_templates(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "expected_status": "conceptual_only",
                "availability_status": "conceptual_only",
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "expected_status": "conceptual_only",
                "availability_status": "conceptual_only",
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "expected_status": "conceptual_only",
                "availability_status": "conceptual_only",
            },
            {
                "component_id": "future_fundamental_context",
                "family": "fundamental_valuation",
                "expected_status": "blocked",
                "availability_status": "blocked",
            },
            {
                "component_id": "future_sentiment_context",
                "family": "sentiment_narrative",
                "expected_status": "blocked",
                "availability_status": "blocked",
            },
        ]
    ).to_csv(
        tmp_path / "phase11e_template_component_availability_report.csv",
        index=False,
    )

    direction_rows = []
    for component_id, family in [
        ("technical_regime_context", "technical"),
        ("macro_regime_context", "macro_rates_inflation"),
        ("validation_risk_context", "validation_risk"),
    ]:
        for direction in ["supportive", "neutral", "fragile"]:
            direction_rows.append(
                {
                    "component_id": component_id,
                    "family": family,
                    "conceptual_direction": direction,
                    "trading_allowed": False,
                    "signal_allowed": False,
                }
            )
    pd.DataFrame(direction_rows).to_csv(
        tmp_path / "phase11e_template_component_direction_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "component_id": f"c{index}",
                "returns_inference_allowed": False,
                "silent_fill_allowed": False,
            }
            for index in range(5)
        ]
    ).to_csv(tmp_path / "phase11e_template_missingness_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "policy_id": f"w{index}",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "cutoff_search_allowed": False,
                "pre_registration_required": True,
            }
            for index in range(5)
        ]
    ).to_csv(
        tmp_path / "phase11e_template_weighting_policy_report.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "family": "fundamental_valuation",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
            {
                "family": "sentiment_narrative",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
        ]
    ).to_csv(tmp_path / "phase11e_template_blocked_family_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "boundary_item": item,
                "allowed": False,
                "expected_allowed": False,
                "passed": True,
            }
            for item in [
                "score_calculation",
                "numeric_score_weights",
                "empirical_return_weights",
                "signal_creation",
                "allocation_rule_creation",
                "strategy_backtest",
                "model_training",
                "new_data_ingestion",
                "candidate_promotion",
            ]
        ]
    ).to_csv(tmp_path / "phase11e_template_boundary_report.csv", index=False)

    pd.DataFrame(
        [
            {"report_name": f"r{index}", "schema_passed": True}
            for index in range(6)
        ]
    ).to_csv(tmp_path / "phase11e_template_schema_compliance.csv", index=False)

    pd.DataFrame(
        [
            {"report_name": f"r{index}", "generated": True}
            for index in range(6)
        ]
    ).to_csv(tmp_path / "phase11e_template_inventory.csv", index=False)

    pd.DataFrame(
        [
            {
                "phase": "Phase 11E",
                "verdict": "Completed — diagnostic panel template audit passed",
                "all_gates_passed": True,
                "strategy_promotion": False,
                "candidate_promotion": False,
            }
        ]
    ).to_csv(tmp_path / "phase11e_template_conclusion.csv", index=False)


def test_phase11f_content_checks_pass_valid_templates(tmp_path):
    _write_phase11e_templates(tmp_path)
    phase_config = _phase_config(tmp_path)

    inventory = build_phase11f_source_template_inventory(phase_config)
    phase11e_check = build_phase11f_phase11e_result_check(
        phase11e_conclusion=pd.read_csv(
            tmp_path / "phase11e_template_conclusion.csv"
        ),
        schema_compliance=pd.read_csv(
            tmp_path / "phase11e_template_schema_compliance.csv"
        ),
    )
    component_check = build_phase11f_component_content_check(
        component_availability=pd.read_csv(
            tmp_path / "phase11e_template_component_availability_report.csv"
        ),
        expected_components=phase_config["expected_components"],
        expected_active_components=phase_config["expected_active_components"],
        expected_blocked_families=phase_config["expected_blocked_families"],
    )
    direction_check = build_phase11f_direction_content_check(
        component_direction=pd.read_csv(
            tmp_path / "phase11e_template_component_direction_report.csv"
        ),
        expected_active_components=phase_config["expected_active_components"],
        expected_directions=phase_config["expected_directions"],
    )
    missingness_check = build_phase11f_missingness_content_check(
        pd.read_csv(tmp_path / "phase11e_template_missingness_report.csv")
    )
    weighting_check = build_phase11f_weighting_content_check(
        pd.read_csv(tmp_path / "phase11e_template_weighting_policy_report.csv")
    )
    blocked_check = build_phase11f_blocked_family_content_check(
        blocked_family=pd.read_csv(
            tmp_path / "phase11e_template_blocked_family_report.csv"
        ),
        expected_blocked_families=phase_config["expected_blocked_families"],
    )
    boundary_check = build_phase11f_boundary_content_check(
        boundary=pd.read_csv(tmp_path / "phase11e_template_boundary_report.csv"),
        expected_boundary_items=phase_config["expected_boundary_items"],
    )
    phase11g = build_phase11f_phase11g_boundary_check(phase_config)
    scope = build_phase11f_scope_boundary_check(phase_config)

    assert bool(inventory["present"].all())
    assert bool(phase11e_check["passed"].all())
    assert bool(component_check["passed"].all())
    assert bool(direction_check["passed"].all())
    assert bool(missingness_check["passed"].all())
    assert bool(weighting_check["passed"].all())
    assert bool(blocked_check["passed"].all())
    assert bool(boundary_check["passed"].all())
    assert bool(phase11g["passed"].all())
    assert bool(scope["passed"].all())


def test_phase11f_gate_report_passes_valid_content_audit(tmp_path):
    _write_phase11e_templates(tmp_path)
    phase_config = _phase_config(tmp_path)

    summary = build_phase11f_summary(
        phase_config=phase_config,
        source_template_inventory=build_phase11f_source_template_inventory(
            phase_config
        ),
        phase11e_result_check=build_phase11f_phase11e_result_check(
            phase11e_conclusion=pd.read_csv(
                tmp_path / "phase11e_template_conclusion.csv"
            ),
            schema_compliance=pd.read_csv(
                tmp_path / "phase11e_template_schema_compliance.csv"
            ),
        ),
        component_content_check=build_phase11f_component_content_check(
            component_availability=pd.read_csv(
                tmp_path / "phase11e_template_component_availability_report.csv"
            ),
            expected_components=phase_config["expected_components"],
            expected_active_components=phase_config["expected_active_components"],
            expected_blocked_families=phase_config["expected_blocked_families"],
        ),
        direction_content_check=build_phase11f_direction_content_check(
            component_direction=pd.read_csv(
                tmp_path / "phase11e_template_component_direction_report.csv"
            ),
            expected_active_components=phase_config["expected_active_components"],
            expected_directions=phase_config["expected_directions"],
        ),
        missingness_content_check=build_phase11f_missingness_content_check(
            pd.read_csv(tmp_path / "phase11e_template_missingness_report.csv")
        ),
        weighting_content_check=build_phase11f_weighting_content_check(
            pd.read_csv(tmp_path / "phase11e_template_weighting_policy_report.csv")
        ),
        blocked_family_content_check=build_phase11f_blocked_family_content_check(
            blocked_family=pd.read_csv(
                tmp_path / "phase11e_template_blocked_family_report.csv"
            ),
            expected_blocked_families=phase_config["expected_blocked_families"],
        ),
        boundary_content_check=build_phase11f_boundary_content_check(
            boundary=pd.read_csv(tmp_path / "phase11e_template_boundary_report.csv"),
            expected_boundary_items=phase_config["expected_boundary_items"],
        ),
        phase11g_boundary_check=build_phase11f_phase11g_boundary_check(
            phase_config
        ),
        scope_boundary_check=build_phase11f_scope_boundary_check(phase_config),
    )
    gate_report = build_phase11f_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11f_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — diagnostic panel content audit passed"
    )


def test_phase11f_fails_if_signal_boundary_is_true(tmp_path):
    _write_phase11e_templates(tmp_path)
    phase_config = _phase_config(tmp_path)
    phase_config["allow_signal_creation"] = True

    summary = build_phase11f_summary(
        phase_config=phase_config,
        source_template_inventory=build_phase11f_source_template_inventory(
            phase_config
        ),
        phase11e_result_check=build_phase11f_phase11e_result_check(
            phase11e_conclusion=pd.read_csv(
                tmp_path / "phase11e_template_conclusion.csv"
            ),
            schema_compliance=pd.read_csv(
                tmp_path / "phase11e_template_schema_compliance.csv"
            ),
        ),
        component_content_check=build_phase11f_component_content_check(
            component_availability=pd.read_csv(
                tmp_path / "phase11e_template_component_availability_report.csv"
            ),
            expected_components=phase_config["expected_components"],
            expected_active_components=phase_config["expected_active_components"],
            expected_blocked_families=phase_config["expected_blocked_families"],
        ),
        direction_content_check=build_phase11f_direction_content_check(
            component_direction=pd.read_csv(
                tmp_path / "phase11e_template_component_direction_report.csv"
            ),
            expected_active_components=phase_config["expected_active_components"],
            expected_directions=phase_config["expected_directions"],
        ),
        missingness_content_check=build_phase11f_missingness_content_check(
            pd.read_csv(tmp_path / "phase11e_template_missingness_report.csv")
        ),
        weighting_content_check=build_phase11f_weighting_content_check(
            pd.read_csv(tmp_path / "phase11e_template_weighting_policy_report.csv")
        ),
        blocked_family_content_check=build_phase11f_blocked_family_content_check(
            blocked_family=pd.read_csv(
                tmp_path / "phase11e_template_blocked_family_report.csv"
            ),
            expected_blocked_families=phase_config["expected_blocked_families"],
        ),
        boundary_content_check=build_phase11f_boundary_content_check(
            boundary=pd.read_csv(tmp_path / "phase11e_template_boundary_report.csv"),
            expected_boundary_items=phase_config["expected_boundary_items"],
        ),
        phase11g_boundary_check=build_phase11f_phase11g_boundary_check(
            phase_config
        ),
        scope_boundary_check=build_phase11f_scope_boundary_check(phase_config),
    )
    gate_report = build_phase11f_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11f_writes_expected_reports(tmp_path):
    _write_phase11e_templates(tmp_path)
    config = {
        "phase11f_regime_scoring_diagnostic_panel_content_audit": {
            "enabled": True,
            **_phase_config(tmp_path),
        }
    }

    outputs = save_phase11f_regime_scoring_diagnostic_panel_content_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11f_content_source_template_inventory.csv").exists()
    assert (tmp_path / "phase11f_content_phase11e_result_check.csv").exists()
    assert (tmp_path / "phase11f_content_component_check.csv").exists()
    assert (tmp_path / "phase11f_content_direction_check.csv").exists()
    assert (tmp_path / "phase11f_content_missingness_check.csv").exists()
    assert (tmp_path / "phase11f_content_weighting_check.csv").exists()
    assert (tmp_path / "phase11f_content_blocked_family_check.csv").exists()
    assert (tmp_path / "phase11f_content_boundary_check.csv").exists()
    assert (tmp_path / "phase11f_content_phase11g_boundary_check.csv").exists()
    assert (tmp_path / "phase11f_content_scope_boundary_check.csv").exists()
    assert (tmp_path / "phase11f_content_summary.csv").exists()
    assert (tmp_path / "phase11f_content_gate_report.csv").exists()
    assert (tmp_path / "phase11f_content_conclusion.csv").exists()
    assert (
        tmp_path / "phase11f_regime_scoring_diagnostic_panel_content_audit.md"
    ).exists()