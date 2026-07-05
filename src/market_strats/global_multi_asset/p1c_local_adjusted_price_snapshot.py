from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import yaml

PHASE_ID = "p1c_local_adjusted_price_snapshot_v1"
STRATEGY_ID = "gma5_equal_weight_atomic_sleeves_v1"
PARENT_EXECUTION_REFERENCE = "gma5_clean_execution_20260622T075912Z_v1"
PLACEHOLDER = "REQUIRED_MANUAL_ENTRY"
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_v1")

REQUIRED_LANGUAGE = [
    "P-1C defines and validates the local adjusted-price snapshot format required for future manual intake.",
    "No actual manual snapshot or intake manifest was supplied to this run.",
    "No signal, sleeve weight, ETF target, paper decision, paper session, performance result, broker instruction, or real-money action is produced.",
    "P-1 remains a separate manual-paper observation programme for the frozen GMA-5 equal-weight atomic sleeve portfolio.",
]

SNAPSHOT_COLUMNS = [
    "session_date",
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
SNAPSHOT_HEADER_LINE = ",".join(SNAPSHOT_COLUMNS)

MANIFEST_FIELDS = [
    "intake_id",
    "manual_intake_timestamp_utc",
    "scheduled_decision_session_date",
    "session_data_snapshot_path",
    "session_data_snapshot_sha256",
    "data_source_description",
    "source_last_observed_session",
    "data_cutoff_timestamp_utc",
    "snapshot_format",
    "snapshot_schema_version",
    "operator_attestation",
    "p1c_snapshot_schema_hash",
    "p1c_required_history_registry_hash",
]

P1_INPUTS = {
    "p1a_contract": Path("configs/global_multi_asset_alpha/p1a_manual_paper_contract_v1.yaml"),
    "p1b_contract": Path(
        "configs/global_multi_asset_alpha/p1b_manual_data_intake_preflight_contract_v1.yaml"
    ),
    "p1a_parent_resolution": Path(
        "reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1/"
        "p1a_parent_reference_resolution_v1.json"
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
    "p1b_execution_manifest": Path(
        "reports/global_multi_asset_alpha/p1b_manual_data_intake_preflight_v1/"
        "p1b_execution_manifest_v1.json"
    ),
    "p1b_lock": Path(
        "reports/global_multi_asset_alpha/p1b_manual_data_intake_preflight_v1/"
        "p1b_preflight_lock_v1.json"
    ),
}

GMA5_REFERENCE_FILES = {
    "gma5_config": Path(
        "C:/Users/Devesh Pansare/Desktop/Personal_Projects/"
        "market-strats-lab-gma5-v1-evidence-snapshot-20260623/"
        "configs/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1.yaml"
    ),
    "clean_execution_manifest": Path(
        "C:/Users/Devesh Pansare/Desktop/Personal_Projects/"
        "market-strats-lab-gma5-v1-evidence-snapshot-20260623/"
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_clean_execution_manifest_v1.json"
    ),
    "gma5_source_snapshot": Path(
        "C:/Users/Devesh Pansare/Desktop/Personal_Projects/"
        "market-strats-lab-gma5-v1-evidence-snapshot-20260623/"
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/source_snapshots/src/"
        "market_strats/global_multi_asset/gma5_atomic_sleeve_ensemble.py"
    ),
}

OUTPUT_PATHS = {
    "contract": Path(
        "configs/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_contract_v1.yaml"
    ),
    "docs": Path("docs/global_multi_asset_alpha/p1c_local_adjusted_price_snapshot_contract_v1.md"),
    "snapshot_template": OUTPUT_DIR / "p1c_adjusted_price_snapshot_template_v1.csv",
    "manifest_template": OUTPUT_DIR / "p1c_manual_snapshot_intake_manifest_template_v1.json",
    "history_registry": OUTPUT_DIR / "p1c_required_history_registry_v1.csv",
    "schema_reference": OUTPUT_DIR / "p1c_snapshot_schema_reference_v1.md",
    "dry_run_json": OUTPUT_DIR / "p1c_template_only_dry_run_v1.json",
    "dry_run_md": OUTPUT_DIR / "p1c_template_only_dry_run_v1.md",
    "execution_manifest": OUTPUT_DIR / "p1c_execution_manifest_v1.json",
    "lock": OUTPUT_DIR / "p1c_local_snapshot_lock_v1.json",
}

VALIDATION_REQUIREMENTS = [
    "manifest_present",
    "snapshot_present",
    "snapshot_sha256_verified",
    "manifest_schema_exact",
    "p1a_parent_lock_hash_verified",
    "p1a_parent_strategy_verified",
    "p1a_zero_row_ledger_verified",
    "p1b_dry_run_boundary_verified",
    "snapshot_header_exact",
    "snapshot_session_dates_valid",
    "snapshot_session_dates_strictly_ascending",
    "snapshot_has_no_duplicate_dates",
    "snapshot_has_no_missing_values",
    "snapshot_has_only_positive_finite_adjusted_prices",
    "snapshot_cutoff_is_consistent",
    "snapshot_last_session_matches_declared_source_last_observed_session",
    "snapshot_history_meets_frozen_gma5_requirement",
    "operator_attestation_present",
    "paper_only_boundary_verified",
]

DRY_RUN_FAILED_REQUIREMENTS = [
    "manifest_present",
    "snapshot_present",
    "snapshot_sha256_verified",
    "manifest_schema_exact",
    "snapshot_header_exact",
    "snapshot_session_dates_valid",
    "snapshot_session_dates_strictly_ascending",
    "snapshot_has_no_duplicate_dates",
    "snapshot_has_no_missing_values",
    "snapshot_has_only_positive_finite_adjusted_prices",
    "snapshot_cutoff_is_consistent",
    "snapshot_last_session_matches_declared_source_last_observed_session",
    "snapshot_history_meets_frozen_gma5_requirement",
    "operator_attestation_present",
]

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


class P1CLocalSnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class P1Inputs:
    p1a_contract: dict[str, Any]
    p1b_contract: dict[str, Any]
    p1a_parent_resolution: dict[str, Any]
    p1a_lock: dict[str, Any]
    p1b_dry_run: dict[str, Any]
    p1b_execution_manifest: dict[str, Any]
    p1b_lock: dict[str, Any]
    input_hashes: dict[str, str]


@dataclass(frozen=True)
class HistoryRequirement:
    requirement_id: str
    parent_source_file: str
    parent_source_sha256: str
    parent_reference_excerpt_or_identifier: str
    affected_sleeve_or_parent_rule: str
    lookback_sessions: int
    warmup_buffer_sessions: int
    minimum_required_snapshot_sessions: int
    reason: str


@dataclass(frozen=True)
class SnapshotValidationResult:
    status: str
    failed_requirements: list[str]
    manual_snapshot_validated: bool
    target_generated: bool
    paper_session_created: bool
    manual_paper_ledger_modified: bool


def sha256_file(path: Path) -> str:
    if path.is_dir():
        raise P1CLocalSnapshotError(f"Refusing to hash a directory: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1CLocalSnapshotError(f"Expected JSON object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1CLocalSnapshotError(f"Expected YAML object: {path}")
    return payload


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise P1CLocalSnapshotError(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def _is_present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip() != PLACEHOLDER


def load_p1_inputs(repo_root: Path) -> P1Inputs:
    paths = {name: repo_root / relative for name, relative in P1_INPUTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise P1CLocalSnapshotError("Missing required P-1 input(s): " + ", ".join(missing))
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
        p1a_parent_resolution=_read_json(paths["p1a_parent_resolution"]),
        p1a_lock=_read_json(paths["p1a_lock"]),
        p1b_dry_run=_read_json(paths["p1b_dry_run"]),
        p1b_execution_manifest=_read_json(paths["p1b_execution_manifest"]),
        p1b_lock=_read_json(paths["p1b_lock"]),
        input_hashes=hashes,
    )
    verify_p1_boundaries(p1)
    return p1


def verify_p1_boundaries(p1: P1Inputs) -> None:
    for name, payload in (
        ("p1a_contract", p1.p1a_contract),
        ("p1b_contract", p1.p1b_contract),
        ("p1a_parent_resolution", p1.p1a_parent_resolution),
        ("p1a_lock", p1.p1a_lock),
    ):
        _require_equal(f"{name}.strategy_id", payload.get("strategy_id"), STRATEGY_ID)
        _require_equal(
            f"{name}.parent_execution_reference",
            payload.get("parent_execution_reference"),
            PARENT_EXECUTION_REFERENCE,
        )
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
        "p1b_dry_run.preflight_dry_run_status",
        p1.p1b_dry_run.get("preflight_dry_run_status"),
        "not_run_missing_preconditions",
    )
    _require_equal(
        "p1b_dry_run.paper_session_created", p1.p1b_dry_run.get("paper_session_created"), False
    )
    _require_equal(
        "p1b_dry_run.manual_paper_ledger_modified",
        p1.p1b_dry_run.get("manual_paper_ledger_modified"),
        False,
    )
    _require_equal(
        "p1b_lock.paper_session_created", p1.p1b_lock.get("paper_session_created"), False
    )
    _require_equal(
        "p1b_lock.manual_paper_ledger_modified",
        p1.p1b_lock.get("manual_paper_ledger_modified"),
        False,
    )


def derive_history_requirements(
    reference_files: dict[str, Path] = GMA5_REFERENCE_FILES,
) -> list[HistoryRequirement]:
    missing = [str(path) for path in reference_files.values() if not path.is_file()]
    if missing:
        raise P1CLocalSnapshotError(
            "parent_price_history_requirement_unresolved: " + ", ".join(missing)
        )
    hashes = {name: sha256_file(path) for name, path in reference_files.items()}
    config = _read_yaml(reference_files["gma5_config"])
    manifest = _read_json(reference_files["clean_execution_manifest"])
    source_text = reference_files["gma5_source_snapshot"].read_text(encoding="utf-8")
    if manifest.get("clean_execution_run_id") != PARENT_EXECUTION_REFERENCE:
        raise P1CLocalSnapshotError("parent_price_history_requirement_unresolved")
    if STRATEGY_ID not in config.get("variants", []):
        raise P1CLocalSnapshotError("parent_price_history_requirement_unresolved")
    if "Dummy" in source_text and "gma5_atomic_sleeve_ensemble" not in source_text:
        source_identifier = "source_snapshot_contains_no_executable_rule_detail"
    else:
        source_identifier = "gma5_atomic_sleeve_ensemble_source_snapshot_present"
    trial_ids = [row.get("trial_id", "") for row in config.get("atomic_sleeves", [])]
    rules = [
        (
            "absolute_trend_12m_equal_weight",
            "gma4_abs_trend_12m_equal_weight_v1",
            252,
            "trial identifier contains explicit 12m absolute-trend lookback",
        ),
        (
            "cross_sectional_momentum_12m_top5_inverse_volatility",
            "gma4_xsmom_12m_top5_inverse_vol_v1",
            252,
            "trial identifier contains explicit 12m cross-sectional momentum lookback",
        ),
        (
            "defensive_spy_200d_rotation",
            "gma4_defensive_spy_200d_rotation_v1",
            200,
            "trial identifier contains explicit 200d defensive rotation lookback",
        ),
    ]
    rows: list[HistoryRequirement] = []
    for requirement_id, trial_id, lookback, reason in rules:
        if trial_id not in trial_ids:
            raise P1CLocalSnapshotError("parent_price_history_requirement_unresolved")
        rows.append(
            HistoryRequirement(
                requirement_id=requirement_id,
                parent_source_file=str(reference_files["gma5_config"]),
                parent_source_sha256=hashes["gma5_config"],
                parent_reference_excerpt_or_identifier=f"atomic_sleeves.trial_id={trial_id}; {source_identifier}",
                affected_sleeve_or_parent_rule=trial_id,
                lookback_sessions=lookback,
                warmup_buffer_sessions=1,
                minimum_required_snapshot_sessions=lookback + 1,
                reason=reason,
            )
        )
    if not rows:
        raise P1CLocalSnapshotError("parent_price_history_requirement_unresolved")
    return rows


def minimum_required_snapshot_sessions(requirements: list[HistoryRequirement]) -> int:
    if not requirements:
        raise P1CLocalSnapshotError("parent_price_history_requirement_unresolved")
    return max(row.minimum_required_snapshot_sessions for row in requirements)


def get_xnys_sessions(start_date: date, end_date: date) -> list[date]:
    try:
        import exchange_calendars as xcals  # type: ignore[import-not-found]
    except ImportError as exc:
        raise P1CLocalSnapshotError("xnys_calendar_unavailable") from exc
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(start_date.isoformat(), end_date.isoformat())
    return [item.date() for item in sessions]


def final_xnys_session_of_month(
    session_date: date, session_provider: Callable[[date, date], list[date]] = get_xnys_sessions
) -> date:
    if session_date.month == 12:
        month_end = date(session_date.year, 12, 31)
    else:
        month_end = date(session_date.year, session_date.month + 1, 1).replace(day=1)
        month_end = date.fromordinal(month_end.toordinal() - 1)
    sessions = session_provider(session_date.replace(day=1), month_end)
    if not sessions:
        raise P1CLocalSnapshotError("xnys_calendar_unavailable")
    return sessions[-1]


def build_manifest_template() -> dict[str, str]:
    return {field: PLACEHOLDER for field in MANIFEST_FIELDS}


def validate_local_snapshot_intake(
    repo_root: Path,
    manifest_path: Path | None,
    session_provider: Callable[[date, date], list[date]] = get_xnys_sessions,
) -> SnapshotValidationResult:
    load_p1_inputs(repo_root)
    requirements = derive_history_requirements()
    min_sessions = minimum_required_snapshot_sessions(requirements)
    if manifest_path is None:
        return SnapshotValidationResult(
            status="invalid_local_snapshot_no_target_generated",
            failed_requirements=DRY_RUN_FAILED_REQUIREMENTS.copy(),
            manual_snapshot_validated=False,
            target_generated=False,
            paper_session_created=False,
            manual_paper_ledger_modified=False,
        )
    failed: list[str] = []
    if not manifest_path.is_file():
        failed.append("manifest_present")
        return _invalid(failed)
    manifest = _read_json(manifest_path)
    if set(manifest) != set(MANIFEST_FIELDS) or any(
        manifest.get(field) == PLACEHOLDER for field in MANIFEST_FIELDS
    ):
        failed.append("manifest_schema_exact")
    if manifest.get("snapshot_format") != "csv_adjusted_close_wide_v1":
        failed.append("manifest_schema_exact")
    if manifest.get("snapshot_schema_version") != "p1c_adjusted_price_snapshot_v1":
        failed.append("manifest_schema_exact")
    snapshot_path_value = manifest.get("session_data_snapshot_path")
    snapshot_path = Path(snapshot_path_value) if _is_present(snapshot_path_value) else None
    if snapshot_path is not None and not snapshot_path.is_absolute():
        snapshot_path = manifest_path.parent / snapshot_path
    if snapshot_path is None or not snapshot_path.is_file():
        failed.append("snapshot_present")
        return _invalid(_dedupe(failed))
    expected_hash = manifest.get("session_data_snapshot_sha256")
    if not _is_present(expected_hash) or sha256_file(snapshot_path) != str(expected_hash):
        failed.append("snapshot_sha256_verified")
    if not _is_present(manifest.get("operator_attestation")):
        failed.append("operator_attestation_present")
    rows, snapshot_failures, session_dates = inspect_snapshot(snapshot_path)
    failed.extend(snapshot_failures)
    if rows:
        schedule_failures = validate_calendar_consistency(
            session_dates,
            manifest,
            min_sessions,
            session_provider,
        )
        failed.extend(schedule_failures)
    if failed:
        return _invalid(_dedupe(failed))
    return SnapshotValidationResult(
        status="validated_local_snapshot_no_target_generated",
        failed_requirements=[],
        manual_snapshot_validated=True,
        target_generated=False,
        paper_session_created=False,
        manual_paper_ledger_modified=False,
    )


def _invalid(failed: list[str]) -> SnapshotValidationResult:
    return SnapshotValidationResult(
        status="invalid_local_snapshot_no_target_generated",
        failed_requirements=failed,
        manual_snapshot_validated=False,
        target_generated=False,
        paper_session_created=False,
        manual_paper_ledger_modified=False,
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def inspect_snapshot(snapshot_path: Path) -> tuple[list[dict[str, str]], list[str], list[date]]:
    failed: list[str] = []
    with snapshot_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != SNAPSHOT_COLUMNS:
            failed.append("snapshot_header_exact")
        rows = list(reader)
    session_dates: list[date] = []
    seen_dates: set[date] = set()
    previous: date | None = None
    for row in rows:
        raw_date = row.get("session_date", "")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            failed.append("snapshot_session_dates_valid")
            continue
        if parsed_date in seen_dates:
            failed.append("snapshot_has_no_duplicate_dates")
        if previous is not None and parsed_date <= previous:
            failed.append("snapshot_session_dates_strictly_ascending")
        seen_dates.add(parsed_date)
        previous = parsed_date
        session_dates.append(parsed_date)
        for column in SNAPSHOT_COLUMNS[1:]:
            value = row.get(column)
            if value is None or value == "":
                failed.append("snapshot_has_no_missing_values")
                continue
            try:
                numeric_value = float(value)
            except ValueError:
                failed.append("snapshot_has_only_positive_finite_adjusted_prices")
                continue
            if not math.isfinite(numeric_value) or numeric_value <= 0:
                failed.append("snapshot_has_only_positive_finite_adjusted_prices")
    return rows, _dedupe(failed), session_dates


def validate_calendar_consistency(
    session_dates: list[date],
    manifest: dict[str, Any],
    minimum_sessions: int,
    session_provider: Callable[[date, date], list[date]],
) -> list[str]:
    failed: list[str] = []
    try:
        scheduled = date.fromisoformat(str(manifest.get("scheduled_decision_session_date")))
        source_last = date.fromisoformat(str(manifest.get("source_last_observed_session")))
        cutoff = datetime.fromisoformat(
            str(manifest.get("data_cutoff_timestamp_utc")).replace("Z", "+00:00")
        )
    except ValueError:
        return [
            "snapshot_cutoff_is_consistent",
            "snapshot_last_session_matches_declared_source_last_observed_session",
        ]
    if scheduled != final_xnys_session_of_month(scheduled, session_provider):
        failed.append("snapshot_cutoff_is_consistent")
    if source_last != scheduled:
        failed.append("snapshot_last_session_matches_declared_source_last_observed_session")
    if not session_dates or session_dates[-1] != scheduled or session_dates[-1] != source_last:
        failed.append("snapshot_last_session_matches_declared_source_last_observed_session")
    if session_dates and session_dates[-1] > cutoff.date():
        failed.append("snapshot_cutoff_is_consistent")
    if session_dates:
        expected_sessions = session_provider(session_dates[0], session_dates[-1])
        if expected_sessions != session_dates:
            failed.append("snapshot_session_dates_valid")
    if len(session_dates) < minimum_sessions:
        failed.append("snapshot_history_meets_frozen_gma5_requirement")
    return _dedupe(failed)


def build_history_registry_rows(requirements: list[HistoryRequirement]) -> list[dict[str, Any]]:
    return [row.__dict__ for row in requirements]


def build_contract_yaml(
    p1: P1Inputs, requirements: list[HistoryRequirement], registry_hash: str | None = None
) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "required_language": REQUIRED_LANGUAGE,
        "snapshot_value_type": "adjusted_close_price",
        "snapshot_header": SNAPSHOT_COLUMNS,
        "snapshot_header_line": SNAPSHOT_HEADER_LINE,
        "snapshot_format": "csv_adjusted_close_wide_v1",
        "snapshot_schema_version": "p1c_adjusted_price_snapshot_v1",
        "p1c_minimum_required_snapshot_sessions": minimum_required_snapshot_sessions(requirements),
        "p1c_required_history_registry_hash": registry_hash,
        "p1a_input_hashes": p1.input_hashes,
        "validation_requirements": VALIDATION_REQUIREMENTS,
        "prohibited_actions": [
            "forward_fill",
            "backfill",
            "interpolation",
            "price_normalisation",
            "split_adjustment",
            "dividend_adjustment",
            "date_insertion",
            "date_removal",
            "row_filtering",
            "ticker_replacement",
            "signals",
            "sleeve_weights",
            "ETF_targets",
            "portfolio_weights",
            "turnover",
            "costs",
            "returns",
            "performance",
            "paper_decisions",
            "orders",
        ],
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


def generate_p1c_files(repo_root: Path = Path.cwd()) -> dict[str, Any]:
    p1 = load_p1_inputs(repo_root)
    ledger_before = p1.input_hashes["p1a_ledger"]
    template_before = p1.input_hashes["p1a_session_template"]
    requirements = derive_history_requirements()
    history_rows = build_history_registry_rows(requirements)
    write_csv(
        repo_root / OUTPUT_PATHS["history_registry"],
        history_rows,
        [
            "requirement_id",
            "parent_source_file",
            "parent_source_sha256",
            "parent_reference_excerpt_or_identifier",
            "affected_sleeve_or_parent_rule",
            "lookback_sessions",
            "warmup_buffer_sessions",
            "minimum_required_snapshot_sessions",
            "reason",
        ],
    )
    registry_hash = sha256_file(repo_root / OUTPUT_PATHS["history_registry"])
    contract = build_contract_yaml(p1, requirements, registry_hash)
    write_text(
        repo_root / OUTPUT_PATHS["contract"],
        yaml.safe_dump(contract, sort_keys=False),
    )
    write_text(repo_root / OUTPUT_PATHS["snapshot_template"], SNAPSHOT_HEADER_LINE + "\n")
    write_json(repo_root / OUTPUT_PATHS["manifest_template"], build_manifest_template())
    write_docs(repo_root / OUTPUT_PATHS["docs"], requirements, registry_hash)
    write_schema_reference(
        repo_root / OUTPUT_PATHS["schema_reference"], requirements, registry_hash
    )
    dry_run = build_template_only_dry_run(p1, requirements, registry_hash)
    write_json(repo_root / OUTPUT_PATHS["dry_run_json"], dry_run)
    write_dry_run_markdown(repo_root / OUTPUT_PATHS["dry_run_md"], dry_run)
    generated_hashes = {
        name: sha256_file(repo_root / path)
        for name, path in OUTPUT_PATHS.items()
        if name not in {"execution_manifest", "lock"} and (repo_root / path).is_file()
    }
    execution_manifest = {
        "phase_id": PHASE_ID,
        "template_only": True,
        "actual_manual_snapshot_supplied": False,
        "p1_inputs_read": {name: str(path) for name, path in P1_INPUTS.items()},
        "gma5_reference_files_read": {
            name: str(path) for name, path in GMA5_REFERENCE_FILES.items()
        },
        "p1_input_hashes": p1.input_hashes,
        "generated_artifact_hashes_excluding_manifest_and_lock": generated_hashes,
        "files_hashed_count": len(p1.input_hashes)
        + len(GMA5_REFERENCE_FILES)
        + len(generated_hashes),
    }
    write_json(repo_root / OUTPUT_PATHS["execution_manifest"], execution_manifest)
    generated_hashes_with_manifest = {
        **generated_hashes,
        "execution_manifest": sha256_file(repo_root / OUTPUT_PATHS["execution_manifest"]),
    }
    lock = {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "p1c_template_only_dry_run_status": "not_run_no_manual_snapshot_or_manifest",
        "manual_snapshot_validated": False,
        "target_generated": False,
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "p1c_minimum_required_snapshot_sessions": minimum_required_snapshot_sessions(requirements),
        "p1c_required_history_registry_hash": registry_hash,
        "snapshot_schema_hash": hashlib.sha256(SNAPSHOT_HEADER_LINE.encode("utf-8")).hexdigest(),
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
    return {"dry_run": dry_run, "lock": lock, "output_paths": OUTPUT_PATHS}


def build_template_only_dry_run(
    p1: P1Inputs, requirements: list[HistoryRequirement], registry_hash: str
) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "p1c_template_only_dry_run_status": "not_run_no_manual_snapshot_or_manifest",
        "manual_snapshot_validated": False,
        "target_generated": False,
        "paper_session_created": False,
        "manual_paper_ledger_modified": False,
        "required_language": REQUIRED_LANGUAGE,
        "passed_requirements": [
            "p1a_parent_lock_hash_verified",
            "p1a_parent_strategy_verified",
            "p1a_zero_row_ledger_verified",
            "p1b_dry_run_boundary_verified",
            "paper_only_boundary_verified",
        ],
        "failed_requirements": DRY_RUN_FAILED_REQUIREMENTS.copy(),
        "p1_input_hashes": p1.input_hashes,
        "p1c_minimum_required_snapshot_sessions": minimum_required_snapshot_sessions(requirements),
        "p1c_required_history_registry_hash": registry_hash,
    }


def write_docs(path: Path, requirements: list[HistoryRequirement], registry_hash: str) -> None:
    write_text(
        path,
        "\n".join(
            [
                "# P-1C Local Adjusted-Price Snapshot Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"Snapshot header: `{SNAPSHOT_HEADER_LINE}`",
                f"P-1C minimum required snapshot sessions: `{minimum_required_snapshot_sessions(requirements)}`",
                f"Required history registry SHA-256: `{registry_hash}`",
                "",
                "P-1C uses the local XNYS calendar only for future validation and fails closed if the calendar is unavailable.",
                "It accepts adjusted-close values as supplied or rejects the snapshot; it does not repair, backfill, normalize, adjust, filter, or substitute data.",
                "",
            ]
        ),
    )


def write_schema_reference(
    path: Path, requirements: list[HistoryRequirement], registry_hash: str
) -> None:
    write_text(
        path,
        "\n".join(
            [
                "# P-1C Adjusted-Price Snapshot Schema Reference V1",
                "",
                f"Header: `{SNAPSHOT_HEADER_LINE}`",
                "Value type: `adjusted_close_price`",
                "Date format: `YYYY-MM-DD`",
                "Date order: `strictly_ascending`",
                f"Minimum complete XNYS sessions: `{minimum_required_snapshot_sessions(requirements)}`",
                f"Required history registry SHA-256: `{registry_hash}`",
                "",
            ]
        ),
    )


def write_dry_run_markdown(path: Path, dry_run: dict[str, Any]) -> None:
    failed = "\n".join(f"- `{item}`" for item in dry_run["failed_requirements"])
    passed = "\n".join(f"- `{item}`" for item in dry_run["passed_requirements"])
    write_text(
        path,
        "\n".join(
            [
                "# P-1C Template-Only Dry Run V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"- p1c_template_only_dry_run_status: `{dry_run['p1c_template_only_dry_run_status']}`",
                f"- manual_snapshot_validated: `{str(dry_run['manual_snapshot_validated']).lower()}`",
                f"- target_generated: `{str(dry_run['target_generated']).lower()}`",
                f"- paper_session_created: `{str(dry_run['paper_session_created']).lower()}`",
                f"- manual_paper_ledger_modified: `{str(dry_run['manual_paper_ledger_modified']).lower()}`",
                "",
                "## Passed Requirements",
                "",
                passed,
                "",
                "## Failed Requirements",
                "",
                failed,
                "",
            ]
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate P-1C local snapshot contract artifacts")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = generate_p1c_files(args.repo_root)
    dry_run = result["dry_run"]
    print(f"phase_id={PHASE_ID}")
    print(f"strategy_id={STRATEGY_ID}")
    print(f"parent_execution_reference={PARENT_EXECUTION_REFERENCE}")
    print(f"p1c_template_only_dry_run_status={dry_run['p1c_template_only_dry_run_status']}")
    print(f"manual_snapshot_validated={str(dry_run['manual_snapshot_validated']).lower()}")
    print(f"target_generated={str(dry_run['target_generated']).lower()}")
    print(f"paper_session_created={str(dry_run['paper_session_created']).lower()}")
    print(f"manual_paper_ledger_modified={str(dry_run['manual_paper_ledger_modified']).lower()}")
    print("failed_requirements=" + ",".join(dry_run["failed_requirements"]))
    for key, path in sorted(OUTPUT_PATHS.items()):
        print(f"{key}={args.repo_root / path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
