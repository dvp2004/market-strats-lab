from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    FORBIDDEN_GMA4_SYMBOLS,
    GMA4_CANONICAL_RESEARCH_END_DATE,
    REQUIRED_COST_SCENARIOS,
    REQUIRED_EVALUATION_SCOPES,
    REQUIRED_SCOREBOARD_COLUMNS,
    REQUIRED_STRATEGY_FAMILIES,
    build_gma4_contract_summary,
    load_gma4_tournament_config,
    load_gma4_trial_registry,
    validate_gma4_contract,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma4_cross_asset_tournament_v1.yaml")
REGISTRY_PATH = Path("configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml")


@pytest.fixture()
def config():
    return load_gma4_tournament_config(CONFIG_PATH)


@pytest.fixture()
def registry():
    return load_gma4_trial_registry(REGISTRY_PATH)


def test_gma4_contract_loads_and_validates(config, registry):
    validate_gma4_contract(config, registry)
    summary = build_gma4_contract_summary(config, registry)
    assert summary.trial_count == 20
    assert summary.universe_count == 22


def test_universe_is_exact_required_22_etfs_in_order(config):
    assert config.universe == FIXED_GMA4_UNIVERSE
    assert config.universe[14] == "BIL"
    assert "CASH" not in config.universe


def test_forbidden_symbols_are_rejected(config, registry, tmp_path: Path):
    raw = deepcopy(config.raw)
    raw["universe"]["symbols"] = [*FIXED_GMA4_UNIVERSE[:-1], "SHY"]
    path = tmp_path / "bad_gma4_config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    bad_config = load_gma4_tournament_config(path)

    with pytest.raises(ValueError, match="universe.symbols"):
        validate_gma4_contract(bad_config, registry)

    for symbol in FORBIDDEN_GMA4_SYMBOLS:
        assert symbol not in config.universe


def test_registry_contains_exactly_20_unique_trial_ids(registry):
    trial_ids = [trial["trial_id"] for trial in registry.trials]
    assert len(trial_ids) == 20
    assert len(set(trial_ids)) == 20


def test_all_required_strategy_families_are_represented(registry):
    families = {trial["family"] for trial in registry.trials}
    assert REQUIRED_STRATEGY_FAMILIES <= families


def test_blend_components_reference_valid_non_blend_trials(registry):
    trial_by_id = {trial["trial_id"]: trial for trial in registry.trials}
    blends = [trial for trial in registry.trials if trial["family"] == "simple_blend"]
    assert len(blends) == 3
    for blend in blends:
        component_ids = blend["parameters"]["component_trial_ids"]
        assert component_ids
        for component_id in component_ids:
            assert component_id in trial_by_id
            assert trial_by_id[component_id]["family"] != "simple_blend"


def test_blends_require_independently_robust_components(registry):
    blends = [trial for trial in registry.trials if trial["family"] == "simple_blend"]
    for blend in blends:
        requirement = blend["parameters"]["component_robustness_requirement"]
        assert requirement == "component_robustness_required_before_candidate_consideration"
        assert blend["candidate_eligibility"]["reason"] == requirement


def test_required_cost_scopes_and_scoreboard_columns_exist(config):
    assert config.cost_scenarios == REQUIRED_COST_SCENARIOS
    assert config.evaluation_scopes == REQUIRED_EVALUATION_SCOPES
    assert set(REQUIRED_SCOREBOARD_COLUMNS) <= set(config.scoreboard_columns)
    assert not config.raw["scoreboard"]["ranking_by_highest_sharpe_alone_allowed"]


def test_all_regime_end_dates_are_on_or_before_research_end(config):
    for regime in config.regimes:
        assert regime["end_date"] <= GMA4_CANONICAL_RESEARCH_END_DATE.isoformat()


def test_geopolitical_stress_is_descriptive_only(config):
    regimes = {regime["regime_id"]: regime for regime in config.regimes}
    geopolitical = regimes["geopolitical_stress_descriptive"]
    assert geopolitical["eligible_for_candidate_selection"] is False
    assert geopolitical["descriptive_only"] is True


def test_no_historical_final_holdout_claim_is_permitted(config):
    evidence = config.raw["evidence"]
    assert evidence["evidence_class"] == "observed_development_evidence"
    assert evidence["historical_final_holdout_claim_allowed"] is False
    assert evidence["canonical_research_end_date"] == GMA4_CANONICAL_RESEARCH_END_DATE.isoformat()


def test_every_safety_flag_remains_disabled(config):
    track = config.raw["track"]
    assert track["paper_only"] is True
    for key in [
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
        "manual_tradingview_packet_generation_allowed",
        "active_gma_paper_workflow_influence_allowed",
        "prospective_shadow_generation_allowed",
    ]:
        assert track[key] is False


def test_no_registry_trial_is_candidate_or_live_eligible(registry):
    for trial in registry.trials:
        assert trial["status"] == "preregistered_not_run"
        eligibility = trial["candidate_eligibility"]
        assert eligibility["approved_for_paper"] is False
        assert eligibility["approved_for_live"] is False
        assert eligibility["approved_for_gma_allocation"] is False
        assert eligibility["approved_for_prospective_shadow"] is False
        assert eligibility["approved_for_broker_execution"] is False


def test_registry_trial_eligible_symbols_remain_within_fixed_universe(registry):
    allowed = set(FIXED_GMA4_UNIVERSE)
    for trial in registry.trials:
        assert set(trial["eligible_symbols"]) <= allowed
        assert not (set(trial["eligible_symbols"]) & FORBIDDEN_GMA4_SYMBOLS)


def test_contract_does_not_depend_on_market_intelligence_lab():
    source = Path("src/market_strats/global_multi_asset/gma4_contract.py").read_text(
        encoding="utf-8"
    )
    assert "market_intelligence_lab" not in source
