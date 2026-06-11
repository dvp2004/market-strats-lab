from pathlib import Path

import pandas as pd

import market_strats.run_backtest as run_backtest


def _daily_config(tmp_path: Path) -> dict:
    tracking_dir = tmp_path / "reports" / "paper_trading" / "regime_informed_tracking"
    dashboard_dir = tmp_path / "reports" / "paper_trading" / "dashboard"
    return {
        "daily_paper_runner": {
            "enabled": True,
            "output_dir": str(dashboard_dir),
            "regime_informed_tracking_dir": str(tracking_dir),
            "run_heavy_research_modules": False,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        "phase15wxyz_fresh_extension_pipeline": {"enabled": False},
        "phase18a_paper_signal_operational_hardening": {"enabled": True},
        "phase20b_finalist_dynamic_allocation": {"enabled": True},
        "phase21c_regime_informed_paper_tracking": {"enabled": True},
        "phase21d_regime_informed_adoption": {"enabled": True},
        "phase21e_regime_informed_session_ingestion": {"enabled": True},
        "phase17a_strategy_factory": {"enabled": True},
        "phase19a_strategy_factory_multiverse": {"enabled": True},
        "phase21a_historical_regime_stress_lab": {"enabled": True},
    }


def _write_minimal_daily_sources(tmp_path: Path) -> None:
    tracking_dir = tmp_path / "reports" / "paper_trading" / "regime_informed_tracking"
    dashboard_dir = tmp_path / "reports" / "paper_trading" / "dashboard"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "asset": "SPY",
                "target_weight": 1.0,
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_paper_targets.csv", index=False)
    pd.DataFrame(
        [
            {"key": "selected_signal_date", "value": "2026-06-08"},
            {"key": "warnings_present", "value": "True"},
            {"key": "blocking_symbols", "value": "none"},
        ]
    ).to_csv(
        tracking_dir / "regime_informed_daily_tracking_tear_sheet.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "selected_signal_date": "2026-06-08",
                "adoption_status": "regime_informed_shortlist_adopted_manual_paper_only",
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_active_tracking_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "selected_signal_date": "2026-06-08",
                "validation_status": "valid_manual_paper_session",
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_session_validation.csv", index=False)
    pd.DataFrame(
        [
            {
                "phase21e_decision": "regime_informed_session_ingested_valid_manual_paper_only"
            }
        ]
    ).to_csv(dashboard_dir / "regime_informed_session_ingestion_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "manual_decision": "skip_due_warning",
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_manual_session_ledger.csv", index=False)


def test_daily_paper_only_cli_flag_is_available():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    assert "--daily-paper-only" in source
    assert "_run_daily_paper_workflow(config=config, reports_dir=reports_dir)" in source


def test_daily_runtime_status_csv_is_written(tmp_path):
    _write_minimal_daily_sources(tmp_path)
    config = _daily_config(tmp_path)

    outputs = run_backtest._write_daily_runtime_status(
        config=config,
        reports_dir=tmp_path / "reports",
        modules_run=["phase18a", "phase20b", "phase21c", "phase21d", "phase21e"],
        modules_skipped=["phase19a_multiverse", "phase21a_regime_stress"],
        runtime_seconds=1.234,
    )

    status = pd.read_csv(outputs["runtime_status_csv"])
    assert status.loc[0, "daily_paper_status"] == (
        "daily_paper_workflow_completed_manual_paper_only"
    )
    assert status.loc[0, "daily_paper_only"]
    assert not status.loc[0, "live_trading_allowed"]
    assert not status.loc[0, "real_money_allowed"]
    assert not status.loc[0, "broker_api_integration_allowed"]
    assert not status.loc[0, "promotion_allowed"]


def test_daily_paper_runner_skips_heavy_research_phases(monkeypatch, tmp_path):
    _write_minimal_daily_sources(tmp_path)
    config = _daily_config(tmp_path)
    calls: list[str] = []

    def fail_if_called(**_kwargs):
        raise AssertionError("heavy research phase should not run")

    monkeypatch.setattr(run_backtest, "save_phase17a_strategy_factory_report", fail_if_called)
    monkeypatch.setattr(
        run_backtest, "save_phase19a_strategy_factory_multiverse", fail_if_called
    )
    monkeypatch.setattr(run_backtest, "save_phase21a_historical_regime_stress_lab", fail_if_called)

    def phase15_chain(**_kwargs):
        calls.append("phase15q")
        return {"phase15q": {}}

    def phase18a(**_kwargs):
        calls.append("phase18a")
        return {}

    def phase20b(**_kwargs):
        calls.append("phase20b")
        return {}

    def phase21c(**_kwargs):
        calls.append("phase21c")
        return {}

    def phase21d(**_kwargs):
        calls.append("phase21d")
        return {}

    def phase21e(**_kwargs):
        calls.append("phase21e")
        return {}

    monkeypatch.setattr(run_backtest, "_run_daily_phase15_operational_chain", phase15_chain)
    monkeypatch.setattr(
        run_backtest, "save_phase18a_paper_signal_operational_hardening", phase18a
    )
    monkeypatch.setattr(run_backtest, "save_phase20b_finalist_dynamic_allocation", phase20b)
    monkeypatch.setattr(run_backtest, "_run_phase21c_regime_informed_paper_tracking", phase21c)
    monkeypatch.setattr(run_backtest, "_run_phase21d_regime_informed_adoption", phase21d)
    monkeypatch.setattr(
        run_backtest, "_run_phase21e_regime_informed_session_ingestion", phase21e
    )

    outputs = run_backtest._run_daily_paper_workflow(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    assert calls == ["phase15q", "phase18a", "phase20b", "phase21c", "phase21d", "phase21e"]
    status = pd.read_csv(outputs["runtime_status_csv"])
    assert "phase19a_multiverse" in status.loc[0, "modules_skipped"]
    assert "phase21a_regime_stress" in status.loc[0, "modules_skipped"]
    assert "phase17_strategy_factory" in status.loc[0, "modules_skipped"]
