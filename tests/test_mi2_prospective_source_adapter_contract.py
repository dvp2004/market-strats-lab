from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "intelligence" / "mi2_prospective_source_adapter_contract_v1.yaml"
)


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


def test_contract_is_parseable_design_only_and_not_implemented() -> None:
    assert CONTRACT_PATH.is_file()
    contract = _contract()
    assert contract["design_only"] is True
    assert contract["research_only"] is True
    assert contract["portfolio_influence"] == 0
    assert contract["adapter_status"] == "not_implemented"


def test_provenance_sidecar_fields() -> None:
    contract = _contract()
    sidecar_schema = contract["provenance_sidecar_schema"]["fields"]

    expected = {
        "decision_date",
        "decision_timestamp_utc",
        "data_cutoff_or_availability_reference",
        "raw_prediction_artifact_sha256",
        "upstream_source_data_artifact_sha256",
        "model_identifier",
        "model_implementation_or_specification_sha256",
        "universe_identifier",
        "feature_or_signal_schema_identifier",
        "signal_horizon_sessions",
        "operator_capture_attestation",
    }
    assert expected <= set(sidecar_schema)


def test_source_to_export_mapping() -> None:
    contract = _contract()
    mapping = contract["source_to_export_mapping"]["raw_to_export_fields"]

    assert mapping["session_date"] == "decision_date"
    assert mapping["instrument_id"] == "asset_identifier"
    assert mapping["model_name"] == "model_identifier"
    assert mapping["prediction"] == "signal_score"

    vals = contract["adapter_validations"]
    assert "computed_deterministically" in vals["signal_rank"]
    assert "computed_deterministically" in vals["signal_percentile"]
    assert "hardcoded_true" in vals["research_only"]
    assert "hardcoded_zero" in vals["portfolio_influence"]


def test_canonical_model_binding() -> None:
    contract = _contract()
    validation_rules = contract["sidecar_validation_rules"]
    assert validation_rules["canonical_model_identifier_match"] is True
    assert validation_rules["frozen_implementation_hash_match"] is True
    assert validation_rules["cutoff_compatibility"] == "20:00 America/New_York"
    assert validation_rules["frozen_universe_match"] is True


def test_leakage_prevention_rules() -> None:
    contract = _contract()
    leakage = contract["leakage_prevention"]
    rules = set(leakage["rules"])

    assert "never_read_targets_or_outcomes_during_signal_generation_or_provenance" in rules
    assert "never_copy_targets_or_outcomes_to_export_packet_manifest_or_ledger" in rules
    assert "reject_selected_row_if_any_target_or_outcome_field_is_non_null" in rules
    assert "treat_non_null_future_outcome_as_fail_closed_breach" in rules


def test_runner_compatibility() -> None:
    contract = _contract()
    compat = contract["runner_compatibility"]

    assert (
        "hash_of_the_raw_upstream_prediction_artifact"
        in compat["runner_source_artifact_sha256_meaning"]
    )
    assert "separately" in compat["upstream_source_data_artifact_recording"]
    assert "not_authoritative" in compat["adapter_export_authoritative_status"]
    assert "adapter_must_not_write_to_ledger" in compat["ledger_write_prohibition"]


def test_fail_closed_conditions() -> None:
    contract = _contract()
    fails = set(contract["fail_closed_conditions"])

    expected = {
        "missing_or_invalid_provenance_sidecar",
        "raw_artifact_hash_mismatch",
        "wrong_model_identifier",
        "model_specification_hash_mismatch",
        "universe_mismatch",
        "invalid_or_missing_cutoff",
        "decision_timestamp_incoherent",
        "missing_schema_or_horizon",
        "missing_required_source_fields",
        "duplicate_or_incomplete_assets",
        "prohibited_field_output",
        "selected_row_contains_matured_target_or_outcome",
        "non_research_only_output",
        "nonzero_portfolio_influence",
    }
    assert expected <= fails


def test_prohibited_fields() -> None:
    contract = _contract()
    prohibited = set(contract["leakage_prevention"]["prohibited_fields"])

    expected = {
        "target_value",
        "target_weight",
        "position_size",
        "portfolio_weight",
        "portfolio_return",
        "strategy_return",
        "realised_return",
        "order",
        "trade",
        "broker",
        "account",
        "execution",
        "cash_allocation",
        "real_money",
    }
    assert expected <= prohibited


def test_no_forbidden_paths_or_secrets() -> None:
    raw = CONTRACT_PATH.read_text(encoding="utf-8")

    # Absolute paths
    assert re.search(r"[A-Za-z]:[\\/]", raw) is None
    # Network calls
    assert "http://" not in raw.casefold()
    assert "https://" not in raw.casefold()

    forbidden_keys = {
        "api_key",
        "password",
        "secret",
        "credential",
        "account_id",
        "broker_url",
        "broker_account",
    }
    all_keys = {key.casefold() for key in _walk_keys(_contract())}
    assert not (all_keys & forbidden_keys)
