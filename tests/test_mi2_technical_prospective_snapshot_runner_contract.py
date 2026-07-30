from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT / "configs" / "intelligence" / "mi2_technical_prospective_snapshot_runner_contract_v1.yaml"
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
    assert contract["runner_status"] == "not_implemented"


def test_contract_defines_correct_identities_and_cutoff() -> None:
    contract = _contract()

    identity = contract["fixed_identity"]
    assert identity["model_identifier"] == "ridge_fixed_alpha_1_0"
    assert "required_implementation_sha256" in identity
    assert identity["universe_identifier"] == "mi1_us_liquid_etf_22_v1"

    timing = contract["timing_and_cutoff"]
    assert timing["data_cutoff"] == "20:00 America/New_York"
    assert "after_20_00" in timing["earliest_permitted_snapshot_creation_time"].casefold()
    assert "next_valid_us_equity_session_open" in timing["execution_convention"]

    provenance = contract["required_provenance"]
    assert "source_data_cutoff_timestamp" in provenance
    assert "source_artifact_sha256" in provenance


def test_storage_policy_is_local_private_and_ignored() -> None:
    contract = _contract()
    policy = contract["storage_policy"]

    # Must use relative paths only
    assert not str(policy["root_directory"]).startswith("/")
    assert not re.match(r"[A-Za-z]:[\\/]", str(policy["root_directory"]))

    assert policy["is_local"] is True
    assert policy["is_private"] is True
    assert policy["is_versioned"] is False
    assert policy["layout_type"] == "append_only"
    assert "ignored_by_git" in policy["pre_write_verification"]


def test_ledger_and_manifest_schemas_exist() -> None:
    contract = _contract()
    manifest = set(contract["snapshot_manifest_schema"]["fields"])
    assert {"snapshot_id", "decision_date", "payload_sha256", "source_artifact_sha256"} <= manifest

    ledger = set(contract["ledger_schema"]["fields"])
    assert {"decision_date", "snapshot_id", "payload_sha256", "registration_timestamp"} <= ledger

    prohibited_ledger = set(contract["ledger_schema"]["prohibited_ledger_concepts"])
    assert {"targets", "weights", "orders", "execution", "performance"} <= prohibited_ledger


def test_safety_and_integrity_concepts_present() -> None:
    contract = _contract()
    safety = contract["safety_and_integrity"]

    assert safety["duplicate_decision_date_prevention"] is True
    assert safety["overwrite_prohibition"] is True
    assert "before_and_after" in safety["hash_verification"]

    fails = set(safety["fail_closed_conditions"])
    assert {
        "incomplete_universe",
        "invalid_cutoff",
        "wrong_model_identity",
        "absent_provenance",
        "duplicate_decision_date",
        "prohibited_fields_present",
    } <= fails


def test_prohibited_fields_are_listed() -> None:
    contract = _contract()
    prohibited = set(contract["prohibited_fields"])
    assert {
        "target_weight",
        "position_size",
        "portfolio_weight",
        "order",
        "trade",
        "broker",
        "account",
        "execution",
        "cash_allocation",
        "real_money",
        "portfolio_return",
        "strategy_return",
    } <= prohibited


def test_contract_has_no_paths_secrets_or_live_data() -> None:
    raw = CONTRACT_PATH.read_text(encoding="utf-8")

    # Absolute paths
    assert re.search(r"[A-Za-z]:[\\/]", raw) is None
    # Network calls
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
    all_keys = {key.casefold() for key in _walk_keys(_contract())}
    assert not (all_keys & forbidden_operational_keys)
