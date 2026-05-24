from pathlib import Path

import pandas as pd

from market_strats.analysis.final_phase10_checkpoint_audit import (
    build_phase10h_canonical_hierarchy_check,
    build_phase10h_conclusion,
    build_phase10h_config_flag_check,
    build_phase10h_gate_report,
    build_phase10h_phase10g_closeout_check,
    build_phase10h_readme_phrase_check,
    build_phase10h_report_inventory_check,
    build_phase10h_summary,
    save_phase10h_final_phase10_checkpoint_audit,
)


def _phase_config(tmp_path: Path):
    return {
        "audit_role": "Final Phase 10 checkpoint / README-config-report consistency audit",
        "phase_branch": "Phase 10 macro/rates/inflation extension",
        "checkpoint_status": "Phase 10 closed — macro branch closed without promotion",
        "next_allowed_step": "Architecture review for richer information layers",
        "readme_path": str(tmp_path / "README.md"),
        "expected_disabled_flags": {
            "phase10a_feature_family_feasibility_spec": False,
            "phase10b_macro_data_source_leakage_audit": False,
            "phase10c_macro_source_reliability_alignment_audit": False,
            "phase10d_diagnostic_macro_regime_analysis": False,
            "phase10e_preregistered_macro_hypothesis_spec": False,
            "phase10f_preregistered_macro_rule_test": False,
            "phase10g_macro_extension_closeout_audit": False,
            "relative_momentum_allocator": True,
        },
        "expected_report_prefixes": [
            "phase10a_feature_family",
            "phase10b_macro",
            "phase10c_macro",
            "phase10d_macro",
            "phase10e_macro",
            "phase10f_macro",
            "phase10g_macro",
        ],
        "expected_markdown_reports": [
            "phase10a_feature_family_feasibility_spec.md",
            "phase10b_macro_data_source_leakage_audit.md",
            "phase10c_macro_source_reliability_alignment_audit.md",
            "phase10d_diagnostic_macro_regime_analysis.md",
            "phase10e_preregistered_macro_hypothesis_spec.md",
            "phase10f_preregistered_macro_rule_test.md",
            "phase10g_macro_extension_closeout_audit.md",
        ],
        "phase10g_reports": {
            "conclusion": str(tmp_path / "phase10g_macro_closeout_conclusion.csv"),
            "gate_report": str(tmp_path / "phase10g_macro_closeout_gate_report.csv"),
            "summary": str(tmp_path / "phase10g_macro_closeout_summary.csv"),
            "phase10f_failure_check": str(
                tmp_path / "phase10g_macro_closeout_phase10f_failure_check.csv"
            ),
        },
        "required_readme_phrases": [
            "Phase 10A",
            "Phase 10B",
            "Phase 10C",
            "Phase 10D",
            "Phase 10E",
            "Phase 10F",
            "Phase 10G",
            "macro/rates/inflation",
            "closed without promotion",
            "Phase 10F failed",
            "no macro successor candidate exists",
            "final hierarchy remains unchanged",
            "SPY Buy & Hold",
            "SPY 12M Momentum",
            "deep_drawdown_guard",
            "loose_relief",
            "research-only",
        ],
        "forbidden_readme_phrases": [
            "Phase 10F passed",
            "macro rule promoted",
            "macro successor candidate was created",
            "macro strategy promoted",
            "production-ready strategy",
            "live-trading recommendation",
            "financial advice",
        ],
        "canonical_hierarchy_phrases": [
            "SPY Buy & Hold",
            "SPY 12M Momentum",
            "3D",
            "deep_drawdown_guard",
            "loose_relief",
        ],
        "gates": {
            "require_readme_required_phrases": True,
            "require_readme_forbidden_phrases_absent": True,
            "require_expected_reports_present": True,
            "require_config_flags_clean": True,
            "require_phase10g_closeout_passed": True,
            "require_phase10f_failure_locked": True,
            "require_no_successor_candidate": True,
            "require_final_candidate_unchanged": True,
            "require_canonical_hierarchy_present": True,
            "require_no_strategy_promotion": True,
            "required_audit_role": "Final Phase 10 checkpoint / README-config-report consistency audit",
        },
    }


def _runtime_config(tmp_path: Path, enabled: bool = True):
    return {
        "phase10a_feature_family_feasibility_spec": {"enabled": False},
        "phase10b_macro_data_source_leakage_audit": {"enabled": False},
        "phase10c_macro_source_reliability_alignment_audit": {"enabled": False},
        "phase10d_diagnostic_macro_regime_analysis": {"enabled": False},
        "phase10e_preregistered_macro_hypothesis_spec": {"enabled": False},
        "phase10f_preregistered_macro_rule_test": {"enabled": False},
        "phase10g_macro_extension_closeout_audit": {"enabled": False},
        "relative_momentum_allocator": {"enabled": True},
        "phase10h_final_phase10_checkpoint_audit": {
            "enabled": enabled,
            **_phase_config(tmp_path),
        },
    }


def _write_readme(tmp_path: Path):
    text = """
# Market Strats Lab

Phase 10A Phase 10B Phase 10C Phase 10D Phase 10E Phase 10F Phase 10G.

The macro/rates/inflation branch was closed without promotion.
Phase 10F failed and no macro successor candidate exists.
The final hierarchy remains unchanged.

SPY Buy & Hold remains the raw wealth benchmark.
SPY 12M Momentum remains the simple defensive benchmark.
The current final candidate uses 3D confirmation, deep_drawdown_guard, and loose_relief.

This project is research-only and not a live trading system.
"""
    (tmp_path / "README.md").write_text(text, encoding="utf-8")


def _write_report_inventory(tmp_path: Path):
    prefixes = [
        "phase10a_feature_family",
        "phase10b_macro",
        "phase10c_macro",
        "phase10d_macro",
        "phase10e_macro",
        "phase10f_macro",
        "phase10g_macro",
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
        "phase10g_macro_extension_closeout_audit.md",
    ]

    for report in markdown_reports:
        (tmp_path / report).write_text("# report\n", encoding="utf-8")


def _write_phase10g_reports(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "phase": "Phase 10G",
                "diagnostic": "Macro extension closeout / failure documentation audit",
                "verdict": "Completed — macro extension closed without promotion",
                "all_gates_passed": True,
                "interpretation": "Closed without promotion.",
            }
        ]
    ).to_csv(tmp_path / "phase10g_macro_closeout_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "gate": "Macro branch is closed without promotion",
                "passed": True,
                "all_gates_passed": True,
            },
            {
                "gate": "No successor candidate was created",
                "passed": True,
                "all_gates_passed": True,
            },
        ]
    ).to_csv(tmp_path / "phase10g_macro_closeout_gate_report.csv", index=False)

    pd.DataFrame(
        [
            {
                "branch": "Phase 10 macro/rates/inflation extension",
                "status": "Closed — no macro rule promoted",
                "next_allowed_step": "Architecture review",
                "successor_candidate_created": False,
                "final_candidate_changed": False,
                "macro_rule_promotion_allowed": False,
                "strategy_promotion": False,
            }
        ]
    ).to_csv(tmp_path / "phase10g_macro_closeout_summary.csv", index=False)

    pd.DataFrame(
        [
            {
                "check": "Phase 10F conclusion documents failure",
                "passed": True,
                "detail": "verdict=Failed / no pre-registered macro rule passed",
                "result": "Passed",
            },
            {
                "check": "Phase 10F conclusion says no rule passed",
                "passed": True,
                "detail": "any_rule_passed=False",
                "result": "Passed",
            },
            {
                "check": "Phase 10F discipline gates passed",
                "passed": True,
                "detail": "discipline_rows=12",
                "result": "Passed",
            },
        ]
    ).to_csv(
        tmp_path / "phase10g_macro_closeout_phase10f_failure_check.csv",
        index=False,
    )


def test_phase10h_gate_report_passes_valid_checkpoint(tmp_path):
    _write_readme(tmp_path)
    _write_report_inventory(tmp_path)
    _write_phase10g_reports(tmp_path)

    phase_config = _phase_config(tmp_path)
    runtime_config = _runtime_config(tmp_path, enabled=False)
    readme_text = (tmp_path / "README.md").read_text(encoding="utf-8")

    phrase_check = build_phase10h_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=phase_config["required_readme_phrases"],
        forbidden_phrases=phase_config["forbidden_readme_phrases"],
    )
    config_check = build_phase10h_config_flag_check(
        runtime_config=runtime_config,
        expected_flags=phase_config["expected_disabled_flags"],
    )
    report_check = build_phase10h_report_inventory_check(
        reports_dir=tmp_path,
        phase_config=phase_config,
    )
    closeout_check = build_phase10h_phase10g_closeout_check(
        phase_config=phase_config,
    )
    hierarchy_check = build_phase10h_canonical_hierarchy_check(
        readme_text=readme_text,
        canonical_phrases=phase_config["canonical_hierarchy_phrases"],
    )
    summary = build_phase10h_summary(
        phase_config=phase_config,
        readme_phrase_check=phrase_check,
        config_flag_check=config_check,
        report_inventory_check=report_check,
        phase10g_closeout_check=closeout_check,
        canonical_hierarchy_check=hierarchy_check,
    )
    gate_report = build_phase10h_gate_report(
        phase_config=phase_config,
        summary=summary,
    )
    conclusion = build_phase10h_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — final Phase 10 checkpoint passed"
    )


def test_phase10h_fails_if_readme_overclaims(tmp_path):
    _write_readme(tmp_path)
    readme_path = tmp_path / "README.md"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8") + "\nPhase 10F passed.\n",
        encoding="utf-8",
    )
    phase_config = _phase_config(tmp_path)

    phrase_check = build_phase10h_readme_phrase_check(
        readme_text=readme_path.read_text(encoding="utf-8"),
        required_phrases=phase_config["required_readme_phrases"],
        forbidden_phrases=phase_config["forbidden_readme_phrases"],
    )

    assert not bool(phrase_check["passed"].all())


def test_save_phase10h_writes_expected_reports(tmp_path):
    _write_readme(tmp_path)
    _write_report_inventory(tmp_path)
    _write_phase10g_reports(tmp_path)

    outputs = save_phase10h_final_phase10_checkpoint_audit(
        config=_runtime_config(tmp_path, enabled=True),
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10h_final_checkpoint_readme_phrase_check.csv").exists()
    assert (tmp_path / "phase10h_final_checkpoint_config_flag_check.csv").exists()
    assert (tmp_path / "phase10h_final_checkpoint_report_inventory_check.csv").exists()
    assert (tmp_path / "phase10h_final_checkpoint_phase10g_closeout_check.csv").exists()
    assert (
        tmp_path / "phase10h_final_checkpoint_canonical_hierarchy_check.csv"
    ).exists()
    assert (tmp_path / "phase10h_final_checkpoint_summary.csv").exists()
    assert (tmp_path / "phase10h_final_checkpoint_gate_report.csv").exists()
    assert (tmp_path / "phase10h_final_checkpoint_conclusion.csv").exists()
    assert (tmp_path / "phase10h_final_phase10_checkpoint_audit.md").exists()