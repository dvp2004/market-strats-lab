import pandas as pd

from market_strats.analysis.technical_extension_closeout_audit import (
    build_phase9e_closeout_summary,
    build_phase9e_config_flag_check,
    build_phase9e_conclusion,
    build_phase9e_gate_report,
    build_phase9e_phase9d_failure_check,
    build_phase9e_report_inventory_check,
    save_phase9e_technical_extension_closeout_audit,
)


def _phase_config():
    return {
        "closeout_scope": {
            "branch": "Phase 9 technical indicator extension",
            "status": "Closed — no rule promoted",
            "successor_candidate_created": False,
            "final_candidate_changed": False,
            "rule_promotion_allowed": False,
            "next_allowed_step": "Pause or checkpoint consistency",
        },
        "expected_disabled_flags": {
            "phase9a_technical_indicator_expansion_diagnostic": False,
            "phase9b_technical_regime_cluster_stability_audit": False,
            "phase9c_preregistered_technical_rule_design_spec": False,
            "phase9d_preregistered_technical_rule_test": False,
            "phase9e_technical_extension_closeout_audit": True,
            "relative_momentum_allocator": True,
        },
        "expected_report_prefixes": [
            "phase9a_technical",
            "phase9b_technical",
            "phase9c_preregistered",
            "phase9d_preregistered",
        ],
        "phase9d_expected": {
            "conclusion_verdict": "Failed / no pre-registered rule passed",
            "no_passed_rules": True,
            "no_strategy_promotion": True,
            "no_successor_candidate": True,
        },
        "required_closeout_wording": [
            "No technical rule was promoted",
        ],
        "gates": {
            "require_expected_reports_present": True,
            "require_config_flags_match": True,
            "require_phase9d_failure_documented": True,
            "require_no_phase9d_rule_passed": True,
            "require_no_strategy_promotion": True,
            "require_no_successor_candidate": True,
            "require_branch_closed_without_promotion": True,
        },
    }


def _runtime_config():
    return {
        "phase9a_technical_indicator_expansion_diagnostic": {"enabled": False},
        "phase9b_technical_regime_cluster_stability_audit": {"enabled": False},
        "phase9c_preregistered_technical_rule_design_spec": {"enabled": False},
        "phase9d_preregistered_technical_rule_test": {"enabled": False},
        "phase9e_technical_extension_closeout_audit": {
            "enabled": True,
            **_phase_config(),
        },
        "relative_momentum_allocator": {"enabled": True},
    }


def _write_phase_reports(tmp_path):
    for prefix in [
        "phase9a_technical",
        "phase9b_technical",
        "phase9c_preregistered",
    ]:
        (tmp_path / f"{prefix}_dummy.csv").write_text("x\n1\n", encoding="utf-8")

    pd.DataFrame(
        [
            {
                "phase": "Phase 9D",
                "diagnostic": "Pre-registered technical rule test",
                "verdict": "Failed / no pre-registered rule passed",
                "passed_rules": "",
                "all_gates_passed_for_at_least_one_rule": False,
                "interpretation": "No rule passed.",
            }
        ]
    ).to_csv(tmp_path / "phase9d_preregistered_rule_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "rule_id": "H1",
                "gate": "Example",
                "passed": False,
                "all_rule_gates_passed": False,
                "any_rule_passed": False,
            },
            {
                "rule_id": "H2",
                "gate": "Example",
                "passed": False,
                "all_rule_gates_passed": False,
                "any_rule_passed": False,
            },
        ]
    ).to_csv(tmp_path / "phase9d_preregistered_rule_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "rule_id": "H1",
                "strategy_promotion": False,
                "role": "Candidate for further validation only",
            },
            {
                "rule_id": "H2",
                "strategy_promotion": False,
                "role": "Candidate for further validation only",
            },
        ]
    ).to_csv(
        tmp_path / "phase9d_preregistered_rule_comparison_summary.csv",
        index=False,
    )


def test_phase9e_checks_and_gate_report_pass(tmp_path):
    _write_phase_reports(tmp_path)
    phase_config = _phase_config()
    runtime_config = _runtime_config()

    report_check = build_phase9e_report_inventory_check(
        reports_dir=tmp_path,
        expected_report_prefixes=phase_config["expected_report_prefixes"],
    )
    config_check = build_phase9e_config_flag_check(
        runtime_config=runtime_config,
        expected_flags=phase_config["expected_disabled_flags"],
    )
    failure_check = build_phase9e_phase9d_failure_check(
        reports_dir=tmp_path,
        phase_config=phase_config,
    )
    summary = build_phase9e_closeout_summary(
        phase_config=phase_config,
        report_inventory_check=report_check,
        config_flag_check=config_check,
        phase9d_failure_check=failure_check,
    )
    gate_report = build_phase9e_gate_report(
        report_inventory_check=report_check,
        config_flag_check=config_check,
        phase9d_failure_check=failure_check,
        closeout_summary=summary,
        phase_config=phase_config,
    )
    conclusion = build_phase9e_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — technical extension closed without promotion"
    )


def test_phase9e_fails_if_phase9d_conclusion_does_not_show_failure(tmp_path):
    _write_phase_reports(tmp_path)
    pd.DataFrame(
        [
            {
                "phase": "Phase 9D",
                "diagnostic": "Pre-registered technical rule test",
                "verdict": "Passed for further validation",
                "passed_rules": "H1",
            }
        ]
    ).to_csv(tmp_path / "phase9d_preregistered_rule_conclusion.csv", index=False)

    phase_config = _phase_config()
    failure_check = build_phase9e_phase9d_failure_check(
        reports_dir=tmp_path,
        phase_config=phase_config,
    )

    assert not bool(failure_check["passed"].all())


def test_save_phase9e_writes_expected_reports(tmp_path):
    _write_phase_reports(tmp_path)
    config = _runtime_config()

    outputs = save_phase9e_technical_extension_closeout_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (
        tmp_path / "phase9e_technical_extension_report_inventory_check.csv"
    ).exists()
    assert (tmp_path / "phase9e_technical_extension_config_flag_check.csv").exists()
    assert (tmp_path / "phase9e_technical_extension_phase9d_failure_check.csv").exists()
    assert (tmp_path / "phase9e_technical_extension_closeout_summary.csv").exists()
    assert (tmp_path / "phase9e_technical_extension_gate_report.csv").exists()
    assert (tmp_path / "phase9e_technical_extension_conclusion.csv").exists()
    assert (tmp_path / "phase9e_technical_extension_closeout_audit.md").exists()