from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from market_strats.global_multi_asset.gma4_contract import (
    FIXED_GMA4_UNIVERSE,
    GMA4_CANONICAL_RESEARCH_END_DATE,
    REQUIRED_SCOREBOARD_COLUMNS,
    load_gma4_trial_registry,
)
from market_strats.global_multi_asset.gma4_strategy_library import build_gma4_trial_rules
from market_strats.global_multi_asset.gma4_tournament import (
    LATEST_RESULTS_CSV,
    LATEST_RESULTS_MD,
    RUN_HISTORY_FILENAME,
    run_gma4_tournament,
    trial_eligible_start_dates,
)

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma4_cross_asset_tournament_v1.yaml")
REGISTRY_PATH = Path("configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml")


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


@pytest.fixture(scope="module")
def completed_tournament(tmp_path_factory: pytest.TempPathFactory):
    dates = _dates()
    return run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=_prices(),
        cash=_cash(dates),
        output_root=tmp_path_factory.mktemp("gma4_runs") / "runs",
    )


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


def test_blocked_tournament_appends_history_without_false_scoreboard_data(tmp_path: Path):
    dates = _dates()
    prices = _prices()
    prices.pop("DBC")
    output_root = tmp_path / "reports" / "runs"

    result = run_gma4_tournament(
        config_path=CONFIG_PATH,
        prices=prices,
        cash=_cash(dates),
        output_root=output_root,
        run_id_override="gma4_blocked_history_test",
    )
    history = pd.read_csv(output_root.parent / RUN_HISTORY_FILENAME)
    latest = pd.read_csv(output_root.parent / LATEST_RESULTS_CSV)
    latest_md = (output_root.parent / LATEST_RESULTS_MD).read_text(encoding="utf-8")

    assert result.status == "blocked_data_coverage"
    assert len(history) == 1
    assert history.iloc[0]["run_id"] == "gma4_blocked_history_test"
    assert history.iloc[0]["tournament_status"] == "blocked_data_coverage"
    assert bool(history.iloc[0]["scoreboard_created"]) is False
    assert set(latest["tournament_status"]) == {"blocked_data_coverage"}
    assert "DBC" in latest_md
    assert "net_cagr" not in latest.columns


def test_repeat_blocked_run_id_does_not_duplicate_history_rows(tmp_path: Path):
    dates = _dates()
    prices = _prices()
    prices.pop("DBC")
    output_root = tmp_path / "reports" / "runs"
    kwargs = {
        "config_path": CONFIG_PATH,
        "prices": prices,
        "cash": _cash(dates),
        "output_root": output_root,
        "run_id_override": "gma4_repeat_history_test",
    }

    run_gma4_tournament(**kwargs)
    run_gma4_tournament(**kwargs)

    history = pd.read_csv(output_root.parent / RUN_HISTORY_FILENAME)
    assert history["run_id"].tolist() == ["gma4_repeat_history_test"]


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


def test_trial_decision_eligible_starts_match_declared_lookbacks():
    dates = _dates()
    registry = load_gma4_trial_registry(REGISTRY_PATH)
    starts = trial_eligible_start_dates(dates, registry)
    rules = build_gma4_trial_rules()

    assert starts["gma4_benchmark_spy_buy_hold_v1"] == dates[0]
    assert starts["gma4_meanrev_5d_bottom3_equal_weight_v1"] == dates[5]
    assert starts["gma4_abs_trend_12m_equal_weight_v1"] == dates[252]
    assert (
        starts["gma4_blend_equal_abs12_xsmom12_v1"]
        == dates[rules["gma4_blend_equal_abs12_xsmom12_v1"].required_lookback_sessions]
    )


def test_tournament_writes_required_artifacts_for_valid_synthetic_data(completed_tournament):
    result = completed_tournament

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


def test_successful_tournament_writes_history_and_latest_result_tables(completed_tournament):
    result = completed_tournament
    comparison_root = result.run_dir.parent.parent

    history = pd.read_csv(comparison_root / RUN_HISTORY_FILENAME)
    latest = pd.read_csv(comparison_root / LATEST_RESULTS_CSV)
    latest_md = (comparison_root / LATEST_RESULTS_MD).read_text(encoding="utf-8").lower()

    assert result.run_id in set(history["run_id"])
    row = history.loc[history["run_id"] == result.run_id].iloc[0]
    assert row["tournament_status"] == "completed"
    assert bool(row["scoreboard_created"]) is True
    assert int(row["scoreboard_row_count"]) > 0
    assert len(latest) == 20
    assert set(latest["status"]) == {"evaluated"}
    assert latest["net_cagr"].astype(float).is_monotonic_decreasing
    for forbidden in ["winner", "candidate", "execution", "promotion", "live-trading"]:
        assert forbidden not in latest_md


def test_no_decisions_are_evaluated_before_trial_lookback_is_available(completed_tournament):
    dates = _dates()
    scoreboard = pd.read_csv(completed_tournament.run_dir / "gma4_tournament_scoreboard.csv")
    full = scoreboard.loc[
        (scoreboard["evaluation_scope"] == "full_common_history")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
    ].set_index("trial_id")

    assert full.loc["gma4_benchmark_spy_buy_hold_v1", "evaluation_effective_start_date"] == str(
        dates[0]
    )
    assert full.loc[
        "gma4_meanrev_5d_bottom3_equal_weight_v1", "evaluation_effective_start_date"
    ] == str(dates[5])
    assert full.loc["gma4_abs_trend_12m_equal_weight_v1", "evaluation_effective_start_date"] == str(
        dates[252]
    )
    assert int(
        full.loc["gma4_abs_trend_12m_equal_weight_v1", "excluded_pre_decision_sessions"]
    ) > int(full.loc["gma4_meanrev_5d_bottom3_equal_weight_v1", "excluded_pre_decision_sessions"])


def test_partial_pre_decision_regime_coverage_is_labelled(completed_tournament):
    scoreboard = pd.read_csv(completed_tournament.run_dir / "gma4_tournament_scoreboard.csv")
    rows = scoreboard.loc[
        (scoreboard["regime_id"] == "geopolitical_stress_descriptive")
        & (scoreboard["trial_id"] == "gma4_abs_trend_12m_equal_weight_v1")
        & (scoreboard["cost_scenario"] == "baseline_1bps")
    ]

    assert not rows.empty
    assert set(rows["regime_coverage_status"]) == {"partial_pre_decision_coverage"}
    assert (rows["excluded_pre_decision_sessions"].astype(int) > 0).all()


def test_generated_reports_avoid_operational_or_promotion_approval_language(completed_tournament):
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in completed_tournament.run_dir.iterdir()
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


def test_tournament_outputs_are_under_supplied_report_root(completed_tournament):
    assert completed_tournament.run_dir.exists()
