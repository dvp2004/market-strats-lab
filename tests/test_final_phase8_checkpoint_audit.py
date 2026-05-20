import yaml

from market_strats.analysis.final_phase8_checkpoint_audit import (
    build_phase8g_canonical_check,
    build_phase8g_config_flag_check,
    build_phase8g_conclusion,
    build_phase8g_gate_report,
    build_phase8g_readme_phrase_check,
    build_phase8g_report_inventory_check,
    save_phase8g_final_phase8_checkpoint_audit,
)


def test_phase8g_readme_phrase_check_detects_required_and_forbidden_phrases():
    readme_text = (
        "SPY Buy & Hold remains the raw wealth benchmark. "
        "The final candidate is not production-ready."
    )

    result = build_phase8g_readme_phrase_check(
        readme_text=readme_text,
        required_phrases=["raw wealth benchmark", "not production-ready"],
        forbidden_phrases=["Phase 8F production-readiness passed"],
    )

    assert bool(result["passed"].all())


def test_phase8g_config_flag_check_detects_expected_flags():
    runtime_config = {
        "phase8a_tax_drag_diagnostic": {"enabled": False},
        "relative_momentum_allocator": {"enabled": True},
    }

    result = build_phase8g_config_flag_check(
        runtime_config=runtime_config,
        expected_flags={
            "phase8a_tax_drag_diagnostic": False,
            "relative_momentum_allocator": True,
        },
    )

    assert bool(result["passed"].all())


def test_phase8g_report_inventory_check_detects_prefixes(tmp_path):
    (tmp_path / "phase8a_tax_drag_summary.csv").write_text("x", encoding="utf-8")
    (tmp_path / "phase8b_bid_ask_market_impact_summary.csv").write_text(
        "x",
        encoding="utf-8",
    )

    result = build_phase8g_report_inventory_check(
        reports_dir=tmp_path,
        expected_report_prefixes=[
            "phase8a_tax_drag",
            "phase8b_bid_ask_market_impact",
        ],
    )

    assert bool(result["passed"].all())


def test_phase8g_canonical_check_requires_full_caveat_stack():
    readme_text = (
        "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief. "
        "SPY Buy & Hold. SPY 12M Momentum. 2006-04-28. 2026-05-01. "
        "mixed rolling-window liveability. meaningful spread/impact sensitivity. "
        "mixed walk-forward evidence. material behavioural-regret risk. "
        "research-degrees-of-freedom caveat. research-only."
    )
    phase_config = {
        "canonical": {
            "final_candidate": "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief",
            "raw_wealth_benchmark": "SPY Buy & Hold",
            "simple_defensive_benchmark": "SPY 12M Momentum",
            "canonical_start_date": "2006-04-28",
            "canonical_end_date": "2026-05-01",
        }
    }

    result = build_phase8g_canonical_check(
        readme_text=readme_text,
        phase_config=phase_config,
    )

    assert bool(result["passed"].all())


def test_phase8g_gate_report_passes_when_all_checks_pass(tmp_path):
    readme_check = build_phase8g_readme_phrase_check(
        readme_text="required phrase only",
        required_phrases=["required phrase"],
        forbidden_phrases=["bad phrase"],
    )
    config_check = build_phase8g_config_flag_check(
        runtime_config={"phase8g_final_phase8_checkpoint_audit": {"enabled": True}},
        expected_flags={"phase8g_final_phase8_checkpoint_audit": True},
    )
    (tmp_path / "phase8a_tax_drag_summary.csv").write_text("x", encoding="utf-8")
    report_check = build_phase8g_report_inventory_check(
        reports_dir=tmp_path,
        expected_report_prefixes=["phase8a_tax_drag"],
    )
    canonical_check = build_phase8g_canonical_check(
        readme_text=(
            "candidate. SPY Buy & Hold. SPY 12M Momentum. 2006-04-28. "
            "2026-05-01. mixed rolling-window liveability. "
            "meaningful spread/impact sensitivity. mixed walk-forward evidence. "
            "material behavioural-regret risk. research-degrees-of-freedom caveat. "
            "research-only."
        ),
        phase_config={
            "canonical": {
                "final_candidate": "candidate",
                "raw_wealth_benchmark": "SPY Buy & Hold",
                "simple_defensive_benchmark": "SPY 12M Momentum",
                "canonical_start_date": "2006-04-28",
                "canonical_end_date": "2026-05-01",
            }
        },
    )

    gate_report = build_phase8g_gate_report(
        readme_phrase_check=readme_check,
        config_flag_check=config_check,
        report_inventory_check=report_check,
        canonical_check=canonical_check,
        phase_config={},
    )
    conclusion = build_phase8g_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — Phase 8 checkpoint consistent"
    )


def test_save_phase8g_writes_expected_reports(tmp_path, monkeypatch):
    readme_text = (
        "SPY Buy & Hold remains the raw wealth benchmark. SPY 12M Momentum. "
        "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief. "
        "best execution-realistic risk-adjusted candidate built so far. "
        "mixed rolling-window liveability. meaningful spread/impact sensitivity. "
        "mixed walk-forward evidence. material behavioural-regret risk. "
        "research-degrees-of-freedom caveat. research-only. not production-ready. "
        "not live-tradable. not financial advice. 2006-04-28. 2026-05-01."
    )

    readme_path = tmp_path / "README.md"
    config_path = tmp_path / "spy_sma10.yaml"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    readme_path.write_text(readme_text, encoding="utf-8")

    persisted_config = {
        "phase8a_tax_drag_diagnostic": {"enabled": False},
        "phase8g_final_phase8_checkpoint_audit": {"enabled": True},
        "relative_momentum_allocator": {"enabled": True},
    }
    config_path.write_text(yaml.safe_dump(persisted_config), encoding="utf-8")
    (reports_dir / "phase8a_tax_drag_summary.csv").write_text("x", encoding="utf-8")

    config = {
        "phase8g_final_phase8_checkpoint_audit": {
            "enabled": True,
            "readme_path": str(readme_path),
            "config_path": str(config_path),
            "required_readme_phrases": [
                "SPY Buy & Hold remains the raw wealth benchmark",
                "not production-ready",
            ],
            "forbidden_readme_phrases": [
                "Phase 8F production-readiness passed",
            ],
            "expected_disabled_flags": {
                "phase8a_tax_drag_diagnostic": False,
                "phase8g_final_phase8_checkpoint_audit": True,
                "relative_momentum_allocator": True,
            },
            "expected_report_prefixes": ["phase8a_tax_drag"],
        }
    }

    outputs = save_phase8g_final_phase8_checkpoint_audit(
        config=config,
        reports_dir=reports_dir,
    )

    assert not outputs["gate_report"].empty
    assert (reports_dir / "phase8g_final_checkpoint_readme_phrase_check.csv").exists()
    assert (reports_dir / "phase8g_final_checkpoint_config_flag_check.csv").exists()
    assert (
        reports_dir / "phase8g_final_checkpoint_report_inventory_check.csv"
    ).exists()
    assert (reports_dir / "phase8g_final_checkpoint_canonical_check.csv").exists()
    assert (reports_dir / "phase8g_final_checkpoint_gate_report.csv").exists()
    assert (reports_dir / "phase8g_final_checkpoint_conclusion.csv").exists()
    assert (reports_dir / "phase8g_final_phase8_checkpoint_audit.md").exists()