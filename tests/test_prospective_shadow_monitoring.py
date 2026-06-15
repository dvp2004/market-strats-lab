from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.prospective_shadow_monitoring import (
    PILOT_UNIVERSE,
    REQUIRED_MODEL_HASH,
    deterministic_session_id,
    save_phase23k_prospective_shadow_monitoring,
    trading_horizon_end_date,
)


def _prices(periods: int = 8, *, open_gap: float = 0.0, invalid_ohlc: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2026-06-12", periods=periods)
    rows = []
    for index, date in enumerate(dates):
        close = 100.0 + index
        open_price = close * (1.0 + open_gap) if date == pd.Timestamp("2026-06-15") else close
        high = max(open_price, close) + 1.0
        low = min(open_price, close) - 1.0
        if invalid_ohlc and date == pd.Timestamp("2026-06-15"):
            high = low - 1.0
        rows.append(
            {
                "date": date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "adj_close": close,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def _write_sources(
    tmp_path: Path,
    *,
    ranking: bool = True,
    execution_available: bool = False,
    entered: bool = False,
    wrong_hash: bool = False,
    changed_universe: bool = False,
    nonpositive_open: bool = False,
    invalid_ohlc: bool = False,
    open_gap: float = 0.0,
    mature: bool = False,
    fill_mismatch: bool = False,
    negative_cash: bool = False,
) -> dict:
    reports = tmp_path / "reports"
    phase23j = reports / "phase23j"
    shadow = reports / "shadow"
    phase23f = reports / "phase23f"
    data = tmp_path / "data" / "combined"
    phase23j.mkdir(parents=True, exist_ok=True)
    shadow.mkdir(parents=True, exist_ok=True)
    phase23f.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    model_hash = "bad_hash" if wrong_hash else REQUIRED_MODEL_HASH
    signal_date = "2026-06-12"
    pd.DataFrame(
        [
            {
                "phase23j_decision": "ready",
                "post_endpoint_data_ready": True,
                "prospective_ranking_generated": ranking,
                "manual_shadow_proposal_ready": ranking,
                "simulated_fill_ready": execution_available,
                "selected_signal_date": signal_date if ranking else "",
                "post_endpoint_as_of_date": "2026-06-13",
                "model_version": "phase23g_ridge_ranker_v1",
                "phase23i_freeze_hash": model_hash,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    ).to_csv(phase23j / "phase23j_summary.csv", index=False)

    universe = PILOT_UNIVERSE.copy()
    if changed_universe:
        universe[-1] = "ZZZZ"
    ranking_rows = []
    for rank, ticker in enumerate(universe, start=1):
        ranking_rows.append(
            {
                "signal_date": signal_date,
                "ticker": ticker,
                "sector_asof": "Tech" if rank <= 6 else "Other",
                "model_version": "phase23g_ridge_ranker_v1",
                "predicted_rank": rank,
                "predicted_20d_excess_return_or_ranking_score": 17 - rank,
                "prediction_is_prospective": True,
                "reference_price": 100.0,
                "reference_price_date": signal_date,
            }
        )
    ranking_frame = pd.DataFrame(ranking_rows) if ranking else pd.DataFrame()
    ranking_frame.to_csv(phase23j / "phase23j_current_ranking.csv", index=False)

    selected = universe[:5]
    target_rows = []
    proposed_rows = []
    for ticker in selected:
        open_price = 100.0 * (1.0 + open_gap) if execution_available else np.nan
        if nonpositive_open:
            open_price = 0.0
        target_rows.append(
            {
                "selected_signal_date": signal_date,
                "planned_execution_date": "2026-06-15",
                "expected_execution_date": "2026-06-15",
                "observed_execution_date": "2026-06-15" if execution_available else "",
                "portfolio_id": "ridge_top5_equal_weight",
                "ticker": ticker,
                "target_weight": 0.2,
                "target_notional": 20000.0,
                "reference_price": 100.0,
                "reference_price_date": signal_date,
                "execution_open_price": open_price,
                "execution_price_available": execution_available and open_price > 0,
                "estimated_target_shares": 200,
                "paper_order_allowed": execution_available and open_price > 0,
                "order_blocking_reason": "" if execution_available and open_price > 0 else "execution_open_price_pending",
            }
        )
        proposed_rows.append(
            {
                "selected_signal_date": signal_date,
                "portfolio_id": "ridge_top5_equal_weight",
                "ticker": ticker,
                "target_weight": 0.2,
                "target_notional": 20000.0,
                "reference_price": 100.0,
                "reference_price_date": signal_date,
                "current_shares": 0,
                "target_shares": 200,
                "proposed_quantity": 200,
                "order_side": "BUY",
                "paper_order_allowed": execution_available and open_price > 0,
                "order_blocking_reason": "" if execution_available and open_price > 0 else "execution_open_price_pending",
            }
        )
    pd.DataFrame(target_rows).to_csv(phase23j / "phase23j_current_target_portfolio.csv", index=False)
    pd.DataFrame(proposed_rows).to_csv(shadow / "current_proposed_order_plan.csv", index=False)

    feature_rows = []
    for index, ticker in enumerate(universe):
        row = {"signal_date": signal_date, "ticker": ticker}
        for feature in [
            "momentum_21d",
            "momentum_63d",
            "momentum_252d_skip21d",
            "trend_distance_200d",
            "realized_volatility_21d",
            "volume_surprise_20d",
            "average_dollar_volume_20d",
            "beta_252d",
            "market_breadth_200d",
            "cross_sectional_dispersion_21d",
        ]:
            row[feature] = float(index)
        feature_rows.append(row)
    pd.DataFrame(feature_rows).to_csv(phase23j / "phase23j_prospective_feature_panel.csv", index=False)
    reference = []
    for day in range(12):
        for index, ticker in enumerate(PILOT_UNIVERSE):
            row = {"signal_date": f"2026-04-{day + 1:02d}", "ticker": ticker}
            for feature in feature_rows[0]:
                if feature not in {"signal_date", "ticker"}:
                    row[feature] = float(index + day * 0.1)
            reference.append(row)
    pd.DataFrame(reference).to_csv(phase23f / "phase23f_pilot_feature_panel.csv", index=False)

    periods = 35 if mature else 8
    for ticker in PILOT_UNIVERSE:
        frame = _prices(periods, open_gap=open_gap, invalid_ohlc=invalid_ohlc)
        if ticker == PILOT_UNIVERSE[0] and nonpositive_open:
            frame.loc[frame["date"].eq(pd.Timestamp("2026-06-15")), "open"] = 0.0
        frame.to_csv(data / f"{ticker}.csv", index=False)
    _prices(periods).to_csv(data / "benchmark_SPY.csv", index=False)

    ledger_rows = []
    if entered:
        for ticker in selected:
            ledger_rows.append(
                {
                    "session_date": "2026-06-14",
                    "selected_signal_date": signal_date,
                    "portfolio_id": "ridge_top5_equal_weight",
                    "ticker": ticker,
                    "session_state": "entered",
                    "simulated_fill_quantity": 201 if fill_mismatch and ticker == selected[0] else 200,
                    "simulated_fill_price": 100.0,
                }
            )
    pd.DataFrame(ledger_rows).to_csv(shadow / "immutable_session_ledger.csv", index=False)
    pd.DataFrame(
        [{"ticker": selected[0], "market_value": 20000.0}] if entered else []
    ).to_csv(shadow / "positions.csv", index=False)
    pd.DataFrame(
        [{"cash_balance": -5.0 if negative_cash else 100000.0}]
    ).to_csv(shadow / "cash_ledger.csv", index=False)
    pd.DataFrame([{"portfolio_value": 100000.0, "cash_balance": 100000.0}]).to_csv(
        shadow / "valuation_history.csv", index=False
    )
    return {
        "phase23k_prospective_monitoring": {
            "enabled": True,
            "output_dir": str(reports / "phase23k"),
            "dashboard_status_path": str(reports / "dashboard" / "phase23k.csv"),
            "source_phase23j_dir": str(phase23j),
            "source_phase23i_shadow_dir": str(shadow),
            "source_phase23f_dir": str(phase23f),
            "combined_input_dir": str(data),
            "post_endpoint_input_dir": str(data),
            "pilot_input_dir": str(data),
            "minimum_sessions_for_drift_warning": 8,
            "expected_universe_size": 16,
            "selected_count": 5,
            "negative_cash_tolerance": 0.01,
        }
    }


def _run(tmp_path: Path, **kwargs):
    config = _write_sources(tmp_path, **kwargs)
    return save_phase23k_prospective_shadow_monitoring(config=config, reports_dir=tmp_path / "reports")


def test_deterministic_session_id_is_stable() -> None:
    first = deterministic_session_id(
        candidate_system_id="a",
        model_id="b",
        model_hash="c",
        signal_date="2026-06-12",
        decision_cadence="weekly",
    )
    second = deterministic_session_id(
        candidate_system_id="a",
        model_id="b",
        model_hash="c",
        signal_date="2026-06-12",
        decision_cadence="weekly",
    )
    assert first == second


def test_zero_session_run_writes_empty_reports(tmp_path: Path) -> None:
    outputs = _run(tmp_path, ranking=False)
    assert outputs["summary"].iloc[0]["phase23k_decision"] == "phase23k_monitoring_written_no_current_session"
    assert outputs["full_ranking_snapshots"].empty


def test_blocked_proposal_is_recorded(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert outputs["session_registry"].iloc[0]["proposal_status"] == "proposal_blocked"
    assert outputs["order_execution_reconciliation"]["fill_validation_status"].str.contains("missing|pending").any()


def test_ready_proposal_is_recorded(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True)
    assert outputs["session_registry"].iloc[0]["proposal_status"] == "proposal_ready"


def test_entered_session_is_recorded(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, entered=True)
    assert outputs["session_registry"].iloc[0]["execution_status"] == "entered"


def test_rerun_same_session_does_not_duplicate_snapshot_rows(tmp_path: Path) -> None:
    _run(tmp_path)
    outputs = save_phase23k_prospective_shadow_monitoring(
        config=_write_sources(tmp_path), reports_dir=tmp_path / "reports"
    )
    assert len(outputs["full_ranking_snapshots"]) == 16


def test_conflicting_immutable_session_content_blocks(tmp_path: Path) -> None:
    _run(tmp_path)
    config = _write_sources(tmp_path)
    ranking_path = Path(config["phase23k_prospective_monitoring"]["source_phase23j_dir"]) / "phase23j_current_ranking.csv"
    ranking = pd.read_csv(ranking_path)
    ranking.loc[0, "predicted_rank"] = 16
    ranking.to_csv(ranking_path, index=False)
    outputs = save_phase23k_prospective_shadow_monitoring(config=config, reports_dir=tmp_path / "reports")
    assert "immutable_session_content_changed" in set(outputs["incident_log"]["category"])


def test_correct_model_hash_passes(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert bool(outputs["summary"].iloc[0]["model_hash_verified"])


def test_incorrect_model_hash_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, wrong_hash=True)
    assert "model_hash_mismatch" in set(outputs["incident_log"]["category"])


def test_changed_universe_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, changed_universe=True)
    assert "changed_universe" in set(outputs["incident_log"]["category"])


def test_ranking_snapshot_preserves_all_sixteen_securities(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert len(outputs["full_ranking_snapshots"]) == 16


def test_exactly_five_selected_flags_and_weights(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    selected = outputs["full_ranking_snapshots"].loc[outputs["full_ranking_snapshots"]["selected_flag"]]
    assert len(selected) == 5
    assert selected["target_weight"].eq(0.2).all()


def test_missing_opening_price_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert "missing_execution_price" in set(outputs["incident_log"]["category"])


def test_nonpositive_opening_price_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, nonpositive_open=True)
    assert "invalid_execution_price" in set(outputs["incident_log"]["category"])


def test_invalid_ohlc_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, invalid_ohlc=True)
    assert "invalid_ohlc" in set(outputs["incident_log"]["category"])


def test_gap_above_warning_creates_warning_without_order_change(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, open_gap=0.03)
    recon = outputs["order_execution_reconciliation"]
    assert recon["gap_warning_flag"].any()
    assert recon["approved_quantity"].eq(200).all()


def test_gap_above_severe_creates_severe_warning(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, open_gap=0.06)
    assert outputs["order_execution_reconciliation"]["gap_severe_flag"].any()


def test_expected_date_can_exist_before_observed_date(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    recon = outputs["order_execution_reconciliation"]
    assert recon["expected_execution_date"].eq("2026-06-15").all()
    assert recon["observed_execution_date"].fillna("").eq("").all()


def test_observed_date_requires_real_row(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True)
    assert outputs["order_execution_reconciliation"]["observed_execution_date"].eq("2026-06-15").all()


def test_fill_quantity_mismatch_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, entered=True, fill_mismatch=True)
    assert "order_fill_mismatch" in set(outputs["incident_log"]["category"])


def test_correct_delta_order_reconciles(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, entered=True)
    assert not outputs["order_execution_reconciliation"]["blocking_reason"].astype(str).str.contains("mismatch").any()


def test_positions_and_cash_are_monitored_from_phase23i_sources(tmp_path: Path) -> None:
    outputs = _run(tmp_path, execution_available=True, entered=True)
    assert "source_path" in outputs["position_history"].columns
    assert "source_path" in outputs["cash_history"].columns


def test_negative_cash_outside_tolerance_blocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, negative_cash=True)
    assert "negative_cash" in set(outputs["incident_log"]["category"])


def test_no_ic_before_twenty_trading_days(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert outputs["prospective_ic_history"].empty
    assert outputs["prediction_maturity_registry"]["maturity_status"].eq("prediction_pending").all()


def test_maturity_uses_trading_days_not_calendar_days() -> None:
    frame = _prices(35)
    assert trading_horizon_end_date(
        signal_date="2026-06-12",
        price_frame=frame,
        horizon_trading_days=20,
    ) == pd.Timestamp("2026-07-10")


def test_matured_outcomes_preserve_all_sixteen_stocks(tmp_path: Path) -> None:
    outputs = _run(tmp_path, mature=True)
    assert len(outputs["matured_cross_sectional_outcomes"]) == 16


def test_ic_uses_complete_cross_section(tmp_path: Path) -> None:
    outputs = _run(tmp_path, mature=True)
    assert outputs["prospective_ic_history"].iloc[0]["security_count"] == 16


def test_ic_reports_insufficient_variation_for_constant_realised_outcomes(tmp_path: Path) -> None:
    outputs = _run(tmp_path, mature=True)
    row = outputs["prospective_ic_history"].iloc[0]
    assert pd.isna(row["spearman_ic"])
    assert row["status"] == "insufficient_cross_sectional_variation"


def test_ic_reports_insufficient_variation_for_constant_model_scores(tmp_path: Path) -> None:
    config = _write_sources(tmp_path, mature=True)
    ranking_path = Path(config["phase23k_prospective_monitoring"]["source_phase23j_dir"]) / "phase23j_current_ranking.csv"
    ranking = pd.read_csv(ranking_path)
    ranking["predicted_20d_excess_return_or_ranking_score"] = 1.0
    ranking.to_csv(ranking_path, index=False)

    outputs = save_phase23k_prospective_shadow_monitoring(config=config, reports_dir=tmp_path / "reports")
    row = outputs["prospective_ic_history"].iloc[0]
    assert pd.isna(row["spearman_ic"])
    assert row["status"] == "insufficient_cross_sectional_variation"


def test_top_minus_bottom_spread_is_calculated(tmp_path: Path) -> None:
    outputs = _run(tmp_path, mature=True)
    assert pd.notna(outputs["prospective_spread_history"].iloc[0]["top_minus_bottom_spread"])


def test_feature_drift_is_descriptive_before_eight_sessions(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert outputs["feature_drift_report"]["drift_status"].eq("descriptive_only").all()


def test_score_drift_report_is_written(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    assert not outputs["score_drift_report"].empty


def test_concentration_warning_does_not_change_target_weights(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    selected = outputs["full_ranking_snapshots"].loc[outputs["full_ranking_snapshots"]["selected_flag"]]
    assert selected["target_weight"].eq(0.2).all()


def test_incident_log_dedupes_same_incident(tmp_path: Path) -> None:
    _run(tmp_path)
    outputs = save_phase23k_prospective_shadow_monitoring(
        config=_write_sources(tmp_path), reports_dir=tmp_path / "reports"
    )
    assert not outputs["incident_log"]["incident_id"].duplicated().any()


def test_safety_flags_remain_false(tmp_path: Path) -> None:
    outputs = _run(tmp_path)
    summary = outputs["summary"].iloc[0]
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])
