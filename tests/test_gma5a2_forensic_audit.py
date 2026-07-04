import csv
import hashlib
import json
from pathlib import Path

from market_strats.global_multi_asset.gma5a2_forensic_audit import (
    RUN_ID,
    generate_forensic_audit,
)
from market_strats.global_multi_asset.gma_master_report import (
    GMA4_RUN_ID,
    generate_master_report,
)


def _write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scoreboard_row(
    entity_id: str,
    entity_type: str,
    cost_scenario: str,
    evaluation_scope: str,
    status: str = "evaluated",
    regime_id: str = "",
) -> dict[str, str]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "cost_scenario": cost_scenario,
        "evaluation_scope": evaluation_scope,
        "window_id": regime_id or evaluation_scope,
        "regime_id": regime_id,
        "start_date": "2012-05-31",
        "end_date": "2026-05-01" if not regime_id else "2009-03-09",
        "session_count": "3500" if not regime_id else "0",
        "metric_type": "annualised_cagr_and_drawdown",
        "cumulative_net_return": "1.0",
        "net_cagr": "0.08" if cost_scenario == "baseline_1bps" else "0.06",
        "max_drawdown": "-0.2",
        "sharpe_0rf": "0.8",
        "annualised_turnover": "4.0",
        "cost_drag": "0.01",
        "status": status,
    }


def _make_gma5a2_fixture(tmp_path: Path, include_training: bool = True) -> tuple[Path, Path, Path]:
    root = tmp_path / "reports" / "global_multi_asset_alpha" / "gma5_atomic_sleeve_ensemble_v1"
    run_dir = root / "runs" / RUN_ID
    run_dir.mkdir(parents=True)
    variants = [
        "gma5_equal_weight_atomic_sleeves_v1",
        "gma5_risk_weighted_atomic_sleeves_v1",
        "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
    ]
    scoreboard = []
    for variant in variants:
        scoreboard.append(
            _scoreboard_row(variant, "ensemble_variant", "baseline_1bps", "full_common_oos")
        )
        scoreboard.append(
            _scoreboard_row(variant, "ensemble_variant", "severe_50bps", "full_common_oos")
        )
        scoreboard.append(
            _scoreboard_row(variant, "ensemble_variant", "baseline_1bps", "rolling_3_year")
        )
        scoreboard.append(
            _scoreboard_row(variant, "ensemble_variant", "baseline_1bps", "rolling_3_year")
        )
        scoreboard.append(
            _scoreboard_row(variant, "ensemble_variant", "baseline_1bps", "rolling_5_year")
        )
        scoreboard.append(
            _scoreboard_row(
                variant,
                "ensemble_variant",
                "baseline_1bps",
                "predefined_regime",
                status="unavailable_before_minimum_training_history",
                regime_id="gfc_stress",
            )
        )
    scoreboard.append(
        _scoreboard_row(
            "gma4_benchmark_spy_buy_hold_v1", "gma4_reference", "baseline_1bps", "full_common_oos"
        )
    )
    scoreboard.append(
        _scoreboard_row(
            "gma4_benchmark_spy_buy_hold_v1", "gma4_reference", "severe_50bps", "full_common_oos"
        )
    )
    _write_csv(run_dir / "gma5_ensemble_scoreboard.csv", scoreboard)
    _write_csv(root / "gma5_latest_ensemble_scoreboard_v1.csv", scoreboard)

    weight_rows = []
    for variant in variants:
        for date, status, weight in [
            ("2012-05-31", "unavailable_before_minimum_training_history", "0.0"),
            ("2015-05-29", "evaluated", "0.25"),
        ]:
            for sleeve in ["s1", "s2", "s3", "s4"]:
                weight_rows.append(
                    {
                        "variant_id": variant,
                        "decision_date": date,
                        "sleeve_id": sleeve,
                        "sleeve_family": "fixture",
                        "sleeve_allocation_weight": weight,
                        "status": status,
                    }
                )
    _write_csv(run_dir / "gma5_ensemble_monthly_sleeve_weights.csv", weight_rows)
    _write_csv(
        run_dir / "gma5_ensemble_monthly_etf_targets.csv",
        [
            {
                "variant_id": variant,
                "decision_date": "2012-05-31",
                "symbol": symbol,
                "composite_etf_target_weight": weight,
            }
            for variant in variants
            for symbol, weight in [("SPY", "0.7"), ("BIL", "0.3")]
        ],
    )
    _write_csv(
        run_dir / "gma5_ensemble_monthly_features.csv",
        [
            {
                "sleeve_id": "s1",
                "decision_date": "2007-05-31",
                "execution_start_date": "2007-06-01",
            }
        ],
    )
    training_rows = (
        [
            {
                "decision_date": "2015-05-29",
                "sleeve_id": "s1",
                "training_row_count": "60",
                "training_start_date": "2010-05-28",
                "training_end_date": "2015-04-30",
                "ridge_alpha": "10.0",
                "feature_mean_json": "{}",
                "feature_std_json": "{}",
                "prediction": "0.01",
            }
        ]
        if include_training
        else []
    )
    _write_csv(
        run_dir / "gma5_ensemble_training_audit.csv",
        training_rows,
        fields=[
            "decision_date",
            "sleeve_id",
            "training_row_count",
            "training_start_date",
            "training_end_date",
            "ridge_alpha",
            "feature_mean_json",
            "feature_std_json",
            "prediction",
        ],
    )
    _write_csv(run_dir / "gma5_ensemble_rejections.csv", [], fields=["reason"])
    (run_dir / "gma5_ensemble_manifest.json").write_text(
        json.dumps(
            {
                "created_at_utc": "2026-06-22T08:14:19.221811+00:00",
                "run_id": RUN_ID,
                "gma4_source_run_id": GMA4_RUN_ID,
                "first_ensemble_out_of_sample_date": "2012-05-31",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_csv(
        root / "gma5_latest_implementation_audit_v1.csv",
        [
            {
                "check_name": "first_ridge_oos_date_matches_training_rule",
                "status": "fail",
                "evidence_source": "fixture",
                "evidence_detail": "fixture",
            },
            {
                "check_name": "composite_replay_adapter_path_evidenced",
                "status": "insufficient_saved_evidence",
                "evidence_source": "fixture",
                "evidence_detail": "fixture",
            },
            {
                "check_name": "no_sleeve_equity_curve_averaging_evidenced",
                "status": "insufficient_saved_evidence",
                "evidence_source": "fixture",
                "evidence_detail": "fixture",
            },
        ],
    )
    gma5_source = tmp_path / "gma5_source.py"
    replay_source = tmp_path / "replay_source.py"
    gma5_source.write_text("# fixture source\n", encoding="utf-8")
    replay_source.write_text(
        "def target_resolver(): pass\n_simulate_strategy = object()\n", encoding="utf-8"
    )
    return root, gma5_source, replay_source


def test_common_oos_and_first_true_ridge_date_are_distinct(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)

    result = generate_forensic_audit(root, gma5_source, replay_source)
    ridge = next(
        row
        for row in result.timeline_rows
        if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
    )

    assert ridge["first_common_ensemble_oos_date"] == "2012-05-31"
    assert ridge["first_true_learned_ridge_decision_date"] == "2015-05-29"
    assert ridge["pre_model_policy"] == "no_allocation_before_training"
    assert result.ridge_headline_classification == "includes_pre_model_fallback_period"


def test_gfc_unavailable_due_to_common_oos_start_for_every_variant(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)

    result = generate_forensic_audit(root, gma5_source, replay_source)

    assert {row["gfc_coverage_status"] for row in result.timeline_rows} == {
        "unavailable_before_common_oos_start"
    }


def test_missing_training_audit_does_not_invent_learned_date(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path, include_training=False)

    result = generate_forensic_audit(root, gma5_source, replay_source)
    ridge = next(
        row
        for row in result.timeline_rows
        if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
    )

    assert ridge["first_true_learned_ridge_decision_date"] == "insufficient_saved_evidence"
    assert result.ridge_headline_classification == "insufficient_saved_evidence"


def test_current_source_evidence_is_not_historical_evidence(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)

    result = generate_forensic_audit(root, gma5_source, replay_source)
    by_check = {row["check_name"]: row for row in result.replay_rows}

    assert (
        by_check["current_source_composite_target_replay_path_exists"]["status"]
        == "current_source_evidenced_only"
    )
    assert (
        by_check["historical_run_replay_adapter_hash_exists"]["status"]
        == "insufficient_saved_evidence"
    )


def test_historical_evidence_requires_run_specific_trace(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)
    manifest_path = root / "runs" / RUN_ID / "gma5_ensemble_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["composite_replay_adapter_hash"] = "abc123"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    result = generate_forensic_audit(root, gma5_source, replay_source)
    by_check = {row["check_name"]: row for row in result.replay_rows}

    assert (
        by_check["historical_run_replay_adapter_hash_exists"]["status"] == "historically_evidenced"
    )


def test_repeated_audit_generation_is_deterministic_and_sources_unchanged(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)
    source_paths = [
        root / "runs" / RUN_ID / "gma5_ensemble_scoreboard.csv",
        root / "runs" / RUN_ID / "gma5_ensemble_monthly_sleeve_weights.csv",
        root / "runs" / RUN_ID / "gma5_ensemble_monthly_etf_targets.csv",
        root / "runs" / RUN_ID / "gma5_ensemble_training_audit.csv",
        gma5_source,
        replay_source,
    ]
    before = {path: _sha256(path) for path in source_paths}

    result = generate_forensic_audit(root, gma5_source, replay_source)
    first_timeline = result.timeline_csv_path.read_bytes()
    generate_forensic_audit(root, gma5_source, replay_source)

    assert result.timeline_csv_path.read_bytes() == first_timeline
    assert {path: _sha256(path) for path in source_paths} == before


def test_master_csv_includes_gma5_rolling_window_count_rows(tmp_path):
    root, gma5_source, replay_source = _make_gma5a2_fixture(tmp_path)
    generate_forensic_audit(root, gma5_source, replay_source)
    gma4_root = tmp_path / "reports" / "global_multi_asset_alpha" / "gma4_cross_asset_tournament_v1"
    gma4_run = gma4_root / "runs" / GMA4_RUN_ID
    gma4_run.mkdir(parents=True)
    _write_csv(
        gma4_run / "gma4_tournament_scoreboard.csv",
        [
            {
                "run_id": GMA4_RUN_ID,
                "trial_id": "trial",
                "strategy_id": "strategy",
                "family": "family",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "full_common_history",
                "start_date": "2007-05-30",
                "end_date": "2026-05-01",
                "net_cagr": "0.1",
                "sharpe_0rf": "0.5",
                "sortino_0rf": "0.6",
                "max_drawdown": "-0.2",
                "annualised_turnover": "1.0",
                "cost_drag": "0.01",
                "average_cash_weight": "0.0",
                "maximum_hhi_concentration": "0.5",
                "status": "evaluated",
            }
        ],
    )
    _write_csv(
        gma4_root / "gma4_latest_robustness_board_v2.csv",
        [
            {
                "run_id": GMA4_RUN_ID,
                "trial_id": "trial",
                "strategy_id": "strategy",
                "family": "family",
                "effective_evaluation_start_date": "2007-05-30",
                "effective_evaluation_end_date": "2026-05-01",
                "severe_cost_full_history_net_cagr": "0.08",
                "cost_sensitivity_cagr_change": "-0.02",
                "positive_rolling_3_year_fraction": "1.0",
                "positive_rolling_5_year_fraction": "1.0",
                "gfc_regime_coverage_status": "partial_coverage",
                "covid_crash_regime_coverage_status": "full_coverage",
                "concentration_measurement_status": "concentration_measurement_available",
            }
        ],
    )
    generate_master_report(gma4_root, root, tmp_path / "reports" / "global_multi_asset_alpha")
    master_rows = _read_csv(
        tmp_path / "reports" / "global_multi_asset_alpha" / "gma_research_latest_v1.csv"
    )
    rolling_rows = [
        row
        for row in master_rows
        if row["metric_name"] in {"rolling 3Y window count", "rolling 5Y window count"}
    ]

    assert len(rolling_rows) == 6
    assert {
        row["metric_value"]
        for row in rolling_rows
        if row["metric_name"] == "rolling 3Y window count"
    } == {"2"}
    assert {
        row["metric_value"]
        for row in rolling_rows
        if row["metric_name"] == "rolling 5Y window count"
    } == {"1"}
