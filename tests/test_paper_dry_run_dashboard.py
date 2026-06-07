from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_dry_run_dashboard import (
    save_phase16b_paper_dry_run_dashboard,
)


def _base_config(tmp_path: Path, *, visual_paths: dict[str, str] | None = None, **overrides) -> dict:
    reports_dir = tmp_path / "reports"
    output_dir = reports_dir / "paper_trading"
    dashboard_dir = output_dir / "dashboard"
    section = {
        "enabled": True,
        "output_dir": str(output_dir),
        "dashboard_dir": str(dashboard_dir),
        "paper_notional_usd": 10000,
        "use_latest_available_signal_date_when_audit_date_missing": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "source_files": {
            "latest_signal": str(output_dir / "latest_signal.csv"),
            "paper_orders_preview": str(output_dir / "paper_orders_preview.csv"),
            "paper_trading_readiness_status": str(
                output_dir / "paper_trading_readiness_status.csv"
            ),
            "wxyz_fresh_handoff": str(tmp_path / "data" / "fresh" / "phase15q_rule_generated_candidate_stream.csv"),
            "switch_event_log": str(
                reports_dir / "phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv"
            ),
        },
        "visual_artifacts": visual_paths or {},
    }
    section.update(overrides)
    return {
        "phase15m_fresh_current_signal_generation": {
            "audit_current_date": "2026-06-02",
        },
        "phase16b_paper_dry_run_dashboard": section,
    }


def _section(config: dict) -> dict:
    return config["phase16b_paper_dry_run_dashboard"]


def _write_phase16a_outputs(config: dict, *, allowed: bool = True, live: bool = False) -> None:
    output_dir = Path(_section(config)["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "signal_date": "2026-06-02",
                "data_as_of_date": "2026-06-02",
                "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "current_mode": "offensive_spy",
                "current_exposure": 1.0,
                "target_action": "risk_on_hold_preview",
                "switch_triggered": False,
                "paper_dry_run_allowed": allowed,
                "paper_account_only": True,
                "live_trading_allowed": live,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "readiness_status": "paper_dry_run_preregistered_manual_preview_only",
                "blocking_warnings": "",
                "generated_at_utc": "2026-06-07T20:45:40+00:00",
            }
        ]
    ).to_csv(output_dir / "latest_signal.csv", index=False)
    pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "target_weight": 1.0,
                "paper_notional_usd": 10000,
                "target_notional_usd": 10000,
                "order_action": "PAPER_TARGET_WEIGHT_ONLY",
                "execution_instruction": "manual_paper_trade_only",
                "order_placement_attempted": False,
                "preview_only": True,
                "paper_account_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "readiness_status": "paper_dry_run_preregistered_manual_preview_only",
                "blocking_warnings": "",
            }
        ]
    ).to_csv(output_dir / "paper_orders_preview.csv", index=False)
    pd.DataFrame(
        [
            {
                "phase": "Phase 16A",
                "paper_dry_run_preregistration_allowed": allowed,
                "paper_account_only": True,
                "paper_trading_ready": False,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "order_placement_attempted": False,
                "readiness_status": "paper_dry_run_preregistered_manual_preview_only",
            }
        ]
    ).to_csv(output_dir / "paper_trading_readiness_status.csv", index=False)


def _write_fresh_and_switch_sources(config: dict) -> None:
    fresh_path = Path(_section(config)["source_files"]["wxyz_fresh_handoff"])
    fresh_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-06-02",
                "SPY_close": 600.0,
                "SPY_return": 0.001,
                "target_offensive_weight": 1.0,
            },
            {
                "date": "2026-06-05",
                "SPY_close": 603.0,
                "SPY_return": 0.002,
                "target_offensive_weight": 1.0,
            },
        ]
    ).to_csv(fresh_path, index=False)

    switch_path = Path(_section(config)["source_files"]["switch_event_log"])
    switch_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "switch_event_id": 36,
                "decision_date": "2026-04-13",
                "previous_mode": "defensive_or_cash",
                "current_mode": "offensive_spy",
                "previous_exposure": 0.0,
                "current_exposure": 1.0,
            }
        ]
    ).to_csv(switch_path, index=False)


def _write_visual_sources(tmp_path: Path) -> dict[str, str]:
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    dates = ["2026-06-01", "2026-06-02"]
    paths = {
        "equity_curve": visual_dir / "equity.csv",
        "drawdown_curve": visual_dir / "drawdown.csv",
        "exposure_timeline": visual_dir / "exposure.csv",
        "rolling_relative_performance": visual_dir / "rolling.csv",
    }
    pd.DataFrame(
        {
            "decision_date": dates,
            "candidate_equity": [10000, 10050],
            "benchmark_equity": [10000, 10025],
        }
    ).to_csv(paths["equity_curve"], index=False)
    pd.DataFrame(
        {
            "decision_date": dates,
            "candidate_drawdown": [0.0, -0.01],
            "benchmark_drawdown": [0.0, -0.02],
        }
    ).to_csv(paths["drawdown_curve"], index=False)
    pd.DataFrame(
        {
            "decision_date": dates,
            "exposure": [1.0, 1.0],
            "mode": ["offensive_spy", "offensive_spy"],
        }
    ).to_csv(paths["exposure_timeline"], index=False)
    pd.DataFrame(
        {
            "decision_date": dates,
            "rolling_relative_return": [0.0, 0.01],
        }
    ).to_csv(paths["rolling_relative_performance"], index=False)
    return {key: str(path) for key, path in paths.items()}


def test_phase16b_allowed_case_creates_dashboard_csvs_and_pngs(tmp_path):
    config = _base_config(tmp_path, visual_paths=_write_visual_sources(tmp_path))
    _write_phase16a_outputs(config)
    _write_fresh_and_switch_sources(config)

    outputs = save_phase16b_paper_dry_run_dashboard(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    dashboard_dir = Path(_section(config)["dashboard_dir"])
    output_dir = Path(_section(config)["output_dir"])
    assert bool(outputs["conclusion"].iloc[0]["all_gates_passed"])
    assert bool(outputs["summary"].iloc[0]["charts_complete"])
    for name in [
        "current_signal_state.csv",
        "paper_orders_preview.csv",
        "data_freshness.csv",
        "latest_switch_event.csv",
        "stop_condition_status.csv",
        "equity_curve.csv",
        "drawdown_curve.csv",
        "exposure_timeline.csv",
        "rolling_relative_performance.csv",
        "paper_equity_curve.png",
        "paper_drawdown_curve.png",
        "paper_exposure_timeline.png",
        "paper_rolling_relative_performance.png",
        "index.md",
    ]:
        assert (dashboard_dir / name).exists()
    assert (output_dir / "paper_signal_history.csv").exists()
    assert (output_dir / "paper_journal.csv").exists()
    assert (output_dir / "paper_portfolio_state.csv").exists()


def test_phase16b_blocked_latest_signal_fails_closed(tmp_path):
    config = _base_config(tmp_path, visual_paths=_write_visual_sources(tmp_path))
    _write_fresh_and_switch_sources(config)
    output_dir = Path(_section(config)["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"order_action": "PAPER_TARGET_WEIGHT_ONLY"}]).to_csv(
        output_dir / "paper_orders_preview.csv",
        index=False,
    )

    outputs = save_phase16b_paper_dry_run_dashboard(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    conclusion = outputs["conclusion"].iloc[0]
    stops = outputs["stop_condition_status"]
    assert not bool(conclusion["all_gates_passed"])
    assert "latest_signal_present" in conclusion["failure_reason"]
    assert bool(stops.loc[stops["stop_id"] == "latest_signal_missing", "triggered"].iloc[0])


def test_phase16b_duplicate_signal_history_rows_are_not_created(tmp_path):
    config = _base_config(tmp_path, visual_paths=_write_visual_sources(tmp_path))
    _write_phase16a_outputs(config)
    _write_fresh_and_switch_sources(config)
    output_dir = Path(_section(config)["output_dir"])
    existing = pd.read_csv(output_dir / "latest_signal.csv")
    existing.to_csv(output_dir / "paper_signal_history.csv", index=False)

    outputs = save_phase16b_paper_dry_run_dashboard(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    assert len(outputs["paper_signal_history"]) == 1


def test_phase16b_stop_condition_status_catches_live_real_money_broker_flags(tmp_path):
    config = _base_config(
        tmp_path,
        visual_paths=_write_visual_sources(tmp_path),
        live_trading_allowed=True,
        real_money_allowed=True,
        broker_api_integration_allowed=True,
    )
    _write_phase16a_outputs(config)
    _write_fresh_and_switch_sources(config)

    outputs = save_phase16b_paper_dry_run_dashboard(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    stops = outputs["stop_condition_status"].set_index("stop_id")
    assert bool(stops.loc["live_trading_flag_true", "triggered"])
    assert bool(stops.loc["real_money_flag_true", "triggered"])
    assert bool(stops.loc["broker_api_flag_true", "triggered"])
    assert not bool(outputs["conclusion"].iloc[0]["all_gates_passed"])


def test_phase16b_missing_visual_csvs_create_placeholders_without_chart_success(tmp_path):
    config = _base_config(tmp_path)
    _write_phase16a_outputs(config)
    _write_fresh_and_switch_sources(config)

    outputs = save_phase16b_paper_dry_run_dashboard(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    dashboard_dir = Path(_section(config)["dashboard_dir"])
    assert not bool(outputs["summary"].iloc[0]["charts_complete"])
    assert bool(outputs["equity_curve"].iloc[0]["placeholder"])
    assert (dashboard_dir / "equity_curve.csv").exists()
    assert (dashboard_dir / "paper_equity_curve.png").exists()
