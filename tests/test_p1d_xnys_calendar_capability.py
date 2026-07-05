from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import types
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset import p1d_xnys_calendar_capability as p1d


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_p1_fixture(repo: Path) -> None:
    p1a_contract = {
        "strategy_id": p1d.STRATEGY_ID,
        "parent_execution_reference": p1d.PARENT_EXECUTION_REFERENCE,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "gma7_dependency": "none",
    }
    p1b_contract = {
        "strategy_id": p1d.STRATEGY_ID,
        "parent_execution_reference": p1d.PARENT_EXECUTION_REFERENCE,
    }
    p1c_contract = {
        "strategy_id": p1d.STRATEGY_ID,
        "parent_execution_reference": p1d.PARENT_EXECUTION_REFERENCE,
        "p1c_minimum_required_snapshot_sessions": 253,
    }
    _write_text(repo / p1d.P1_INPUTS["p1a_contract"], yaml.safe_dump(p1a_contract))
    _write_text(repo / p1d.P1_INPUTS["p1b_contract"], yaml.safe_dump(p1b_contract))
    _write_text(repo / p1d.P1_INPUTS["p1c_contract"], yaml.safe_dump(p1c_contract))
    _write_csv(repo / p1d.P1_INPUTS["p1a_ledger"], [], p1d.LEDGER_FIELDS)
    _write_csv(repo / p1d.P1_INPUTS["p1a_session_template"], [], p1d.LEDGER_FIELDS)
    _write_json(
        repo / p1d.P1_INPUTS["p1a_lock"],
        {
            "strategy_id": p1d.STRATEGY_ID,
            "parent_execution_reference": p1d.PARENT_EXECUTION_REFERENCE,
            "paper_mode": "manual_observation_only",
            "real_money": "prohibited",
            "broker_connection": "prohibited",
            "trade_execution": "prohibited",
            "automated_order_generation": "prohibited",
            "gma7_dependency": "none",
            "ledger_row_count": 0,
        },
    )
    _write_json(
        repo / p1d.P1_INPUTS["p1b_dry_run"],
        {
            "strategy_id": p1d.STRATEGY_ID,
            "preflight_dry_run_status": "not_run_missing_preconditions",
            "paper_session_created": False,
            "manual_paper_ledger_modified": False,
        },
    )
    _write_json(
        repo / p1d.P1_INPUTS["p1b_lock"],
        {
            "strategy_id": p1d.STRATEGY_ID,
            "preflight_dry_run_status": "not_run_missing_preconditions",
            "paper_session_created": False,
            "manual_paper_ledger_modified": False,
        },
    )
    _write_json(repo / p1d.P1_INPUTS["p1c_execution_manifest"], {"phase_id": "p1c"})
    _write_json(
        repo / p1d.P1_INPUTS["p1c_lock"],
        {
            "strategy_id": p1d.STRATEGY_ID,
            "p1c_template_only_dry_run_status": "not_run_no_manual_snapshot_or_manifest",
            "p1c_minimum_required_snapshot_sessions": 253,
            "manual_snapshot_validated": False,
        },
    )
    _write_csv(
        repo / p1d.P1_INPUTS["p1c_history_registry"],
        [
            {
                "requirement_id": "absolute_trend_12m_equal_weight",
                "minimum_required_snapshot_sessions": 253,
            }
        ],
        ["requirement_id", "minimum_required_snapshot_sessions"],
    )


def _wheel(filename: str = "exchange_calendars-4.11.3-py3-none-any.whl") -> p1d.WheelRecord:
    return p1d.WheelRecord(
        filename=filename,
        sha256="a" * 64,
        size_bytes=123,
        package_name="exchange_calendars",
        package_version="4.11.3",
    )


def _dependency(root: Path) -> p1d.DependencyRecord:
    wheel = _wheel()
    return p1d.DependencyRecord(
        package_name="exchange_calendars",
        package_version="4.11.3",
        calendar_identifier="XNYS",
        wheel_filename=wheel.filename,
        wheel_sha256=wheel.sha256,
        wheel_size_bytes=wheel.size_bytes,
        dependency_root_path=str(root),
        wheels_path=str(root / "wheels"),
        site_packages_path=str(root / "site_packages"),
        python_executable_path="python.exe",
        python_version="3.11.9",
        wheel_inventory=[wheel],
    )


def _probe() -> dict[str, object]:
    return {
        "calendar_identifier": "XNYS",
        "calendar_dependency_status": "local_external_dependency_frozen",
        "calendar_api_available": True,
        "session_validation_capability_available": True,
        "approximate_weekday_logic_used": False,
        "base_project_venv_modified": False,
        "synthetic_probe_start": "2024-01-02",
        "synthetic_probe_end": "2024-01-05",
        "synthetic_probe_session_count": 4,
    }


def test_p1a_p1b_p1c_parent_locks_and_boundaries_are_verified(tmp_path: Path):
    _write_p1_fixture(tmp_path)

    loaded = p1d.load_p1_inputs(tmp_path)

    assert loaded.p1a_lock["strategy_id"] == p1d.STRATEGY_ID
    assert loaded.p1b_dry_run["preflight_dry_run_status"] == "not_run_missing_preconditions"
    assert loaded.p1c_lock["p1c_minimum_required_snapshot_sessions"] == 253


def test_p1a_ledger_and_session_template_remain_zero_row_and_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    dependency = _dependency(tmp_path / "dep")
    monkeypatch.setattr(p1d, "acquire_dependency", lambda *_args: dependency)
    monkeypatch.setattr(p1d, "probe_xnys_calendar", lambda *_args: _probe())
    ledger = tmp_path / p1d.P1_INPUTS["p1a_ledger"]
    template = tmp_path / p1d.P1_INPUTS["p1a_session_template"]
    before = (_sha256(ledger), _sha256(template))

    p1d.generate_p1d_files(tmp_path, tmp_path / "dep")

    assert (_sha256(ledger), _sha256(template)) == before
    assert list(csv.DictReader(ledger.open("r", encoding="utf-8"))) == []
    assert list(csv.DictReader(template.open("r", encoding="utf-8"))) == []


def test_capability_resolves_only_xnys_identifier(tmp_path: Path):
    dependency = _dependency(tmp_path / "dep")
    payload = p1d.dependency_payload(dependency)

    assert payload["calendar_identifier"] == "XNYS"


def test_unavailable_exchange_calendars_import_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fail_import(_name: str) -> object:
        raise ImportError("missing")

    monkeypatch.setattr(p1d.importlib, "import_module", fail_import)

    with pytest.raises(p1d.P1DCalendarCapabilityError, match="import failed"):
        p1d.probe_xnys_calendar(tmp_path)


def test_missing_xnys_calendar_identifier_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_module = types.SimpleNamespace(
        get_calendar=lambda _name: (_ for _ in ()).throw(KeyError())
    )
    monkeypatch.setattr(p1d.importlib, "import_module", lambda _name: fake_module)

    with pytest.raises(p1d.P1DCalendarCapabilityError, match="XNYS calendar"):
        p1d.probe_xnys_calendar(tmp_path)


def test_wheel_hash_mismatch_fails_closed(tmp_path: Path):
    actual = _dependency(tmp_path / "dep")
    expected = _dependency(tmp_path / "dep")
    expected = p1d.DependencyRecord(**{**expected.__dict__, "wheel_sha256": "b" * 64})

    with pytest.raises(p1d.P1DCalendarCapabilityError, match="wheel_sha256"):
        p1d.verify_dependency_lock(actual, expected)


def test_package_version_mismatch_fails_closed(tmp_path: Path):
    actual = _dependency(tmp_path / "dep")
    expected = p1d.DependencyRecord(**{**actual.__dict__, "package_version": "4.0.0"})

    with pytest.raises(p1d.P1DCalendarCapabilityError, match="package_version"):
        p1d.verify_dependency_lock(actual, expected)


def test_weekday_approximation_is_never_marked_used(tmp_path: Path):
    dependency = _dependency(tmp_path / "dep")
    probe = p1d.build_probe_payload(dependency, _probe())

    assert probe["approximate_weekday_logic_used"] is False


def test_shared_project_venv_install_target_fails_closed():
    with pytest.raises(p1d.P1DCalendarCapabilityError, match="shared_project_venv"):
        p1d.ensure_external_dependency_target(p1d.SHARED_VENV_ROOT / "p1d")


def test_no_price_snapshot_target_performance_order_or_broker_logic_is_present():
    source = Path(p1d.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    assert calls.isdisjoint(
        {
            "calculate_signal",
            "calculate_weights",
            "calculate_targets",
            "calculate_returns",
            "calculate_performance",
            "generate_order",
            "create_broker_instruction",
        }
    )


def test_no_recursive_traversal_globbing_or_directory_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_p1_fixture(tmp_path)
    dependency = _dependency(tmp_path / "dep")
    monkeypatch.setattr(p1d, "acquire_dependency", lambda *_args: dependency)
    monkeypatch.setattr(p1d, "probe_xnys_calendar", lambda *_args: _probe())

    def fail_recursive(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("recursive traversal is prohibited")

    monkeypatch.setattr(Path, "rglob", fail_recursive)
    monkeypatch.setattr(Path, "glob", fail_recursive)
    monkeypatch.setattr(os, "walk", fail_recursive)

    p1d.generate_p1d_files(tmp_path, tmp_path / "dep")
    with pytest.raises(p1d.P1DCalendarCapabilityError, match="Refusing to hash a directory"):
        p1d.sha256_file(tmp_path)


def test_real_probe_payload_reports_exact_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dependency = _dependency(tmp_path / "dep")
    probe = p1d.build_probe_payload(dependency, _probe())

    assert probe["calendar_identifier"] == "XNYS"
    assert probe["calendar_dependency_status"] == "local_external_dependency_frozen"
    assert probe["calendar_api_available"] is True
    assert probe["session_validation_capability_available"] is True
    assert probe["base_project_venv_modified"] is False


def test_generation_is_deterministic_after_dependency_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_p1_fixture(first)
    _write_p1_fixture(second)

    monkeypatch.setattr(p1d, "acquire_dependency", lambda _root, *_args: _dependency(_root))
    monkeypatch.setattr(p1d, "probe_xnys_calendar", lambda *_args: _probe())

    p1d.generate_p1d_files(first, tmp_path / "dep")
    p1d.generate_p1d_files(second, tmp_path / "dep")

    for key, relative_path in p1d.OUTPUT_PATHS.items():
        assert (first / relative_path).read_text(encoding="utf-8") == (
            second / relative_path
        ).read_text(encoding="utf-8"), key
