import csv
import hashlib
import json
from pathlib import Path

import pytest

from market_strats.global_multi_asset.gma_master_report import (
    GMA4_RUN_ID,
    GMA5_CLEAN_RUN_ID,
    GMA5_RUN_ID,
    MasterReportError,
    generate_master_report,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gma4_scoreboard_row(
    trial_id: str,
    strategy_id: str,
    family: str,
    net_cagr: str,
    max_drawdown: str,
) -> dict[str, str]:
    return {
        "run_id": GMA4_RUN_ID,
        "trial_id": trial_id,
        "strategy_id": strategy_id,
        "family": family,
        "cost_scenario": "baseline_1bps",
        "evaluation_scope": "full_common_history",
        "window_id": "full_common_history",
        "regime_id": "",
        "start_date": "2007-05-30",
        "end_date": "2026-05-01",
        "trial_decision_eligible_start_date": "2007-05-30",
        "evaluation_effective_start_date": "2007-05-30",
        "excluded_pre_decision_sessions": "0",
        "regime_coverage_status": "full_decision_eligible_coverage",
        "session_count": "4762",
        "terminal_wealth": "200000",
        "net_cagr": net_cagr,
        "annualised_volatility": "0.1",
        "sharpe_0rf": "0.7",
        "sortino_0rf": "0.9",
        "max_drawdown": max_drawdown,
        "calmar": "0.5",
        "time_underwater_days": "100",
        "trade_count": "10",
        "cumulative_turnover": "10",
        "annualised_turnover": "2.0",
        "cost_drag": "0.01",
        "average_rebalance_turnover": "0.1",
        "max_single_asset_weight_observed": "0.4",
        "average_cash_weight": "0.02",
        "maximum_cash_weight": "0.1",
        "maximum_hhi_concentration": "0.33",
        "benchmark_relative_return": "0.2",
        "data_hash": "data",
        "config_hash": "config",
        "trial_hash": "trial",
        "evidence_class": "observed_development_evidence",
        "status": "evaluated",
        "rejection_reason": "",
    }


def _gma4_robustness_row(
    trial_id: str,
    strategy_id: str,
    family: str,
    severe_cagr: str,
) -> dict[str, str]:
    return {
        "run_id": GMA4_RUN_ID,
        "trial_id": trial_id,
        "strategy_id": strategy_id,
        "family": family,
        "effective_evaluation_start_date": "2008-05-29",
        "effective_evaluation_end_date": "2026-05-01",
        "evaluated_session_count": "4510",
        "comparable_sample_group": "2008-05-29|2026-05-01|4510",
        "pareto_comparison_status": "identical_effective_sample_only",
        "baseline_full_history_net_cagr": "0.08",
        "baseline_full_history_sharpe": "0.7",
        "baseline_full_history_max_drawdown": "-0.2",
        "baseline_full_history_annualised_turnover": "2.0",
        "baseline_full_history_cost_drag": "0.01",
        "severe_cost_full_history_net_cagr": severe_cagr,
        "cost_sensitivity_cagr_change": "-0.02",
        "worst_rolling_3_year_net_cagr": "0.01",
        "median_rolling_3_year_net_cagr": "0.08",
        "positive_rolling_3_year_fraction": "1.0",
        "worst_rolling_5_year_net_cagr": "0.03",
        "median_rolling_5_year_net_cagr": "0.09",
        "positive_rolling_5_year_fraction": "1.0",
        "positive_sequential_walk_forward_fraction": "0.8",
        "worst_long_regime_net_cagr": "0.02",
        "worst_short_regime_cumulative_net_return": "-0.1",
        "positive_long_regime_fraction": "1.0",
        "positive_short_regime_fraction": "0.5",
        "parameter_neighbour_support": "broadly_consistent",
        "concentration_measurement_status": "concentration_measurement_available",
        "hhi_source_file": "gma4_tournament_scoreboard.csv",
        "hhi_source_column": "maximum_hhi_concentration",
        "maximum_hhi_concentration": "0.33",
        "pareto_dominated": "False",
        "historical_research_status": "historical_non_dominated",
        "research_notes": "fixture",
        "gfc_regime_coverage_status": "partial_coverage",
        "gfc_regime_session_count": "100",
        "gfc_regime_metric_type": "cumulative_return_and_drawdown",
        "gfc_regime_cumulative_net_return": "-0.1",
        "gfc_regime_max_drawdown": "-0.2",
        "gfc_regime_net_cagr": "",
        "covid_crash_regime_coverage_status": "full_coverage",
    }


def _gma5_scoreboard_row(
    entity_id: str,
    entity_type: str,
    cost_scenario: str,
    evaluation_scope: str,
    net_cagr: str,
    max_drawdown: str,
    status: str = "evaluated",
    regime_id: str = "",
) -> dict[str, str]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "cost_scenario": cost_scenario,
        "evaluation_scope": evaluation_scope,
        "window_id": evaluation_scope if not regime_id else regime_id,
        "regime_id": regime_id,
        "start_date": "2012-05-31",
        "end_date": "2026-05-01" if not regime_id else "2009-03-09",
        "session_count": "3500" if not regime_id else "0",
        "metric_type": "annualised_cagr_and_drawdown" if not regime_id else "unavailable",
        "cumulative_net_return": "1.0" if not regime_id else "",
        "net_cagr": net_cagr,
        "max_drawdown": max_drawdown,
        "sharpe_0rf": "0.8" if not regime_id else "",
        "annualised_turnover": "4.0" if not regime_id else "",
        "cost_drag": "0.01" if not regime_id else "",
        "status": status,
    }


def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "reports" / "global_multi_asset_alpha"
    gma4_root = root / "gma4_cross_asset_tournament_v1"
    gma5_root = root / "gma5_atomic_sleeve_ensemble_v1"
    out_root = root

    (gma4_root / "runs" / GMA4_RUN_ID).mkdir(parents=True)
    (gma5_root / "runs" / GMA5_RUN_ID).mkdir(parents=True)
    (gma4_root / "gma4_results_discussion_latest_v1.md").write_text(
        "| poisoned markdown | 999% |\n", encoding="utf-8"
    )

    _write_csv(
        gma4_root / "runs" / GMA4_RUN_ID / "gma4_tournament_scoreboard.csv",
        [
            _gma4_scoreboard_row(
                "gma4_abs_trend_12m_equal_weight_v1",
                "absolute_trend",
                "absolute_trend",
                "0.08",
                "-0.20",
            ),
            _gma4_scoreboard_row(
                "gma4_benchmark_spy_buy_hold_v1",
                "spy_buy_hold",
                "benchmark",
                "0.10",
                "-0.50",
            ),
        ],
    )
    _write_csv(
        gma4_root / "gma4_latest_robustness_board_v2.csv",
        [
            _gma4_robustness_row(
                "gma4_abs_trend_12m_equal_weight_v1",
                "absolute_trend",
                "absolute_trend",
                "0.06",
            ),
            _gma4_robustness_row(
                "gma4_benchmark_spy_buy_hold_v1",
                "spy_buy_hold",
                "benchmark",
                "0.09",
            ),
        ],
    )

    gma5_rows = []
    for entity_id, entity_type, baseline, severe in [
        ("gma5_equal_weight_atomic_sleeves_v1", "ensemble_variant", "0.091", "0.074"),
        ("gma5_risk_weighted_atomic_sleeves_v1", "ensemble_variant", "0.083", "0.067"),
        ("gma5_fixed_alpha_ridge_atomic_ensemble_v1", "ensemble_variant", "0.055", "0.027"),
        ("gma4_benchmark_spy_buy_hold_v1", "gma4_reference", "0.152", "0.151"),
        ("gma4_benchmark_bil_buy_hold_v1", "gma4_reference", "0.015", "0.014"),
    ]:
        gma5_rows.append(
            _gma5_scoreboard_row(
                entity_id,
                entity_type,
                "baseline_1bps",
                "full_common_oos",
                baseline,
                "-0.15",
            )
        )
        gma5_rows.append(
            _gma5_scoreboard_row(
                entity_id,
                entity_type,
                "severe_50bps",
                "full_common_oos",
                severe,
                "-0.17",
            )
        )
        if entity_type == "ensemble_variant":
            gma5_rows.append(
                _gma5_scoreboard_row(
                    entity_id,
                    entity_type,
                    "baseline_1bps",
                    "predefined_regime",
                    "",
                    "",
                    status="unavailable_before_minimum_training_history",
                    regime_id="gfc_stress",
                )
            )
    _write_csv(gma5_root / "gma5_latest_ensemble_scoreboard_v1.csv", gma5_rows)
    _write_csv(
        gma5_root / "gma5_latest_implementation_audit_v1.csv",
        [
            {
                "check_name": "first_ridge_oos_date_matches_training_rule",
                "status": "fail",
                "evidence_source": "fixture",
                "evidence_detail": "first OOS requires 60 completed observations",
            },
            {
                "check_name": "composite_replay_adapter_path_evidenced",
                "status": "insufficient_saved_evidence",
                "evidence_source": "fixture",
                "evidence_detail": "no matching replay source hash",
            },
            {
                "check_name": "no_sleeve_equity_curve_averaging_evidenced",
                "status": "insufficient_saved_evidence",
                "evidence_source": "fixture",
                "evidence_detail": "no run-specific source hash",
            },
        ],
    )
    (gma5_root / "runs" / GMA5_RUN_ID / "gma5_ensemble_manifest.json").write_text(
        json.dumps(
            {
                "created_at_utc": "2026-06-22T08:14:19.221811+00:00",
                "run_id": GMA5_RUN_ID,
                "gma4_source_run_id": GMA4_RUN_ID,
                "first_ensemble_out_of_sample_date": "2012-05-31",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return gma4_root, gma5_root, out_root


def _write_clean_execution_manifest(gma5_root: Path) -> None:
    clean_run_dir = gma5_root / "runs" / GMA5_CLEAN_RUN_ID
    clean_run_dir.mkdir(parents=True, exist_ok=True)
    (clean_run_dir / "gma5_clean_execution_manifest_v1.json").write_text(
        json.dumps(
            {
                "clean_execution_run_id": GMA5_CLEAN_RUN_ID,
                "original_run_id": GMA5_RUN_ID,
                "overall_reproducibility_status": "clean_execution_exact_reproduction_verified",
                "runtime_replay_trace": {"replay_adapter_invocation_count": 12},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_valid_structured_inputs_generate_required_outputs(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)

    result = generate_master_report(gma4_root, gma5_root, out_root)

    assert result.master_md_path.exists()
    assert result.master_csv_path.exists()
    assert result.validation_md_path.exists()
    assert result.validation_csv_path.exists()
    assert result.gma5_common_oos_start == "2012-05-31"
    assert result.gma5_common_oos_end == "2026-05-01"
    assert all(row["status"] == "pass" for row in result.validation_rows)


def test_entity_identity_collision_fails_generation(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)
    scoreboard_path = gma4_root / "runs" / GMA4_RUN_ID / "gma4_tournament_scoreboard.csv"
    rows = _read_csv(scoreboard_path)
    rows.append(
        {
            **rows[0],
            "strategy_id": "conflicting_strategy_name",
            "net_cagr": "0.07",
        }
    )
    _write_csv(scoreboard_path, rows)

    with pytest.raises(MasterReportError, match="entity identity collision"):
        generate_master_report(gma4_root, gma5_root, out_root)


def test_gma4_and_gma5_facts_come_from_structured_sources_not_markdown(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)

    generate_master_report(gma4_root, gma5_root, out_root)
    master_rows = _read_csv(out_root / "gma_research_latest_v1.csv")
    markdown = (out_root / "gma_research_latest_v1.md").read_text(encoding="utf-8")

    assert "999%" not in markdown
    assert any(
        row["phase"] == "GMA-4"
        and row["source_file"] == "gma4_tournament_scoreboard.csv"
        and row["metric_value"] == "0.08"
        for row in master_rows
    )
    assert all(
        row["source_file"] != "gma4_results_discussion_latest_v1.md"
        for row in master_rows
        if row["phase"] == "GMA-5"
    )
    assert any(
        row["phase"] == "GMA-5"
        and row["source_file"] == "gma5_latest_ensemble_scoreboard_v1.csv"
        and row["metric_value"] == "0.091"
        for row in master_rows
    )


def test_gma5_rows_use_common_oos_start_end(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)

    generate_master_report(gma4_root, gma5_root, out_root)
    master_rows = _read_csv(out_root / "gma_research_latest_v1.csv")
    gma5_metric_rows = [
        row
        for row in master_rows
        if row["record_type"] in {"ensemble_variant_metrics", "same_period_comparator_metrics"}
    ]

    assert gma5_metric_rows
    assert {row["evaluation_scope"] for row in gma5_metric_rows} == {"common_out_of_sample"}
    assert {row["period_start"] for row in gma5_metric_rows} == {"2012-05-31"}
    assert {row["period_end"] for row in gma5_metric_rows} == {"2026-05-01"}


def test_required_evidence_gates_appear(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)

    generate_master_report(gma4_root, gma5_root, out_root)
    master_rows = _read_csv(out_root / "gma_research_latest_v1.csv")
    gate_names = {
        row["metric_name"] for row in master_rows if row["record_type"] == "evidence_gate"
    }

    assert gate_names == {
        "first_ridge_oos_date_matches_training_rule",
        "composite_replay_adapter_path_evidenced",
        "no_sleeve_equity_curve_averaging_evidenced",
    }


def test_clean_execution_evidence_updates_master_only_on_success(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)
    _write_clean_execution_manifest(gma5_root)

    generate_master_report(gma4_root, gma5_root, out_root)
    master_rows = _read_csv(out_root / "gma_research_latest_v1.csv")
    markdown = (out_root / "gma_research_latest_v1.md").read_text(encoding="utf-8")
    clean_rows = [
        row for row in master_rows if row["record_type"] == "clean_execution_reproduction_evidence"
    ]

    assert clean_rows
    assert {row["run_id"] for row in clean_rows} == {GMA5_CLEAN_RUN_ID}
    assert any(
        row["metric_name"] == "netted composite ETF replay verified for clean reproduction"
        and row["metric_value"] == "resolved"
        for row in clean_rows
    )
    assert "not an impossible retroactive source snapshot" in markdown
    assert "GMA-5A.3R" in markdown


def test_repeated_generation_is_byte_identical_and_sources_unchanged(tmp_path):
    gma4_root, gma5_root, out_root = _make_fixture(tmp_path)
    source_paths = [
        gma4_root / "runs" / GMA4_RUN_ID / "gma4_tournament_scoreboard.csv",
        gma4_root / "gma4_latest_robustness_board_v2.csv",
        gma4_root / "gma4_results_discussion_latest_v1.md",
        gma5_root / "gma5_latest_ensemble_scoreboard_v1.csv",
        gma5_root / "gma5_latest_implementation_audit_v1.csv",
        gma5_root / "runs" / GMA5_RUN_ID / "gma5_ensemble_manifest.json",
    ]
    before = {path: _sha256(path) for path in source_paths}

    generate_master_report(gma4_root, gma5_root, out_root)
    first_csv = (out_root / "gma_research_latest_v1.csv").read_bytes()
    first_md = (out_root / "gma_research_latest_v1.md").read_bytes()
    generate_master_report(gma4_root, gma5_root, out_root)

    assert (out_root / "gma_research_latest_v1.csv").read_bytes() == first_csv
    assert (out_root / "gma_research_latest_v1.md").read_bytes() == first_md
    assert {path: _sha256(path) for path in source_paths} == before


def test_master_module_does_not_import_execution_paths():
    source = Path("src/market_strats/global_multi_asset/gma_master_report.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "import subprocess",
        "from subprocess",
        "import requests",
        "from requests",
        "import urllib",
        "from urllib",
        "gma4_replay_adapter import",
        "gma4_tournament import",
        "paper_order(",
        "broker(",
        "candidate(",
        "promotion(",
    ]
    assert not any(term in source for term in forbidden)
