"""GMA-4A cross-asset historical tournament contract and registry validation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

GMA4_PHASE_ID = "gma4_cross_asset_historical_strategy_tournament_v1"
GMA4_EVIDENCE_CLASS = "observed_development_evidence"
GMA4_CANONICAL_RESEARCH_END_DATE = date(2026, 5, 1)

FIXED_GMA4_UNIVERSE = [
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

FORBIDDEN_GMA4_SYMBOLS = {
    "SHY",
    "VNQ",
    "UUP",
    "BTC-USD",
    "ETH-USD",
}

REQUIRED_SAFETY_FLAGS = {
    "paper_only": True,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "manual_tradingview_packet_generation_allowed": False,
    "active_gma_paper_workflow_influence_allowed": False,
    "prospective_shadow_generation_allowed": False,
}

REQUIRED_COST_SCENARIOS = [
    "baseline_1bps",
    "stressed_10bps",
    "stressed_25bps",
    "severe_50bps",
]

REQUIRED_EVALUATION_SCOPES = [
    "full_common_history",
    "rolling_3_year",
    "rolling_5_year",
    "sequential_walk_forward",
    "predefined_regime",
]

REQUIRED_REGIME_IDS = {
    "gfc_stress",
    "euro_us_debt_stress",
    "low_vol_calm_2017",
    "covid_crash",
    "covid_recovery",
    "inflation_rate_shock_2022",
    "geopolitical_stress_descriptive",
}

REQUIRED_STRATEGY_FAMILIES = {
    "absolute_trend",
    "cross_sectional_momentum",
    "short_horizon_mean_reversion",
    "defensive_risk_regime_allocation",
    "simple_blend",
}

REQUIRED_TRIAL_FIELDS = {
    "trial_id",
    "strategy_id",
    "family",
    "version",
    "description",
    "rebalance_cadence",
    "signal_inputs",
    "parameters",
    "weighting_method",
    "eligible_symbols",
    "cost_scenarios",
    "status",
    "candidate_eligibility",
}

REQUIRED_CANDIDATE_FALSE_FLAGS = {
    "approved_for_paper",
    "approved_for_live",
    "approved_for_gma_allocation",
    "approved_for_prospective_shadow",
    "approved_for_broker_execution",
}

REQUIRED_SCOREBOARD_COLUMNS = [
    "run_id",
    "trial_id",
    "strategy_id",
    "family",
    "cost_scenario",
    "evaluation_scope",
    "window_id",
    "regime_id",
    "start_date",
    "end_date",
    "session_count",
    "terminal_wealth",
    "net_cagr",
    "annualised_volatility",
    "sharpe_0rf",
    "sortino_0rf",
    "max_drawdown",
    "calmar",
    "time_underwater_days",
    "trade_count",
    "cumulative_turnover",
    "annualised_turnover",
    "cost_drag",
    "average_rebalance_turnover",
    "max_single_asset_weight_observed",
    "average_cash_weight",
    "maximum_cash_weight",
    "maximum_hhi_concentration",
    "benchmark_relative_return",
    "data_hash",
    "config_hash",
    "trial_hash",
    "evidence_class",
    "status",
    "rejection_reason",
]


@dataclass(frozen=True)
class GMA4TournamentConfig:
    path: Path
    raw: dict[str, Any]
    universe: list[str]
    cost_scenarios: list[str]
    evaluation_scopes: list[str]
    regimes: list[dict[str, Any]]
    scoreboard_columns: list[str]


@dataclass(frozen=True)
class GMA4TrialRegistry:
    path: Path
    raw: dict[str, Any]
    trials: list[dict[str, Any]]


@dataclass(frozen=True)
class GMA4ContractSummary:
    phase_id: str
    evidence_class: str
    universe_count: int
    trial_count: int
    trial_count_by_family: dict[str, int]
    cost_scenarios: list[str]
    evaluation_scopes: list[str]
    scoreboard_column_count: int


def _parse_iso_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field_name} must be an ISO date string")


def _load_yaml_mapping(path: str | Path, label: str) -> dict[str, Any]:
    yaml_path = Path(path)
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    return raw


def _require_exact_list(name: str, actual: list[str], expected: list[str]) -> None:
    if actual != expected:
        raise ValueError(f"{name} must equal {expected!r}")


def _validate_safety_flags(track: dict[str, Any]) -> None:
    for key, expected in REQUIRED_SAFETY_FLAGS.items():
        if track.get(key) is not expected:
            raise ValueError(f"track.{key} must be {str(expected).lower()}")


def _validate_universe_symbols(symbols: list[str], context: str) -> None:
    outside = sorted(set(symbols) - set(FIXED_GMA4_UNIVERSE))
    forbidden = sorted(set(symbols) & FORBIDDEN_GMA4_SYMBOLS)
    if outside:
        raise ValueError(f"{context} contains symbols outside fixed GMA-4 universe: {outside}")
    if forbidden:
        raise ValueError(f"{context} contains forbidden symbols: {forbidden}")


def load_gma4_tournament_config(path: str | Path) -> GMA4TournamentConfig:
    config_path = Path(path)
    raw = _load_yaml_mapping(config_path, "GMA-4 tournament config")
    universe = list((raw.get("universe") or {}).get("symbols") or [])
    evaluation = raw.get("evaluation_contract") or {}
    scoreboard = raw.get("scoreboard") or {}
    return GMA4TournamentConfig(
        path=config_path,
        raw=raw,
        universe=[str(symbol) for symbol in universe],
        cost_scenarios=[str(item) for item in evaluation.get("cost_scenarios", [])],
        evaluation_scopes=[str(item) for item in evaluation.get("evaluation_scopes", [])],
        regimes=list(evaluation.get("regimes", [])),
        scoreboard_columns=[str(item) for item in scoreboard.get("columns", [])],
    )


def load_gma4_trial_registry(path: str | Path) -> GMA4TrialRegistry:
    registry_path = Path(path)
    raw = _load_yaml_mapping(registry_path, "GMA-4 trial registry")
    trials = raw.get("trials") or []
    if not isinstance(trials, list):
        raise ValueError("GMA-4 trial registry trials must be a list")
    return GMA4TrialRegistry(path=registry_path, raw=raw, trials=trials)


def validate_gma4_contract(
    config: GMA4TournamentConfig,
    registry: GMA4TrialRegistry,
) -> None:
    track = config.raw.get("track") or {}
    evidence = config.raw.get("evidence") or {}
    universe_raw = config.raw.get("universe") or {}
    scoreboard = config.raw.get("scoreboard") or {}

    if track.get("phase_id") != GMA4_PHASE_ID:
        raise ValueError(f"track.phase_id must be {GMA4_PHASE_ID}")
    _validate_safety_flags(track)

    if evidence.get("evidence_class") != GMA4_EVIDENCE_CLASS:
        raise ValueError(f"evidence.evidence_class must be {GMA4_EVIDENCE_CLASS}")
    if evidence.get("historical_final_holdout_claim_allowed") is not False:
        raise ValueError("historical final holdout claims are prohibited for GMA-4")
    end_date = _parse_iso_date(
        evidence.get("canonical_research_end_date"),
        "evidence.canonical_research_end_date",
    )
    if end_date != GMA4_CANONICAL_RESEARCH_END_DATE:
        raise ValueError("canonical_research_end_date must remain 2026-05-01")

    _require_exact_list("universe.symbols", config.universe, FIXED_GMA4_UNIVERSE)
    if universe_raw.get("internal_cash_is_universe_asset") is not False:
        raise ValueError("CASH must not be an additional GMA-4 universe asset")
    if universe_raw.get("bil_role") != "tradeable_defensive_cash_proxy":
        raise ValueError("BIL must be the tradeable defensive cash-proxy ETF")
    _validate_universe_symbols(config.universe, "universe.symbols")
    forbidden_declared = set(universe_raw.get("forbidden_symbols") or [])
    if not FORBIDDEN_GMA4_SYMBOLS <= forbidden_declared:
        raise ValueError("forbidden_symbols must include all prohibited GMA-4 symbols")

    _require_exact_list(
        "evaluation_contract.cost_scenarios",
        config.cost_scenarios,
        REQUIRED_COST_SCENARIOS,
    )
    _require_exact_list(
        "evaluation_contract.evaluation_scopes",
        config.evaluation_scopes,
        REQUIRED_EVALUATION_SCOPES,
    )
    regime_ids = {str(regime.get("regime_id")) for regime in config.regimes}
    if regime_ids != REQUIRED_REGIME_IDS:
        raise ValueError("GMA-4 regime identifiers do not match the required contract")
    for regime in config.regimes:
        regime_id = str(regime.get("regime_id"))
        regime_end = _parse_iso_date(regime.get("end_date"), f"{regime_id}.end_date")
        if regime_end > GMA4_CANONICAL_RESEARCH_END_DATE:
            raise ValueError(f"{regime_id} ends after canonical research end date")
        if regime_id == "geopolitical_stress_descriptive":
            if regime.get("eligible_for_candidate_selection") is not False:
                raise ValueError("geopolitical_stress_descriptive must be descriptive-only")
            if regime.get("descriptive_only") is not True:
                raise ValueError("geopolitical_stress_descriptive must be marked descriptive_only")

    if scoreboard.get("ranking_by_highest_sharpe_alone_allowed") is not False:
        raise ValueError("ranking by highest Sharpe alone is prohibited")
    missing_scoreboard = sorted(set(REQUIRED_SCOREBOARD_COLUMNS) - set(config.scoreboard_columns))
    if missing_scoreboard:
        raise ValueError(f"scoreboard columns missing: {missing_scoreboard}")

    if registry.raw.get("phase_id") != GMA4_PHASE_ID:
        raise ValueError("trial registry phase_id must match GMA-4 phase")
    if len(registry.trials) != 20:
        raise ValueError("GMA-4 trial registry must contain exactly 20 trials")
    trial_ids = [str(trial.get("trial_id")) for trial in registry.trials]
    if len(set(trial_ids)) != len(trial_ids):
        raise ValueError("GMA-4 trial IDs must be unique")

    trial_by_id = {trial_id: trial for trial_id, trial in zip(trial_ids, registry.trials)}
    families = {str(trial.get("family")) for trial in registry.trials}
    if not REQUIRED_STRATEGY_FAMILIES <= families:
        raise ValueError("GMA-4 registry is missing required strategy families")

    for trial in registry.trials:
        missing_fields = sorted(REQUIRED_TRIAL_FIELDS - set(trial))
        if missing_fields:
            raise ValueError(f"{trial.get('trial_id')} missing fields: {missing_fields}")
        trial_id = str(trial["trial_id"])
        if trial["status"] != "preregistered_not_run":
            raise ValueError(f"{trial_id} must start as preregistered_not_run")
        _validate_universe_symbols(
            [str(symbol) for symbol in trial["eligible_symbols"]],
            f"{trial_id}.eligible_symbols",
        )
        _require_exact_list(
            f"{trial_id}.cost_scenarios",
            [str(item) for item in trial["cost_scenarios"]],
            REQUIRED_COST_SCENARIOS,
        )

        eligibility = trial["candidate_eligibility"] or {}
        for key in REQUIRED_CANDIDATE_FALSE_FLAGS:
            if eligibility.get(key) is not False:
                raise ValueError(f"{trial_id}.candidate_eligibility.{key} must be false")

        if trial["family"] == "simple_blend":
            parameters = trial["parameters"] or {}
            if (
                parameters.get("component_robustness_requirement")
                != "component_robustness_required_before_candidate_consideration"
            ):
                raise ValueError(f"{trial_id} must require robust components")
            component_ids = [str(item) for item in parameters.get("component_trial_ids", [])]
            if not component_ids:
                raise ValueError(f"{trial_id} must reference component trial IDs")
            for component_id in component_ids:
                if component_id not in trial_by_id:
                    raise ValueError(f"{trial_id} references unknown component {component_id}")
                if trial_by_id[component_id].get("family") == "simple_blend":
                    raise ValueError(f"{trial_id} cannot blend another blend")


def build_gma4_contract_summary(
    config: GMA4TournamentConfig,
    registry: GMA4TrialRegistry,
) -> GMA4ContractSummary:
    validate_gma4_contract(config, registry)
    family_counts = Counter(str(trial["family"]) for trial in registry.trials)
    return GMA4ContractSummary(
        phase_id=GMA4_PHASE_ID,
        evidence_class=GMA4_EVIDENCE_CLASS,
        universe_count=len(config.universe),
        trial_count=len(registry.trials),
        trial_count_by_family=dict(sorted(family_counts.items())),
        cost_scenarios=config.cost_scenarios,
        evaluation_scopes=config.evaluation_scopes,
        scoreboard_column_count=len(config.scoreboard_columns),
    )
