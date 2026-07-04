from __future__ import annotations

import ast
import hashlib
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
import yaml

from market_strats.global_multi_asset.gma6b2_commodity_etp_historical_continuity import (
    CONFIG_PATH,
    GMA6B2PortabilityError,
    INCOMPLETE,
    OVERLAY_BLOCKED,
    OVERLAY_FLAGS,
    REQUIRED_TICKERS,
    resolve_evidence_files,
    run_historical_continuity_audit,
    validate_historical_continuity_contract,
)

MODULE_PATH = (
    CONFIG_PATH.parents[2]
    / "src/market_strats/global_multi_asset/"
    "gma6b2_commodity_etp_historical_continuity.py"
)


def _load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, config: dict[str, Any]) -> Path:
    path = tmp_path / "contract" / "continuity.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _prepare_evidence(
    tmp_path: Path,
    config: dict[str, Any],
    *,
    omit_source_id: str | None = None,
) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    for record in config["source_manifest"]:
        source_id = record["official_source_id"]
        if source_id == omit_source_id:
            continue
        payload = f"synthetic continuity evidence for {source_id}\n".encode()
        path = root / record["required_evidence_file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        record["source_sha256"] = hashlib.sha256(payload).hexdigest()
    return root


def _prepared_run(
    tmp_path: Path,
    config: dict[str, Any] | None = None,
):
    config = deepcopy(config or _load_config())
    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    output_root = tmp_path / "outputs"
    result = run_historical_continuity_audit(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    return result, output_root


def _audit(config: dict[str, Any], ticker: str) -> dict[str, Any]:
    return next(row for row in config["audit_records"] if row["ticker"] == ticker)


def _source(
    config: dict[str, Any], ticker: str, role: str
) -> dict[str, Any]:
    return next(
        row
        for row in config["source_manifest"]
        if row["ticker"] == ticker and row["historical_window_role"] == role
    )


def _all_strings(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_strings(child)
    elif isinstance(value, str):
        yield value


def test_contract_is_portable_and_valid_without_artifacts():
    config = _load_config()
    validate_historical_continuity_contract(config)
    strings = list(_all_strings(config))
    assert not any("://" in value for value in strings)
    assert not any(PureWindowsPath(value).is_absolute() for value in strings)
    assert not any("official_source_url" in value for value in strings)
    assert (
        config["contract"]["evidence_root_policy"]
        == "must_be_supplied_explicitly_for_artifact_validation"
    )
    assert (
        config["contract"]["output_root_policy"]
        == "must_be_supplied_explicitly_for_output_generation"
    )


def test_explicit_roots_are_required(tmp_path: Path):
    config = deepcopy(_load_config())
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6B2PortabilityError, match="gma6b2_evidence_root_required"
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=None,
            output_root=tmp_path / "outputs",
        )

    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6B2PortabilityError, match="gma6b2_output_root_required"
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=evidence_root,
            output_root=None,
        )


def test_relative_roots_are_rejected(tmp_path: Path):
    config = deepcopy(_load_config())
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6B2PortabilityError,
        match="gma6b2_evidence_root_must_be_absolute",
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=Path("evidence"),
            output_root=tmp_path / "outputs",
        )

    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6B2PortabilityError, match="gma6b2_output_root_must_be_absolute"
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=evidence_root,
            output_root=Path("outputs"),
        )


def test_missing_evidence_root_fails_deterministically(tmp_path: Path):
    config_path = _write_config(tmp_path, _load_config())
    with pytest.raises(
        GMA6B2PortabilityError, match="gma6b2_evidence_root_missing"
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=tmp_path / "absent",
            output_root=tmp_path / "outputs",
        )


def test_missing_required_file_fails_deterministically(tmp_path: Path):
    config = deepcopy(_load_config())
    missing_id = config["source_manifest"][-1]["official_source_id"]
    evidence_root = _prepare_evidence(
        tmp_path, config, omit_source_id=missing_id
    )
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6B2PortabilityError,
        match=f"gma6b2_required_evidence_missing:{missing_id}",
    ):
        run_historical_continuity_audit(
            config_path,
            evidence_root=evidence_root,
            output_root=tmp_path / "outputs",
        )


def test_invalid_relative_evidence_path_is_rejected():
    config = deepcopy(_load_config())
    config["source_manifest"][0]["required_evidence_file"] = "../outside.txt"
    with pytest.raises(
        GMA6B2PortabilityError, match="gma6b2_invalid_relative_path"
    ):
        validate_historical_continuity_contract(config)


def test_absolute_and_url_like_evidence_paths_are_rejected():
    for invalid_path in (
        "/" + "outside.txt",
        "C" + ":" + "\\outside.txt",
        "https" + ":" + "//invalid.example/evidence",
    ):
        config = deepcopy(_load_config())
        config["source_manifest"][0]["required_evidence_file"] = invalid_path
        with pytest.raises(
            GMA6B2PortabilityError, match="gma6b2_invalid_relative_path"
        ):
            validate_historical_continuity_contract(config)


def test_checksum_mismatch_fails_deterministically(tmp_path: Path):
    config = deepcopy(_load_config())
    evidence_root = _prepare_evidence(tmp_path, config)
    first = config["source_manifest"][0]
    path = evidence_root / first["required_evidence_file"]
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(
        GMA6B2PortabilityError,
        match=f"gma6b2_evidence_checksum_mismatch:{first['official_source_id']}",
    ):
        resolve_evidence_files(config, evidence_root)


def test_outputs_are_written_only_below_injected_root(tmp_path: Path):
    result, output_root = _prepared_run(tmp_path)
    expected = {
        "gma6b2_commodity_etp_historical_continuity_v1.csv",
        "gma6b2_commodity_etp_historical_continuity_v1.md",
        "gma6b2_commodity_etp_historical_source_manifest_v1.csv",
    }
    assert result.overlay_status == OVERLAY_FLAGS
    assert {path.name for path in output_root.iterdir()} == expected
    assert all(path.is_file() for path in output_root.iterdir())
    assert not (tmp_path / "reports").exists()


def test_uso_and_dba_must_both_be_present():
    config = _load_config()
    config["audit_records"] = [
        row for row in config["audit_records"] if row["ticker"] == "USO"
    ]
    with pytest.raises(ValueError, match="USO and DBA"):
        validate_historical_continuity_contract(config)


def test_default_audit_documents_flagged_overlay(tmp_path: Path):
    result, _ = _prepared_run(tmp_path)
    assert [row["ticker"] for row in result.rows] == REQUIRED_TICKERS
    assert result.overlay_status == OVERLAY_FLAGS
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert (
        uso["required_later_regime_flag"]
        == "uso_roll_methodology_pre_may_2020_vs_from_may_2020"
    )


def test_non_primary_source_fails_validation(tmp_path: Path):
    config = _load_config()
    config["source_manifest"][0]["document_type"] = "market_data_website"
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["historical_continuity_status"] == INCOMPLETE
    assert "non_primary_official_source" in uso["blocking_reason"]


def test_missing_early_window_reference_fails_closed(tmp_path: Path):
    config = _load_config()
    early_dba = _source(config, "DBA", "early_window_reference")
    config["source_manifest"].remove(early_dba)
    result, _ = _prepared_run(tmp_path, config)
    dba = next(row for row in result.rows if row["ticker"] == "DBA")
    assert dba["later_research_execution_overlay_eligibility"] == OVERLAY_BLOCKED
    assert "missing_early_window_reference" in dba["blocking_reason"]


def test_missing_current_structure_reference_fails_closed(tmp_path: Path):
    config = _load_config()
    current_uso = _source(config, "USO", "current_structure_reference")
    config["source_manifest"].remove(current_uso)
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["later_research_execution_overlay_eligibility"] == OVERLAY_BLOCKED
    assert "missing_current_structure_reference" in uso["blocking_reason"]


def test_documented_material_change_requires_regime_flag(tmp_path: Path):
    config = _load_config()
    _audit(config, "USO")["required_later_regime_flag"] = "not_required"
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["historical_continuity_status"] == INCOMPLETE
    assert "methodology_regime_flag_required" in uso["blocking_reason"]


def test_incomplete_continuity_blocks_overlay(tmp_path: Path):
    config = _load_config()
    dba = _audit(config, "DBA")
    dba["historical_continuity_status"] = "continuity_evidence_incomplete"
    dba["later_research_execution_overlay_eligibility"] = (
        "blocked_data_contract_failure"
    )
    result, _ = _prepared_run(tmp_path, config)
    assert result.overlay_status == OVERLAY_BLOCKED


def test_spot_proxy_wording_fails_validation(tmp_path: Path):
    config = _load_config()
    dba = _audit(config, "DBA")
    dba["spot_proxy_claim_permitted"] = True
    dba["historical_return_interpretation"] = (
        "DBA adjusted prices are used as a spot proxy."
    )
    result, _ = _prepared_run(tmp_path, config)
    dba_row = next(row for row in result.rows if row["ticker"] == "DBA")
    assert dba_row["historical_continuity_status"] == INCOMPLETE
    assert "spot_proxy_claim_not_permitted" in dba_row["blocking_reason"]


def test_repeated_generation_is_deterministic(tmp_path: Path):
    config = deepcopy(_load_config())
    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    output_root = tmp_path / "outputs"
    first = run_historical_continuity_audit(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    first_outputs = {
        path.name: path.read_bytes() for path in sorted(output_root.iterdir())
    }
    second = run_historical_continuity_audit(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    second_outputs = {
        path.name: path.read_bytes() for path in sorted(output_root.iterdir())
    }
    assert first == second
    assert first_outputs == second_outputs


def test_production_module_has_no_cwd_output_or_hidden_discovery():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assigned_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    blocked_calls = {
        "expand" + "user",
        "ho" + "me",
        "r" + "glob",
        "glob",
        "get" + "env",
    }
    assert not {"REPORT_CSV", "REPORT_MD", "SOURCE_MANIFEST_CSV"} & assigned_names
    assert not {"os", "glob", "requests", "urllib"} & imported_modules
    assert not blocked_calls & called_attributes


def test_run_attempts_no_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    import socket

    def fail_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", fail_network)
    result, _ = _prepared_run(tmp_path)
    assert result.overlay_status == OVERLAY_FLAGS
