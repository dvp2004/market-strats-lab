from pathlib import Path

import pandas as pd

from market_strats.analysis.individual_equity_feature_panel_contract import (
    build_availability_join_policy,
    build_cross_sectional_normalization_policy,
    build_dependency_readiness_matrix,
    build_feature_panel_schema,
    build_initial_feature_manifest,
    build_missingness_policy,
    build_target_registry,
    build_training_split_policy,
    save_phase23e_combined_feature_panel_contract,
    validate_feature_panel_frame,
    validate_target_frame,
)


def _config(tmp_path: Path) -> dict:
    return {
        "phase23e_combined_feature_panel_contract": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "phase23e"),
            "dashboard_status_path": str(
                tmp_path / "reports" / "paper_trading" / "dashboard" / "phase23e.csv"
            ),
        }
    }


def _valid_panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "panel_row_id": "2025-08-08|SP500_POINT_IN_TIME|US0378331005",
                "decision_timestamp_utc": "2025-08-08T20:00:00Z",
                "signal_date": "2025-08-08",
                "execution_date": "2025-08-11",
                "universe_id": "SP500_POINT_IN_TIME",
                "permanent_security_id": "US0378331005",
                "permanent_company_id": "CIK0000320193",
                "ticker_asof": "AAPL",
                "sector_asof": "Information Technology",
                "industry_asof": "Technology Hardware",
                "membership_known_timestamp_utc": "2025-01-01T00:00:00Z",
                "membership_effective_date": "1982-11-30",
                "membership_active": True,
                "model_cutoff_timestamp_utc": "2025-08-08T20:05:00Z",
                "technical_available_timestamp_utc": "2025-08-08T20:00:00Z",
                "fundamental_available_timestamp_utc": "2025-08-01T16:35:00Z",
                "sentiment_available_timestamp_utc": "2025-08-08T19:55:00Z",
                "macro_available_timestamp_utc": "2025-08-08T12:35:00Z",
                "cross_asset_available_timestamp_utc": "2025-08-08T20:00:00Z",
                "market_stress_available_timestamp_utc": "2025-08-08T20:00:00Z",
                "liquidity_available_timestamp_utc": "2025-08-08T20:00:00Z",
                "event_available_timestamp_utc": "2025-08-08T19:55:00Z",
                "feature_max_available_timestamp_utc": "2025-08-08T20:00:00Z",
                "feature_set_version": "phase23e_contract_v1",
                "source_snapshot_id": "snapshot-1",
                "split_label": "TRAIN",
                "training_eligible": True,
            }
        ]
    )


def _valid_targets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "panel_row_id": "2025-08-08|SP500_POINT_IN_TIME|US0378331005",
                "target_name": "forward_20d_excess_return_vs_universe",
                "target_horizon_trading_days": 20,
                "target_value": 0.04,
                "target_period_start_date": "2025-08-11",
                "target_period_end_date": "2025-09-08",
                "target_available_timestamp_utc": "2025-09-09T00:00:00Z",
                "target_set_version": "phase23e_targets_v1",
            }
        ]
    )


def test_panel_schema_contains_identity_membership_availability_and_split_contracts():
    columns = set(build_feature_panel_schema()["column"])
    assert {
        "decision_timestamp_utc",
        "permanent_security_id",
        "membership_known_timestamp_utc",
        "feature_max_available_timestamp_utc",
        "feature_set_version",
        "source_snapshot_id",
        "split_label",
    }.issubset(columns)


def test_initial_manifest_registers_all_feature_families():
    families = set(build_initial_feature_manifest()["feature_family"])
    assert {
        "technical",
        "fundamental",
        "sentiment_news",
        "macro",
        "cross_asset",
        "market_stress",
        "liquidity_risk",
        "event_corporate_action",
        "missingness_quality",
    } == families


def test_target_registry_separates_forward_labels_from_predictors():
    registry = build_target_registry(
        {
            "primary_target": "forward_20d_excess_return_vs_universe",
        }
    )
    assert registry["primary_target"].sum() == 1
    assert not bool(registry["predictor_table_allowed"].any())
    assert registry["horizon_trading_days"].max() == 63


def test_availability_missingness_and_normalization_policies_block_leakage():
    availability = " ".join(
        build_availability_join_policy()["requirement"].astype(str)
    ).lower()
    missingness = " ".join(build_missingness_policy()["requirement"].astype(str)).lower()
    normalization = " ".join(
        build_cross_sectional_normalization_policy()["requirement"].astype(str)
    ).lower()
    assert "cutoff" in availability
    assert "future" in availability
    assert "never backward-fill" in missingness
    assert "training fold" in missingness
    assert "eligible" in normalization
    assert "survivor" in normalization


def test_split_policy_uses_purge_embargo_and_blocks_random_rows():
    policy = build_training_split_policy(
        {
            "purge_window_trading_days": 63,
            "embargo_window_trading_days": 63,
            "maximum_target_horizon_trading_days": 63,
        }
    )
    text = " ".join(policy["requirement"].astype(str)).lower()
    assert "purged" in text or "removed" in text
    assert "embargo" in text
    assert "random row-level" in text
    assert policy.loc[policy["policy"].eq("purged_boundaries"), "parameter"].iloc[0] == 63


def test_dependencies_are_explicit_and_fail_closed():
    matrix = build_dependency_readiness_matrix()
    assert {
        "point_in_time_universe_membership",
        "stock_price_volume_corporate_actions",
        "fundamental_as_filed_facts",
        "sentiment_news_text",
        "macro_vintages",
    }.issubset(set(matrix["dependency"]))
    assert not bool(matrix["data_ready_now"].any())


def test_feature_panel_validator_accepts_valid_row():
    report = validate_feature_panel_frame(_valid_panel())
    assert report["passed"].all()
    assert bool(report["all_gates_passed"].iloc[0])


def test_feature_panel_validator_rejects_future_feature_clock():
    panel = _valid_panel()
    panel.loc[0, "sentiment_available_timestamp_utc"] = "2025-08-08T20:10:00Z"
    panel.loc[0, "feature_max_available_timestamp_utc"] = "2025-08-08T20:10:00Z"
    report = validate_feature_panel_frame(panel)
    row = report.loc[
        report["gate"].eq("feature_availability_not_after_cutoff")
    ].iloc[0]
    assert not bool(row["passed"])


def test_feature_panel_validator_rejects_duplicate_grain_and_wrong_max_clock():
    panel = pd.concat([_valid_panel(), _valid_panel()], ignore_index=True)
    panel.loc[1, "panel_row_id"] = "different-row-id"
    panel.loc[0, "feature_max_available_timestamp_utc"] = "2025-08-08T19:55:00Z"
    report = validate_feature_panel_frame(panel)
    assert not bool(
        report.loc[
            report["gate"].eq("decision_security_universe_grain_unique"), "passed"
        ].iloc[0]
    )
    assert not bool(
        report.loc[
            report["gate"].eq("feature_max_clock_reconciles"), "passed"
        ].iloc[0]
    )


def test_target_validator_accepts_valid_target_and_panel_lineage():
    report = validate_target_frame(_valid_targets(), panel=_valid_panel())
    assert report["passed"].all()


def test_target_validator_rejects_label_available_before_period_end():
    targets = _valid_targets()
    targets.loc[0, "target_available_timestamp_utc"] = "2025-08-20T00:00:00Z"
    report = validate_target_frame(targets, panel=_valid_panel())
    assert not bool(
        report.loc[
            report["gate"].eq("target_available_only_after_period_end"), "passed"
        ].iloc[0]
    )


def test_phase23e_writes_reports_without_reports_reports_and_blocks_training(tmp_path):
    config = {
        "phase23e_combined_feature_panel_contract": {
            "enabled": True,
            "output_dir": (
                "reports/individual_equity_decision_system/"
                "phase23e_combined_feature_panel_contract"
            ),
            "dashboard_status_path": (
                "reports/paper_trading/dashboard/"
                "phase23e_combined_feature_panel_contract_status.csv"
            ),
        }
    }
    outputs = save_phase23e_combined_feature_panel_contract(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    summary = outputs["summary"].iloc[0]
    assert bool(summary["phase_execution_gates_passed"])
    assert bool(summary["feature_panel_contract_ready"])
    assert not bool(summary["feature_panel_data_ready"])
    assert not bool(summary["panel_build_allowed"])
    assert not bool(summary["model_training_allowed"])
    assert not bool(summary["backtest_allowed"])
    assert not bool(summary["promotion_allowed"])
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])

    output_dir = (
        tmp_path
        / "reports"
        / "individual_equity_decision_system"
        / "phase23e_combined_feature_panel_contract"
    )
    required_files = [
        "phase23e_summary.csv",
        "phase23e_panel_grain_contract.csv",
        "phase23e_feature_panel_schema.csv",
        "phase23e_feature_manifest_schema.csv",
        "phase23e_feature_family_contract.csv",
        "phase23e_initial_feature_manifest.csv",
        "phase23e_target_registry.csv",
        "phase23e_availability_join_policy.csv",
        "phase23e_missingness_policy.csv",
        "phase23e_cross_sectional_normalization_policy.csv",
        "phase23e_training_split_policy.csv",
        "phase23e_dependency_readiness_matrix.csv",
        "phase23e_validation_plan.csv",
        "phase23e_phase23f_pilot_plan.csv",
        "phase23e_gate_report.csv",
        "phase23e_feature_panel_import_template.csv",
        "phase23e_target_import_template.csv",
        "phase23e_feature_manifest_import_template.csv",
        "phase23e_combined_feature_panel_contract.md",
    ]
    for filename in required_files:
        assert (output_dir / filename).exists()
    assert not (tmp_path / "reports" / "reports").exists()

    dashboard = (
        tmp_path
        / "reports"
        / "paper_trading"
        / "dashboard"
        / "phase23e_combined_feature_panel_contract_status.csv"
    )
    assert dashboard.exists()


def test_phase23e_respects_absolute_test_output_paths(tmp_path):
    outputs = save_phase23e_combined_feature_panel_contract(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )
    assert not outputs["summary"].empty
    assert (tmp_path / "reports" / "phase23e" / "phase23e_summary.csv").exists()


def test_run_backtest_exposes_phase23e_only_cli():
    source = Path("src/market_strats/run_backtest.py").read_text(encoding="utf-8")
    assert "--phase23e-only" in source
    assert "_run_phase23e_combined_feature_panel_contract(" in source
    assert "save_phase23e_combined_feature_panel_contract" in source
