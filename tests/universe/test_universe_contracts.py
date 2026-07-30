from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from market_strats.universe.contracts import (
    QualificationVerdict,
    UniverseContractError,
    load_source_registry,
    load_universe_contract,
    require_explicit_root,
    require_safe_relative_path,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/universe/free_sp500_point_in_time_universe_v1.yaml"
REGISTRY = ROOT / "configs/universe/free_source_registry_v1.yaml"


def test_frozen_contract_loads_with_required_research_boundaries() -> None:
    contract = load_universe_contract(CONTRACT)
    assert contract["historical_endpoint"].isoformat() == "2026-05-01"
    assert contract["model_training_authorized"] is False
    assert contract["same_close_execution"] == "prohibited"
    assert contract["current_survivor_filtering"] == "prohibited"


def test_same_close_execution_rejected(tmp_path: Path) -> None:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract["same_close_execution"] = "allowed"
    path = tmp_path / "contract.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(UniverseContractError, match="same_close_execution"):
        load_universe_contract(path)


def test_current_survivor_filtering_rejected(tmp_path: Path) -> None:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract["current_survivor_filtering"] = "allowed"
    path = tmp_path / "contract.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(UniverseContractError, match="current_survivor_filtering"):
        load_universe_contract(path)


def test_evaluation_segments_cannot_be_shortened(tmp_path: Path) -> None:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract["evaluation_segment_minimum_monthly_decisions"]["untouched_holdout"] = 35
    path = tmp_path / "contract.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(UniverseContractError, match="untouched_holdout"):
        load_universe_contract(path)


def test_source_registry_accepts_only_zero_cost_classes() -> None:
    _, sources = load_source_registry(REGISTRY)
    assert len(sources) == 5
    assert {row.cost_classification for row in sources.values()} == {
        "free_open_licence",
        "free_public_official",
        "free_personal_research_access",
    }


@pytest.mark.parametrize(
    "classification",
    ["paid", "trial_requiring_payment", "commercial_subscription", "unknown_cost"],
)
def test_paid_or_unknown_source_is_rejected(
    tmp_path: Path,
    classification: str,
) -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    registry["sources"][0]["cost_classification"] = classification
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with pytest.raises(UniverseContractError, match="Rejected source cost"):
        load_source_registry(path)


def test_missing_source_terms_field_rejected(tmp_path: Path) -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    del registry["sources"][0]["permitted_local_use"]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    with pytest.raises(UniverseContractError, match="missing fields"):
        load_source_registry(path)


def test_explicit_roots_are_required_and_must_be_absolute(tmp_path: Path) -> None:
    with pytest.raises(UniverseContractError, match="supplied explicitly"):
        require_explicit_root(None, "data_root")
    with pytest.raises(UniverseContractError, match="absolute path"):
        require_explicit_root(Path("relative"), "data_root")
    assert require_explicit_root(tmp_path, "data_root") == tmp_path.resolve()


def test_relative_artifact_paths_fail_closed_on_escape() -> None:
    assert require_safe_relative_path("folder/file.csv", "artifact") == Path("folder/file.csv")
    with pytest.raises(UniverseContractError, match="safe relative"):
        require_safe_relative_path("../outside.csv", "artifact")


def test_verdict_enum_contains_only_strict_terminal_values() -> None:
    assert {item.value for item in QualificationVerdict} == {
        "qualified_for_model_research",
        "blocked_free_source_coverage_failure",
        "blocked_identity_reconciliation_failure",
        "blocked_membership_reconciliation_failure",
        "blocked_price_or_delisting_failure",
        "blocked_source_terms_failure",
    }


def test_configs_contain_no_machine_specific_paths() -> None:
    text = CONTRACT.read_text(encoding="utf-8") + REGISTRY.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "c:\\" not in lowered
    assert "/users/" not in lowered
    assert "\\users\\" not in lowered
    assert "${" not in text
