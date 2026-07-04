from __future__ import annotations

import ast
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from market_strats.global_multi_asset import gma7a_predictive_ensemble_contract as gma7a

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml")


@pytest.fixture(scope="module")
def contract():
    return gma7a.load_contract(CONFIG_PATH)


def test_new_worktree_is_detached_from_86a49fc():
    head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert head == gma7a.BASE_COMMIT
    assert branch == ""


def test_core22_is_only_active_gma7_cohort(contract):
    assert contract["cohorts"]["active"] == ["etf_multi_asset_core_v1"]


def test_crypto_and_futures_are_deferred_only(contract):
    deferred = contract["cohorts"]["deferred"]
    assert [item["cohort_id"] for item in deferred] == [
        "crypto_directional_v1",
        "direct_futures_and_commodity_v1",
    ]
    assert all(item["allowed_in_gma7a_through_gma7e"] is False for item in deferred)


def test_core22_ticker_order_is_exact(contract):
    assert contract["universe"]["symbols"] == gma7a.CORE_22_UNIVERSE
    assert contract["universe"]["symbols"][14] == "BIL"


def test_development_and_lockbox_dates_are_exact(contract):
    dev = contract["partitions"]["development_and_nested_walk_forward"]
    lockbox = contract["partitions"]["locked_outer_evaluation"]
    assert dev["start_date"] == "2007-05-30"
    assert dev["end_date"] == "2020-12-31"
    assert dev["minimum_chronological_development_folds"] >= 4
    assert lockbox["name"] == "GMA-7 model-specific lockbox"
    assert lockbox["start_date"] == "2021-01-04"
    assert lockbox["end_date"] == "2026-05-01"
    assert lockbox["pristine_holdout_claim_allowed"] is False


def test_every_feature_has_timestamp_lag_and_treatment_fields(contract):
    required = {
        "feature_name",
        "feature_family",
        "source",
        "observation_timestamp",
        "availability_timestamp",
        "decision_timestamp",
        "allowed_lag",
        "missing_data_treatment",
        "cross_sectional_or_time_series_treatment",
    }
    for feature in contract["features"]:
        assert required <= set(feature)
        assert feature["feature_family"] in gma7a.FEATURE_FAMILIES
        assert "decision" in feature["availability_timestamp"]


def test_no_target_includes_decision_session_close_to_close_return(contract):
    assert contract["timing"]["decision_session_close_to_close_target_return_allowed"] is False
    for target in contract["targets"]:
        assert target["target_start"] == "next tradable session after the decision timestamp"
        assert target["decision_session_close_to_close_return_included"] is False


def test_twenty_session_purge_embargo_is_required(contract):
    assert contract["partitions"]["label_horizon"] == "20 trading sessions"
    assert contract["partitions"]["purge_embargo"] == "20 trading sessions"
    assert (
        contract["partitions"]["training_label_overlap_with_test_target_interval_allowed"] is False
    )


def test_model_family_list_is_exact(contract):
    assert [item["model_id"] for item in contract["model_blocks"]] == gma7a.MODEL_BLOCKS


def test_gradient_boosted_grid_is_finite_and_exact(contract):
    tree = next(
        item
        for item in contract["model_blocks"]
        if item["model_id"] == "bounded_gradient_boosted_tree_return_rank_model"
    )
    assert tree["allowed_grid"] == gma7a.GBDT_GRID
    assert tree["unlimited_search_allowed"] is False
    assert tree["bayesian_search_allowed"] is False
    assert tree["random_search_allowed"] is False
    assert tree["neural_network_allowed"] is False
    assert tree["reinforcement_learning_allowed"] is False


def test_ensemble_uses_equal_weights_only(contract):
    ensemble = contract["ensemble"]
    assert ensemble["return_score_components"] == gma7a.RETURN_SCORE_COMPONENTS
    assert ensemble["ensemble_weighting"] == "fixed_equal_weight_across_qualifying_return_scores"
    assert ensemble["learned_optimised_adaptive_or_performance_weighted_weights_allowed"] is False


def test_risk_overlay_cannot_be_averaged_into_return_scores(contract):
    ensemble = contract["ensemble"]
    assert ensemble["risk_overlay"] == "risk_downside_model"
    assert ensemble["risk_overlay_averaged_into_return_scores_allowed"] is False
    assert "risk_downside_model" not in ensemble["return_score_components"]


def test_component_entry_gates_are_exact(contract):
    gates = contract["qualification_gates"]
    return_gates = gates["return_score_component_entry_gates_at_stressed_10bps"]
    assert (
        return_gates["positive_median_fold_net_active_return_vs_core22_equal_weight_benchmark"]
        is True
    )
    assert return_gates["positive_chronological_test_folds_minimum"] == 3
    assert return_gates["maximum_single_fold_share_of_total_active_return_maximum"] == 0.50
    assert return_gates["aggregate_maximum_drawdown_worsening_vs_benchmark_maximum"] == 0.03
    assert return_gates["highest_cagr_or_sharpe_alone_sufficient"] is False
    risk_gates = gates["risk_downside_overlay_gates"]
    assert risk_gates["no_worse_than_0.03_aggregate_active_return_vs_benchmark"] is True
    assert risk_gates["aggregate_maximum_drawdown_improvement_or_no_worsening_vs_benchmark"] is True
    assert risk_gates["stability_across_at_least_3_chronological_test_folds"] is True


def test_common_portfolio_construction_rule_is_shared_and_fixed(contract):
    rule = contract["portfolio_construction"]
    assert (
        rule["monthly_rebalance_schedule"]
        == "final eligible decision session of each calendar month"
    )
    assert rule["eligible_asset_filter"] == "non_BIL_assets_with_positive_standardised_return_score"
    assert rule["selection_rule"] == "select_up_to_top_5_eligible_assets"
    assert rule["position_weight_method"] == "equal_weight_across_selected_risky_assets"
    assert rule["BIL_fallback_rule"] == "BIL_receives_unallocated_or_risk_scaled_residual_weight"
    assert rule["maximum_single_risky_asset_weight"] == 0.20
    assert rule["maximum_total_risky_asset_exposure"] == 1.00
    assert rule["score_standardisation_method"] == "cross_sectional_z_score_over_non_BIL_assets"
    assert rule["turnover_measurement_method"] == "one_way_monthly_turnover"
    assert rule["cost_scenarios"] == gma7a.COST_SCENARIOS
    assert rule["risk_overlay"]["target_annualised_portfolio_volatility"] == 0.10
    assert rule["model_specific_leverage_allowed"] is False
    assert rule["model_specific_cost_treatment_allowed"] is False


def test_no_data_strategy_replay_allocation_paper_broker_or_live_imports():
    source = Path(gma7a.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = [
        "gma4_tournament",
        "gma5",
        "gma6",
        "replay",
        "strategy",
        "allocation",
        "paper",
        "broker",
        "live",
    ]
    assert not any(any(fragment in module for fragment in forbidden) for module in imported)


def test_no_prior_gma_or_master_report_file_is_modified():
    status = subprocess.check_output(["git", "status", "--short"], text=True).splitlines()
    changed_paths = [line[3:] for line in status]
    assert changed_paths
    forbidden_fragments = [
        "gma4_",
        "gma5_",
        "gma6_",
        "gma_research_",
        "master",
    ]
    assert not any(
        any(fragment in path for fragment in forbidden_fragments) for path in changed_paths
    )


def test_contract_generation_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    subprocess.run(["git", "worktree", "list"], check=True, capture_output=True, text=True)
    # Use the real repo root as source of generated content; compare two pure builds in temp roots.
    for root in [first, second]:
        (root / "src").mkdir(parents=True)
        gma7a.generate_contract_files(root, require_base_commit=False)
    for key, rel in gma7a.OUTPUT_PATHS.items():
        assert (first / rel).read_text(encoding="utf-8") == (second / rel).read_text(
            encoding="utf-8"
        ), key


def test_validate_contract_rejects_mutated_active_cohort(contract):
    bad = deepcopy(contract)
    bad["cohorts"]["active"] = ["etf_multi_asset_core_v1", "crypto_directional_v1"]
    with pytest.raises(gma7a.GMA7AContractError):
        gma7a.validate_contract(bad)


def test_required_language_and_parent_reference_verification(contract):
    for line in gma7a.REQUIRED_LANGUAGE:
        assert line in contract["required_language"]
    parents = contract["parent_references"]
    assert parents["gma6_v1_evidence_snapshot"]["gma6f_classification_lock_in_manifest"] is True
    assert parents["execution_convention_parent"]["immutable_reference"] == gma7a.BASE_COMMIT


def test_p1_boundary_is_design_only(contract):
    p1 = contract["p1_boundary"]
    assert p1["P-1 strategy"] == "frozen GMA-5 equal-weight atomic sleeve portfolio"
    assert p1["P-1 rule changes"] == "prohibited after its manual-paper contract is locked"
    assert p1["GMA-7 research outputs"] == "cannot alter P-1 rules"
    assert p1["p1_files_created_by_gma7a"] is False
