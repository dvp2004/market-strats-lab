from pathlib import Path

import pandas as pd

from market_strats.analysis.paper_signal_operational_hardening import (
    DEFAULT_SYMBOLS,
    build_config_hash_report,
    build_daily_execution_tear_sheet,
    build_manual_execution_journal_template,
    build_signal_date_policy_report,
    build_watchlist_paper_preview,
    inspect_fresh_data_quality,
    save_phase18a_paper_signal_operational_hardening,
)


PHASE18A = "phase18a_paper_signal_operational_hardening"
WATCHLIST_CANDIDATES = [
    "sf_spy_qqq_60_40_monthly_rebalanced",
    "sf_spy_core_phase6_overlay_satellite_qqq",
    "sf_spy_qqq_btc_capped_offensive",
]
JOURNAL_COLUMNS = {
    "journal_date",
    "candidate_id",
    "asset",
    "target_weight",
    "target_notional_usd",
    "manual_execution_status",
    "paper_account_value",
    "paper_fill_price",
    "paper_fill_quantity",
    "deviation_from_preview",
    "notes",
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
}


def _base_config(tmp_path: Path, *, audit_date: str | None = "2026-06-02") -> dict:
    section = {
        "enabled": True,
        "output_dir": str(tmp_path / "reports" / "paper_trading" / "operational_hardening"),
        "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
        "use_latest_available_when_audit_date_missing": True,
        "allow_audit_date_override": True,
        "data_quality": {
            "etf_warning_abs_daily_return_pct": 10,
            "etf_block_abs_daily_return_pct": 15,
            "btc_warning_abs_daily_return_pct": 20,
            "btc_block_abs_daily_return_pct": 40,
            "require_positive_prices": True,
            "require_no_duplicate_dates": True,
            "require_latest_row_non_null": True,
            "require_high_low_volume_when_available": True,
        },
        "watchlist_preview": {
            "enabled": True,
            "paper_notional_usd": 10000,
            "include_candidates": WATCHLIST_CANDIDATES,
        },
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }
    config = {PHASE18A: section, "phase17a_strategy_factory": {"btc_max_weight": 0.10}}
    if audit_date is not None:
        config["phase15m_fresh_current_signal_generation"] = {
            "audit_current_date": audit_date
        }
    else:
        config["phase15m_fresh_current_signal_generation"] = {}
    return config


def _write_price_parquet(data_dir: Path, symbol: str, rows: list[tuple[str, float | None]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["date", "adj_close"])
    frame.to_parquet(data_dir / f"{symbol}.parquet", index=False)


def _watchlist_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": WATCHLIST_CANDIDATES,
            "watchlist_role": [
                "clean_growth_watchlist",
                "baseline_linked_growth_watchlist",
                "high_growth_high_caveat_watchlist",
            ],
            "promotion_allowed": [False, False, False],
            "paper_watchlist_only": [True, True, True],
        }
    )


def _latest_allocations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_id": "sf_spy_qqq_60_40_monthly_rebalanced",
                "allocation_date": "2026-06-05",
                "asset": "SPY",
                "weight": 0.60,
            },
            {
                "strategy_id": "sf_spy_qqq_60_40_monthly_rebalanced",
                "allocation_date": "2026-06-05",
                "asset": "QQQ",
                "weight": 0.40,
            },
            {
                "strategy_id": "sf_spy_core_phase6_overlay_satellite_qqq",
                "allocation_date": "2026-06-05",
                "asset": "SPY",
                "weight": 0.60,
            },
            {
                "strategy_id": "sf_spy_core_phase6_overlay_satellite_qqq",
                "allocation_date": "2026-06-05",
                "asset": "QQQ",
                "weight": 0.40,
            },
            {
                "strategy_id": "sf_spy_qqq_btc_capped_offensive",
                "allocation_date": "2026-06-05",
                "asset": "SPY",
                "weight": 0.55,
            },
            {
                "strategy_id": "sf_spy_qqq_btc_capped_offensive",
                "allocation_date": "2026-06-05",
                "asset": "QQQ",
                "weight": 0.35,
            },
            {
                "strategy_id": "sf_spy_qqq_btc_capped_offensive",
                "allocation_date": "2026-06-05",
                "asset": "BTC-USD",
                "weight": 0.10,
            },
        ]
    )


def _signal_policy_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "configured_audit_date": "2026-06-02",
                "latest_fresh_stream_date": "2026-06-08",
                "selected_signal_date": "2026-06-08",
                "configured_audit_date_capped_run": False,
                "warning": "configured_audit_date_older_than_latest_fresh_stream_date",
                "policy_explicit": True,
            }
        ]
    )


def _baseline_signal() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal_date": "2026-06-02",
                "data_as_of_date": "2026-06-02",
                "current_mode": "offensive_spy",
                "current_exposure": 1.0,
                "target_action": "risk_on_hold_preview",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def _quality_frame(*, warnings: str = "", blocks: str = "") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "asset_type": "etf",
                "warnings": "",
                "blocking_failures": "",
                "quality_status": "passed",
            },
            {
                "symbol": "BTC-USD",
                "asset_type": "crypto",
                "warnings": warnings,
                "blocking_failures": blocks,
                "quality_status": "blocked" if blocks else "warning" if warnings else "passed",
            },
        ]
    )


def _build_tear_sheet_for_quality(data_quality: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    config = _base_config(Path("."))
    preview, orders = build_watchlist_paper_preview(
        config=config,
        watchlist_candidates=_watchlist_candidates(),
        latest_allocations=_latest_allocations(),
    )
    journal = build_manual_execution_journal_template(orders)
    return build_daily_execution_tear_sheet(
        signal_policy=_signal_policy_frame(),
        data_quality=data_quality,
        baseline_signal=_baseline_signal(),
        preview=preview,
        preview_orders=orders,
        journal_template=journal,
        recurring_paper_trading_ready=False,
        live_trading_allowed=False,
        real_money_allowed=False,
        broker_api_integration_allowed=False,
    )


def test_stale_configured_audit_date_warning_is_written(tmp_path):
    config = _base_config(tmp_path, audit_date="2026-06-02")
    fresh_stream = pd.DataFrame({"date": ["2026-06-02", "2026-06-05"]})

    policy = build_signal_date_policy_report(config=config, fresh_stream=fresh_stream)
    row = policy.iloc[0]

    assert row["configured_audit_date"] == "2026-06-02"
    assert row["latest_fresh_stream_date"] == "2026-06-05"
    assert row["selected_signal_date"] == "2026-06-05"
    assert row["warning"] == "configured_audit_date_older_than_latest_fresh_stream_date"
    assert bool(row["audit_date_override_applied"])


def test_no_audit_date_policy_uses_latest_available_date(tmp_path):
    config = _base_config(tmp_path, audit_date=None)
    fresh_stream = pd.DataFrame({"date": ["2026-06-03", "2026-06-08"]})

    policy = build_signal_date_policy_report(config=config, fresh_stream=fresh_stream)
    row = policy.iloc[0]

    assert row["configured_audit_date"] == ""
    assert row["selected_signal_date"] == "2026-06-08"
    assert bool(row["latest_available_row_used_if_audit_date_absent"])


def test_duplicate_date_in_fresh_data_fails_closed(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-01", 101.0), ("2026-06-02", 102.0)],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={"require_no_duplicate_dates": True},
        current_date=pd.Timestamp("2026-06-09"),
    )

    assert "duplicate_dates_present" in report.iloc[0]["blocking_failures"]
    assert report.iloc[0]["quality_status"] == "blocked"


def test_null_latest_price_fails_closed(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", None)],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={"require_latest_row_non_null": True},
        current_date=pd.Timestamp("2026-06-09"),
    )

    assert "latest_row_price_null" in report.iloc[0]["blocking_failures"]
    assert report.iloc[0]["quality_status"] == "blocked"


def test_non_positive_price_fails_closed(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", 0.0)],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={"require_positive_prices": True},
        current_date=pd.Timestamp("2026-06-09"),
    )

    assert "non_positive_price_present" in report.iloc[0]["blocking_failures"]
    assert report.iloc[0]["quality_status"] == "blocked"


def test_outlier_return_warns_or_blocks_by_threshold(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", 125.0)],
    )

    warning_report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={
            "max_abs_daily_return_warning_pct": 20,
            "max_abs_daily_return_block_pct": 40,
        },
        current_date=pd.Timestamp("2026-06-09"),
    )
    assert "daily_return_outlier_warning" in warning_report.iloc[0]["warnings"]
    assert warning_report.iloc[0]["quality_status"] == "warning"

    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", 150.0)],
    )
    block_report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={
            "max_abs_daily_return_warning_pct": 20,
            "max_abs_daily_return_block_pct": 40,
        },
        current_date=pd.Timestamp("2026-06-09"),
    )
    assert "daily_return_outlier_block" in block_report.iloc[0]["blocking_failures"]
    assert block_report.iloc[0]["quality_status"] == "blocked"


def test_fresh_data_quality_report_includes_explicit_threshold_columns(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", 112.0)],
    )
    _write_price_parquet(
        data_dir,
        "BTC-USD",
        [("2026-06-01", 100.0), ("2026-06-02", 125.0)],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY", "BTC-USD"],
        quality_config={
            "etf_warning_abs_daily_return_pct": 10,
            "etf_block_abs_daily_return_pct": 15,
            "btc_warning_abs_daily_return_pct": 20,
            "btc_block_abs_daily_return_pct": 40,
        },
        current_date=pd.Timestamp("2026-06-09"),
    )
    by_symbol = report.set_index("symbol")

    assert {
        "asset_type",
        "warning_abs_daily_return_pct",
        "block_abs_daily_return_pct",
    }.issubset(report.columns)
    assert by_symbol.loc["SPY", "asset_type"] == "etf"
    assert by_symbol.loc["SPY", "warning_abs_daily_return_pct"] == 10
    assert by_symbol.loc["SPY", "block_abs_daily_return_pct"] == 15
    assert by_symbol.loc["BTC-USD", "asset_type"] == "crypto"
    assert by_symbol.loc["BTC-USD", "warning_abs_daily_return_pct"] == 20
    assert by_symbol.loc["BTC-USD", "block_abs_daily_return_pct"] == 40
    assert "daily_return_outlier_warning" in by_symbol.loc["SPY", "warnings"]
    assert "daily_return_outlier_warning" in by_symbol.loc["BTC-USD", "warnings"]


def test_etf_uses_etf_block_threshold(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "SPY",
        [("2026-06-01", 100.0), ("2026-06-02", 116.0)],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["SPY"],
        quality_config={
            "etf_warning_abs_daily_return_pct": 10,
            "etf_block_abs_daily_return_pct": 15,
            "btc_warning_abs_daily_return_pct": 20,
            "btc_block_abs_daily_return_pct": 40,
        },
        current_date=pd.Timestamp("2026-06-09"),
    )

    assert report.iloc[0]["asset_type"] == "etf"
    assert "daily_return_outlier_block" in report.iloc[0]["blocking_failures"]


def test_data_quality_gates_latest_return_not_old_history(tmp_path):
    data_dir = tmp_path / "fresh" / "processed"
    _write_price_parquet(
        data_dir,
        "QQQ",
        [
            ("2026-06-01", 100.0),
            ("2026-06-02", 120.0),
            ("2026-06-03", 121.0),
        ],
    )

    report, _latest = inspect_fresh_data_quality(
        data_dir=data_dir,
        symbols=["QQQ"],
        quality_config={
            "etf_warning_abs_daily_return_pct": 10,
            "etf_block_abs_daily_return_pct": 15,
        },
        current_date=pd.Timestamp("2026-06-09"),
    )

    row = report.iloc[0]
    assert row["max_abs_daily_return_pct"] == 20.0
    assert row["latest_abs_daily_return_pct"] < 10.0
    assert row["blocking_failures"] == ""
    assert row["quality_status"] == "passed"


def test_daily_execution_tear_sheet_markdown_includes_safety_banner():
    tear_sheet, markdown = _build_tear_sheet_for_quality(_quality_frame())

    assert "NO LIVE TRADING" in markdown
    assert "NO REAL MONEY" in markdown
    assert "NO BROKER/API" in markdown
    assert "MANUAL PAPER PREVIEW ONLY" in markdown
    final_action = tear_sheet.loc[
        tear_sheet["key"] == "final_recommended_manual_action",
        "value",
    ].iloc[0]
    assert final_action == "NO BLOCKING ISSUES — MANUAL PAPER PREVIEW ONLY"
    btc_candidates = tear_sheet.loc[
        tear_sheet["key"] == "candidate_includes_or_can_include_btc",
        "value",
    ].iloc[0]
    assert btc_candidates == "sf_spy_qqq_btc_capped_offensive"


def test_daily_execution_tear_sheet_blocks_hold_current_state():
    tear_sheet, markdown = _build_tear_sheet_for_quality(
        _quality_frame(blocks="daily_return_outlier_block")
    )

    assert "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE" in markdown
    final_action = tear_sheet.loc[
        tear_sheet["key"] == "final_recommended_manual_action",
        "value",
    ].iloc[0]
    assert final_action == "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE"


def test_daily_execution_tear_sheet_warns_manual_review_before_entry():
    tear_sheet, markdown = _build_tear_sheet_for_quality(
        _quality_frame(warnings="btc_weekend_data_available_common_date_caveat")
    )

    assert "WARNINGS PRESENT — MANUAL REVIEW BEFORE PAPER ENTRY" in markdown
    final_action = tear_sheet.loc[
        tear_sheet["key"] == "final_recommended_manual_action",
        "value",
    ].iloc[0]
    assert final_action == "WARNINGS PRESENT — MANUAL REVIEW BEFORE PAPER ENTRY"


def test_config_hash_is_stable_and_changes_for_relevant_config(tmp_path):
    config = _base_config(tmp_path)
    first = build_config_hash_report(config=config, generated_at_utc="2026-06-09T00:00:00Z")
    second = build_config_hash_report(config=config, generated_at_utc="2026-06-09T00:00:00Z")

    assert first["hash_value"].tolist() == second["hash_value"].tolist()

    changed = _base_config(tmp_path)
    changed["phase17a_strategy_factory"]["btc_max_weight"] = 0.05
    changed_report = build_config_hash_report(
        config=changed,
        generated_at_utc="2026-06-09T00:00:00Z",
    )
    scope = "phase17_strategy_factory_watchlist"
    original_hash = first.loc[first["hash_scope"] == scope, "hash_value"].iloc[0]
    changed_hash = changed_report.loc[
        changed_report["hash_scope"] == scope,
        "hash_value",
    ].iloc[0]
    assert original_hash != changed_hash


def test_watchlist_preview_keeps_safety_flags_false_and_btc_caveat(tmp_path):
    config = _base_config(tmp_path)

    preview, orders = build_watchlist_paper_preview(
        config=config,
        watchlist_candidates=_watchlist_candidates(),
        latest_allocations=_latest_allocations(),
    )

    assert not preview.empty
    assert not orders.empty
    assert not preview["live_trading_allowed"].any()
    assert not preview["real_money_allowed"].any()
    assert not preview["broker_api_integration_allowed"].any()
    assert not preview["promotion_allowed"].any()
    assert not preview["paper_trading_ready"].any()
    btc_rows = preview[preview["candidate_id"] == "sf_spy_qqq_btc_capped_offensive"]
    assert btc_rows["blocking_warnings"].str.contains("btc_weekend_gap_risk").any()


def test_manual_execution_journal_template_has_required_columns(tmp_path):
    config = _base_config(tmp_path)
    _preview, orders = build_watchlist_paper_preview(
        config=config,
        watchlist_candidates=_watchlist_candidates(),
        latest_allocations=_latest_allocations(),
    )

    journal = build_manual_execution_journal_template(orders)

    assert JOURNAL_COLUMNS.issubset(set(journal.columns))
    assert set(journal["manual_execution_status"]) == {"not_entered"}
    assert not journal["live_trading_allowed"].any()
    assert not journal["real_money_allowed"].any()
    assert not journal["broker_api_integration_allowed"].any()


def test_save_phase18a_writes_outputs_and_passes_manual_preview_gate(tmp_path):
    reports_dir = tmp_path / "reports"
    fresh_stream_path = tmp_path / "data" / "fresh" / "phase15q.csv"
    fresh_processed_dir = tmp_path / "data" / "fresh" / "processed"
    latest_signal_path = reports_dir / "paper_trading" / "latest_signal.csv"
    watchlist_path = (
        reports_dir
        / "strategy_factory"
        / "watchlist"
        / "phase17c_watchlist_candidates.csv"
    )
    latest_allocations_path = (
        reports_dir
        / "strategy_factory"
        / "transactions"
        / "strategy_latest_allocations.csv"
    )

    fresh_stream_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": ["2026-06-02", "2026-06-05"]}).to_csv(
        fresh_stream_path,
        index=False,
    )
    latest_signal_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "signal_date": ["2026-06-05"],
            "paper_dry_run_allowed": [True],
            "live_trading_allowed": [False],
            "real_money_allowed": [False],
            "broker_api_integration_allowed": [False],
        }
    ).to_csv(latest_signal_path, index=False)
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    _watchlist_candidates().to_csv(watchlist_path, index=False)
    latest_allocations_path.parent.mkdir(parents=True, exist_ok=True)
    _latest_allocations().to_csv(latest_allocations_path, index=False)

    for symbol in DEFAULT_SYMBOLS:
        _write_price_parquet(
            fresh_processed_dir,
            symbol,
            [("2026-06-03", 100.0), ("2026-06-04", 101.0), ("2026-06-05", 102.0)],
        )

    config = _base_config(tmp_path)
    config[PHASE18A]["source_files"] = {
        "fresh_stream": str(fresh_stream_path),
        "fresh_processed_data_dir": str(fresh_processed_dir),
        "baseline_latest_signal": str(latest_signal_path),
        "watchlist_candidates": str(watchlist_path),
        "strategy_latest_allocations": str(latest_allocations_path),
    }

    outputs = save_phase18a_paper_signal_operational_hardening(
        config=config,
        reports_dir=reports_dir,
    )

    output_dir = Path(config[PHASE18A]["output_dir"])
    assert (output_dir / "phase18a_summary.csv").exists()
    assert (output_dir / "fresh_data_quality_report.csv").exists()
    assert (output_dir / "watchlist_paper_preview.csv").exists()
    assert (output_dir / "daily_execution_tear_sheet.csv").exists()
    assert (output_dir / "daily_execution_tear_sheet.md").exists()
    assert (
        reports_dir / "paper_trading" / "dashboard" / "operational_hardening_status.csv"
    ).exists()
    markdown = (output_dir / "daily_execution_tear_sheet.md").read_text(encoding="utf-8")
    assert "NO LIVE TRADING" in markdown
    assert "NO REAL MONEY" in markdown
    assert "NO BROKER/API" in markdown
    assert "MANUAL PAPER PREVIEW ONLY" in markdown
    gate_ids = set(outputs["gate_report"]["gate_id"])
    assert "daily_execution_tear_sheet_written" in gate_ids
    assert "daily_execution_tear_sheet_md_written" in gate_ids
    assert bool(outputs["summary"].iloc[0]["daily_execution_tear_sheet_written"])
    assert bool(outputs["summary"].iloc[0]["daily_execution_tear_sheet_md_written"])
    assert outputs["summary"].iloc[0]["decision"] == (
        "paper_signal_operational_hardening_completed_manual_preview_only"
    )
    assert not bool(outputs["summary"].iloc[0]["recurring_paper_trading_ready"])
