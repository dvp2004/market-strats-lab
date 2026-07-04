from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from market_strats.global_multi_asset.gma4_contract import load_gma4_trial_registry
from market_strats.global_multi_asset.gma6c_tournament_contract import (
    COMPARABILITY_STATUS,
    CONTROL_UNIVERSE_VERSION,
    EXPANDED_UNIVERSE,
    EXPANDED_UNIVERSE_VERSION,
    FIXED_GMA4_UNIVERSE,
    FROZEN_ADDITIONS,
    REQUIRED_USO_FLAG,
    GMA6CContractError,
    run_gma6c_tournament_contract,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6c_cross_universe_tournament_v1.yaml")
REGISTRY_PATH = Path("configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml")
MODULE_PATH = Path("src/market_strats/global_multi_asset/gma6c_tournament_contract.py")


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, config: dict) -> Path:
    path = tmp_path / "gma6c.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def _config_with_temp_outputs(tmp_path: Path) -> dict:
    config = deepcopy(_load_config())
    output_root = tmp_path / "reports"
    config["outputs"] = {
        "preregistration_csv": str(
            output_root / "gma6c_cross_universe_tournament_preregistration_v1.csv"
        ),
        "preregistration_md": str(
            output_root / "gma6c_cross_universe_tournament_preregistration_v1.md"
        ),
        "lock_json": str(output_root / "gma6c_cross_universe_tournament_lock_v1.json"),
    }
    return config


def _run_temp(tmp_path: Path):
    return run_gma6c_tournament_contract(
        _write_config(tmp_path, _config_with_temp_outputs(tmp_path))
    )


def _arms(config: dict) -> dict[str, list[str]]:
    return {arm["universe_version"]: arm["symbols"] for arm in config["universe_arms"]}


def test_exactly_two_universe_arms_exist():
    arms = _arms(_load_config())
    assert list(arms) == [CONTROL_UNIVERSE_VERSION, EXPANDED_UNIVERSE_VERSION]
    assert len(arms) == 2


def test_control_contains_exactly_22_tickers():
    arms = _arms(_load_config())
    assert arms[CONTROL_UNIVERSE_VERSION] == FIXED_GMA4_UNIVERSE
    assert len(arms[CONTROL_UNIVERSE_VERSION]) == 22


def test_expanded_contains_exactly_29_tickers():
    arms = _arms(_load_config())
    assert arms[EXPANDED_UNIVERSE_VERSION] == EXPANDED_UNIVERSE
    assert len(arms[EXPANDED_UNIVERSE_VERSION]) == 29


def test_expanded_contains_control_plus_exactly_seven_additions():
    arms = _arms(_load_config())
    assert arms[EXPANDED_UNIVERSE_VERSION][:22] == arms[CONTROL_UNIVERSE_VERSION]
    assert arms[EXPANDED_UNIVERSE_VERSION][22:] == FROZEN_ADDITIONS


def test_no_27_instrument_fallback_arm_exists():
    config = _load_config()
    assert all(len(arm["symbols"]) != 27 for arm in config["universe_arms"])


def test_trial_inventory_matches_gma4_twenty_trials_in_order(tmp_path: Path):
    result = _run_temp(tmp_path)
    registry = load_gma4_trial_registry(REGISTRY_PATH)
    expected = [trial["trial_id"] for trial in registry.trials]
    control_rows = [
        row
        for row in result.preregistration_rows
        if row["universe_version"] == CONTROL_UNIVERSE_VERSION
    ]
    expanded_rows = [
        row
        for row in result.preregistration_rows
        if row["universe_version"] == EXPANDED_UNIVERSE_VERSION
    ]
    assert [row["source_gma4_trial_id"] for row in control_rows] == expected
    assert [row["source_gma4_trial_id"] for row in expanded_rows] == expected
    assert len(expected) == 20


def test_no_new_trial_ids_or_parameters_appear(tmp_path: Path):
    result = _run_temp(tmp_path)
    registry = load_gma4_trial_registry(REGISTRY_PATH)
    source_ids = {trial["trial_id"] for trial in registry.trials}
    for row in result.preregistration_rows:
        assert row["source_gma4_trial_id"] in source_ids
        assert row["arm_trial_id"].endswith(f"__{row['source_gma4_trial_id']}")
        assert row["sample_comparability_status"] == COMPARABILITY_STATUS
    equal_weight = [
        row
        for row in result.preregistration_rows
        if row["source_gma4_trial_id"] == "gma4_benchmark_equal_weight_22_monthly_v1"
    ]
    assert {row["portfolio_construction_label"] for row in equal_weight} == {
        "equal_weight_current_universe_monthly"
    }
    assert {row["universe_size"] for row in equal_weight} == {"22", "29"}


def test_uso_regime_flag_is_mandatory_for_expanded_outputs(tmp_path: Path):
    result = _run_temp(tmp_path)
    expanded_rows = [
        row
        for row in result.preregistration_rows
        if row["universe_version"] == EXPANDED_UNIVERSE_VERSION
    ]
    assert expanded_rows
    assert {row["methodology_regime_flag"] for row in expanded_rows} == {REQUIRED_USO_FLAG}


def test_gma6b_overlay_verdict_fails_closed_when_altered(tmp_path: Path):
    config = _config_with_temp_outputs(tmp_path)
    source = Path(config["source_inputs"]["gma6b_commodity_pool_overlay"])
    altered = tmp_path / "bad_b1.csv"
    text = source.read_text(encoding="utf-8").replace(
        "documented_for_later_research_execution", "structure_review_pending", 1
    )
    altered.write_text(text, encoding="utf-8")
    config["source_inputs"]["gma6b_commodity_pool_overlay"] = str(altered)
    with pytest.raises(GMA6CContractError, match="B.1"):
        run_gma6c_tournament_contract(_write_config(tmp_path, config))


def test_gma6b2_continuity_verdict_fails_closed_when_altered(tmp_path: Path):
    config = _config_with_temp_outputs(tmp_path)
    source = Path(config["source_inputs"]["gma6b2_continuity_overlay"])
    altered = tmp_path / "bad_b2.csv"
    text = source.read_text(encoding="utf-8").replace(REQUIRED_USO_FLAG, "not_required", 1)
    altered.write_text(text, encoding="utf-8")
    config["source_inputs"]["gma6b2_continuity_overlay"] = str(altered)
    with pytest.raises(GMA6CContractError, match="USO methodology"):
        run_gma6c_tournament_contract(_write_config(tmp_path, config))


def test_module_does_not_import_or_invoke_data_provider_replay_strategy_allocation_or_model_modules():
    source = MODULE_PATH.read_text(encoding="utf-8")
    import_lines = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    blocked_terms = [
        "data.price_provider",
        "gma4_tournament",
        "gma4_replay_adapter",
        "gma4_strategy_library",
        "allocation",
        "portfolio",
        "sklearn",
        "model",
        "target",
    ]
    assert not any(term in line for term in blocked_terms for line in import_lines)


def test_repeated_output_generation_is_deterministic(tmp_path: Path):
    config = _config_with_temp_outputs(tmp_path)
    config_path = _write_config(tmp_path, config)
    first = run_gma6c_tournament_contract(config_path)
    first_csv = first.preregistration_csv.read_text(encoding="utf-8")
    first_md = first.preregistration_md.read_text(encoding="utf-8")
    first_lock = first.lock_json.read_text(encoding="utf-8")
    second = run_gma6c_tournament_contract(config_path)
    assert second.preregistration_csv.read_text(encoding="utf-8") == first_csv
    assert second.preregistration_md.read_text(encoding="utf-8") == first_md
    assert second.lock_json.read_text(encoding="utf-8") == first_lock


def test_prohibited_decision_language_is_absent_from_generated_outputs(tmp_path: Path):
    result = _run_temp(tmp_path)
    text = (
        result.preregistration_md.read_text(encoding="utf-8")
        + "\n"
        + result.preregistration_csv.read_text(encoding="utf-8")
    ).lower()
    allowed_required_sentence = "no strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced."
    text_without_required_sentence = text.replace(allowed_required_sentence, "")
    for term in [
        "candidate",
        "winner",
        "approved",
        "recommended",
        "deployable",
        "live-ready",
        "promotion",
    ]:
        assert term not in text_without_required_sentence
