from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_dry_run_preregistration import (
    DASHBOARD_PANELS,
    save_phase16a_paper_dry_run_preregistration,
)


def _base_config(tmp_path: Path, **overrides) -> dict:
    output_dir = tmp_path / "reports" / "paper_trading"
    dashboard_dir = output_dir / "dashboard"
    decision_path = tmp_path / "reports" / "phase15n_decision.csv"
    signal_path = tmp_path / "reports" / "phase15m_signal.csv"
    section = {
        "enabled": True,
        "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
        "required_upstream_decision": "paper_dry_run_preregistration_allowed_next",
        "paper_account_only": True,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "paper_notional_usd": 10000,
        "output_dir": str(output_dir),
        "dashboard_dir": str(dashboard_dir),
        "phase15n_reports": {
            "decision_report": str(decision_path),
        },
        "phase15m_reports": {
            "current_signal_file": str(signal_path),
        },
    }
    section.update(overrides)
    return {"phase16a_paper_dry_run_preregistration": section}


def _decision_path(config: dict) -> Path:
    return Path(
        config["phase16a_paper_dry_run_preregistration"]["phase15n_reports"][
            "decision_report"
        ]
    )


def _signal_path(config: dict) -> Path:
    return Path(
        config["phase16a_paper_dry_run_preregistration"]["phase15m_reports"][
            "current_signal_file"
        ]
    )


def _write_phase15n_decision(
    config: dict,
    *,
    decision: str = "paper_dry_run_preregistration_allowed_next",
    allowed: bool = True,
    live: bool = False,
    real_money: bool = False,
    broker: bool = False,
) -> None:
    path = _decision_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "decision": decision,
                "paper_dry_run_preregistration_allowed_next": allowed,
                "paper_trading_ready": False,
                "broker_api_integration_allowed": broker,
                "paper_trading_deployment_allowed": False,
                "live_trading_allowed": live,
                "real_money_allowed": real_money,
                "failure_reason": "",
            }
        ]
    ).to_csv(path, index=False)


def _write_phase15m_signal(
    config: dict,
    *,
    mode: str = "offensive_spy",
    exposure: float = 1.0,
    action: str = "risk_on_hold_preview",
) -> None:
    path = _signal_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "signal_date": "2026-06-02",
                "data_as_of_date": "2026-06-02",
                "generated_at_utc": "2026-06-07T15:55:42+00:00",
                "candidate_system_id": "phase6b_loose_relief_execution_realistic_overlay",
                "current_mode": mode,
                "previous_mode": mode,
                "current_exposure": exposure,
                "previous_exposure": exposure,
                "target_action": action,
                "switch_triggered": False,
                "blocking_warnings": "",
            }
        ]
    ).to_csv(path, index=False)


def test_phase16a_allowed_case_creates_latest_signal_and_order_preview(tmp_path):
    config = _base_config(tmp_path)
    _write_phase15n_decision(config)
    _write_phase15m_signal(config)

    outputs = save_phase16a_paper_dry_run_preregistration(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    latest = outputs["latest_signal"].iloc[0]
    order = outputs["paper_orders_preview"].iloc[0]
    conclusion = outputs["conclusion"].iloc[0]

    assert bool(conclusion["all_gates_passed"])
    assert bool(latest["paper_dry_run_allowed"])
    assert latest["current_mode"] == "offensive_spy"
    assert float(latest["current_exposure"]) == 1.0
    assert latest["target_action"] == "risk_on_hold_preview"
    assert order["symbol"] == "SPY"
    assert float(order["target_weight"]) == 1.0
    assert float(order["target_notional_usd"]) == 10000
    assert order["order_action"] == "PAPER_TARGET_WEIGHT_ONLY"
    assert order["execution_instruction"] == "manual_paper_trade_only"

    output_dir = Path(
        config["phase16a_paper_dry_run_preregistration"]["output_dir"]
    )
    assert (output_dir / "latest_signal.csv").exists()
    assert (output_dir / "latest_signal.md").exists()
    assert (output_dir / "paper_orders_preview.csv").exists()


def test_phase16a_blocked_15n_decision_fails_closed(tmp_path):
    config = _base_config(tmp_path)
    _write_phase15n_decision(
        config,
        decision="blocked_fresh_signal_audit_failed",
        allowed=False,
    )
    _write_phase15m_signal(config)

    outputs = save_phase16a_paper_dry_run_preregistration(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    latest = outputs["latest_signal"].iloc[0]
    order = outputs["paper_orders_preview"].iloc[0]
    conclusion = outputs["conclusion"].iloc[0]

    assert not bool(conclusion["all_gates_passed"])
    assert not bool(latest["paper_dry_run_allowed"])
    assert not bool(latest["live_trading_allowed"])
    assert not bool(latest["real_money_allowed"])
    assert not bool(latest["broker_api_integration_allowed"])
    assert order["order_action"] == "PAPER_NO_ORDER_BLOCKED"
    assert "phase15n_required_decision" in conclusion["failure_reason"]
    assert "phase15n_preregistration_allowed" in conclusion["failure_reason"]


def test_phase16a_missing_15m_signal_fails_closed(tmp_path):
    config = _base_config(tmp_path)
    _write_phase15n_decision(config)

    outputs = save_phase16a_paper_dry_run_preregistration(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    latest = outputs["latest_signal"].iloc[0]
    conclusion = outputs["conclusion"].iloc[0]

    assert not bool(conclusion["all_gates_passed"])
    assert not bool(latest["paper_dry_run_allowed"])
    assert latest["readiness_status"] == "blocked_paper_dry_run_preregistration"
    assert "phase15m_current_signal_present" in conclusion["failure_reason"]
    assert "latest_signal_required_fields_present" in conclusion["failure_reason"]


def test_phase16a_live_real_money_and_broker_flags_fail_closed(tmp_path):
    config = _base_config(
        tmp_path,
        live_trading_allowed=True,
        real_money_allowed=True,
        broker_api_integration_allowed=True,
    )
    _write_phase15n_decision(config, live=True, real_money=True, broker=True)
    _write_phase15m_signal(config)

    outputs = save_phase16a_paper_dry_run_preregistration(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    latest = outputs["latest_signal"].iloc[0]
    readiness = outputs["paper_trading_readiness_status"].iloc[0]
    conclusion = outputs["conclusion"].iloc[0]

    assert not bool(conclusion["all_gates_passed"])
    assert not bool(latest["live_trading_allowed"])
    assert not bool(latest["real_money_allowed"])
    assert not bool(latest["broker_api_integration_allowed"])
    assert not bool(readiness["live_trading_allowed"])
    assert not bool(readiness["real_money_allowed"])
    assert not bool(readiness["broker_api_integration_allowed"])
    assert "config_live_trading_disabled" in conclusion["failure_reason"]
    assert "upstream_broker_api_disabled" in conclusion["failure_reason"]


def test_phase16a_dashboard_manifest_is_created(tmp_path):
    config = _base_config(tmp_path)
    _write_phase15n_decision(config)
    _write_phase15m_signal(config)

    outputs = save_phase16a_paper_dry_run_preregistration(
        config=config,
        reports_dir=tmp_path / "reports",
    )

    manifest = outputs["dashboard_manifest"]
    dashboard_dir = Path(
        config["phase16a_paper_dry_run_preregistration"]["dashboard_dir"]
    )

    assert set(manifest["panel_id"]) == set(DASHBOARD_PANELS)
    assert (dashboard_dir / "dashboard_manifest.csv").exists()
    assert (dashboard_dir / "index.md").exists()
