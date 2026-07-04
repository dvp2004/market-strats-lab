from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

PHASE_ID = "gma7d_development_gate_integration_v1"
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/gma7d_development_gate_integration_v1")

EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH = (
    "e767cb622bfe41240a8a4536920f79def3d267092b1bd0dcb2e6a06865ecdc6a"
)
EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH = (
    "b93bd9800ddfffa19f12100c4538a4668ae61c20b7e322fec8df9441f63a166b"
)
EXPECTED_NORMALISED_BUNDLE_HASH = "3d3d920e9bafa430fb313fe0f494954826a73f8962a15eb8709d02f2bae14bb6"
EXPECTED_GMA7B_FEATURE_ROWS = 4536
EXPECTED_GMA7B_MISSING_FEATURE_ROWS = 0
EXPECTED_GMA7C_LABEL_ROWS = 3171
EXPECTED_GMA7C_SCORE_ROWS = 7980
EXPECTED_GMA7C_COMPONENT_METRIC_ROWS = 60
EXPECTED_GMA7C_RISK_METRIC_ROWS = 60
EXPECTED_GMA7C_GATE_ROWS = 15
EXPECTED_GMA7C_OUTER_FOLD_COUNT = 4
EXPECTED_FULLY_QUALIFYING_COUNT = 0

RETURN_MODEL_IDS = [
    "bounded_gradient_boosted_tree_return_rank_model",
    "deterministic_cross_asset_regime_model",
    "regularised_linear_return_rank_model",
]
GATE_NAMES = [
    "positive_median_fold_net_active_return_vs_core22_equal_weight_benchmark",
    "positive_chronological_test_folds_at_least_3",
    "maximum_single_fold_share_of_total_active_return_lte_0_50",
    "aggregate_active_return_positive",
    "aggregate_maximum_drawdown_worsening_vs_benchmark_lte_0_03",
]

REQUIRED_LANGUAGE = [
    "This is a fail-closed integration of frozen GMA-7C development evidence.",
    "No return-score component met every predeclared stressed-10 bps gate.",
    "The fixed equal-weight GMA-7 ensemble is not constructed.",
    "The 2021-01-04 through 2026-05-01 GMA-7 model-specific lockbox remains unused.",
    "This is observed development evidence and not a pristine final holdout.",
    "No execution or promotion decision is produced.",
]

ENSEMBLE_STATUS = "not_constructed_no_fully_qualifying_return_score_components"
LOCKBOX_STATUS = "unused_preserved"
RISK_OVERLAY_STATUS = "not_integrated_without_a_fully_qualifying_return_score_component"
RETURN_BLOCK_STATUS = "not_eligible_for_fixed_equal_weight_ensemble"
DEVELOPMENT_STATE = "development_evidence_frozen_no_ensemble_eligible"
TEST_GUARD_SCOPE = "permits_named_GMA7B_files_only_while_continuing_to_block_GMA4_GMA5_GMA6_and_master_report_changes"

PARENT_ARTIFACTS = {
    "gma7a_contract": Path(
        "configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml"
    ),
    "gma7b_contract": Path(
        "configs/global_multi_asset_alpha/gma7b_etf_feature_store_contract_v1.yaml"
    ),
    "gma7c_contract": Path(
        "configs/global_multi_asset_alpha/gma7c_development_model_contract_v1.yaml"
    ),
    "gma7a_lock": Path("reports/global_multi_asset_alpha/gma7a_predictive_ensemble_lock_v1.json"),
    "gma7b_manifest": Path(
        "reports/global_multi_asset_alpha/gma7b_etf_feature_store_v1/gma7b_feature_store_manifest_v1.json"
    ),
    "gma7b_lock": Path(
        "reports/global_multi_asset_alpha/gma7b_etf_feature_store_v1/gma7b_feature_store_lock_v1.json"
    ),
    "gma7c_label_manifest": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_label_manifest_v1.json"
    ),
    "gma7c_execution_manifest": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_execution_manifest_v1.json"
    ),
    "gma7c_lock": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_lock_v1.json"
    ),
    "gma7c_gate_board": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_component_gate_board_v1.csv"
    ),
    "gma7c_component_metrics": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_component_development_metrics_v1.csv"
    ),
    "gma7c_risk_overlay_metrics": Path(
        "reports/global_multi_asset_alpha/gma7c_development_model_evaluation_v1/gma7c_risk_overlay_development_metrics_v1.csv"
    ),
}

OUTPUT_PATHS = {
    "config": Path(
        "configs/global_multi_asset_alpha/gma7d_development_gate_integration_contract_v1.yaml"
    ),
    "docs": Path("docs/global_multi_asset_alpha/gma7d_development_gate_integration_contract_v1.md"),
    "parent_verification": OUTPUT_DIR / "gma7d_parent_verification_v1.csv",
    "component_freeze_board": OUTPUT_DIR / "gma7d_component_freeze_board_v1.csv",
    "component_freeze_board_md": OUTPUT_DIR / "gma7d_component_freeze_board_v1.md",
    "no_ensemble_lock": OUTPUT_DIR / "gma7d_no_ensemble_lock_v1.json",
    "execution_manifest": OUTPUT_DIR / "gma7d_execution_manifest_v1.json",
}


class GMA7DIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class ParentEvidence:
    hashes: dict[str, str]
    gma7b_manifest: dict[str, Any]
    gma7b_lock: dict[str, Any]
    gma7c_contract: dict[str, Any]
    gma7c_label_manifest: dict[str, Any]
    gma7c_execution_manifest: dict[str, Any]
    gma7c_lock: dict[str, Any]
    gate_board: pd.DataFrame
    component_metrics: pd.DataFrame
    risk_overlay_metrics: pd.DataFrame


@dataclass(frozen=True)
class GMA7DResult:
    manifest: dict[str, Any]
    output_paths: dict[str, Path]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GMA7DIntegrationError(f"JSON parent artifact must be an object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GMA7DIntegrationError(f"YAML parent artifact must be an object: {path}")
    return payload


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise GMA7DIntegrationError(f"{name} mismatch: expected {expected!r}, got {actual!r}")


def load_parent_evidence(repo_root: Path = Path.cwd()) -> ParentEvidence:
    paths = {name: repo_root / relative for name, relative in PARENT_ARTIFACTS.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise GMA7DIntegrationError("Missing required parent artifact(s): " + ", ".join(missing))
    hashes = {name: sha256_file(path) for name, path in paths.items()}
    gate_board = pd.read_csv(paths["gma7c_gate_board"])
    component_metrics = pd.read_csv(paths["gma7c_component_metrics"])
    risk_overlay_metrics = pd.read_csv(paths["gma7c_risk_overlay_metrics"])
    evidence = ParentEvidence(
        hashes=hashes,
        gma7b_manifest=_read_json(paths["gma7b_manifest"]),
        gma7b_lock=_read_json(paths["gma7b_lock"]),
        gma7c_contract=_read_yaml(paths["gma7c_contract"]),
        gma7c_label_manifest=_read_json(paths["gma7c_label_manifest"]),
        gma7c_execution_manifest=_read_json(paths["gma7c_execution_manifest"]),
        gma7c_lock=_read_json(paths["gma7c_lock"]),
        gate_board=gate_board,
        component_metrics=component_metrics,
        risk_overlay_metrics=risk_overlay_metrics,
    )
    verify_parent_evidence(evidence)
    return evidence


def verify_parent_evidence(evidence: ParentEvidence) -> None:
    for payload_name, payload in [
        ("gma7b_manifest", evidence.gma7b_manifest),
        ("gma7b_lock", evidence.gma7b_lock),
        ("gma7c_label_manifest", evidence.gma7c_label_manifest),
        ("gma7c_execution_manifest", evidence.gma7c_execution_manifest),
        ("gma7c_lock", evidence.gma7c_lock),
    ]:
        _require_equal(
            f"{payload_name}.gma6_snapshot_manifest_hash",
            payload.get("gma6_snapshot_manifest_hash"),
            EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH,
        )
        _require_equal(
            f"{payload_name}.gma6b_data_bundle_manifest_hash",
            payload.get("gma6b_data_bundle_manifest_hash"),
            EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH,
        )
        _require_equal(
            f"{payload_name}.normalised_bundle_hash",
            payload.get("normalised_bundle_hash"),
            EXPECTED_NORMALISED_BUNDLE_HASH,
        )

    _require_equal(
        "gma7b_manifest.feature_row_count",
        evidence.gma7b_manifest.get("feature_row_count"),
        EXPECTED_GMA7B_FEATURE_ROWS,
    )
    _require_equal(
        "gma7b_manifest.missing_feature_row_count",
        evidence.gma7b_manifest.get("missing_feature_row_count"),
        EXPECTED_GMA7B_MISSING_FEATURE_ROWS,
    )
    _require_equal(
        "gma7c_label_manifest.label_row_count",
        evidence.gma7c_label_manifest.get("label_row_count"),
        EXPECTED_GMA7C_LABEL_ROWS,
    )
    _require_equal(
        "gma7c_execution_manifest.label_row_count",
        evidence.gma7c_execution_manifest.get("label_row_count"),
        EXPECTED_GMA7C_LABEL_ROWS,
    )
    _require_equal(
        "gma7c_execution_manifest.score_row_count",
        evidence.gma7c_execution_manifest.get("score_row_count"),
        EXPECTED_GMA7C_SCORE_ROWS,
    )
    _require_equal(
        "gma7c_execution_manifest.component_metric_row_count",
        evidence.gma7c_execution_manifest.get("component_metric_row_count"),
        EXPECTED_GMA7C_COMPONENT_METRIC_ROWS,
    )
    _require_equal(
        "gma7c_execution_manifest.risk_overlay_metric_row_count",
        evidence.gma7c_execution_manifest.get("risk_overlay_metric_row_count"),
        EXPECTED_GMA7C_RISK_METRIC_ROWS,
    )
    _require_equal(
        "gma7c_execution_manifest.gate_row_count",
        evidence.gma7c_execution_manifest.get("gate_row_count"),
        EXPECTED_GMA7C_GATE_ROWS,
    )
    _require_equal(
        "gma7c_component_metrics row count",
        len(evidence.component_metrics),
        EXPECTED_GMA7C_COMPONENT_METRIC_ROWS,
    )
    _require_equal(
        "gma7c_risk_overlay_metrics row count",
        len(evidence.risk_overlay_metrics),
        EXPECTED_GMA7C_RISK_METRIC_ROWS,
    )
    _require_equal(
        "gma7c_gate_board row count",
        len(evidence.gate_board),
        EXPECTED_GMA7C_GATE_ROWS,
    )
    _require_equal(
        "gma7c outer fold count",
        len(evidence.gma7c_contract.get("outer_folds", [])),
        EXPECTED_GMA7C_OUTER_FOLD_COUNT,
    )
    for payload_name, payload in [
        ("gma7c_label_manifest", evidence.gma7c_label_manifest),
        ("gma7c_execution_manifest", evidence.gma7c_execution_manifest),
        ("gma7c_lock", evidence.gma7c_lock),
    ]:
        _require_equal(f"{payload_name}.lockbox_used", payload.get("lockbox_used"), False)
    for payload_name, payload in [
        ("gma7c_execution_manifest", evidence.gma7c_execution_manifest),
        ("gma7c_lock", evidence.gma7c_lock),
    ]:
        _require_equal(
            f"{payload_name}.equal_weight_ensemble_built",
            payload.get("equal_weight_ensemble_built"),
            False,
        )
        _require_equal(
            f"{payload_name}.paper_broker_or_live_path_created",
            payload.get("paper_broker_or_live_path_created"),
            False,
        )
    _require_equal(
        "gma7c_execution_manifest.gma7a_test_guard_change_disclosure",
        evidence.gma7c_execution_manifest.get("gma7a_test_guard_change_disclosure"),
        True,
    )
    _require_equal(
        "gma7c_execution_manifest.gma7a_test_guard_change_scope",
        evidence.gma7c_execution_manifest.get("gma7a_test_guard_change_scope"),
        TEST_GUARD_SCOPE,
    )
    _require_gate_board_shape(evidence.gate_board)


def _require_gate_board_shape(gate_board: pd.DataFrame) -> None:
    required = {
        "model_id",
        "gate_name",
        "gate_status",
        "positive_chronological_test_folds",
        "single_fold_share",
        "aggregate_net_active_return",
    }
    missing = required - set(gate_board.columns)
    if missing:
        raise GMA7DIntegrationError(
            "Gate board missing required column(s): " + ", ".join(sorted(missing))
        )
    model_ids = sorted(gate_board["model_id"].unique().tolist())
    _require_equal("return-score model ids", model_ids, RETURN_MODEL_IDS)
    for model_id, group in gate_board.groupby("model_id", sort=True):
        _require_equal(f"{model_id} gate row count", len(group), len(GATE_NAMES))
        _require_equal(f"{model_id} gate names", group["gate_name"].tolist(), GATE_NAMES)
        if not set(group["gate_status"]).issubset({"pass", "fail"}):
            raise GMA7DIntegrationError(f"{model_id} has unsupported gate_status value")


def model_is_fully_qualifying(group: pd.DataFrame) -> bool:
    return bool((group["gate_status"] == "pass").all())


def build_component_freeze_board(evidence: ParentEvidence) -> pd.DataFrame:
    source_gate_hash = evidence.hashes["gma7c_gate_board"]
    rows: list[dict[str, Any]] = []
    for model_id, group in evidence.gate_board.groupby("model_id", sort=True):
        group = group.reset_index(drop=True)
        fully_qualifying = model_is_fully_qualifying(group)
        failed = group.loc[group["gate_status"] != "pass", "gate_name"].tolist()
        failed_evidence = group.loc[group["gate_status"] != "pass"].to_dict("records")
        rows.append(
            {
                "model_id": model_id,
                "gate_1_name": group.loc[0, "gate_name"],
                "gate_1_status": group.loc[0, "gate_status"],
                "gate_2_name": group.loc[1, "gate_name"],
                "gate_2_status": group.loc[1, "gate_status"],
                "gate_3_name": group.loc[2, "gate_name"],
                "gate_3_status": group.loc[2, "gate_status"],
                "gate_4_name": group.loc[3, "gate_name"],
                "gate_4_status": group.loc[3, "gate_status"],
                "gate_5_name": group.loc[4, "gate_name"],
                "gate_5_status": group.loc[4, "gate_status"],
                "failed_gate_names": ";".join(failed),
                "fully_qualifying_status": "fully_qualifying"
                if fully_qualifying
                else "not_fully_qualifying",
                "fixed_ensemble_integration_status": RETURN_BLOCK_STATUS,
                "failed_gate_source_evidence_json": json.dumps(
                    failed_evidence, sort_keys=True, separators=(",", ":")
                ),
                "source_gate_board_hash": source_gate_hash,
                "gma7c_development_scope_only": True,
                "lockbox_used": False,
            }
        )
    board = pd.DataFrame(rows)
    fully_qualifying_count = int((board["fully_qualifying_status"] == "fully_qualifying").sum())
    _require_equal(
        "fully qualifying return-score component count",
        fully_qualifying_count,
        EXPECTED_FULLY_QUALIFYING_COUNT,
    )
    if (board["fixed_ensemble_integration_status"] != RETURN_BLOCK_STATUS).any():
        raise GMA7DIntegrationError(
            "Frozen source outcome unexpectedly permits ensemble construction"
        )
    return board


def build_parent_verification(evidence: ParentEvidence) -> pd.DataFrame:
    rows = []
    for artifact_id, relative_path in PARENT_ARTIFACTS.items():
        rows.append(
            {
                "artifact_id": artifact_id,
                "relative_path": relative_path.as_posix(),
                "sha256": evidence.hashes[artifact_id],
                "verification_status": "verified",
                "gma7a_test_guard_change_disclosure": True,
                "gma7a_test_guard_change_scope": TEST_GUARD_SCOPE,
            }
        )
    return pd.DataFrame(rows)


def build_no_ensemble_lock(evidence: ParentEvidence, freeze_board: pd.DataFrame) -> dict[str, Any]:
    fully_qualifying_count = int(
        (freeze_board["fully_qualifying_status"] == "fully_qualifying").sum()
    )
    _require_equal("fully qualifying component count", fully_qualifying_count, 0)
    return {
        "phase_id": PHASE_ID,
        "required_language": REQUIRED_LANGUAGE,
        "gma7_v1_development_state": DEVELOPMENT_STATE,
        "gma7a_contract_hash": evidence.hashes["gma7a_contract"],
        "gma7a_lock_hash": evidence.hashes["gma7a_lock"],
        "gma7b_contract_hash": evidence.hashes["gma7b_contract"],
        "gma7b_manifest_hash": evidence.hashes["gma7b_manifest"],
        "gma7b_lock_hash": evidence.hashes["gma7b_lock"],
        "gma7c_contract_hash": evidence.hashes["gma7c_contract"],
        "gma7c_label_manifest_hash": evidence.hashes["gma7c_label_manifest"],
        "gma7c_execution_manifest_hash": evidence.hashes["gma7c_execution_manifest"],
        "gma7c_lock_hash": evidence.hashes["gma7c_lock"],
        "gma7c_gate_board_hash": evidence.hashes["gma7c_gate_board"],
        "core22_universe_hash": evidence.gma7b_manifest["core22_universe_hash"],
        "feature_store_hash": evidence.gma7b_manifest["monthly_feature_store_hash"],
        "component_count": int(len(freeze_board)),
        "fully_qualifying_component_count": fully_qualifying_count,
        "ensemble_status": ENSEMBLE_STATUS,
        "lockbox_status": LOCKBOX_STATUS,
        "risk_overlay_integration_status": RISK_OVERLAY_STATUS,
        "no_model_fit_performed": True,
        "no_score_generation_performed": True,
        "no_performance_calculation_performed": True,
        "no_paper_broker_or_live_path_created": True,
        "gma7a_test_guard_change_disclosure": True,
        "gma7a_test_guard_change_scope": TEST_GUARD_SCOPE,
    }


def build_execution_manifest(
    evidence: ParentEvidence, freeze_board: pd.DataFrame, no_ensemble_lock: dict[str, Any]
) -> dict[str, Any]:
    return {
        **no_ensemble_lock,
        "parent_artifact_count": len(PARENT_ARTIFACTS),
        "gate_row_count": int(len(evidence.gate_board)),
        "component_metric_row_count": int(len(evidence.component_metrics)),
        "risk_overlay_metric_row_count": int(len(evidence.risk_overlay_metrics)),
        "return_score_block_status_values": sorted(
            freeze_board["fixed_ensemble_integration_status"].unique().tolist()
        ),
    }


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame[columns].to_dict("records"):
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def write_component_freeze_markdown(path: Path, freeze_board: pd.DataFrame) -> None:
    lines = [
        "# GMA-7D Component Freeze Board V1",
        "",
        *REQUIRED_LANGUAGE,
        "",
        markdown_table(
            freeze_board,
            [
                "model_id",
                "failed_gate_names",
                "fully_qualifying_status",
                "fixed_ensemble_integration_status",
                "lockbox_used",
            ],
        ),
        "",
        f"Programme-level ensemble status: `{ENSEMBLE_STATUS}`.",
        f"Risk-overlay integration status: `{RISK_OVERLAY_STATUS}`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_contract_yaml() -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "evidence_class": "fail_closed_frozen_development_evidence_integration",
        "required_language": REQUIRED_LANGUAGE,
        "source_inputs": {key: value.as_posix() for key, value in PARENT_ARTIFACTS.items()},
        "return_score_block_status": RETURN_BLOCK_STATUS,
        "programme_level_ensemble_status": ENSEMBLE_STATUS,
        "lockbox_status": LOCKBOX_STATUS,
        "risk_overlay_integration_status": RISK_OVERLAY_STATUS,
        "gma7_v1_development_state": DEVELOPMENT_STATE,
        "prohibited_actions": {
            "model_refit": True,
            "model_selection_rerun": True,
            "label_generation": True,
            "score_generation": True,
            "portfolio_performance_recalculation": True,
            "ensemble_construction": True,
            "lockbox_access": True,
            "paper_broker_or_live_path_creation": True,
        },
    }


def write_contract_files(repo_root: Path) -> None:
    config_path = repo_root / OUTPUT_PATHS["config"]
    docs_path = repo_root / OUTPUT_PATHS["docs"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(build_contract_yaml(), sort_keys=False), encoding="utf-8")
    docs_path.write_text(
        "\n".join(
            [
                "# GMA-7D Development Gate Integration Contract V1",
                "",
                *REQUIRED_LANGUAGE,
                "",
                "GMA-7D consumes frozen GMA-7A, GMA-7B, and GMA-7C artifacts only. It reads the precomputed GMA-7C gate board directly and fails closed if parent hashes, counts, lockbox state, or gate row structure differ from the frozen evidence contract.",
                "",
                f"Programme-level ensemble status: `{ENSEMBLE_STATUS}`.",
                f"Risk-overlay integration status: `{RISK_OVERLAY_STATUS}`.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def generate_gate_integration_files(repo_root: Path = Path.cwd()) -> GMA7DResult:
    evidence = load_parent_evidence(repo_root)
    parent_verification = build_parent_verification(evidence)
    freeze_board = build_component_freeze_board(evidence)
    no_ensemble_lock = build_no_ensemble_lock(evidence, freeze_board)
    manifest = build_execution_manifest(evidence, freeze_board, no_ensemble_lock)
    write_contract_files(repo_root)
    write_csv(repo_root / OUTPUT_PATHS["parent_verification"], parent_verification)
    write_csv(repo_root / OUTPUT_PATHS["component_freeze_board"], freeze_board)
    write_component_freeze_markdown(
        repo_root / OUTPUT_PATHS["component_freeze_board_md"], freeze_board
    )
    write_json(repo_root / OUTPUT_PATHS["no_ensemble_lock"], no_ensemble_lock)
    write_json(repo_root / OUTPUT_PATHS["execution_manifest"], manifest)
    return GMA7DResult(
        manifest=manifest,
        output_paths={key: repo_root / value for key, value in OUTPUT_PATHS.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GMA-7D frozen gate integration records")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = generate_gate_integration_files(args.repo_root)
    print(f"phase_id={PHASE_ID}")
    print(f"component_count={result.manifest['component_count']}")
    print(f"fully_qualifying_component_count={result.manifest['fully_qualifying_component_count']}")
    print(f"ensemble_status={result.manifest['ensemble_status']}")
    print(f"lockbox_status={result.manifest['lockbox_status']}")
    for key, path in sorted(result.output_paths.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
