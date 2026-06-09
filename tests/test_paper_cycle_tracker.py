from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_cycle_tracker import (
    build_current_cycle_row,
    build_runbook_markdown,
    build_streak_report,
    build_warning_block_history,
    save_phase18b_paper_cycle_tracker,
    update_cycle_history,
)


PHASE18B = "phase18b_paper_cycle_tracker"
FINAL_WARNING_ACTION = "WARNINGS PRESENT — MANUAL REVIEW BEFORE PAPER ENTRY"
FINAL_CLEAN_ACTION = "NO BLOCKING ISSUES — MANUAL PAPER PREVIEW ONLY"
FINAL_BLOCK_ACTION = "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE"


def _tear_sheet(*, warnings: str = "BTC-USD", blocks: str = "none") -> pd.DataFrame:
    status = "blocked" if blocks != "none" else "warning" if warnings != "none" else "passed"
    final_action = (
        FINAL_BLOCK_ACTION
        if blocks != "none"
        else FINAL_WARNING_ACTION
        if warnings != "none"
        else FINAL_CLEAN_ACTION
    )
    return pd.DataFrame(
        [
            {"category": "signal_date_policy", "key": "selected_signal_date", "value": "2026-06-08"},
            {"category": "signal_date_policy", "key": "data_as_of_date", "value": "2026-06-08"},
            {
                "category": "fresh_data_quality",
                "key": "fresh_data_quality_status",
                "value": status,
            },
            {
                "category": "fresh_data_quality",
                "key": "symbols_with_warnings",
                "value": warnings,
            },
            {
                "category": "fresh_data_quality",
                "key": "symbols_with_blocking_failures",
                "value": blocks,
            },
            {
                "category": "baseline_phase6_signal",
                "key": "baseline_paper_action",
                "value": "risk_on_hold_preview",
            },
            {
                "category": "watchlist_preview",
                "key": "nonzero_watchlist_preview_orders",
                "value": "sf_spy_qqq_60_40_monthly_rebalanced: SPY target_weight=60.00%",
            },
            {
                "category": "manual_journal",
                "key": "manual_journal_status",
                "value": "not_entered:2",
            },
            {"category": "safety_flags", "key": "live_trading_allowed", "value": "False"},
            {"category": "safety_flags", "key": "real_money_allowed", "value": "False"},
            {
                "category": "safety_flags",
                "key": "broker_api_integration_allowed",
                "value": "False",
            },
            {
                "category": "readiness",
                "key": "recurring_paper_trading_ready",
                "value": "False",
            },
            {
                "category": "final_action",
                "key": "final_recommended_manual_action",
                "value": final_action,
            },
        ]
    )


def _phase18a_conclusion(*, passed: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "decision": (
                    "paper_signal_operational_hardening_completed_manual_preview_only"
                    if passed
                    else "paper_signal_operational_hardening_failed_closed"
                ),
                "all_gates_passed": passed,
                "recurring_paper_trading_ready": False,
            }
        ]
    )


def _quality(*, warnings: str = "btc_weekend_data_available_common_date_caveat", blocks: str = "") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "SPY", "warnings": "", "blocking_failures": "", "quality_status": "passed"},
            {
                "symbol": "BTC-USD",
                "warnings": warnings,
                "blocking_failures": blocks,
                "quality_status": "blocked" if blocks else "warning" if warnings else "passed",
            },
        ]
    )


def _journal(statuses: list[str] | None = None) -> pd.DataFrame:
    statuses = statuses or ["not_entered", "not_entered"]
    return pd.DataFrame({"manual_execution_status": statuses})


def _config(tmp_path: Path) -> dict:
    return {
        PHASE18B: {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "paper_trading" / "cycle_tracker"),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "source_operational_hardening_dir": str(
                tmp_path / "reports" / "paper_trading" / "operational_hardening"
            ),
            "required_consecutive_clean_cycles": 10,
            "allow_warning_cycles_for_readiness": False,
            "require_manual_journal_entries": False,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def _write_phase18a_fixture(
    tmp_path: Path,
    *,
    warnings: str = "BTC-USD",
    blocks: str = "none",
) -> Path:
    phase18a_dir = tmp_path / "reports" / "paper_trading" / "operational_hardening"
    phase18a_dir.mkdir(parents=True, exist_ok=True)
    _tear_sheet(warnings=warnings, blocks=blocks).to_csv(
        phase18a_dir / "daily_execution_tear_sheet.csv",
        index=False,
    )
    (phase18a_dir / "daily_execution_tear_sheet.md").write_text(
        "# Tear Sheet\n\nNO LIVE TRADING\nNO REAL MONEY\nNO BROKER/API\nMANUAL PAPER PREVIEW ONLY\n",
        encoding="utf-8",
    )
    _phase18a_conclusion(passed=blocks == "none").to_csv(
        phase18a_dir / "phase18a_conclusion.csv",
        index=False,
    )
    _quality(
        warnings="btc_weekend_data_available_common_date_caveat" if warnings != "none" else "",
        blocks="daily_return_outlier_block" if blocks != "none" else "",
    ).to_csv(phase18a_dir / "fresh_data_quality_report.csv", index=False)
    _journal().to_csv(phase18a_dir / "manual_execution_journal_template.csv", index=False)
    return phase18a_dir


def _cycle_row(*, clean: bool, warning: bool = False, blocked: bool = False, day: int = 1) -> dict:
    return {
        "cycle_date": f"2026-06-{day:02d}",
        "selected_signal_date": f"2026-06-{day:02d}",
        "data_as_of_date": f"2026-06-{day:02d}",
        "clean_cycle": clean,
        "warning_cycle": warning,
        "blocked_cycle": blocked,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }


def test_cycle_history_is_created_from_phase18a_tear_sheet(tmp_path):
    _write_phase18a_fixture(tmp_path)

    outputs = save_phase18b_paper_cycle_tracker(config=_config(tmp_path), reports_dir=tmp_path / "reports")
    history = outputs["paper_cycle_history"]
    latest = outputs["paper_cycle_latest"].iloc[0]

    assert len(history) == 1
    assert latest["selected_signal_date"] == "2026-06-08"
    assert latest["data_as_of_date"] == "2026-06-08"
    assert latest["baseline_action"] == "risk_on_hold_preview"
    assert bool(latest["watchlist_preview_available"])


def test_same_cycle_is_deduped_not_duplicated(tmp_path):
    _write_phase18a_fixture(tmp_path)
    config = _config(tmp_path)
    reports_dir = tmp_path / "reports"

    save_phase18b_paper_cycle_tracker(config=config, reports_dir=reports_dir)
    outputs = save_phase18b_paper_cycle_tracker(config=config, reports_dir=reports_dir)

    assert len(outputs["paper_cycle_history"]) == 1


def test_warning_cycle_is_not_clean_when_warnings_exist():
    row = build_current_cycle_row(
        tear_sheet=_tear_sheet(warnings="BTC-USD", blocks="none"),
        phase18a_conclusion=_phase18a_conclusion(),
        data_quality=_quality(warnings="btc_weekend_data_available_common_date_caveat"),
        manual_journal_template=_journal(),
        tear_sheet_csv_available=True,
        tear_sheet_md_available=True,
        cycle_date="2026-06-09",
    )

    assert not row["clean_cycle"]
    assert row["warning_cycle"]
    assert not row["blocked_cycle"]


def test_blocked_cycle_is_not_clean_when_blocking_symbols_exist():
    row = build_current_cycle_row(
        tear_sheet=_tear_sheet(warnings="none", blocks="QQQ"),
        phase18a_conclusion=_phase18a_conclusion(passed=False),
        data_quality=_quality(warnings="", blocks="daily_return_outlier_block"),
        manual_journal_template=_journal(),
        tear_sheet_csv_available=True,
        tear_sheet_md_available=True,
        cycle_date="2026-06-09",
    )

    assert not row["clean_cycle"]
    assert not row["warning_cycle"]
    assert row["blocked_cycle"]


def test_clean_cycle_increments_streak():
    history = pd.DataFrame([_cycle_row(clean=True, day=day) for day in range(1, 4)])

    streak = build_streak_report(
        history=history,
        required_consecutive_clean_cycles=10,
        allow_warning_cycles_for_readiness=False,
        require_manual_journal_entries=False,
        manual_journal_entries_complete=True,
    )

    assert streak.iloc[0]["current_consecutive_clean_cycles"] == 3
    assert bool(streak.iloc[0]["latest_cycle_clean"])


def test_warning_cycle_blocks_streak_when_warnings_not_allowed():
    history = pd.DataFrame(
        [
            *[_cycle_row(clean=True, day=day) for day in range(1, 10)],
            _cycle_row(clean=False, warning=True, day=10),
        ]
    )

    streak = build_streak_report(
        history=history,
        required_consecutive_clean_cycles=10,
        allow_warning_cycles_for_readiness=False,
        require_manual_journal_entries=False,
        manual_journal_entries_complete=True,
    )
    row = streak.iloc[0]

    assert row["current_consecutive_clean_cycles"] == 0
    assert not bool(row["recurring_paper_readiness_candidate"])
    assert "latest_cycle_has_warning" in row["readiness_blocking_reasons"]


def test_readiness_remains_false_before_ten_clean_cycles():
    history = pd.DataFrame([_cycle_row(clean=True, day=day) for day in range(1, 10)])

    streak = build_streak_report(
        history=history,
        required_consecutive_clean_cycles=10,
        allow_warning_cycles_for_readiness=False,
        require_manual_journal_entries=False,
        manual_journal_entries_complete=True,
    )

    assert not bool(streak.iloc[0]["recurring_paper_readiness_candidate"])
    assert "insufficient_consecutive_clean_cycles" in streak.iloc[0]["readiness_blocking_reasons"]


def test_readiness_becomes_true_only_after_ten_clean_cycles_and_safety_flags_false():
    history = pd.DataFrame([_cycle_row(clean=True, day=day) for day in range(1, 11)])

    streak = build_streak_report(
        history=history,
        required_consecutive_clean_cycles=10,
        allow_warning_cycles_for_readiness=False,
        require_manual_journal_entries=False,
        manual_journal_entries_complete=True,
    )

    assert bool(streak.iloc[0]["recurring_paper_readiness_candidate"])
    assert streak.iloc[0]["readiness_blocking_reasons"] == ""


def test_runbook_includes_no_live_no_real_no_broker_language():
    runbook = build_runbook_markdown()

    assert "NO LIVE TRADING" in runbook
    assert "NO REAL MONEY" in runbook
    assert "NO BROKER/API" in runbook
    assert "MANUAL PAPER ONLY" in runbook


def test_warning_block_history_includes_btc_warning():
    cycle = _cycle_row(clean=False, warning=True)
    warning_history = build_warning_block_history(
        cycle_row=cycle,
        data_quality=_quality(warnings="btc_weekend_data_available_common_date_caveat"),
    )

    assert len(warning_history) == 1
    assert warning_history.iloc[0]["symbol"] == "BTC-USD"
    assert warning_history.iloc[0]["severity"] == "warning"
    assert (
        warning_history.iloc[0]["warning_or_block_reason"]
        == "btc_weekend_data_available_common_date_caveat"
    )


def test_update_cycle_history_replaces_same_cycle():
    existing = pd.DataFrame(
        [
            {
                **_cycle_row(clean=False, warning=True),
                "fresh_data_status": "warning",
            }
        ]
    )
    current = pd.DataFrame(
        [
            {
                **_cycle_row(clean=True),
                "fresh_data_status": "passed",
            }
        ]
    )

    history = update_cycle_history(existing_history=existing, current_cycle=current)

    assert len(history) == 1
    assert bool(history.iloc[0]["clean_cycle"])
    assert history.iloc[0]["fresh_data_status"] == "passed"
