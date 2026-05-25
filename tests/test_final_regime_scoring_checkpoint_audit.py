from pathlib import Path

import pandas as pd

from market_strats.analysis.final_regime_scoring_checkpoint_audit import (
    build_phase11g_boundary_report_check,
    build_phase11g_branch_closure_check,
    build_phase11g_conclusion,
    build_phase11g_config_flag_check,
    build_phase11g_gate_report,
    build_phase11g_phase12a_boundary_check,
    build_phase11g_phase_conclusion_check,
    build_phase11g_phase_gate_report_check,
    build_phase11g_report_inventory_check,
    build_phase11g_scope_boundary_check,
    build_phase11g_summary,
    save_phase11g_final_regime_scoring_checkpoint_audit,
)


def _phase_config(tmp_path: Path):
    return {
        "audit_role": "Final Phase 11 regime scoring closeout/checkpoint audit only",
        "phase_branch": (
            "Phase 11 regime scoring architecture and diagnostic panel branch"
        ),
        "checkpoint_status": (
            "Phase 11 closed — regime scoring architecture and diagnostic panel "
            "prepared without scoring"
        ),
        "next_allowed_step": "Phase 12A score-calculation pre-registration spec only",
        "allow_score_calculation": False,
        "allow_numeric_score_weights": False,
        "allow_empirical_return_weights": False,
        "allow_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_strategy_backtest": False,
        "allow_model_training": False,
        "allow_new_data_ingestion": False,
        "allow_candidate_promotion": False,
        "expected_runtime_flags": {
            "phase11a_richer_information_architecture_review": False,
            "phase11b_regime_scoring_architecture_spec": False,
            "phase11c_regime_scoring_rulebook_spec": False,
            "phase11d_regime_scoring_diagnostic_panel_design": False,
            "phase11e_regime_scoring_diagnostic_panel_template_audit": False,
            "phase11f_regime_scoring_diagnostic_panel_content_audit": False,
            "phase11g_final_regime_scoring_checkpoint_audit": True,
            "relative_momentum_allocator": True,
        },
        "expected_report_prefixes": [
            "phase11a_architecture",
            "phase11b_regime_scoring",
            "phase11c_regime_scoring",
            "phase11d_diagnostic_panel",
            "phase11e_template",
            "phase11f_content",
        ],
        "expected_markdown_reports": [
            "phase11a_richer_information_architecture_review.md",
            "phase11b_regime_scoring_architecture_spec.md",
            "phase11c_regime_scoring_rulebook_spec.md",
            "phase11d_regime_scoring_diagnostic_panel_design.md",
            "phase11e_regime_scoring_diagnostic_panel_template_audit.md",
            "phase11f_regime_scoring_diagnostic_panel_content_audit.md",
        ],
        "phase_conclusion_reports": {
            "phase11a": str(tmp_path / "phase11a_architecture_conclusion.csv"),
            "phase11b": str(tmp_path / "phase11b_regime_scoring_conclusion.csv"),
            "phase11c": str(tmp_path / "phase11c_regime_scoring_conclusion.csv"),
            "phase11d": str(tmp_path / "phase11d_diagnostic_panel_conclusion.csv"),
            "phase11e": str(tmp_path / "phase11e_template_conclusion.csv"),
            "phase11f": str(tmp_path / "phase11f_content_conclusion.csv"),
        },
        "phase_gate_reports": {
            "phase11a": str(tmp_path / "phase11a_architecture_gate_report.csv"),
            "phase11b": str(tmp_path / "phase11b_regime_scoring_gate_report.csv"),
            "phase11c": str(tmp_path / "phase11c_regime_scoring_gate_report.csv"),
            "phase11d": str(tmp_path / "phase11d_diagnostic_panel_gate_report.csv"),
            "phase11e": str(tmp_path / "phase11e_template_gate_report.csv"),
            "phase11f": str(tmp_path / "phase11f_content_gate_report.csv"),
        },
        "required_phase_verdict_fragments": {
            "phase11a": "architecture review passed",
            "phase11b": "regime scoring architecture spec passed",
            "phase11c": "regime scoring rulebook spec passed",
            "phase11d": "diagnostic panel design passed",
            "phase11e": "diagnostic panel template audit passed",
            "phase11f": "diagnostic panel content audit passed",
        },
        "expected_boundary_reports": {
            "phase11e_boundary": str(
                tmp_path / "phase11f_content_phase11g_boundary_check.csv"
            ),
            "phase11f_scope": str(tmp_path / "phase11f_content_scope_boundary_check.csv"),
            "phase11f_boundary_content": str(
                tmp_path / "phase11f_content_boundary_check.csv"
            ),
        },
        "branch_closure_claims": {
            "regime_score_exists": False,
            "signal_exists": False,
            "allocation_rule_exists": False,
            "strategy_test_exists": False,
            "model_exists": False,
            "new_data_ingested": False,
            "candidate_promoted": False,
            "final_candidate_changed": False,
        },
        "phase12a_boundary": {
            "allowed_next_step": "Score-calculation pre-registration spec only",
            "forbidden_next_step": (
                "actual score calculation, signal creation, allocation rule, "
                "strategy backtest, model training, new data ingestion, or "
                "candidate promotion"
            ),
            "phase12a_may_define_score_formula_spec": True,
            "phase12a_may_define_non_return_weight_policy": True,
            "phase12a_may_calculate_scores": False,
            "phase12a_may_assign_empirical_weights": False,
            "phase12a_may_create_signal": False,
            "phase12a_may_test_strategy": False,
            "phase12a_may_train_model": False,
            "phase12a_may_ingest_new_data": False,
            "phase12a_may_promote_candidate": False,
        },
        "gates": {
            "require_report_inventory_present": True,
            "require_markdown_reports_present": True,
            "require_config_flags_clean_for_run": True,
            "require_phase_conclusions_passed": True,
            "require_phase_gate_reports_passed": True,
            "require_phase11f_locked": True,
            "require_boundary_reports_passed": True,
            "require_no_score_signal_model_strategy_promotion": True,
            "require_phase12a_boundary_spec_only": True,
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
                "Final Phase 11 regime scoring closeout/checkpoint audit only"
            ),
        },
    }


def _runtime_config(tmp_path: Path):
    return {
        "phase11a_richer_information_architecture_review": {"enabled": False},
        "phase11b_regime_scoring_architecture_spec": {"enabled": False},
        "phase11c_regime_scoring_rulebook_spec": {"enabled": False},
        "phase11d_regime_scoring_diagnostic_panel_design": {"enabled": False},
        "phase11e_regime_scoring_diagnostic_panel_template_audit": {
            "enabled": False
        },
        "phase11f_regime_scoring_diagnostic_panel_content_audit": {
            "enabled": False
        },
        "phase11g_final_regime_scoring_checkpoint_audit": {
            "enabled": True,
            **_phase_config(tmp_path),
        },
        "relative_momentum_allocator": {"enabled": True},
    }


def _write_reports(tmp_path: Path):
    phase_verdicts = {
        "phase11a_architecture": "Completed — architecture review passed",
        "phase11b_regime_scoring": (
            "Completed — regime scoring architecture spec passed"
        ),
        "phase11c_regime_scoring": "Completed — regime scoring rulebook spec passed",
        "phase11d_diagnostic_panel": "Completed — diagnostic panel design passed",
        "phase11e_template": "Completed — diagnostic panel template audit passed",
        "phase11f_content": "Completed — diagnostic panel content audit passed",
    }

    for prefix, verdict in phase_verdicts.items():
        pd.DataFrame(
            [
                {
                    "phase": prefix,
                    "verdict": verdict,
                    "all_gates_passed": True,
                    "strategy_promotion": False,
                    "candidate_promotion": False,
                }
            ]
        ).to_csv(tmp_path / f"{prefix}_conclusion.csv", index=False)

        pd.DataFrame(
            [
                {
                    "gate": "dummy gate",
                    "passed": True,
                    "result": "Passed",
                    "all_gates_passed": True,
                }
            ]
        ).to_csv(tmp_path / f"{prefix}_gate_report.csv", index=False)

    for markdown in [
        "phase11a_richer_information_architecture_review.md",
        "phase11b_regime_scoring_architecture_spec.md",
        "phase11c_regime_scoring_rulebook_spec.md",
        "phase11d_regime_scoring_diagnostic_panel_design.md",
        "phase11e_regime_scoring_diagnostic_panel_template_audit.md",
        "phase11f_regime_scoring_diagnostic_panel_content_audit.md",
    ]:
        (tmp_path / markdown).write_text("# report\n", encoding="utf-8")

    for boundary_name in [
        "phase11f_content_phase11g_boundary_check.csv",
        "phase11f_content_scope_boundary_check.csv",
        "phase11f_content_boundary_check.csv",
    ]:
        pd.DataFrame(
            [
                {
                    "boundary_item": "dummy",
                    "passed": True,
                    "result": "Passed",
                }
            ]
        ).to_csv(tmp_path / boundary_name, index=False)


def test_phase11g_builds_passing_checkpoint(tmp_path):
    _write_reports(tmp_path)
    phase_config = _phase_config(tmp_path)

    inventory = build_phase11g_report_inventory_check(
        reports_dir=tmp_path,
        phase_config=phase_config,
    )
    config_check = build_phase11g_config_flag_check(
        runtime_config=_runtime_config(tmp_path),
        expected_flags=phase_config["expected_runtime_flags"],
    )
    conclusion_check = build_phase11g_phase_conclusion_check(
        phase_config=phase_config,
    )
    gate_check = build_phase11g_phase_gate_report_check(
        phase_config=phase_config,
    )
    boundary_check = build_phase11g_boundary_report_check(
        phase_config=phase_config,
    )
    closure_check = build_phase11g_branch_closure_check(
        phase_config=phase_config,
    )
    phase12a = build_phase11g_phase12a_boundary_check(phase_config)
    scope = build_phase11g_scope_boundary_check(phase_config)

    summary = build_phase11g_summary(
        phase_config=phase_config,
        report_inventory_check=inventory,
        config_flag_check=config_check,
        phase_conclusion_check=conclusion_check,
        phase_gate_report_check=gate_check,
        boundary_report_check=boundary_check,
        branch_closure_check=closure_check,
        phase12a_boundary_check=phase12a,
        scope_boundary_check=scope,
    )
    gate_report = build_phase11g_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase11g_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — final Phase 11 regime scoring checkpoint passed"
    )


def test_phase11g_fails_if_score_exists_claim_true(tmp_path):
    _write_reports(tmp_path)
    phase_config = _phase_config(tmp_path)
    phase_config["branch_closure_claims"]["regime_score_exists"] = True

    closure_check = build_phase11g_branch_closure_check(
        phase_config=phase_config,
    )

    assert not bool(closure_check["passed"].all())


def test_phase11g_save_writes_expected_reports(tmp_path):
    _write_reports(tmp_path)

    outputs = save_phase11g_final_regime_scoring_checkpoint_audit(
        config=_runtime_config(tmp_path),
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase11g_final_checkpoint_report_inventory_check.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_config_flag_check.csv").exists()
    assert (
        tmp_path / "phase11g_final_checkpoint_phase_conclusion_check.csv"
    ).exists()
    assert (
        tmp_path / "phase11g_final_checkpoint_phase_gate_report_check.csv"
    ).exists()
    assert (tmp_path / "phase11g_final_checkpoint_boundary_report_check.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_branch_closure_check.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_phase12a_boundary_check.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_scope_boundary_check.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_summary.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_gate_report.csv").exists()
    assert (tmp_path / "phase11g_final_checkpoint_conclusion.csv").exists()
    assert (
        tmp_path / "phase11g_final_regime_scoring_checkpoint_audit.md"
    ).exists()