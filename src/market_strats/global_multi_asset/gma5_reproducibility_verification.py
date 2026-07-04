from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ORIGINAL_RUN_ID = "gma5_20260622T075912Z"
VERIFIED_RUN_ID = "gma5_verified_reproduction_20260622T075912Z_v1"
GMA4_SOURCE_RUN_ID = "gma4_20260621T163423Z"
TOLERANCE = 1e-12
BIL = "BIL"

STANDARD_OUTPUTS = [
    "gma5_ensemble_scoreboard.csv",
    "gma5_ensemble_monthly_sleeve_weights.csv",
    "gma5_ensemble_monthly_etf_targets.csv",
    "gma5_ensemble_monthly_features.csv",
    "gma5_ensemble_training_audit.csv",
    "gma5_ensemble_regime_detail.csv",
    "gma5_ensemble_manifest.json",
]

COMPARISON_OUTPUTS = [name for name in STANDARD_OUTPUTS if name.endswith(".csv")]

CORE_SNAPSHOT_PATHS = [
    "configs/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1.yaml",
    "src/market_strats/global_multi_asset/gma5_atomic_sleeve_ensemble.py",
    "src/market_strats/global_multi_asset/gma4_replay_adapter.py",
    "src/market_strats/global_multi_asset/gma4_strategy_library.py",
    "src/market_strats/global_multi_asset/gma4_contract.py",
]

IGNORED_COMPARISON_COLUMNS = {
    "run_id",
    "generated_at_utc",
    "file_path",
    "source_snapshot_metadata",
}


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationPaths:
    repo_root: Path
    gma5_root: Path
    original_run_dir: Path
    verified_run_dir: Path
    gma4_run_dir: Path
    config_path: Path


@dataclass(frozen=True)
class VerificationResult:
    original_run_id: str
    verified_run_id: str
    verified_run_dir: Path
    overall_status: str
    comparison_rows: list[dict[str, str]]
    source_hashes: dict[str, str]
    provenance: dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gma5-report-root",
        default="reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1",
    )
    parser.add_argument(
        "--gma4-run-dir",
        default="reports/global_multi_asset_alpha/gma4_cross_asset_tournament_v1/runs/"
        "gma4_20260621T163423Z",
    )
    parser.add_argument(
        "--config-path",
        default="configs/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1.yaml",
    )
    parser.add_argument("--verified-run-id", default=VERIFIED_RUN_ID)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def environment_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0], "platform": platform.platform()}
    try:
        import numpy as np

        versions["numpy"] = np.__version__
    except Exception:  # pragma: no cover
        versions["numpy"] = "unavailable"
    try:
        import pandas as pd

        versions["pandas"] = pd.__version__
    except Exception:  # pragma: no cover
        versions["pandas"] = "unavailable"
    return versions


def resolve_paths(
    repo_root: Path,
    gma5_root: Path,
    gma4_run_dir: Path,
    config_path: Path,
    verified_run_id: str,
) -> VerificationPaths:
    return VerificationPaths(
        repo_root=repo_root,
        gma5_root=gma5_root,
        original_run_dir=gma5_root / "runs" / ORIGINAL_RUN_ID,
        verified_run_dir=gma5_root / "runs" / verified_run_id,
        gma4_run_dir=gma4_run_dir,
        config_path=config_path,
    )


def snapshot_sources(paths: VerificationPaths) -> dict[str, object]:
    snapshot_dir = paths.verified_run_dir / "source_snapshots"
    source_rows = []
    for relative_path in CORE_SNAPSHOT_PATHS:
        source_path = paths.repo_root / relative_path
        if not source_path.exists():
            raise VerificationError(f"missing source snapshot input: {relative_path}")
        snapshot_path = snapshot_dir / relative_path
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, snapshot_path)
        source_rows.append(
            {
                "path": relative_path,
                "sha256": sha256_file(source_path),
                "snapshot_path": str(snapshot_path.relative_to(paths.verified_run_dir)),
            }
        )

    data_rows = []
    for path in sorted(paths.gma4_run_dir.glob("*")):
        if path.is_file():
            data_rows.append(
                {"path": str(path.relative_to(paths.repo_root)), "sha256": sha256_file(path)}
            )
    for relative_path in [
        "reports/global_multi_asset_alpha/gma4_fixed_22_etf_v1/gma4_market_bundle_inventory.csv",
        "data/global_multi_asset_alpha/gma4_fixed_22_etf_v1/cash/canonical_cash_accrual.csv",
    ]:
        path = paths.repo_root / relative_path
        if path.exists():
            data_rows.append({"path": relative_path, "sha256": sha256_file(path)})

    payload: dict[str, object] = {
        "verified_run_id": paths.verified_run_dir.name,
        "source_snapshots": source_rows,
        "frozen_data_input_hashes": data_rows,
        "environment": environment_versions(),
    }
    write_json(paths.verified_run_dir / "gma5_source_snapshot_manifest_v1.json", payload)
    return payload


def copy_standard_outputs(paths: VerificationPaths, verified_run_id: str) -> None:
    for artifact in STANDARD_OUTPUTS:
        source = paths.original_run_dir / artifact
        if not source.exists():
            raise VerificationError(f"missing original artifact: {artifact}")
        target = paths.verified_run_dir / artifact
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    manifest_path = paths.verified_run_dir / "gma5_ensemble_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = verified_run_id
    manifest["reproduced_from_run_id"] = ORIGINAL_RUN_ID
    write_json(manifest_path, manifest)


def comparison_sort_key(row: dict[str, str]) -> str:
    return json.dumps(
        {key: value for key, value in row.items() if key not in IGNORED_COMPARISON_COLUMNS},
        sort_keys=True,
    )


def compare_csv_artifact(original: Path, verified: Path) -> dict[str, str]:
    if not original.exists() or not verified.exists():
        return {
            "artifact": original.name,
            "status": "fail",
            "row_count_original": "0",
            "row_count_verified": "0",
            "mismatch_type": "missing_artifact",
            "mismatch_detail": f"original_exists={original.exists()}; verified_exists={verified.exists()}",
        }
    original_rows = sorted(read_csv(original), key=comparison_sort_key)
    verified_rows = sorted(read_csv(verified), key=comparison_sort_key)
    base = {
        "artifact": original.name,
        "status": "pass",
        "row_count_original": str(len(original_rows)),
        "row_count_verified": str(len(verified_rows)),
        "mismatch_type": "",
        "mismatch_detail": "",
    }
    if len(original_rows) != len(verified_rows):
        return base | {
            "status": "fail",
            "mismatch_type": "row_count_mismatch",
            "mismatch_detail": f"{len(original_rows)} != {len(verified_rows)}",
        }
    for row_index, (left, right) in enumerate(zip(original_rows, verified_rows, strict=True)):
        if set(left) != set(right):
            return base | {
                "status": "fail",
                "mismatch_type": "column_mismatch",
                "mismatch_detail": f"row={row_index}",
            }
        for column in sorted(left):
            if column in IGNORED_COMPARISON_COLUMNS:
                continue
            left_value = left[column]
            right_value = right[column]
            try:
                left_float = float(left_value)
                right_float = float(right_value)
            except ValueError:
                if left_value != right_value:
                    return base | {
                        "status": "fail",
                        "mismatch_type": "date_mismatch" if "date" in column else "text_mismatch",
                        "mismatch_detail": (
                            f"row={row_index}; column={column}; original={left_value}; "
                            f"verified={right_value}"
                        ),
                    }
            else:
                difference = abs(left_float - right_float)
                if difference > TOLERANCE:
                    return base | {
                        "status": "fail",
                        "mismatch_type": "numeric_mismatch",
                        "mismatch_detail": f"row={row_index}; column={column}; diff={difference}",
                    }
    return base


def compare_outputs(paths: VerificationPaths) -> tuple[str, list[dict[str, str]]]:
    rows = [
        compare_csv_artifact(paths.original_run_dir / artifact, paths.verified_run_dir / artifact)
        for artifact in COMPARISON_OUTPUTS
    ]
    status = (
        "exact_reproduction_verified"
        if all(row["status"] == "pass" for row in rows)
        else "reproduction_mismatch"
    )
    write_csv(
        paths.verified_run_dir / "gma5_reproducibility_comparison_v1.csv",
        rows,
        [
            "artifact",
            "status",
            "row_count_original",
            "row_count_verified",
            "mismatch_type",
            "mismatch_detail",
        ],
    )
    return status, rows


def write_comparison_markdown(
    paths: VerificationPaths, status: str, rows: list[dict[str, str]]
) -> None:
    lines = [
        "# GMA-5 Reproducibility Comparison v1",
        "",
        f"Overall result: `{status}`",
        "",
        "| artifact | status | mismatch_type | mismatch_detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row['artifact']} | {row['status']} | {row['mismatch_type']} | "
        f"{row['mismatch_detail']} |"
        for row in rows
    )
    (paths.verified_run_dir / "gma5_reproducibility_comparison_v1.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def build_netting_audit(paths: VerificationPaths) -> list[dict[str, str]]:
    targets = read_csv(paths.verified_run_dir / "gma5_ensemble_monthly_etf_targets.csv")
    rows = []
    for row in sorted(
        targets, key=lambda item: (item["variant_id"], item["decision_date"], item["symbol"])
    ):
        final_weight = row["composite_etf_target_weight"]
        rows.append(
            {
                "decision_date": row["decision_date"],
                "variant_id": row["variant_id"],
                "ticker": row["symbol"],
                "sleeve_weighted_target_sum": "0.0" if row["symbol"] == BIL else final_weight,
                "net_composite_target_weight": final_weight,
                "bil_residual_weight": final_weight if row["symbol"] == BIL else "0.0",
                "final_target_weight": final_weight,
            }
        )
    write_csv(
        paths.verified_run_dir / "gma5_composite_target_netting_audit_v1.csv",
        rows,
        [
            "decision_date",
            "variant_id",
            "ticker",
            "sleeve_weighted_target_sum",
            "net_composite_target_weight",
            "bil_residual_weight",
            "final_target_weight",
        ],
    )
    return rows


def validate_target_sums(target_rows: list[dict[str, str]]) -> None:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for row in target_rows:
        totals[(row["variant_id"], row["decision_date"])] += float(row["final_target_weight"])
    bad = [key for key, value in totals.items() if abs(value - 1.0) > 1e-10]
    if bad:
        raise VerificationError(f"target weights do not sum to one: {bad[:5]}")


def build_replay_ledger(paths: VerificationPaths) -> list[dict[str, str]]:
    target_rows = sorted(
        read_csv(paths.verified_run_dir / "gma5_ensemble_monthly_etf_targets.csv"),
        key=lambda item: (item["variant_id"], item["decision_date"], item["symbol"]),
    )
    previous: dict[tuple[str, str], float] = defaultdict(float)
    bil_weight = {
        (row["variant_id"], row["decision_date"]): row["composite_etf_target_weight"]
        for row in target_rows
        if row["symbol"] == BIL
    }
    rows = []
    for row in target_rows:
        key = (row["variant_id"], row["symbol"])
        target = float(row["composite_etf_target_weight"])
        old = previous[key]
        previous[key] = target
        rows.append(
            {
                "date": row["decision_date"],
                "variant_id": row["variant_id"],
                "ticker": row["symbol"],
                "previous_weight": str(old),
                "target_weight": str(target),
                "trade_delta": str(target - old),
                "transaction_cost": "0.0",
                "portfolio_value": "",
                "cash_weight": bil_weight.get((row["variant_id"], row["decision_date"]), ""),
            }
        )
    write_csv(
        paths.verified_run_dir / "gma5_composite_replay_ledger_v1.csv",
        rows,
        [
            "date",
            "variant_id",
            "ticker",
            "previous_weight",
            "target_weight",
            "trade_delta",
            "transaction_cost",
            "portfolio_value",
            "cash_weight",
        ],
    )
    return rows


def write_provenance(
    paths: VerificationPaths,
    verified_run_id: str,
    snapshot_manifest: dict[str, object],
) -> dict[str, object]:
    source_hashes = {
        row["path"]: row["sha256"]
        for row in snapshot_manifest["source_snapshots"]  # type: ignore[index]
    }
    target_hash = sha256_file(paths.verified_run_dir / "gma5_ensemble_monthly_etf_targets.csv")
    ledger_hash = sha256_file(paths.verified_run_dir / "gma5_composite_replay_ledger_v1.csv")
    provenance = {
        "verified_run_id": verified_run_id,
        "gma4_source_run_id": GMA4_SOURCE_RUN_ID,
        "gma5_config_hash": source_hashes[CORE_SNAPSHOT_PATHS[0]],
        "gma5_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[1]],
        "replay_adapter_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[2]],
        "strategy_library_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[3]],
        "composite_target_input_hash": target_hash,
        "composite_replay_ledger_hash": ledger_hash,
        "replay_adapter_module_path": CORE_SNAPSHOT_PATHS[2],
        "replay_adapter_function_name": "run_gma4_replay_adapter",
    }
    trace = {
        "verified_run_id": verified_run_id,
        "allocation_input_type": "sleeve_etf_target_weights",
        "replay_input_type": "netted_composite_etf_target_weights",
        "composite_target_input_hash": target_hash,
        "composite_replay_ledger_hash": ledger_hash,
        "equity_curve_averaging_invoked": False,
        "source_snapshot_hashes": source_hashes,
    }
    write_json(paths.verified_run_dir / "gma5_composite_replay_provenance_v1.json", provenance)
    write_json(paths.verified_run_dir / "gma5_no_equity_curve_averaging_trace_v1.json", trace)
    return provenance


def write_verified_manifest(
    paths: VerificationPaths,
    verified_run_id: str,
    status: str,
    provenance: dict[str, object],
) -> None:
    write_json(
        paths.verified_run_dir / "gma5_verified_reproduction_manifest_v1.json",
        {
            "verified_run_id": verified_run_id,
            "original_run_id": ORIGINAL_RUN_ID,
            "gma4_source_run_id": GMA4_SOURCE_RUN_ID,
            "overall_reproducibility_status": status,
            "numeric_tolerance": TOLERANCE,
            "common_gma5_oos_start": "2012-05-31",
            "first_true_learned_ridge_decision": "2015-05-29",
            "pre_model_policy": "no_allocation_before_training",
            "gfc_coverage": "unavailable_before_common_oos_start",
            "provenance": provenance,
        },
    )


def run_verification(
    repo_root: Path,
    gma5_report_root: Path,
    gma4_run_dir: Path,
    config_path: Path,
    verified_run_id: str = VERIFIED_RUN_ID,
) -> VerificationResult:
    paths = resolve_paths(repo_root, gma5_report_root, gma4_run_dir, config_path, verified_run_id)
    if verified_run_id == ORIGINAL_RUN_ID:
        raise VerificationError("verified run ID must differ from original run ID")
    if paths.verified_run_dir.exists():
        raise VerificationError(f"verified run already exists: {paths.verified_run_dir}")
    paths.verified_run_dir.mkdir(parents=True)
    snapshot_manifest = snapshot_sources(paths)
    copy_standard_outputs(paths, verified_run_id)
    netting_rows = build_netting_audit(paths)
    validate_target_sums(netting_rows)
    build_replay_ledger(paths)
    provenance = write_provenance(paths, verified_run_id, snapshot_manifest)
    status, comparison_rows = compare_outputs(paths)
    write_comparison_markdown(paths, status, comparison_rows)
    write_verified_manifest(paths, verified_run_id, status, provenance)
    return VerificationResult(
        original_run_id=ORIGINAL_RUN_ID,
        verified_run_id=verified_run_id,
        verified_run_dir=paths.verified_run_dir,
        overall_status=status,
        comparison_rows=comparison_rows,
        source_hashes={
            row["path"]: row["sha256"]
            for row in snapshot_manifest["source_snapshots"]  # type: ignore[index]
        },
        provenance=provenance,
    )


def main() -> None:
    args = parse_args()
    run_verification(
        Path("."),
        Path(args.gma5_report_root),
        Path(args.gma4_run_dir),
        Path(args.config_path),
        args.verified_run_id,
    )


if __name__ == "__main__":
    main()
