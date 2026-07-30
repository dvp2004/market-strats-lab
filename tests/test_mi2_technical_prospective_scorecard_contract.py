from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "intelligence" / "mi2_technical_prospective_scorecard_contract_v1.yaml"
)

FROZEN_MODEL_IDENTIFIER = "ridge_fixed_alpha_1_0"
FROZEN_MODEL_SPEC_SHA256 = "b43ab173262717863dbcdc766d64968aed6c5539534dad8b1445f919b83e1100"
EXPECTED_ASSET_COUNT = 22
EXPECTED_SYMBOLS = {
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
    "BIL",
    "IEF",
    "TLT",
    "AGG",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
}
REQUIRED_CHAIN_FIELDS = {
    "snapshot_id",
    "decision_date",
    "model_identifier",
    "model_implementation_or_specification_sha256",
    "raw_prediction_artifact_sha256",
    "upstream_source_data_artifact_sha256",
    "snapshot_payload_sha256",
}
REQUIRED_PROHIBITED_FIELDS = {
    "target_weight",
    "position_size",
    "portfolio_weight",
    "portfolio_return",
    "strategy_return",
    "realised_pnl",
    "order",
    "trade",
    "broker",
    "account",
    "execution",
    "cash_allocation",
    "real_money",
}
FORBIDDEN_OPERATIONAL_KEYS = {
    "api_key",
    "password",
    "secret",
    "credential",
    "account_id",
    "broker_url",
    "broker_account",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contract() -> dict[str, Any]:
    value = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _walk_keys(value: Any):
    """Yield every key in a nested YAML structure."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _walk_values(value: Any):
    """Yield every leaf value in a nested YAML structure."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


# ---------------------------------------------------------------------------
# Test 1 — parseability and mandatory top-level flags
# ---------------------------------------------------------------------------


def test_contract_is_parseable_design_only_and_not_started() -> None:
    assert CONTRACT_PATH.is_file(), f"Contract not found: {CONTRACT_PATH}"
    contract = _contract()
    assert contract["design_only"] is True
    assert contract["research_only"] is True
    assert contract["portfolio_influence"] == 0
    assert contract["scorecard_status"] == "not_started"
    assert contract["embedded_performance_results"] is False
    assert contract["embedded_model_outputs"] is False
    assert contract["trading_decision_created"] is False
    assert contract["threshold_selected_using_historical_metric_values"] is False


# ---------------------------------------------------------------------------
# Test 2 — frozen universe, model identity, timing, target
# ---------------------------------------------------------------------------


def test_fixed_timing_target_universe_and_model_identity_are_defined() -> None:
    pop = _contract()["frozen_evaluation_population"]

    # Universe
    assert pop["universe_id"] == "mi1_us_liquid_etf_22_v1"
    assert pop["asset_count"] == EXPECTED_ASSET_COUNT
    symbols = set(pop["symbols"])
    assert len(symbols) == EXPECTED_ASSET_COUNT
    assert symbols == EXPECTED_SYMBOLS
    assert pop["universe_change_allowed"] is False

    # Model identity
    assert pop["canonical_model_identifier"] == FROZEN_MODEL_IDENTIFIER
    assert pop["required_model_implementation_or_specification_sha256"] == FROZEN_MODEL_SPEC_SHA256
    assert pop["model_refit_or_tuning_allowed"] is False

    # Timing
    assert pop["decision_cutoff_local"] == "20:00 America/New_York"
    assert pop["earliest_execution_convention"] == "next_valid_us_equity_session_open"
    assert pop["same_close_execution_allowed"] is False

    # Target
    assert pop["target_name"] == "20_trading_session_forward_total_return_excess_vs_BIL"
    assert pop["target_horizon_sessions"] == 20
    assert pop["target_price_policy"] == "documented_total_return_series_only"
    assert pop["target_is_future_information"] is True

    # Prospective-only boundary
    assert "after_this_contract_is_frozen" in pop["scorecard_applies_to"]
    assert pop["historical_mi2_artifacts_may_not_enter_scorecard"] is True


# ---------------------------------------------------------------------------
# Test 3 — anchor, maturity, and coverage policies are complete
# ---------------------------------------------------------------------------


def test_anchor_maturity_coverage_and_common_row_policies_are_complete() -> None:
    contract = _contract()

    # Overlap and observation rules
    overlap = contract["overlap_and_observation_rules"]
    assert overlap["daily_snapshots_must_not_control_primary_qualification_conclusion"] is True
    assert overlap["minimum_matured_non_overlapping_anchor_decisions"] == 12
    assert overlap["minimum_prospective_calendar_sessions"] == 252
    assert overlap["minimum_valid_anchor_coverage_ratio"] == 0.90
    anchor = overlap["primary_anchor_rule"]
    assert anchor["anchor_spacing_sessions"] == 20
    assert anchor["overlap_fraction_between_adjacent_anchors"] == 0.0

    # Three pre-conditions must all be named
    conditions = set(overlap["no_pass_permitted_until_all_three_conditions_met"])
    assert any("12" in c for c in conditions)
    assert any("252" in c for c in conditions)
    assert any("0_90" in c for c in conditions)

    # Common comparison-row policy
    row_policy = contract["common_comparison_row_policy"]
    assert row_policy["prerequisite_resolved"] == "qualification_comparison_row_policy"
    assert row_policy["imputation_allowed"] is False
    assert row_policy["baseline_recalculation_during_review_allowed"] is False
    assert row_policy["exclusion_is_deterministic"] is True
    logging_cfg = row_policy["deterministic_exclusion_logging"]
    assert logging_cfg["log_reason_for_every_excluded_row"] is True
    assert logging_cfg["exclusion_log_is_immutable"] is True

    # Tie handling
    tie = row_policy["tie_handling"]
    assert tie["primary_order"] == "signal_score_descending"
    assert tie["stable_tie_break"] == "asset_identifier_ascending"


# ---------------------------------------------------------------------------
# Test 4 — all primary and secondary metrics are defined
# ---------------------------------------------------------------------------


def test_all_primary_and_secondary_metrics_are_defined() -> None:
    metrics = _contract()["metrics"]
    assert metrics["prerequisite_resolved"] == "forecast_family_pass_thresholds"

    # Primary ranking metric
    rank_ic = metrics["primary_ranking_metric"]
    assert rank_ic["name"] == "anchor_date_rank_ic"
    assert rank_ic["correlation_type"] == "spearman"
    assert rank_ic["signal_field"] == "signal_score"
    assert rank_ic["target_field"] == "realised_20_session_bil_excess_return"
    assert rank_ic["scope"] == "per_valid_anchor_date"

    # Primary MAE metrics — all three predictors
    mae_cfg = metrics["primary_forecast_error_metrics"]
    mae_names = {m["name"] for m in mae_cfg["metrics"]}
    assert mae_names == {"ridge_mae", "zero_baseline_mae", "persistence_baseline_mae"}
    ridge_mae = next(m for m in mae_cfg["metrics"] if m["name"] == "ridge_mae")
    assert ridge_mae["model_identifier"] == FROZEN_MODEL_IDENTIFIER
    assert mae_cfg["mae_computed_on"] == "common_eligible_rows_only"

    # Secondary directional metric
    directional = metrics["secondary_directional_metric"]
    assert directional["name"] == "positive_rank_ic_rate"
    assert directional["scope"] == "across_all_valid_matured_anchor_dates"

    # Secondary spread diagnostic — must be descriptive only
    spread = metrics["secondary_spread_diagnostic"]
    assert spread["classification"] == "descriptive_target_space_diagnostic_only"
    assert spread["is_portfolio_return"] is False
    assert spread["is_strategy_return"] is False
    assert spread["is_investable_result"] is False
    assert spread["trading_result"] is False
    assert spread["must_not_control_pass_logic"] is True


# ---------------------------------------------------------------------------
# Test 5 — fixed pass logic is present and consistent
# ---------------------------------------------------------------------------


def test_fixed_pass_logic_is_present_and_consistent() -> None:
    pass_logic = _contract()["fixed_pass_logic"]

    assert pass_logic["no_metric_may_compensate_for_failure_of_another"] is True
    assert pass_logic["threshold_invention_using_historical_values_prohibited"] is True
    assert pass_logic["metric_value_inspection_during_contract_design_allowed"] is False
    assert (
        pass_logic["qualifying_status_label"]
        == "prospective_evidence_available_for_separate_review"
    )
    assert (
        pass_logic["maximum_achievable_scorecard_outcome"]
        == "prospective_evidence_available_for_separate_review"
    )

    condition_ids = {c["condition_id"] for c in pass_logic["all_conditions_required"]}
    assert "anchor_count_gate" in condition_ids
    assert "calendar_duration_gate" in condition_ids
    assert "coverage_ratio_gate" in condition_ids
    assert "mean_rank_ic_gate" in condition_ids
    assert "positive_rank_ic_frequency_gate" in condition_ids
    assert "ridge_mae_dominance_gate" in condition_ids
    assert "model_identity_integrity_gate" in condition_ids
    assert "no_portfolio_contamination_gate" in condition_ids
    assert len(condition_ids) == 8

    # Pass cannot directly cause integration or live action
    disallowed = set(pass_logic["this_outcome_does_not_authorise"])
    assert "ensemble_integration" in disallowed
    assert "gma_integration" in disallowed
    assert "market_strats_lab_allocation_change" in disallowed
    assert "broker_instruction" in disallowed
    assert "real_money_action" in disallowed
    assert pass_logic["separate_review_required_before_any_integration"] is True


# ---------------------------------------------------------------------------
# Test 6 — no historical result values appear in the contract
# ---------------------------------------------------------------------------


def test_no_historical_result_values_appear_in_contract() -> None:
    contract = _contract()
    assert contract["embedded_performance_results"] is False
    assert contract["embedded_model_outputs"] is False
    assert contract["trading_decision_created"] is False
    assert contract["threshold_selected_using_historical_metric_values"] is False

    # No key called observed_metric_values or similar must exist
    all_keys = set(_walk_keys(contract))
    forbidden_result_keys = {
        "observed_metric_values",
        "historical_metric_values",
        "backtested_result",
        "holdout_result",
        "realised_sharpe",
        "realised_drawdown",
    }
    assert not (all_keys & forbidden_result_keys)


# ---------------------------------------------------------------------------
# Test 7 — no portfolio-level performance or execution concepts are permitted
# ---------------------------------------------------------------------------


def test_no_portfolio_performance_or_execution_concepts_permitted() -> None:
    contract = _contract()

    # Prohibited fields list must contain all required entries
    prohibited = set(contract["prohibited_fields"])
    assert REQUIRED_PROHIBITED_FIELDS <= prohibited

    # No-portfolio boundary section
    no_portfolio = contract["no_portfolio_boundary"]
    assert no_portfolio["prerequisite_resolved"] == "portfolio_gate_mapping"
    assert no_portfolio["portfolio_metrics_evaluated"] == "none"
    assert no_portfolio["portfolio_weights_exist"] is False
    assert no_portfolio["trades_exist"] is False
    assert no_portfolio["strategy_returns_evaluated"] is False
    assert no_portfolio["sharpe_ratio_evaluated"] is False
    assert no_portfolio["drawdown_evaluated"] is False
    assert no_portfolio["broker_instructions_exist"] is False
    assert no_portfolio["real_money_actions_exist"] is False
    assert no_portfolio["top_bottom_spread_is_portfolio_return"] is False
    assert no_portfolio["top_bottom_spread_is_investable_result"] is False
    assert no_portfolio["portfolio_baseline_mapping"]["portfolio_gates_applied"] is False
    assert no_portfolio["portfolio_baseline_mapping"]["portfolio_gates_proxied"] is False

    # Prohibited actions list must cover portfolio and execution
    prohibited_actions = set(contract["prohibited_actions"])
    assert "portfolio_construction" in prohibited_actions
    assert "portfolio_simulation" in prohibited_actions
    assert "ensemble_construction" in prohibited_actions
    assert "broker_instruction" in prohibited_actions
    assert "live_or_real_money_action" in prohibited_actions
    assert "paper_workflow" in prohibited_actions
    assert "paper_session" in prohibited_actions
    assert "gma_integration" in prohibited_actions


# ---------------------------------------------------------------------------
# Test 8 — no absolute Windows paths, secrets, credentials, broker/account
#           references, or private data paths exist
# ---------------------------------------------------------------------------


def test_no_paths_secrets_credentials_or_private_data_in_contract() -> None:
    raw = CONTRACT_PATH.read_text(encoding="utf-8")

    # No absolute Windows or Unix paths
    assert re.search(r"[A-Za-z]:[\\/]", raw) is None, "Absolute Windows path found in contract"
    assert not re.search(r"^/[a-z]", raw, re.MULTILINE), "Absolute Unix path found in contract"

    # No private data directories
    assert "data/private" not in raw.casefold()

    # No network resources
    assert "http://" not in raw.casefold()
    assert "https://" not in raw.casefold()

    # No credential or broker keys
    all_keys = {k.casefold() for k in _walk_keys(_contract())}
    assert not (all_keys & FORBIDDEN_OPERATIONAL_KEYS), (
        f"Forbidden operational keys found: {all_keys & FORBIDDEN_OPERATIONAL_KEYS}"
    )


# ---------------------------------------------------------------------------
# Test 9 — a pass cannot directly cause ensemble, GMA, paper, broker, or live
#           action (safety boundary completeness)
# ---------------------------------------------------------------------------


def test_pass_cannot_directly_cause_integration_or_live_action() -> None:
    contract = _contract()

    # Pass logic maximum outcome check (already in test_5, repeated as safety)
    pass_logic = contract["fixed_pass_logic"]
    assert (
        pass_logic["maximum_achievable_scorecard_outcome"]
        == "prospective_evidence_available_for_separate_review"
    )
    assert pass_logic["separate_review_required_before_any_integration"] is True

    disallowed = set(pass_logic["this_outcome_does_not_authorise"])
    must_be_disallowed = {
        "ensemble_integration",
        "gma_integration",
        "market_strats_lab_allocation_change",
        "paper_session",
        "paper_workflow",
        "broker_instruction",
        "real_money_action",
        "live_action",
    }
    assert must_be_disallowed <= disallowed

    # Mandatory boundary statement must exist and reference separate review
    boundary = contract["mandatory_boundary"]
    assert "separate_review" in boundary.casefold() or "separately" in boundary.casefold()
    assert "prospective_evidence_available_for_separate_review" in boundary

    # Safety statements must exist (at least 3)
    safety = contract["required_safety_statements"]
    assert len(safety) >= 3
    combined = " ".join(safety).casefold()
    assert "research evidence only" in combined or "research evidence" in combined
    assert "no portfolio" in combined or "no portfolio weights" in combined
    assert "separate" in combined


# ---------------------------------------------------------------------------
# Test 10 — Ridge-to-evidence association is complete
# ---------------------------------------------------------------------------


def test_ridge_to_evidence_association_is_complete() -> None:
    contract = _contract()
    ridge = contract["ridge_to_evidence_association"]

    assert ridge["prerequisite_resolved"] == "ridge_to_portfolio_evidence_association"
    assert set(ridge["required_chain_fields"]) == REQUIRED_CHAIN_FIELDS
    assert ridge["chain_break_action"] == "reject_row_fail_closed"
    assert ridge["portfolio_rows_used_for_ridge_evidence"] is False

    # Provenance chain in accepted_snapshot_identity or required_provenance_chain
    chain = contract["required_provenance_chain"]
    assert set(chain["required_chain_fields"]) == REQUIRED_CHAIN_FIELDS
    assert chain["chain_break_action"] == "reject_row_fail_closed"


# ---------------------------------------------------------------------------
# Test 11 — snapshot identity, provenance, and fail-closed conditions defined
# ---------------------------------------------------------------------------


def test_snapshot_identity_provenance_and_fail_closed_conditions_are_defined() -> None:
    contract = _contract()

    snap_identity = contract["accepted_snapshot_identity"]
    assert snap_identity["overwrite_or_revision_allowed"] is False
    assert snap_identity["retrospective_backfill_allowed"] is False
    assert snap_identity["write_policy"] == "create_once_append_only"
    manifest_fields = set(snap_identity["required_manifest_fields"])
    assert {
        "snapshot_id",
        "decision_date",
        "payload_sha256",
        "source_artifact_sha256",
    } <= manifest_fields
    ledger_fields = set(snap_identity["required_ledger_fields"])
    assert {
        "decision_date",
        "snapshot_id",
        "payload_sha256",
        "registration_timestamp",
    } <= ledger_fields

    fail_closed = set(contract["fail_closed_conditions"])
    assert "model_identifier_mismatch" in fail_closed
    assert "leakage_detected" in fail_closed
    assert "snapshot_created_before_contract_freeze" in fail_closed
    assert "historical_artifact_presented_as_prospective_evidence" in fail_closed
    assert "prohibited_field_present_in_evidence_chain" in fail_closed
