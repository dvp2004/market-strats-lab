import pandas as pd

from market_strats.analysis.research_degrees_of_freedom_audit import (
    build_phase8e_claim_adjustment,
    build_phase8e_conclusion,
    build_phase8e_gate_report,
    build_phase8e_inventory,
    build_phase8e_summary,
    save_phase8e_research_degrees_of_freedom_audit,
)


def _sample_phase_config():
    return {
        "claim_context": {
            "final_candidate": "SPY 3D + guards",
            "final_candidate_role": "Best execution-realistic risk-adjusted candidate built so far",
            "raw_wealth_benchmark": "SPY Buy & Hold",
            "simple_defensive_benchmark": "SPY 12M Momentum",
            "canonical_start_date": "2006-04-28",
            "canonical_end_date": "2026-05-01",
        },
        "gates": {
            "require_failed_branches_documented": True,
            "require_multiple_comparisons_caveat": True,
            "require_raw_wealth_hierarchy_preserved": True,
            "require_final_claim_narrowed": True,
            "max_promoted_share_of_tested_units": 0.50,
            "min_failed_or_rejected_units": 2,
        },
        "inventory": [
            {
                "phase": "Phase 1",
                "branch": "Single-asset strategy tests",
                "tested_units": 10,
                "promoted_units": 2,
                "failed_or_rejected_units": 6,
                "mixed_or_caveated_units": 2,
                "status": "Mixed",
                "notes": "Several failed branches documented.",
            },
            {
                "phase": "Phase 8",
                "branch": "Real-world friction diagnostics",
                "tested_units": 4,
                "promoted_units": 0,
                "failed_or_rejected_units": 3,
                "mixed_or_caveated_units": 1,
                "status": "Mostly failed",
                "notes": "Friction/liveability caveats documented.",
            },
        ],
    }


def test_phase8e_inventory_summary_and_claim_adjustment_are_created():
    phase_config = _sample_phase_config()

    inventory = build_phase8e_inventory(phase_config)
    summary = build_phase8e_summary(inventory, phase_config)
    claim_adjustment = build_phase8e_claim_adjustment(summary, inventory)

    assert not inventory.empty
    assert not summary.empty
    assert not claim_adjustment.empty
    assert int(summary.iloc[0]["total_tested_units"]) == 14
    assert int(summary.iloc[0]["total_failed_or_rejected_units"]) == 9
    assert "narrow" in claim_adjustment.iloc[0]["recommended_wording"].lower()


def test_phase8e_gate_report_passes_for_documented_inventory():
    phase_config = _sample_phase_config()
    inventory = build_phase8e_inventory(phase_config)
    summary = build_phase8e_summary(inventory, phase_config)
    claim_adjustment = build_phase8e_claim_adjustment(summary, inventory)
    gate_report = build_phase8e_gate_report(
        inventory,
        summary,
        claim_adjustment,
        phase_config,
    )
    conclusion = build_phase8e_conclusion(gate_report, summary)

    assert not gate_report.empty
    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == "Completed — claims narrowed"


def test_phase8e_gate_report_fails_when_inventory_is_missing():
    phase_config = _sample_phase_config()
    phase_config["inventory"] = []

    inventory = build_phase8e_inventory(phase_config)
    summary = build_phase8e_summary(inventory, phase_config)
    claim_adjustment = build_phase8e_claim_adjustment(summary, inventory)
    gate_report = build_phase8e_gate_report(
        inventory,
        summary,
        claim_adjustment,
        phase_config,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase8e_writes_expected_reports(tmp_path):
    config = {
        "phase8e_research_degrees_of_freedom_audit": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase8e_research_degrees_of_freedom_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["inventory"].empty
    assert (tmp_path / "phase8e_research_degrees_of_freedom_inventory.csv").exists()
    assert (tmp_path / "phase8e_research_degrees_of_freedom_summary.csv").exists()
    assert (
        tmp_path / "phase8e_research_degrees_of_freedom_claim_adjustment.csv"
    ).exists()
    assert (
        tmp_path / "phase8e_research_degrees_of_freedom_gate_report.csv"
    ).exists()
    assert (
        tmp_path / "phase8e_research_degrees_of_freedom_conclusion.csv"
    ).exists()
    assert (tmp_path / "phase8e_research_degrees_of_freedom_audit.md").exists()


def test_phase8e_summary_handles_empty_inventory():
    phase_config = _sample_phase_config()
    phase_config["inventory"] = []

    inventory = build_phase8e_inventory(phase_config)
    summary = build_phase8e_summary(inventory, phase_config)

    assert isinstance(summary, pd.DataFrame)
    assert int(summary.iloc[0]["total_tested_units"]) == 0
    assert summary.iloc[0]["claim_strength_after_audit"] == "Invalid — no inventory supplied"