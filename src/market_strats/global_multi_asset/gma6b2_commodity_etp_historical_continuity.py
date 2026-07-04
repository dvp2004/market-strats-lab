"""GMA-6B.2 historical commodity-ETP methodology continuity audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

import yaml

PHASE_ID = "gma6b2_commodity_etp_historical_continuity_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = (
    PROJECT_ROOT
    / "configs/global_multi_asset_alpha/"
    "gma6b2_commodity_etp_historical_continuity_v1.yaml"
)
REQUIRED_TICKERS = ["USO", "DBA"]
PRIMARY_SOURCE_TYPES = {
    "sec_filing",
    "sec_prospectus",
    "issuer_prospectus",
    "statutory_prospectus",
    "annual_report",
    "official_issuer_product_document",
}
SOURCE_ROLES = {
    "early_window_reference",
    "material_change_reference",
    "current_structure_reference",
}
CONTINUITY_STATUSES = {
    "historical_methodology_continuity_documented",
    "material_methodology_change_documented",
    "continuity_evidence_incomplete",
}
ELIGIBILITY_VALUES = {
    "eligible_for_later_gma6_research_execution",
    "eligible_only_with_documented_methodology_regime_flags",
    "blocked_data_contract_failure",
}
OVERLAY_ELIGIBLE = "eligible_for_later_gma6_research_execution"
OVERLAY_FLAGS = "eligible_only_with_documented_methodology_regime_flags"
OVERLAY_BLOCKED = "blocked_data_contract_failure"
CONTINUITY_DOCUMENTED = "historical_methodology_continuity_documented"
MATERIAL_CHANGE = "material_methodology_change_documented"
INCOMPLETE = "continuity_evidence_incomplete"
OUTPUT_KEYS = {
    "overlay_csv",
    "overlay_markdown",
    "source_manifest_csv",
}

SOURCE_FIELDS = [
    "ticker",
    "issuer",
    "document_title",
    "document_type",
    "filing_or_publication_date",
    "effective_date_if_stated",
    "official_source_id",
    "required_evidence_file",
    "source_retrieved_at_utc",
    "source_sha256",
    "historical_window_role",
    "source_supported_summary",
]
AUDIT_FIELDS = [
    "ticker",
    "historical_window_start",
    "historical_window_end",
    "historical_continuity_status",
    "material_methodology_change_detected",
    "material_change_effective_date",
    "material_change_description",
    "historical_return_interpretation",
    "spot_proxy_claim_permitted",
    "traded_etp_total_return_interpretation",
    "later_research_execution_overlay_eligibility",
    "required_later_regime_flag",
    "blocking_reason",
]
SOURCE_REQUIRED_TEXT_FIELDS = [
    "issuer",
    "document_title",
    "document_type",
    "filing_or_publication_date",
    "official_source_id",
    "required_evidence_file",
    "source_retrieved_at_utc",
    "source_sha256",
    "historical_window_role",
    "source_supported_summary",
]
AUDIT_REQUIRED_TEXT_FIELDS = [
    "historical_window_start",
    "historical_window_end",
    "material_change_description",
    "historical_return_interpretation",
]


class GMA6B2PortabilityError(ValueError):
    """Raised when the portable evidence or output contract is violated."""


@dataclass(frozen=True)
class OutputPaths:
    overlay_csv: Path
    overlay_markdown: Path
    source_manifest_csv: Path


@dataclass(frozen=True)
class ContinuityResult:
    rows: list[dict[str, str]]
    source_manifest_rows: list[dict[str, str]]
    overlay_status: str


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GMA6B2PortabilityError("gma6b2_config_file_missing")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6B2PortabilityError("gma6b2_config_must_contain_mapping")
    return raw


def text_value(record: dict[str, Any], field: str) -> str:
    value = record.get(field, "")
    if value is None:
        return ""
    return str(value).strip()


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise ValueError(f"Expected boolean-compatible value, got {value!r}")


def _relative_path(value: Any, field: str) -> Path:
    text = str(value or "").strip()
    path = Path(text)
    pure = PurePath(text)
    if (
        not text
        or "://" in text
        or path.is_absolute()
        or path.drive
        or ".." in pure.parts
        or text.startswith(("/", "\\"))
    ):
        raise GMA6B2PortabilityError(f"gma6b2_invalid_relative_path:{field}")
    return path


def _required_absolute_root(root: Path | None, kind: str) -> Path:
    if root is None:
        raise GMA6B2PortabilityError(f"gma6b2_{kind}_root_required")
    path = Path(root)
    if not path.is_absolute():
        raise GMA6B2PortabilityError(f"gma6b2_{kind}_root_must_be_absolute")
    return path.resolve()


def _contract(config: dict[str, Any]) -> dict[str, Any]:
    contract = config.get("contract")
    if not isinstance(contract, dict):
        raise GMA6B2PortabilityError("gma6b2_contract_mapping_required")
    return contract


def _mapping_records(config: dict[str, Any], field: str) -> list[dict[str, Any]]:
    records = config.get(field)
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise GMA6B2PortabilityError(f"gma6b2_{field}_must_be_mapping_list")
    return records


def validate_ticker_set(records: list[dict[str, Any]], label: str) -> None:
    tickers = sorted({text_value(record, "ticker") for record in records})
    if tickers != sorted(REQUIRED_TICKERS):
        raise ValueError(f"GMA-6B.2 {label} must include both USO and DBA")


def validate_historical_continuity_contract(config: dict[str, Any]) -> None:
    """Validate metadata and research semantics without reading artifacts."""
    contract = _contract(config)
    if contract.get("phase_id") != PHASE_ID:
        raise GMA6B2PortabilityError("gma6b2_phase_id_mismatch")
    if (
        contract.get("evidence_root_policy")
        != "must_be_supplied_explicitly_for_artifact_validation"
    ):
        raise GMA6B2PortabilityError("gma6b2_evidence_root_policy_invalid")
    if (
        contract.get("output_root_policy")
        != "must_be_supplied_explicitly_for_output_generation"
    ):
        raise GMA6B2PortabilityError("gma6b2_output_root_policy_invalid")
    if not str(contract.get("evidence_bundle_id", "")).strip():
        raise GMA6B2PortabilityError("gma6b2_evidence_bundle_id_required")

    output_files = contract.get("output_files")
    if not isinstance(output_files, dict) or set(output_files) != OUTPUT_KEYS:
        raise GMA6B2PortabilityError("gma6b2_output_files_invalid")
    for key, value in output_files.items():
        _relative_path(value, f"output_files.{key}")

    source_rows = _mapping_records(config, "source_manifest")
    audit_records = _mapping_records(config, "audit_records")
    validate_ticker_set(source_rows, "source manifest")
    validate_ticker_set(audit_records, "audit records")
    source_ids: set[str] = set()
    for record in source_rows:
        ticker = text_value(record, "ticker")
        if "official_source_url" in record:
            raise GMA6B2PortabilityError(
                f"gma6b2_provider_url_field_not_permitted:{ticker}"
            )
        _relative_path(
            record.get("required_evidence_file"),
            f"source_manifest.{ticker}.required_evidence_file",
        )
        source_id = text_value(record, "official_source_id")
        if not source_id or "://" in source_id or source_id in source_ids:
            raise GMA6B2PortabilityError(f"gma6b2_source_id_invalid:{ticker}")
        source_ids.add(source_id)
        digest = text_value(record, "source_sha256")
        if len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise GMA6B2PortabilityError(
                f"gma6b2_source_sha256_invalid:{source_id}"
            )


def resolve_evidence_files(
    config: dict[str, Any], evidence_root: Path | None
) -> dict[str, Path]:
    validate_historical_continuity_contract(config)
    root = _required_absolute_root(evidence_root, "evidence")
    if not root.is_dir():
        raise GMA6B2PortabilityError("gma6b2_evidence_root_missing")

    resolved: dict[str, Path] = {}
    for record in _mapping_records(config, "source_manifest"):
        source_id = text_value(record, "official_source_id")
        relative = _relative_path(
            record.get("required_evidence_file"),
            f"source_manifest.{source_id}.required_evidence_file",
        )
        candidate = (root / relative).resolve()
        if root not in candidate.parents:
            raise GMA6B2PortabilityError(
                f"gma6b2_evidence_path_outside_root:{source_id}"
            )
        if not candidate.is_file():
            raise GMA6B2PortabilityError(
                f"gma6b2_required_evidence_missing:{source_id}"
            )
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != text_value(record, "source_sha256"):
            raise GMA6B2PortabilityError(
                f"gma6b2_evidence_checksum_mismatch:{source_id}"
            )
        resolved[source_id] = candidate
    return resolved


def resolve_output_paths(
    config: dict[str, Any], output_root: Path | None
) -> OutputPaths:
    validate_historical_continuity_contract(config)
    root = _required_absolute_root(output_root, "output")
    output_files = _contract(config)["output_files"]
    paths = {
        key: (root / _relative_path(value, f"output_files.{key}")).resolve()
        for key, value in output_files.items()
    }
    for key, path in paths.items():
        if root not in path.parents:
            raise GMA6B2PortabilityError(
                f"gma6b2_output_path_outside_root:{key}"
            )
    return OutputPaths(
        overlay_csv=paths["overlay_csv"],
        overlay_markdown=paths["overlay_markdown"],
        source_manifest_csv=paths["source_manifest_csv"],
    )


def source_validation_reasons(
    source_rows: list[dict[str, Any]], ticker: str
) -> list[str]:
    reasons: list[str] = []
    ticker_sources = [
        row for row in source_rows if text_value(row, "ticker") == ticker
    ]
    roles = {text_value(row, "historical_window_role") for row in ticker_sources}
    if "early_window_reference" not in roles:
        reasons.append("missing_early_window_reference")
    if "current_structure_reference" not in roles:
        reasons.append("missing_current_structure_reference")
    for row in ticker_sources:
        for field in SOURCE_REQUIRED_TEXT_FIELDS:
            if not text_value(row, field):
                reasons.append(f"missing_source_{field}")
        if text_value(row, "document_type") not in PRIMARY_SOURCE_TYPES:
            reasons.append("non_primary_official_source")
        if text_value(row, "historical_window_role") not in SOURCE_ROLES:
            reasons.append("invalid_historical_window_role")
    return sorted(set(reasons))


def audit_validation_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field in AUDIT_REQUIRED_TEXT_FIELDS:
        if not text_value(record, field):
            reasons.append(f"missing_{field}")
    status = text_value(record, "historical_continuity_status")
    eligibility = text_value(record, "later_research_execution_overlay_eligibility")
    if status not in CONTINUITY_STATUSES:
        reasons.append("invalid_historical_continuity_status")
    if eligibility not in ELIGIBILITY_VALUES:
        reasons.append("invalid_later_research_execution_overlay_eligibility")
    try:
        material_change = bool_value(
            record.get("material_methodology_change_detected")
        )
    except ValueError:
        material_change = False
        reasons.append("invalid_material_methodology_change_detected")
    try:
        spot_proxy = bool_value(record.get("spot_proxy_claim_permitted"))
    except ValueError:
        spot_proxy = True
        reasons.append("invalid_spot_proxy_claim_permitted")
    try:
        etp_return = bool_value(
            record.get("traded_etp_total_return_interpretation")
        )
    except ValueError:
        etp_return = False
        reasons.append("invalid_traded_etp_total_return_interpretation")
    if spot_proxy:
        reasons.append("spot_proxy_claim_not_permitted")
    if not etp_return:
        reasons.append("traded_etp_total_return_interpretation_required")
    interpretation = text_value(record, "historical_return_interpretation").lower()
    if "spot" in interpretation and "not" not in interpretation:
        reasons.append("historical_return_interpretation_may_claim_spot_proxy")
    regime_flag = text_value(record, "required_later_regime_flag")
    if material_change:
        if status != MATERIAL_CHANGE:
            reasons.append("material_change_status_required")
        if not regime_flag or regime_flag == "not_required":
            reasons.append("methodology_regime_flag_required")
        if text_value(record, "material_change_effective_date") in {
            "",
            "not_documented",
        }:
            reasons.append("material_change_effective_date_required")
    if status == INCOMPLETE and eligibility != OVERLAY_BLOCKED:
        reasons.append("incomplete_continuity_must_block")
    return sorted(set(reasons))


def normalise_audit_record(
    record: dict[str, Any], source_rows: list[dict[str, Any]]
) -> dict[str, str]:
    ticker = text_value(record, "ticker")
    reasons = [
        *source_validation_reasons(source_rows, ticker),
        *audit_validation_reasons(record),
    ]
    row = {field: text_value(record, field) for field in AUDIT_FIELDS}
    row["spot_proxy_claim_permitted"] = str(
        bool_value(record.get("spot_proxy_claim_permitted"))
    ).lower()
    row["traded_etp_total_return_interpretation"] = str(
        bool_value(record.get("traded_etp_total_return_interpretation"))
    ).lower()
    row["material_methodology_change_detected"] = str(
        bool_value(record.get("material_methodology_change_detected"))
    ).lower()
    if reasons:
        row["historical_continuity_status"] = INCOMPLETE
        row["later_research_execution_overlay_eligibility"] = OVERLAY_BLOCKED
        row["blocking_reason"] = ";".join(sorted(set(reasons)))
    return row


def source_manifest_rows(
    source_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    rows = [
        {field: text_value(record, field) for field in SOURCE_FIELDS}
        for record in source_rows
    ]
    role_order = {
        "early_window_reference": 0,
        "material_change_reference": 1,
        "current_structure_reference": 2,
    }
    ticker_order = {ticker: index for index, ticker in enumerate(REQUIRED_TICKERS)}
    return sorted(
        rows,
        key=lambda row: (
            ticker_order.get(row["ticker"], 99),
            role_order.get(row["historical_window_role"], 99),
            row["filing_or_publication_date"],
        ),
    )


def overlay_status(rows: list[dict[str, str]]) -> str:
    eligibilities = {
        row["later_research_execution_overlay_eligibility"] for row in rows
    }
    if OVERLAY_BLOCKED in eligibilities:
        return OVERLAY_BLOCKED
    if OVERLAY_FLAGS in eligibilities:
        return OVERLAY_FLAGS
    return OVERLAY_ELIGIBLE


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_markdown(
    path: Path, rows: list[dict[str, str]], status: str
) -> None:
    body = [
        "# GMA-6B.2 Historical Commodity-ETP Methodology Continuity v1",
        "",
        "USO and DBA are analysed only as historical traded ETP return exposures.",
        "Their adjusted-price paths are not asserted to represent spot commodity returns.",
        "Documented futures-roll, collateral, fee, distribution, split, benchmark, and vehicle-structure effects remain part of the realised traded-instrument return.",
        "This is observed development evidence and not a pristine final holdout.",
        "No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.",
        "",
        f"gma6b2_historical_commodity_etp_continuity_overlay_status: `{status}`",
        "",
        markdown_table(
            [
                "ticker",
                "continuity status",
                "material change",
                "regime flag",
                "eligibility",
                "blocking reason",
            ],
            [
                [
                    row["ticker"],
                    row["historical_continuity_status"],
                    row["material_methodology_change_detected"],
                    row["required_later_regime_flag"],
                    row["later_research_execution_overlay_eligibility"],
                    row["blocking_reason"],
                ]
                for row in rows
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")


def run_historical_continuity_audit(
    config_path: Path = CONFIG_PATH,
    *,
    evidence_root: Path | None = None,
    output_root: Path | None = None,
) -> ContinuityResult:
    config = load_yaml(config_path)
    validate_historical_continuity_contract(config)
    resolve_evidence_files(config, evidence_root)
    output_paths = resolve_output_paths(config, output_root)
    source_rows_raw = _mapping_records(config, "source_manifest")
    audit_records = _mapping_records(config, "audit_records")
    rows = [
        normalise_audit_record(record, source_rows_raw)
        for record in audit_records
    ]
    ticker_order = {ticker: index for index, ticker in enumerate(REQUIRED_TICKERS)}
    rows = sorted(rows, key=lambda row: ticker_order[row["ticker"]])
    source_rows = source_manifest_rows(source_rows_raw)
    status = overlay_status(rows)
    write_csv(output_paths.overlay_csv, rows, AUDIT_FIELDS)
    write_csv(output_paths.source_manifest_csv, source_rows, SOURCE_FIELDS)
    write_markdown(output_paths.overlay_markdown, rows, status)
    return ContinuityResult(rows, source_rows, status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate GMA-6B.2 commodity ETP continuity reports."
    )
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output-root", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_historical_continuity_audit(
        Path(args.config),
        evidence_root=Path(args.evidence_root),
        output_root=Path(args.output_root),
    )


if __name__ == "__main__":
    main()
