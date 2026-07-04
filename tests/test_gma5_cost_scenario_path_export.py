from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from market_strats.global_multi_asset.gma4_replay_adapter import GMA4ReplayAdapterResult
from market_strats.global_multi_asset.gma5_cost_scenario_path_export import (
    CLEAN_RUN_ID,
    COST_SCENARIOS,
    VARIANTS,
    CostScenarioPathExportError,
    build_learned_scoreboard,
    reconcile_full_period,
    run_export,
    sha256_file,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _fake_result(strategy_id: str, bps: float) -> GMA4ReplayAdapterResult:
    dates = pd.to_datetime(["2015-05-28", "2015-05-29", "2015-06-01"]).date
    values = [100.0, 101.0 + bps / 10000.0, 102.0 + bps / 10000.0]
    equity = pd.DataFrame(
        {
            "valuation_date": dates,
            "portfolio_value": values,
            "daily_return": pd.Series(values).pct_change().fillna(0.0),
        }
    )
    costs = pd.DataFrame(
        {
            "execution_date": dates,
            "trade_notional_abs": [0.0, 10.0, 0.0],
            "transaction_cost": [0.0, bps / 10000.0, 0.0],
        }
    )
    return GMA4ReplayAdapterResult(
        equity=equity,
        drawdown=pd.DataFrame(),
        holdings=pd.DataFrame(),
        orders=pd.DataFrame(),
        fills=pd.DataFrame(),
        costs=costs,
        signals=pd.DataFrame(),
        signal_dates=[],
        execution_dates=list(dates),
    )


def _make_clean_run(tmp_path: Path) -> Path:
    run_dir = (
        tmp_path
        / "reports"
        / "global_multi_asset_alpha"
        / "gma5_atomic_sleeve_ensemble_v1"
        / "runs"
        / CLEAN_RUN_ID
    )
    target_rows = [
        {
            "variant_id": variant,
            "decision_date": "2015-05-29",
            "symbol": "BIL",
            "composite_etf_target_weight": "1.0",
        }
        for variant in VARIANTS
    ]
    _write_csv(run_dir / "gma5_ensemble_monthly_etf_targets.csv", target_rows)
    _write_csv(
        run_dir / "gma5_composite_target_netting_audit_v2.csv",
        [
            {
                "variant_id": row["variant_id"],
                "decision_date": row["decision_date"],
                "ticker": row["symbol"],
                "final_target_weight": row["composite_etf_target_weight"],
            }
            for row in target_rows
        ],
    )
    target_hash = sha256_file(run_dir / "gma5_ensemble_monthly_etf_targets.csv")
    (run_dir / "gma5_clean_execution_manifest_v1.json").write_text(
        json.dumps({"clean_execution_run_id": CLEAN_RUN_ID}), encoding="utf-8"
    )
    (run_dir / "gma5_runtime_replay_trace_v1.json").write_text(
        json.dumps({"runtime": "fixture"}), encoding="utf-8"
    )
    (run_dir / "gma5_composite_replay_provenance_v1.json").write_text(
        json.dumps(
            {
                "composite_target_input_hash": target_hash,
                "replay_adapter_source_hash": "adapter_hash",
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "gma5_ensemble_scoreboard.csv",
        [
            {
                "entity_id": variant,
                "cost_scenario": cost,
                "evaluation_scope": "full_common_oos",
                "status": "evaluated",
                "net_cagr": "0",
                "max_drawdown": "0",
                "cumulative_net_return": "0",
                "annualised_turnover": "0",
                "cost_drag": "0",
            }
            for variant in VARIANTS
            for cost in COST_SCENARIOS
        ],
    )
    return run_dir


def test_saved_target_hash_must_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = _make_clean_run(tmp_path)
    (run_dir / "gma5_composite_replay_provenance_v1.json").write_text(
        json.dumps({"composite_target_input_hash": "bad", "replay_adapter_source_hash": "h"}),
        encoding="utf-8",
    )

    with pytest.raises(CostScenarioPathExportError, match="saved target hash mismatch"):
        run_export(run_dir, replay_function=lambda **_kwargs: _fake_result("x", 1.0))


def test_path_export_invokes_replay_and_exports_all_variant_cost_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = _make_clean_run(tmp_path)
    calls = []

    def fake_loader():
        return {"BIL": pd.DataFrame({"total_return_index": [1.0]})}, pd.DataFrame(), pd.DataFrame()

    def fake_replay(**kwargs):
        calls.append(kwargs)
        return _fake_result(kwargs["strategy_id"], kwargs["config"].cost_bps_per_notional)

    monkeypatch.setattr(
        "market_strats.global_multi_asset.gma5_cost_scenario_path_export.load_gma4_bundle_prices_cash",
        fake_loader,
    )
    result = run_export(run_dir, replay_function=fake_replay)

    exported_pairs = {(row["variant_id"], row["cost_scenario"]) for row in result.path_rows}
    assert len(calls) == 12
    assert exported_pairs == {(variant, cost) for variant in VARIANTS for cost in COST_SCENARIOS}
    assert all(row["cost_scenario"] in COST_SCENARIOS for row in result.path_rows)
    assert {str(call["minimum_signal_date"]) for call in calls} == {"2015-05-29"}
    assert result.journal["strategy_or_model_logic_invoked"] is False
    assert result.journal["saved_target_hash_verified"] is True
    assert (run_dir / "gma5_cost_scenario_path_export_v1.csv").exists()


def test_full_period_reconciliation_blocks_learned_metrics_until_pass(tmp_path: Path) -> None:
    run_dir = _make_clean_run(tmp_path)
    full_metrics = {
        (variant, cost): {
            "net_cagr": 1.0,
            "max_drawdown": 0.0,
            "cumulative_net_return": 0.0,
            "annualised_turnover": 0.0,
            "cost_drag": 0.0,
        }
        for variant in VARIANTS
        for cost in COST_SCENARIOS
    }

    status, _rows = reconcile_full_period(run_dir, full_metrics)
    learned, scope, _dates = build_learned_scoreboard([], status)

    assert status == "full_period_path_reconciliation_failed"
    assert {row["measurement_status"] for row in learned} == {"not_available_from_saved_artifacts"}
    assert scope[0]["measurement_status"] == "not_available_from_saved_artifacts"


def test_learned_only_start_uses_effective_replay_path_date() -> None:
    rows = [
        {
            "date": "2015-06-01",
            "variant_id": variant,
            "cost_scenario": cost,
            "portfolio_value": "100",
            "net_return": "0",
            "turnover": "0",
            "transaction_cost": "0",
        }
        for variant in VARIANTS
        for cost in COST_SCENARIOS
    ]

    learned, _scope, dates = build_learned_scoreboard(
        rows, "full_period_path_reconciliation_passed"
    )

    assert dates["first_learned_ridge_decision_date"] == "2015-05-29"
    assert dates["learned_only_metric_start_date"] == "2015-06-01"
    assert {row["period_start"] for row in learned} == {"2015-06-01"}
    assert all(row["annualised_volatility"] != "" for row in learned)


def test_no_forbidden_operations_in_export_source() -> None:
    source = Path(
        "src/market_strats/global_multi_asset/gma5_cost_scenario_path_export.py"
    ).read_text(encoding="utf-8")
    forbidden = [
        "git add",
        "git commit",
        "git push",
        "requests",
        "urllib",
        "paper_order",
        "broker",
        "candidate",
        "promotion_path",
        "train_test_split",
        "fit(",
    ]
    assert not any(term in source for term in forbidden)


def test_repeated_generation_is_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir = _make_clean_run(tmp_path)

    def fake_loader():
        return {"BIL": pd.DataFrame({"total_return_index": [1.0]})}, pd.DataFrame(), pd.DataFrame()

    monkeypatch.setattr(
        "market_strats.global_multi_asset.gma5_cost_scenario_path_export.load_gma4_bundle_prices_cash",
        fake_loader,
    )
    run_export(
        run_dir,
        replay_function=lambda **kwargs: _fake_result("x", kwargs["config"].cost_bps_per_notional),
    )
    first = (run_dir / "gma5_cost_scenario_path_export_v1.csv").read_bytes()
    run_export(
        run_dir,
        replay_function=lambda **kwargs: _fake_result("x", kwargs["config"].cost_bps_per_notional),
    )

    assert (run_dir / "gma5_cost_scenario_path_export_v1.csv").read_bytes() == first
    assert _read_csv(run_dir / "gma5_learned_only_scope_availability_v1.csv")
