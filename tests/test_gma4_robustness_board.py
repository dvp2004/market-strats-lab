from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from market_strats.global_multi_asset.gma4_robustness_board import (
    BOARD_COLUMNS,
    GMA4RobustnessBoardError,
    build_gma4_robustness_outputs,
)


REGIMES = [
    "gfc_stress",
    "euro_us_debt_stress",
    "low_vol_calm_2017",
    "covid_crash",
    "covid_recovery",
    "inflation_rate_shock_2022",
    "geopolitical_stress_descriptive",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score_row(
    *,
    trial_id: str,
    strategy_id: str,
    family: str,
    cost_scenario: str,
    evaluation_scope: str,
    window_id: str,
    net_cagr: float,
    max_drawdown: float,
    turnover: float,
    cost_drag: float,
    hhi: float | None,
    regime_id: str = "",
    effective_start: str = "2020-01-01",
    coverage_status: str = "full_decision_eligible_coverage",
) -> dict[str, object]:
    return {
        "run_id": "gma4_test_run",
        "trial_id": trial_id,
        "strategy_id": strategy_id,
        "family": family,
        "cost_scenario": cost_scenario,
        "evaluation_scope": evaluation_scope,
        "window_id": window_id,
        "regime_id": regime_id,
        "start_date": "2020-01-01",
        "end_date": "2022-12-31",
        "trial_decision_eligible_start_date": "2020-01-01",
        "evaluation_effective_start_date": effective_start,
        "excluded_pre_decision_sessions": 0,
        "regime_coverage_status": coverage_status,
        "session_count": 252,
        "terminal_wealth": 100000.0 * (1.0 + net_cagr),
        "net_cagr": net_cagr,
        "annualised_volatility": 0.1,
        "sharpe_0rf": net_cagr / 0.1,
        "sortino_0rf": net_cagr / 0.08,
        "max_drawdown": max_drawdown,
        "calmar": 0.0,
        "time_underwater_days": 0,
        "trade_count": 1,
        "cumulative_turnover": turnover,
        "annualised_turnover": turnover,
        "cost_drag": cost_drag,
        "average_rebalance_turnover": 0.0,
        "max_single_asset_weight_observed": 0.4,
        "average_cash_weight": 0.1,
        "maximum_cash_weight": 0.2,
        "maximum_hhi_concentration": "" if hhi is None else hhi,
        "benchmark_relative_return": 0.0,
        "data_hash": "data",
        "config_hash": "config",
        "trial_hash": trial_id,
        "evidence_class": "observed_development_evidence",
        "status": "evaluated",
        "rejection_reason": "",
    }


def _trial_rows(
    *,
    trial_id: str,
    strategy_id: str,
    family: str,
    baseline: float,
    severe: float,
    drawdown: float,
    turnover: float,
    cost_drag: float,
    hhi: float | None = 0.25,
    rolling3: tuple[float, float] = (0.03, 0.05),
    rolling5: tuple[float, float] = (0.04, 0.06),
    sequential: tuple[float, float] = (0.02, 0.03),
    regimes: tuple[float, ...] = (0.01, 0.02, 0.03, -0.01, 0.04, -0.02, 0.03),
    partial_first_regime: bool = False,
) -> list[dict[str, object]]:
    rows = [
        _score_row(
            trial_id=trial_id,
            strategy_id=strategy_id,
            family=family,
            cost_scenario="baseline_1bps",
            evaluation_scope="full_common_history",
            window_id="full_common_history",
            net_cagr=baseline,
            max_drawdown=drawdown,
            turnover=turnover,
            cost_drag=cost_drag,
            hhi=hhi,
        ),
        _score_row(
            trial_id=trial_id,
            strategy_id=strategy_id,
            family=family,
            cost_scenario="severe_50bps",
            evaluation_scope="full_common_history",
            window_id="full_common_history",
            net_cagr=severe,
            max_drawdown=drawdown,
            turnover=turnover,
            cost_drag=cost_drag * 2,
            hhi=hhi,
        ),
    ]
    for idx, value in enumerate(rolling3):
        rows.append(
            _score_row(
                trial_id=trial_id,
                strategy_id=strategy_id,
                family=family,
                cost_scenario="baseline_1bps",
                evaluation_scope="rolling_3_year",
                window_id=f"r3_{idx}",
                net_cagr=value,
                max_drawdown=drawdown,
                turnover=turnover,
                cost_drag=cost_drag,
                hhi=hhi,
            )
        )
    for idx, value in enumerate(rolling5):
        rows.append(
            _score_row(
                trial_id=trial_id,
                strategy_id=strategy_id,
                family=family,
                cost_scenario="baseline_1bps",
                evaluation_scope="rolling_5_year",
                window_id=f"r5_{idx}",
                net_cagr=value,
                max_drawdown=drawdown,
                turnover=turnover,
                cost_drag=cost_drag,
                hhi=hhi,
            )
        )
    for idx, value in enumerate(sequential):
        rows.append(
            _score_row(
                trial_id=trial_id,
                strategy_id=strategy_id,
                family=family,
                cost_scenario="baseline_1bps",
                evaluation_scope="sequential_walk_forward",
                window_id=f"seq_{idx}",
                net_cagr=value,
                max_drawdown=drawdown,
                turnover=turnover,
                cost_drag=cost_drag,
                hhi=hhi,
            )
        )
    for idx, (regime, value) in enumerate(zip(REGIMES, regimes, strict=True)):
        rows.append(
            _score_row(
                trial_id=trial_id,
                strategy_id=strategy_id,
                family=family,
                cost_scenario="baseline_1bps",
                evaluation_scope="predefined_regime",
                window_id=regime,
                regime_id=regime,
                net_cagr=value,
                max_drawdown=drawdown,
                turnover=turnover,
                cost_drag=cost_drag,
                hhi=hhi,
                effective_start="2020-03-01" if partial_first_regime and idx == 0 else "2020-01-01",
                coverage_status="partial_pre_decision_coverage"
                if partial_first_regime and idx == 0
                else "full_decision_eligible_coverage",
            )
        )
    return rows


def _write_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "reports" / "runs" / "gma4_test_run"
    run_dir.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    rows.extend(
        _trial_rows(
            trial_id="gma4_abs_trend_10m_equal_weight_v1",
            strategy_id="absolute_trend",
            family="absolute_trend",
            baseline=0.07,
            severe=0.05,
            drawdown=-0.20,
            turnover=4.0,
            cost_drag=0.01,
            rolling3=(0.02, 0.03),
            partial_first_regime=True,
        )
    )
    rows.extend(
        _trial_rows(
            trial_id="gma4_abs_trend_12m_equal_weight_v1",
            strategy_id="absolute_trend",
            family="absolute_trend",
            baseline=0.08,
            severe=0.06,
            drawdown=-0.18,
            turnover=3.0,
            cost_drag=0.01,
            rolling3=(0.03, 0.04),
        )
    )
    rows.extend(
        _trial_rows(
            trial_id="gma4_meanrev_5d_bottom3_equal_weight_v1",
            strategy_id="short_horizon_mean_reversion",
            family="short_horizon_mean_reversion",
            baseline=0.09,
            severe=-0.02,
            drawdown=-0.35,
            turnover=80.0,
            cost_drag=0.15,
            hhi=None,
            rolling3=(-0.03, 0.08),
        )
    )
    pd.DataFrame(rows).to_csv(run_dir / "gma4_tournament_scoreboard.csv", index=False)
    pd.DataFrame(
        [
            {
                "trial_id": "gma4_abs_trend_10m_equal_weight_v1",
                "cost_scenario": "baseline_1bps",
            }
        ]
    ).to_csv(run_dir / "gma4_evaluation_detail.csv", index=False)
    (run_dir / "gma4_rejections.csv").write_text("\r\n", encoding="utf-8")
    (run_dir / "gma4_run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "gma4_test_run",
                "evidence_class": "observed_development_evidence",
                "holdout_status": "not_a_pristine_final_holdout",
                "common_history_start": "2020-01-01",
                "common_history_end": "2022-12-31",
            }
        ),
        encoding="utf-8",
    )
    discussion = run_dir.parent.parent / "gma4_results_discussion_latest_v1.md"
    discussion.write_text(
        "# GMA-4 Historical Results Discussion\n\n"
        "## Research Scope\n\nExisting scope text.\n\n"
        "## Baseline Full-History Table\n\nExisting baseline table.\n\n"
        "## Update Protocol\n\nExisting update protocol.\n",
        encoding="utf-8",
    )
    return run_dir


def test_valid_inputs_generate_every_required_output(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    result = build_gma4_robustness_outputs(run_dir)

    assert list(result.board.columns) == BOARD_COLUMNS
    assert len(result.board) == 3
    for path in [
        run_dir / "gma4_robustness_board_v1.csv",
        run_dir / "gma4_robustness_board_v1.md",
        run_dir / "gma4_historical_research_shortlist_v1.csv",
        run_dir.parent.parent / "gma4_latest_robustness_board_v1.csv",
        run_dir.parent.parent / "gma4_latest_robustness_board_v1.md",
        run_dir.parent.parent / "gma4_latest_historical_research_shortlist_v1.csv",
    ]:
        assert path.exists()


def test_missing_or_malformed_inputs_fail_closed(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    (run_dir / "gma4_run_manifest.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(GMA4RobustnessBoardError, match="malformed JSON"):
        build_gma4_robustness_outputs(run_dir)


def test_metrics_aggregate_across_cost_windows_sequential_and_regimes(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    board = build_gma4_robustness_outputs(run_dir).board.set_index("trial_id")
    row = board.loc["gma4_abs_trend_10m_equal_weight_v1"]

    assert row["baseline_full_history_net_cagr"] == pytest.approx(0.07)
    assert row["severe_cost_full_history_net_cagr"] == pytest.approx(0.05)
    assert row["cost_sensitivity_cagr_change"] == pytest.approx(-0.02)
    assert row["worst_rolling_3_year_net_cagr"] == pytest.approx(0.02)
    assert row["median_rolling_5_year_net_cagr"] == pytest.approx(0.05)
    assert row["positive_sequential_walk_forward_fraction"] == pytest.approx(1.0)
    assert row["worst_predefined_regime_net_cagr"] == pytest.approx(-0.02)


def test_partial_regime_rows_are_counted_from_effective_rows(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    board = build_gma4_robustness_outputs(run_dir).board.set_index("trial_id")

    assert (
        "partial_regime_rows=1" in board.loc["gma4_abs_trend_10m_equal_weight_v1", "research_notes"]
    )


def test_pareto_dominance_is_deterministic(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    board = build_gma4_robustness_outputs(run_dir).board.set_index("trial_id")

    assert bool(board.loc["gma4_abs_trend_10m_equal_weight_v1", "pareto_dominated"]) is True
    assert (
        board.loc["gma4_abs_trend_10m_equal_weight_v1", "historical_research_status"]
        == "historically_dominated"
    )
    assert (
        board.loc["gma4_abs_trend_12m_equal_weight_v1", "historical_research_status"]
        == "historical_non_dominated"
    )


def test_missing_hhi_is_marked_missing_instead_of_fabricated(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    board = build_gma4_robustness_outputs(run_dir).board.set_index("trial_id")
    row = board.loc["gma4_meanrev_5d_bottom3_equal_weight_v1"]

    assert row["concentration_measurement_status"] == "concentration_measurement_missing"
    assert row["historical_research_status"] == "insufficient_measurement"
    assert (
        pd.isna(row["baseline_full_history_maximum_hhi_concentration"])
        or row["baseline_full_history_maximum_hhi_concentration"] == ""
    )


def test_parameter_neighbour_labels_are_deterministic_and_descriptive(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    board = build_gma4_robustness_outputs(run_dir).board.set_index("trial_id")

    assert (
        board.loc["gma4_abs_trend_10m_equal_weight_v1", "parameter_neighbour_support"]
        == "broadly_consistent"
    )
    assert (
        board.loc["gma4_meanrev_5d_bottom3_equal_weight_v1", "parameter_neighbour_support"]
        == "isolated_variant"
    )


def test_generated_text_contains_no_forbidden_decision_language(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    build_gma4_robustness_outputs(run_dir)
    text = (run_dir / "gma4_robustness_board_v1.md").read_text(encoding="utf-8").lower()

    for forbidden in [
        "winner",
        "live-ready",
        "recommended for execution",
        "paper order",
        "broker",
        "prospective-shadow",
        "candidate",
    ]:
        assert forbidden not in text
    assert "no execution or promotion decision is produced" in text


def test_module_does_not_import_or_invoke_gma4_tournament():
    source = Path("src/market_strats/global_multi_asset/gma4_robustness_board.py").read_text(
        encoding="utf-8"
    )

    assert "import gma4_tournament" not in source
    assert "from market_strats.global_multi_asset.gma4_tournament" not in source


def test_source_tournament_files_remain_unchanged(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    input_paths = [
        run_dir / "gma4_tournament_scoreboard.csv",
        run_dir / "gma4_evaluation_detail.csv",
        run_dir / "gma4_rejections.csv",
        run_dir / "gma4_run_manifest.json",
    ]
    before = {path: _sha256(path) for path in input_paths}

    build_gma4_robustness_outputs(run_dir)

    assert {path: _sha256(path) for path in input_paths} == before


def test_repeated_invocation_gives_identical_run_specific_content(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    build_gma4_robustness_outputs(run_dir)
    first = {
        path.name: path.read_bytes()
        for path in [
            run_dir / "gma4_robustness_board_v1.csv",
            run_dir / "gma4_robustness_board_v1.md",
            run_dir / "gma4_historical_research_shortlist_v1.csv",
        ]
    }

    build_gma4_robustness_outputs(run_dir)

    second = {name: (run_dir / name).read_bytes() for name in first}
    assert second == first


def test_discussion_file_preserves_existing_content_outside_marker_section(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    discussion = run_dir.parent.parent / "gma4_results_discussion_latest_v1.md"
    original = discussion.read_text(encoding="utf-8")

    build_gma4_robustness_outputs(run_dir)
    updated = discussion.read_text(encoding="utf-8")

    assert "Existing scope text." in updated
    assert "Existing baseline table." in updated
    assert "Existing update protocol." in updated
    assert "<!-- GMA4F_ROBUSTNESS_START -->" in updated
    assert "<!-- GMA4F_ROBUSTNESS_END -->" in updated
    assert original.split("## Update Protocol")[1].strip() in updated


def test_no_paper_broker_live_prospective_candidate_or_promotion_paths_change(tmp_path: Path):
    run_dir = _write_run_dir(tmp_path)
    result = build_gma4_robustness_outputs(run_dir)
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in [result.output_paths["run_board_md"], result.output_paths["latest_board_md"]]
    )

    for forbidden in [
        "paper order",
        "broker integration",
        "live path",
        "prospective-shadow",
        "candidate record",
        "promotion logic",
    ]:
        assert forbidden not in combined
