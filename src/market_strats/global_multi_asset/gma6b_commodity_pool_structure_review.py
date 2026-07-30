"""GMA-6B.1 commodity-pool structure interpretation overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

PHASE_ID = "gma6b_commodity_pool_structure_review_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = (
    PROJECT_ROOT
    / "configs/global_multi_asset_alpha/gma6b_commodity_pool_structure_review_v1.yaml"
)
REQUIRED_TICKERS = ["USO", "DBA"]
PRIMARY_SOURCE_TYPES = {
    "issuer_prospectus",
    "statutory_prospectus",
    "annual_report",
    "sec_filing",
    "sec_prospectus",
    "official_issuer_product_document",
}
ECONOMIC_LABELS = {
    "futures_linked_oil_etp_return_exposure",
    "futures_linked_agriculture_etp_return_exposure",
    "structure_unresolved",
}
STATUS_VALUES = {
    "documented_for_later_research_execution",
    "structure_review_pending",
    "blocked_data_contract_failure",
}
ELIGIBILITY_VALUES = {
    "eligible_for_later_research_execution",
    "structure_review_pending",
    "blocked_data_contract_failure",
}
DOCUMENTED_STATUS = "documented_for_later_research_execution"
PENDING_STATUS = "structure_review_pending"
BLOCKED_STATUS = "blocked_data_contract_failure"
ELIGIBLE = "eligible_for_later_research_execution"
OVERLAY_BOTH_DOCUMENTED = "both_documented_for_later_research_execution"
OVERLAY_PENDING = "one_or_more_structure_review_pending"
OVERLAY_BLOCKED = "one_or_more_blocked_data_contract_failure"

REVIEW_FIELDS = [
    "ticker",
    "issuer",
    "official_source_id",
    "required_evidence_file",
    "official_source_title",
    "source_retrieved_at_utc",
    "source_sha256",
    "vehicle_structure",
    "stated_investment_objective",
    "primary_exposure_instruments",
    "roll_or_contract_management_description",
    "collateral_or_cash_description",
    "distribution_and_corporate_action_note",
    "adjusted_price_interpretation",
    "economic_exposure_label",
    "spot_proxy_claim_permitted",
    "traded_etp_total_return_interpretation",
    "structure_review_status",
    "later_research_execution_eligibility",
    "blocking_reason",
]
SOURCE_FIELDS = [
    "ticker",
    "issuer",
    "official_source_id",
    "required_evidence_file",
    "official_source_title",
    "official_source_type",
    "source_retrieved_at_utc",
    "source_sha256",
]
REQUIRED_TEXT_FIELDS = [
    "issuer",
    "official_source_id",
    "required_evidence_file",
    "official_source_title",
    "source_retrieved_at_utc",
    "source_sha256",
    "vehicle_structure",
    "stated_investment_objective",
    "primary_exposure_instruments",
    "roll_or_contract_management_description",
    "collateral_or_cash_description",
    "distribution_and_corporate_action_note",
    "adjusted_price_interpretation",
]
OUTPUT_KEYS = {
    "overlay_csv",
    "overlay_markdown",
    "source_manifest_csv",
}


class GMA6BPortabilityError(ValueError):
    """Raised when the portable evidence or output contract is violated."""


@dataclass(frozen=True)
class OutputPaths:
    overlay_csv: Path
    overlay_markdown: Path
    source_manifest_csv: Path


@dataclass(frozen=True)
class ReviewResult:
    rows: list[dict[str, str]]
    source_manifest_rows: list[dict[str, str]]
    overlay_status: str
    gma6b_universe_status_after_overlay: str


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GMA6BPortabilityError("gma6b_config_file_missing")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6BPortabilityError("gma6b_config_must_contain_mapping")
    return raw


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


def text_value(record: dict[str, Any], field: str) -> str:
    value = record.get(field, "")
    if value is None:
        return ""
    return str(value).strip()


def _relative_path(value: Any, field: str) -> Path:
    text = str(value or "").strip()
    path = Path(text)
    posix_path = PurePosixPath(text)
    windows_path = PureWindowsPath(text)
    if (
        not text
        or "://" in text
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in posix_path.parts
        or ".." in windows_path.parts
        or text.startswith(("/", "\\"))
    ):
        raise GMA6BPortabilityError(f"gma6b_invalid_relative_path:{field}")
    return path


def _required_absolute_root(root: Path | None, kind: str) -> Path:
    if root is None:
        raise GMA6BPortabilityError(f"gma6b_{kind}_root_required")
    path = Path(root)
    if not path.is_absolute():
        raise GMA6BPortabilityError(f"gma6b_{kind}_root_must_be_absolute")
    return path.resolve()


def _contract(config: dict[str, Any]) -> dict[str, Any]:
    contract = config.get("contract")
    if not isinstance(contract, dict):
        raise GMA6BPortabilityError("gma6b_contract_mapping_required")
    return contract


def _records(config: dict[str, Any]) -> list[dict[str, Any]]:
    records = config.get("review_records")
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise GMA6BPortabilityError("gma6b_review_records_must_be_mapping_list")
    return records


def validate_required_tickers(records: list[dict[str, Any]]) -> None:
    tickers = [str(record.get("ticker", "")) for record in records]
    if sorted(tickers) != sorted(REQUIRED_TICKERS):
        raise ValueError("GMA-6B.1 review must contain exactly USO and DBA")
    if len(tickers) != len(set(tickers)):
        raise ValueError("GMA-6B.1 review tickers must be unique")


def validate_structure_review_contract(config: dict[str, Any]) -> None:
    """Validate metadata and semantics without accessing artifact files."""
    contract = _contract(config)
    if contract.get("phase_id") != PHASE_ID:
        raise GMA6BPortabilityError("gma6b_phase_id_mismatch")
    if (
        contract.get("evidence_root_policy")
        != "must_be_supplied_explicitly_for_artifact_validation"
    ):
        raise GMA6BPortabilityError("gma6b_evidence_root_policy_invalid")
    if (
        contract.get("output_root_policy")
        != "must_be_supplied_explicitly_for_output_generation"
    ):
        raise GMA6BPortabilityError("gma6b_output_root_policy_invalid")
    if not str(contract.get("evidence_bundle_id", "")).strip():
        raise GMA6BPortabilityError("gma6b_evidence_bundle_id_required")

    output_files = contract.get("output_files")
    if not isinstance(output_files, dict) or set(output_files) != OUTPUT_KEYS:
        raise GMA6BPortabilityError("gma6b_output_files_invalid")
    for key, value in output_files.items():
        _relative_path(value, f"output_files.{key}")

    records = _records(config)
    validate_required_tickers(records)
    for record in records:
        ticker = text_value(record, "ticker")
        if "official_source_url" in record:
            raise GMA6BPortabilityError(
                f"gma6b_provider_url_field_not_permitted:{ticker}"
            )
        _relative_path(
            record.get("required_evidence_file"),
            f"review_records.{ticker}.required_evidence_file",
        )
        source_id = text_value(record, "official_source_id")
        if not source_id or "://" in source_id:
            raise GMA6BPortabilityError(f"gma6b_source_id_invalid:{ticker}")
        digest = text_value(record, "source_sha256")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise GMA6BPortabilityError(f"gma6b_source_sha256_invalid:{ticker}")


def resolve_evidence_files(
    config: dict[str, Any], evidence_root: Path | None
) -> dict[str, Path]:
    validate_structure_review_contract(config)
    root = _required_absolute_root(evidence_root, "evidence")
    if not root.is_dir():
        raise GMA6BPortabilityError("gma6b_evidence_root_missing")

    resolved: dict[str, Path] = {}
    for record in _records(config):
        ticker = text_value(record, "ticker")
        relative = _relative_path(
            record.get("required_evidence_file"),
            f"review_records.{ticker}.required_evidence_file",
        )
        candidate = (root / relative).resolve()
        if root not in candidate.parents:
            raise GMA6BPortabilityError(
                f"gma6b_evidence_path_outside_root:{ticker}"
            )
        if not candidate.is_file():
            raise GMA6BPortabilityError(
                f"gma6b_required_evidence_missing:{ticker}"
            )
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != text_value(record, "source_sha256"):
            raise GMA6BPortabilityError(
                f"gma6b_evidence_checksum_mismatch:{ticker}"
            )
        resolved[ticker] = candidate
    return resolved


def resolve_output_paths(
    config: dict[str, Any], output_root: Path | None
) -> OutputPaths:
    validate_structure_review_contract(config)
    root = _required_absolute_root(output_root, "output")
    output_files = _contract(config)["output_files"]
    paths = {
        key: (root / _relative_path(value, f"output_files.{key}")).resolve()
        for key, value in output_files.items()
    }
    for key, path in paths.items():
        if root not in path.parents:
            raise GMA6BPortabilityError(f"gma6b_output_path_outside_root:{key}")
    return OutputPaths(
        overlay_csv=paths["overlay_csv"],
        overlay_markdown=paths["overlay_markdown"],
        source_manifest_csv=paths["source_manifest_csv"],
    )


def find_blocking_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    source_type = text_value(record, "official_source_type")
    if source_type not in PRIMARY_SOURCE_TYPES:
        reasons.append("official_primary_source_missing_or_invalid")
    for field in REQUIRED_TEXT_FIELDS:
        if not text_value(record, field):
            reasons.append(f"missing_{field}")
    economic_label = text_value(record, "economic_exposure_label")
    if economic_label not in ECONOMIC_LABELS:
        reasons.append("invalid_economic_exposure_label")
    elif economic_label == "structure_unresolved":
        reasons.append("economic_exposure_unresolved")
    configured_status = text_value(record, "structure_review_status")
    if configured_status not in STATUS_VALUES:
        reasons.append("invalid_structure_review_status")
    configured_eligibility = text_value(record, "later_research_execution_eligibility")
    if configured_eligibility not in ELIGIBILITY_VALUES:
        reasons.append("invalid_later_research_execution_eligibility")
    try:
        spot_proxy = bool_value(record.get("spot_proxy_claim_permitted"))
    except ValueError:
        reasons.append("invalid_spot_proxy_claim_permitted")
        spot_proxy = True
    try:
        total_return = bool_value(record.get("traded_etp_total_return_interpretation"))
    except ValueError:
        reasons.append("invalid_traded_etp_total_return_interpretation")
        total_return = False
    if spot_proxy:
        reasons.append("spot_proxy_claim_not_permitted")
    if not total_return:
        reasons.append("traded_etp_total_return_interpretation_required")
    interpretation = text_value(record, "adjusted_price_interpretation").lower()
    if "spot" in interpretation and "not" not in interpretation:
        reasons.append("adjusted_price_interpretation_may_claim_spot_proxy")
    if "no additional synthetic roll-cost deduction" not in interpretation:
        reasons.append("missing_no_extra_roll_cost_deduction_assumption")
    if configured_eligibility == ELIGIBLE and (spot_proxy or not total_return):
        reasons.append("eligible_status_inconsistent_with_interpretation_flags")
    return sorted(set(reasons))


def normalise_review_record(record: dict[str, Any]) -> dict[str, str]:
    reasons = find_blocking_reasons(record)
    configured_status = text_value(record, "structure_review_status")
    configured_eligibility = text_value(record, "later_research_execution_eligibility")
    configured_reason = text_value(record, "blocking_reason")
    if reasons:
        status = BLOCKED_STATUS
        eligibility = BLOCKED_STATUS
        blocking_reason = ";".join(reasons)
    elif configured_status == PENDING_STATUS or configured_eligibility == PENDING_STATUS:
        status = PENDING_STATUS
        eligibility = PENDING_STATUS
        blocking_reason = configured_reason or "structure_review_pending"
    else:
        status = DOCUMENTED_STATUS
        eligibility = ELIGIBLE
        blocking_reason = ""
    row = {field: text_value(record, field) for field in REVIEW_FIELDS}
    row["spot_proxy_claim_permitted"] = str(
        bool_value(record.get("spot_proxy_claim_permitted"))
    ).lower()
    row["traded_etp_total_return_interpretation"] = str(
        bool_value(record.get("traded_etp_total_return_interpretation"))
    ).lower()
    row["structure_review_status"] = status
    row["later_research_execution_eligibility"] = eligibility
    row["blocking_reason"] = blocking_reason
    return row


def overlay_status(rows: list[dict[str, str]]) -> str:
    statuses = {row["structure_review_status"] for row in rows}
    if BLOCKED_STATUS in statuses:
        return OVERLAY_BLOCKED
    if PENDING_STATUS in statuses:
        return OVERLAY_PENDING
    return OVERLAY_BOTH_DOCUMENTED


def universe_status_after_overlay(status: str) -> str:
    if status == OVERLAY_BOTH_DOCUMENTED:
        return "eligible_for_later_gma6_research_execution"
    return "blocked_data_contract_failure"


def source_manifest_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {field: text_value(record, field) for field in SOURCE_FIELDS}
        for record in records
    ]
    order = {ticker: index for index, ticker in enumerate(REQUIRED_TICKERS)}
    return sorted(rows, key=lambda row: order[row["ticker"]])


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
    path: Path, rows: list[dict[str, str]], status: str, universe_status: str
) -> None:
    body = [
        "# GMA-6B.1 Commodity-Pool Structure Review v1",
        "",
        "USO and DBA are evaluated only as traded ETP return exposures.",
        "Their adjusted-price history is not asserted to be a spot commodity return series.",
        "Any embedded futures-roll, collateral, fee, distribution, split, or vehicle-structure effects remain part of the historical traded-instrument return.",
        "This is observed development evidence and not a pristine final holdout.",
        "No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.",
        "",
        f"gma6b_commodity_pool_overlay_status: `{status}`",
        f"gma6b_universe_status_after_overlay: `{universe_status}`",
        "",
        markdown_table(
            [
                "ticker",
                "economic exposure",
                "structure status",
                "later research eligibility",
                "blocking reason",
            ],
            [
                [
                    row["ticker"],
                    row["economic_exposure_label"],
                    row["structure_review_status"],
                    row["later_research_execution_eligibility"],
                    row["blocking_reason"],
                ]
                for row in rows
            ],
        ),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")


def run_structure_review(
    config_path: Path = CONFIG_PATH,
    *,
    evidence_root: Path | None,
    output_root: Path | None,
) -> ReviewResult:
    config = load_yaml(config_path)
    validate_structure_review_contract(config)
    resolve_evidence_files(config, evidence_root)
    output_paths = resolve_output_paths(config, output_root)
    records = _records(config)
    rows = [normalise_review_record(record) for record in records]
    order = {ticker: index for index, ticker in enumerate(REQUIRED_TICKERS)}
    rows = sorted(rows, key=lambda row: order[row["ticker"]])
    status = overlay_status(rows)
    universe_status = universe_status_after_overlay(status)
    source_rows = source_manifest_rows(records)
    write_csv(output_paths.overlay_csv, rows, REVIEW_FIELDS)
    write_csv(output_paths.source_manifest_csv, source_rows, SOURCE_FIELDS)
    write_markdown(
        output_paths.overlay_markdown, rows, status, universe_status
    )
    return ReviewResult(rows, source_rows, status, universe_status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate GMA-6B.1 commodity-pool overlay reports."
    )
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output-root", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_structure_review(
        Path(args.config),
        evidence_root=Path(args.evidence_root),
        output_root=Path(args.output_root),
    )


if __name__ == "__main__":
    main()
