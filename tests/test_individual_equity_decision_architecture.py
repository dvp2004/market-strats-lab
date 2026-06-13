from pathlib import Path

from market_strats.analysis.individual_equity_decision_architecture import (
    build_autonomous_decision_schema,
    build_feature_family_registry,
    build_point_in_time_universe_contract,
    build_research_roadmap,
    save_phase23a_individual_equity_decision_architecture,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase23a_individual_equity_decision_architecture": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "individual_equity"),
            "dashboard_status_path": str(
                tmp_path / "reports" / "paper_trading" / "dashboard" / "phase23a_status.csv"
            ),
        }
    }


def test_point_in_time_universe_contract_blocks_survivorship_shortcuts():
    contract = build_point_in_time_universe_contract()
    assert len(contract) >= 6
    assert contract["required"].all()
    assert "current_constituents_backfilled_through_history" in set(
        contract["blocked_shortcut"]
    )
    assert "survivors_only_price_panel" in set(contract["blocked_shortcut"])


def test_feature_registry_contains_required_signal_families():
    registry = build_feature_family_registry()
    required = {
        "technical",
        "fundamental",
        "sentiment",
        "macro",
        "cross_asset",
        "market_stress",
    }
    assert required.issubset(set(registry["family"]))
    assert registry["point_in_time_rule"].str.len().gt(0).all()


def test_autonomous_decision_schema_contains_model_portfolio_and_safety_fields():
    schema = build_autonomous_decision_schema()
    columns = set(schema["column"])
    assert {
        "predicted_excess_return_20d",
        "positive_alpha_probability_20d",
        "cross_sectional_rank",
        "approved_target_weight",
        "trade_action",
        "blocking_reasons",
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
    }.issubset(columns)


def test_roadmap_requires_universe_audit_before_model_training():
    roadmap = build_research_roadmap()
    next_row = roadmap.loc[roadmap["status"] == "next"].iloc[0]
    assert next_row["phase"] == "23B"
    assert "point-in-time" in next_row["objective"].lower()
    assert roadmap.loc[roadmap["phase"] == "23G", "status"].iloc[0] == "planned"


def test_phase23a_writes_reports_and_enforces_research_only_boundary(tmp_path):
    outputs = save_phase23a_individual_equity_decision_architecture(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    assert bool(outputs["summary"].iloc[0]["all_gates_passed"])
    assert outputs["summary"].iloc[0]["next_phase"].startswith("Phase 23B")
    assert outputs["scope_boundary"]["passed"].all()
    assert not bool(outputs["summary"].iloc[0]["promotion_allowed"])
    assert not bool(outputs["summary"].iloc[0]["live_trading_allowed"])
    assert not bool(outputs["summary"].iloc[0]["real_money_allowed"])
    assert not bool(outputs["summary"].iloc[0]["broker_api_integration_allowed"])

    output_dir = tmp_path / "reports" / "individual_equity"
    required_files = [
        "phase23a_summary.csv",
        "phase23a_gate_report.csv",
        "phase23a_point_in_time_universe_contract.csv",
        "phase23a_feature_family_registry.csv",
        "phase23a_autonomous_decision_schema.csv",
        "phase23a_research_roadmap.csv",
        "phase23a_individual_equity_decision_architecture.md",
    ]
    for filename in required_files:
        assert (output_dir / filename).exists()

    dashboard = (
        tmp_path
        / "reports"
        / "paper_trading"
        / "dashboard"
        / "phase23a_status.csv"
    )
    assert dashboard.exists()


def test_run_backtest_exposes_phase23a_only_cli():
    source = Path("src/market_strats/run_backtest.py").read_text(encoding="utf-8")
    assert "--phase23a-only" in source
    assert "_run_phase23a_individual_equity_decision_architecture(" in source
    assert "save_phase23a_individual_equity_decision_architecture" in source
