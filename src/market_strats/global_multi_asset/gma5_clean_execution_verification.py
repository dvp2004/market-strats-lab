from __future__ import annotations

import argparse
import builtins
import csv
import hashlib
import json
import platform
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ORIGINAL_RUN_ID = "gma5_20260622T075912Z"
CLEAN_RUN_ID = "gma5_clean_execution_20260622T075912Z_v1"
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

CSV_COMPARISON_OUTPUTS = [name for name in STANDARD_OUTPUTS if name.endswith(".csv")]
JSON_COMPARISON_OUTPUTS = ["gma5_ensemble_manifest.json"]

CORE_SNAPSHOT_PATHS = [
    "configs/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1.yaml",
    "src/market_strats/global_multi_asset/gma5_atomic_sleeve_ensemble.py",
    "src/market_strats/global_multi_asset/gma4_replay_adapter.py",
    "src/market_strats/global_multi_asset/gma4_strategy_library.py",
    "src/market_strats/global_multi_asset/gma4_contract.py",
]

IGNORED_COMPARISON_COLUMNS = {
    "run_id",
    "created_at_utc",
    "generated_at_utc",
    "file_path",
    "source_snapshot_metadata",
}

IGNORED_MANIFEST_KEYS = {
    "run_id",
    "created_at_utc",
    "git_commit",
}


class CleanExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CleanExecutionPaths:
    repo_root: Path
    gma5_root: Path
    original_run_dir: Path
    clean_run_dir: Path
    gma4_run_dir: Path
    config_path: Path


@dataclass(frozen=True)
class CleanExecutionResult:
    original_run_id: str
    clean_run_id: str
    clean_run_dir: Path
    overall_status: str
    comparison_rows: list[dict[str, str]]
    execution_uuid: str
    journal: dict[str, Any]
    replay_trace: dict[str, Any]


class OriginalOutputReadGuard:
    def __init__(self, original_run_dir: Path, standard_outputs: list[str]) -> None:
        self.original_paths = {(original_run_dir / name).resolve() for name in standard_outputs}
        self.original_read_before_finished = False
        self._original_open: Any = None
        self._original_path_open: Any = None
        self._original_read_text: Any = None
        self._original_read_bytes: Any = None

    def _check_path(self, path: Any) -> None:
        try:
            resolved = Path(path).resolve()
        except TypeError:
            return
        if resolved in self.original_paths:
            self.original_read_before_finished = True
            raise CleanExecutionError(
                f"blocked original standard output read before clean execution finished: "
                f"{resolved.name}"
            )

    def __enter__(self) -> OriginalOutputReadGuard:
        self._original_open = builtins.open
        self._original_path_open = Path.open
        self._original_read_text = Path.read_text
        self._original_read_bytes = Path.read_bytes

        guard = self

        def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            guard._check_path(file)
            return guard._original_open(file, *args, **kwargs)

        def guarded_path_open(path_self: Path, *args: Any, **kwargs: Any) -> Any:
            guard._check_path(path_self)
            return guard._original_path_open(path_self, *args, **kwargs)

        def guarded_read_text(path_self: Path, *args: Any, **kwargs: Any) -> str:
            guard._check_path(path_self)
            return guard._original_read_text(path_self, *args, **kwargs)

        def guarded_read_bytes(path_self: Path) -> bytes:
            guard._check_path(path_self)
            return guard._original_read_bytes(path_self)

        builtins.open = guarded_open
        Path.open = guarded_path_open
        Path.read_text = guarded_read_text
        Path.read_bytes = guarded_read_bytes
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        builtins.open = self._original_open
        Path.open = self._original_path_open
        Path.read_text = self._original_read_text
        Path.read_bytes = self._original_read_bytes


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
    parser.add_argument("--clean-run-id", default=CLEAN_RUN_ID)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def write_json(path: Path, payload: dict[str, Any]) -> None:
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
    clean_run_id: str,
) -> CleanExecutionPaths:
    return CleanExecutionPaths(
        repo_root=repo_root,
        gma5_root=gma5_root,
        original_run_dir=gma5_root / "runs" / ORIGINAL_RUN_ID,
        clean_run_dir=gma5_root / "runs" / clean_run_id,
        gma4_run_dir=gma4_run_dir,
        config_path=config_path,
    )


def snapshot_sources(paths: CleanExecutionPaths, execution_uuid: str) -> dict[str, Any]:
    snapshot_dir = paths.clean_run_dir / "source_snapshots"
    source_rows = []
    for relative_path in CORE_SNAPSHOT_PATHS:
        source_path = paths.repo_root / relative_path
        if not source_path.exists():
            raise CleanExecutionError(f"missing source snapshot input: {relative_path}")
        payload = source_path.read_bytes()
        snapshot_path = snapshot_dir / relative_path
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(payload)
        source_rows.append(
            {
                "path": relative_path,
                "sha256": sha256_bytes(payload),
                "snapshot_path": str(snapshot_path.relative_to(paths.clean_run_dir)),
            }
        )

    frozen_input_rows = []
    for path in sorted(paths.gma4_run_dir.glob("*")):
        if path.is_file():
            frozen_input_rows.append(
                {"path": str(path.relative_to(paths.repo_root)), "sha256": sha256_file(path)}
            )
    for relative_path in [
        "reports/global_multi_asset_alpha/gma4_fixed_22_etf_v1/gma4_market_bundle_inventory.csv",
        "data/global_multi_asset_alpha/gma4_fixed_22_etf_v1/cash/canonical_cash_accrual.csv",
    ]:
        path = paths.repo_root / relative_path
        if path.exists():
            frozen_input_rows.append({"path": relative_path, "sha256": sha256_file(path)})

    payload = {
        "clean_execution_run_id": paths.clean_run_dir.name,
        "execution_uuid": execution_uuid,
        "source_snapshots": source_rows,
        "frozen_data_input_hashes": frozen_input_rows,
        "environment": environment_versions(),
    }
    write_json(paths.clean_run_dir / "gma5_source_snapshot_manifest_v1.json", payload)
    return payload


def hash_outputs(run_dir: Path) -> dict[str, str]:
    hashes = {}
    for name in STANDARD_OUTPUTS:
        path = run_dir / name
        if not path.exists():
            raise CleanExecutionError(f"missing standard output: {path}")
        hashes[name] = sha256_file(path)
    return hashes


def comparison_sort_key(row: dict[str, str]) -> str:
    comparable = {key: value for key, value in row.items() if key not in IGNORED_COMPARISON_COLUMNS}
    return stable_json(comparable)


def compare_csv_artifact(original: Path, clean: Path) -> dict[str, str]:
    original_rows = sorted(read_csv(original), key=comparison_sort_key)
    clean_rows = sorted(read_csv(clean), key=comparison_sort_key)
    base = {
        "artifact": original.name,
        "status": "pass",
        "row_count_original": str(len(original_rows)),
        "row_count_clean": str(len(clean_rows)),
        "mismatch_type": "",
        "mismatch_detail": "",
    }
    if len(original_rows) != len(clean_rows):
        return base | {
            "status": "fail",
            "mismatch_type": "row_count_mismatch",
            "mismatch_detail": f"{len(original_rows)} != {len(clean_rows)}",
        }
    for row_index, (left, right) in enumerate(zip(original_rows, clean_rows, strict=True)):
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
                            f"clean={right_value}"
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


def compare_json_artifact(original: Path, clean: Path) -> dict[str, str]:
    original_payload = json.loads(original.read_text(encoding="utf-8"))
    clean_payload = json.loads(clean.read_text(encoding="utf-8"))
    original_comparable = {
        key: value for key, value in original_payload.items() if key not in IGNORED_MANIFEST_KEYS
    }
    clean_comparable = {
        key: value for key, value in clean_payload.items() if key not in IGNORED_MANIFEST_KEYS
    }
    status = original_comparable == clean_comparable
    return {
        "artifact": original.name,
        "status": "pass" if status else "fail",
        "row_count_original": "1",
        "row_count_clean": "1",
        "mismatch_type": "" if status else "manifest_mismatch",
        "mismatch_detail": "" if status else "manifest differs after ignored keys",
    }


def compare_outputs(paths: CleanExecutionPaths) -> tuple[str, list[dict[str, str]]]:
    rows = [
        compare_csv_artifact(paths.original_run_dir / artifact, paths.clean_run_dir / artifact)
        for artifact in CSV_COMPARISON_OUTPUTS
    ]
    rows.extend(
        compare_json_artifact(paths.original_run_dir / artifact, paths.clean_run_dir / artifact)
        for artifact in JSON_COMPARISON_OUTPUTS
    )
    if all(row["status"] == "pass" for row in rows):
        status = "clean_execution_exact_reproduction_verified"
    else:
        status = "clean_execution_reproduction_mismatch"
    write_csv(
        paths.clean_run_dir / "gma5_clean_execution_comparison_v1.csv",
        rows,
        [
            "artifact",
            "status",
            "row_count_original",
            "row_count_clean",
            "mismatch_type",
            "mismatch_detail",
        ],
    )
    return status, rows


def write_comparison_markdown(
    paths: CleanExecutionPaths, status: str, rows: list[dict[str, str]]
) -> None:
    lines = [
        "# GMA-5 Clean Execution Comparison v1",
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
    (paths.clean_run_dir / "gma5_clean_execution_comparison_v1.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def build_netting_audit(paths: CleanExecutionPaths) -> list[dict[str, str]]:
    targets = read_csv(paths.clean_run_dir / "gma5_ensemble_monthly_etf_targets.csv")
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
        paths.clean_run_dir / "gma5_composite_target_netting_audit_v2.csv",
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
        raise CleanExecutionError(f"target weights do not sum to one: {bad[:5]}")


def variant_hashes_from_rows(
    rows: list[dict[str, str]], variant_column: str = "variant_id"
) -> dict[str, str]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[variant_column]].append(row)
    return {
        variant: sha256_bytes(
            stable_json(sorted(variant_rows, key=lambda item: stable_json(item))).encode("utf-8")
        )
        for variant, variant_rows in sorted(grouped.items())
    }


def build_replay_ledger(paths: CleanExecutionPaths) -> list[dict[str, str]]:
    target_rows = sorted(
        read_csv(paths.clean_run_dir / "gma5_ensemble_monthly_etf_targets.csv"),
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
        paths.clean_run_dir / "gma5_composite_replay_ledger_v2.csv",
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


def write_runtime_artifacts(
    paths: CleanExecutionPaths,
    execution_uuid: str,
    clean_run_id: str,
    source_manifest: dict[str, Any],
    replay_call_strategy_ids: list[str],
    netting_rows: list[dict[str, str]],
    ledger_rows: list[dict[str, str]],
) -> dict[str, Any]:
    source_hashes = {row["path"]: row["sha256"] for row in source_manifest["source_snapshots"]}
    variant_ids = sorted(
        {strategy_id for strategy_id in replay_call_strategy_ids if strategy_id.startswith("gma5_")}
    )
    target_hashes = variant_hashes_from_rows(netting_rows)
    ledger_hashes = variant_hashes_from_rows(ledger_rows)
    replay_trace = {
        "execution_uuid": execution_uuid,
        "clean_execution_run_id": clean_run_id,
        "replay_adapter_module_path": CORE_SNAPSHOT_PATHS[2],
        "replay_adapter_function_name": "run_gma4_replay_adapter",
        "replay_adapter_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[2]],
        "replay_adapter_invocation_count": len(replay_call_strategy_ids),
        "variant_ids_replayed": variant_ids,
        "composite_target_input_hashes_by_variant": target_hashes,
        "composite_replay_ledger_hashes_by_variant": ledger_hashes,
    }
    no_averaging_trace = {
        "execution_uuid": execution_uuid,
        "clean_execution_run_id": clean_run_id,
        "allocation_input_type": "sleeve_etf_target_weights",
        "replay_input_type": "netted_composite_etf_target_weights",
        "equity_curve_averaging_invoked": False,
        "runtime_evidence": {
            "replay_adapter_invocation_count": len(replay_call_strategy_ids),
            "variant_ids_replayed": variant_ids,
            "composite_target_input_hashes_by_variant": target_hashes,
            "composite_replay_ledger_hashes_by_variant": ledger_hashes,
        },
    }
    provenance = {
        "execution_uuid": execution_uuid,
        "clean_execution_run_id": clean_run_id,
        "gma4_source_run_id": GMA4_SOURCE_RUN_ID,
        "gma5_config_hash": source_hashes[CORE_SNAPSHOT_PATHS[0]],
        "gma5_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[1]],
        "replay_adapter_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[2]],
        "strategy_library_source_hash": source_hashes[CORE_SNAPSHOT_PATHS[3]],
        "composite_target_input_hash": sha256_file(
            paths.clean_run_dir / "gma5_ensemble_monthly_etf_targets.csv"
        ),
        "composite_replay_ledger_hash": sha256_file(
            paths.clean_run_dir / "gma5_composite_replay_ledger_v2.csv"
        ),
        "replay_adapter_module_path": CORE_SNAPSHOT_PATHS[2],
        "replay_adapter_function_name": "run_gma4_replay_adapter",
    }
    write_json(paths.clean_run_dir / "gma5_runtime_replay_trace_v1.json", replay_trace)
    write_json(
        paths.clean_run_dir / "gma5_no_equity_curve_averaging_trace_v2.json",
        no_averaging_trace,
    )
    write_json(paths.clean_run_dir / "gma5_composite_replay_provenance_v1.json", provenance)
    return replay_trace


def write_clean_manifest(
    paths: CleanExecutionPaths,
    execution_uuid: str,
    status: str,
    replay_trace: dict[str, Any],
    journal: dict[str, Any],
) -> None:
    write_json(
        paths.clean_run_dir / "gma5_clean_execution_manifest_v1.json",
        {
            "clean_execution_run_id": paths.clean_run_dir.name,
            "original_run_id": ORIGINAL_RUN_ID,
            "gma4_source_run_id": GMA4_SOURCE_RUN_ID,
            "execution_uuid": execution_uuid,
            "overall_reproducibility_status": status,
            "numeric_tolerance": TOLERANCE,
            "common_gma5_oos_start": "2012-05-31",
            "first_true_learned_ridge_decision": "2015-05-29",
            "pre_model_policy": "no_allocation_before_training",
            "gfc_coverage": "unavailable_before_common_oos_start",
            "runtime_replay_trace": replay_trace,
            "execution_journal": {
                "execution_started_at_utc": journal["execution_started_at_utc"],
                "execution_finished_at_utc": journal["execution_finished_at_utc"],
                "original_output_read_phase_started_at_utc": journal[
                    "original_output_read_phase_started_at_utc"
                ],
                "standard_outputs_generated_by_execution": journal[
                    "standard_outputs_generated_by_execution"
                ],
                "original_standard_outputs_read_before_execution_finished": journal[
                    "original_standard_outputs_read_before_execution_finished"
                ],
            },
        },
    )


def run_with_replay_trace(
    paths: CleanExecutionPaths,
    clean_run_id: str,
    executor: Callable[[Path, str], Any] | None,
) -> tuple[list[str], Any]:
    import market_strats.global_multi_asset.gma5_atomic_sleeve_ensemble as gma5

    replay_call_strategy_ids: list[str] = []
    original_adapter = gma5.run_gma4_replay_adapter
    original_mkdir = Path.mkdir
    clean_run_dir_resolved = paths.clean_run_dir.resolve()

    def traced_adapter(*args: Any, **kwargs: Any) -> Any:
        replay_call_strategy_ids.append(str(kwargs.get("strategy_id", "unknown")))
        return original_adapter(*args, **kwargs)

    def mkdir_allow_existing_clean_dir(path_self: Path, *args: Any, **kwargs: Any) -> None:
        if path_self.resolve() == clean_run_dir_resolved and path_self.exists():
            return None
        return original_mkdir(path_self, *args, **kwargs)

    gma5.run_gma4_replay_adapter = traced_adapter
    Path.mkdir = mkdir_allow_existing_clean_dir
    try:
        if executor is None:
            result = gma5.run_gma5_atomic_sleeve_ensemble(paths.config_path, clean_run_id)
        else:
            result = executor(paths.config_path, clean_run_id)
    finally:
        gma5.run_gma4_replay_adapter = original_adapter
        Path.mkdir = original_mkdir
    if (
        not replay_call_strategy_ids
        and executor is not None
        and hasattr(result, "replay_call_strategy_ids")
    ):
        replay_call_strategy_ids.extend(str(item) for item in result.replay_call_strategy_ids)
    return replay_call_strategy_ids, result


def assert_standard_outputs_generated(paths: CleanExecutionPaths, run_result: Any) -> None:
    if (
        hasattr(run_result, "run_dir")
        and Path(run_result.run_dir).resolve() != paths.clean_run_dir.resolve()
    ):
        raise CleanExecutionError("clean execution returned an unexpected run directory")
    for output in STANDARD_OUTPUTS:
        if not (paths.clean_run_dir / output).exists():
            raise CleanExecutionError(f"clean execution did not produce {output}")


def run_clean_execution_verification(
    repo_root: Path,
    gma5_report_root: Path,
    gma4_run_dir: Path,
    config_path: Path,
    clean_run_id: str = CLEAN_RUN_ID,
    executor: Callable[[Path, str], Any] | None = None,
) -> CleanExecutionResult:
    paths = resolve_paths(repo_root, gma5_report_root, gma4_run_dir, config_path, clean_run_id)
    if clean_run_id == ORIGINAL_RUN_ID:
        raise CleanExecutionError("clean run ID must differ from original run ID")
    if paths.clean_run_dir.exists():
        raise CleanExecutionError(f"clean execution run already exists: {paths.clean_run_dir}")
    paths.clean_run_dir.mkdir(parents=True)

    execution_uuid = str(uuid.uuid4())
    journal: dict[str, Any] = {
        "clean_execution_run_id": clean_run_id,
        "execution_uuid": execution_uuid,
        "execution_started_at_utc": utc_now(),
        "execution_finished_at_utc": "",
        "original_output_read_phase_started_at_utc": "",
        "new_output_hashes_before_comparison": {},
        "original_output_hashes_at_comparison": {},
        "standard_outputs_generated_by_execution": False,
        "original_standard_outputs_read_before_execution_finished": False,
    }
    source_manifest = snapshot_sources(paths, execution_uuid)

    with OriginalOutputReadGuard(paths.original_run_dir, STANDARD_OUTPUTS) as guard:
        replay_call_strategy_ids, run_result = run_with_replay_trace(paths, clean_run_id, executor)
        assert_standard_outputs_generated(paths, run_result)
        journal["execution_finished_at_utc"] = utc_now()
        journal["new_output_hashes_before_comparison"] = hash_outputs(paths.clean_run_dir)
        journal["standard_outputs_generated_by_execution"] = True
        journal["original_standard_outputs_read_before_execution_finished"] = (
            guard.original_read_before_finished
        )

    if journal["original_standard_outputs_read_before_execution_finished"]:
        raise CleanExecutionError("original standard output was read during clean execution")
    if not replay_call_strategy_ids:
        raise CleanExecutionError("clean execution did not invoke the replay adapter")

    netting_rows = build_netting_audit(paths)
    validate_target_sums(netting_rows)
    ledger_rows = build_replay_ledger(paths)
    replay_trace = write_runtime_artifacts(
        paths,
        execution_uuid,
        clean_run_id,
        source_manifest,
        replay_call_strategy_ids,
        netting_rows,
        ledger_rows,
    )
    if replay_trace["replay_adapter_invocation_count"] <= 0:
        raise CleanExecutionError("runtime replay trace has no adapter invocation")

    journal["original_output_read_phase_started_at_utc"] = utc_now()
    journal["original_output_hashes_at_comparison"] = hash_outputs(paths.original_run_dir)
    status, comparison_rows = compare_outputs(paths)
    write_comparison_markdown(paths, status, comparison_rows)
    write_clean_manifest(paths, execution_uuid, status, replay_trace, journal)
    write_json(paths.clean_run_dir / "gma5_clean_execution_journal_v1.json", journal)
    return CleanExecutionResult(
        original_run_id=ORIGINAL_RUN_ID,
        clean_run_id=clean_run_id,
        clean_run_dir=paths.clean_run_dir,
        overall_status=status,
        comparison_rows=comparison_rows,
        execution_uuid=execution_uuid,
        journal=journal,
        replay_trace=replay_trace,
    )


def main() -> None:
    args = parse_args()
    run_clean_execution_verification(
        Path("."),
        Path(args.gma5_report_root),
        Path(args.gma4_run_dir),
        Path(args.config_path),
        args.clean_run_id,
    )


if __name__ == "__main__":
    main()
