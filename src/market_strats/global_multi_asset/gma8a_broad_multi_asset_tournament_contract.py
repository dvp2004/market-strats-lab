"""GMA-8A broad ETF/ETP tournament preregistration and artifact generation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

CONTRACT_ID = "gma8a_broad_multi_asset_tournament_contract_v1"
ACTIVE_SCOPE = "broad_etf_etp_strategy_tournament_v1"
SOURCE_COMMIT = "86a49fc3cc589ea9b2835423524e33e5fb8cc208"
CORE_ARM_ID = "gma8_core_22_etf_v1"
EXPANDED_ARM_ID = "gma8_expanded_29_etp_v1"
CORE_22 = [
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
EXPANDED_29 = [*CORE_22, "VNQ", "TIP", "USO", "DBA", "SLV", "EWG", "EWJ"]
DEFERRED_COHORTS = [
    "individual_us_equities_survivorship_free_v1",
    "crypto_directional_24x7_v1",
    "direct_futures_continuous_contracts_v1",
    "fx_directional_v1",
]
REQUIRED_FAMILIES = [
    "benchmark_buy_and_hold",
    "benchmark_equal_weight_monthly",
    "absolute_trend",
    "cross_sectional_momentum",
    "short_horizon_mean_reversion",
    "breakout_trend_following",
    "volatility_targeting_and_inverse_volatility",
    "drawdown_and_defensive_overlays",
    "fixed_rule_blends",
]
REQUIRED_COST_SCENARIOS = [
    "baseline_1bps",
    "stressed_10bps",
    "stressed_25bps",
    "severe_50bps",
]
REQUIRED_EVALUATION_SCOPES = [
    "full_history",
    "rolling_3_year",
    "rolling_5_year",
    "chronological_walk_forward",
    "predefined_regime_windows",
]
REQUIRED_REGIME_IDS = [
    "global_financial_crisis_2007_10_to_2009_03",
    "post_gfc_recovery_2009_04_to_2012_12",
    "taper_and_commodity_stress_2013_01_to_2015_12",
    "late_cycle_and_trade_stress_2016_01_to_2019_12",
    "covid_crash_and_recovery_2020_02_to_2021_03",
    "inflation_rate_shock_2022_01_to_2023_12",
    "recent_geopolitical_stress_2023_10_to_gma8b_frozen_endpoint",
]
REQUIRED_METRICS = [
    "gross_return",
    "net_return",
    "CAGR",
    "Sharpe",
    "Sortino",
    "maximum_drawdown",
    "Calmar",
    "annualised_turnover",
    "cost_drag",
    "maximum_HHI",
    "positive_fold_count",
    "largest_fold_return_share",
    "regime_window_results",
    "largest_regime_return_share",
]
REQUIRED_GATES = [
    "positive_net_active_return_vs_benchmark_at_stressed_10bps",
    "at_least_3_positive_chronological_test_folds",
    "largest_fold_return_share_lte_0_50",
    "maximum_drawdown_not_worse_than_benchmark_by_more_than_0_03",
    "no_single_regime_window_accounts_for_majority_of_total_active_return",
    "turnover_and_cost_drag_reported",
]
REQUIRED_STRATEGY_FIELDS = {
    "strategy_id",
    "strategy_family",
    "signal_inputs",
    "lookback_sessions",
    "formation_frequency",
    "rebalance_frequency",
    "ranking_or_trigger_rule",
    "portfolio_construction",
    "maximum_positions",
    "fallback_asset_or_cash_rule",
    "risk_overlay_rule",
    "turnover_control_rule",
    "eligible_universe_arm",
}
FALSE_EXECUTION_FLAGS = [
    "data_download_performed",
    "market_data_read",
    "indicator_calculation_performed",
    "model_fit_performed",
    "backtest_performed",
    "strategy_ranking_performed",
    "portfolio_target_generated",
    "paper_broker_or_live_path_created",
]
OUTPUT_FILENAMES = [
    "gma8a_universe_arm_registry_v1.csv",
    "gma8a_deferred_cohort_registry_v1.csv",
    "gma8a_strategy_grid_registry_v1.csv",
    "gma8a_regime_window_registry_v1.csv",
    "gma8a_metric_registry_v1.csv",
    "gma8a_robustness_gate_registry_v1.csv",
    "gma8a_preregistration_v1.md",
    "gma8a_lock_v1.json",
    "gma8a_execution_manifest_v1.json",
]


class GMA8AContractError(ValueError):
    """Raised when the frozen GMA-8A design contract is invalid."""


@dataclass(frozen=True)
class GMA8AContract:
    path: Path
    raw: dict[str, Any]
    strategy_templates: list[dict[str, Any]]


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_contract(path: str | Path) -> GMA8AContract:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA8AContractError("GMA-8A contract must be a YAML mapping")
    templates = (raw.get("strategy_grid") or {}).get("base_templates")
    if not isinstance(templates, list):
        raise GMA8AContractError("strategy_grid.base_templates must be a list")
    return GMA8AContract(config_path, raw, templates)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GMA8AContractError(message)


def _validate_strategy_coverage(templates: list[dict[str, Any]]) -> None:
    by_family: dict[str, list[dict[str, Any]]] = {
        family: [row for row in templates if row["strategy_family"] == family]
        for family in REQUIRED_FAMILIES
    }
    _require(all(by_family.values()), "every required strategy family must be represented")

    absolute = by_family["absolute_trend"]
    _require(
        {50, 100, 150, 200, 252} <= {row["lookback_sessions"] for row in absolute},
        "absolute trend lookbacks are incomplete",
    )

    momentum = by_family["cross_sectional_momentum"]
    _require(
        {21, 63, 126, 252} <= {row["lookback_sessions"] for row in momentum},
        "cross-sectional momentum lookbacks are incomplete",
    )
    _require(
        {3, 5, 8} <= {row["maximum_positions"] for row in momentum},
        "cross-sectional momentum position counts are incomplete",
    )
    momentum_constructions = {row["portfolio_construction"] for row in momentum}
    _require(
        {"top_n_equal_weight", "top_n_inverse_volatility_63_sessions"} <= momentum_constructions,
        "cross-sectional momentum constructions are incomplete",
    )

    mean_reversion = by_family["short_horizon_mean_reversion"]
    _require(
        {2, 5, 10} <= {row["lookback_sessions"] for row in mean_reversion},
        "mean-reversion lookbacks are incomplete",
    )
    _require(
        {3, 5} <= {row["maximum_positions"] for row in mean_reversion},
        "mean-reversion position counts are incomplete",
    )
    _require(
        all("maximum_holding_sessions=" in row["turnover_control_rule"] for row in mean_reversion),
        "mean-reversion holding periods must be fixed",
    )

    breakout = by_family["breakout_trend_following"]
    _require(
        {20, 60, 120} <= {row["lookback_sessions"] for row in breakout},
        "breakout windows are incomplete",
    )
    _require(
        all(row["fallback_asset_or_cash_rule"] == "residual_to_BIL" for row in breakout),
        "breakout strategies must use BIL fallback",
    )

    volatility = by_family["volatility_targeting_and_inverse_volatility"]
    _require(
        {21, 63, 126} <= {row["lookback_sessions"] for row in volatility},
        "volatility windows are incomplete",
    )
    _require(
        {"target_volatility_0.08", "target_volatility_0.10", "target_volatility_0.12"}
        <= {row["risk_overlay_rule"] for row in volatility},
        "volatility targets are incomplete",
    )

    overlays = by_family["drawdown_and_defensive_overlays"]
    _require(
        {"drawdown_0.10", "drawdown_0.15", "drawdown_0.20"}
        <= {row["ranking_or_trigger_rule"] for row in overlays},
        "drawdown thresholds are incomplete",
    )
    _require(
        {"defensive_fallback_BIL", "defensive_fallback_IEF", "defensive_fallback_AGG"}
        <= {row["fallback_asset_or_cash_rule"] for row in overlays},
        "defensive fallbacks are incomplete",
    )

    blends = by_family["fixed_rule_blends"]
    _require(
        all(row["portfolio_construction"] == "equal_weight_fixed_components" for row in blends),
        "all blends must use fixed equal component weights",
    )


def validate_contract(contract: GMA8AContract) -> None:
    raw = contract.raw
    identity = raw.get("contract") or {}
    _require(identity.get("contract_id") == CONTRACT_ID, "contract_id is invalid")
    _require(identity.get("active_scope") == ACTIVE_SCOPE, "active_scope is invalid")
    _require(identity.get("source_commit") == SOURCE_COMMIT, "source_commit is invalid")
    _require(identity.get("design_only") is True, "GMA-8A must remain design-only")

    boundary = raw.get("gma6_boundary") or {}
    for field in [
        "gma6_v1_classifications_remain_unchanged",
        "gma8_expanded_29_is_not_a_gma6_subset_or_rescue_search",
        "no_27_instrument_fallback_arm",
    ]:
        _require(boundary.get(field) is True, f"gma6_boundary.{field} must be true")

    arms = raw.get("universe_arms") or {}
    _require(
        (arms.get(CORE_ARM_ID) or {}).get("symbols") == CORE_22, "Core-22 must be exact and ordered"
    )
    _require(
        (arms.get(EXPANDED_ARM_ID) or {}).get("symbols") == EXPANDED_29,
        "Expanded-29 must be exact and ordered",
    )
    _require(EXPANDED_29[: len(CORE_22)] == CORE_22, "Core-22 ordering must be preserved")
    _require(len(set(EXPANDED_29) - set(CORE_22)) == 7, "Expanded-29 must add seven assets")
    expanded_metadata = (arms.get(EXPANDED_ARM_ID) or {}).get("symbol_metadata") or {}
    _require(
        expanded_metadata.get("USO") == "uso_roll_methodology_pre_may_2020_vs_from_may_2020",
        "USO methodology metadata is required",
    )
    _require(
        "USO" in EXPANDED_29 and "DBA" in EXPANDED_29, "USO and DBA must remain in Expanded-29"
    )

    deferred = raw.get("deferred_cohorts") or []
    _require(
        [row.get("cohort_id") for row in deferred] == DEFERRED_COHORTS,
        "deferred cohorts must be exact and ordered",
    )
    _require(
        all(row.get("blocked_until_separate_contract") is True for row in deferred),
        "all deferred cohorts must be blocked",
    )

    grid = raw.get("strategy_grid") or {}
    templates = contract.strategy_templates
    _require(
        grid.get("parameter_search") == "finite_preregistered_grid_only",
        "free-form parameter search is prohibited",
    )
    _require(
        grid.get("maximum_base_strategy_template_count") == 80,
        "maximum base template count must be 80",
    )
    _require(grid.get("maximum_arm_trial_count") == 160, "maximum arm trial count must be 160")
    _require(
        grid.get("exact_base_strategy_template_count") == 80 and len(templates) == 80,
        "the registry must enumerate exactly 80 base templates",
    )
    _require(grid.get("exact_arm_trial_count") == 160, "the frozen arm-trial count must be 160")
    _require(
        grid.get("strategy_grid_hash") == _canonical_hash(templates),
        "strategy_grid_hash does not match the explicit template grid",
    )

    strategy_ids = [str(row.get("strategy_id")) for row in templates]
    _require(len(strategy_ids) == len(set(strategy_ids)), "strategy IDs must be unique")
    for row in templates:
        missing = sorted(REQUIRED_STRATEGY_FIELDS - set(row))
        _require(not missing, f"{row.get('strategy_id')} missing fields: {missing}")
        for field in REQUIRED_STRATEGY_FIELDS:
            _require(
                row[field] not in (None, "", []),
                f"{row['strategy_id']}.{field} must be fixed and non-empty",
            )
        _require(
            row["eligible_universe_arm"] == [CORE_ARM_ID, EXPANDED_ARM_ID],
            f"{row['strategy_id']} must be preregistered for both arms",
        )
        _require(
            row["risk_overlay_rule"] != "may_increase_gross_exposure",
            "risk overlays may not increase gross exposure",
        )
    _require(
        {row["strategy_family"] for row in templates} == set(REQUIRED_FAMILIES),
        "strategy families must match the frozen family set",
    )
    serialized_grid = json.dumps(templates).casefold()
    for forbidden in ["learned", "stacking", "dynamic optimisation", "free-form", "unbounded"]:
        _require(
            forbidden not in serialized_grid, f"strategy grid contains prohibited term: {forbidden}"
        )
    _validate_strategy_coverage(templates)

    evaluation = raw.get("evaluation") or {}
    _require(
        evaluation.get("development_and_selection_period")
        == {"start_date": "2007-05-30", "end_date": "2020-12-31"},
        "development period is invalid",
    )
    outer = evaluation.get("gma8_strategy_specific_outer_evaluation") or {}
    _require(outer.get("start_date") == "2021-01-04", "outer evaluation start is invalid")
    _require(
        outer.get("end_date") == "gma8b_frozen_data_endpoint",
        "outer evaluation must end at the frozen GMA-8B endpoint",
    )
    _require(
        evaluation.get("gma8b_endpoint_must_be_pinned_before_market_data_read") is True,
        "GMA-8B endpoint must be pinned before market-data read",
    )
    _require(
        evaluation.get("outer_period_is_pristine_programme_wide_holdout") is False,
        "the GMA-8 outer period is not a programme-wide pristine holdout",
    )
    _require(
        evaluation.get("evaluation_scopes") == REQUIRED_EVALUATION_SCOPES,
        "evaluation scopes are invalid",
    )
    _require(
        evaluation.get("cost_scenarios") == REQUIRED_COST_SCENARIOS, "cost scenarios are invalid"
    )

    benchmark = raw.get("benchmark_and_exposure") or {}
    _require(
        benchmark.get("primary_active_return_comparator_by_arm")
        == {
            CORE_ARM_ID: "gma8_core_22_equal_weight_monthly_benchmark",
            EXPANDED_ARM_ID: "gma8_expanded_29_equal_weight_monthly_benchmark",
        },
        "matched-universe active-return comparators are invalid",
    )
    _require(
        benchmark.get("reference_benchmarks_only") == ["SPY", "BIL"],
        "SPY and BIL must remain reference benchmarks only",
    )
    _require(benchmark.get("shorting") == "prohibited", "shorting must be prohibited")
    _require(benchmark.get("gross_exposure_maximum") == 1.0, "gross exposure maximum must be 1.00")
    _require(
        benchmark.get("risk_overlay_may_only_reduce_risky_exposure") is True,
        "risk overlays may only reduce risky exposure",
    )
    _require(
        benchmark.get("residual_weight_destination") == "BIL", "residual weight must go to BIL"
    )

    regimes = raw.get("regime_windows") or []
    _require(
        [row.get("regime_id") for row in regimes] == REQUIRED_REGIME_IDS,
        "regime identifiers are invalid",
    )
    for row in regimes:
        start = date.fromisoformat(row["start_date"])
        if row["end_date"] != "gma8b_frozen_endpoint":
            _require(
                start <= date.fromisoformat(row["end_date"]),
                f"{row['regime_id']} is empty or reversed",
            )
        _require(row.get("tuning_period") is False, "regime windows are reporting-only")
    _require(
        "latest" not in json.dumps(regimes).casefold(),
        "rolling latest regime endpoints are prohibited",
    )

    leakage = raw.get("leakage_controls") or {}
    expected_leakage = {
        "decision_after_session_close": True,
        "earliest_execution": "next_tradable_session",
        "no_future_price_in_signal": True,
        "no_future_price_in_label_or_metric": True,
        "chronological_train_test_separation_required": True,
        "embargo_sessions": 20,
        "same_cost_assumption_for_all_comparisons": True,
        "same_data_snapshot_per_universe_arm": True,
    }
    _require(leakage == expected_leakage, "leakage controls are invalid")
    _require(
        (raw.get("metrics") or {}).get("required") == REQUIRED_METRICS,
        "required metrics are invalid",
    )

    concentration = raw.get("concentration_definitions") or {}
    _require(
        concentration.get("largest_fold_return_share")
        == "maximum_positive_fold_active_return / sum_positive_fold_active_returns",
        "fold concentration formula is invalid",
    )
    _require(
        concentration.get("largest_regime_return_share")
        == "maximum_positive_regime_active_return / sum_positive_regime_active_returns",
        "regime concentration formula is invalid",
    )
    _require(
        concentration.get("zero_denominator_result") == "fail_gate",
        "zero concentration denominators must fail",
    )

    gates = raw.get("robustness_gates") or []
    _require(
        [row.get("gate_id") for row in gates] == REQUIRED_GATES, "robustness gates are invalid"
    )
    _require(
        all(row.get("status") == "preregistered_not_evaluated" for row in gates),
        "no robustness gate may be marked as evaluated",
    )
    execution = raw.get("design_execution_assertions") or {}
    _require(
        all(execution.get(flag) is False for flag in FALSE_EXECUTION_FLAGS),
        "all design-only execution assertions must remain false",
    )


def _csv_text(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _pipe(value: Any) -> str:
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value)


def _universe_rows(contract: GMA8AContract) -> list[dict[str, Any]]:
    rows = []
    arms = contract.raw["universe_arms"]
    for arm_id in [CORE_ARM_ID, EXPANDED_ARM_ID]:
        arm = arms[arm_id]
        metadata = arm.get("symbol_metadata") or {}
        for ordinal, symbol in enumerate(arm["symbols"], start=1):
            role = "active_etf_etp"
            if symbol == "BIL":
                role = "tradeable_residual_asset_and_reference_benchmark"
            elif symbol == "SPY":
                role = "active_asset_and_reference_benchmark"
            rows.append(
                {
                    "universe_arm": arm_id,
                    "ordinal": ordinal,
                    "symbol": symbol,
                    "active_scope": ACTIVE_SCOPE,
                    "instrument_scope": "exchange_traded_fund_or_product",
                    "role": role,
                    "methodology_metadata": metadata.get(symbol, "not_applicable"),
                    "result_evidence_scope": "etf_etp_only",
                }
            )
    return rows


def _strategy_rows(contract: GMA8AContract) -> list[dict[str, Any]]:
    grid_hash = contract.raw["strategy_grid"]["strategy_grid_hash"]
    rows = []
    for template in contract.strategy_templates:
        for arm_id in template["eligible_universe_arm"]:
            row = {key: _pipe(template[key]) for key in REQUIRED_STRATEGY_FIELDS}
            row["arm_trial_id"] = f"{template['strategy_id']}__{arm_id}"
            row["eligible_universe_arm"] = arm_id
            row["strategy_grid_hash"] = grid_hash
            row["status"] = "preregistered_not_run"
            rows.append(row)
    return rows


def _render_preregistration(contract: GMA8AContract) -> str:
    raw = contract.raw
    family_counts = Counter(row["strategy_family"] for row in contract.strategy_templates)
    lines = [
        "# GMA-8A Broad Multi-Asset Strategy Tournament Preregistration V1",
        "",
        "GMA-8A is design-only. Its active scope is `broad_etf_etp_strategy_tournament_v1`; "
        "despite the programme name, V1 evidence is limited to exchange-traded funds and "
        "products. Individual equities, crypto, direct futures, and FX are deferred cohorts.",
        "",
        "Highest historical CAGR or Sharpe alone is not a selection rule. A strategy must be "
        "judged across costs, turnover, drawdown, chronological folds, and predefined "
        "historical regimes. No execution or promotion decision is produced.",
        "",
        "## Frozen Scope",
        "",
        f"- Base strategy templates: `{len(contract.strategy_templates)}`",
        f"- Universe-arm trials: `{len(contract.strategy_templates) * 2}`",
        f"- Strategy grid hash: `{raw['strategy_grid']['strategy_grid_hash']}`",
        f"- Core arm: `{CORE_ARM_ID}` (22 instruments, including BIL)",
        f"- Expanded arm: `{EXPANDED_ARM_ID}` (29 instruments, including USO and DBA)",
        "- No 27-instrument fallback arm exists.",
        "- GMA-6 V1 classifications remain unchanged; Expanded-29 is not a GMA-6 rescue search.",
        "",
        "GMA-8A results must never be described as direct commodity, crypto, stock-selection, "
        "futures, or FX strategy evidence. USO and DBA are historically traded ETPs. Future "
        "USO diagnostics must preserve `uso_roll_methodology_pre_may_2020_vs_from_may_2020`.",
        "",
        "## Strategy Families",
        "",
        "| Family | Base templates |",
        "|---|---:|",
    ]
    lines.extend(f"| {family} | {family_counts[family]} |" for family in REQUIRED_FAMILIES)
    lines.extend(
        [
            "",
            "Every template is explicitly enumerated in the contract. Free-form search, learned "
            "stacking, dynamic component optimisation, and post-result grid changes are prohibited.",
            "",
            "## Evaluation Lock",
            "",
            "Development and selection use 2007-05-30 through 2020-12-31. Strategy-specific outer "
            "evaluation begins 2021-01-04 and ends at the GMA-8B frozen data endpoint. GMA-8B must "
            "pin that endpoint before reading market data. The outer period is not a pristine "
            "programme-wide holdout and may not be used for strategy selection, parameter changes, "
            "universe changes, or post-hoc exclusions.",
            "",
            "Each arm's monthly equal-weight benchmark, including BIL, is its primary active-return "
            "comparator. SPY and BIL are reference benchmarks only. Strategies are long-only and "
            "unlevered; gross exposure is capped at 1.00, overlays may only reduce risky exposure, "
            "and residual weight goes to BIL.",
            "",
            "Positive fold and regime concentration shares use only positive active-return "
            "contributions. A zero positive-return denominator fails the applicable gate.",
            "",
            "## Terminal Boundary",
            "",
            "No market data was read, no indicator or model was calculated, no backtest or ranking "
            "was run, and no portfolio, paper, broker, or live path was created. The next separate "
            "reviewed phase is GMA-8B, a point-in-time historical data-universe and provenance "
            "contract for these ETF/ETP arms.",
            "",
        ]
    )
    return "\n".join(lines)


def build_artifacts(contract: GMA8AContract) -> dict[str, str]:
    validate_contract(contract)
    raw = contract.raw
    universe_rows = _universe_rows(contract)
    deferred_rows = raw["deferred_cohorts"]
    strategy_rows = _strategy_rows(contract)
    regime_rows = raw["regime_windows"]
    metric_rows = [
        {"metric_id": metric, "required": True, "status": "preregistered"}
        for metric in raw["metrics"]["required"]
    ]
    gate_rows = raw["robustness_gates"]
    artifacts = {
        OUTPUT_FILENAMES[0]: _csv_text(list(universe_rows[0]), universe_rows),
        OUTPUT_FILENAMES[1]: _csv_text(list(deferred_rows[0]), deferred_rows),
        OUTPUT_FILENAMES[2]: _csv_text(
            [
                "arm_trial_id",
                "strategy_id",
                "strategy_family",
                "signal_inputs",
                "lookback_sessions",
                "formation_frequency",
                "rebalance_frequency",
                "ranking_or_trigger_rule",
                "portfolio_construction",
                "maximum_positions",
                "fallback_asset_or_cash_rule",
                "risk_overlay_rule",
                "turnover_control_rule",
                "eligible_universe_arm",
                "strategy_grid_hash",
                "status",
            ],
            strategy_rows,
        ),
        OUTPUT_FILENAMES[3]: _csv_text(list(regime_rows[0]), regime_rows),
        OUTPUT_FILENAMES[4]: _csv_text(list(metric_rows[0]), metric_rows),
        OUTPUT_FILENAMES[5]: _csv_text(list(gate_rows[0]), gate_rows),
        OUTPUT_FILENAMES[6]: _render_preregistration(contract),
    }
    config_hash = hashlib.sha256(contract.path.read_bytes()).hexdigest()
    lock = {
        "active_scope": ACTIVE_SCOPE,
        "contract_id": CONTRACT_ID,
        "contract_version": "v1",
        "source_commit": SOURCE_COMMIT,
        "config_sha256": config_hash,
        "strategy_grid_hash": raw["strategy_grid"]["strategy_grid_hash"],
        "exact_base_strategy_template_count": len(contract.strategy_templates),
        "exact_arm_trial_count": len(strategy_rows),
        "development_and_selection_period": raw["evaluation"]["development_and_selection_period"],
        "gma8_strategy_specific_outer_evaluation": raw["evaluation"][
            "gma8_strategy_specific_outer_evaluation"
        ],
        "gma8b_endpoint_pin_required_before_market_data_read": True,
        "gma6_v1_classifications_remain_unchanged": True,
        "gma8_expanded_29_is_not_a_gma6_subset_or_rescue_search": True,
        "no_27_instrument_fallback_arm": True,
        "status": "preregistered_not_run",
        "artifact_sha256": {name: _sha256_text(content) for name, content in artifacts.items()},
        **raw["design_execution_assertions"],
    }
    artifacts[OUTPUT_FILENAMES[7]] = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    manifest = {
        "active_scope": ACTIVE_SCOPE,
        "contract_id": CONTRACT_ID,
        "operation": "design_only_contract_generation",
        "input_files": [contract.path.as_posix()],
        "output_files": OUTPUT_FILENAMES,
        "deterministic_generation": True,
        "wall_clock_timestamp_recorded": False,
        "market_data_paths_read": [],
        "strategy_grid_hash": raw["strategy_grid"]["strategy_grid_hash"],
        "result_status": "preregistered_not_run",
        **raw["design_execution_assertions"],
    }
    artifacts[OUTPUT_FILENAMES[8]] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return artifacts


def generate_artifacts(contract_path: str | Path, output_root: str | Path) -> list[Path]:
    contract = load_contract(contract_path)
    artifacts = build_artifacts(contract)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in OUTPUT_FILENAMES:
        path = root / name
        path.write_text(artifacts[name], encoding="utf-8", newline="")
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the design-only GMA-8A registries")
    parser.add_argument(
        "--config",
        default="configs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        default="reports/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_v1",
    )
    args = parser.parse_args()
    contract = load_contract(args.config)
    paths = generate_artifacts(args.config, args.output_root)
    print(f"contract_id={CONTRACT_ID}")
    print(f"active_scope={ACTIVE_SCOPE}")
    print(f"base_strategy_template_count={len(contract.strategy_templates)}")
    print(f"arm_trial_count={len(contract.strategy_templates) * 2}")
    print(f"strategy_grid_hash={contract.raw['strategy_grid']['strategy_grid_hash']}")
    print("market_data_read=false")
    print("backtest_performed=false")
    for path in paths:
        print(f"output={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
