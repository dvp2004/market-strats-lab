from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset.gma8a_broad_multi_asset_tournament_contract import (
    ACTIVE_SCOPE,
    CONTRACT_ID,
    CORE_22,
    CORE_ARM_ID,
    DEFERRED_COHORTS,
    EXPANDED_29,
    EXPANDED_ARM_ID,
    FALSE_EXECUTION_FLAGS,
    GMA8AContractError,
    OUTPUT_FILENAMES,
    REQUIRED_COST_SCENARIOS,
    REQUIRED_EVALUATION_SCOPES,
    REQUIRED_FAMILIES,
    REQUIRED_GATES,
    REQUIRED_REGIME_IDS,
    REQUIRED_STRATEGY_FIELDS,
    SOURCE_COMMIT,
    generate_artifacts,
    load_contract,
    validate_contract,
)

CONFIG_PATH = Path(
    "configs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.yaml"
)
SOURCE_PATH = Path(
    "src/market_strats/global_multi_asset/gma8a_broad_multi_asset_tournament_contract.py"
)
ALLOWED_PATHS = {
    CONFIG_PATH.as_posix(),
    "docs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.md",
    SOURCE_PATH.as_posix(),
    "tests/test_gma8a_broad_multi_asset_tournament_contract.py",
    "configs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8b_historical_data_provenance.py",
    "tests/test_gma8b_historical_data_provenance.py",
    "configs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8b_source_pointer_intake.py",
    "tests/test_gma8b_source_pointer_intake.py",
    "configs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.yaml",
    "docs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.md",
    "src/market_strats/global_multi_asset/gma8c_frozen_etf_etp_tournament.py",
    "tests/test_gma8c_frozen_etf_etp_tournament.py",
}


def _grid_hash(templates: list[dict]) -> str:
    payload = json.dumps(templates, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.fixture()
def synthetic_contract_path(tmp_path: Path) -> Path:
    raw = deepcopy(load_contract(CONFIG_PATH).raw)
    path = tmp_path / "synthetic_gma8a_contract.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture()
def contract(synthetic_contract_path: Path):
    loaded = load_contract(synthetic_contract_path)
    validate_contract(loaded)
    return loaded


def test_worktree_is_detached_from_required_commit():
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert branch == ""
    assert head == SOURCE_COMMIT


def test_active_scope_is_honest_etf_etp_only(contract):
    identity = contract.raw["contract"]
    assert identity["contract_id"] == CONTRACT_ID
    assert identity["active_scope"] == ACTIVE_SCOPE
    assert identity["result_evidence_scope"] == "ETF/ETP strategies only"
    assert set(identity["result_scope_exclusions"]) == {
        "direct_commodity",
        "crypto",
        "stock_selection",
        "direct_futures",
        "FX",
    }


def test_core_22_is_exact_and_ordered(contract):
    assert contract.raw["universe_arms"][CORE_ARM_ID]["symbols"] == CORE_22
    assert len(CORE_22) == 22


def test_expanded_29_is_exact_ordered_and_contains_core_once(contract):
    symbols = contract.raw["universe_arms"][EXPANDED_ARM_ID]["symbols"]
    assert symbols == EXPANDED_29
    assert len(symbols) == 29
    assert symbols[:22] == CORE_22
    assert all(symbols.count(symbol) == 1 for symbol in CORE_22)
    assert set(symbols) - set(CORE_22) == {"VNQ", "TIP", "USO", "DBA", "SLV", "EWG", "EWJ"}


def test_gma6_boundary_and_uso_metadata_are_frozen(contract):
    boundary = contract.raw["gma6_boundary"]
    assert all(boundary.values())
    metadata = contract.raw["universe_arms"][EXPANDED_ARM_ID]["symbol_metadata"]
    assert metadata["USO"] == "uso_roll_methodology_pre_may_2020_vs_from_may_2020"
    assert "USO" in EXPANDED_29 and "DBA" in EXPANDED_29


def test_all_deferred_cohorts_are_present_and_blocked(contract):
    deferred = contract.raw["deferred_cohorts"]
    assert [row["cohort_id"] for row in deferred] == DEFERRED_COHORTS
    assert all(row["blocked_until_separate_contract"] for row in deferred)
    assert all(row["reason"] for row in deferred)


def test_grid_is_exactly_enumerated_and_hash_locked(contract):
    grid = contract.raw["strategy_grid"]
    assert len(contract.strategy_templates) == 80
    assert grid["maximum_base_strategy_template_count"] == 80
    assert grid["maximum_arm_trial_count"] == 160
    assert grid["exact_base_strategy_template_count"] == 80
    assert grid["exact_arm_trial_count"] == 160
    assert grid["strategy_grid_hash"] == _grid_hash(contract.strategy_templates)


def test_every_strategy_has_fixed_required_fields_and_unique_id(contract):
    ids = []
    for row in contract.strategy_templates:
        assert REQUIRED_STRATEGY_FIELDS <= set(row)
        assert all(row[field] not in (None, "", []) for field in REQUIRED_STRATEGY_FIELDS)
        assert row["eligible_universe_arm"] == [CORE_ARM_ID, EXPANDED_ARM_ID]
        ids.append(row["strategy_id"])
    assert len(ids) == len(set(ids)) == 80


def test_no_free_form_or_unbounded_parameter_search(contract):
    grid = contract.raw["strategy_grid"]
    assert grid["parameter_search"] == "finite_preregistered_grid_only"
    assert grid["additions_removals_or_changes_after_result_viewing_allowed"] is False


def test_each_required_family_has_minimum_fixed_grid_coverage(contract):
    by_family = {
        family: [row for row in contract.strategy_templates if row["strategy_family"] == family]
        for family in REQUIRED_FAMILIES
    }
    assert all(by_family.values())
    assert {50, 100, 150, 200, 252} <= {
        row["lookback_sessions"] for row in by_family["absolute_trend"]
    }
    momentum = by_family["cross_sectional_momentum"]
    assert {21, 63, 126, 252} <= {row["lookback_sessions"] for row in momentum}
    assert {3, 5, 8} <= {row["maximum_positions"] for row in momentum}
    assert {"top_n_equal_weight", "top_n_inverse_volatility_63_sessions"} <= {
        row["portfolio_construction"] for row in momentum
    }
    mean_reversion = by_family["short_horizon_mean_reversion"]
    assert {2, 5, 10} <= {row["lookback_sessions"] for row in mean_reversion}
    assert {3, 5} <= {row["maximum_positions"] for row in mean_reversion}
    breakout = by_family["breakout_trend_following"]
    assert {20, 60, 120} <= {row["lookback_sessions"] for row in breakout}
    volatility = by_family["volatility_targeting_and_inverse_volatility"]
    assert {21, 63, 126} <= {row["lookback_sessions"] for row in volatility}
    overlays = by_family["drawdown_and_defensive_overlays"]
    assert {"drawdown_0.10", "drawdown_0.15", "drawdown_0.20"} <= {
        row["ranking_or_trigger_rule"] for row in overlays
    }


def test_development_outer_period_and_endpoint_pin_are_exact(contract):
    evaluation = contract.raw["evaluation"]
    assert evaluation["development_and_selection_period"] == {
        "start_date": "2007-05-30",
        "end_date": "2020-12-31",
    }
    assert evaluation["gma8_strategy_specific_outer_evaluation"] == {
        "start_date": "2021-01-04",
        "end_date": "gma8b_frozen_data_endpoint",
    }
    assert evaluation["gma8b_endpoint_must_be_pinned_before_market_data_read"] is True
    assert evaluation["outer_period_is_pristine_programme_wide_holdout"] is False


def test_matched_benchmarks_and_long_only_unlevered_rules(contract):
    rules = contract.raw["benchmark_and_exposure"]
    assert rules["primary_active_return_comparator_by_arm"] == {
        CORE_ARM_ID: "gma8_core_22_equal_weight_monthly_benchmark",
        EXPANDED_ARM_ID: "gma8_expanded_29_equal_weight_monthly_benchmark",
    }
    assert rules["reference_benchmarks_only"] == ["SPY", "BIL"]
    assert rules["shorting"] == "prohibited"
    assert rules["gross_exposure_maximum"] == 1.0
    assert rules["risk_overlay_may_only_reduce_risky_exposure"] is True
    assert rules["residual_weight_destination"] == "BIL"


def test_regime_windows_are_chronological_nonempty_and_endpoint_locked(contract):
    regimes = contract.raw["regime_windows"]
    assert [row["regime_id"] for row in regimes] == REQUIRED_REGIME_IDS
    for row in regimes:
        if row["end_date"] != "gma8b_frozen_endpoint":
            assert row["start_date"] <= row["end_date"]
        assert row["tuning_period"] is False
    assert "latest" not in json.dumps(regimes).casefold()


def test_cost_scenarios_scopes_and_gates_are_exact(contract):
    evaluation = contract.raw["evaluation"]
    assert evaluation["cost_scenarios"] == REQUIRED_COST_SCENARIOS
    assert evaluation["evaluation_scopes"] == REQUIRED_EVALUATION_SCOPES
    assert [row["gate_id"] for row in contract.raw["robustness_gates"]] == REQUIRED_GATES
    assert all(
        row["status"] == "preregistered_not_evaluated" for row in contract.raw["robustness_gates"]
    )


def test_concentration_formulas_and_zero_denominator_failure_are_exact(contract):
    definitions = contract.raw["concentration_definitions"]
    assert definitions["largest_fold_return_share"] == (
        "maximum_positive_fold_active_return / sum_positive_fold_active_returns"
    )
    assert definitions["largest_regime_return_share"] == (
        "maximum_positive_regime_active_return / sum_positive_regime_active_returns"
    )
    assert definitions["zero_denominator_result"] == "fail_gate"


def test_learned_predictive_ensembles_are_excluded(contract):
    grid_text = json.dumps(contract.strategy_templates).casefold()
    assert "learned" not in grid_text
    assert "stacking" not in grid_text
    assert contract.raw["contract"]["result_status"] == "preregistered_not_run"


def test_malformed_contract_fails_closed(synthetic_contract_path: Path):
    raw = yaml.safe_load(synthetic_contract_path.read_text(encoding="utf-8"))
    raw["strategy_grid"]["base_templates"][0].pop("rebalance_frequency")
    raw["strategy_grid"]["strategy_grid_hash"] = _grid_hash(raw["strategy_grid"]["base_templates"])
    synthetic_contract_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(GMA8AContractError, match="missing fields"):
        validate_contract(load_contract(synthetic_contract_path))


def test_generation_creates_all_outputs_with_160_arm_trials(
    synthetic_contract_path: Path, tmp_path: Path
):
    output_root = tmp_path / "reports"
    paths = generate_artifacts(synthetic_contract_path, output_root)
    assert [path.name for path in paths] == OUTPUT_FILENAMES
    with (output_root / "gma8a_strategy_grid_registry_v1.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 160
    assert len({row["arm_trial_id"] for row in rows}) == 160
    assert {row["eligible_universe_arm"] for row in rows} == {CORE_ARM_ID, EXPANDED_ARM_ID}


def test_generation_is_deterministic(synthetic_contract_path: Path, tmp_path: Path):
    output_root = tmp_path / "reports"
    generate_artifacts(synthetic_contract_path, output_root)
    first = {name: (output_root / name).read_bytes() for name in OUTPUT_FILENAMES}
    generate_artifacts(synthetic_contract_path, output_root)
    second = {name: (output_root / name).read_bytes() for name in OUTPUT_FILENAMES}
    assert first == second


def test_lock_and_manifest_prove_design_only_execution(
    synthetic_contract_path: Path, tmp_path: Path
):
    output_root = tmp_path / "reports"
    generate_artifacts(synthetic_contract_path, output_root)
    lock = json.loads((output_root / "gma8a_lock_v1.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output_root / "gma8a_execution_manifest_v1.json").read_text(encoding="utf-8")
    )
    for field in FALSE_EXECUTION_FLAGS:
        assert lock[field] is False
        assert manifest[field] is False
    assert manifest["market_data_paths_read"] == []
    assert lock["exact_base_strategy_template_count"] == 80
    assert lock["exact_arm_trial_count"] == 160


def test_generated_text_has_required_research_boundary(
    synthetic_contract_path: Path, tmp_path: Path
):
    output_root = tmp_path / "reports"
    generate_artifacts(synthetic_contract_path, output_root)
    text = (output_root / "gma8a_preregistration_v1.md").read_text(encoding="utf-8")
    assert "Highest historical CAGR or Sharpe alone is not a selection rule." in text
    assert "No execution or promotion decision is produced." in text
    assert "GMA-8B" in text
    assert "ETF/ETP" in text


def test_module_does_not_import_or_invoke_tournament_or_execution_paths():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for forbidden in [
        "gma4_tournament",
        "gma6d_cross_universe_tournament",
        "run_backtest",
        "yfinance",
        "requests",
        "urllib",
        "import broker",
        "submit_order(",
        "create_paper_order(",
    ]:
        assert forbidden not in source


def test_only_gma8a_allowed_paths_are_changed_or_untracked():
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed = {line[3:].replace("\\", "/") for line in status if line.strip()}
    assert changed <= ALLOWED_PATHS
