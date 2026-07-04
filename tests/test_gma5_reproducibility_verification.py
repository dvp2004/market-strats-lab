import csv
import json
from pathlib import Path

import pytest

from market_strats.global_multi_asset.gma5_reproducibility_verification import (
    COMPARISON_OUTPUTS,
    CORE_SNAPSHOT_PATHS,
    ORIGINAL_RUN_ID,
    STANDARD_OUTPUTS,
    VERIFIED_RUN_ID,
    VerificationError,
    compare_csv_artifact,
    run_verification,
    sha256_file,
)


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _make_core_sources(repo_root: Path) -> None:
    for relative in CORE_SNAPSHOT_PATHS:
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")


def _standard_rows(name: str) -> list[dict[str, str]]:
    if name == "gma5_ensemble_monthly_etf_targets.csv":
        return [
            {
                "variant_id": "v1",
                "decision_date": "2020-01-31",
                "symbol": "SPY",
                "composite_etf_target_weight": "0.7",
            },
            {
                "variant_id": "v1",
                "decision_date": "2020-01-31",
                "symbol": "BIL",
                "composite_etf_target_weight": "0.3",
            },
        ]
    if name == "gma5_ensemble_training_audit.csv":
        return [
            {
                "decision_date": "2015-05-29",
                "sleeve_id": "s1",
                "training_row_count": "60",
                "prediction": "0.01",
            }
        ]
    if name == "gma5_ensemble_monthly_features.csv":
        return [{"sleeve_id": "s1", "decision_date": "2020-01-31", "feature": "1.0"}]
    if name == "gma5_ensemble_monthly_sleeve_weights.csv":
        return [
            {
                "variant_id": "v1",
                "decision_date": "2020-01-31",
                "sleeve_id": "s1",
                "sleeve_allocation_weight": "1.0",
            }
        ]
    return [
        {
            "entity_id": "v1",
            "entity_type": "ensemble_variant",
            "cost_scenario": "baseline_1bps",
            "evaluation_scope": "full_common_oos",
            "start_date": "2012-05-31",
            "end_date": "2026-05-01",
            "net_cagr": "0.1",
            "max_drawdown": "-0.2",
            "status": "evaluated",
        }
    ]


def _make_fixture(repo_root: Path) -> tuple[Path, Path, Path]:
    _make_core_sources(repo_root)
    gma5_root = (
        repo_root / "reports" / "global_multi_asset_alpha" / "gma5_atomic_sleeve_ensemble_v1"
    )
    original = gma5_root / "runs" / ORIGINAL_RUN_ID
    original.mkdir(parents=True)
    for output in STANDARD_OUTPUTS:
        path = original / output
        if output.endswith(".json"):
            path.write_text(
                json.dumps({"run_id": ORIGINAL_RUN_ID, "created_at_utc": "2026-06-22T00:00:00Z"}),
                encoding="utf-8",
            )
        else:
            _write_csv(path, _standard_rows(output))
    gma4_run = (
        repo_root
        / "reports"
        / "global_multi_asset_alpha"
        / "gma4_cross_asset_tournament_v1"
        / "runs"
        / "gma4_20260621T163423Z"
    )
    gma4_run.mkdir(parents=True)
    for name in ["gma4_run_manifest.json", "gma4_tournament_scoreboard.csv"]:
        (gma4_run / name).write_text("fixture\n", encoding="utf-8")
    inventory = (
        repo_root
        / "reports"
        / "global_multi_asset_alpha"
        / "gma4_fixed_22_etf_v1"
        / "gma4_market_bundle_inventory.csv"
    )
    inventory.parent.mkdir(parents=True)
    inventory.write_text("fixture\n", encoding="utf-8")
    cash = (
        repo_root
        / "data"
        / "global_multi_asset_alpha"
        / "gma4_fixed_22_etf_v1"
        / "cash"
        / "canonical_cash_accrual.csv"
    )
    cash.parent.mkdir(parents=True)
    cash.write_text("fixture\n", encoding="utf-8")
    return gma5_root, gma4_run, repo_root / CORE_SNAPSHOT_PATHS[0]


def test_source_snapshots_are_written_before_verification_outputs(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)
    (gma5_root / "runs" / ORIGINAL_RUN_ID / "gma5_ensemble_scoreboard.csv").unlink()

    with pytest.raises(VerificationError):
        run_verification(tmp_path, gma5_root, gma4_run, config)

    manifest = gma5_root / "runs" / VERIFIED_RUN_ID / "gma5_source_snapshot_manifest_v1.json"
    assert manifest.exists()


def test_exact_reproduction_writes_hashes_netting_replay_and_trace(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)

    result = run_verification(tmp_path, gma5_root, gma4_run, config)

    assert result.overall_status == "exact_reproduction_verified"
    manifest = json.loads(
        (result.verified_run_dir / "gma5_verified_reproduction_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["provenance"]["gma5_config_hash"] == sha256_file(config)
    assert "src/market_strats/global_multi_asset/gma4_replay_adapter.py" in result.source_hashes
    netting = _read_csv(result.verified_run_dir / "gma5_composite_target_netting_audit_v1.csv")
    assert sum(float(row["final_target_weight"]) for row in netting) == 1.0
    bil = next(row for row in netting if row["ticker"] == "BIL")
    assert bil["bil_residual_weight"] == bil["final_target_weight"]
    provenance = json.loads(
        (result.verified_run_dir / "gma5_composite_replay_provenance_v1.json").read_text(
            encoding="utf-8"
        )
    )
    ledger_path = result.verified_run_dir / "gma5_composite_replay_ledger_v1.csv"
    assert provenance["composite_replay_ledger_hash"] == sha256_file(ledger_path)
    trace = json.loads(
        (result.verified_run_dir / "gma5_no_equity_curve_averaging_trace_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert trace["allocation_input_type"] == "sleeve_etf_target_weights"
    assert trace["replay_input_type"] == "netted_composite_etf_target_weights"
    assert trace["equity_curve_averaging_invoked"] is False


def test_original_run_files_remain_unchanged(tmp_path):
    gma5_root, gma4_run, config = _make_fixture(tmp_path)
    original_files = list((gma5_root / "runs" / ORIGINAL_RUN_ID).glob("*"))
    before = {path: sha256_file(path) for path in original_files if path.is_file()}

    run_verification(tmp_path, gma5_root, gma4_run, config)

    assert {path: sha256_file(path) for path in original_files if path.is_file()} == before


def test_compare_catches_row_count_date_text_and_numeric_mismatches(tmp_path):
    original = tmp_path / "original.csv"
    verified = tmp_path / "verified.csv"
    fields = ["date", "name", "value"]
    _write_csv(original, [{"date": "2020-01-31", "name": "a", "value": "1.0"}], fields)
    _write_csv(verified, [], fields)
    assert compare_csv_artifact(original, verified)["mismatch_type"] == "row_count_mismatch"
    _write_csv(verified, [{"date": "2020-02-29", "name": "a", "value": "1.0"}], fields)
    assert compare_csv_artifact(original, verified)["mismatch_type"] == "date_mismatch"
    _write_csv(verified, [{"date": "2020-01-31", "name": "b", "value": "1.0"}], fields)
    assert compare_csv_artifact(original, verified)["mismatch_type"] == "text_mismatch"
    _write_csv(verified, [{"date": "2020-01-31", "name": "a", "value": "1.000000000002"}], fields)
    assert compare_csv_artifact(original, verified)["mismatch_type"] == "numeric_mismatch"
    _write_csv(verified, [{"date": "2020-01-31", "name": "a", "value": "1.0000000000005"}], fields)
    assert compare_csv_artifact(original, verified)["status"] == "pass"


def test_no_forbidden_operation_terms_in_verifier_source():
    source = Path(
        "src/market_strats/global_multi_asset/gma5_reproducibility_verification.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "git add",
        "git commit",
        "git push",
        "requests",
        "urllib",
        "broker",
        "paper",
        "candidate",
        "promotion",
        "live",
        "prospective",
    ]
    assert not any(term in source for term in forbidden)


def test_all_required_standard_outputs_are_compared():
    assert set(COMPARISON_OUTPUTS) == {
        "gma5_ensemble_scoreboard.csv",
        "gma5_ensemble_monthly_sleeve_weights.csv",
        "gma5_ensemble_monthly_etf_targets.csv",
        "gma5_ensemble_monthly_features.csv",
        "gma5_ensemble_training_audit.csv",
        "gma5_ensemble_regime_detail.csv",
    }
