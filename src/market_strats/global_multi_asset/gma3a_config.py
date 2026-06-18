"""GMA-3A transparent strategy tournament configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GMA3A_TRACK_ID = "gma_alpha"
GMA3A_PHASE_ID = "gma3a_transparent_strategy_tournament"

TOP_LEVEL_KEYS = {
    "track",
    "data_purpose",
    "accepted_inputs",
    "paths",
    "capital",
    "calendar",
    "costs",
    "limits",
    "selection_gates",
    "strategy_universe",
    "live_paper_ensemble",
    "manual_tradingview",
}

TRACK_KEYS = {
    "track_id",
    "phase_id",
    "paper_only",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "browser_automation_allowed",
    "ml_portfolio_influence_allowed",
}

ACCEPTED_KEYS = {
    "gma1a_commit",
    "gma1a_tag",
    "gma1a_accepted_selection_hash",
    "gma1b_commit",
    "gma1b_tag",
    "gma1b_accepted_canonical_macro_hash",
    "gma2_commit",
    "gma2_tag",
    "gma2_accepted_replay_hash",
    "canonical_research_end_date",
}


@dataclass(frozen=True)
class GMA3AConfig:
    path: Path
    raw: dict[str, Any]
    track: dict[str, Any]
    data_purpose: str
    accepted_inputs: dict[str, str]
    paths: dict[str, Path]


def _unknown_keys(section: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown keys in {name}: {unknown}")


def _must_be_false(section: dict[str, Any], key: str) -> None:
    if bool(section.get(key, True)):
        raise ValueError(f"{key} must be false for GMA-3A")


def validate_gma3a_config(raw: dict[str, Any], *, path: Path | None = None) -> GMA3AConfig:
    _unknown_keys(raw, TOP_LEVEL_KEYS, "config")
    missing = sorted(TOP_LEVEL_KEYS - set(raw))
    if missing:
        raise ValueError(f"Missing top-level config sections: {missing}")

    data_purpose = raw.get("data_purpose", "")

    track = raw["track"] or {}
    accepted = raw["accepted_inputs"] or {}
    _unknown_keys(track, TRACK_KEYS, "track")
    _unknown_keys(accepted, ACCEPTED_KEYS, "accepted_inputs")

    if track.get("track_id") != GMA3A_TRACK_ID:
        raise ValueError("track.track_id must be gma_alpha")
    if track.get("phase_id") != GMA3A_PHASE_ID:
        raise ValueError("track.phase_id must be gma3a_transparent_strategy_tournament")
    if not bool(track.get("paper_only", False)):
        raise ValueError("track.paper_only must be true")
    for key in [
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
        "browser_automation_allowed",
        "ml_portfolio_influence_allowed",
    ]:
        _must_be_false(track, key)

    for key in ACCEPTED_KEYS:
        if not str(accepted.get(key, "")):
            raise ValueError(f"accepted_inputs.{key} must be populated")
    if accepted["canonical_research_end_date"] != "2026-05-01":
        raise ValueError("canonical_research_end_date must remain 2026-05-01")
    if raw["calendar"].get("same_close_execution_allowed") is not False:
        raise ValueError("same-close execution is not allowed")
    if raw["manual_tradingview"].get("broker_submission_allowed") is not False:
        raise ValueError("TradingView broker submission must be false")
    if raw["manual_tradingview"].get("real_money_allowed") is not False:
        raise ValueError("TradingView real money must be false")

    paths = {key: Path(value) for key, value in (raw["paths"] or {}).items()}
    return GMA3AConfig(
        path=path or Path(""),
        raw=raw,
        track=track,
        data_purpose=str(data_purpose),
        accepted_inputs={key: str(value) for key, value in accepted.items()},
        paths=paths,
    )


def load_gma3a_config(path: str | Path) -> GMA3AConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("GMA-3A config must be a mapping")
    return validate_gma3a_config(raw, path=config_path)
