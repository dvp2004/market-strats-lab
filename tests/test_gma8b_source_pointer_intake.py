from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset.gma8b_source_pointer_intake import (
    BUNDLE_LINEAGE_HASH,
    FAILED_DRY_RUN_REQUIREMENTS,
    GRID_HASH,
    MANUAL_ENTRY,
    NORMALISED_LINEAGE_HASH,
    OUTPUT_FILENAMES,
    REQUIRED_LANGUAGE,
    REQUIRED_TEMPLATE_FIELDS,
    SNAPSHOT_LINEAGE_HASH,
    SourcePointerIntakeError,
    build_template,
    generate_empty_template_dry_run,
    load_settings,
    validate_submitted_intake,
    verify_frozen_inputs,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.yaml")
SOURCE_PATH = Path("src/market_strats/global_multi_asset/gma8b_source_pointer_intake.py")
GMA8A_TEST_PATH = Path("tests/test_gma8a_broad_multi_asset_tournament_contract.py")
EXACT_GUARD_PATHS = {
    "configs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8a_broad_multi_asset_tournament_contract.py",
    "tests/test_gma8a_broad_multi_asset_tournament_contract.py",
    "configs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8b_historical_data_provenance.py",
    "tests/test_gma8b_historical_data_provenance.py",
    "configs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8b_source_pointer_intake.py",
    "tests/test_gma8b_source_pointer_intake.py",
    "configs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8c_frozen_etf_etp_tournament.py",
    "tests/test_gma8c_frozen_etf_etp_tournament.py",
}


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_intake(tmp_path: Path) -> tuple[dict[str, str], Path]:
    worktree_root = tmp_path / "gma8_worktree"
    worktree_root.mkdir()
    source_root = tmp_path / "manual_source_files"
    source_root.mkdir()
    panel = source_root / "adjusted_prices.csv"
    panel.write_text("session_date,SPY\n2020-01-02,100.0\n", encoding="utf-8")
    panel_hash = _sha256(panel)
    inventory = source_root / "normalised_inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "normalised_bundle_hash": NORMALISED_LINEAGE_HASH,
                "files": [
                    {
                        "path": str(panel),
                        "sha256": panel_hash,
                        "role": "adjusted_price_source",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot = source_root / "gma6_snapshot_manifest.json"
    snapshot.write_text(
        json.dumps(
            {
                "lineage": {
                    "gma6_snapshot_manifest_hash": SNAPSHOT_LINEAGE_HASH,
                    "gma6b_data_bundle_manifest_hash": BUNDLE_LINEAGE_HASH,
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    intake = {
        "gma6_snapshot_manifest_path": str(snapshot),
        "normalised_file_inventory_path": str(inventory),
        "adjusted_price_panel_path": str(panel),
        "gma6_snapshot_manifest_sha256": _sha256(snapshot),
        "normalised_file_inventory_sha256": _sha256(inventory),
        "adjusted_price_panel_sha256": panel_hash,
        "gma6_snapshot_manifest_expected_lineage_hash": SNAPSHOT_LINEAGE_HASH,
        "gma6b_data_bundle_manifest_expected_lineage_hash": BUNDLE_LINEAGE_HASH,
        "normalised_bundle_expected_lineage_hash": NORMALISED_LINEAGE_HASH,
        "operator_attestation": "I attest these are exact immutable local source files.",
        "created_timestamp_utc": "2026-06-27T00:00:00Z",
    }
    return intake, worktree_root


def test_gma8a_counts_and_strategy_grid_hash_are_verified():
    evidence = verify_frozen_inputs(load_settings(CONFIG_PATH))
    assert evidence.base_strategy_template_count == 80
    assert evidence.arm_trial_count == 160
    assert evidence.strategy_grid_hash == GRID_HASH


def test_all_three_frozen_gma6_lineage_hashes_are_required():
    evidence = verify_frozen_inputs(load_settings(CONFIG_PATH))
    assert evidence.gma6_snapshot_manifest_hash == SNAPSHOT_LINEAGE_HASH
    assert evidence.gma6b_data_bundle_manifest_hash == BUNDLE_LINEAGE_HASH
    assert evidence.normalised_bundle_hash == NORMALISED_LINEAGE_HASH


def test_template_has_exact_fields_and_manual_entry_values_only():
    template = build_template(load_settings(CONFIG_PATH))
    assert list(template) == REQUIRED_TEMPLATE_FIELDS
    assert len(template) == 11
    assert set(template.values()) == {MANUAL_ENTRY}


def test_empty_template_is_rejected_as_submitted_intake(tmp_path: Path):
    template = build_template(load_settings(CONFIG_PATH))
    with pytest.raises(SourcePointerIntakeError, match="empty template"):
        validate_submitted_intake(template, tmp_path)


@pytest.mark.parametrize(
    "field",
    [
        "gma6_snapshot_manifest_path",
        "normalised_file_inventory_path",
        "adjusted_price_panel_path",
        "gma6_snapshot_manifest_sha256",
        "normalised_file_inventory_sha256",
        "adjusted_price_panel_sha256",
        "operator_attestation",
    ],
)
def test_missing_path_hash_or_attestation_fails_closed(tmp_path: Path, field: str):
    intake, root = _valid_intake(tmp_path)
    intake.pop(field)
    with pytest.raises(SourcePointerIntakeError):
        validate_submitted_intake(intake, root)


def test_relative_path_fails_closed(tmp_path: Path):
    intake, root = _valid_intake(tmp_path)
    intake["adjusted_price_panel_path"] = "relative\\adjusted_prices.csv"
    with pytest.raises(SourcePointerIntakeError, match="absolute Windows path"):
        validate_submitted_intake(intake, root)


def test_directory_path_fails_closed(tmp_path: Path):
    intake, root = _valid_intake(tmp_path)
    intake["adjusted_price_panel_path"] = str(tmp_path)
    with pytest.raises(SourcePointerIntakeError, match="existing file"):
        validate_submitted_intake(intake, root)


def test_path_inside_gma8_worktree_fails_closed(tmp_path: Path):
    intake, root = _valid_intake(tmp_path)
    forbidden_panel = root / "adjusted_prices.csv"
    forbidden_panel.write_text("not read\n", encoding="utf-8")
    intake["adjusted_price_panel_path"] = str(forbidden_panel)
    intake["adjusted_price_panel_sha256"] = _sha256(forbidden_panel)
    with pytest.raises(SourcePointerIntakeError, match="GMA-8 worktree"):
        validate_submitted_intake(intake, root)


def test_synthetic_direct_file_intake_with_matching_hashes_is_structurally_valid(
    tmp_path: Path,
):
    intake, root = _valid_intake(tmp_path)
    result = validate_submitted_intake(intake, root)
    assert result["validation_status"] == "structurally_valid_source_pointer_intake"
    assert result["historical_price_panel_parsed"] is False
    assert set(result["resolved_paths"]) == {
        "gma6_snapshot_manifest_path",
        "normalised_file_inventory_path",
        "adjusted_price_panel_path",
    }


def test_hash_mismatch_fails_closed(tmp_path: Path):
    intake, root = _valid_intake(tmp_path)
    intake["adjusted_price_panel_sha256"] = "0" * 64
    with pytest.raises(SourcePointerIntakeError, match="SHA-256 mismatch"):
        validate_submitted_intake(intake, root)


def test_no_source_path_discovery_or_directory_enumeration_is_used():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for prohibited in [
        "Get-ChildItem",
        "Path.rglob",
        "Path.glob",
        "os.walk",
        "glob.glob",
        "directory enumeration",
    ]:
        assert prohibited not in source


def test_real_empty_template_dry_run_does_not_read_historical_price_panel(tmp_path: Path):
    output = tmp_path / "output"
    generate_empty_template_dry_run(CONFIG_PATH, output)
    dry_run = json.loads(
        (output / "gma8b_source_pointer_template_dry_run_v1.json").read_text(encoding="utf-8")
    )
    assert dry_run["source_pointer_dry_run_status"] == ("not_run_missing_manual_source_pointers")
    assert dry_run["submitted_source_pointer_intake_present"] is False
    assert dry_run["historical_price_panel_read"] is False
    assert dry_run["failed_requirements"] == FAILED_DRY_RUN_REQUIREMENTS


def test_no_strategy_or_execution_work_is_invoked():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for prohibited in [
        "yfinance",
        "run_backtest",
        "gma4_tournament",
        "fit(",
        "predict(",
        "submit_order(",
        "create_paper_order(",
    ]:
        assert prohibited not in source


def test_gma8a_guard_allows_exact_authorized_paths_and_rejects_unrelated_path():
    spec = importlib.util.spec_from_file_location("gma8a_guard_module", GMA8A_TEST_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ALLOWED_PATHS == EXACT_GUARD_PATHS
    assert "src/market_strats/global_multi_asset/unrelated.py" not in module.ALLOWED_PATHS
    assert not any("*" in path for path in module.ALLOWED_PATHS)


def test_required_language_is_emitted_exactly(tmp_path: Path):
    output = tmp_path / "output"
    generate_empty_template_dry_run(CONFIG_PATH, output)
    text = (output / "gma8b_source_pointer_preregistration_v1.md").read_text(encoding="utf-8")
    for sentence in REQUIRED_LANGUAGE:
        assert sentence in text


def test_output_generation_is_deterministic(tmp_path: Path):
    output = tmp_path / "output"
    generate_empty_template_dry_run(CONFIG_PATH, output)
    first = {name: (output / name).read_bytes() for name in OUTPUT_FILENAMES}
    generate_empty_template_dry_run(CONFIG_PATH, output)
    second = {name: (output / name).read_bytes() for name in OUTPUT_FILENAMES}
    assert first == second


def test_config_template_mutation_fails_closed(tmp_path: Path):
    raw = deepcopy(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    raw["manual_template"]["adjusted_price_panel_path"] = "guessed.csv"
    config = tmp_path / "bad.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    settings = load_settings(config)
    with pytest.raises(SourcePointerIntakeError, match="values must remain empty"):
        build_template(settings)
