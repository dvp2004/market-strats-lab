import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from market_strats.intelligence.mi2.prospective_snapshot_runner import (
    EXPECTED_UNIVERSE,
    FROZEN_MODEL_IDENTIFIER,
    ProspectiveSnapshotRunnerError,
    SnapshotRunnerConfig,
    write_prospective_snapshot,
)
from market_strats.intelligence.mi2.signal_export_parity import EXPORT_COLUMNS

NY_TZ = ZoneInfo("America/New_York")


@pytest.fixture
def synthetic_snapshot_df():
    rows = []
    for asset in sorted(EXPECTED_UNIVERSE):
        rows.append(
            {
                "decision_date": "2026-06-28",
                "asset_identifier": asset,
                "model_identifier": FROZEN_MODEL_IDENTIFIER,
                "feature_or_signal_schema_identifier": "mi2e_research_only_technical_signal_export_v1",  # noqa: E501
                "signal_horizon_sessions": 20,
                "signal_score": 0.05,
                "signal_rank": 1,
                "signal_percentile": 1.0,
                "data_cutoff_or_availability_reference": "20:00 America/New_York",
                "source_artifact_sha256": "dummy_source_hash",
                "research_only": True,
                "portfolio_influence": 0,
            }
        )
    return pd.DataFrame(rows)[list(EXPORT_COLUMNS)]


@pytest.fixture
def valid_config(tmp_path, synthetic_snapshot_df, monkeypatch):
    monkeypatch.setattr(
        "market_strats.intelligence.mi2.prospective_snapshot_runner._is_git_ignored",
        lambda repo, path: True,
    )
    monkeypatch.setattr(
        "market_strats.intelligence.mi2.prospective_snapshot_runner._get_file_sha256",
        lambda path: "dummy_source_hash",
    )

    export_artifact_path = tmp_path / "export.parquet"
    source_artifact_path = tmp_path / "source.txt"
    storage_root = tmp_path / "data" / "private" / "mi2" / "prospective_snapshots"

    synthetic_snapshot_df.to_parquet(export_artifact_path, index=False)
    source_artifact_path.write_text("dummy source content")

    return SnapshotRunnerConfig(
        repository_root=tmp_path,
        storage_root=storage_root,
        export_artifact_path=export_artifact_path,
        source_artifact_path=source_artifact_path,
        confirm_write=True,
    )


def test_valid_synthetic_capture_writes_one_snapshot_manifest_ledger(valid_config):
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    write_prospective_snapshot(valid_config, current_time)

    storage_root = valid_config.storage_root
    assert (storage_root / "snapshots" / "snapshot_2026-06-28.parquet").exists()
    assert (storage_root / "manifests" / "snapshot_2026-06-28.json").exists()

    ledger_file = storage_root / "ledger" / "mi2_prospective_snapshot_ledger.jsonl"
    assert ledger_file.exists()

    lines = ledger_file.read_text().splitlines()
    assert len(lines) == 1

    # Check manifest payload hash
    df = pd.read_parquet(storage_root / "snapshots" / "snapshot_2026-06-28.parquet")
    from market_strats.intelligence.mi2.signal_export_parity import canonical_export_sha256

    actual_hash = canonical_export_sha256(df)

    manifest = json.loads((storage_root / "manifests" / "snapshot_2026-06-28.json").read_text())
    assert manifest["payload_sha256"] == actual_hash

    ledger_entry = json.loads(lines[0])
    assert "target_weight" not in ledger_entry
    assert "portfolio_return" not in ledger_entry


def test_missing_confirm_flag_rejects(valid_config):
    valid_config.confirm_write = False
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="confirm-write"):
        write_prospective_snapshot(valid_config, current_time)


def test_identical_decision_date_rejects_as_duplicate(valid_config):
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    write_prospective_snapshot(valid_config, current_time)

    with pytest.raises(ProspectiveSnapshotRunnerError, match="already exists"):
        write_prospective_snapshot(valid_config, current_time)


def test_incomplete_universe_rejects(valid_config, synthetic_snapshot_df):
    bad_df = synthetic_snapshot_df.iloc[:-1]  # drop one
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="exactly the 22-ETF universe"):
        write_prospective_snapshot(valid_config, current_time)


def test_duplicate_asset_rejects(valid_config, synthetic_snapshot_df):
    bad_df = pd.concat([synthetic_snapshot_df, synthetic_snapshot_df.iloc[[0]]], ignore_index=True)
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="exactly one row per asset"):
        write_prospective_snapshot(valid_config, current_time)


def test_wrong_model_identity_rejects(valid_config, synthetic_snapshot_df):
    bad_df = synthetic_snapshot_df.copy()
    bad_df["model_identifier"] = "wrong_model"
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="Model identifier must be exactly"):
        write_prospective_snapshot(valid_config, current_time)


def test_missing_or_mismatched_source_sha256_rejects(valid_config, synthetic_snapshot_df):
    bad_df = synthetic_snapshot_df.copy()
    bad_df["source_artifact_sha256"] = "wrong_hash"
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="does not match declared hash"):
        write_prospective_snapshot(valid_config, current_time)


def test_invalid_or_too_early_cutoff_rejects(valid_config):
    # Creation time 19:59 is too early
    current_time = datetime(2026, 6, 28, 19, 59, 59, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="cannot be earlier than 20:00"):
        write_prospective_snapshot(valid_config, current_time)


def test_prohibited_fields_reject(valid_config, synthetic_snapshot_df):
    bad_df = synthetic_snapshot_df.copy()
    bad_df["target_weight"] = 0.5
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="prohibited fields"):
        write_prospective_snapshot(valid_config, current_time)


def test_research_only_or_portfolio_influence_violations_reject(
    valid_config, synthetic_snapshot_df
):
    bad_df = synthetic_snapshot_df.copy()
    bad_df["research_only"] = False
    bad_df.to_parquet(valid_config.export_artifact_path, index=False)
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="research_only=true"):
        write_prospective_snapshot(valid_config, current_time)


def test_storage_root_not_git_ignored_rejects(valid_config, monkeypatch):
    monkeypatch.setattr(
        "market_strats.intelligence.mi2.prospective_snapshot_runner._is_git_ignored",
        lambda repo, path: False,
    )
    current_time = datetime(2026, 6, 28, 20, 5, 0, tzinfo=NY_TZ)
    with pytest.raises(ProspectiveSnapshotRunnerError, match="ignored by Git"):
        write_prospective_snapshot(valid_config, current_time)
