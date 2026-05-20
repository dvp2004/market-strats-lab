from market_strats.analysis.production_readiness_boundary_audit import (
    build_phase8f_blocker_inventory,
    build_phase8f_boundary_statement,
    build_phase8f_category_summary,
    build_phase8f_conclusion,
    build_phase8f_gate_report,
    build_phase8f_summary,
    save_phase8f_production_readiness_boundary_audit,
)


def _sample_phase_config():
    return {
        "claim_context": {
            "project_scope": "Research-grade systematic strategy lab",
            "production_ready": False,
            "live_trading_claim": False,
            "final_candidate": "SPY 3D + guards",
            "final_candidate_role": "Best execution-realistic risk-adjusted candidate built so far",
            "raw_wealth_benchmark": "SPY Buy & Hold",
            "simple_defensive_benchmark": "SPY 12M Momentum",
            "canonical_start_date": "2006-04-28",
            "canonical_end_date": "2026-05-01",
        },
        "gates": {
            "require_not_production_ready": True,
            "require_no_live_trading_claim": True,
            "min_critical_blockers": 4,
            "require_data_risk_documented": True,
            "require_execution_risk_documented": True,
            "require_tax_risk_documented": True,
            "require_operational_risk_documented": True,
            "require_monitoring_risk_documented": True,
            "require_human_review_required": True,
        },
        "blockers": [
            {
                "category": "Data",
                "area": "Primary data dependency",
                "severity": "Critical",
                "status": "Blocker",
                "production_gap": "Research data dependency.",
                "current_project_state": "Cached adjusted-close data.",
                "required_for_production": "Production data source.",
                "recommended_next_step": "Keep research-only.",
            },
            {
                "category": "Execution",
                "area": "Order fills",
                "severity": "Critical",
                "status": "Blocker",
                "production_gap": "No fill model.",
                "current_project_state": "Scenario slippage only.",
                "required_for_production": "Broker execution model.",
                "recommended_next_step": "Do not trade.",
            },
            {
                "category": "Tax",
                "area": "Tax lots",
                "severity": "Critical",
                "status": "Blocker",
                "production_gap": "No tax-lot engine.",
                "current_project_state": "Simplified tax proxy.",
                "required_for_production": "Tax accounting engine.",
                "recommended_next_step": "Keep diagnostic only.",
            },
            {
                "category": "Monitoring",
                "area": "Live monitoring",
                "severity": "Critical",
                "status": "Blocker",
                "production_gap": "No alerts.",
                "current_project_state": "Research reports only.",
                "required_for_production": "Monitoring and reconciliation.",
                "recommended_next_step": "No production use.",
            },
            {
                "category": "Operations",
                "area": "Configuration drift",
                "severity": "Major",
                "status": "Gap",
                "production_gap": "Manual config controls.",
                "current_project_state": "Checkpoint checks.",
                "required_for_production": "Deployment controls.",
                "recommended_next_step": "Improve manifests.",
            },
            {
                "category": "Governance",
                "area": "Human review",
                "severity": "Critical",
                "status": "Blocker",
                "production_gap": "No sign-off process.",
                "current_project_state": "Research commits only.",
                "required_for_production": "Governance approval.",
                "recommended_next_step": "Human review required.",
            },
        ],
    }


def test_phase8f_inventory_summary_and_boundary_statement_are_created():
    phase_config = _sample_phase_config()

    inventory = build_phase8f_blocker_inventory(phase_config)
    category_summary = build_phase8f_category_summary(inventory)
    summary = build_phase8f_summary(inventory, phase_config)
    boundary_statement = build_phase8f_boundary_statement(summary, inventory)

    assert not inventory.empty
    assert not category_summary.empty
    assert not summary.empty
    assert not boundary_statement.empty
    assert not bool(summary.iloc[0]["production_ready_after_audit"])
    assert "research-grade" in boundary_statement.iloc[0]["recommended_statement"]


def test_phase8f_gate_report_passes_when_boundary_is_documented():
    phase_config = _sample_phase_config()
    inventory = build_phase8f_blocker_inventory(phase_config)
    summary = build_phase8f_summary(inventory, phase_config)
    boundary_statement = build_phase8f_boundary_statement(summary, inventory)
    gate_report = build_phase8f_gate_report(
        inventory,
        summary,
        boundary_statement,
        phase_config,
    )
    conclusion = build_phase8f_conclusion(gate_report, summary)

    assert not gate_report.empty
    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — research-only boundary documented"
    )


def test_phase8f_gate_report_fails_when_live_trading_claim_is_true():
    phase_config = _sample_phase_config()
    phase_config["claim_context"]["live_trading_claim"] = True

    inventory = build_phase8f_blocker_inventory(phase_config)
    summary = build_phase8f_summary(inventory, phase_config)
    boundary_statement = build_phase8f_boundary_statement(summary, inventory)
    gate_report = build_phase8f_gate_report(
        inventory,
        summary,
        boundary_statement,
        phase_config,
    )

    assert not bool(gate_report["passed"].all())


def test_phase8f_empty_inventory_fails_boundary_discipline():
    phase_config = _sample_phase_config()
    phase_config["blockers"] = []

    inventory = build_phase8f_blocker_inventory(phase_config)
    summary = build_phase8f_summary(inventory, phase_config)
    boundary_statement = build_phase8f_boundary_statement(summary, inventory)
    gate_report = build_phase8f_gate_report(
        inventory,
        summary,
        boundary_statement,
        phase_config,
    )

    assert inventory.empty
    assert not bool(gate_report["passed"].all())


def test_save_phase8f_writes_expected_reports(tmp_path):
    config = {
        "phase8f_production_readiness_boundary_audit": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase8f_production_readiness_boundary_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["blocker_inventory"].empty
    assert (tmp_path / "phase8f_production_boundary_blocker_inventory.csv").exists()
    assert (tmp_path / "phase8f_production_boundary_category_summary.csv").exists()
    assert (tmp_path / "phase8f_production_boundary_summary.csv").exists()
    assert (tmp_path / "phase8f_production_boundary_statement.csv").exists()
    assert (tmp_path / "phase8f_production_boundary_gate_report.csv").exists()
    assert (tmp_path / "phase8f_production_boundary_conclusion.csv").exists()
    assert (tmp_path / "phase8f_production_readiness_boundary_audit.md").exists()