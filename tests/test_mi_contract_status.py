from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "configs" / "intelligence"
STATUS_PATH = CONFIG_ROOT / "mi_current_status_v1.yaml"
SCORECARD_PATH = CONFIG_ROOT / "mi2_technical_prospective_scorecard_contract_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_status_hashes_match_all_migrated_contracts_and_implementations() -> None:
    status = yaml.safe_load(STATUS_PATH.read_text(encoding="utf-8"))
    contracts = status["contracts"]

    expected_contracts = {path.name for path in CONFIG_ROOT.glob("*.yaml") if path != STATUS_PATH}
    assert set(contracts) == expected_contracts

    for file_name, entry in contracts.items():
        assert entry["contract_sha256"] == _sha256(CONFIG_ROOT / file_name)
        for relative_path, expected_hash in entry["implementations"].items():
            assert expected_hash == _sha256(ROOT / relative_path)


def test_scorecard_parent_hashes_are_resolved_and_exact() -> None:
    text = SCORECARD_PATH.read_text(encoding="utf-8")
    scorecard = yaml.safe_load(text)

    assert "to_be_recorded" not in text
    for parent in scorecard["frozen_parent_contracts"].values():
        assert parent["sha256"] == _sha256(CONFIG_ROOT / parent["file_name"])


def test_historical_statuses_are_not_presented_as_current_claims() -> None:
    status = yaml.safe_load(STATUS_PATH.read_text(encoding="utf-8"))
    contracts = status["contracts"]

    assert (
        contracts["mi2_prospective_source_adapter_contract_v1.yaml"]["current_status"]
        == "implemented_portable_and_tested"
    )
    assert (
        contracts["mi2_technical_prospective_snapshot_runner_contract_v1.yaml"][
            "current_status"
        ]
        == "implemented_portable_and_tested"
    )
    assert (
        contracts["mi2_technical_prospective_scorecard_contract_v1.yaml"][
            "current_status"
        ]
        == "parent_hashes_resolved_scorecard_not_implemented"
    )
    assert status["boundaries"]["real_prospective_observation_started"] is False
    assert status["boundaries"]["technical_family_qualified"] is False
    assert status["boundaries"]["portfolio_influence"] == 0
