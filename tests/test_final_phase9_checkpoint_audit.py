from pathlib import Path

import pandas as pd
import yaml

from market_strats.analysis.final_phase9_checkpoint_audit import (
    build_phase9f_canonical_check,
    build_phase9f_closeout_check,
    build_phase9f_conclusion,
    build_phase9f_config_flag_check,
    build_phase9f_gate_report,
    build_phase9f_readme_phrase_check,
    build_phase9f_report_inventory_check,
    build_phase9f_summary,
    save_phase9f_final_phase9_checkpoint_audit,
)


def _readme_text() -> str:
    return (
        "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief. "
        "SPY Buy & Hold remains the raw wealth benchmark. "
        "SPY 12M Momentum remains the simple defensive timing benchmark. "
        "2006-04-28. 2026-05-01. "
        "mixed rolling-window liveability. meaningful spread/impact sensitivity. "
        "mixed walk-forward evidence. material behavioural-regret risk. "
        "research-degrees-of-freedom caveat. research-only/non-production boundary. "
        "diagnostic-only Phase 9A technical-regime evidence. "
        "diagnostic-only Phase 9B cluster-stability evidence. "
        "Phase 9C pre-registered technical-rule design spec. "
        "failed Phase 9D pre-registered technical-rule test. "
        "Phase 9E technical-extension closeout with no rule promotion. "
        "No technical rule was promoted. No successor candidate. "
        "The final candidate hierarchy is unchanged. "
        "research-only. not production-ready. not live-tradable. not financial advice."
    )


def _phase_config(readme_path: Path, config_path: Path) -> dict:
    return {
        "readme_path": str(readme_path),
        "config_path": str(config_path),
        "canonical": {
            "final_candidate": "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief",
            "raw_wealth_benchmark": "SPY Buy & Hold",
            "simple_defensive_benchmark": "SPY 12M Momentum",
            "canonical_start_date": "2006-04-28",
            "canonical_end_date": "2026-05-01",
        },
        "required_readme_phrases": [
            "Phase 9A",
            "Phase 9B",
            "Phase 9C",
            "Phase 9D",
            "Phase 9E",
            "No technical rule was promoted",
            "No successor candidate",
            "The final candidate hierarchy is unchanged",
            "not production-ready",
        ],
        "forbidden_readme_phrases": [
            "Phase 9D passed for further validation",
            "RSI rule validated",
        ],
        "expected_disabled_flags": {
            "phase9a_technical_indicator_expansion_diagnostic": False,
            "phase9b_technical_regime_cluster_stability_audit": False,
            "phase9c_preregistered_technical_rule_design_spec": False,
            "phase9d_preregistered_technical_rule_test": False,
            "phase9e_technical_extension_closeout_audit": False,
            "phase9f_final_phase9_checkpoint_audit": True,
            "relative_momentum_allocator": True,
        },
        "expected_report_prefixes": [
            "phase9a_technical",
            "phase9b_technical",
            "phase9c_preregistered",
            "phase9d_preregistered",
            "phase9e_technical",
        ],
    }


def _write_reports(tmp_path: Path) -> None:
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
            }
        ]
    ).to_csv(tmp_path / "phase9d_preregistered_rule_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "phase": "Phase 9E",
                "diagnostic": "Technical extension closeout",
                "verdict": "Completed — technical extension closed without promotion",
            }
        ]
    ).to_csv(tmp_path / "phase9e_technical_extension_conclusion.csv", index=False)

    pd.DataFrame(
        [
            {
                "successor_candidate_created": False,
                "rule_promotion_allowed": False,
                "final_candidate_changed": False,
            }
        ]
    ).to_csv(
        tmp_path / "phase9e_technical_extension_closeout_summary.csv",
        index=False,
    )


def _persisted_config() -> dict:
    return {
        "phase9a_technical_indicator_expansion_diagnostic": {"enabled": False},
        "phase9b_technical_regime_cluster_stability_audit": {"enabled": False},
        "phase9c_preregistered_technical_rule_design_spec": {"enabled": False},
        "phase9d_preregistered_technical_rule_test": {"enabled": False},
        "phase9e_technical_extension_closeout_audit": {"enabled": False},
        "phase9f_final_phase9_checkpoint_audit": {"enabled": True},
        "relative_momentum_allocator": {"enabled": True},
    }


def test_phase9f_checks_pass_when_readme_config_reports_are_consistent(tmp_path):
    readme_text = _readme_text()
    readme_path = tmp_path / "README.md"
    config_path = tmp_path / "spy_sma10.yaml"
    readme_path.write_text(readme_text, encoding="utf-8")
    config_path.write_text(yaml.safe_dump(_persisted_config()), encoding="utf-8")
    _write_reports(tmp_path)

    phase_config = _phase_config(readme_path, config_path)

    phrase_check = build_phase9f_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=phase_config["required_readme_phrases"],
        forbidden_phrases=phase_config["forbidden_readme_phrases"],
    )
    config_check = build_phase9f_config_flag_check(
        runtime_config=_persisted_config(),
        expected_flags=phase_config["expected_disabled_flags"],
    )
    report_check = build_phase9f_report_inventory_check(
        reports_dir=tmp_path,
        expected_report_prefixes=phase_config["expected_report_prefixes"],
    )
    canonical_check = build_phase9f_canonical_check(
        readme_text=readme_text,
        phase_config=phase_config,
    )
    closeout_check = build_phase9f_closeout_check(
        reports_dir=tmp_path,
        readme_text=readme_text,
        phase_config=phase_config,
    )
    summary = build_phase9f_summary(
        readme_phrase_check=phrase_check,
        config_flag_check=config_check,
        report_inventory_check=report_check,
        canonical_check=canonical_check,
        closeout_check=closeout_check,
    )
    gate_report = build_phase9f_gate_report(
        readme_phrase_check=phrase_check,
        config_flag_check=config_check,
        report_inventory_check=report_check,
        canonical_check=canonical_check,
        closeout_check=closeout_check,
        summary=summary,
        phase_config=phase_config,
    )
    conclusion = build_phase9f_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == "Completed — Phase 9 checkpoint consistent"


def test_phase9f_forbidden_phrase_fails_gate():
    phrase_check = build_phase9f_readme_phrase_check(
        readme_text="Phase 9D passed for further validation",
        required_phrases=[],
        forbidden_phrases=["Phase 9D passed for further validation"],
    )

    forbidden_rows = phrase_check[phrase_check["check_type"] == "forbidden_phrase"]

    assert not bool(forbidden_rows["passed"].all())


def test_save_phase9f_writes_expected_reports(tmp_path):
    readme_path = tmp_path / "README.md"
    config_path = tmp_path / "spy_sma10.yaml"
    readme_path.write_text(_readme_text(), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(_persisted_config()), encoding="utf-8")
    _write_reports(tmp_path)

    config = {
        "phase9f_final_phase9_checkpoint_audit": {
            "enabled": True,
            **_phase_config(readme_path, config_path),
        }
    }

    outputs = save_phase9f_final_phase9_checkpoint_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase9f_final_checkpoint_readme_phrase_check.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_config_flag_check.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_report_inventory_check.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_canonical_check.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_closeout_check.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_summary.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_gate_report.csv").exists()
    assert (tmp_path / "phase9f_final_checkpoint_conclusion.csv").exists()
    assert (tmp_path / "phase9f_final_phase9_checkpoint_audit.md").exists()