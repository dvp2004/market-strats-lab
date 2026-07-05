from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PHASE_ID = "p1d_xnys_calendar_capability_v1"
STRATEGY_ID = "gma5_equal_weight_atomic_sleeves_v1"
PARENT_EXECUTION_REFERENCE = "gma5_clean_execution_20260622T075912Z_v1"
PACKAGE_NAME = "exchange_calendars"
CALENDAR_IDENTIFIER = "XNYS"
DEPENDENCY_ROOT = Path(
    "C:/Users/Devesh Pansare/Desktop/Personal_Projects/p1_xnys_calendar_dependency_v1"
)
SHARED_VENV_ROOT = Path("C:/Users/Devesh Pansare/Desktop/Personal_Projects/Market-strats-lab/.venv")
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/p1d_xnys_calendar_capability_v1")

REQUIRED_LANGUAGE = [
    "P-1D freezes an isolated local XNYS calendar capability for future P-1 snapshot validation.",
    "No actual market-price snapshot or manual intake manifest was supplied.",
    "No signal, sleeve weight, ETF target, paper decision, paper session, performance result, broker instruction, or real-money action is produced.",
    "The shared project virtual environment was not modified.",
    "P-1 remains a separate manual-paper observation programme for the frozen GMA-5 equal-weight atomic sleeve portfolio.",
]

P1_INPUTS = {
    "p1a_contract": Path("configs/global_multi_asset_alpha/p1a_manual_paper_contract_v1.yaml"),
    "p1b_contract": Path(
        "configs/global_multi_asset_alpha/p1b_manual_data_intake_preflight_contract_v1.yaml"
    ),
    "p1c_contract": Path(
        "configs/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_contract_v1.yaml"
    ),
    "p1a_lock": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/p1a_manual_paper_lock_v1.json"
    ),
    "p1a_ledger": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_manual_paper_ledger_v1.csv"
    ),
    "p1a_session_template": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_manual_paper_session_template_v1.csv"
    ),
    "p1b_dry_run": Path(
        "reports/global_multi_asset_alpha/p1b_manual_data_intake_preflight_v1/"
        "p1b_preflight_dry_run_v1.json"
    ),
    "p1b_lock": Path(
        "reports/global_multi_asset_alpha/p1b_manual_data_intake_preflight_v1/"
        "p1b_preflight_lock_v1.json"
    ),
    "p1c_execution_manifest": Path(
        "reports/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_v1/"
        "p1c_execution_manifest_v1.json"
    ),
    "p1c_lock": Path(
        "reports/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_v1/"
        "p1c_local_snapshot_lock_v1.json"
    ),
    "p1c_history_registry": Path(
        "reports/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_v1/"
        "p1c_required_history_registry_v1.csv"
    ),
}

OUTPUT_PATHS = {
    "contract": Path(
        "configs/global_multi_asset_alpha/p1d_xnys_calendar_capability_contract_v1.yaml"
    ),
    "docs": Path("docs/global_multi_asset_alpha/p1d_xnys_calendar_capability_contract_v1.md"),
    "dependency_manifest": OUTPUT_DIR / "p1d_xnys_calendar_dependency_manifest_v1.json",
    "probe_json": OUTPUT_DIR / "p1d_xnys_calendar_probe_v1.json",
    "probe_md": OUTPUT_DIR / "p1d_xnys_calendar_probe_v1.md",
    "wheel_inventory": OUTPUT_DIR / "p1d_xnys_calendar_wheel_inventory_v1.csv",
    "execution_manifest": OUTPUT_DIR / "p1d_execution_manifest_v1.json",
    "lock": OUTPUT_DIR / "p1d_xnys_calendar_lock_v1.json",
}

LEDGER_FIELDS = [
    "session_id",
    "scheduled_decision_session_date",
    "actual_decision_timestamp_utc",
    "data_cutoff_timestamp_utc",
    "source_last_observed_session",
    "session_data_snapshot_path",
    "session_data_snapshot_sha256",
    "parent_strategy_id",
    "parent_execution_reference",
    "parent_reference_manifest_sha256",
    "manual_preflight_validation_status",
    "manual_decision",
    "manual_decision_reason",
    "target_file_sha256",
    "target_row_count",
    "target_weight_sum",
    "execution_status",
    "paper_session_status",
    "warning_flags",
    "operator_notes",
    "ledger_created_timestamp_utc",
]


class P1DCalendarCapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class P1Inputs:
    p1a_contract: dict[str, Any]
    p1b_contract: dict[str, Any]
    p1c_contract: dict[str, Any]
    p1a_lock: dict[str, Any]
    p1b_dry_run: dict[str, Any]
    p1b_lock: dict[str, Any]
    p1c_execution_manifest: dict[str, Any]
    p1c_lock: dict[str, Any]
    input_hashes: dict[str, str]


@dataclass(frozen=True)
class WheelRecord:
    filename: str
    sha256: str
    size_bytes: int
    package_name: str
    package_version: str


@dataclass(frozen=True)
class DependencyRecord:
    package_name: str
    package_version: str
    calendar_identifier: str
    wheel_filename: str
    wheel_sha256: str
    wheel_size_bytes: int
    dependency_root_path: str
    wheels_path: str
    site_packages_path: str
    python_executable_path: str
    python_version: str
    wheel_inventory: list[WheelRecord]


def sha256_file(path: Path) -> str:
    if path.is_dir():
        raise P1DCalendarCapabilityError(f"Refusing to hash a directory: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1DCalendarCapabilityError(f"Expected JSON object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1DCalendarCapabilityError(f"Expected YAML object: {path}")
    return payload


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise P1DCalendarCapabilityError(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def load_p1_inputs(repo_root: Path) -> P1Inputs:
    paths = {name: repo_root / relative for name, relative in P1_INPUTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise P1DCalendarCapabilityError("Missing required P-1 input(s): " + ", ".join(missing))
    hashes = {name: sha256_file(path) for name, path in paths.items()}
    ledger_fields, ledger_rows = _read_csv(paths["p1a_ledger"])
    template_fields, template_rows = _read_csv(paths["p1a_session_template"])
    _require_equal("p1a_ledger_fields", ledger_fields, LEDGER_FIELDS)
    _require_equal("p1a_session_template_fields", template_fields, LEDGER_FIELDS)
    _require_equal("p1a_ledger_row_count", len(ledger_rows), 0)
    _require_equal("p1a_session_template_row_count", len(template_rows), 0)
    p1 = P1Inputs(
        p1a_contract=_read_yaml(paths["p1a_contract"]),
        p1b_contract=_read_yaml(paths["p1b_contract"]),
        p1c_contract=_read_yaml(paths["p1c_contract"]),
        p1a_lock=_read_json(paths["p1a_lock"]),
        p1b_dry_run=_read_json(paths["p1b_dry_run"]),
        p1b_lock=_read_json(paths["p1b_lock"]),
        p1c_execution_manifest=_read_json(paths["p1c_execution_manifest"]),
        p1c_lock=_read_json(paths["p1c_lock"]),
        input_hashes=hashes,
    )
    verify_p1_boundaries(p1)
    return p1


def verify_p1_boundaries(p1: P1Inputs) -> None:
    for name, payload in (
        ("p1a_contract", p1.p1a_contract),
        ("p1b_contract", p1.p1b_contract),
        ("p1c_contract", p1.p1c_contract),
        ("p1a_lock", p1.p1a_lock),
    ):
        _require_equal(f"{name}.strategy_id", payload.get("strategy_id"), STRATEGY_ID)
    for name, payload in (("p1a_contract", p1.p1a_contract), ("p1a_lock", p1.p1a_lock)):
        _require_equal(f"{name}.paper_mode", payload.get("paper_mode"), "manual_observation_only")
        _require_equal(f"{name}.real_money", payload.get("real_money"), "prohibited")
        _require_equal(f"{name}.broker_connection", payload.get("broker_connection"), "prohibited")
        _require_equal(f"{name}.trade_execution", payload.get("trade_execution"), "prohibited")
        _require_equal(
            f"{name}.automated_order_generation",
            payload.get("automated_order_generation"),
            "prohibited",
        )
        _require_equal(f"{name}.gma7_dependency", payload.get("gma7_dependency"), "none")
    _require_equal("p1a_lock.ledger_row_count", p1.p1a_lock.get("ledger_row_count"), 0)
    _require_equal(
        "p1b_preflight_dry_run_status",
        p1.p1b_dry_run.get("preflight_dry_run_status"),
        "not_run_missing_preconditions",
    )
    _require_equal("p1b_paper_session_created", p1.p1b_dry_run.get("paper_session_created"), False)
    _require_equal(
        "p1b_manual_paper_ledger_modified",
        p1.p1b_dry_run.get("manual_paper_ledger_modified"),
        False,
    )
    _require_equal(
        "p1c_template_only_dry_run_status",
        p1.p1c_lock.get("p1c_template_only_dry_run_status"),
        "not_run_no_manual_snapshot_or_manifest",
    )
    _require_equal(
        "p1c_minimum_required_snapshot_sessions",
        p1.p1c_lock.get("p1c_minimum_required_snapshot_sessions"),
        253,
    )
    _require_equal(
        "p1c_manual_snapshot_validated", p1.p1c_lock.get("manual_snapshot_validated"), False
    )


def ensure_external_dependency_target(dependency_root: Path) -> tuple[Path, Path]:
    root = dependency_root.resolve()
    shared_venv = SHARED_VENV_ROOT.resolve()
    if root == shared_venv or shared_venv in root.parents:
        raise P1DCalendarCapabilityError("shared_project_venv_install_target_prohibited")
    if dependency_root.exists():
        raise P1DCalendarCapabilityError(f"Dependency directory already exists: {dependency_root}")
    wheels = dependency_root / "wheels"
    site_packages = dependency_root / "site_packages"
    wheels.mkdir(parents=True)
    site_packages.mkdir()
    return wheels, site_packages


def download_binary_wheels(python_executable: Path, wheels_path: Path) -> None:
    subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "download",
            PACKAGE_NAME,
            "--only-binary=:all:",
            "--dest",
            str(wheels_path),
            "--no-cache-dir",
        ],
        check=True,
    )


def parse_exchange_calendar_wheel_version(filename: str) -> str | None:
    match = re.match(r"^exchange_calendars-([0-9][A-Za-z0-9_.!]*)-", filename)
    if not match:
        return None
    version = match.group(1)
    if re.search(r"(a|b|rc|dev)", version, flags=re.IGNORECASE):
        raise P1DCalendarCapabilityError("Prerelease exchange_calendars wheel is prohibited")
    return version


def inventory_wheels(wheels_path: Path) -> tuple[list[WheelRecord], WheelRecord]:
    wheel_files = sorted(
        [path for path in wheels_path.iterdir() if path.is_file() and path.suffix == ".whl"]
    )
    if not wheel_files:
        raise P1DCalendarCapabilityError("No downloaded wheels found")
    records: list[WheelRecord] = []
    exchange_records: list[WheelRecord] = []
    for path in wheel_files:
        version = parse_exchange_calendar_wheel_version(path.name)
        normalized_name = path.name.split("-")[0].replace("-", "_")
        record = WheelRecord(
            filename=path.name,
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            package_name=normalized_name,
            package_version=version or "",
        )
        records.append(record)
        if version is not None:
            exchange_records.append(record)
    if len(exchange_records) != 1:
        raise P1DCalendarCapabilityError(
            "Expected exactly one non-prerelease exchange_calendars wheel"
        )
    return records, exchange_records[0]


def install_from_local_wheels(
    python_executable: Path, wheels_path: Path, site_packages_path: Path, package_version: str
) -> None:
    subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            f"{PACKAGE_NAME}=={package_version}",
            "--no-index",
            "--find-links",
            str(wheels_path),
            "--target",
            str(site_packages_path),
            "--no-cache-dir",
        ],
        check=True,
    )


def probe_xnys_calendar(site_packages_path: Path) -> dict[str, Any]:
    site_packages = str(site_packages_path)
    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    try:
        module = importlib.import_module(PACKAGE_NAME)
    except ImportError as exc:
        raise P1DCalendarCapabilityError(
            "exchange_calendars import failed from isolated site_packages"
        ) from exc
    try:
        calendar = module.get_calendar(CALENDAR_IDENTIFIER)
    except Exception as exc:  # noqa: BLE001
        raise P1DCalendarCapabilityError("XNYS calendar identifier could not be resolved") from exc
    sessions = calendar.sessions_in_range("2024-01-02", "2024-01-05")
    if len(sessions) == 0:
        raise P1DCalendarCapabilityError("XNYS synthetic session probe returned no sessions")
    return {
        "calendar_identifier": CALENDAR_IDENTIFIER,
        "calendar_dependency_status": "local_external_dependency_frozen",
        "calendar_api_available": True,
        "session_validation_capability_available": True,
        "approximate_weekday_logic_used": False,
        "base_project_venv_modified": False,
        "synthetic_probe_start": "2024-01-02",
        "synthetic_probe_end": "2024-01-05",
        "synthetic_probe_session_count": int(len(sessions)),
    }


def acquire_dependency(
    dependency_root: Path = DEPENDENCY_ROOT,
    python_executable: Path = Path(sys.executable),
) -> DependencyRecord:
    wheels_path, site_packages_path = ensure_external_dependency_target(dependency_root)
    download_binary_wheels(python_executable, wheels_path)
    wheel_records, exchange_wheel = inventory_wheels(wheels_path)
    install_from_local_wheels(
        python_executable, wheels_path, site_packages_path, exchange_wheel.package_version
    )
    probe_xnys_calendar(site_packages_path)
    return DependencyRecord(
        package_name=PACKAGE_NAME,
        package_version=exchange_wheel.package_version,
        calendar_identifier=CALENDAR_IDENTIFIER,
        wheel_filename=exchange_wheel.filename,
        wheel_sha256=exchange_wheel.sha256,
        wheel_size_bytes=exchange_wheel.size_bytes,
        dependency_root_path=str(dependency_root),
        wheels_path=str(wheels_path),
        site_packages_path=str(site_packages_path),
        python_executable_path=str(python_executable),
        python_version=sys.version.split()[0],
        wheel_inventory=wheel_records,
    )


def verify_dependency_lock(record: DependencyRecord, expected: DependencyRecord) -> None:
    _require_equal("package_name", record.package_name, expected.package_name)
    _require_equal("package_version", record.package_version, expected.package_version)
    _require_equal("calendar_identifier", record.calendar_identifier, expected.calendar_identifier)
    _require_equal("wheel_sha256", record.wheel_sha256, expected.wheel_sha256)


def dependency_payload(record: DependencyRecord) -> dict[str, Any]:
    return {
        "package_name": record.package_name,
        "package_version": record.package_version,
        "calendar_identifier": record.calendar_identifier,
        "wheel_filename": record.wheel_filename,
        "wheel_sha256": record.wheel_sha256,
        "wheel_size_bytes": record.wheel_size_bytes,
        "dependency_root_path": record.dependency_root_path,
        "wheels_path": record.wheels_path,
        "site_packages_path": record.site_packages_path,
        "python_executable_path": record.python_executable_path,
        "python_version": record.python_version,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_contract_payload(record: DependencyRecord) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "required_language": REQUIRED_LANGUAGE,
        **dependency_payload(record),
        "future_p1e_requirement": (
            "P-1E must use this exact dependency root and fail closed if package version, "
            "calendar identifier, or wheel hash differs from the P-1D lock."
        ),
        "prohibited_actions": [
            "approximate_weekday_logic",
            "manual_holiday_rules",
            "market_data_fetch",
            "snapshot_validation",
            "target_generation",
            "sleeve_calculation",
            "ETF_target_calculation",
            "paper_decision",
            "paper_session",
            "ledger_write",
            "performance_calculation",
            "broker_instruction",
            "real_money_action",
        ],
    }


def build_probe_payload(record: DependencyRecord, site_probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        **dependency_payload(record),
        **site_probe,
        "required_language": REQUIRED_LANGUAGE,
        "actual_market_price_snapshot_supplied": False,
        "manual_intake_manifest_supplied": False,
        "target_generated": False,
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "broker_instruction_created": False,
        "real_money_action_created": False,
    }


def generate_p1d_files(
    repo_root: Path = Path.cwd(),
    dependency_root: Path = DEPENDENCY_ROOT,
    python_executable: Path = Path(sys.executable),
) -> dict[str, Any]:
    p1 = load_p1_inputs(repo_root)
    ledger_before = p1.input_hashes["p1a_ledger"]
    template_before = p1.input_hashes["p1a_session_template"]
    record = acquire_dependency(dependency_root, python_executable)
    site_probe = probe_xnys_calendar(Path(record.site_packages_path))
    dependency_manifest = {"phase_id": PHASE_ID, **dependency_payload(record)}
    probe = build_probe_payload(record, site_probe)
    write_json(repo_root / OUTPUT_PATHS["dependency_manifest"], dependency_manifest)
    write_json(repo_root / OUTPUT_PATHS["probe_json"], probe)
    write_probe_markdown(repo_root / OUTPUT_PATHS["probe_md"], probe)
    write_csv(
        repo_root / OUTPUT_PATHS["wheel_inventory"],
        [wheel.__dict__ for wheel in record.wheel_inventory],
        ["filename", "sha256", "size_bytes", "package_name", "package_version"],
    )
    contract = build_contract_payload(record)
    write_text(
        repo_root / OUTPUT_PATHS["contract"],
        yaml.safe_dump(contract, sort_keys=False),
    )
    write_docs(repo_root / OUTPUT_PATHS["docs"], record)
    generated_hashes = {
        key: sha256_file(repo_root / path)
        for key, path in OUTPUT_PATHS.items()
        if key not in {"execution_manifest", "lock"} and (repo_root / path).is_file()
    }
    execution_manifest = {
        "phase_id": PHASE_ID,
        "p1_inputs_read": {name: str(path) for name, path in P1_INPUTS.items()},
        "p1_input_hashes": p1.input_hashes,
        "generated_artifact_hashes_excluding_manifest_and_lock": generated_hashes,
        "files_hashed_count": len(p1.input_hashes)
        + len(record.wheel_inventory)
        + len(generated_hashes),
        "shared_project_virtual_environment_modified": False,
        **dependency_payload(record),
    }
    write_json(repo_root / OUTPUT_PATHS["execution_manifest"], execution_manifest)
    generated_hashes_with_manifest = {
        **generated_hashes,
        "execution_manifest": sha256_file(repo_root / OUTPUT_PATHS["execution_manifest"]),
    }
    lock = {
        "phase_id": PHASE_ID,
        **dependency_payload(record),
        "calendar_dependency_status": "local_external_dependency_frozen",
        "calendar_api_available": True,
        "session_validation_capability_available": True,
        "approximate_weekday_logic_used": False,
        "base_project_venv_modified": False,
        "target_generated": False,
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "generated_artifact_hashes_excluding_lock": generated_hashes_with_manifest,
        "generated_artifact_hash_count_excluding_lock": len(generated_hashes_with_manifest),
    }
    write_json(repo_root / OUTPUT_PATHS["lock"], lock)
    p1_after = load_p1_inputs(repo_root)
    _require_equal(
        "p1a_ledger_sha256_after_generation", p1_after.input_hashes["p1a_ledger"], ledger_before
    )
    _require_equal(
        "p1a_session_template_sha256_after_generation",
        p1_after.input_hashes["p1a_session_template"],
        template_before,
    )
    return {"dependency": dependency_payload(record), "probe": probe, "lock": lock}


def write_docs(path: Path, record: DependencyRecord) -> None:
    payload = dependency_payload(record)
    write_text(
        path,
        "\n".join(
            [
                "# P-1D XNYS Calendar Capability Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"Package: `{payload['package_name']}=={payload['package_version']}`",
                f"Calendar identifier: `{payload['calendar_identifier']}`",
                f"Dependency root: `{payload['dependency_root_path']}`",
                f"Wheel SHA-256: `{payload['wheel_sha256']}`",
                "",
            ]
        ),
    )


def write_probe_markdown(path: Path, probe: dict[str, Any]) -> None:
    write_text(
        path,
        "\n".join(
            [
                "# P-1D XNYS Calendar Capability Probe V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"- calendar_identifier: `{probe['calendar_identifier']}`",
                f"- calendar_dependency_status: `{probe['calendar_dependency_status']}`",
                f"- calendar_api_available: `{str(probe['calendar_api_available']).lower()}`",
                "- session_validation_capability_available: "
                f"`{str(probe['session_validation_capability_available']).lower()}`",
                f"- approximate_weekday_logic_used: `{str(probe['approximate_weekday_logic_used']).lower()}`",
                f"- base_project_venv_modified: `{str(probe['base_project_venv_modified']).lower()}`",
                "",
            ]
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze isolated local XNYS calendar capability")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dependency-root", type=Path, default=DEPENDENCY_ROOT)
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    result = generate_p1d_files(args.repo_root, args.dependency_root, args.python_executable)
    probe = result["probe"]
    print(f"phase_id={PHASE_ID}")
    print(f"package_name={probe['package_name']}")
    print(f"package_version={probe['package_version']}")
    print(f"calendar_identifier={probe['calendar_identifier']}")
    print(f"calendar_dependency_status={probe['calendar_dependency_status']}")
    print(f"calendar_api_available={str(probe['calendar_api_available']).lower()}")
    print(
        "session_validation_capability_available="
        f"{str(probe['session_validation_capability_available']).lower()}"
    )
    print(f"base_project_venv_modified={str(probe['base_project_venv_modified']).lower()}")
    for key, path in sorted(OUTPUT_PATHS.items()):
        print(f"{key}={args.repo_root / path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
