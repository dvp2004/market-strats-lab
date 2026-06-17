"""GMA-2 point-in-time replay foundation configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GMA2_TRACK_ID = "gma_alpha"
GMA2_PHASE_ID = "gma2_replay_foundation"

TOP_LEVEL_KEYS = {
    "track",
    "accepted_inputs",
    "research_start_date",
    "research_end_date",
    "smoke_replay_start_date",
    "smoke_replay_end_date",
    "signal_calendar",
    "execution_policy",
    "valuation_policy",
    "cash_accrual_policy",
    "transaction_cost_policy",
    "missing_data_policy",
    "stale_price_policy",
    "rebalance_policy",
    "benchmark",
    "initial_capital",
    "minimum_trade_notional",
    "portfolio_tolerance",
    "portfolio_weight_tolerance",
    "paths",
    "smoke_policies",
}

TRACK_KEYS = {
    "track_id",
    "phase_id",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "simulated_monetary_results_only",
}

ACCEPTED_INPUT_KEYS = {
    "gma1a_commit",
    "gma1a_tag",
    "gma1a_accepted_selection_hash",
    "gma1b_commit",
    "gma1b_tag",
    "gma1b_accepted_live_hash",
    "gma1b_accepted_canonical_macro_hash",
    "canonical_research_end_date",
}

PATH_KEYS = {
    "canonical_market_root",
    "canonical_macro_root",
    "data_foundation_report_root",
    "macro_foundation_report_root",
    "replay_data_root",
    "replay_report_root",
}


@dataclass(frozen=True)
class GMA2Config:
    path: Path
    raw: dict[str, Any]
    track: dict[str, Any]
    accepted_inputs: dict[str, str]
    paths: dict[str, Path]
    smoke_policies: dict[str, Any]


def _unknown_keys(section: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {unknown}")


def _must_be_false(section: dict[str, Any], key: str) -> None:
    if bool(section.get(key, True)):
        raise ValueError(f"{key} must be false for GMA-2")


def validate_gma2_config(raw: dict[str, Any], *, path: Path | None = None) -> GMA2Config:
    _unknown_keys(raw, TOP_LEVEL_KEYS, "config")
    missing = sorted(TOP_LEVEL_KEYS - set(raw))
    if missing:
        raise ValueError(f"Missing top-level config sections: {missing}")

    track = raw["track"] or {}
    accepted_inputs = raw["accepted_inputs"] or {}
    paths_raw = raw["paths"] or {}
    smoke_policies = raw["smoke_policies"] or {}

    _unknown_keys(track, TRACK_KEYS, "track")
    _unknown_keys(accepted_inputs, ACCEPTED_INPUT_KEYS, "accepted_inputs")
    _unknown_keys(paths_raw, PATH_KEYS, "paths")

    if track.get("track_id") != GMA2_TRACK_ID:
        raise ValueError(f"track.track_id must be {GMA2_TRACK_ID!r}")
    if track.get("phase_id") != GMA2_PHASE_ID:
        raise ValueError(f"track.phase_id must be {GMA2_PHASE_ID!r}")
    if not bool(track.get("paper_only", False)):
        raise ValueError("track.paper_only must be true")
    if not bool(track.get("simulated_monetary_results_only", False)):
        raise ValueError("track.simulated_monetary_results_only must be true")
    _must_be_false(track, "live_trading_allowed")
    _must_be_false(track, "real_money_allowed")
    _must_be_false(track, "broker_api_integration_allowed")

    for key in ACCEPTED_INPUT_KEYS:
        if key != "gma1b_accepted_live_hash" and not str(accepted_inputs.get(key, "")):
            raise ValueError(f"accepted_inputs.{key} must be populated")
    if accepted_inputs.get("canonical_research_end_date") != "2026-05-01":
        raise ValueError("canonical_research_end_date must remain 2026-05-01")

    if raw["execution_policy"].get("same_close_execution_allowed") is not False:
        raise ValueError("same-close execution must be disabled")
    if raw["cash_accrual_policy"].get("authoritative_series") != "DGS3MO":
        raise ValueError("cash accrual must use DGS3MO")
    if raw["cash_accrual_policy"].get("future_yield_observations_allowed") is not False:
        raise ValueError("future cash yield observations must be prohibited")

    if not smoke_policies:
        raise ValueError("At least one smoke policy is required")
    for name, policy in smoke_policies.items():
        if policy.get("label") != "engine_validation_only":
            raise ValueError(f"{name} must be labelled engine_validation_only")
        if not bool(policy.get("not_strategy_candidate", False)):
            raise ValueError(f"{name} must not be labelled a strategy candidate")
        if not bool(policy.get("not_paper_trading_recommendation", False)):
            raise ValueError(f"{name} must not be a paper-trading recommendation")

    paths = {key: Path(value) for key, value in paths_raw.items()}
    return GMA2Config(
        path=path or Path(""),
        raw=raw,
        track=track,
        accepted_inputs={key: str(value) for key, value in accepted_inputs.items()},
        paths=paths,
        smoke_policies=smoke_policies,
    )


def load_gma2_config(path: str | Path) -> GMA2Config:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA-2 config must be a mapping")
    return validate_gma2_config(raw, path=config_path)
