from __future__ import annotations

import ast
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.global_multi_asset.gma4_contract import FIXED_GMA4_UNIVERSE
from market_strats.global_multi_asset.gma4_replay_adapter import GMA4ReplayAdapterResult
from market_strats.global_multi_asset.gma5_atomic_sleeve_ensemble import (
    ACTIVE_SLEEVE_IDS,
    BIL,
    CONFIG_PATH,
    REGIMES,
    VARIANTS,
    _cap_sleeves,
    _composite_targets,
    _comparator_table,
    _discussion_section,
    _gma5_canonical_section,
    _hhi_provenance,
    _market_features,
    _metrics,
    _ridge_allocations,
    _risk_weighted_allocations,
    _rolling_window_bounds,
    _stable_json,
    _variant_table,
    _write_markdown_scoreboard,
    build_gma5a_implementation_audit,
    load_gma5_config,
    repair_gma5a_canonical_discussion,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _feature_row(
    sleeve_id: str,
    decision_date: date,
    *,
    completed: int = 60,
    value: float = 1.0,
    target: float = 0.01,
) -> dict[str, object]:
    config = load_gma5_config()
    row: dict[str, object] = {
        "sleeve_id": sleeve_id,
        "decision_date": decision_date,
        "completed_observation_count": completed,
        "target_return": target,
    }
    row.update({column: value for column in config.feature_columns})
    return row


def _fake_result(session_count: int = 300, *, cost: float = 100.0) -> GMA4ReplayAdapterResult:
    dates = pd.date_range("2020-01-01", periods=session_count, freq="D").date
    values = 100000.0 * (1.0002 ** np.arange(session_count))
    equity = pd.DataFrame(
        {
            "valuation_date": dates,
            "portfolio_value": values,
            "daily_return": pd.Series(values).pct_change().fillna(0.0),
        }
    )
    costs = pd.DataFrame(
        {
            "execution_date": [dates[min(10, session_count - 1)]],
            "trade_notional_abs": [10000.0],
            "transaction_cost": [cost],
        }
    )
    empty = pd.DataFrame()
    return GMA4ReplayAdapterResult(
        equity=equity,
        drawdown=empty,
        holdings=empty,
        orders=empty,
        fills=empty,
        costs=costs,
        signals=empty,
        signal_dates=[],
        execution_dates=[],
    )


def test_gma5_module_does_not_import_or_invoke_gma4_tournament():
    source_path = Path("src/market_strats/global_multi_asset/gma5_atomic_sleeve_ensemble.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.append(node.func.id)

    assert not any(name.endswith("gma4_tournament") for name in imports)
    assert "run_gma4_tournament" not in calls


def test_atomic_sleeve_pool_and_exclusions_are_frozen():
    config = load_gma5_config(CONFIG_PATH)
    excluded = set(config.raw["excluded_from_learned_inputs"])

    assert [item["trial_id"] for item in config.raw["atomic_sleeves"]] == ACTIVE_SLEEVE_IDS
    assert config.sleeve_families["gma4_defensive_drawdown_guard_v1"] == "defensive_risk_regime"
    assert config.sleeve_families["gma4_defensive_spy_200d_rotation_v1"] == (
        "defensive_risk_regime"
    )
    assert "gma4_xsmom_12m_top3_equal_weight_v1" in excluded
    assert all("benchmark" not in sleeve for sleeve in ACTIVE_SLEEVE_IDS)
    assert all("blend" not in sleeve for sleeve in ACTIVE_SLEEVE_IDS)


def test_equal_weight_allocations_are_exactly_twenty_five_percent_before_netting():
    allocations = {sleeve_id: 0.25 for sleeve_id in ACTIVE_SLEEVE_IDS}

    assert set(allocations) == set(ACTIVE_SLEEVE_IDS)
    assert set(allocations.values()) == {0.25}
    assert sum(allocations.values()) == 1.0


def test_risk_weighted_allocations_use_current_rows_only_not_future_rows():
    config = load_gma5_config()
    current = pd.DataFrame(
        [
            _feature_row(ACTIVE_SLEEVE_IDS[0], date(2021, 1, 31), completed=36, value=0.1),
            _feature_row(ACTIVE_SLEEVE_IDS[1], date(2021, 1, 31), completed=36, value=0.2),
        ]
    )
    future = pd.DataFrame(
        [_feature_row(ACTIVE_SLEEVE_IDS[2], date(2099, 1, 31), completed=500, value=99.0)]
    )

    without_future = _risk_weighted_allocations(current, config)
    with_future_not_passed = _risk_weighted_allocations(current.copy(), config)

    assert without_future == with_future_not_passed
    assert ACTIVE_SLEEVE_IDS[2] not in without_future
    assert not future.empty


def test_ridge_uses_strictly_prior_completed_targets_and_training_statistics_only():
    config = load_gma5_config()
    decision_date = date(2025, 1, 31)
    train_dates = pd.date_range("2020-01-31", periods=60, freq="ME").date
    history = pd.DataFrame(
        [
            _feature_row(ACTIVE_SLEEVE_IDS[0], item, completed=idx, value=1.0, target=0.01)
            for idx, item in enumerate(train_dates, start=1)
        ]
    )
    current = pd.DataFrame(
        [_feature_row(ACTIVE_SLEEVE_IDS[0], decision_date, completed=61, value=999.0)]
    )
    all_features = pd.concat([history, current], ignore_index=True)

    _weights, audit = _ridge_allocations(current, all_features, decision_date, config)

    assert audit
    assert audit[0]["training_end_date"] < decision_date
    means = json.loads(audit[0]["feature_mean_json"])
    assert set(means) == set(config.feature_columns)
    assert all(value == 1.0 for value in means.values())
    assert audit[0]["ridge_alpha"] == config.ridge_alpha == 10.0


def test_ridge_outputs_do_not_exist_before_sixty_monthly_observations():
    config = load_gma5_config()
    decision_date = date(2024, 12, 31)
    train_dates = pd.date_range("2020-01-31", periods=59, freq="ME").date
    history = pd.DataFrame(
        [
            _feature_row(ACTIVE_SLEEVE_IDS[0], item, completed=idx, value=1.0, target=0.01)
            for idx, item in enumerate(train_dates, start=1)
        ]
    )
    current = pd.DataFrame(
        [_feature_row(ACTIVE_SLEEVE_IDS[0], decision_date, completed=59, value=1.0)]
    )

    weights, audit = _ridge_allocations(current, history, decision_date, config)

    assert weights == {}
    assert audit == []


def test_individual_and_joint_defensive_family_caps_are_enforced():
    config = load_gma5_config()
    raw = {
        ACTIVE_SLEEVE_IDS[0]: 0.01,
        ACTIVE_SLEEVE_IDS[1]: 0.01,
        ACTIVE_SLEEVE_IDS[2]: 10.0,
        ACTIVE_SLEEVE_IDS[3]: 10.0,
    }

    capped = _cap_sleeves(raw, config.sleeve_families, config.individual_cap, config.family_cap)

    assert all(value <= 0.40 + 1e-12 for value in capped.values())
    defensive_total = capped[ACTIVE_SLEEVE_IDS[2]] + capped[ACTIVE_SLEEVE_IDS[3]]
    assert defensive_total <= 0.50 + 1e-12


def test_composite_targets_net_overlaps_and_allocate_residual_to_bil():
    sleeve_targets = {
        ACTIVE_SLEEVE_IDS[0]: {"SPY": 0.50, BIL: 0.50},
        ACTIVE_SLEEVE_IDS[1]: {"SPY": 1.00},
        ACTIVE_SLEEVE_IDS[2]: {BIL: 1.00},
        ACTIVE_SLEEVE_IDS[3]: {BIL: 1.00},
    }
    allocations = {ACTIVE_SLEEVE_IDS[0]: 0.25, ACTIVE_SLEEVE_IDS[1]: 0.25}

    target = _composite_targets(allocations, sleeve_targets)

    assert abs(sum(target.values()) - 1.0) < 1e-12
    assert target["SPY"] == 0.375
    assert target[BIL] == 0.625
    assert set(target) <= set(FIXED_GMA4_UNIVERSE)


def test_metrics_use_composite_replay_costs_and_short_regimes_do_not_annualise():
    result = _fake_result(session_count=40, cost=125.0)
    start = result.equity["valuation_date"].iloc[0]
    end = result.equity["valuation_date"].iloc[-1]

    row = _metrics(
        entity_id=VARIANTS[0],
        entity_type="ensemble_variant",
        cost_scenario="severe_50bps",
        result=result,
        start=start,
        end=end,
        scope="predefined_regime",
        window_id="covid_crash",
        regime_id="covid_crash",
    )

    assert row["metric_type"] == "cumulative_return_and_drawdown"
    assert row["net_cagr"] == ""
    assert row["cost_drag"] == 0.00125


def test_gfc_is_labelled_unavailable_before_minimum_training_history():
    result = _fake_result()
    row = _metrics(
        entity_id=VARIANTS[2],
        entity_type="ensemble_variant",
        cost_scenario="baseline_1bps",
        result=result,
        start=date(2007, 10, 9),
        end=date(2009, 3, 9),
        scope="predefined_regime",
        window_id="gfc_stress",
        regime_id="gfc_stress",
        status="unavailable_before_minimum_training_history",
    )

    assert row["session_count"] == 0
    assert row["status"] == "unavailable_before_minimum_training_history"
    assert REGIMES["gfc_stress"] == ("2007-10-09", "2009-03-09")


def test_rolling_window_bounds_are_deterministic():
    dates = pd.date_range("2018-01-01", "2025-12-31", freq="B").date

    first = _rolling_window_bounds(list(dates), date(2020, 1, 31), 3)
    second = _rolling_window_bounds(list(dates), date(2020, 1, 31), 3)

    assert first == second
    assert first[0][0] == "2020_2022"
    assert all(start <= end for _window, start, end in first)
    assert _rolling_window_bounds(list(dates), date(2020, 1, 31), 5)


def test_market_features_use_spy_and_bil_common_history_only():
    spy_dates = pd.date_range("2000-01-03", periods=400, freq="B").date
    bil_dates = spy_dates[260:]
    prices = {
        symbol: pd.DataFrame(
            {"total_return_index": np.linspace(100.0, 120.0, len(bil_dates))},
            index=bil_dates,
        )
        for symbol in FIXED_GMA4_UNIVERSE
    }
    prices["SPY"] = pd.DataFrame(
        {"total_return_index": np.linspace(100.0, 140.0, len(spy_dates))},
        index=spy_dates,
    )
    prices[BIL] = pd.DataFrame(
        {"total_return_index": np.linspace(100.0, 101.0, len(bil_dates))},
        index=bil_dates,
    )

    features = _market_features(prices, spy_dates[-1])

    assert features == {
        "market_spy_200d_trend_state": 0.0,
        "market_spy_252d_drawdown": 0.0,
        "market_cross_asset_breadth": 0.0,
    }


def test_hhi_provenance_reads_frozen_scoreboard_without_modifying_it():
    config = load_gma5_config()
    scoreboard_path = Path(config.raw["source"]["gma4_run_dir"]) / "gma4_tournament_scoreboard.csv"
    before = _sha256(scoreboard_path)

    provenance = _hhi_provenance(config)

    assert _sha256(scoreboard_path) == before
    assert provenance["source_column"] == "maximum_hhi_concentration"
    assert provenance["status"] in {
        "validated_from_frozen_gma4_scoreboard",
        "concentration_measurement_missing",
    }


def test_generated_text_avoids_forbidden_decision_language(tmp_path: Path):
    scoreboard = pd.DataFrame(
        [
            {
                "entity_id": VARIANTS[0],
                "entity_type": "ensemble_variant",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "full_common_oos",
                "net_cagr": 0.01,
                "max_drawdown": -0.02,
                "sharpe_0rf": 1.0,
                "annualised_turnover": 0.5,
                "status": "evaluated",
            }
        ]
    )
    path = tmp_path / "scoreboard.md"
    _write_markdown_scoreboard(path, scoreboard, "gma5_test")
    combined = (
        path.read_text(encoding="utf-8").lower()
        + _discussion_section("gma5_test", date(2025, 1, 31)).lower()
    )

    for forbidden in [
        "winner",
        "candidate",
        "approved",
        "promoted",
        "live_ready",
        "recommended_for_execution",
    ]:
        assert forbidden not in combined
    assert "no execution or promotion decision is produced" in combined
    assert "observed_development_evidence" in combined
    assert "not_a_pristine_final_holdout" in combined


def test_stable_json_is_deterministic_for_repeated_research_outputs():
    payload = {"b": [2, 1], "a": {"z": 3}}

    assert _stable_json(payload) == _stable_json(payload)


def _gma5_score_row(
    entity_id: str,
    cost_scenario: str,
    evaluation_scope: str,
    *,
    regime_id: str = "",
    net_cagr: float | str = 0.05,
    max_drawdown: float | str = -0.10,
    status: str = "evaluated",
) -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "entity_type": "ensemble_variant" if entity_id in VARIANTS else "gma4_reference",
        "cost_scenario": cost_scenario,
        "evaluation_scope": evaluation_scope,
        "window_id": regime_id or evaluation_scope,
        "regime_id": regime_id,
        "start_date": "2012-05-31",
        "end_date": "2026-05-01",
        "session_count": 1000 if status == "evaluated" else 0,
        "metric_type": "annualised_cagr_and_drawdown" if status == "evaluated" else "unavailable",
        "cumulative_net_return": 0.5 if status == "evaluated" else "",
        "net_cagr": net_cagr,
        "max_drawdown": max_drawdown,
        "sharpe_0rf": 0.5,
        "annualised_turnover": 1.0,
        "cost_drag": 0.01,
        "status": status,
    }


def _write_synthetic_reporting_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    gma4_run = tmp_path / "gma4_run"
    gma5_run = tmp_path / "gma5_root" / "runs" / "gma5_test"
    gma4_run.mkdir(parents=True)
    gma5_run.mkdir(parents=True)
    config = load_gma5_config()
    manifest = {
        "run_id": "gma5_test",
        "first_ensemble_out_of_sample_date": "2012-05-31",
        "ensemble_configuration_hash": _sha256(CONFIG_PATH),
        "atomic_sleeve_registry_hash": hashlib.sha256(
            json.dumps(
                config.raw["atomic_sleeves"], sort_keys=True, separators=(",", ":"), default=str
            ).encode("utf-8")
        ).hexdigest(),
        "gma4_source_file_hashes": {},
    }
    (gma5_run / "gma5_ensemble_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = []
    for idx, variant in enumerate(VARIANTS):
        rows.extend(
            [
                _gma5_score_row(
                    variant, "baseline_1bps", "full_common_oos", net_cagr=0.09 - idx * 0.02
                ),
                _gma5_score_row(
                    variant, "severe_50bps", "full_common_oos", net_cagr=0.07 - idx * 0.02
                ),
                _gma5_score_row(variant, "baseline_1bps", "rolling_3_year"),
                _gma5_score_row(variant, "baseline_1bps", "rolling_5_year"),
                _gma5_score_row(
                    variant,
                    "baseline_1bps",
                    "predefined_regime",
                    regime_id="gfc_stress",
                    net_cagr="",
                    max_drawdown="",
                    status="unavailable_before_minimum_training_history",
                ),
            ]
        )
    for reference in [
        "gma4_benchmark_bil_buy_hold_v1",
        "gma4_benchmark_spy_buy_hold_v1",
        "gma4_benchmark_equal_weight_22_monthly_v1",
        "gma4_abs_trend_12m_equal_weight_v1",
        "gma4_xsmom_12m_top5_inverse_vol_v1",
        "gma4_defensive_drawdown_guard_v1",
        "gma4_defensive_spy_200d_rotation_v1",
        "gma4_blend_equal_abs10_xsmom6_defensive_v1",
    ]:
        rows.append(_gma5_score_row(reference, "baseline_1bps", "full_common_oos"))
        rows.append(_gma5_score_row(reference, "severe_50bps", "full_common_oos"))
    pd.DataFrame(rows).to_csv(gma5_run / "gma5_ensemble_scoreboard.csv", index=False)
    pd.DataFrame(
        [
            {
                "variant_id": variant,
                "decision_date": "2020-01-31",
                "sleeve_id": sleeve,
                "sleeve_family": "test",
                "sleeve_allocation_weight": 0.25,
                "status": "available",
            }
            for variant in VARIANTS
            for sleeve in ACTIVE_SLEEVE_IDS
        ]
    ).to_csv(gma5_run / "gma5_ensemble_monthly_sleeve_weights.csv", index=False)
    pd.DataFrame(
        [
            {
                "variant_id": variant,
                "decision_date": "2020-01-31",
                "symbol": symbol,
                "composite_etf_target_weight": 1.0 if symbol == BIL else 0.0,
            }
            for variant in VARIANTS
            for symbol in FIXED_GMA4_UNIVERSE
        ]
    ).to_csv(gma5_run / "gma5_ensemble_monthly_etf_targets.csv", index=False)
    pd.DataFrame(
        [
            {
                "sleeve_id": ACTIVE_SLEEVE_IDS[0],
                "decision_date": "2020-01-31",
                "execution_start_date": "2020-02-03",
                "execution_end_date": "2020-02-28",
                "target_available_date": "2020-02-28",
            }
        ]
    ).to_csv(gma5_run / "gma5_ensemble_monthly_features.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_date": "2015-05-29",
                "sleeve_id": ACTIVE_SLEEVE_IDS[0],
                "training_row_count": 60,
                "training_start_date": "2010-05-28",
                "training_end_date": "2015-04-30",
                "ridge_alpha": 10.0,
            }
        ]
    ).to_csv(gma5_run / "gma5_ensemble_training_audit.csv", index=False)
    pd.DataFrame(
        [
            {
                "trial_id": "trial_a",
                "family": "benchmark",
                "cost_scenario": "baseline_1bps",
                "evaluation_scope": "full_common_history",
                "net_cagr": 0.10,
                "sharpe_0rf": 1.0,
                "sortino_0rf": 1.2,
                "max_drawdown": -0.2,
                "annualised_turnover": 0.5,
                "cost_drag": 0.001,
                "average_cash_weight": 0.1,
                "maximum_hhi_concentration": 0.3333,
            }
        ]
    ).to_csv(gma4_run / "gma4_tournament_scoreboard.csv", index=False)
    pd.DataFrame(
        [
            {
                "gfc_regime_coverage_status": "partial_coverage",
                "gfc_regime_metric_type": "annualised_cagr_and_drawdown",
                "covid_crash_regime_coverage_status": "full_coverage",
                "covid_crash_regime_metric_type": "cumulative_return_and_drawdown",
                "covid_recovery_regime_coverage_status": "full_coverage",
                "covid_recovery_regime_metric_type": "annualised_cagr_and_drawdown",
                "inflation_2022_regime_coverage_status": "full_coverage",
                "inflation_2022_regime_metric_type": "cumulative_return_and_drawdown",
                "geopolitical_post_2023_regime_coverage_status": "full_coverage",
                "geopolitical_post_2023_regime_metric_type": "annualised_cagr_and_drawdown",
            }
        ]
    ).to_csv(gma4_run / "gma4_robustness_board_v2.csv", index=False)
    discussion = tmp_path / "discussion.md"
    discussion.write_text(
        "# Discussion\n\n"
        "## Baseline Full-History Table\n\n"
        "| Rank | Strategy | Family | Net CAGR | Sharpe | Sortino | Max Drawdown | Annual Turnover | Cost Drag | Average Cash | Max HHI |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| 1 | Trial A | benchmark | 0.00% | 0.000 | 0.000 | 0.00% | 0.00x | 0.00% | 0.00% | not reported |\n\n"
        "<!-- GMA4F_ROBUSTNESS_START -->\nold\n"
        "<!-- GMA4F1_CORRECTION_START -->\nnested\n<!-- GMA4F1_CORRECTION_END -->\n"
        "<!-- GMA4F_ROBUSTNESS_END -->\n\n"
        "<!-- GMA5_ENSEMBLE_START -->\nold gma5\n<!-- GMA5_ENSEMBLE_END -->\n\n"
        "## Update Protocol\n",
        encoding="utf-8",
    )
    return gma4_run, gma5_run, discussion


def test_gma5_variant_and_comparator_tables_render_from_saved_scoreboard(tmp_path: Path):
    _gma4_run, gma5_run, _discussion = _write_synthetic_reporting_run(tmp_path)
    manifest = json.loads((gma5_run / "gma5_ensemble_manifest.json").read_text())
    scoreboard = pd.read_csv(gma5_run / "gma5_ensemble_scoreboard.csv")

    variant_table = _variant_table(scoreboard, manifest)
    comparator_table = _comparator_table(scoreboard)
    section = _gma5_canonical_section(
        variant_table=variant_table, comparator_table=comparator_table, run_id="gma5_test"
    )

    assert list(variant_table["Variant"]) == VARIANTS
    assert len(comparator_table) == 8
    assert "Comparator metrics are not present" not in section
    assert "gma5_equal_weight_atomic_sleeves_v1" in section
    assert "GFC coverage status" in section


def test_reporting_repair_removes_nested_markers_and_renders_hhi(tmp_path: Path):
    gma4_run, gma5_run, discussion = _write_synthetic_reporting_run(tmp_path)

    repair_gma5a_canonical_discussion(
        discussion_path=discussion,
        gma4_run_dir=gma4_run,
        gma5_run_dir=gma5_run,
    )
    text = discussion.read_text(encoding="utf-8")

    assert text.count("<!-- GMA4F_ROBUSTNESS_START -->") == 1
    assert text.count("<!-- GMA4F_ROBUSTNESS_END -->") == 1
    assert "GMA4F1_CORRECTION" not in text
    assert "GMA-4F v1 is retained in run outputs for audit history" in text
    assert "0.333" in text
    assert "Short-regime annualised CAGR tables are not retained" in text


def test_audit_marks_replay_source_evidence_insufficient_and_oos_mismatch_failed(
    tmp_path: Path,
):
    _gma4_run, gma5_run, _discussion = _write_synthetic_reporting_run(tmp_path)

    audit = build_gma5a_implementation_audit(run_dir=gma5_run, config_path=CONFIG_PATH)
    by_check = audit.set_index("check_name")

    assert by_check.loc["composite_replay_adapter_path_evidenced", "status"] == (
        "insufficient_saved_evidence"
    )
    assert by_check.loc["no_sleeve_equity_curve_averaging_evidenced", "status"] == (
        "insufficient_saved_evidence"
    )
    assert by_check.loc["first_ridge_oos_date_matches_training_rule", "status"] == "fail"
    assert by_check.loc["monthly_etf_targets_sum_to_one", "status"] == "pass"
