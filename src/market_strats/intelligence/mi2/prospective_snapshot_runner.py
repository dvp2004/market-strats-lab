"""Immutable prospective snapshot runner for MI-2."""

import argparse
import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from market_strats.intelligence.mi2.signal_export_parity import canonical_export_sha256

logger = logging.getLogger(__name__)

EXPECTED_UNIVERSE = frozenset(
    [
        "AGG",
        "BIL",
        "DBC",
        "EEM",
        "EFA",
        "GLD",
        "HYG",
        "IEF",
        "IWM",
        "LQD",
        "QQQ",
        "SPY",
        "TLT",
        "XLB",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLU",
        "XLV",
        "XLY",
    ]
)

PROHIBITED_FIELDS = frozenset(
    [
        "target_weight",
        "position_size",
        "portfolio_weight",
        "order",
        "trade",
        "broker",
        "account",
        "execution",
        "cash_allocation",
        "real_money",
        "portfolio_return",
        "strategy_return",
    ]
)

FROZEN_MODEL_IDENTIFIER = "ridge_fixed_alpha_1_0"
FROZEN_MODEL_HASH = "b43ab173262717863dbcdc766d64968aed6c5539534dad8b1445f919b83e1100"
FROZEN_UNIVERSE_IDENTIFIER = "mi1_us_liquid_etf_22_v1"
NY_TZ = ZoneInfo("America/New_York")


class ProspectiveSnapshotRunnerError(ValueError):
    """Raised for any prospective snapshot validation failure."""


@dataclass
class SnapshotRunnerConfig:
    repository_root: Path
    storage_root: Path
    export_artifact_path: Path
    source_artifact_path: Path
    confirm_write: bool


def _is_git_ignored(repository_root: Path, path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=repository_root,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _get_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_prospective_snapshot(
    config: SnapshotRunnerConfig, current_time: datetime | None = None
) -> None:
    if not config.confirm_write:
        raise ProspectiveSnapshotRunnerError(
            "The --confirm-write-research-snapshot flag is required."
        )

    if not config.storage_root.is_absolute():
        raise ProspectiveSnapshotRunnerError("Storage root must be an absolute path.")

    try:
        config.storage_root.relative_to(config.repository_root)
    except ValueError:
        raise ProspectiveSnapshotRunnerError("Storage root must be inside the repository.")

    # Must be git ignored (check a hypothetical file inside the root)
    dummy_file = config.storage_root / "test.parquet"
    if not _is_git_ignored(config.repository_root, dummy_file):
        raise ProspectiveSnapshotRunnerError("Storage root must be ignored by Git.")

    if not config.export_artifact_path.exists():
        raise ProspectiveSnapshotRunnerError("Export artifact does not exist.")

    if not config.source_artifact_path.exists():
        raise ProspectiveSnapshotRunnerError("Source artifact does not exist.")

    df = pd.read_parquet(config.export_artifact_path)
    if df.empty:
        raise ProspectiveSnapshotRunnerError("Export artifact is empty.")

    columns_lower = {str(c).lower() for c in df.columns}
    if columns_lower & PROHIBITED_FIELDS:
        raise ProspectiveSnapshotRunnerError("Export artifact contains prohibited fields.")

    if "decision_date" not in df.columns:
        raise ProspectiveSnapshotRunnerError("decision_date column is missing.")

    decision_dates = df["decision_date"].unique()
    if len(decision_dates) != 1:
        raise ProspectiveSnapshotRunnerError(
            "Export artifact must contain exactly one decision date."
        )

    decision_date_str = str(decision_dates[0])
    try:
        decision_date = datetime.strptime(decision_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ProspectiveSnapshotRunnerError("decision_date must be YYYY-MM-DD.")

    if "asset_identifier" not in df.columns:
        raise ProspectiveSnapshotRunnerError("asset_identifier column is missing.")

    universe = set(df["asset_identifier"])
    if universe != EXPECTED_UNIVERSE:
        raise ProspectiveSnapshotRunnerError(
            "Export artifact does not contain exactly the 22-ETF universe."
        )

    if len(df) != 22:
        raise ProspectiveSnapshotRunnerError(
            "Export artifact must contain exactly one row per asset."
        )

    if (
        "model_identifier" not in df.columns
        or not (df["model_identifier"] == FROZEN_MODEL_IDENTIFIER).all()
    ):
        raise ProspectiveSnapshotRunnerError(
            f"Model identifier must be exactly {FROZEN_MODEL_IDENTIFIER}."
        )

    if "research_only" not in df.columns or not df["research_only"].all():
        raise ProspectiveSnapshotRunnerError("Every row must have research_only=true.")

    if "portfolio_influence" not in df.columns or not (df["portfolio_influence"] == 0).all():
        raise ProspectiveSnapshotRunnerError("Every row must have portfolio_influence=0.")

    actual_source_sha256 = _get_file_sha256(config.source_artifact_path)
    if (
        "source_artifact_sha256" not in df.columns
        or not (df["source_artifact_sha256"] == actual_source_sha256).all()
    ):
        raise ProspectiveSnapshotRunnerError(
            "Source artifact SHA-256 does not match declared hash."
        )

    if "data_cutoff_or_availability_reference" not in df.columns:
        raise ProspectiveSnapshotRunnerError(
            "data_cutoff_or_availability_reference column is missing."
        )

    cutoff_vals = df["data_cutoff_or_availability_reference"].unique()
    if (
        len(cutoff_vals) != 1
        or "20:00" not in str(cutoff_vals[0])
        or "America/New_York" not in str(cutoff_vals[0])
    ):
        raise ProspectiveSnapshotRunnerError(
            "A valid 20:00 America/New_York cutoff/provenance reference is required."
        )

    if current_time is None:
        current_time = datetime.now(NY_TZ)
    else:
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=NY_TZ)
        else:
            current_time = current_time.astimezone(NY_TZ)

    required_cutoff_time = datetime(
        decision_date.year, decision_date.month, decision_date.day, 20, 0, 0, tzinfo=NY_TZ
    )
    if current_time < required_cutoff_time:
        raise ProspectiveSnapshotRunnerError(
            "Creation time cannot be earlier than 20:00 New York time on the decision date."
        )

    # Calculate payload hash
    payload_sha256 = canonical_export_sha256(df)

    snapshot_id = f"snapshot_{decision_date_str}_{payload_sha256[:12]}"
    creation_timestamp = current_time.isoformat()

    snapshots_dir = config.storage_root / "snapshots"
    manifests_dir = config.storage_root / "manifests"
    ledger_dir = config.storage_root / "ledger"

    snapshots_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    snapshot_file = snapshots_dir / f"snapshot_{decision_date_str}.parquet"
    manifest_file = manifests_dir / f"snapshot_{decision_date_str}.json"
    ledger_file = ledger_dir / "mi2_prospective_snapshot_ledger.jsonl"

    if snapshot_file.exists() or manifest_file.exists():
        raise ProspectiveSnapshotRunnerError("Destination snapshot or manifest already exists.")

    if ledger_file.exists():
        ledger_lines = ledger_file.read_text(encoding="utf-8").splitlines()
        for line in ledger_lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("decision_date") == decision_date_str:
                raise ProspectiveSnapshotRunnerError(
                    "Decision date has previously been recorded in ledger."
                )

    # Write atomically
    manifest_data = {
        "snapshot_id": snapshot_id,
        "decision_date": decision_date_str,
        "creation_timestamp": creation_timestamp,
        "model_identifier": FROZEN_MODEL_IDENTIFIER,
        "universe_identifier": FROZEN_UNIVERSE_IDENTIFIER,
        "payload_sha256": payload_sha256,
        "source_artifact_sha256": actual_source_sha256,
    }

    ledger_data = {
        "snapshot_id": snapshot_id,
        "decision_date": decision_date_str,
        "creation_timestamp": creation_timestamp,
        "model_identifier": FROZEN_MODEL_IDENTIFIER,
        "universe_identifier": FROZEN_UNIVERSE_IDENTIFIER,
        "payload_sha256": payload_sha256,
        "source_artifact_sha256": actual_source_sha256,
        "research_only": True,
        "portfolio_influence": 0,
    }

    # Verify no prohibited fields in ledger
    for k in ledger_data.keys():
        if k in PROHIBITED_FIELDS:
            raise ProspectiveSnapshotRunnerError("Prohibited field found in ledger data.")

    # Create temporary files
    temp_snapshot = snapshot_file.with_suffix(".tmp")
    df.to_parquet(temp_snapshot, index=False)

    verify_hash = canonical_export_sha256(pd.read_parquet(temp_snapshot))
    if verify_hash != payload_sha256:
        temp_snapshot.unlink(missing_ok=True)
        raise ProspectiveSnapshotRunnerError("Hash verification failed after temporary write.")

    temp_snapshot.rename(snapshot_file)
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with ledger_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ledger_data) + "\n")

    logger.info("Snapshot successfully written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MI-2 Immutable Prospective Snapshot Runner")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--export-artifact-path", type=Path, required=True)
    parser.add_argument("--source-artifact-path", type=Path, required=True)
    parser.add_argument("--confirm-write-research-snapshot", action="store_true")
    args = parser.parse_args()

    config = SnapshotRunnerConfig(
        repository_root=args.repository_root.resolve(),
        storage_root=args.storage_root.resolve(),
        export_artifact_path=args.export_artifact_path.resolve(),
        source_artifact_path=args.source_artifact_path.resolve(),
        confirm_write=args.confirm_write_research_snapshot,
    )
    write_prospective_snapshot(config)
