"""GMA-6C cross-universe tournament design lock.

This module validates the local GMA-6A/GMA-6B design inputs and writes a
pre-registration package for a later frozen GMA-6D execution. It does not run
or import strategy, replay, allocation, data-provider, or model code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    REQUIRED_COST_SCENARIOS,
    load_gma4_tournament_config,
    load_gma4_trial_registry,
    validate_gma4_contract,
)

DEFAULT_CONFIG_PATH = Path(
    "configs/global_multi_asset_alpha/gma6c_cross_universe_tournament_v1.yaml"
)
PHASE_ID = "gma6c_cross_universe_tournament_v1"
CONTROL_UNIVERSE_VERSION = "gma6_core_22_control_v1"
EXPANDED_UNIVERSE_VERSION = "gma6_expanded_29_v1"
FROZEN_ADDITIONS = ["VNQ", "TIP", "USO", "DBA", "SLV", "EWG", "EWJ"]
EXPANDED_UNIVERSE = [*FIXED_GMA4_UNIVERSE, *FROZEN_ADDITIONS]
REQUIRED_B1_OVERLAY_STATUS = "both_documented_for_later_research_execution"
REQUIRED_EFFECTIVE_OVERLAY_STATUS = "eligible_only_with_documented_methodology_regime_flags"
REQUIRED_USO_FLAG = "uso_roll_methodology_pre_may_2020_vs_from_may_2020"
REQUIRED_DBA_FLAG = "not_required"
EXECUTION_STATUS = "design_only_not_executed"
COMPARABILITY_STATUS = "matched_sample_required_later_common_valid_dates"
HISTORY_START = "2007-05-30"
HISTORY_END = "2026-05-01"
EVALUATION_VIEWS = [
    "full_history",
    "rolling_3y",
    "rolling_5y",
    "sequential_walk_forward",
    "predefined_regimes",
]
TERMINAL_STOP_RULE = [
    "After GMA-6C passes, the next and only permitted GMA-6 task is one frozen GMA-6D cross-universe tournament execution.",
    "No GMA-6C.1, new strategy family, parameter sweep, additional asset, or universe alteration is permitted before that execution and results review.",
]
REQUIRED_WORDING = [
    "This is observed development evidence and not a pristine final holdout.",
    "No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.",
    "GMA-4 and GMA-5 V1 remain unchanged.",
    "GMA-6C is a frozen design contract only and contains no performance results.",
]

PREREGISTRATION_COLUMNS = [
    "source_gma4_trial_id",
    "arm_trial_id",
    "universe_version",
    "universe_size",
    "trial_family",
    "benchmark_or_strategy",
    "strategy_id",
    "portfolio_construction_label",
    "parameter_definition",
    "rebalance_frequency",
    "required_history_rule",
    "cost_scenarios",
    "trial_definition_hash",
    "comparison_period_start",
    "comparison_period_end",
    "sample_comparability_status",
    "methodology_regime_flag",
    "execution_status",
]


class GMA6CContractError(ValueError):
    """Raised when a GMA-6C design-lock prerequisite fails closed."""


@dataclass(frozen=True)
class GMA6CResult:
    preregistration_rows: list[dict[str, str]]
    lock: dict[str, Any]
    preregistration_csv: Path
    preregistration_md: Path
    lock_json: Path


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6CContractError(f"{path} must be a YAML mapping")
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA6CContractError(f"{path} must be a JSON object")
    return raw


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise GMA6CContractError(f"{path} must contain at least one row")
    return rows


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _structured_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GMA6CContractError(message)


def _path_from_config(config: dict[str, Any], section: str, key: str) -> Path:
    value = (config.get(section) or {}).get(key)
    if not value:
        raise GMA6CContractError(f"config missing {section}.{key}")
    return Path(str(value))


def _validate_universe_arms(config: dict[str, Any], gma6a: dict[str, Any]) -> None:
    arms = config.get("universe_arms") or []
    _require(len(arms) == 2, "GMA-6C must define exactly two universe arms")
    by_version = {str(arm.get("universe_version")): arm for arm in arms}
    _require(CONTROL_UNIVERSE_VERSION in by_version, "missing core 22 control arm")
    _require(EXPANDED_UNIVERSE_VERSION in by_version, "missing expanded 29 arm")
    _require(
        list(by_version[CONTROL_UNIVERSE_VERSION].get("symbols") or []) == FIXED_GMA4_UNIVERSE,
        "control universe must equal the frozen 22 ETF universe",
    )
    _require(
        list(by_version[EXPANDED_UNIVERSE_VERSION].get("symbols") or []) == EXPANDED_UNIVERSE,
        "expanded universe must equal the frozen 29 ETF universe",
    )
    _require(
        len(by_version[EXPANDED_UNIVERSE_VERSION].get("symbols") or []) != 27,
        "27-instrument fallback arm is prohibited",
    )
    _require(
        list(gma6a.get("frozen_core_v1_universe") or []) == FIXED_GMA4_UNIVERSE,
        "GMA-6A core universe does not match GMA-4 fixed 22 universe",
    )
    _require(
        list(gma6a.get("fixed_additions") or []) == FROZEN_ADDITIONS,
        "GMA-6A fixed additions do not match the GMA-6C frozen additions",
    )


def _validate_b1_overlay(rows: list[dict[str, str]]) -> str:
    by_ticker = {row.get("ticker", ""): row for row in rows}
    _require(set(by_ticker) == {"USO", "DBA"}, "B.1 overlay must contain exactly USO and DBA")
    for ticker, row in by_ticker.items():
        _require(
            row.get("structure_review_status") == "documented_for_later_research_execution",
            f"{ticker} B.1 structure review is not documented",
        )
        _require(
            row.get("later_research_execution_eligibility")
            == "eligible_for_later_research_execution",
            f"{ticker} B.1 later research eligibility is not eligible",
        )
        _require(
            row.get("spot_proxy_claim_permitted") == "false",
            f"{ticker} spot proxy claim must be false",
        )
        _require(
            row.get("traded_etp_total_return_interpretation") == "true",
            f"{ticker} traded ETP interpretation must be true",
        )
    return REQUIRED_B1_OVERLAY_STATUS


def _validate_b2_overlay(rows: list[dict[str, str]]) -> dict[str, str]:
    by_ticker = {row.get("ticker", ""): row for row in rows}
    _require(set(by_ticker) == {"USO", "DBA"}, "B.2 overlay must contain exactly USO and DBA")
    uso = by_ticker["USO"]
    dba = by_ticker["DBA"]
    _require(
        uso.get("later_research_execution_overlay_eligibility")
        == REQUIRED_EFFECTIVE_OVERLAY_STATUS,
        "USO must be eligible only with documented methodology regime flags",
    )
    _require(
        uso.get("required_later_regime_flag") == REQUIRED_USO_FLAG,
        "USO methodology regime flag is missing or altered",
    )
    _require(
        uso.get("material_methodology_change_detected") == "true",
        "USO material methodology change must be detected",
    )
    _require(
        dba.get("later_research_execution_overlay_eligibility")
        == "eligible_for_later_gma6_research_execution",
        "DBA B.2 overlay eligibility must remain eligible",
    )
    _require(
        dba.get("required_later_regime_flag") == REQUIRED_DBA_FLAG, "DBA flag must be not_required"
    )
    _require(
        dba.get("material_methodology_change_detected") == "false",
        "DBA material methodology change must remain false",
    )
    return {"USO": REQUIRED_USO_FLAG, "DBA": REQUIRED_DBA_FLAG}


def _validate_data_bundle_verdict(verdict: dict[str, Any]) -> None:
    blocked = sorted(str(item) for item in verdict.get("blocked_or_pending_tickers") or [])
    _require(
        blocked == ["DBA", "USO"],
        "raw GMA-6B verdict must be blocked only for DBA and USO before overlays",
    )
    _require(
        verdict.get("universe_verdict") == "blocked_data_contract_failure",
        "raw GMA-6B verdict must remain a pre-overlay blocked data contract failure",
    )


def _trial_definition(trial: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial_id": trial["trial_id"],
        "strategy_id": trial["strategy_id"],
        "family": trial["family"],
        "version": trial["version"],
        "description": trial["description"],
        "rebalance_cadence": trial["rebalance_cadence"],
        "signal_inputs": trial["signal_inputs"],
        "parameters": trial["parameters"],
        "weighting_method": trial["weighting_method"],
        "eligible_symbols": trial["eligible_symbols"],
        "cost_scenarios": trial["cost_scenarios"],
    }


def _parameter_definition(trial: dict[str, Any], universe_size: int) -> str:
    parameters = dict(trial.get("parameters") or {})
    parameters.pop("component_robustness_requirement", None)
    if str(trial.get("trial_id")) == "gma4_benchmark_equal_weight_22_monthly_v1":
        parameters = {"asset_count": universe_size}
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _portfolio_construction_label(trial: dict[str, Any]) -> str:
    if str(trial.get("trial_id")) == "gma4_benchmark_equal_weight_22_monthly_v1":
        return "equal_weight_current_universe_monthly"
    return str(trial.get("weighting_method"))


def _benchmark_or_strategy(trial: dict[str, Any]) -> str:
    return "benchmark" if str(trial.get("family")) == "benchmark" else "strategy"


def _build_preregistration_rows(registry_trials: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    arms = [
        (CONTROL_UNIVERSE_VERSION, FIXED_GMA4_UNIVERSE, REQUIRED_DBA_FLAG),
        (EXPANDED_UNIVERSE_VERSION, EXPANDED_UNIVERSE, REQUIRED_USO_FLAG),
    ]
    for trial in registry_trials:
        source_trial_id = str(trial["trial_id"])
        definition = _trial_definition(trial)
        trial_hash = _structured_sha256(definition)
        for universe_version, universe, methodology_flag in arms:
            universe_size = len(universe)
            rows.append(
                {
                    "source_gma4_trial_id": source_trial_id,
                    "arm_trial_id": f"{universe_version}__{source_trial_id}",
                    "universe_version": universe_version,
                    "universe_size": str(universe_size),
                    "trial_family": str(trial["family"]),
                    "benchmark_or_strategy": _benchmark_or_strategy(trial),
                    "strategy_id": str(trial["strategy_id"]),
                    "portfolio_construction_label": _portfolio_construction_label(trial),
                    "parameter_definition": _parameter_definition(trial, universe_size),
                    "rebalance_frequency": str(trial["rebalance_cadence"]),
                    "required_history_rule": "matched_core_expanded_common_valid_decision_execution_dates",
                    "cost_scenarios": ";".join(str(item) for item in REQUIRED_COST_SCENARIOS),
                    "trial_definition_hash": trial_hash,
                    "comparison_period_start": HISTORY_START,
                    "comparison_period_end": HISTORY_END,
                    "sample_comparability_status": COMPARABILITY_STATUS,
                    "methodology_regime_flag": methodology_flag,
                    "execution_status": EXECUTION_STATUS,
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREREGISTRATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _write_markdown(path: Path, rows: list[dict[str, str]], lock: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_arm = {
        CONTROL_UNIVERSE_VERSION: FIXED_GMA4_UNIVERSE,
        EXPANDED_UNIVERSE_VERSION: EXPANDED_UNIVERSE,
    }
    inventory_rows = [
        [
            row["source_gma4_trial_id"],
            row["universe_version"],
            row["arm_trial_id"],
            row["portfolio_construction_label"],
            row["methodology_regime_flag"],
        ]
        for row in rows
    ]
    content = [
        "# GMA-6C Cross-Universe Tournament Pre-Registration v1",
        "",
        *REQUIRED_WORDING,
        "",
        "## Universe Arms",
        "",
        f"- {CONTROL_UNIVERSE_VERSION}: {', '.join(by_arm[CONTROL_UNIVERSE_VERSION])}",
        f"- {EXPANDED_UNIVERSE_VERSION}: {', '.join(by_arm[EXPANDED_UNIVERSE_VERSION])}",
        "",
        "There is no 27-instrument fallback arm. USO and DBA remain in the expanded arm.",
        "",
        "## Matched-Sample Rule",
        "",
        "Later execution must compare each same-template core-versus-expanded pair on identical valid decision and execution dates.",
        f"If either arm lacks required history on a date, both arms begin at the later common valid date. sample_comparability_status is `{COMPARABILITY_STATUS}`.",
        "Highest historical CAGR or Sharpe alone is not a selection rule.",
        "",
        "## Methodology-Regime Metadata",
        "",
        f"Expanded-universe rows carry `{REQUIRED_USO_FLAG}`. USO later diagnostics require descriptive pre-flag and from-flag slices, with no causation proof interpretation and no return-series alteration after outcomes are reviewed.",
        f"DBA carries `{REQUIRED_DBA_FLAG}`.",
        "",
        "## Trial Inventory",
        "",
        _markdown_table(
            [
                "source_gma4_trial_id",
                "universe_version",
                "arm_trial_id",
                "construction",
                "methodology_regime_flag",
            ],
            inventory_rows,
        ),
        "",
        "## Design Lock Hashes",
        "",
        _markdown_table(
            ["field", "sha256"],
            [[key, str(lock[key])] for key in sorted(lock) if key.endswith("_hash")],
        ),
        "",
        "## Terminal Stop Rule",
        "",
        *[f"- {line}" for line in TERMINAL_STOP_RULE],
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def _build_lock(
    *,
    config: dict[str, Any],
    gma6a: dict[str, Any],
    gma6a_path: Path,
    data_manifest_path: Path,
    b1_overlay_path: Path,
    b2_overlay_path: Path,
    trial_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    parent_commit = str((gma6a.get("contract") or {}).get("parent_gma4_commit") or "")
    _require(parent_commit, "GMA-6A parent_gma4_commit is missing")
    methodology_rules = config.get("methodology_regime_rules") or {}
    return {
        "phase_id": PHASE_ID,
        "parent_gma4_commit": parent_commit,
        "gma6a_universe_contract_hash": _file_sha256(gma6a_path),
        "gma6b_data_bundle_manifest_hash": _file_sha256(data_manifest_path),
        "gma6b_commodity_pool_overlay_hash": _file_sha256(b1_overlay_path),
        "gma6b2_continuity_overlay_hash": _file_sha256(b2_overlay_path),
        "control_universe_hash": _structured_sha256(FIXED_GMA4_UNIVERSE),
        "expanded_universe_hash": _structured_sha256(EXPANDED_UNIVERSE),
        "trial_inventory_hash": _structured_sha256(trial_inventory),
        "cost_scenario_hash": _structured_sha256(REQUIRED_COST_SCENARIOS),
        "methodology_regime_rules_hash": _structured_sha256(methodology_rules),
        "execution_status": EXECUTION_STATUS,
        "effective_gma6b_universe_status_after_overlay": REQUIRED_EFFECTIVE_OVERLAY_STATUS,
        "terminal_stop_rule": TERMINAL_STOP_RULE,
    }


def run_gma6c_tournament_contract(config_path: str | Path = DEFAULT_CONFIG_PATH) -> GMA6CResult:
    config_path = Path(config_path)
    config = _load_yaml(config_path)
    contract = config.get("contract") or {}
    _require(contract.get("phase_id") == PHASE_ID, "config phase_id is not GMA-6C")
    _require(contract.get("design_only") is True, "GMA-6C config must be design-only")
    _require(
        contract.get("execution_status") == EXECUTION_STATUS,
        "GMA-6C execution status must be design-only",
    )
    _require(
        contract.get("required_gma6b_universe_status_after_overlay")
        == REQUIRED_EFFECTIVE_OVERLAY_STATUS,
        "GMA-6C must require the corrected effective GMA-6B overlay status",
    )

    gma6a_path = _path_from_config(config, "source_inputs", "gma6a_universe_contract")
    data_manifest_path = _path_from_config(config, "source_inputs", "gma6b_data_bundle_manifest")
    data_verdict_path = _path_from_config(config, "source_inputs", "gma6b_data_bundle_verdict")
    b1_overlay_path = _path_from_config(config, "source_inputs", "gma6b_commodity_pool_overlay")
    b2_overlay_path = _path_from_config(config, "source_inputs", "gma6b2_continuity_overlay")
    gma4_config_path = _path_from_config(config, "source_inputs", "gma4_tournament_config")
    gma4_registry_path = _path_from_config(config, "source_inputs", "gma4_trial_registry")
    preregistration_csv = _path_from_config(config, "outputs", "preregistration_csv")
    preregistration_md = _path_from_config(config, "outputs", "preregistration_md")
    lock_json = _path_from_config(config, "outputs", "lock_json")

    gma6a = _load_yaml(gma6a_path)
    _load_yaml(_path_from_config(config, "source_inputs", "gma6b_data_bundle_config"))
    _load_yaml(_path_from_config(config, "source_inputs", "gma6b_commodity_pool_config"))
    _load_yaml(_path_from_config(config, "source_inputs", "gma6b2_continuity_config"))
    _load_json(data_manifest_path)
    _validate_data_bundle_verdict(_load_json(data_verdict_path))
    _validate_universe_arms(config, gma6a)

    b1_status = _validate_b1_overlay(_load_csv_rows(b1_overlay_path))
    _require(
        contract.get("required_gma6b_commodity_pool_overlay_status") == b1_status,
        "GMA-6C B.1 overlay requirement does not match derived overlay status",
    )
    methodology_flags = _validate_b2_overlay(_load_csv_rows(b2_overlay_path))
    _require(methodology_flags["USO"] == REQUIRED_USO_FLAG, "USO methodology flag not preserved")
    _require(methodology_flags["DBA"] == REQUIRED_DBA_FLAG, "DBA methodology flag not preserved")

    gma4_config = load_gma4_tournament_config(gma4_config_path)
    registry = load_gma4_trial_registry(gma4_registry_path)
    validate_gma4_contract(gma4_config, registry)
    _require(len(registry.trials) == 20, "GMA-6C must preserve exactly 20 GMA-4 trials")

    trial_inventory = [_trial_definition(trial) for trial in registry.trials]
    rows = _build_preregistration_rows(registry.trials)
    _require(len(rows) == 40, "GMA-6C must write 20 trials for each of two arms")
    lock = _build_lock(
        config=config,
        gma6a=gma6a,
        gma6a_path=gma6a_path,
        data_manifest_path=data_manifest_path,
        b1_overlay_path=b1_overlay_path,
        b2_overlay_path=b2_overlay_path,
        trial_inventory=trial_inventory,
    )

    _write_csv(preregistration_csv, rows)
    _write_markdown(preregistration_md, rows, lock)
    _write_json(lock_json, lock)
    return GMA6CResult(
        preregistration_rows=rows,
        lock=lock,
        preregistration_csv=preregistration_csv,
        preregistration_md=preregistration_md,
        lock_json=lock_json,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the GMA-6C design-only tournament contract outputs."
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="Path to the GMA-6C config YAML."
    )
    args = parser.parse_args(argv)
    result = run_gma6c_tournament_contract(args.config)
    print(f"phase_id: {PHASE_ID}")
    print(f"execution_status: {result.lock['execution_status']}")
    print(f"preregistration_rows: {len(result.preregistration_rows)}")
    print(f"trial_inventory_hash: {result.lock['trial_inventory_hash']}")
    print(f"preregistration_csv: {result.preregistration_csv}")
    print(f"preregistration_md: {result.preregistration_md}")
    print(f"lock_json: {result.lock_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
