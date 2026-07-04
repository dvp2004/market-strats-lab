from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE_COMMIT = "86a49fc"
PHASE_ID = "gma7a_predictive_ensemble_contract_v1"
ACTIVE_COHORT = "etf_multi_asset_core_v1"
DEFERRED_COHORTS = ["crypto_directional_v1", "direct_futures_and_commodity_v1"]
CORE_22_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
    "BIL",
    "IEF",
    "TLT",
    "AGG",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
]
FEATURE_FAMILIES = [
    "trend_and_momentum",
    "short_horizon_mean_reversion",
    "realised_volatility_drawdown_and_correlation_risk",
    "cross_asset_regime_context",
]
MODEL_BLOCKS = [
    "regularised_linear_return_rank_model",
    "bounded_gradient_boosted_tree_return_rank_model",
    "risk_downside_model",
    "deterministic_cross_asset_regime_model",
    "fixed_equal_weight_ensemble_of_qualifying_return_scores",
]
RETURN_SCORE_COMPONENTS = [
    "regularised_linear_return_rank_model",
    "bounded_gradient_boosted_tree_return_rank_model",
    "deterministic_cross_asset_regime_model",
]
RISK_OVERLAY = "risk_downside_model"
GBDT_GRID = {
    "max_depth": [2, 3],
    "learning_rate": [0.03, 0.05],
    "n_estimators": [100, 250],
    "min_samples_leaf": [10, 25],
    "subsample": [0.7, 1.0],
}
COST_SCENARIOS = ["baseline_1bps", "stressed_10bps", "stressed_25bps", "severe_50bps"]
REQUIRED_LANGUAGE = [
    "This is observed development evidence and not a pristine final holdout.",
    "The 2021-01-04 through 2026-05-01 period is a GMA-7 model-specific lockbox.",
    "Highest historical CAGR or Sharpe alone is not a selection rule.",
    "No execution or promotion decision is produced.",
]
H2_SNAPSHOT_ROOT = Path(
    r"C:\Users\Devesh Pansare\Desktop\Personal_Projects\market-strats-lab-gma5-v1-evidence-snapshot-20260623"
)
H3_SNAPSHOT_ROOT = Path(
    r"C:\Users\Devesh Pansare\Desktop\Personal_Projects\market-strats-lab-gma6-v1-evidence-snapshot-20260624"
)
GMA6F_LOCK_RELATIVE_PATH = "reports/global_multi_asset_alpha/gma6_cross_universe_tournament_v1/gma6f_universe_classification_locks_v1.json"
OUTPUT_PATHS = {
    "config": Path("configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml"),
    "docs": Path("docs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.md"),
    "csv": Path(
        "reports/global_multi_asset_alpha/gma7a_predictive_ensemble_preregistration_v1.csv"
    ),
    "md": Path("reports/global_multi_asset_alpha/gma7a_predictive_ensemble_preregistration_v1.md"),
    "lock": Path("reports/global_multi_asset_alpha/gma7a_predictive_ensemble_lock_v1.json"),
}


class GMA7AContractError(ValueError):
    pass


@dataclass(frozen=True)
class ParentReferenceVerification:
    gma5_snapshot_root: str
    gma5_snapshot_manifest_sha256: str
    gma6_snapshot_root: str
    gma6_snapshot_manifest_sha256: str
    gma6_snapshot_verification_sha256: str
    gma6f_classification_lock_in_manifest: bool


def sha256_hex(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_parent_references(
    h2: Path = H2_SNAPSHOT_ROOT, h3: Path = H3_SNAPSHOT_ROOT
) -> ParentReferenceVerification:
    h2_manifest = h2 / "gma5_v1_evidence_snapshot_manifest_v1.csv"
    h3_manifest = h3 / "gma6_v1_evidence_snapshot_manifest_v1.csv"
    h3_verification = h3 / "gma6_v1_evidence_snapshot_verification_v1.csv"
    for path in [h2_manifest, h3_manifest, h3_verification]:
        if not path.is_file():
            raise GMA7AContractError(f"Missing immutable parent reference: {path}")
    rows = list(csv.DictReader(h3_manifest.open("r", encoding="utf-8-sig", newline="")))
    in_manifest = any(
        row.get("relative_path", "").replace("\\", "/") == GMA6F_LOCK_RELATIVE_PATH for row in rows
    )
    if not in_manifest:
        raise GMA7AContractError(
            "GMA-6F classification lock is absent from the GMA-6 snapshot manifest"
        )
    return ParentReferenceVerification(
        str(h2),
        sha256_hex(h2_manifest),
        str(h3),
        sha256_hex(h3_manifest),
        sha256_hex(h3_verification),
        True,
    )


def build_feature_specs() -> list[dict[str, str]]:
    common = {
        "observation_timestamp": "monthly decision-session close",
        "availability_timestamp": "decision_timestamp_after_decision_session_close",
        "decision_timestamp": "after the decision-session close",
        "allowed_lag": "available_by_monthly_decision_session_close_only",
        "missing_data_treatment": "predeclared_missing_as_unavailable_no_forward_target_leakage",
    }
    specs = [
        (
            "total_return_momentum_12m_excluding_recent_month",
            "trend_and_momentum",
            "time_series_and_cross_sectional_rank",
        ),
        ("total_return_momentum_6m", "trend_and_momentum", "time_series_and_cross_sectional_rank"),
        (
            "short_horizon_5d_reversal",
            "short_horizon_mean_reversion",
            "time_series_signal_cross_sectional_rank_monthly_only",
        ),
        (
            "realised_volatility_63d",
            "realised_volatility_drawdown_and_correlation_risk",
            "time_series_risk_measure_and_cross_sectional_rank",
        ),
        (
            "maximum_drawdown_252d",
            "realised_volatility_drawdown_and_correlation_risk",
            "time_series_risk_measure_and_cross_sectional_rank",
        ),
        (
            "cross_asset_regime_trend_breadth",
            "cross_asset_regime_context",
            "cross_sectional_context_broadcast_to_assets",
        ),
    ]
    return [
        {
            **common,
            "feature_name": name,
            "feature_family": family,
            "source": "future_gma7b_etf_multi_asset_core_v1_feature_store",
            "cross_sectional_or_time_series_treatment": treatment,
        }
        for name, family, treatment in specs
    ]


def build_target_specs() -> list[dict[str, Any]]:
    same_interval = "same_forward_20_trading_session_interval_from_next_executable_session"
    return [
        {
            "target_name": "relative_return_target",
            "definition": "asset_total_return_from_next_executable_session_to_horizon_end minus BIL_total_return_over_the_same_interval",
            "target_start": "next tradable session after the decision timestamp",
            "horizon": "20 trading sessions",
            "same_interval_as_bil": same_interval,
            "decision_session_close_to_close_return_included": False,
        },
        {
            "target_name": "outperform_BIL_target",
            "definition": "asset_total_return_over_the_same_interval greater_than BIL_total_return_over_the_same_interval",
            "target_start": "next tradable session after the decision timestamp",
            "horizon": "20 trading sessions",
            "same_interval_as_bil": same_interval,
            "decision_session_close_to_close_return_included": False,
        },
        {
            "target_name": "downside_risk_target",
            "definition": "realised_downside_risk_over_the_same_forward_20_trading_session_interval",
            "target_start": "next tradable session after the decision timestamp",
            "horizon": "20 trading sessions",
            "same_interval_as_bil": same_interval,
            "decision_session_close_to_close_return_included": False,
        },
    ]


def build_model_blocks() -> list[dict[str, Any]]:
    return [
        {
            "model_id": "regularised_linear_return_rank_model",
            "allowed_objectives": [
                "relative_return_rank_regression",
                "BIL_outperformance_classification",
            ],
            "family_counting_rule": "one_regularised_linear_model_family",
        },
        {
            "model_id": "bounded_gradient_boosted_tree_return_rank_model",
            "allowed_grid": GBDT_GRID,
            "unlimited_search_allowed": False,
            "bayesian_search_allowed": False,
            "random_search_allowed": False,
            "neural_network_allowed": False,
            "reinforcement_learning_allowed": False,
        },
        {"model_id": "risk_downside_model", "role": "risk_overlay_only_not_return_score_component"},
        {
            "model_id": "deterministic_cross_asset_regime_model",
            "role": "qualifying_return_score_component_candidate",
        },
        {
            "model_id": "fixed_equal_weight_ensemble_of_qualifying_return_scores",
            "role": "fixed_equal_weight_return_score_ensemble",
            "learned_stacker_allowed": False,
            "adaptive_ensemble_weight_optimizer_allowed": False,
        },
    ]


def build_portfolio_rule() -> dict[str, Any]:
    return {
        "monthly_rebalance_schedule": "final eligible decision session of each calendar month",
        "eligible_asset_filter": "non_BIL_assets_with_positive_standardised_return_score",
        "selection_rule": "select_up_to_top_5_eligible_assets",
        "position_weight_method": "equal_weight_across_selected_risky_assets",
        "BIL_fallback_rule": "BIL_receives_unallocated_or_risk_scaled_residual_weight",
        "maximum_single_risky_asset_weight": 0.20,
        "maximum_total_risky_asset_exposure": 1.00,
        "score_standardisation_method": "cross_sectional_z_score_over_non_BIL_assets",
        "turnover_measurement_method": "one_way_monthly_turnover",
        "cost_scenarios": COST_SCENARIOS,
        "risk_overlay": {
            "target_annualised_portfolio_volatility": 0.10,
            "risk_scaling_floor": 0.00,
            "risk_scaling_cap": 1.00,
        },
        "execution_price_convention": "match_frozen_parent_GMA_next_tradable_session_execution_convention",
        "model_specific_leverage_allowed": False,
        "model_specific_concentration_rule_allowed": False,
        "model_specific_rebalance_frequency_allowed": False,
        "model_specific_cost_treatment_allowed": False,
    }


def build_qualification_gates() -> dict[str, Any]:
    return {
        "return_score_component_entry_gates_at_stressed_10bps": {
            "positive_median_fold_net_active_return_vs_core22_equal_weight_benchmark": True,
            "positive_chronological_test_folds_minimum": 3,
            "maximum_single_fold_share_of_total_active_return_maximum": 0.50,
            "aggregate_maximum_drawdown_worsening_vs_benchmark_maximum": 0.03,
            "highest_cagr_or_sharpe_alone_sufficient": False,
        },
        "risk_downside_overlay_gates": {
            "no_worse_than_0.03_aggregate_active_return_vs_benchmark": True,
            "aggregate_maximum_drawdown_improvement_or_no_worsening_vs_benchmark": True,
            "stability_across_at_least_3_chronological_test_folds": True,
        },
    }


def build_contract(parent_refs: ParentReferenceVerification) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "contract_version": "v1",
        "base_commit": BASE_COMMIT,
        "evidence_class": "observed_development_evidence",
        "required_language": REQUIRED_LANGUAGE,
        "parent_references": {
            "gma5_v1_evidence_snapshot": {
                "root": parent_refs.gma5_snapshot_root,
                "manifest_sha256": parent_refs.gma5_snapshot_manifest_sha256,
                "role": "immutable_gma4_gma5_parent_reference",
            },
            "gma6_v1_evidence_snapshot": {
                "root": parent_refs.gma6_snapshot_root,
                "manifest_sha256": parent_refs.gma6_snapshot_manifest_sha256,
                "verification_sha256": parent_refs.gma6_snapshot_verification_sha256,
                "gma6f_classification_lock_in_manifest": parent_refs.gma6f_classification_lock_in_manifest,
                "role": "immutable_gma6_parent_reference",
            },
            "execution_convention_parent": {
                "source_path": "src/market_strats/global_multi_asset/gma4_replay_adapter.py",
                "immutable_reference": BASE_COMMIT,
                "execution_price_convention": "monthly signal observed at decision-session close; earliest execution is the next tradable session using the frozen parent GMA next-session execution convention",
            },
        },
        "cohorts": {
            "active": [ACTIVE_COHORT],
            "deferred": [
                {
                    "cohort_id": cohort,
                    "status": "deferred_separately_versioned_future_workstream",
                    "allowed_in_gma7a_through_gma7e": False,
                }
                for cohort in DEFERRED_COHORTS
            ],
        },
        "universe": {
            "cohort_id": ACTIVE_COHORT,
            "symbols": CORE_22_UNIVERSE,
            "bil_role": "tradeable_defensive_cash_proxy_and_relative_return_benchmark",
        },
        "partitions": {
            "development_and_nested_walk_forward": {
                "start_date": "2007-05-30",
                "end_date": "2020-12-31",
                "minimum_chronological_development_folds": 4,
            },
            "locked_outer_evaluation": {
                "name": "GMA-7 model-specific lockbox",
                "start_date": "2021-01-04",
                "end_date": "2026-05-01",
                "pristine_holdout_claim_allowed": False,
            },
            "label_horizon": "20 trading sessions",
            "purge_embargo": "20 trading sessions",
            "hyperparameter_selection_scope": "training_portion_of_each_development_fold_only",
            "training_label_overlap_with_test_target_interval_allowed": False,
        },
        "timing": {
            "signal_observation_cutoff": "monthly decision-session close",
            "decision_timestamp": "after the decision-session close",
            "earliest_execution_timestamp": "next tradable session",
            "target_start": "next tradable session after the decision timestamp",
            "portfolio_rebalance_frequency": "monthly",
            "decision_session_close_to_close_target_return_allowed": False,
        },
        "feature_families": FEATURE_FAMILIES,
        "features": build_feature_specs(),
        "targets": build_target_specs(),
        "model_blocks": build_model_blocks(),
        "ensemble": {
            "return_score_components": RETURN_SCORE_COMPONENTS,
            "component_score_standardisation": "cross_sectional_z_score_at_decision_timestamp",
            "ensemble_weighting": "fixed_equal_weight_across_qualifying_return_scores",
            "learned_optimised_adaptive_or_performance_weighted_weights_allowed": False,
            "risk_overlay": RISK_OVERLAY,
            "risk_overlay_averaged_into_return_scores_allowed": False,
            "risk_overlay_allowed_actions": [
                "fixed_predeclared_exposure_cap",
                "risk_scaling_rule",
                "eligibility_filter",
            ],
        },
        "portfolio_construction": build_portfolio_rule(),
        "qualification_gates": build_qualification_gates(),
        "p1_boundary": {
            "P-1 strategy": "frozen GMA-5 equal-weight atomic sleeve portfolio",
            "P-1 purpose": "forward operational and performance observation",
            "P-1 rule changes": "prohibited after its manual-paper contract is locked",
            "GMA-7 research outputs": "cannot alter P-1 rules",
            "p1_files_created_by_gma7a": False,
        },
        "scope_boundaries": {
            "design_only": True,
            "download_data_allowed": False,
            "construct_feature_store_allowed": False,
            "fit_model_allowed": False,
            "calculate_forecasts_allowed": False,
            "generate_targets_allowed": False,
            "run_strategy_allowed": False,
            "replay_portfolio_allowed": False,
            "calculate_performance_allowed": False,
            "paper_account_allowed": False,
            "broker_connection_allowed": False,
            "live_trading_path_allowed": False,
            "gma4_gma5_gma6_files_mutable": False,
        },
        "terminal_boundary": {
            "after_gma7a_stop": True,
            "only_permitted_next_task": "GMA-7B feature-store construction for etf_multi_asset_core_v1",
        },
    }


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("phase_id") != PHASE_ID or contract.get("base_commit") != BASE_COMMIT:
        raise GMA7AContractError("phase or base commit mismatch")
    if contract["cohorts"]["active"] != [ACTIVE_COHORT]:
        raise GMA7AContractError("GMA-7 V1 must have exactly one active cohort")
    if [item["cohort_id"] for item in contract["cohorts"]["deferred"]] != DEFERRED_COHORTS:
        raise GMA7AContractError("Deferred cohorts are not exact")
    if any(item["allowed_in_gma7a_through_gma7e"] for item in contract["cohorts"]["deferred"]):
        raise GMA7AContractError("Deferred cohorts cannot be active through GMA-7E")
    if contract["universe"]["symbols"] != CORE_22_UNIVERSE:
        raise GMA7AContractError("Core-22 universe order mismatch")
    partitions = contract["partitions"]
    dev = partitions["development_and_nested_walk_forward"]
    lockbox = partitions["locked_outer_evaluation"]
    if dev["start_date"] != "2007-05-30" or dev["end_date"] != "2020-12-31":
        raise GMA7AContractError("Development partition mismatch")
    if dev["minimum_chronological_development_folds"] < 4:
        raise GMA7AContractError("At least four chronological development folds are required")
    if lockbox["name"] != "GMA-7 model-specific lockbox":
        raise GMA7AContractError("Lockbox name mismatch")
    if lockbox["start_date"] != "2021-01-04" or lockbox["end_date"] != "2026-05-01":
        raise GMA7AContractError("Lockbox date mismatch")
    if lockbox["pristine_holdout_claim_allowed"]:
        raise GMA7AContractError("The lockbox cannot be called pristine")
    if (
        partitions["label_horizon"] != "20 trading sessions"
        or partitions["purge_embargo"] != "20 trading sessions"
    ):
        raise GMA7AContractError("Label horizon and purge embargo must both be 20 trading sessions")
    if partitions["training_label_overlap_with_test_target_interval_allowed"]:
        raise GMA7AContractError("Training labels cannot overlap test target intervals")
    if contract["feature_families"] != FEATURE_FAMILIES:
        raise GMA7AContractError("Feature family list mismatch")
    required_feature_fields = {
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
        missing = sorted(required_feature_fields - set(feature))
        if missing:
            raise GMA7AContractError(f"Feature missing required fields: {missing}")
        if feature["feature_family"] not in FEATURE_FAMILIES:
            raise GMA7AContractError("Feature uses an unapproved family")
    if contract["timing"]["decision_session_close_to_close_target_return_allowed"]:
        raise GMA7AContractError("Targets cannot include decision-session close-to-close return")
    for target in contract["targets"]:
        if target["target_start"] != "next tradable session after the decision timestamp":
            raise GMA7AContractError("Target start mismatch")
        if target["decision_session_close_to_close_return_included"]:
            raise GMA7AContractError("Target includes forbidden decision-session return")
    model_ids = [item["model_id"] for item in contract["model_blocks"]]
    if model_ids != MODEL_BLOCKS:
        raise GMA7AContractError("Model block list mismatch")
    tree_model = next(
        item
        for item in contract["model_blocks"]
        if item["model_id"] == "bounded_gradient_boosted_tree_return_rank_model"
    )
    if tree_model["allowed_grid"] != GBDT_GRID:
        raise GMA7AContractError("Gradient boosted tree grid mismatch")
    if (
        tree_model["unlimited_search_allowed"]
        or tree_model["bayesian_search_allowed"]
        or tree_model["random_search_allowed"]
    ):
        raise GMA7AContractError("Unbounded model search is prohibited")
    ensemble = contract["ensemble"]
    if ensemble["return_score_components"] != RETURN_SCORE_COMPONENTS:
        raise GMA7AContractError("Return-score components mismatch")
    if ensemble["ensemble_weighting"] != "fixed_equal_weight_across_qualifying_return_scores":
        raise GMA7AContractError("Only equal ensemble weights are allowed")
    if (
        ensemble["risk_overlay"] != RISK_OVERLAY
        or ensemble["risk_overlay_averaged_into_return_scores_allowed"]
    ):
        raise GMA7AContractError("Risk overlay cannot be averaged into return scores")
    portfolio = contract["portfolio_construction"]
    if (
        portfolio["monthly_rebalance_schedule"]
        != "final eligible decision session of each calendar month"
    ):
        raise GMA7AContractError("Rebalance schedule mismatch")
    if portfolio["cost_scenarios"] != COST_SCENARIOS:
        raise GMA7AContractError("Cost scenario list mismatch")
    if (
        portfolio["maximum_single_risky_asset_weight"] != 0.20
        or portfolio["maximum_total_risky_asset_exposure"] != 1.00
    ):
        raise GMA7AContractError("Portfolio exposure caps mismatch")
    if portfolio["risk_overlay"]["target_annualised_portfolio_volatility"] != 0.10:
        raise GMA7AContractError("Risk overlay target volatility mismatch")
    return_gates = contract["qualification_gates"][
        "return_score_component_entry_gates_at_stressed_10bps"
    ]
    if return_gates["positive_chronological_test_folds_minimum"] != 3:
        raise GMA7AContractError("Return-score fold gate mismatch")
    if return_gates["highest_cagr_or_sharpe_alone_sufficient"]:
        raise GMA7AContractError("Highest CAGR or Sharpe alone cannot qualify a component")
    if (
        contract["p1_boundary"]["P-1 strategy"]
        != "frozen GMA-5 equal-weight atomic sleeve portfolio"
    ):
        raise GMA7AContractError("P-1 strategy boundary mismatch")
    if contract["p1_boundary"]["p1_files_created_by_gma7a"]:
        raise GMA7AContractError("GMA-7A cannot create P-1 files")
    for line in REQUIRED_LANGUAGE:
        if line not in contract["required_language"]:
            raise GMA7AContractError(f"Missing required language: {line}")
    forbidden_true = [
        key
        for key, value in contract["scope_boundaries"].items()
        if key.endswith("_allowed") and value
    ]
    if forbidden_true:
        raise GMA7AContractError(f"Forbidden scope flag enabled: {forbidden_true}")


def load_contract(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA7AContractError("Contract YAML must be a mapping")
    return raw


def current_head_short(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, text=True
    ).strip()


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def markdown_table(rows: list[list[str]]) -> str:
    header = rows[0]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join(lines)


def preregistration_rows(contract: dict[str, Any]) -> list[dict[str, str]]:
    rows = [
        {
            "record_type": "phase",
            "name": "phase_id",
            "value": PHASE_ID,
            "status": "locked",
            "notes": "design_only",
        },
        {
            "record_type": "cohort",
            "name": "active",
            "value": ACTIVE_COHORT,
            "status": "active",
            "notes": "only active cohort",
        },
    ]
    rows.extend(
        {
            "record_type": "universe",
            "name": "core22_symbol",
            "value": symbol,
            "status": "locked",
            "notes": ACTIVE_COHORT,
        }
        for symbol in contract["universe"]["symbols"]
    )
    rows.extend(
        {
            "record_type": "cohort",
            "name": "deferred",
            "value": item["cohort_id"],
            "status": "deferred",
            "notes": item["status"],
        }
        for item in contract["cohorts"]["deferred"]
    )
    rows.extend(
        {
            "record_type": "feature_family",
            "name": family,
            "value": family,
            "status": "locked",
            "notes": "permitted",
        }
        for family in FEATURE_FAMILIES
    )
    rows.extend(
        {
            "record_type": "model_block",
            "name": model,
            "value": model,
            "status": "locked",
            "notes": "permitted",
        }
        for model in MODEL_BLOCKS
    )
    rows.extend(
        {
            "record_type": "required_language",
            "name": "boundary",
            "value": line,
            "status": "locked",
            "notes": "must appear",
        }
        for line in REQUIRED_LANGUAGE
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["record_type", "name", "value", "status", "notes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_contract_markdown(contract: dict[str, Any]) -> str:
    cohort_rows = [["cohort", "status"], [ACTIVE_COHORT, "active"]]
    cohort_rows.extend([item["cohort_id"], "deferred"] for item in contract["cohorts"]["deferred"])
    model_rows = [["model block", "role"]]
    model_rows.extend(
        [item["model_id"], item.get("role", "return/risk model family")]
        for item in contract["model_blocks"]
    )
    return "\n".join(
        [
            "# GMA-7A Predictive Ensemble Research Contract V1",
            "",
            "This document preregisters a design-only predictive multi-asset ETF research contract.",
            "",
            *REQUIRED_LANGUAGE,
            "",
            "## Active and Deferred Cohorts",
            "",
            markdown_table(cohort_rows),
            "",
            "## Core-22 Universe",
            "",
            ", ".join(CORE_22_UNIVERSE),
            "",
            "## Partitions and Timing",
            "",
            "Development and nested walk-forward: 2007-05-30 through 2020-12-31.",
            "Locked outer evaluation: 2021-01-04 through 2026-05-01, the GMA-7 model-specific lockbox.",
            "Label horizon and purge embargo are both 20 trading sessions.",
            "Targets start at the next tradable session after the decision timestamp and exclude decision-session close-to-close return.",
            "",
            "## Feature Families",
            "",
            "- " + "\n- ".join(FEATURE_FAMILIES),
            "",
            "## Model Blocks",
            "",
            markdown_table(model_rows),
            "",
            "## Ensemble and Risk Overlay",
            "",
            "Return scores come only from the regularised linear, bounded tree, and deterministic regime components. Qualifying component scores are cross-sectionally standardised at the decision timestamp and combined with fixed equal weights only. The risk/downside model is a risk overlay only and cannot be averaged into return scores.",
            "",
            "## Portfolio Construction",
            "",
            "The shared monthly score-to-portfolio rule selects up to the top 5 non-BIL assets with positive standardised scores, equal-weights selected risky assets, assigns residual weight to BIL, caps each risky asset at 0.20, and caps total risky exposure at 1.00. Cost scenarios are baseline_1bps, stressed_10bps, stressed_25bps, and severe_50bps.",
            "",
            "## P-1 Boundary",
            "",
            "P-1 strategy = frozen GMA-5 equal-weight atomic sleeve portfolio. P-1 purpose = forward operational and performance observation. P-1 rule changes = prohibited after its manual-paper contract is locked. GMA-7 research outputs = cannot alter P-1 rules.",
            "",
            "## Scope Boundary",
            "",
            "GMA-7A creates design and validation-contract evidence only. It does not fetch data, construct a feature store, fit a model, calculate forecasts, generate targets, run a strategy, replay a portfolio, calculate performance, create a paper account, connect to a broker, or create a live-trading path.",
            "",
        ]
    )


def build_preregistration_markdown(contract: dict[str, Any]) -> str:
    table = [["record_type", "name", "value", "status"]]
    table.extend(
        [row["record_type"], row["name"], row["value"], row["status"]]
        for row in preregistration_rows(contract)
    )
    return "\n".join(
        [
            "# GMA-7A Predictive Ensemble Preregistration V1",
            "",
            "This report is design-only preregistration evidence for etf_multi_asset_core_v1.",
            "",
            markdown_table(table),
            "",
        ]
    )


def build_lock(
    contract: dict[str, Any], parent_refs: ParentReferenceVerification
) -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "contract_version": "v1",
        "base_commit": BASE_COMMIT,
        "active_cohorts": contract["cohorts"]["active"],
        "deferred_cohorts": DEFERRED_COHORTS,
        "core22_universe_hash": hashlib.sha256("|".join(CORE_22_UNIVERSE).encode()).hexdigest(),
        "feature_families": FEATURE_FAMILIES,
        "model_blocks": MODEL_BLOCKS,
        "gbdt_grid": GBDT_GRID,
        "parent_references": parent_refs.__dict__,
        "design_only": True,
        "no_execution_or_promotion_decision": True,
    }


def generate_contract_files(
    repo_root: Path, *, require_base_commit: bool = True
) -> dict[str, Path]:
    parent_refs = verify_parent_references()
    contract = build_contract(parent_refs)
    validate_contract(contract)
    if require_base_commit:
        head = current_head_short(repo_root)
        if head != BASE_COMMIT:
            raise GMA7AContractError(
                f"GMA-7A worktree must be detached at {BASE_COMMIT}; found {head}"
            )
    write_yaml(repo_root / OUTPUT_PATHS["config"], contract)
    (repo_root / OUTPUT_PATHS["docs"]).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / OUTPUT_PATHS["docs"]).write_text(
        build_contract_markdown(contract), encoding="utf-8"
    )
    write_csv(repo_root / OUTPUT_PATHS["csv"], preregistration_rows(contract))
    (repo_root / OUTPUT_PATHS["md"]).write_text(
        build_preregistration_markdown(contract), encoding="utf-8"
    )
    (repo_root / OUTPUT_PATHS["lock"]).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / OUTPUT_PATHS["lock"]).write_text(
        json.dumps(build_lock(contract, parent_refs), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {key: repo_root / value for key, value in OUTPUT_PATHS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GMA-7A design-only contract files")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    outputs = generate_contract_files(args.repo_root)
    for key, path in sorted(outputs.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
