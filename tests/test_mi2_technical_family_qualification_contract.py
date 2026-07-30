from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "intelligence" / "mi2_technical_family_qualification_contract_v1.yaml"
)
EXPECTED_STATUSES = {
    "qualified_for_research_only_future_integration",
    "not_qualified_for_future_integration",
    "not_evaluable_from_existing_accepted_artifacts",
}
REQUIRED_CONCEPTS = {
    "accepted_input_artifact_class",
    "required_fields",
    "identity_keys",
    "decision_timestamp",
    "asset_identifier",
    "model_identifier",
    "score_field",
    "target_field",
    "point_in_time_availability",
    "technical_family_baselines",
    "primary_predictive_metric",
    "secondary_predictive_metrics",
    "chronological_evaluation_blocks",
    "purge_and_embargo",
    "missing_data_source_behavior",
    "qualification_comparison_row_policy",
    "deterministic_tie_handling",
    "forecast_family_pass_thresholds",
    "portfolio_gate_mapping",
    "ridge_to_portfolio_evidence_association",
    "family_level_status_rule",
}


def _contract() -> dict[str, Any]:
    value = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _walk(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_contract_exists_is_parseable_and_design_only() -> None:
    assert CONTRACT_PATH.is_file()
    contract = _contract()
    assert contract["design_only"] is True
    assert contract["evidence_class"] == "observed_development_evidence"
    assert contract["research_only"] is True
    assert contract["portfolio_influence"] == 0
    assert contract["embedded_performance_results"] is False


def test_exact_input_identity_timing_and_baselines_are_frozen() -> None:
    contract = _contract()
    artifacts = contract["accepted_input_artifact_class"]["artifacts"]
    prediction = next(
        item for item in artifacts if item["artifact_id"] == "mi2_walk_forward_predictions"
    )
    assert set(prediction["required_fields"]) == {
        "instrument_id",
        "session_date",
        "target_value",
        "prediction",
        "model_name",
        "evaluation_segment",
        "zero_prediction",
        "persistence_prediction",
    }
    timing = contract["identity_and_timing"]
    assert timing["prediction_identity_keys"] == ["session_date", "instrument_id", "model_name"]
    assert timing["decision_timestamp_field"] == "decision_timestamp_utc"
    assert timing["score_field"] == "prediction"
    assert timing["target_field"] == "target_value"
    assert contract["inherited_mi2_registry_rules"]["forecast_baselines"] == [
        "zero_forward_excess_return",
        "persistence_last_observed_return",
    ]


def test_chronology_metrics_and_registry_thresholds_are_inherited_exactly() -> None:
    contract = _contract()
    rules = contract["inherited_mi2_registry_rules"]
    windows = rules["walk_forward_and_holdout"]
    assert windows == {
        "initial_training_fraction": 0.5,
        "walk_forward_test_block_sessions": 20,
        "expanding_window": True,
        "purge_sessions": 20,
        "embargo_sessions": 20,
        "untouched_holdout_fraction": 0.2,
        "holdout_rule": "final_20_percent_of_coverage_audit_eligible_sessions",
        "holdout_tuning_allowed": False,
    }
    assert contract["supported_evaluation"]["primary_predictive_metric"]["name"] == "forecast_mae"
    assert [
        metric["name"]
        for metric in contract["supported_evaluation"]["secondary_predictive_metrics"]
    ] == ["forecast_rank_correlation"]
    assert rules["promotion_criteria"]["require_holdout_sharpe_improvement_minimum"] == 0.10
    assert (
        rules["promotion_criteria"]["require_holdout_max_drawdown_not_worse_by_more_than"] == 0.02
    )


def test_every_required_evaluation_concept_is_frozen_or_unresolved() -> None:
    resolution = _contract()["evaluation_concept_resolution"]
    assert set(resolution) == REQUIRED_CONCEPTS
    assert set(resolution.values()) <= {"frozen", "unresolved"}
    unresolved_ids = {item["prerequisite_id"] for item in _contract()["unresolved_prerequisites"]}
    assert unresolved_ids == {
        "qualification_comparison_row_policy",
        "forecast_family_pass_thresholds",
        "portfolio_gate_mapping",
        "ridge_to_portfolio_evidence_association",
    }


def test_status_rule_and_all_safety_boundaries_are_frozen() -> None:
    contract = _contract()
    rule = contract["family_level_status_rule"]
    assert set(rule["result_statuses"]) == EXPECTED_STATUSES
    assert [item["status"] for item in rule["precedence"]] == [
        "not_evaluable_from_existing_accepted_artifacts",
        "not_qualified_for_future_integration",
        "qualified_for_research_only_future_integration",
    ]
    assert rule["threshold_invention_allowed"] is False
    assert rule["metric_value_inspection_during_contract_design_allowed"] is False
    assert {
        "model_tuning",
        "model_refitting",
        "feature_addition_or_change",
        "target_change",
        "universe_change",
        "portfolio_construction",
        "ensemble_construction",
        "market_strats_allocation_change",
        "paper_session",
        "broker_instruction",
        "real_money_action",
    } <= set(contract["prohibited_changes"] + contract["prohibited_actions"])


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
    assert not ({key.casefold() for key, _ in _walk(_contract())} & forbidden_operational_keys)
    assert _contract()["embedded_performance_results"] is False
    assert "observed_metric_values" not in _contract()
