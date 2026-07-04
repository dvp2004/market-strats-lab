from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

import market_strats.global_multi_asset.gma8b_historical_data_provenance as gma8b
from market_strats.global_multi_asset.gma8b_historical_data_provenance import (
    BUNDLE_CONFIG_RELATIVE_PATH,
    BUNDLE_MANIFEST_RELATIVE_PATH,
    CORE_22,
    CORE_ARM_ID,
    EXACT_COLUMNS,
    EXPANDED_29,
    EXPANDED_ARM_ID,
    FALSE_OPERATION_FIELDS,
    GMA8BDataQualityError,
    GMA8BSourceResolutionError,
    GRID_HASH,
    OUTPUT_FILENAMES,
    ResolvedSource,
    audit,
    generate,
    inspect_source,
    load_settings,
    resolve_sources,
    validate_gma8a_parent,
)

CONFIG_PATH = Path(
    "configs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.yaml"
)
SOURCE_PATH = Path("src/market_strats/global_multi_asset/gma8b_historical_data_provenance.py")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _price_rows(offset: int = 0) -> list[dict[str, object]]:
    start = date(2000, 1, 1) + timedelta(days=offset)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 100 + index,
            "high": 101 + index,
            "low": 99 + index,
            "close": 100.5 + index,
            "adj_close": 90.5 + index,
            "volume": 1000 + index,
        }
        for index in range(260)
    ]


def _synthetic_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    worktree = tmp_path / "worktree"
    parent_root = worktree / "parent"
    parent_root.mkdir(parents=True)
    parent_config = parent_root / "gma8a.yaml"
    parent_config.write_text(
        yaml.safe_dump(
            {
                "strategy_grid": {
                    "exact_base_strategy_template_count": 80,
                    "exact_arm_trial_count": 160,
                    "strategy_grid_hash": GRID_HASH,
                }
            }
        ),
        encoding="utf-8",
    )
    parent_lock = parent_root / "lock.json"
    parent_lock.write_text(
        json.dumps(
            {
                "exact_base_strategy_template_count": 80,
                "exact_arm_trial_count": 160,
                "strategy_grid_hash": GRID_HASH,
            }
        ),
        encoding="utf-8",
    )
    parent_execution = parent_root / "execution.json"
    parent_execution.write_text(
        json.dumps(
            {
                "data_download_performed": False,
                "market_data_read": False,
                "backtest_performed": False,
                "strategy_ranking_performed": False,
            }
        ),
        encoding="utf-8",
    )
    universe = parent_root / "universe.csv"
    universe_rows = [{"universe_arm": CORE_ARM_ID, "symbol": ticker} for ticker in CORE_22] + [
        {"universe_arm": EXPANDED_ARM_ID, "symbol": ticker} for ticker in EXPANDED_29
    ]
    _write_csv(universe, ["universe_arm", "symbol"], universe_rows)
    strategy = parent_root / "strategy.csv"
    strategy_rows = [
        {
            "strategy_id": f"strategy_{index:02d}",
            "lookback_sessions": "252" if index == 0 else "63",
            "universe_arm": arm,
        }
        for index in range(80)
        for arm in [CORE_ARM_ID, EXPANDED_ARM_ID]
    ]
    _write_csv(strategy, ["strategy_id", "lookback_sessions", "universe_arm"], strategy_rows)

    snapshot_root = tmp_path / "immutable_snapshot"
    snapshot_root.mkdir()
    sources = snapshot_root / "series"
    sources.mkdir()
    inventory_rows = []
    manifest_rows = []
    source_paths: dict[str, Path] = {}
    for index, ticker in enumerate(EXPANDED_29):
        path = sources / f"{ticker}.csv"
        offset = index if ticker in CORE_22 else 40 + index
        _write_csv(path, EXACT_COLUMNS, _price_rows(offset))
        digest = _sha256(path)
        source_paths[ticker] = path
        inventory_rows.append({"ticker": ticker, "normalised_series_file_hash": digest})
        manifest_rows.append(
            {
                "relative_path": f"normalised/{ticker}.csv",
                "source_path": f"Z:\\must_not_be_used\\{ticker}.csv",
                "snapshot_path": str(path),
                "snapshot_sha256": digest,
                "hash_match": "true",
            }
        )
    inventory = tmp_path / "normalised_hashes.csv"
    _write_csv(inventory, ["ticker", "normalised_series_file_hash"], inventory_rows)
    inventory_hash = _sha256(inventory)
    bundle_config = snapshot_root / "gma6b.yaml"
    bundle_config.write_text(
        yaml.safe_dump(
            {
                "provider": {"auto_adjust": False, "actions": True},
                "eligibility": {"required_tickers": EXPANDED_29},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    bundle_manifest = snapshot_root / "bundle.json"
    bundle_manifest.write_text(
        json.dumps(
            {
                "normalised_file_hashes_hash": inventory_hash,
                "requested_tickers": EXPANDED_29,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    bundle_hash = _sha256(bundle_manifest)
    manifest_rows.extend(
        [
            {
                "relative_path": BUNDLE_CONFIG_RELATIVE_PATH,
                "source_path": "Z:\\must_not_be_used\\gma6b.yaml",
                "snapshot_path": str(bundle_config),
                "snapshot_sha256": _sha256(bundle_config),
                "hash_match": "true",
            },
            {
                "relative_path": BUNDLE_MANIFEST_RELATIVE_PATH,
                "source_path": "Z:\\must_not_be_used\\bundle.json",
                "snapshot_path": str(bundle_manifest),
                "snapshot_sha256": bundle_hash,
                "hash_match": "true",
            },
        ]
    )
    snapshot_manifest = tmp_path / "snapshot_manifest.csv"
    manifest_fields = [
        "relative_path",
        "source_path",
        "snapshot_path",
        "snapshot_sha256",
        "hash_match",
    ]
    _write_csv(snapshot_manifest, manifest_fields, manifest_rows)
    snapshot_hash = _sha256(snapshot_manifest)

    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["gma8a_parent"] = {
        "config_path": str(parent_config.relative_to(worktree)),
        "universe_registry_path": str(universe.relative_to(worktree)),
        "strategy_grid_registry_path": str(strategy.relative_to(worktree)),
        "lock_path": str(parent_lock.relative_to(worktree)),
        "execution_manifest_path": str(parent_execution.relative_to(worktree)),
        "expected_lock_sha256": _sha256(parent_lock),
        "expected_base_strategy_template_count": 80,
        "expected_arm_trial_count": 160,
        "expected_strategy_grid_hash": GRID_HASH,
    }
    raw["frozen_metadata_roots"] = {
        "immutable_snapshot_root": str(snapshot_root),
        "snapshot_manifest_path": str(snapshot_manifest),
        "normalised_inventory_path": str(inventory),
        "snapshot_manifest_sha256": snapshot_hash,
        "gma6b_bundle_config_relative_path": BUNDLE_CONFIG_RELATIVE_PATH,
        "gma6b_bundle_manifest_relative_path": BUNDLE_MANIFEST_RELATIVE_PATH,
    }
    raw["frozen_lineage"] = {
        "gma6_snapshot_manifest_hash": snapshot_hash,
        "gma6b_data_bundle_manifest_hash": bundle_hash,
        "normalised_bundle_hash": inventory_hash,
    }
    config = worktree / "gma8b.yaml"
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(gma8b, "SNAPSHOT_MANIFEST_HASH", snapshot_hash)
    monkeypatch.setattr(gma8b, "BUNDLE_MANIFEST_HASH", bundle_hash)
    monkeypatch.setattr(gma8b, "NORMALISED_BUNDLE_HASH", inventory_hash)
    return {
        "worktree": worktree,
        "config": config,
        "snapshot_root": snapshot_root,
        "snapshot_manifest": snapshot_manifest,
        "manifest_fields": manifest_fields,
        "inventory": inventory,
        "source_paths": source_paths,
    }


def _manifest_rows(case: dict[str, object]) -> list[dict[str, str]]:
    path = case["snapshot_manifest"]
    assert isinstance(path, Path)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _rewrite_manifest(case: dict[str, object], rows: list[dict[str, str]], monkeypatch) -> None:
    path = case["snapshot_manifest"]
    fields = case["manifest_fields"]
    config = case["config"]
    assert isinstance(path, Path) and isinstance(fields, list) and isinstance(config, Path)
    _write_csv(path, fields, rows)
    digest = _sha256(path)
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    raw["frozen_metadata_roots"]["snapshot_manifest_sha256"] = digest
    raw["frozen_lineage"]["gma6_snapshot_manifest_hash"] = digest
    config.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(gma8b, "SNAPSHOT_MANIFEST_HASH", digest)


def test_gma8a_parent_verifies_80_templates_and_160_arm_trials(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    lock_hash, maximum = validate_gma8a_parent(load_settings(case["config"], case["worktree"]))
    assert len(lock_hash) == 64
    assert maximum == 252


def test_production_contract_uses_only_two_direct_metadata_roots():
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    roots = raw["frozen_metadata_roots"]
    assert set(roots) == {
        "immutable_snapshot_root",
        "snapshot_manifest_path",
        "normalised_inventory_path",
        "snapshot_manifest_sha256",
        "gma6b_bundle_config_relative_path",
        "gma6b_bundle_manifest_relative_path",
    }
    assert "source_pointer" not in json.dumps(raw).casefold()


def test_snapshot_manifest_hash_is_required(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    settings = load_settings(case["config"], case["worktree"])
    settings.snapshot_manifest_path.write_text("changed\n", encoding="utf-8")
    with pytest.raises(GMA8BSourceResolutionError, match="snapshot-manifest SHA-256"):
        resolve_sources(settings)


def test_inventory_is_exact_unique_expanded_29(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    resolution = resolve_sources(load_settings(case["config"], case["worktree"]))
    assert [source.ticker for source in resolution.sources] == EXPANDED_29
    assert len({source.ticker for source in resolution.sources}) == 29


def test_each_inventory_hash_maps_to_exactly_one_manifest_row(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    rows = _manifest_rows(case)
    rows.append(dict(rows[0]))
    _rewrite_manifest(case, rows, monkeypatch)
    with pytest.raises(GMA8BSourceResolutionError, match="2 snapshot-manifest matches"):
        resolve_sources(load_settings(case["config"], case["worktree"]))


@pytest.mark.parametrize("failure", ["missing", "outside", "hash_match", "actual_hash"])
def test_missing_outside_or_hash_mismatched_series_fails_closed(tmp_path, monkeypatch, failure):
    case = _synthetic_case(tmp_path, monkeypatch)
    rows = _manifest_rows(case)
    target = rows[0]
    if failure == "missing":
        target["snapshot_path"] = str(Path(case["snapshot_root"]) / "missing.csv")
        _rewrite_manifest(case, rows, monkeypatch)
    elif failure == "outside":
        outside = tmp_path / "outside.csv"
        outside.write_text("outside\n", encoding="utf-8")
        target["snapshot_path"] = str(outside)
        _rewrite_manifest(case, rows, monkeypatch)
    elif failure == "hash_match":
        target["hash_match"] = "false"
        _rewrite_manifest(case, rows, monkeypatch)
    else:
        source_paths = case["source_paths"]
        assert isinstance(source_paths, dict)
        source_paths["SPY"].write_text("changed\n", encoding="utf-8")
    with pytest.raises(GMA8BSourceResolutionError):
        resolve_sources(load_settings(case["config"], case["worktree"]))


def test_source_path_is_provenance_only_and_never_read(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    resolution = resolve_sources(load_settings(case["config"], case["worktree"]))
    assert all(
        "must_not_be_used" in source.source_path_provenance_only for source in resolution.sources
    )
    assert all(source.snapshot_path.is_file() for source in resolution.sources)


@pytest.mark.parametrize(
    ("kind", "date_value", "price_value"),
    [
        ("invalid_date", "invalid", None),
        ("missing", None, ""),
        ("nonnumeric", None, "bad"),
        ("nonfinite", None, "nan"),
        ("zero", None, "0"),
        ("negative", None, "-1"),
    ],
)
def test_invalid_observations_fail_closed(tmp_path, kind, date_value, price_value):
    path = tmp_path / f"{kind}.csv"
    rows = _price_rows()
    if date_value is not None:
        rows[1]["date"] = date_value
    if price_value is not None:
        rows[1]["adj_close"] = price_value
    _write_csv(path, EXACT_COLUMNS, rows)
    source = ResolvedSource("SPY", path, _sha256(path), "synthetic", "not-used")
    with pytest.raises(GMA8BDataQualityError):
        inspect_source(source, 253)


@pytest.mark.parametrize("kind", ["duplicate", "unordered"])
def test_duplicate_or_unordered_dates_fail_closed(tmp_path, kind):
    path = tmp_path / f"{kind}.csv"
    rows = _price_rows()
    rows[1]["date"] = rows[0]["date"] if kind == "duplicate" else "1999-12-31"
    _write_csv(path, EXACT_COLUMNS, rows)
    source = ResolvedSource("SPY", path, _sha256(path), "synthetic", "not-used")
    with pytest.raises(GMA8BDataQualityError):
        inspect_source(source, 253)


def test_253_session_eligibility_is_point_in_time_correct(tmp_path):
    path = tmp_path / "SPY.csv"
    _write_csv(path, EXACT_COLUMNS, _price_rows())
    source = ResolvedSource("SPY", path, _sha256(path), "synthetic", "not-used")
    asset = inspect_source(source, 253)
    assert asset.first_253_session_eligible_date == "2000-09-09"
    assert asset.observed_session_count == 260


def test_arm_coverage_and_cross_arm_start_are_deterministic(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    result = audit(load_settings(case["config"], case["worktree"]))
    by_arm = {row["universe_arm"]: row for row in result.arm_rows}
    core = by_arm[CORE_ARM_ID]["arm_first_all_assets_253_session_eligible_date"]
    expanded = by_arm[EXPANDED_ARM_ID]["arm_first_all_assets_253_session_eligible_date"]
    assert core < expanded
    assert result.cross_arm_start == expanded


def test_no_fill_interpolation_substitution_or_backfill_is_used():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for prohibited in [".ffill(", ".bfill(", ".interpolate(", "replacement_ticker"]:
        assert prohibited not in source


def test_no_strategy_or_execution_workflow_is_imported_or_invoked():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for prohibited in [
        "yfinance",
        "run_backtest",
        "gma4_tournament",
        "fit(",
        "predict(",
        "submit_order(",
        "create_paper_order(",
    ]:
        assert prohibited not in source


def test_no_recursive_traversal_or_directory_scan_is_used():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for prohibited in ["Get-ChildItem", "Path.rglob", "Path.glob", "os.walk", "glob.glob"]:
        assert prohibited not in source


def test_output_generation_is_deterministic(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    output = tmp_path / "output"
    generate(case["config"], output, case["worktree"])
    first = {name: (output / name).read_bytes() for name in OUTPUT_FILENAMES}
    generate(case["config"], output, case["worktree"])
    second = {name: (output / name).read_bytes() for name in OUTPUT_FILENAMES}
    assert first == second


def test_lock_contains_required_values(tmp_path, monkeypatch):
    case = _synthetic_case(tmp_path, monkeypatch)
    output = tmp_path / "output"
    generate(case["config"], output, case["worktree"])
    lock = json.loads((output / "gma8b_data_lock_v1.json").read_text(encoding="utf-8"))
    assert lock["resolved_normalised_series_count"] == 29
    assert lock["resolved_adjusted_price_source_kind"] == (
        "per_ticker_normalised_series_from_immutable_snapshot"
    )
    assert lock["maximum_strategy_lookback_sessions"] == 252
    assert lock["required_price_sessions_for_maximum_lookback"] == 253
    assert lock["inherited_historical_adjusted_price_files_read"] is True
    for field in FALSE_OPERATION_FIELDS:
        assert lock[field] is False
