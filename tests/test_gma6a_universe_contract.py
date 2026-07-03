from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
import yaml

from market_strats.global_multi_asset.gma6a_universe_contract import (
    CONFIG_PATH,
    FIXED_GMA6A_ADDITIONS,
    FROZEN_CORE_V1_UNIVERSE,
    GMA5_V1_EVIDENCE_BUNDLE_ID,
    GMA5_V1_EVIDENCE_ROOT_POLICY,
    GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_SHA256,
    GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE,
    GMA5_V1_REQUIRED_EVIDENCE_FILES,
    GMA6AEvidenceError,
    INSTRUMENT_FIELDS,
    PARENT_GMA4_COMMIT,
    REQUIRED_DATA_GATES,
    build_design_markdown,
    instrument_rows,
    load_gma6a_universe_contract,
    resolve_gma6a_evidence_files,
    validate_gma6a_universe_contract,
    validate_gma6a_evidence_bundle,
    write_design_outputs,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / (
    "src/market_strats/global_multi_asset/gma6a_universe_contract.py"
)
TEST_PATH = Path(__file__).resolve()


def _is_absolute_path_string(value: str) -> bool:
    return PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


def _nested_strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _nested_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nested_strings(item)
    elif isinstance(value, str):
        yield value


@pytest.fixture()
def contract():
    return load_gma6a_universe_contract(CONFIG_PATH)


def test_contract_loads_and_validates(contract):
    validate_gma6a_universe_contract(contract)
    rows = instrument_rows(contract)
    assert len(rows) == 29


def test_v1_core_universe_is_exact_frozen_order(contract):
    assert contract.raw["frozen_core_v1_universe"] == FROZEN_CORE_V1_UNIVERSE
    assert [row["ticker"] for row in contract.instruments[:22]] == FROZEN_CORE_V1_UNIVERSE


def test_gma6a_additions_are_exact_and_unique(contract):
    additions = [
        row["ticker"] for row in contract.instruments if row["core_or_addition"] == "addition"
    ]
    core = [row["ticker"] for row in contract.instruments if row["core_or_addition"] == "core"]
    assert additions == FIXED_GMA6A_ADDITIONS
    assert len(set(core) & set(additions)) == 0
    assert len({row["ticker"] for row in contract.instruments}) == 29


def test_each_instrument_has_required_contract_fields(contract):
    for row in contract.instruments:
        for field in INSTRUMENT_FIELDS:
            assert row[field]
        assert row["universe_version"] == "gma6a_expanded_etf_universe_v1"


def test_addition_specific_overlap_and_structure_notes(contract):
    by_ticker = {row["ticker"]: row for row in contract.instruments}
    assert "commodity-roll/carry review" in by_ticker["USO"]["structure_note"]
    assert "commodity-roll/carry review" in by_ticker["DBA"]["structure_note"]
    assert "EFA" in by_ticker["EWG"]["overlap_note"]
    assert "EFA" in by_ticker["EWJ"]["overlap_note"]
    assert "broad equity exposure" in by_ticker["VNQ"]["overlap_note"]


def test_parent_commit_snapshot_hash_and_data_gates_are_present(contract):
    metadata = contract.raw["contract"]
    assert metadata["parent_gma4_commit"] == PARENT_GMA4_COMMIT
    assert metadata["gma5_v1_evidence_bundle_id"] == GMA5_V1_EVIDENCE_BUNDLE_ID
    assert (
        metadata["gma5_v1_evidence_snapshot_manifest_file"]
        == GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE
    )
    assert metadata["gma5_v1_required_evidence_files"] == (
        GMA5_V1_REQUIRED_EVIDENCE_FILES
    )
    assert metadata["gma5_v1_evidence_root_policy"] == GMA5_V1_EVIDENCE_ROOT_POLICY
    assert "gma5_v1_evidence_snapshot_root" not in metadata
    assert (
        metadata["gma5_v1_evidence_snapshot_manifest_sha256"]
        == GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_SHA256
    )
    assert metadata["data_eligibility_gates"] == REQUIRED_DATA_GATES
    assert metadata["data_failure_status"] == "blocked_data_contract_failure"
    assert metadata["no_automatic_fallback_allowed"] is True


def test_invalid_addition_set_fails_closed(tmp_path: Path, contract):
    raw = deepcopy(contract.raw)
    raw["fixed_additions"][-1] = "EWC"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="fixed_additions"):
        validate_gma6a_universe_contract(load_gma6a_universe_contract(path))


def test_report_generation_is_deterministic(tmp_path: Path):
    csv_one = tmp_path / "one.csv"
    md_one = tmp_path / "one.md"
    csv_two = tmp_path / "two.csv"
    md_two = tmp_path / "two.md"
    write_design_outputs(CONFIG_PATH, csv_one, md_one)
    write_design_outputs(CONFIG_PATH, csv_two, md_two)
    assert csv_one.read_bytes() == csv_two.read_bytes()
    assert md_one.read_bytes() == md_two.read_bytes()
    assert csv_one.read_text(encoding="utf-8").count("\n") == 30
    assert "GMA-6A has no performance results" in md_one.read_text(encoding="utf-8")


def test_generated_markdown_contains_required_design_only_language(contract):
    text = build_design_markdown(contract)
    assert "observed development evidence" in text
    assert "not a pristine final holdout" in text
    assert "no execution or promotion decision is produced" in text
    assert "blocked_data_contract_failure" in text


def test_no_disallowed_decision_language_in_generated_markdown(contract):
    text = build_design_markdown(contract).lower()
    for term in ["winner", "deployable", "live-ready", "approved", "recommended"]:
        assert term not in text


def test_no_external_engine_or_model_imports_in_contract_module():
    source = MODULE_PATH.read_text(encoding="utf-8")
    blocked = [
        "gma4_replay_adapter",
        "gma5_atomic_sleeve_ensemble",
        "run_gma4",
        "strategy_library",
        "sklearn",
        "requests",
        "urllib",
        "yfinance",
    ]
    assert not any(term in source for term in blocked)


def test_contract_metadata_contains_no_absolute_path(contract):
    assert not any(
        _is_absolute_path_string(value) for value in _nested_strings(contract.raw)
    )


def test_production_module_contains_no_absolute_string_literal():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any(_is_absolute_path_string(value) for value in strings)


def test_evidence_root_must_be_supplied_explicitly(contract):
    with pytest.raises(GMA6AEvidenceError, match="gma6a_evidence_root_required"):
        resolve_gma6a_evidence_files(contract, None)


def test_relative_evidence_root_fails_closed(contract):
    with pytest.raises(
        GMA6AEvidenceError, match="gma6a_evidence_root_must_be_absolute"
    ):
        resolve_gma6a_evidence_files(contract, Path("relative-evidence"))


def test_missing_required_evidence_fails_closed(tmp_path: Path, contract):
    with pytest.raises(GMA6AEvidenceError, match="gma6a_required_evidence_missing"):
        resolve_gma6a_evidence_files(contract, tmp_path)


def test_explicit_evidence_root_resolves_synthetic_artifact(tmp_path: Path, contract):
    manifest = tmp_path / GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE
    manifest.write_text("synthetic placeholder\n", encoding="utf-8")
    resolved = resolve_gma6a_evidence_files(contract, tmp_path)
    assert resolved == {GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE: manifest}


def test_synthetic_artifact_hash_mismatch_fails_closed(tmp_path: Path, contract):
    manifest = tmp_path / GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE
    manifest.write_text("synthetic placeholder\n", encoding="utf-8")
    with pytest.raises(
        GMA6AEvidenceError, match="gma6a_evidence_manifest_hash_mismatch"
    ):
        validate_gma6a_evidence_bundle(contract, tmp_path)


def test_unit_test_has_no_excluded_artifact_dependency():
    tree = ast.parse(TEST_PATH.read_text(encoding="utf-8"))
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert referenced_names.isdisjoint({"REPORT_CSV", "REPORT_MD", "DOC_PATH"})


def test_markdown_table_contains_all_29_rows(contract):
    markdown = build_design_markdown(contract)
    for ticker in [*FROZEN_CORE_V1_UNIVERSE, *FIXED_GMA6A_ADDITIONS]:
        assert f"| {ticker} |" in markdown
