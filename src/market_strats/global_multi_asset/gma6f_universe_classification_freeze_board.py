"""GMA-6F cross-universe classification and freeze board.

This module classifies saved GMA-6D/GMA-6E evidence only. It does not fetch data,
run strategies, replay portfolios, fit models, generate targets, or alter contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_ROOT = Path("reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1")
DEFAULT_GMA6C_LOCK = Path(
    "reports/global_multi_asset_alpha/gma6c_cross_universe_tournament_lock_v1.json"
)
DEFAULT_GMA6B2_CONTINUITY = Path(
    "reports/global_multi_asset_alpha/gma6b2_commodity_etp_historical_continuity_v1.csv"
)
COMPLETED_RUN_ID = "gma6d_20260624T061822Z"
CONTROL_UNIVERSE = "gma6_core_22_control_v1"
EXPANDED_UNIVERSE = "gma6_expanded_29_v1"
USO_FLAG = "uso_roll_methodology_pre_may_2020_vs_from_may_2020"
EXPECTED_IDENTICAL_EFFECTIVE_SAMPLE_COUNT = 32144
EXPECTED_NON_COMPARABLE_EXCLUDED_COUNT = 336
FUTURE_BOUNDARY = (
    "GMA-6 V1 cross-universe interpretation is frozen. No GMA-6 V1 universe tuning, "
    "subset search, replacement search, individual-addition attribution search, or "
    "expanded-universe model search is authorised within this research phase.\n"
    "Any future universe research requires a separately versioned and pre-registered contract."
)
CORE_RATIONALE = (
    "Comparable frozen GMA-6D evidence shows stronger net CAGR, Sharpe, and "
    "maximum-drawdown outcomes more often for the core-22 control across the locked trial "
    "inventory and frozen cost scenarios. This is a research reference classification only."
)
EXPANDED_RATIONALE = (
    "The expanded universe showed lower turnover and cost drag in many comparable summaries, "
    "but it did not show broad incremental support on net CAGR, Sharpe, or maximum drawdown "
    "under the locked GMA-6D trial inventory. No individual addition may be removed, "
    "replaced, or isolated after observing these outcomes."
)
KNOWN_LIMITATIONS = [
    "The primary comparison is core-22 versus expanded-29 within the frozen GMA-6D run.",
    "Non-comparable effective samples were excluded from primary aggregates.",
    "GMA-4 results are not directly numerically comparable without an identical data snapshot.",
    "USO and DBA are historical traded ETP return exposures, not spot commodity return series.",
    "USO carries uso_roll_methodology_pre_may_2020_vs_from_may_2020 as descriptive methodology context only.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "This is observed development evidence and not a pristine final holdout.",
    "No execution or promotion decision is produced.",
]
CLASSIFICATIONS = [
    {
        "universe_version": CONTROL_UNIVERSE,
        "classification": "frozen_research_reference",
        "role": "control_universe_baseline",
        "gma6_v1_status": "retained_as_cross_universe_control_reference",
        "rationale": CORE_RATIONALE,
    },
    {
        "universe_version": EXPANDED_UNIVERSE,
        "classification": "archived_from_gma6_v1_expansion",
        "role": "documented_expansion_reference_no_broad_incremental_support",
        "gma6_v1_status": "no_further_gma6_v1_tuning_subsetting_or_expansion",
        "rationale": EXPANDED_RATIONALE,
    },
]
OUTPUT_CSV = "gma6f_universe_classification_freeze_board_v1.csv"
OUTPUT_MD = "gma6f_universe_classification_freeze_board_v1.md"
OUTPUT_LOCK = "gma6f_universe_classification_locks_v1.json"
FORBIDDEN_LANGUAGE = ["candidate", "winner", "approved", "recommended", "deployable", "live-ready"]


class GMA6FClassificationError(ValueError):
    """Fail-closed GMA-6F validation error."""


@dataclass(frozen=True)
class GMA6FResult:
    root: Path
    classification: pd.DataFrame
    lock: dict[str, Any]
    comparable_count: int
    non_comparable_count: int


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6FClassificationError(f"{path} must contain a JSON object")
    return raw


def _read_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise GMA6FClassificationError(f"required input missing or empty: {path}")
    frame = pd.read_csv(path)
    missing = required_columns - set(frame.columns)
    if missing:
        raise GMA6FClassificationError(f"{path} missing columns: {sorted(missing)}")
    if frame.empty:
        raise GMA6FClassificationError(f"required input has no rows: {path}")
    return frame


def _bool_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().map({"true": True, "false": False})


def _validate_preconditions(
    *, root: Path, completed_run_id: str, gma6b2_continuity_path: Path
) -> tuple[dict[str, Any], int, int, str]:
    attempt = _read_csv(
        root / "gma6e_attempt_registry_v1.csv",
        {"run_id", "attempt_status", "eligible_for_latest_reference"},
    )
    integrity = _read_csv(
        root / "gma6e_completed_run_integrity_audit_v1.csv",
        {"check_name", "audit_status"},
    )
    evidence = _read_csv(
        root / "gma6e_comparability_aware_evidence_board_v1.csv",
        {"record_type", "included_in_primary_summary", "sample_comparability_status"},
    )
    completed = attempt.loc[attempt["attempt_status"] == "completed_verified_run"]
    if len(completed) != 1 or completed.iloc[0]["run_id"] != completed_run_id:
        raise GMA6FClassificationError("exactly one completed verified GMA-6D run is required")
    eligible = _bool_series(completed["eligible_for_latest_reference"]).iloc[0]
    if not bool(eligible):
        raise GMA6FClassificationError("completed verified run is not latest-reference eligible")
    timeout_rows = attempt.loc[attempt["run_id"] != completed_run_id]
    if (
        timeout_rows.empty
        or not (timeout_rows["attempt_status"] == "aborted_or_incomplete_attempt").all()
    ):
        raise GMA6FClassificationError("timeout attempts must remain incomplete and excluded")
    if not (integrity["audit_status"] == "pass").all():
        failed = integrity.loc[integrity["audit_status"] != "pass", "check_name"].tolist()
        raise GMA6FClassificationError(f"completed-run integrity verdict is not pass: {failed}")
    trial_metric = evidence.loc[evidence["record_type"] == "trial_metric"].copy()
    included = _bool_series(trial_metric["included_in_primary_summary"])
    comparable_count = int(included.sum())
    non_comparable_count = int((~included).sum())
    if comparable_count != EXPECTED_IDENTICAL_EFFECTIVE_SAMPLE_COUNT:
        raise GMA6FClassificationError(
            f"identical_effective_sample_count mismatch: {comparable_count}"
        )
    if non_comparable_count != EXPECTED_NON_COMPARABLE_EXCLUDED_COUNT:
        raise GMA6FClassificationError(
            f"non_comparable_excluded_count mismatch: {non_comparable_count}"
        )
    comparable_status_count = int(
        (trial_metric["sample_comparability_status"] == "identical_effective_sample").sum()
    )
    if comparable_status_count != comparable_count:
        raise GMA6FClassificationError("comparable sample-status count does not reconcile")
    continuity = _read_csv(gma6b2_continuity_path, {"ticker", "required_later_regime_flag"})
    uso_rows = continuity.loc[continuity["ticker"] == "USO"]
    if len(uso_rows) != 1 or uso_rows.iloc[0]["required_later_regime_flag"] != USO_FLAG:
        raise GMA6FClassificationError("USO methodology regime flag is not retained")
    manifest_path = root / "runs" / completed_run_id / "gma6d_run_manifest_v1.json"
    provenance_path = root / "runs" / completed_run_id / "gma6d_execution_provenance_v1.json"
    manifest = _load_json(manifest_path)
    _load_json(provenance_path)
    if manifest.get("run_id") != completed_run_id:
        raise GMA6FClassificationError("completed_run_id mismatch in manifest")
    return (
        manifest,
        comparable_count,
        non_comparable_count,
        str(uso_rows.iloc[0]["required_later_regime_flag"]),
    )


def _classification_frame() -> pd.DataFrame:
    rows = []
    for row in CLASSIFICATIONS:
        rows.append(
            {
                **row,
                "completed_run_id": COMPLETED_RUN_ID,
                "classification_scope": "saved_output_only_cross_universe_research_reference",
                "known_limitations": " | ".join(KNOWN_LIMITATIONS),
                "future_boundary": FUTURE_BOUNDARY,
            }
        )
    return pd.DataFrame(rows)


def _build_lock(
    *,
    root: Path,
    completed_run_id: str,
    manifest: dict[str, Any],
    comparable_count: int,
    non_comparable_count: int,
    uso_flag: str,
    gma6c_lock_path: Path,
) -> dict[str, Any]:
    manifest_path = root / "runs" / completed_run_id / "gma6d_run_manifest_v1.json"
    return {
        "completed_run_id": completed_run_id,
        "completed_run_manifest_hash": _sha256_file(manifest_path),
        "gma6c_lock_hash": _sha256_file(gma6c_lock_path),
        "gma6b_data_bundle_manifest_hash": manifest["gma6b_data_bundle_manifest_hash"],
        "trial_inventory_hash": manifest["trial_inventory_hash"],
        "cost_scenario_hash": manifest["cost_scenario_hash"],
        "control_universe_hash": manifest["control_universe_hash"],
        "expanded_universe_hash": manifest["expanded_universe_hash"],
        "gma6e_integrity_audit_hash": _sha256_file(
            root / "gma6e_completed_run_integrity_audit_v1.csv"
        ),
        "gma6e_evidence_board_hash": _sha256_file(
            root / "gma6e_comparability_aware_evidence_board_v1.csv"
        ),
        "primary_comparable_observation_count": comparable_count,
        "non_comparable_excluded_observation_count": non_comparable_count,
        "uso_methodology_regime_flag": uso_flag,
        "classifications": {
            row["universe_version"]: row["classification"] for row in CLASSIFICATIONS
        },
        "roles": {row["universe_version"]: row["role"] for row in CLASSIFICATIONS},
        "classification_rationales": {
            row["universe_version"]: row["rationale"] for row in CLASSIFICATIONS
        },
        "known_limitations": KNOWN_LIMITATIONS,
        "future_boundary": FUTURE_BOUNDARY,
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(str(item) for item in row) + " |" for row in rows),
    ]


def _assert_language(text: str) -> None:
    lowered = text.lower()
    allowed = "no execution or promotion decision is produced."
    scrubbed = lowered.replace(allowed, "")
    found = [word for word in FORBIDDEN_LANGUAGE if word in scrubbed]
    if found:
        raise GMA6FClassificationError(f"forbidden wording found: {found}")


def _write_outputs(root: Path, frame: pd.DataFrame, lock: dict[str, Any]) -> None:
    frame.to_csv(root / OUTPUT_CSV, index=False)
    lock_text = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    _assert_language(lock_text)
    (root / OUTPUT_LOCK).write_text(lock_text, encoding="utf-8")
    lines = [
        *KNOWN_LIMITATIONS,
        "No execution or promotion decision is produced.",
        "",
        "## Universe Classifications",
        *_markdown_table(
            ["universe", "classification", "role", "gma6_v1_status"],
            [
                [
                    row["universe_version"],
                    row["classification"],
                    row["role"],
                    row["gma6_v1_status"],
                ]
                for row in frame.to_dict("records")
            ],
        ),
        "",
        "## Rationales",
        *[f"- {row['universe_version']}: {row['rationale']}" for row in frame.to_dict("records")],
        "",
        "## Future Boundary",
        FUTURE_BOUNDARY,
    ]
    md_text = "# GMA-6F Universe Classification Freeze Board v1\n\n" + "\n".join(lines) + "\n"
    _assert_language(md_text)
    (root / OUTPUT_MD).write_text(md_text, encoding="utf-8")


def run_gma6f_classification_freeze_board(
    *,
    root: Path = DEFAULT_ROOT,
    completed_run_id: str = COMPLETED_RUN_ID,
    gma6c_lock_path: Path = DEFAULT_GMA6C_LOCK,
    gma6b2_continuity_path: Path = DEFAULT_GMA6B2_CONTINUITY,
) -> GMA6FResult:
    manifest, comparable_count, non_comparable_count, uso_flag = _validate_preconditions(
        root=root,
        completed_run_id=completed_run_id,
        gma6b2_continuity_path=gma6b2_continuity_path,
    )
    frame = _classification_frame()
    lock = _build_lock(
        root=root,
        completed_run_id=completed_run_id,
        manifest=manifest,
        comparable_count=comparable_count,
        non_comparable_count=non_comparable_count,
        uso_flag=uso_flag,
        gma6c_lock_path=gma6c_lock_path,
    )
    _write_outputs(root, frame, lock)
    return GMA6FResult(root, frame, lock, comparable_count, non_comparable_count)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma6f_universe_classification_freeze_board"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--completed-run-id", default=COMPLETED_RUN_ID)
    args = parser.parse_args(argv)
    result = run_gma6f_classification_freeze_board(
        root=args.root, completed_run_id=args.completed_run_id
    )
    print(f"completed_run_id: {args.completed_run_id}")
    print(f"classification_count: {len(result.classification)}")
    print(f"primary_comparable_observation_count: {result.comparable_count}")
    print(f"non_comparable_excluded_observation_count: {result.non_comparable_count}")
    print(f"output_root: {result.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
