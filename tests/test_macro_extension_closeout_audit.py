from pathlib import Path

import pandas as pd

from market_strats.analysis.macro_extension_closeout_audit import (
    build_phase10g_conclusion,
    build_phase10g_config_flag_check,
    build_phase10g_gate_report,
    build_phase10g_phase10f_failure_check,
    build_phase10g_report_inventory_check,
    build_phase10g_closeout_summary,
    save_phase10g_macro_extension_closeout_audit,
)


def _runtime_config(enabled=False):
    return {
        "phase10a_feature_family_feasibility_spec": {"enabled": False},
        "phase10b_macro_data_source_leakage_audit": {"enabled": False},
        "phase10c_macro_source_reliability_alignment_audit": {"enabled": False},
        "phase10d_diagnostic_macro_regime_analysis": {"enabled": False},
        "phase10e_preregistered_macro_hypothesis_spec": {"enabled": False},
        "phase10f_preregistered_macro_rule_test": {"enabled": False},
        "relative_momentum_allocator": {"enabled": True},
        "phase10g_macro_extension_closeout_audit": {
            "enabled": enabled,
            **_phase_config_base(),
        },
    }


def _phase_config_base():
    return {
        "audit_role": "Macro extension closeout / failure documentation audit",
        "branch": "Phase 10 macro/rates/inflation extension",
        "status": "Closed — no macro rule promoted",
        "next_allowed_step": "Phase 10H final Phase 10 checkpoint audit or architecture review",
        "successor_candidate_created": False,
        "final_candidate_changed": False,
        "macro_rule_promotion_allowed": False,
        "strategy_promotion": False,
        "expected_disabled_flags": {
            "phase10a_feature_family_feasibility_spec": False,
            "phase10b_macro_data_source_leakage_audit": False,
            "phase10c_macro_source_reliability_alignment_audit": False,
            "phase10d_diagnostic_macro_regime_analysis": False,
            "phase10e_preregistered_macro_hypothesis_spec": False,
            "phase10f_preregistered_macro_rule_test": False,
            "relative_momentum_allocator": True,
        },
        "expected_report_prefixes": [
            "phase10a_feature_family",
            "phase10b_macro",
            "phase10c_macro",
            "phase10d_macro",
            "phase10e_macro",
            "phase10f_macro",
        ],
        "expected_markdown_reports": [
            "phase10a_feature_family_feasibility_spec.md",
            "phase10b_macro_data_source_leakage_audit.md",
            "phase10c_macro_source_reliability_alignment_audit.md",
            "phase10d_diagnostic_macro_regime_analysis.md",
            "phase10e_preregistered_macro_hypothesis_spec.md",
            "phase10f_preregistered_macro_rule_test.md",
        ],
        "required_phase10f_verdict": "Failed / no pre-registered macro rule passed",
        "gates": {
            "require_expected_reports_present": True,
            "require_config_flags_clean": True,
            "require_phase10f_failure_documented": True,
            "require_no_phase10f_rule_passed": True,
            "require_phase10f_discipline_passed": True,
            "require_no_strategy_promotion": True,
            "require_no_successor_candidate": True,
            "require_final_candidate_unchanged": True,
            "require_branch_closed_without_promotion": True,
            "required_audit_role": "Macro extension closeout / failure documentation audit",
        },
    }


def _write_phase10f_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 10F",
                "diagnostic": "Pre-registered macro-rule test",
                "verdict": "Failed / no pre-registered macro rule passed",
                "discipline_gates_passed": True,
                "any_rule_passed": False,
                "passed_rules": "",
                "strategy_promotion": False,
                "interpretation": "No pre-registered macro rule passed.",
            }
        ]
    ).to_csv(tmp_path / "phase10f_macro_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "rule_id": "H1",
                "gate": "example",
                "passed": False,
                "all_rule_gates_passed": False,
            },
            {
                "rule_id": "H2",
                "gate": "example",
                "passed": False,
                "all_rule_gates_passed": False,
            },
        ]
    ).to_csv(tmp_path / "phase10f_macro_rule_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "rule_id": "H1",
                "all_rule_gates_passed": False,
                "strategy_promotion": False,
            },
            {
                "rule_id": "H2",
                "all_rule_gates_passed": False,
                "strategy_promotion": False,
            },
        ]
    ).to_csv(tmp_path / "phase10f_macro_rule_comparison_summary.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "Exact pre-registered rule IDs are used",
                "passed": True,
                "all_discipline_gates_passed": True,
            },
            {
                "gate": "No strategy promotion is allowed",
                "passed": True,
                "all_discipline_gates_passed": True,
            },
        ]
    ).to_csv(tmp_path / "phase10f_macro_discipline_gate_report.csv", index=False)


def _write_report_inventory(tmp_path: Path):
    prefixes = [
        "phase10a_feature_family",
        "phase10b_macro",
        "phase10c_macro",
        "phase10d_macro",
        "phase10e_macro",
        "phase10f_macro",
    ]
    for prefix in prefixes:
        (tmp_path / f"{prefix}_dummy.csv").write_text("x\n1\n", encoding="utf-8")

    markdown_reports = [
        "phase10a_feature_family_feasibility_spec.md",
        "phase10b_macro_data_source_leakage_audit.md",
        "phase10c_macro_source_reliability_alignment_audit.md",
        "phase10d_diagnostic_macro_regime_analysis.md",
        "phase10e_preregistered_macro_hypothesis_spec.md",
        "phase10f_preregistered_macro_rule_test.md",
    ]
    for report in markdown_reports:
        (tmp_path / report).write_text("# report\n", encoding="utf-8")


def _phase_config(tmp_path: Path):
    config = _phase_config_base()
    config["phase10f_reports"] = {
        "conclusion": str(tmp_path / "phase10f_macro_conclusion.csv"),
        "rule_gate_report": str(tmp_path / "phase10f_macro_rule_gate_report.csv"),
        "rule_comparison_summary": str(
            tmp_path / "phase10f_macro_rule_comparison_summary.csv"
        ),
        "discipline_gate_report": str(
            tmp_path / "phase10f_macro_discipline_gate_report.csv"
        ),
    }
    return config


def test_phase10g_gate_report_passes_valid_closeout(tmp_path):
    _write_report_inventory(tmp_path)
    _write_phase10f_reports(tmp_path)
    phase_config = _phase_config(tmp_path)
    runtime_config = _runtime_config(enabled=False)
    runtime_config["phase10g_macro_extension_closeout_audit"].update(phase_config)

    inventory = build_phase10g_report_inventory_check(
        reports_dir=tmp_path,
        phase_config=phase_config,
    )
    config_check = build_phase10g_config_flag_check(
        runtime_config=runtime_config,
        expected_flags=phase_config["expected_disabled_flags"],
    )
    failure_check = build_phase10g_phase10f_failure_check(
        phase_config=phase_config,
    )
    closeout = build_phase10g_closeout_summary(phase_config)
    gate_report = build_phase10g_gate_report(
        phase_config=phase_config,
        report_inventory_check=inventory,
        config_flag_check=config_check,
        phase10f_failure_check=failure_check,
        closeout_summary=closeout,
    )
    conclusion = build_phase10g_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — macro extension closed without promotion"
    )


def test_phase10g_fails_if_phase10f_rule_passed(tmp_path):
    _write_report_inventory(tmp_path)
    _write_phase10f_reports(tmp_path)
    pd.DataFrame(
        [
            {
                "phase": "Phase 10F",
                "diagnostic": "Pre-registered macro-rule test",
                "verdict": "Passed for further validation only",
                "discipline_gates_passed": True,
                "any_rule_passed": True,
                "passed_rules": "H2",
                "strategy_promotion": False,
                "interpretation": "A rule passed.",
            }
        ]
    ).to_csv(tmp_path / "phase10f_macro_conclusion.csv", index=False)

    phase_config = _phase_config(tmp_path)
    failure_check = build_phase10g_phase10f_failure_check(
        phase_config=phase_config,
    )

    assert not bool(failure_check["passed"].all())


def test_save_phase10g_writes_expected_reports(tmp_path):
    _write_report_inventory(tmp_path)
    _write_phase10f_reports(tmp_path)

    runtime_config = _runtime_config(enabled=True)
    runtime_config["phase10g_macro_extension_closeout_audit"].update(
        _phase_config(tmp_path)
    )

    outputs = save_phase10g_macro_extension_closeout_audit(
        config=runtime_config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10g_macro_closeout_report_inventory_check.csv").exists()
    assert (tmp_path / "phase10g_macro_closeout_config_flag_check.csv").exists()
    assert (tmp_path / "phase10g_macro_closeout_phase10f_failure_check.csv").exists()
    assert (tmp_path / "phase10g_macro_closeout_summary.csv").exists()
    assert (tmp_path / "phase10g_macro_closeout_gate_report.csv").exists()
    assert (tmp_path / "phase10g_macro_closeout_conclusion.csv").exists()
    assert (tmp_path / "phase10g_macro_extension_closeout_audit.md").exists()