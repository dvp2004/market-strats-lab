from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_scoring_diagnostic_panel_template_audit import (
    build_phase11e_conclusion,
    build_phase11e_gate_report,
    build_phase11e_phase11f_boundary_check,
    build_phase11e_schema_compliance_report,
    build_phase11e_source_design_inventory,
    build_phase11e_summary,
    build_phase11e_template_inventory_report,
    build_phase11e_template_reports,
    save_phase11e_regime_scoring_diagnostic_panel_template_audit,
)


def _phase_config(tmp_path: Path):
    return {
        "implementation_role": (
            "Regime scoring diagnostic panel template implementation audit only"
        ),
        "phase_branch": "Phase 11 architecture review",
        "source_phase": "Phase 11D",
        "proposed_next_phase": "Phase 11F",
        "source_design_reports": {
            "panel_layout_spec": str(
                tmp_path / "phase11d_diagnostic_panel_layout_spec.csv"
            ),
            "required_columns_spec": str(
                tmp_path / "phase11d_diagnostic_panel_required_columns_spec.csv"
            ),
            "component_availability_spec": str(
                tmp_path
                / "phase11d_diagnostic_panel_component_availability_spec.csv"
            ),
            "conceptual_direction_spec": str(
                tmp_path / "phase11d_diagnostic_panel_conceptual_direction_spec.csv"
            ),
            "weighting_policy_spec": str(
                tmp_path / "phase11d_diagnostic_panel_weighting_policy_spec.csv"
            ),
            "blocked_family_spec": str(
                tmp_path / "phase11d_diagnostic_panel_blocked_family_spec.csv"
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
        "phase11f_boundary": {
            "allowed_next_step": "Regime scoring diagnostic panel content audit only",
            "forbidden_next_step": (
                "score calculation, signal creation, strategy backtest, "
                "model training, new data ingestion, or candidate promotion"
            ),
            "phase11f_may_populate_templates_from_existing_phase_reports": True,
            "phase11f_may_calculate_scores": False,
            "phase11f_may_assign_weights": False,
            "phase11f_may_create_signal": False,
            "phase11f_may_test_strategy": False,
            "phase11f_may_train_model": False,
            "phase11f_may_ingest_new_data": False,
            "phase11f_may_promote_candidate": False,
        },
        "gates": {
            "require_source_design_reports_present": True,
            "require_template_reports_generated": True,
            "min_template_reports": 6,
            "require_schema_compliance": True,
            "require_component_availability_rows": True,
            "min_component_availability_rows": 5,
            "require_direction_rows": True,
            "min_direction_rows": 9,
            "require_missingness_rows": True,
            "min_missingness_rows": 5,
            "require_weighting_policy_rows": True,
            "min_weighting_policy_rows": 5,
            "require_blocked_family_rows": True,
            "min_blocked_family_rows": 2,
            "require_boundary_rows": True,
            "min_boundary_rows": 9,
            "require_non_signal_templates": True,
            "require_no_returns_usage": True,
            "require_weighting_non_empirical": True,
            "require_blocked_families_clean": True,
            "require_phase11f_boundary_content_audit_only": True,
            "require_no_score_calculation": True,
            "require_no_numeric_score_weights": True,
            "require_no_empirical_return_weights": True,
            "require_no_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_strategy_backtest": True,
            "require_no_model_training": True,
            "require_no_new_data_ingestion": True,
            "require_no_candidate_promotion": True,
            "required_implementation_role": (
                "Regime scoring diagnostic panel template implementation audit only"
            ),
        },
    }


def _write_phase11d_design_reports(tmp_path: Path):
    panel_layout = pd.DataFrame(
        [
            {
                "panel_id": "component_availability_panel",
                "report_name": "component_availability_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 8,
            },
            {
                "panel_id": "conceptual_direction_panel",
                "report_name": "component_direction_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 8,
            },
            {
                "panel_id": "missingness_panel",
                "report_name": "missingness_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 8,
            },
            {
                "panel_id": "weighting_policy_panel",
                "report_name": "weighting_policy_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 7,
            },
            {
                "panel_id": "blocked_family_panel",
                "report_name": "blocked_family_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 6,
            },
            {
                "panel_id": "boundary_panel",
                "report_name": "boundary_report",
                "required": True,
                "allowed_to_use_returns": False,
                "allowed_to_create_signal": False,
                "required_column_count": 5,
            },
        ]
    )
    panel_layout.to_csv(
        tmp_path / "phase11d_diagnostic_panel_layout_spec.csv",
        index=False,
    )

    required_columns = {
        "component_availability_report": [
            "component_id",
            "family",
            "expected_status",
            "availability_status",
            "source_dependency",
            "unavailable_reason",
            "blocked_reason",
            "future_unblock_requirement",
        ],
        "component_direction_report": [
            "component_id",
            "family",
            "direction_id",
            "conceptual_direction",
            "direction_source",
            "trading_allowed",
            "signal_allowed",
            "notes",
        ],
        "missingness_report": [
            "component_id",
            "family",
            "evidence_status",
            "missingness_reason",
            "handling_policy",
            "returns_inference_allowed",
            "silent_fill_allowed",
            "default_action",
        ],
        "weighting_policy_report": [
            "policy_id",
            "component_id",
            "weighting_policy",
            "numeric_weight_allowed",
            "empirical_return_weight_allowed",
            "cutoff_search_allowed",
            "pre_registration_required",
        ],
        "blocked_family_report": [
            "family",
            "blocked_status",
            "blocked_reason",
            "unblock_requires",
            "current_use_allowed",
            "score_component_allowed",
        ],
        "boundary_report": [
            "boundary_item",
            "allowed",
            "expected_allowed",
            "passed",
            "detail",
        ],
    }
    rows = []
    for report_name, columns in required_columns.items():
        for column in columns:
            rows.append({"report_name": report_name, "required_column": column})
    pd.DataFrame(rows).to_csv(
        tmp_path / "phase11d_diagnostic_panel_required_columns_spec.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 9/11C",
                "future_unblock_requirement": "Existing diagnostics only.",
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 10/11C",
                "future_unblock_requirement": "Existing diagnostics only.",
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "expected_status": "conceptual_only",
                "source_dependency": "Phase 8/9/10/11C",
                "future_unblock_requirement": "Existing validation only.",
            },
            {
                "component_id": "future_fundamental_context",
                "family": "fundamental_valuation",
                "expected_status": "blocked",
                "source_dependency": "No audit.",
                "future_unblock_requirement": "Future feasibility audit.",
            },
            {
                "component_id": "future_sentiment_context",
                "family": "sentiment_narrative",
                "expected_status": "blocked",
                "source_dependency": "No audit.",
                "future_unblock_requirement": "Future feasibility audit.",
            },
        ]
    ).to_csv(
        tmp_path / "phase11d_diagnostic_panel_component_availability_spec.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "component_id": "technical_regime_context",
                "family": "technical",
                "allowed_directions": "supportive; neutral; fragile",
                "trading_allowed": False,
                "signal_allowed": False,
            },
            {
                "component_id": "macro_regime_context",
                "family": "macro_rates_inflation",
                "allowed_directions": "supportive; neutral; fragile",
                "trading_allowed": False,
                "signal_allowed": False,
            },
            {
                "component_id": "validation_risk_context",
                "family": "validation_risk",
                "allowed_directions": "supportive; neutral; fragile",
                "trading_allowed": False,
                "signal_allowed": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase11d_diagnostic_panel_conceptual_direction_spec.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "policy_id": f"w{index}",
                "policy": f"policy {index}",
                "numeric_weight_allowed": False,
                "empirical_return_weight_allowed": False,
                "required": True,
            }
            for index in range(1, 6)
        ]
    ).to_csv(
        tmp_path / "phase11d_diagnostic_panel_weighting_policy_spec.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "family": "fundamental_valuation",
                "blocked_status": "blocked",
                "blocked_reason": "No audit.",
                "unblock_requires": "Future audit.",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
            {
                "family": "sentiment_narrative",
                "blocked_status": "blocked",
                "blocked_reason": "No audit.",
                "unblock_requires": "Future audit.",
                "current_use_allowed": False,
                "score_component_allowed": False,
            },
        ]
    ).to_csv(
        tmp_path / "phase11d_diagnostic_panel_blocked_family_spec.csv",
        index=False,
    )


def test_phase11e_builds_schema_compliant_templates(tmp_path):
    _write_phase11d_design_reports(tmp_path)
    phase_config = _phase_config(tmp_path)

    inventory = build_phase11e_source_design_inventory(phase_config)
    source_paths = phase_config["source_design_reports"]
    source_tables = {
        "panel_layout_spec": pd.read_csv(source_paths["panel_layout_spec"]),
        "required_columns_spec": pd.read_csv(source_paths["required_columns_spec"]),
        "component_availability_spec": pd.read_csv(
            source_paths["component_availability_spec"]
        ),
        "conceptual_direction_spec": pd.read_csv(
            source_paths["conceptual_direction_spec"]
        ),
        "weighting_policy_spec": pd.read_csv(source_paths["weighting_policy_spec"]),
        "blocked_family_spec": pd.read_csv(source_paths["blocked_family_spec"]),
    }
    templates = build_phase11e_template_reports(
        phase_config=phase_config,
        source_tables=source_tables,
    )
    schema = build_phase11e_schema_compliance_report(
        panel_layout_spec=source_tables["panel_layout_spec"],
        required_columns_spec=source_tables["required_columns_spec"],
        template_reports=templates,
    )
    template_inventory = build_phase11e_template_inventory_report(
        template_reports=templates,
    )
    boundary = build_phase11e_phase11f_boundary_check(phase_config)

    assert bool(inventory["present"].all())
    assert len(templates) == 6
    assert bool(schema["schema_passed"].all())
    assert not template_inventory.empty
    assert bool(boundary["passed"].all())


def test_phase11e_gate_report_passes_valid_template_audit(tmp_path):
    _write_phase11d_design_reports(tmp_path)
    phase_config = _phase_config(tmp_path)
    source_paths = phase_config["source_design_reports"]

    source_tables = {
        "panel_layout_spec": pd.read_csv(source_paths["panel_layout_spec"]),
        "required_columns_spec": pd.read_csv(source_paths["required_columns_spec"]),
        "component_availability_spec": pd.read_csv(
            source_paths["component_availability_spec"]
        ),
        "conceptual_direction_spec": pd.read_csv(
            source_paths["conceptual_direction_spec"]
        ),
        "weighting_policy_spec": pd.read_csv(source_paths["weighting_policy_spec"]),
        "blocked_family_spec": pd.read_csv(source_paths["blocked_family_spec"]),
    }
    templates = build_phase11e_template_reports(
        phase_config=phase_config,
        source_tables=source_tables,
    )
    schema = build_phase11e_schema_compliance_report(
        panel_layout_spec=source_tables["panel_layout_spec"],
        required_columns_spec=source_tables["required_columns_spec"],
        template_reports=templates,
    )
    inventory = build_phase11e_source_design_inventory(phase_config)
    template_inventory = build_phase11e_template_inventory_report(
        template_reports=templates,
    )
    boundary = build_phase11e_phase11f_boundary_check(phase_config)
    summary = build_phase11e_summary(
        phase_config=phase_config,
        source_design_inventory=inventory,
        template_inventory=template_inventory,
        schema_compliance=schema,
        template_reports=templates,
        phase11f_boundary_check=boundary,
    )
    gate_report = build_phase11e_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11e_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — diagnostic panel template audit passed"
    )


def test_phase11e_fails_if_score_calculation_allowed(tmp_path):
    _write_phase11d_design_reports(tmp_path)
    phase_config = _phase_config(tmp_path)
    phase_config["allow_score_calculation"] = True
    source_paths = phase_config["source_design_reports"]

    source_tables = {
        "panel_layout_spec": pd.read_csv(source_paths["panel_layout_spec"]),
        "required_columns_spec": pd.read_csv(source_paths["required_columns_spec"]),
        "component_availability_spec": pd.read_csv(
            source_paths["component_availability_spec"]
        ),
        "conceptual_direction_spec": pd.read_csv(
            source_paths["conceptual_direction_spec"]
        ),
        "weighting_policy_spec": pd.read_csv(source_paths["weighting_policy_spec"]),
        "blocked_family_spec": pd.read_csv(source_paths["blocked_family_spec"]),
    }
    templates = build_phase11e_template_reports(
        phase_config=phase_config,
        source_tables=source_tables,
    )
    schema = build_phase11e_schema_compliance_report(
        panel_layout_spec=source_tables["panel_layout_spec"],
        required_columns_spec=source_tables["required_columns_spec"],
        template_reports=templates,
    )
    summary = build_phase11e_summary(
        phase_config=phase_config,
        source_design_inventory=build_phase11e_source_design_inventory(phase_config),
        template_inventory=build_phase11e_template_inventory_report(
            template_reports=templates,
        ),
        schema_compliance=schema,
        template_reports=templates,
        phase11f_boundary_check=build_phase11e_phase11f_boundary_check(
            phase_config
        ),
    )
    gate_report = build_phase11e_gate_report(
        phase_config=phase_config,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase11e_writes_expected_reports(tmp_path):
    _write_phase11d_design_reports(tmp_path)
    config = {
        "phase11e_regime_scoring_diagnostic_panel_template_audit": {
            "enabled": True,
            **_phase_config(tmp_path),
        }
    }

    outputs = save_phase11e_regime_scoring_diagnostic_panel_template_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11e_template_component_availability_report.csv").exists()
    assert (tmp_path / "phase11e_template_component_direction_report.csv").exists()
    assert (tmp_path / "phase11e_template_missingness_report.csv").exists()
    assert (tmp_path / "phase11e_template_weighting_policy_report.csv").exists()
    assert (tmp_path / "phase11e_template_blocked_family_report.csv").exists()
    assert (tmp_path / "phase11e_template_boundary_report.csv").exists()
    assert (tmp_path / "phase11e_template_schema_compliance.csv").exists()
    assert (tmp_path / "phase11e_template_gate_report.csv").exists()
    assert (tmp_path / "phase11e_template_conclusion.csv").exists()
    assert (
        tmp_path / "phase11e_regime_scoring_diagnostic_panel_template_audit.md"
    ).exists()