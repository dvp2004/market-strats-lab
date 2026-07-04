from __future__ import annotations

import ast
import hashlib
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
import yaml

from market_strats.global_multi_asset.gma6b_commodity_pool_structure_review import (
    BLOCKED_STATUS,
    CONFIG_PATH,
    ELIGIBLE,
    GMA6BPortabilityError,
    OVERLAY_BOTH_DOCUMENTED,
    REQUIRED_TICKERS,
    resolve_evidence_files,
    run_structure_review,
    validate_structure_review_contract,
)

MODULE_PATH = (
    CONFIG_PATH.parents[2]
    / "src/market_strats/global_multi_asset/gma6b_commodity_pool_structure_review.py"
)


def _load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, config: dict[str, Any]) -> Path:
    path = tmp_path / "contract" / "review.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _prepare_evidence(
    tmp_path: Path,
    config: dict[str, Any],
    *,
    omit_ticker: str | None = None,
) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    for record in config["review_records"]:
        if record["ticker"] == omit_ticker:
            continue
        payload = f"synthetic evidence for {record['ticker']}\n".encode()
        relative = Path(record["required_evidence_file"])
        path = root / relative
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
    result = run_structure_review(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    return result, output_root


def _record(config: dict[str, Any], ticker: str) -> dict[str, Any]:
    return next(row for row in config["review_records"] if row["ticker"] == ticker)


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
    validate_structure_review_contract(config)
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
        GMA6BPortabilityError, match="gma6b_evidence_root_required"
    ):
        run_structure_review(
            config_path,
            evidence_root=None,
            output_root=tmp_path / "outputs",
        )

    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_output_root_required"
    ):
        run_structure_review(
            config_path,
            evidence_root=evidence_root,
            output_root=None,
        )


def test_relative_roots_are_rejected(tmp_path: Path):
    config = deepcopy(_load_config())
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_evidence_root_must_be_absolute"
    ):
        run_structure_review(
            config_path,
            evidence_root=Path("evidence"),
            output_root=tmp_path / "outputs",
        )

    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_output_root_must_be_absolute"
    ):
        run_structure_review(
            config_path,
            evidence_root=evidence_root,
            output_root=Path("outputs"),
        )


def test_missing_evidence_root_fails_deterministically(tmp_path: Path):
    config_path = _write_config(tmp_path, _load_config())
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_evidence_root_missing"
    ):
        run_structure_review(
            config_path,
            evidence_root=tmp_path / "absent",
            output_root=tmp_path / "outputs",
        )


def test_missing_required_evidence_file_fails_deterministically(tmp_path: Path):
    config = deepcopy(_load_config())
    evidence_root = _prepare_evidence(tmp_path, config, omit_ticker="DBA")
    config_path = _write_config(tmp_path, config)
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_required_evidence_missing:DBA"
    ):
        run_structure_review(
            config_path,
            evidence_root=evidence_root,
            output_root=tmp_path / "outputs",
        )


@pytest.mark.parametrize(
    "invalid_path",
    [
        "../outside.txt",
    ],
)
def test_invalid_relative_evidence_path_is_rejected(invalid_path: str):
    config = deepcopy(_load_config())
    _record(config, "USO")["required_evidence_file"] = invalid_path
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_invalid_relative_path"
    ):
        validate_structure_review_contract(config)


def test_posix_absolute_evidence_path_is_rejected():
    config = deepcopy(_load_config())
    absolute_path = "/" + "outside.txt"
    _record(config, "USO")["required_evidence_file"] = absolute_path
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_invalid_relative_path"
    ):
        validate_structure_review_contract(config)


def test_windows_absolute_evidence_path_is_rejected():
    config = deepcopy(_load_config())
    absolute_path = "C" + ":" + "\\outside.txt"
    _record(config, "USO")["required_evidence_file"] = absolute_path
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_invalid_relative_path"
    ):
        validate_structure_review_contract(config)


def test_url_like_evidence_path_is_rejected():
    config = deepcopy(_load_config())
    url_like_path = "https" + ":" + "//invalid.example/evidence"
    _record(config, "USO")["required_evidence_file"] = url_like_path
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_invalid_relative_path"
    ):
        validate_structure_review_contract(config)


def test_checksum_mismatch_fails_deterministically(tmp_path: Path):
    config = deepcopy(_load_config())
    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    uso_path = evidence_root / _record(config, "USO")["required_evidence_file"]
    uso_path.write_text("changed", encoding="utf-8")
    with pytest.raises(
        GMA6BPortabilityError, match="gma6b_evidence_checksum_mismatch:USO"
    ):
        resolve_evidence_files(config, evidence_root)
    assert config_path.is_file()


def test_outputs_are_written_only_below_injected_root(tmp_path: Path):
    result, output_root = _prepared_run(tmp_path)
    expected = {
        "gma6b_commodity_pool_structure_review_v1.csv",
        "gma6b_commodity_pool_structure_review_v1.md",
        "gma6b_commodity_pool_source_manifest_v1.csv",
    }
    assert result.overlay_status == OVERLAY_BOTH_DOCUMENTED
    assert {path.name for path in output_root.iterdir()} == expected
    assert all(path.is_file() for path in output_root.iterdir())
    assert not (tmp_path / "reports").exists()


def test_uso_and_dba_must_both_be_present(tmp_path: Path):
    config = _load_config()
    config["review_records"] = [
        row for row in config["review_records"] if row["ticker"] == "USO"
    ]
    with pytest.raises(ValueError, match="exactly USO and DBA"):
        validate_structure_review_contract(config)


def test_default_review_documents_both_tickers(tmp_path: Path):
    result, _ = _prepared_run(tmp_path)
    assert [row["ticker"] for row in result.rows] == REQUIRED_TICKERS
    assert result.overlay_status == OVERLAY_BOTH_DOCUMENTED
    assert all(
        row["later_research_execution_eligibility"] == ELIGIBLE
        for row in result.rows
    )


def test_non_primary_source_fails_review(tmp_path: Path):
    config = _load_config()
    _record(config, "USO")["official_source_type"] = "finance_portal"
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["structure_review_status"] == BLOCKED_STATUS
    assert "official_primary_source_missing_or_invalid" in uso["blocking_reason"]


def test_missing_roll_contract_management_fails_closed(tmp_path: Path):
    config = _load_config()
    _record(config, "DBA")["roll_or_contract_management_description"] = ""
    result, _ = _prepared_run(tmp_path, config)
    dba = next(row for row in result.rows if row["ticker"] == "DBA")
    assert dba["structure_review_status"] == BLOCKED_STATUS
    assert "missing_roll_or_contract_management_description" in dba["blocking_reason"]


def test_spot_proxy_wording_fails_validation(tmp_path: Path):
    config = _load_config()
    dba = _record(config, "DBA")
    dba["spot_proxy_claim_permitted"] = True
    dba["adjusted_price_interpretation"] = (
        "GMA-6 treats DBA adjusted prices as a spot proxy."
    )
    result, _ = _prepared_run(tmp_path, config)
    dba_row = next(row for row in result.rows if row["ticker"] == "DBA")
    assert dba_row["structure_review_status"] == BLOCKED_STATUS
    assert "spot_proxy_claim_not_permitted" in dba_row["blocking_reason"]


def test_eligible_status_requires_total_return_interpretation(tmp_path: Path):
    config = _load_config()
    _record(config, "USO")["traded_etp_total_return_interpretation"] = False
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["structure_review_status"] == BLOCKED_STATUS
    assert (
        "traded_etp_total_return_interpretation_required"
        in uso["blocking_reason"]
    )


def test_eligible_status_requires_spot_proxy_false(tmp_path: Path):
    config = _load_config()
    _record(config, "USO")["spot_proxy_claim_permitted"] = True
    result, _ = _prepared_run(tmp_path, config)
    uso = next(row for row in result.rows if row["ticker"] == "USO")
    assert uso["structure_review_status"] == BLOCKED_STATUS
    assert "spot_proxy_claim_not_permitted" in uso["blocking_reason"]


def test_repeated_generation_is_deterministic(tmp_path: Path):
    config = deepcopy(_load_config())
    evidence_root = _prepare_evidence(tmp_path, config)
    config_path = _write_config(tmp_path, config)
    output_root = tmp_path / "outputs"
    first = run_structure_review(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    first_outputs = {
        path.name: path.read_bytes() for path in sorted(output_root.iterdir())
    }
    second = run_structure_review(
        config_path,
        evidence_root=evidence_root,
        output_root=output_root,
    )
    second_outputs = {
        path.name: path.read_bytes() for path in sorted(output_root.iterdir())
    }
    assert first == second
    assert first_outputs == second_outputs


def test_production_module_has_no_cwd_output_or_hidden_input_discovery():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
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
    assert not {"REPORT_CSV", "REPORT_MD", "SOURCE_MANIFEST_CSV"} & assigned_names
    assert not {"os", "glob", "requests", "urllib"} & imported_modules
    blocked_calls = {
        "expand" + "user",
        "ho" + "me",
        "r" + "glob",
        "glob",
        "get" + "env",
    }
    assert not blocked_calls & called_attributes


def test_run_attempts_no_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import socket

    def fail_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", fail_network)
    result, _ = _prepared_run(tmp_path)
    assert result.overlay_status == OVERLAY_BOTH_DOCUMENTED
