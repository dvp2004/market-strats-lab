from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "intelligence" / "mi2_technical_prospective_observation_contract_v1.yaml"
)
EXPECTED_STATUSES = {
    "not_started",
    "observation_ready_pending_valid_snapshot_source",
    "observation_in_progress",
    "prospective_evidence_insufficient",
    "prospective_evidence_available_for_separate_review",
}
EXPECTED_EXPORT_FIELDS = {
    "decision_date",
    "asset_identifier",
    "model_identifier",
    "feature_or_signal_schema_identifier",
    "signal_horizon_sessions",
    "signal_score",
    "signal_rank",
    "signal_percentile",
    "data_cutoff_or_availability_reference",
    "source_artifact_sha256",
    "research_only",
    "portfolio_influence",
}


def _contract() -> dict[str, Any]:
    value = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_contract_is_parseable_design_only_and_not_started() -> None:
    assert CONTRACT_PATH.is_file()
    contract = _contract()
    assert contract["design_only"] is True
    assert contract["research_only"] is True
    assert contract["portfolio_influence"] == 0
    assert contract["prospective_observation_status"] == "not_started"
    assert contract["embedded_performance_results"] is False
    assert contract["embedded_model_outputs"] is False
    assert contract["trading_decision_created"] is False


def test_model_universe_timing_target_and_export_fields_are_frozen() -> None:
    contract = _contract()
    model = contract["frozen_technical_model"]
    assert model["model_identifier"] == "ridge_fixed_alpha_1_0"
    assert re.fullmatch(r"[0-9a-f]{64}", model["required_model_specification_sha256"])
    assert model["refit_or_tuning_allowed"] is False
    universe = contract["fixed_universe"]
    assert universe["asset_count"] == 22
    assert len(universe["symbols"]) == len(set(universe["symbols"])) == 22
    timing = contract["inherited_timing_and_target"]
    assert timing["decision_cutoff_local"] == "20:00 America/New_York"
    assert timing["earliest_execution_convention"] == "next_valid_us_equity_session_open"
    assert timing["target_horizon_sessions"] == 20
    assert set(contract["required_mi2e_signal_export_fields"]) == EXPECTED_EXPORT_FIELDS


def test_snapshot_provenance_immutability_and_determinism_are_required() -> None:
    snapshot = _contract()["prospective_snapshot_contract"]
    assert snapshot["retrospective_backfill_allowed"] is False
    assert snapshot["write_policy"] == "create_once_append_only"
    assert snapshot["overwrite_or_revision_allowed"] is False
    assert snapshot["complete_universe_rule"] == (
        "exactly_one_eligible_row_for_each_of_22_expected_assets"
    )
    required = set(snapshot["immutable_snapshot_requirements"])
    assert {
        "source_data_cutoff_timestamp",
        "source_artifact_sha256",
        "feature_snapshot_sha256",
        "availability_audit_sha256",
        "required_model_specification_sha256",
        "snapshot_payload_sha256",
    } <= required
    handling = _contract()["deterministic_data_quality_handling"]
    assert handling["missing_asset"] == "reject_entire_snapshot_before_write"
    assert handling["signal_tie_break"] == "asset_identifier_ascending"


def test_baseline_common_rows_and_outcome_maturity_fail_closed() -> None:
    contract = _contract()
    baselines = contract["baseline_common_row_contract"]
    assert baselines["required_baseline_model_identifiers"] == [
        "zero_forward_excess_return",
        "persistence_last_observed_return",
    ]
    assert baselines["common_row_rule"] == (
        "technical_model_and_both_baselines_must_share_the_exact_same_identity_set"
    )
    assert "without_imputation" in baselines["incomplete_baseline_handling"]
    maturity = contract["outcome_maturity_contract"]
    assert maturity["maturity_horizon_sessions"] == 20
    assert maturity["pre_maturity_assessment_allowed"] is False
    assert maturity["outcome_overwrite_or_revision_allowed"] is False
    assert maturity["outcome_record_write_policy"] == "separate_append_only_immutable_record"


def test_status_vocabulary_and_unresolved_governance_are_complete() -> None:
    contract = _contract()
    assert set(contract["readiness_logic"]["status_values"]) == EXPECTED_STATUSES
    assert contract["readiness_logic"]["readiness_status_is_not_qualification"] is True
    unresolved = {
        item["prerequisite_id"] for item in contract["unresolved_governance_prerequisites"]
    }
    assert unresolved == {
        "approved_prospective_snapshot_runner",
        "minimum_matured_prospective_decision_count",
        "minimum_prospective_calendar_duration",
        "prospective_family_metric_thresholds",
    }
    evaluation = contract["prospective_evaluation_boundary"]
    assert evaluation["evidence_sufficiency_numerical_threshold"] == (
        "unresolved_governance_prerequisite_not_inherited"
    )
    assert evaluation["observation_report_may_declare_family_pass"] is False
    assert evaluation["historical_artifacts_may_declare_family_pass"] is False


def test_portfolio_execution_fields_and_actions_are_prohibited() -> None:
    contract = _contract()
    assert {
        "target_weight",
        "position_size",
        "portfolio_weight",
        "order",
        "broker",
        "execution",
        "cash_allocation",
        "real_money",
    } <= set(contract["prohibited_fields"])
    assert {
        "model_fit_or_refit",
        "prediction_generation_in_this_phase",
        "outcome_calculation_in_this_phase",
        "portfolio_construction",
        "ensemble_construction",
        "market_strats_allocation_change",
        "paper_workflow",
        "broker_instruction",
        "live_or_real_money_action",
    } <= set(contract["prohibited_actions"])
    assert len(contract["required_safety_statements"]) == 3


def test_contract_has_no_paths_secrets_operational_endpoints_or_results() -> None:
    raw = CONTRACT_PATH.read_text(encoding="utf-8")
    assert re.search(r"[A-Za-z]:[\\/]", raw) is None
    assert "data/private" not in raw.replace("\\", "/").casefold()
    assert "http://" not in raw.casefold()
    assert "https://" not in raw.casefold()
    forbidden_operational_keys = {
        "api_key",
        "password",
        "secret",
        "credential",
        "account_id",
        "broker_url",
        "broker_account",
    }
    assert not ({key.casefold() for key in _walk_keys(_contract())} & forbidden_operational_keys)
    assert _contract()["embedded_performance_results"] is False
    assert _contract()["embedded_model_outputs"] is False
    assert _contract()["trading_decision_created"] is False
