from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PHASE_ID = "p1a_manual_paper_contract_v1"
STRATEGY_ID = "gma5_equal_weight_atomic_sleeves_v1"
PARENT_EXECUTION_REFERENCE = "gma5_clean_execution_20260622T075912Z_v1"
PARENT_SNAPSHOT_ROOT = Path(
    "C:/Users/Devesh Pansare/Desktop/Personal_Projects/market-strats-lab-gma5-v1-evidence-snapshot-20260623"
)
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/p1a_manual_paper_contract_v1")

SLEEVE_IDS = [
    "absolute_trend_12m_equal_weight",
    "cross_sectional_momentum_12m_top5_inverse_volatility",
    "defensive_drawdown_guard",
    "defensive_spy_200d_rotation",
]
PARENT_TRIAL_IDS = {
    "absolute_trend_12m_equal_weight": "gma4_abs_trend_12m_equal_weight_v1",
    "cross_sectional_momentum_12m_top5_inverse_volatility": "gma4_xsmom_12m_top5_inverse_vol_v1",
    "defensive_drawdown_guard": "gma4_defensive_drawdown_guard_v1",
    "defensive_spy_200d_rotation": "gma4_defensive_spy_200d_rotation_v1",
}
PARENT_CONSTRUCTION = [
    "equal_weight_across_four_atomic_sleeves",
    "netted_composite_etf_target_weights",
    "not_sleeve_equity_curve_averaging",
]
REQUIRED_LANGUAGE = [
    "P-1 is a separate manual-paper observation programme for the frozen GMA-5 equal-weight atomic sleeve portfolio.",
    "P-1 does not use or modify GMA-7 outputs.",
    "P-1 paper observations are not proof of future profitability.",
    "No real-money, broker, execution, or promotion decision is produced.",
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
MANUAL_DECISION_VALUES = [
    "recorded_manual_paper_session",
    "skipped_due_warning",
    "not_run_missing_preconditions",
]
EXECUTION_STATUS_VALUES = [
    "not_executed_manual_paper_only",
    "skipped",
    "not_run",
]
PREFLIGHT_REQUIREMENTS = [
    "parent_reference_verified",
    "strategy_identity_verified",
    "all_four_sleeves_verified",
    "netted_composite_target_method_verified",
    "input_snapshot_present",
    "input_snapshot_hash_verified",
    "source_last_observed_session_present",
    "monthly_decision_timing_verified",
    "target_weight_sum_valid",
    "no_discretionary_override",
    "paper_only_boundary_verified",
]
FAILED_PREFLIGHT_RESULT = {
    "manual_decision": "skipped_due_warning",
    "execution_status": "skipped",
    "paper_session_status": "invalid_or_skipped_manual_paper_session",
}
PARENT_FILES = {
    "gma5_config": Path("configs/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1.yaml"),
    "clean_execution_manifest": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_clean_execution_manifest_v1.json"
    ),
    "ensemble_manifest": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_ensemble_manifest.json"
    ),
    "no_equity_curve_averaging_trace": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_no_equity_curve_averaging_trace_v2.json"
    ),
    "runtime_replay_trace": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_runtime_replay_trace_v1.json"
    ),
    "composite_target_netting_audit": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_composite_target_netting_audit_v2.csv"
    ),
    "monthly_sleeve_weights": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_ensemble_monthly_sleeve_weights.csv"
    ),
    "monthly_etf_targets": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_ensemble_monthly_etf_targets.csv"
    ),
    "cost_scenario_manifest": Path(
        "reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1/gma5_cost_scenario_path_export_manifest_v1.json"
    ),
}
OUTPUT_PATHS = {
    "config": Path("configs/global_multi_asset_alpha/p1a_manual_paper_contract_v1.yaml"),
    "docs": Path("docs/global_multi_asset_alpha/p1a_manual_paper_contract_v1.md"),
    "parent_resolution": OUTPUT_DIR / "p1a_parent_reference_resolution_v1.json",
    "preregistration_csv": OUTPUT_DIR / "p1a_manual_paper_preregistration_v1.csv",
    "preregistration_md": OUTPUT_DIR / "p1a_manual_paper_preregistration_v1.md",
    "session_template": OUTPUT_DIR / "p1a_manual_paper_session_template_v1.csv",
    "ledger": OUTPUT_DIR / "p1a_manual_paper_ledger_v1.csv",
    "preflight_checklist": OUTPUT_DIR / "p1a_operational_preflight_checklist_v1.md",
    "lock": OUTPUT_DIR / "p1a_manual_paper_lock_v1.json",
}


class P1AContractError(ValueError):
    pass


@dataclass(frozen=True)
class ParentReference:
    hashes: dict[str, str]
    bounded_parent_files: dict[str, str]
    bounded_proof_hashes: dict[str, str]
    bounded_rows_read: dict[str, int]
    config: dict[str, Any]
    clean_execution_manifest: dict[str, Any]
    ensemble_manifest: dict[str, Any]
    no_equity_curve_trace: dict[str, Any]
    runtime_replay_trace: dict[str, Any]
    cost_scenario_manifest: dict[str, Any]
    parent_reference_manifest_sha256: str


@dataclass(frozen=True)
class P1AResult:
    lock: dict[str, Any]
    output_paths: dict[str, Path]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1AContractError(f"JSON parent artifact must be an object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P1AContractError(f"YAML parent artifact must be an object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise P1AContractError(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def resolve_parent_reference(snapshot_root: Path = PARENT_SNAPSHOT_ROOT) -> ParentReference:
    paths = {name: snapshot_root / relative for name, relative in PARENT_FILES.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise P1AContractError(
            "Missing required frozen GMA-5 parent artifact(s): " + ", ".join(missing)
        )
    hash_file_ids = [
        "gma5_config",
        "clean_execution_manifest",
        "ensemble_manifest",
        "no_equity_curve_averaging_trace",
        "runtime_replay_trace",
        "cost_scenario_manifest",
    ]
    hashes = {name: sha256_file(paths[name]) for name in hash_file_ids}
    sleeve_proof, sleeve_rows_read = read_equal_weight_sleeve_proof(paths["monthly_sleeve_weights"])
    netting_proof, netting_rows_read = read_first_matching_row(
        paths["composite_target_netting_audit"],
        required_columns={
            "sleeve_weighted_target_sum",
            "net_composite_target_weight",
            "bil_residual_weight",
            "final_target_weight",
        },
    )
    target_proof, target_rows_read = read_first_matching_row(paths["monthly_etf_targets"])
    bounded_parent_files = {
        "monthly_sleeve_weights": str(paths["monthly_sleeve_weights"]),
        "composite_target_netting_audit": str(paths["composite_target_netting_audit"]),
        "monthly_etf_targets": str(paths["monthly_etf_targets"]),
    }
    bounded_proof_hashes = {
        "monthly_sleeve_weights": sha256_text(stable_json(sleeve_proof)),
        "composite_target_netting_audit": sha256_text(stable_json(netting_proof)),
        "monthly_etf_targets": sha256_text(stable_json(target_proof)),
    }
    bounded_rows_read = {
        "monthly_sleeve_weights": sleeve_rows_read,
        "composite_target_netting_audit": netting_rows_read,
        "monthly_etf_targets": target_rows_read,
    }
    parent = ParentReference(
        hashes=hashes,
        bounded_parent_files=bounded_parent_files,
        bounded_proof_hashes=bounded_proof_hashes,
        bounded_rows_read=bounded_rows_read,
        config=_read_yaml(paths["gma5_config"]),
        clean_execution_manifest=_read_json(paths["clean_execution_manifest"]),
        ensemble_manifest=_read_json(paths["ensemble_manifest"]),
        no_equity_curve_trace=_read_json(paths["no_equity_curve_averaging_trace"]),
        runtime_replay_trace=_read_json(paths["runtime_replay_trace"]),
        cost_scenario_manifest=_read_json(paths["cost_scenario_manifest"]),
        parent_reference_manifest_sha256="",
    )
    verify_parent_reference(parent, paths)
    payload = parent_resolution_payload(parent, snapshot_root, paths, "")
    manifest_hash = sha256_text(stable_json(payload))
    return ParentReference(
        hashes=parent.hashes,
        bounded_parent_files=parent.bounded_parent_files,
        bounded_proof_hashes=parent.bounded_proof_hashes,
        bounded_rows_read=parent.bounded_rows_read,
        config=parent.config,
        clean_execution_manifest=parent.clean_execution_manifest,
        ensemble_manifest=parent.ensemble_manifest,
        no_equity_curve_trace=parent.no_equity_curve_trace,
        runtime_replay_trace=parent.runtime_replay_trace,
        cost_scenario_manifest=parent.cost_scenario_manifest,
        parent_reference_manifest_sha256=manifest_hash,
    )


def verify_parent_reference(parent: ParentReference, paths: dict[str, Path]) -> None:
    _require_equal("strategy_id", STRATEGY_ID, "gma5_equal_weight_atomic_sleeves_v1")
    _require_equal(
        "clean_execution_run_id",
        parent.clean_execution_manifest.get("clean_execution_run_id"),
        PARENT_EXECUTION_REFERENCE,
    )
    _require_equal(
        "ensemble_manifest.run_id",
        parent.ensemble_manifest.get("run_id"),
        PARENT_EXECUTION_REFERENCE,
    )
    _require_equal(
        "ensemble_manifest.composite_replay_method",
        parent.ensemble_manifest.get("composite_replay_method"),
        "netted_underlying_etf_targets_through_shared_replay_adapter",
    )
    variant_ids = parent.runtime_replay_trace.get("variant_ids_replayed", [])
    if STRATEGY_ID not in variant_ids:
        raise P1AContractError("Frozen strategy variant missing from runtime replay trace")
    variants = parent.config.get("variants", [])
    if STRATEGY_ID not in variants:
        raise P1AContractError("Frozen strategy variant missing from GMA-5 config")
    _require_equal(
        "no_equity_curve_trace.equity_curve_averaging_invoked",
        parent.no_equity_curve_trace.get("equity_curve_averaging_invoked"),
        False,
    )
    _require_equal(
        "no_equity_curve_trace.replay_input_type",
        parent.no_equity_curve_trace.get("replay_input_type"),
        "netted_composite_etf_target_weights",
    )
    _require_equal(
        "no_equity_curve_trace.allocation_input_type",
        parent.no_equity_curve_trace.get("allocation_input_type"),
        "sleeve_etf_target_weights",
    )
    expected_trials = [PARENT_TRIAL_IDS[sleeve_id] for sleeve_id in SLEEVE_IDS]
    actual_trials = [item["trial_id"] for item in parent.config.get("atomic_sleeves", [])]
    _require_equal("atomic_sleeves", actual_trials, expected_trials)
    verify_equal_weight_sleeves(parent.bounded_proof_hashes["monthly_sleeve_weights"])
    verify_netted_targets(
        parent.bounded_proof_hashes["composite_target_netting_audit"],
        parent.bounded_proof_hashes["monthly_etf_targets"],
    )
    expected_costs = ["baseline_1bps", "stressed_10bps", "stressed_25bps", "severe_50bps"]
    _require_equal(
        "config.cost_scenarios",
        list(parent.config.get("cost_scenarios", {}).keys()),
        expected_costs,
    )
    _require_equal(
        "cost_scenario_manifest.cost_scenarios",
        parent.cost_scenario_manifest.get("cost_scenarios"),
        expected_costs,
    )


def read_equal_weight_sleeve_proof(path: Path) -> tuple[list[dict[str, str]], int]:
    rows_read = 0
    proof_rows: list[dict[str, str]] = []
    proof_decision_date: str | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows_read += 1
            if row.get("variant_id") != STRATEGY_ID:
                continue
            if float(row.get("sleeve_allocation_weight", "0")) <= 0:
                continue
            decision_date = row["decision_date"]
            if proof_decision_date is None:
                proof_decision_date = decision_date
            if decision_date != proof_decision_date:
                break
            proof_rows.append(row)
            if len(proof_rows) == len(SLEEVE_IDS):
                break
    if len(proof_rows) != len(SLEEVE_IDS):
        raise P1AContractError("No complete active equal-weight sleeve proof group found")
    _require_equal(
        f"{proof_decision_date} sleeve ids",
        [row["sleeve_id"] for row in proof_rows],
        list(PARENT_TRIAL_IDS.values()),
    )
    weights = [round(float(row["sleeve_allocation_weight"]), 12) for row in proof_rows]
    _require_equal(f"{proof_decision_date} sleeve weights", weights, [0.25, 0.25, 0.25, 0.25])
    return proof_rows, rows_read


def verify_equal_weight_sleeves(proof_hash: str) -> None:
    if not proof_hash:
        raise P1AContractError("Missing bounded equal-weight sleeve proof hash")


def read_first_matching_row(
    path: Path, required_columns: set[str] | None = None
) -> tuple[dict[str, str], int]:
    rows_read = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        if required_columns and not required_columns <= fieldnames:
            raise P1AContractError("Composite target netting audit lacks required columns")
        for row in reader:
            rows_read += 1
            if row.get("variant_id") == STRATEGY_ID:
                return row, rows_read
    raise P1AContractError("Missing bounded proof row for frozen strategy")


def verify_netted_targets(netting_proof_hash: str, target_proof_hash: str) -> None:
    if not netting_proof_hash or not target_proof_hash:
        raise P1AContractError("Missing bounded netted composite target proof hash")


def parent_resolution_payload(
    parent: ParentReference,
    snapshot_root: Path,
    paths: dict[str, Path],
    parent_reference_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "parent_snapshot_root": str(snapshot_root),
        "source_artifacts": {
            name: {"path": str(path), "sha256": parent.hashes[name]}
            for name, path in paths.items()
            if name in parent.hashes
        },
        "bounded_history_proof_artifacts": {
            name: {
                "path": path,
                "proof_row_sha256": parent.bounded_proof_hashes[name],
                "rows_read": parent.bounded_rows_read[name],
            }
            for name, path in parent.bounded_parent_files.items()
        },
        "parent_files_hashed_count": len(parent.hashes),
        "sleeves": [
            {"sleeve_id": sleeve_id, "parent_trial_id": PARENT_TRIAL_IDS[sleeve_id]}
            for sleeve_id in SLEEVE_IDS
        ],
        "parent_portfolio_construction": PARENT_CONSTRUCTION,
        "monthly_decision_session": "monthly final available decision session from frozen GMA-5 monthly target evidence",
        "execution_timing": "monthly_next_open_shared_replay_convention_from_frozen_GMA5_clean_execution",
        "target_weight_convention": "netted_composite_etf_target_weights",
        "transaction_cost_conventions": parent.cost_scenario_manifest["cost_scenarios"],
        "gma7_dependency": "none",
        "gma7_outputs_can_modify_p1_rules": False,
        "gma7_no_ensemble_result_changes_p1_strategy": False,
        "parent_reference_manifest_sha256": parent_reference_manifest_sha256
        if parent_reference_manifest_sha256 is not None
        else parent.parent_reference_manifest_sha256,
    }


def build_contract_yaml(parent: ParentReference) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "required_language": REQUIRED_LANGUAGE,
        "sleeves": SLEEVE_IDS,
        "parent_trial_ids": PARENT_TRIAL_IDS,
        "parent_portfolio_construction": PARENT_CONSTRUCTION,
        "gma7_dependency": "none",
        "gma7_outputs_can_modify_p1_rules": False,
        "gma7_no_ensemble_result_changes_p1_strategy": False,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "strategy_rule_changes_after_lock": "prohibited",
        "discretionary_target_overrides": "prohibited",
        "minimum_valid_manual_sessions_before_review": 6,
        "minimum_forward_observation_period": "6_calendar_months",
        "review_criteria": "operational_completeness_data_integrity_and_forward_observation_only",
        "return_threshold_for_any_future_decision": "prohibited",
        "manual_decision_values": MANUAL_DECISION_VALUES,
        "execution_status_values": EXECUTION_STATUS_VALUES,
        "ledger_fields": LEDGER_FIELDS,
        "preflight_requirements": PREFLIGHT_REQUIREMENTS,
        "failed_preflight_result": FAILED_PREFLIGHT_RESULT,
        "parent_reference_manifest_sha256": parent.parent_reference_manifest_sha256,
        "parent_files_hashed_count": len(parent.hashes),
        "bounded_history_rows_read": parent.bounded_rows_read,
        "session_input_snapshot_requirements": [
            "session_data_snapshot_path",
            "session_data_snapshot_sha256",
            "data_source_description",
            "source_last_observed_session",
            "data_cutoff_timestamp",
            "manual_preflight_validation_status",
        ],
        "prohibited_in_p1a": [
            "web_download",
            "provider_call",
            "data_substitution",
            "ticker_substitution",
            "input_backfill",
            "target_generation",
            "paper_session_recording",
            "performance_calculation",
            "broker_connection",
            "live_workflow",
        ],
    }


def failed_preflight_status(failed_requirements: list[str]) -> dict[str, str]:
    unknown = sorted(set(failed_requirements) - set(PREFLIGHT_REQUIREMENTS))
    if unknown:
        raise P1AContractError("Unknown preflight requirement(s): " + ", ".join(unknown))
    if not failed_requirements:
        return {
            "manual_decision": "recorded_manual_paper_session",
            "execution_status": "not_executed_manual_paper_only",
            "paper_session_status": "valid_manual_paper_session_ready_for_recording",
        }
    return FAILED_PREFLIGHT_RESULT.copy()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_contract_files(repo_root: Path, parent: ParentReference) -> None:
    config_path = repo_root / OUTPUT_PATHS["config"]
    docs_path = repo_root / OUTPUT_PATHS["docs"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(build_contract_yaml(parent), sort_keys=False), encoding="utf-8"
    )
    docs_path.write_text(
        "\n".join(
            [
                "# P-1A Manual-Paper Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"Strategy ID: `{STRATEGY_ID}`.",
                f"Parent execution reference: `{PARENT_EXECUTION_REFERENCE}`.",
                "",
                "Frozen construction: `equal_weight_across_four_atomic_sleeves`, `netted_composite_etf_target_weights`, `not_sleeve_equity_curve_averaging`.",
                "",
                "P-1B may later perform one manually supplied local-data intake and dry-run preflight validation only.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_preregistration_rows(parent: ParentReference) -> list[dict[str, str]]:
    return [
        {"field": "strategy_id", "value": STRATEGY_ID},
        {"field": "parent_execution_reference", "value": PARENT_EXECUTION_REFERENCE},
        {
            "field": "parent_reference_manifest_sha256",
            "value": parent.parent_reference_manifest_sha256,
        },
        {"field": "paper_mode", "value": "manual_observation_only"},
        {"field": "minimum_valid_manual_sessions_before_review", "value": "6"},
        {"field": "minimum_forward_observation_period", "value": "6_calendar_months"},
        {"field": "gma7_dependency", "value": "none"},
        {"field": "real_money", "value": "prohibited"},
        {"field": "broker_connection", "value": "prohibited"},
        {"field": "trade_execution", "value": "prohibited"},
    ]


def write_markdown_outputs(repo_root: Path, parent: ParentReference) -> None:
    preregistration = repo_root / OUTPUT_PATHS["preregistration_md"]
    preregistration.parent.mkdir(parents=True, exist_ok=True)
    preregistration.write_text(
        "\n".join(
            [
                "# P-1A Manual-Paper Preregistration V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                f"- Strategy ID: `{STRATEGY_ID}`",
                f"- Parent execution reference: `{PARENT_EXECUTION_REFERENCE}`",
                f"- Parent reference manifest SHA-256: `{parent.parent_reference_manifest_sha256}`",
                "- Minimum valid manual sessions before review: `6`",
                "- Minimum forward observation period: `6_calendar_months`",
                "- Return threshold for any future decision: `prohibited`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    checklist = repo_root / OUTPUT_PATHS["preflight_checklist"]
    checklist.write_text(
        "\n".join(
            [
                "# P-1A Operational Preflight Checklist V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                *[f"- [ ] {item}" for item in PREFLIGHT_REQUIREMENTS],
                "",
                "Any failed item maps to `manual_decision = skipped_due_warning`, `execution_status = skipped`, and `paper_session_status = invalid_or_skipped_manual_paper_session`.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_lock(parent: ParentReference) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "strategy_id": STRATEGY_ID,
        "parent_execution_reference": PARENT_EXECUTION_REFERENCE,
        "parent_reference_manifest_sha256": parent.parent_reference_manifest_sha256,
        "parent_files_hashed_count": len(parent.hashes),
        "bounded_history_rows_read": parent.bounded_rows_read,
        "required_language": REQUIRED_LANGUAGE,
        "sleeves": SLEEVE_IDS,
        "parent_trial_ids": PARENT_TRIAL_IDS,
        "parent_portfolio_construction": PARENT_CONSTRUCTION,
        "gma7_dependency": "none",
        "gma7_outputs_can_modify_p1_rules": False,
        "gma7_no_ensemble_result_changes_p1_strategy": False,
        "paper_mode": "manual_observation_only",
        "real_money": "prohibited",
        "broker_connection": "prohibited",
        "trade_execution": "prohibited",
        "automated_order_generation": "prohibited",
        "strategy_rule_changes_after_lock": "prohibited",
        "discretionary_target_overrides": "prohibited",
        "minimum_valid_manual_sessions_before_review": 6,
        "minimum_forward_observation_period": "6_calendar_months",
        "review_criteria": "operational_completeness_data_integrity_and_forward_observation_only",
        "return_threshold_for_any_future_decision": "prohibited",
        "ledger_schema_fields": LEDGER_FIELDS,
        "ledger_row_count": 0,
        "future_paper_session_created": False,
        "target_generated": False,
        "performance_calculated": False,
        "broker_or_live_workflow_created": False,
    }


def generate_manual_paper_contract_files(
    repo_root: Path = Path.cwd(), snapshot_root: Path = PARENT_SNAPSHOT_ROOT
) -> P1AResult:
    parent = resolve_parent_reference(snapshot_root)
    paths = {name: snapshot_root / relative for name, relative in PARENT_FILES.items()}
    parent_resolution = parent_resolution_payload(parent, snapshot_root, paths)
    write_contract_files(repo_root, parent)
    write_json(repo_root / OUTPUT_PATHS["parent_resolution"], parent_resolution)
    write_csv(
        repo_root / OUTPUT_PATHS["preregistration_csv"],
        build_preregistration_rows(parent),
        ["field", "value"],
    )
    write_markdown_outputs(repo_root, parent)
    write_csv(repo_root / OUTPUT_PATHS["session_template"], [], LEDGER_FIELDS)
    write_csv(repo_root / OUTPUT_PATHS["ledger"], [], LEDGER_FIELDS)
    lock = build_lock(parent)
    generated_artifact_hashes = {
        key: sha256_file(repo_root / path)
        for key, path in OUTPUT_PATHS.items()
        if key != "lock" and (repo_root / path).is_file()
    }
    lock["generated_artifact_hashes"] = generated_artifact_hashes
    lock["generated_artifact_hash_count_excluding_lock"] = len(generated_artifact_hashes)
    write_json(repo_root / OUTPUT_PATHS["lock"], lock)
    return P1AResult(
        lock=lock, output_paths={key: repo_root / value for key, value in OUTPUT_PATHS.items()}
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the P-1A manual-paper contract")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot-root", type=Path, default=PARENT_SNAPSHOT_ROOT)
    args = parser.parse_args(argv)
    result = generate_manual_paper_contract_files(args.repo_root, args.snapshot_root)
    print(f"phase_id={PHASE_ID}")
    print(f"strategy_id={result.lock['strategy_id']}")
    print(f"parent_execution_reference={result.lock['parent_execution_reference']}")
    print(f"ledger_row_count={result.lock['ledger_row_count']}")
    print("paper_mode=manual_observation_only")
    for key, path in sorted(result.output_paths.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
