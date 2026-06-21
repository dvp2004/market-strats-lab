from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    GMA4_CANONICAL_RESEARCH_END_DATE,
    REQUIRED_SCOREBOARD_COLUMNS,
)
from market_strats.global_multi_asset.gma4_tournament import run_gma4_tournament

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma4_cross_asset_tournament_v1.yaml")


def _dates() -> list[Any]:
    return pd.bdate_range(end=GMA4_CANONICAL_RESEARCH_END_DATE, periods=620).date.tolist()


def _cash(dates: list[Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"accrual_start": dates[idx - 1], "accrual_end": dates[idx], "period_return": 0.0}
            for idx in range(1, len(dates))
        ]
    )


def _price_frame(dates: list[Any], drift: float, base: float) -> pd.DataFrame:
    values = [base]
    for _idx in range(1, len(dates)):
        values.append(values[-1] * (1.0 + drift))
    return pd.DataFrame({"close_raw": values, "total_return_index": values}, index=dates)


def _prices() -> dict[str, pd.DataFrame]:
    dates = _dates()
    prices: dict[str, pd.DataFrame] = {}
    for idx, symbol in enumerate(FIXED_GMA4_UNIVERSE):
        drift = 0.0001 + idx * 0.00001
        if symbol in {"SPY", "QQQ", "XLK", "XLY"}:
            drift = 0.0007 + idx * 0.00001
        if symbol == "BIL":
            drift = 0.00005
        prices[symbol] = _price_frame(dates, drift, 100.0 + idx)
    return prices


def test_tournament_blocks_when_fixed_universe_coverage_is_missing(tmp_path: Path):
    dates = _dates()
    prices = _prices()
    prices.pop("DBC")

    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=prices,
        cash=_cash(dates),
        output_root=tmp_path / "runs",
    )

    assert result.status == "blocked_data_coverage"
    assert result.blockers
    assert (result.run_dir / "gma4_data_coverage.csv").exists()
    assert (result.run_dir / "gma4_data_coverage.md").exists()
    assert not (result.run_dir / "gma4_tournament_scoreboard.csv").exists()


def test_tournament_blocks_when_common_endpoint_is_missing(tmp_path: Path):
    dates = _dates()
    prices = _prices()
    prices["SPY"] = prices["SPY"].iloc[:-1].copy()

    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=prices,
        cash=_cash(dates),
        output_root=tmp_path / "runs",
    )

    assert result.status == "blocked_data_coverage"
    assert any("canonical_endpoint_missing" in blocker for blocker in result.blockers)
    assert not (result.run_dir / "gma4_tournament_scoreboard.csv").exists()


def test_tournament_writes_required_artifacts_for_valid_synthetic_data(tmp_path: Path):
    dates = _dates()

    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=_prices(),
        cash=_cash(dates),
        output_root=tmp_path / "runs",
    )

    assert result.status == "completed"
    expected_files = {
        "gma4_data_coverage.csv",
        "gma4_data_coverage.md",
        "gma4_trial_registry_snapshot.csv",
        "gma4_tournament_scoreboard.csv",
        "gma4_tournament_scoreboard.md",
        "gma4_evaluation_detail.csv",
        "gma4_rejections.csv",
        "gma4_run_manifest.json",
    }
    assert expected_files <= {path.name for path in result.run_dir.iterdir() if path.is_file()}

    scoreboard = pd.read_csv(result.run_dir / "gma4_tournament_scoreboard.csv")
    assert list(scoreboard.columns) == REQUIRED_SCOREBOARD_COLUMNS
    assert set(scoreboard["evidence_class"]) == {"observed_development_evidence"}
    assert set(scoreboard["cost_scenario"]) == {
        "baseline_1bps",
        "stressed_10bps",
        "stressed_25bps",
        "severe_50bps",
    }
    assert scoreboard["trial_id"].nunique() == 20
    assert "geopolitical_stress_descriptive" in set(scoreboard["regime_id"])
    assert not result.compact_scoreboard.empty


def test_generated_reports_avoid_operational_or_promotion_approval_language(tmp_path: Path):
    dates = _dates()
    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=_prices(),
        cash=_cash(dates),
        output_root=tmp_path / "runs",
    )

    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in result.run_dir.iterdir()
        if path.suffix in {".md", ".json"}
    )
    for forbidden in [
        "paper order",
        "broker action",
        "live-trading action",
        "candidate-approved",
        "pristine-final-holdout",
    ]:
        assert forbidden not in combined
    assert "not_a_pristine_final_holdout" in combined
    assert "candidate_selection" in combined
    assert "not_performed" in combined


def test_tournament_outputs_are_under_supplied_report_root(tmp_path: Path):
    dates = _dates()
    root = tmp_path / "custom_runs"
    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=_prices(),
        cash=_cash(dates),
        output_root=root,
    )

    assert result.run_dir.parent == root
    assert result.run_dir.exists()
