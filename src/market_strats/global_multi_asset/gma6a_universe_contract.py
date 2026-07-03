"""Design-only GMA-6A expanded ETF universe contract validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

UNIVERSE_VERSION = "gma6a_expanded_etf_universe_v1"
PARENT_GMA4_COMMIT = "86a49fc"
GMA5_V1_EVIDENCE_BUNDLE_ID = "gma5_v1_evidence_snapshot_20260623"
GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE = (
    "gma5_v1_evidence_snapshot_manifest_v1.csv"
)
GMA5_V1_REQUIRED_EVIDENCE_FILES = [GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE]
GMA5_V1_EVIDENCE_ROOT_POLICY = (
    "must_be_supplied_explicitly_for_artifact_validation"
)
GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_SHA256 = (
    "7cd1f1cec9a4bf20a4dad756041efc1a70ba8a7482665af1d23d84178465cf0c"
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = (
    PROJECT_ROOT
    / "configs/global_multi_asset_alpha/gma6a_expanded_etf_universe_v1.yaml"
)
REPORT_CSV_PATH = (
    PROJECT_ROOT
    / "reports/global_multi_asset_alpha/gma6a_expanded_etf_universe_design_v1.csv"
)
REPORT_MD_PATH = (
    PROJECT_ROOT
    / "reports/global_multi_asset_alpha/gma6a_expanded_etf_universe_design_v1.md"
)

FROZEN_CORE_V1_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
    "BIL",
    "IEF",
    "TLT",
    "AGG",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
]
FIXED_GMA6A_ADDITIONS = ["VNQ", "TIP", "USO", "DBA", "SLV", "EWG", "EWJ"]
REQUIRED_DATA_GATES = [
    "adjusted-price availability",
    "corporate-action handling",
    "coverage from 2007-05-30 through the later frozen end date",
    "no silent ticker substitution",
    "no silent start-date shortening",
    "cash/accrual compatibility",
    "documented handling for ETP/commodity-pool structure",
]
INSTRUMENT_FIELDS = [
    "ticker",
    "universe_version",
    "core_or_addition",
    "asset_cluster",
    "economic_role",
    "structure_note",
    "overlap_note",
    "data_eligibility_requirement",
    "execution_assumption_note",
]


@dataclass(frozen=True)
class GMA6AUniverseContract:
    path: Path
    raw: dict[str, Any]
    instruments: list[dict[str, str]]


class GMA6AEvidenceError(ValueError):
    """Raised when explicitly requested evidence validation cannot proceed."""


def load_gma6a_universe_contract(path: str | Path = CONFIG_PATH) -> GMA6AUniverseContract:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA-6A universe config must be a mapping")
    instruments = raw.get("instruments")
    if not isinstance(instruments, list):
        raise ValueError("instruments must be a list")
    typed = [{key: str(value) for key, value in row.items()} for row in instruments]
    return GMA6AUniverseContract(path=config_path, raw=raw, instruments=typed)


def _require_exact_list(name: str, actual: list[str], expected: list[str]) -> None:
    if actual != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def validate_gma6a_universe_contract(contract: GMA6AUniverseContract) -> None:
    metadata = contract.raw.get("contract") or {}
    core = [str(item) for item in contract.raw.get("frozen_core_v1_universe") or []]
    additions = [str(item) for item in contract.raw.get("fixed_additions") or []]
    instruments = contract.instruments
    if metadata.get("universe_version") != UNIVERSE_VERSION:
        raise ValueError("universe_version must remain frozen")
    if metadata.get("design_only") is not True:
        raise ValueError("GMA-6A contract must remain design-only")
    if metadata.get("parent_gma4_commit") != PARENT_GMA4_COMMIT:
        raise ValueError("parent_gma4_commit is missing or changed")
    if metadata.get("gma5_v1_evidence_bundle_id") != GMA5_V1_EVIDENCE_BUNDLE_ID:
        raise ValueError("GMA-5 evidence bundle identity is missing or changed")
    if (
        metadata.get("gma5_v1_evidence_snapshot_manifest_file")
        != GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_FILE
    ):
        raise ValueError("GMA-5 evidence manifest filename is missing or changed")
    _require_exact_list(
        "gma5_v1_required_evidence_files",
        [str(item) for item in metadata.get("gma5_v1_required_evidence_files") or []],
        GMA5_V1_REQUIRED_EVIDENCE_FILES,
    )
    if metadata.get("gma5_v1_evidence_root_policy") != GMA5_V1_EVIDENCE_ROOT_POLICY:
        raise ValueError("GMA-5 evidence root policy is missing or changed")
    if "gma5_v1_evidence_snapshot_root" in metadata:
        raise ValueError("GMA-5 evidence root must not be stored in the contract")
    if (
        metadata.get("gma5_v1_evidence_snapshot_manifest_sha256")
        != GMA5_V1_EVIDENCE_SNAPSHOT_MANIFEST_SHA256
    ):
        raise ValueError("GMA-5 evidence snapshot manifest hash is missing or changed")
    if metadata.get("data_failure_status") != "blocked_data_contract_failure":
        raise ValueError("data failures must block later execution")
    if metadata.get("no_automatic_fallback_allowed") is not True:
        raise ValueError("automatic fallback must remain prohibited")
    if metadata.get("performance_results_included") is not False:
        raise ValueError("GMA-6A must not contain performance results")
    if metadata.get("decision_scope") != "no execution or promotion decision is produced":
        raise ValueError("decision scope wording is missing")
    if metadata.get("evidence_class") != "observed development evidence":
        raise ValueError("evidence language is missing")
    if metadata.get("holdout_status") != "not a pristine final holdout":
        raise ValueError("holdout language is missing")
    _require_exact_list("frozen_core_v1_universe", core, FROZEN_CORE_V1_UNIVERSE)
    _require_exact_list("fixed_additions", additions, FIXED_GMA6A_ADDITIONS)
    if set(core) & set(additions):
        raise ValueError("core and addition tickers must not overlap")
    tickers = [row.get("ticker", "") for row in instruments]
    if len(tickers) != 29:
        raise ValueError("GMA-6A must contain exactly 29 instruments")
    if len(set(tickers)) != 29:
        raise ValueError("GMA-6A instrument tickers must be unique")
    _require_exact_list("instrument ticker order", tickers, [*core, *additions])
    _require_exact_list(
        "data_eligibility_gates",
        [str(item) for item in metadata.get("data_eligibility_gates") or []],
        REQUIRED_DATA_GATES,
    )
    for row in instruments:
        missing = [field for field in INSTRUMENT_FIELDS if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"{row.get('ticker')} missing fields: {missing}")
        if row["universe_version"] != UNIVERSE_VERSION:
            raise ValueError(f"{row['ticker']} has wrong universe version")
    by_ticker = {row["ticker"]: row for row in instruments}
    if "commodity-roll/carry review" not in by_ticker["USO"]["structure_note"]:
        raise ValueError("USO must require commodity-roll/carry review")
    if "commodity-roll/carry review" not in by_ticker["DBA"]["structure_note"]:
        raise ValueError("DBA must require commodity-roll/carry review")
    if "EFA" not in by_ticker["EWG"]["overlap_note"]:
        raise ValueError("EWG must document EFA overlap")
    if "EFA" not in by_ticker["EWJ"]["overlap_note"]:
        raise ValueError("EWJ must document EFA overlap")
    if "broad equity exposure" not in by_ticker["VNQ"]["overlap_note"]:
        raise ValueError("VNQ must document broad equity overlap")
    for row in instruments[22:]:
        if row["core_or_addition"] != "addition":
            raise ValueError(f"{row['ticker']} must be marked as addition")
        if "no replacement if coverage fails" not in row["data_eligibility_requirement"]:
            raise ValueError(f"{row['ticker']} must fail closed on coverage failure")


def resolve_gma6a_evidence_files(
    contract: GMA6AUniverseContract,
    evidence_root: str | Path | None,
) -> dict[str, Path]:
    """Resolve required evidence only beneath an explicitly supplied root."""
    validate_gma6a_universe_contract(contract)
    if evidence_root is None:
        raise GMA6AEvidenceError("gma6a_evidence_root_required")
    root = Path(evidence_root)
    if not root.is_absolute():
        raise GMA6AEvidenceError("gma6a_evidence_root_must_be_absolute")
    required = contract.raw["contract"]["gma5_v1_required_evidence_files"]
    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for name in required:
        relative = Path(str(name))
        if relative.is_absolute() or ".." in relative.parts:
            raise GMA6AEvidenceError("gma6a_evidence_filename_must_be_relative")
        path = root / relative
        resolved[str(name)] = path
        if not path.is_file():
            missing.append(str(name))
    if missing:
        raise GMA6AEvidenceError(
            "gma6a_required_evidence_missing:" + ",".join(sorted(missing))
        )
    return resolved


def validate_gma6a_evidence_bundle(
    contract: GMA6AUniverseContract,
    evidence_root: str | Path | None,
) -> dict[str, Path]:
    """Validate the frozen manifest identity within an injected evidence root."""
    resolved = resolve_gma6a_evidence_files(contract, evidence_root)
    metadata = contract.raw["contract"]
    manifest_name = str(metadata["gma5_v1_evidence_snapshot_manifest_file"])
    digest = hashlib.sha256(resolved[manifest_name].read_bytes()).hexdigest()
    if digest != metadata["gma5_v1_evidence_snapshot_manifest_sha256"]:
        raise GMA6AEvidenceError("gma6a_evidence_manifest_hash_mismatch")
    return resolved


def instrument_rows(contract: GMA6AUniverseContract) -> list[dict[str, str]]:
    validate_gma6a_universe_contract(contract)
    return [{field: row[field] for field in INSTRUMENT_FIELDS} for row in contract.instruments]


def write_design_csv(rows: list[dict[str, str]], path: Path = REPORT_CSV_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INSTRUMENT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def build_design_markdown(contract: GMA6AUniverseContract) -> str:
    validate_gma6a_universe_contract(contract)
    metadata = contract.raw["contract"]
    rows = instrument_rows(contract)
    table_rows = [
        [
            row["ticker"],
            row["core_or_addition"],
            row["asset_cluster"],
            row["economic_role"],
            row["overlap_note"],
        ]
        for row in rows
    ]
    gates = "\n".join(f"- {gate}" for gate in metadata["data_eligibility_gates"])
    return "\n".join(
        [
            "# GMA-6A Expanded ETF Universe Contract v1",
            "",
            "GMA-6A is a design-only expanded-universe contract. GMA-4/GMA-5 V1 remain unchanged.",
            "GMA-6A has no performance results. This record is observed development evidence, not a pristine final holdout, and no execution or promotion decision is produced.",
            "Any later universe alteration requires a new version.",
            "",
            "## Parent References",
            "",
            f"- parent_gma4_commit: {metadata['parent_gma4_commit']}",
            f"- gma5_v1_evidence_bundle_id: {metadata['gma5_v1_evidence_bundle_id']}",
            "- gma5_v1_evidence_root: supplied explicitly for artifact validation",
            "- gma5_v1_required_evidence_files: "
            + ", ".join(metadata["gma5_v1_required_evidence_files"]),
            f"- gma5_v1_evidence_snapshot_manifest_sha256: {metadata['gma5_v1_evidence_snapshot_manifest_sha256']}",
            "",
            "## Data Eligibility Gates",
            "",
            gates,
            "",
            "If any instrument fails these gates, later GMA-6 execution is labelled blocked_data_contract_failure. No automatic fallback, ticker replacement, or start-date shortening is allowed.",
            "USO and DBA require commodity-roll/carry review before any later execution phase. EWG and EWJ overlap economically with EFA. VNQ overlaps with broad equity exposure. These additions are not represented as improving returns or diversification.",
            "",
            "## Universe Table",
            "",
            markdown_table(
                ["ticker", "core_or_addition", "asset_cluster", "economic_role", "overlap_note"],
                table_rows,
            ),
            "",
        ]
    )


def write_design_markdown(contract: GMA6AUniverseContract, path: Path = REPORT_MD_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_design_markdown(contract), encoding="utf-8")


def write_design_outputs(
    config_path: Path = CONFIG_PATH,
    csv_path: Path = REPORT_CSV_PATH,
    md_path: Path = REPORT_MD_PATH,
) -> None:
    contract = load_gma6a_universe_contract(config_path)
    rows = instrument_rows(contract)
    write_design_csv(rows, csv_path)
    write_design_markdown(contract, md_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and render the GMA-6A universe contract."
    )
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--csv", default=str(REPORT_CSV_PATH))
    parser.add_argument("--markdown", default=str(REPORT_MD_PATH))
    parser.add_argument("--evidence-root")
    parser.add_argument("--validate-evidence", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = load_gma6a_universe_contract(Path(args.config))
    validate_gma6a_universe_contract(contract)
    if args.validate_evidence:
        validate_gma6a_evidence_bundle(contract, args.evidence_root)
    write_design_outputs(Path(args.config), Path(args.csv), Path(args.markdown))


if __name__ == "__main__":
    main()
