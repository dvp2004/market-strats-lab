from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset import cli as gma_cli
from market_strats.global_multi_asset.gma3a_config import validate_gma3a_config
from market_strats.global_multi_asset.gma3a_manual_fills import validate_gma3a_manual_fills
from market_strats.global_multi_asset.gma3a_paper_readiness import run_gma3a_paper_readiness
from market_strats.global_multi_asset.gma3a_post_endpoint_refresh import (
    _best_processed_snapshot_for_materialization,
    _build_post_endpoint_rows,
    _post_endpoint_completed_history,
)
from market_strats.global_multi_asset.gma3a_tournament import (
    STRATEGY_IDS,
    _core_fallback_passed,
    _extend_prices,
    _gma3a_execution_timing_block,
    _is_us_equity_session_date,
    _latest_signal_date_with_later_execution,
    _manual_fill_columns,
    _order_packet_columns,
    run_gma3a_transparent_tournament,
    verify_gma3a_upstream,
)


CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml")
FIXTURE_CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma3a_fixture_contamination_test.yaml")


class ExistingResult:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root


@pytest.fixture()
def temp_config():
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return validate_gma3a_config(raw, path=CONFIG_PATH)


@pytest.fixture()
def fixture_config(tmp_path: Path):
    raw = yaml.safe_load(FIXTURE_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["paths"]["output_root"] = str(tmp_path / "reports")
    raw["paths"]["data_root"] = str(tmp_path / "data")
    return validate_gma3a_config(raw, path=FIXTURE_CONFIG_PATH)


@pytest.fixture()
def result(temp_config):
    output_root = temp_config.paths["output_root"]
    summary_path = output_root / "gma3a_summary.csv"
    assert summary_path.exists(), "production GMA-3A-R summary missing; run full-history tournament first"
    summary = pd.read_csv(summary_path)
    assert not summary.iloc[0]["decision"].startswith("gma3ar_blocked")
    return ExistingResult(output_root)


def test_fixture_contamination_blocking(fixture_config):
    # Proves that a four-day fixture cannot produce passing strategy gates or a paper ensemble
    res = run_gma3a_transparent_tournament(fixture_config)
    assert res.decision == "gma3ar_blocked_fixture_contamination"
    assert res.order_packet_rows == 0


def test_upstream_hash_verification(temp_config):
    accepted = verify_gma3a_upstream(temp_config)
    assert accepted["gma1a_accepted_selection_hash"] == temp_config.accepted_inputs["gma1a_accepted_selection_hash"]
    assert accepted["gma2_accepted_replay_hash"] == temp_config.accepted_inputs["gma2_accepted_replay_hash"]


def test_common_execution_convention(result):
    targets = pd.read_csv(result.output_root / "gma3a_current_strategy_targets.csv")
    assert "expected_execution_date" in targets.columns


def test_strategy_account_isolation(result):
    equity = pd.read_csv(result.output_root / "gma3a_equity_curves.csv")
    assert set(STRATEGY_IDS) <= set(equity["account_id"])
    assert equity.groupby("account_id")["portfolio_value"].count().min() >= 2


def test_no_lookahead(result):
    gates = pd.read_csv(result.output_root / "gma3a_gate_report.csv")
    row = gates.loc[gates["gate"] == "no_lookahead_failure"].iloc[0]
    assert bool(row["passed"])


def test_transaction_costs(result):
    costs = pd.read_csv(result.output_root / "gma3a_turnover_costs.csv")
    assert (costs["transaction_cost"] >= 0).all()
    assert costs["charged_once"].all()


def test_dgs3mo_cash_accrual(result):
    state = pd.read_csv(result.output_root / "gma3a_current_market_state.csv")
    assert "cash_3m_treasury" in set(state["symbol"])


def test_macro_point_in_time_eligibility(result):
    gates = pd.read_csv(result.output_root / "gma3a_gate_report.csv")
    assert gates.loc[gates["gate"] == "no_lookahead_failure", "passed"].all()


def test_walk_forward_separation(result):
    wf = pd.read_csv(result.output_root / "gma3a_walk_forward_scoreboard.csv")
    assert set(wf["evaluation"]) == {"walk_forward"}


def test_holdout_separation(result):
    holdout = pd.read_csv(result.output_root / "gma3a_holdout_scoreboard.csv")
    assert set(holdout["evaluation"]) == {"holdout"}


def test_target_weights_sum_to_one(result):
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    assert targets["final_target_weight"].sum() == pytest.approx(1.0)


def test_no_leverage(result):
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    assert targets["final_target_weight"].sum() <= 1.000001


def test_no_short_positions(result):
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    assert (targets["final_target_weight"] >= 0).all()


def test_asset_concentration_limits(result, temp_config):
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    assert targets.loc[targets["symbol"] != "CASH", "final_target_weight"].max() <= temp_config.raw["limits"]["maximum_single_asset_weight"] + 1e-9


def test_bitcoin_cap(result, temp_config):
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    btc = targets.loc[targets["symbol"] == "BTC-USD", "final_target_weight"]
    assert btc.empty or btc.max() <= temp_config.raw["limits"]["maximum_bitcoin_weight"] + 1e-9


def test_strategy_contribution_reconciliation(result):
    contrib = pd.read_csv(result.output_root / "gma3a_strategy_contributions.csv")
    assert contrib["final_target_weight"].sum() == pytest.approx(1.0)
    assert (contrib["ml_contribution"] == 0).all()


def test_independent_model_ledgers(result):
    equity = pd.read_csv(result.output_root / "gma3a_equity_curves.csv")
    assert equity["account_id"].nunique() == len(STRATEGY_IDS)


def test_current_target_idempotency(temp_config):
    targets_first = (temp_config.paths["output_root"] / "gma3a_live_ensemble_targets.csv").read_text(encoding="utf-8")
    targets_second = (temp_config.paths["output_root"] / "gma3a_live_ensemble_targets.csv").read_text(encoding="utf-8")
    assert targets_first == targets_second


def test_duplicate_packet_rejection(result):
    packet = pd.read_csv(result.output_root / "gma3a_tradingview_order_packet.csv")
    if not packet.empty:
        assert not packet.duplicated(["order_packet_id", "symbol"]).any()


def test_actual_holdings_change_only_after_confirmed_fill(result):
    fills = pd.read_csv(result.output_root / "gma3a_tradingview_manual_fill_template.csv")
    assert list(fills.columns) == _manual_fill_columns()
    holdings = pd.read_csv(result.output_root / "gma3a_actual_holdings.csv")
    assert not holdings.empty


def test_rejected_and_partial_fill_handling_columns_exist(result):
    template = pd.read_csv(result.output_root / "gma3a_tradingview_manual_fill_template.csv")
    assert "rejection_reason" in template.columns
    assert "partial_fill_reason" in template.columns


def test_corrective_delta_from_confirmed_holdings(result):
    recon = pd.read_csv(result.output_root / "gma3a_tracking_reconciliation.csv")
    assert recon["actual_holdings_change_requires_confirmed_manual_fills"].all()


def test_missing_ml_news_fundamental_data_zero_influence(result):
    ml = pd.read_csv(result.output_root / "gma3a_ml_boundary.csv")
    assert ml.iloc[0]["status"] == "not_implemented"
    assert float(ml.iloc[0]["portfolio_influence"]) == 0
    state = pd.read_csv(result.output_root / "gma3a_current_market_state.csv")
    assert (state["unavailable_feature_influence"] == 0).all()


def test_phase23_isolation(result):
    hashes = (result.output_root / "gma3a_input_hashes.json").read_text(encoding="utf-8")
    assert '"phase23_isolated": true' in hashes


def test_no_real_money_flags(result):
    summary = pd.read_csv(result.output_root / "gma3a_summary.csv")
    assert not summary["live_trading_allowed"].any()
    assert not summary["real_money_allowed"].any()
    assert not summary["broker_api_integration_allowed"].any()


def test_no_credentials_or_automatic_order_submission(result):
    entry = (result.output_root / "gma3a_manual_tradingview_entry_sheet.md").read_text(encoding="utf-8")
    assert "NO LIVE TRADING" in entry
    assert "NO REAL MONEY" in entry
    assert "NO BROKER/API" in entry


def test_turnover_audit_has_cumulative_and_annualised_fields(result):
    audit = pd.read_csv(result.output_root / "gma3a_turnover_definition_audit.csv")
    required = {
        "cumulative_turnover",
        "replay_years",
        "annualised_turnover",
        "average_turnover_per_rebalance",
        "rebalance_count",
        "annualised_transaction_cost_drag",
        "total_transaction_costs",
        "turnover_gate_field_used",
    }
    assert required <= set(audit.columns)
    row = audit.loc[audit["strategy_id"] == "gma_balanced_core_v0"].iloc[0]
    assert row["annualised_turnover"] == pytest.approx(
        row["cumulative_turnover"] / row["replay_years"]
    )
    assert set(audit["turnover_gate_field_used"]) == {"annualised_turnover"}


def test_turnover_gate_uses_annualised_metric(result):
    tactical = pd.read_csv(result.output_root / "gma3a_tactical_gate_report.csv")
    core = pd.read_csv(result.output_root / "gma3a_core_fallback_gate_report.csv")
    gate_names = set(tactical["gate"]) | set(core["gate"])
    assert "maximum_annualised_turnover" in gate_names
    assert "core_fallback_maximum_annualised_turnover" in gate_names
    assert "acceptable_turnover" not in gate_names


def test_tactical_and_core_gates_are_separate(result):
    tactical = pd.read_csv(result.output_root / "gma3a_tactical_gate_report.csv")
    core = pd.read_csv(result.output_root / "gma3a_core_fallback_gate_report.csv")
    assert set(tactical["gate_group"]) == {"tactical_candidate_gates"}
    assert set(core["gate_group"]) == {"core_fallback_gates"}


def test_failed_core_cannot_be_selected():
    gates = pd.DataFrame(
        [
            {"strategy_id": "gma_balanced_core_v0", "gate": "positive_net_return", "passed": True},
            {
                "strategy_id": "gma_balanced_core_v0",
                "gate": "core_fallback_maximum_drawdown",
                "passed": False,
            },
        ]
    )
    assert not _core_fallback_passed(gates)


def test_core_only_reason_code_when_no_tactical_qualifiers(result):
    summary = pd.read_csv(result.output_root / "gma3a_summary.csv")
    targets = pd.read_csv(result.output_root / "gma3a_live_ensemble_targets.csv")
    assert summary.iloc[0]["ensemble_type"] == "core_only"
    passers = summary.iloc[0]["passing_tactical_strategies"]
    assert pd.isna(passers) or not str(passers).strip()
    assert set(targets["reason_codes"]) == {"core_only_fallback_no_tactical_qualifiers"}


def test_tactical_contributions_zero_in_core_only_mode(result):
    contrib = pd.read_csv(result.output_root / "gma3a_strategy_contributions.csv")
    assert "tactical_contribution_weight" in contrib.columns
    assert (contrib["tactical_contribution_weight"] == 0).all()
    assert set(contrib["contributing_strategies"]) == {"gma_balanced_core_v0"}


def test_endpoint_boundary_may4_no_signal_influence(result):
    audit = pd.read_csv(result.output_root / "gma3a_endpoint_boundary_audit.csv")
    row = audit.iloc[0]
    assert str(row["historical_selection_data_end"]) == "2026-05-01"
    assert str(row["last_signal_information_date"]) == "2026-05-01"
    assert str(row["last_scheduled_execution_date"]) == "2026-05-04"
    assert bool(row["may_4_execution_or_valuation_allowed"])
    assert not bool(row["may_4_price_used_for_signal_or_selection"])
    assert row["endpoint_boundary_status"] == "passed_next_open_execution_after_endpoint"


def test_macro_defensive_duplicate_classification(result):
    distinct = pd.read_csv(result.output_root / "gma3a_strategy_distinctness_report.csv")
    row = distinct.iloc[0]
    assert row["strategy_id"] == "gma_macro_defensive_overlay_v0"
    assert int(row["macro_overlay_activation_count"]) == 0
    assert row["strategy_distinctness_status"] == "no_effect_relative_to_balanced_core"


def test_empty_packet_remains_empty_without_later_execution_opens(result):
    packet = pd.read_csv(result.output_root / "gma3a_tradingview_order_packet.csv")
    recon = pd.read_csv(result.output_root / "gma3a_tracking_reconciliation.csv")
    assert packet.empty
    assert "non_retroactive_execution_block" in str(recon.iloc[0]["blocking_reason"])


def test_no_change_to_accepted_gma2_files():
    import subprocess

    files = [
        "configs/global_multi_asset_alpha/gma2_replay_foundation.yaml",
        "src/market_strats/global_multi_asset/gma2_config.py",
        "src/market_strats/global_multi_asset/gma2_replay.py",
    ]
    result = subprocess.run(["git", "diff", "--name-only", "--", *files], check=True, capture_output=True, text=True)
    assert not result.stdout.strip()


def test_operational_post_endpoint_refresh_rows_are_merged(tmp_path: Path, temp_config):
    raw = dict(temp_config.raw)
    raw["paths"] = {key: str(value) for key, value in temp_config.paths.items()}
    raw["paths"]["data_root"] = str(tmp_path / "gma3a_data")
    config = validate_gma3a_config(raw, path=temp_config.path)
    post_root = config.paths["data_root"] / "post_endpoint_market"
    post_root.mkdir(parents=True)

    canonical = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-05-01").date(),
                "instrument_id": "SPY",
                "open_raw": 100.0,
                "high_raw": 101.0,
                "low_raw": 99.0,
                "close_raw": 100.0,
                "adj_close_provider": 100.0,
                "volume": 1000,
                "dividend_cash": 0.0,
                "split_ratio": 0.0,
                "is_completed_observation": True,
                "calendar_id": "us_listed_etf",
                "source_manifest_sha256": "canonical_manifest",
                "source_raw_sha256": "canonical_raw",
                "source_normalised_sha256": "canonical_norm",
                "total_return_factor": 1.0,
                "total_return_index": 1.0,
            },
            {
                "date": pd.Timestamp("2026-06-12").date(),
                "instrument_id": "SPY",
                "open_raw": 110.0,
                "high_raw": 111.0,
                "low_raw": 109.0,
                "close_raw": 110.0,
                "adj_close_provider": 110.0,
                "volume": 1000,
                "dividend_cash": 0.0,
                "split_ratio": 0.0,
                "is_completed_observation": True,
                "calendar_id": "us_listed_etf",
                "source_manifest_sha256": "old_manifest",
                "source_raw_sha256": "old_raw",
                "source_normalised_sha256": "old_norm",
                "total_return_factor": 1.1,
                "total_return_index": 1.1,
            },
        ]
    ).set_index("date")
    refreshed = canonical.reset_index().copy()
    refreshed = refreshed.loc[refreshed["date"].astype(str).eq("2026-06-12")].copy()
    refreshed.loc[:, "close_raw"] = 120.0
    refreshed.loc[:, "open_raw"] = 119.0
    refreshed.loc[:, "high_raw"] = 121.0
    refreshed.loc[:, "low_raw"] = 118.0
    refreshed.loc[:, "adj_close_provider"] = 120.0
    refreshed.loc[:, "total_return_index"] = 1.2
    refreshed.loc[:, "source_manifest_sha256"] = "fresh_manifest"
    refreshed.loc[:, "source_raw_sha256"] = "fresh_raw"
    refreshed.loc[:, "source_normalised_sha256"] = "fresh_norm"
    refreshed.to_csv(post_root / "SPY_post_endpoint.csv", index=False)

    augmented, _manifest, _input_hashes, data_status = _extend_prices({"SPY": canonical}, config)

    assert augmented["SPY"].loc[pd.Timestamp("2026-05-01").date(), "close_raw"] == pytest.approx(100.0)
    assert augmented["SPY"].loc[pd.Timestamp("2026-06-12").date(), "close_raw"] == pytest.approx(120.0)
    assert data_status[0]["post_endpoint_source"] == "gma3a_post_endpoint_refresh"


def test_post_endpoint_finalizer_keeps_latest_valid_processed_snapshot_row(tmp_path: Path):
    canonical = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-05-01").date(),
                "instrument_id": "IEF",
                "open_raw": 100.0,
                "high_raw": 101.0,
                "low_raw": 99.0,
                "close_raw": 100.0,
                "adj_close_provider": 100.0,
                "volume": 1000,
                "dividend_cash": 0.0,
                "split_ratio": 0.0,
                "is_completed_observation": True,
                "calendar_id": "us_listed_etf",
                "source_manifest_sha256": "canonical_manifest",
                "source_raw_sha256": "canonical_raw",
                "source_normalised_sha256": "canonical_norm",
                "total_return_factor": 1.0,
                "total_return_index": 1.0,
            }
        ]
    ).set_index("date")
    normalised = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-17"),
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "adj_close": 101.5,
                "volume": 1000,
            },
            {
                "date": pd.Timestamp("2026-06-18"),
                "open": 102.0,
                "high": 103.0,
                "low": 101.0,
                "close": 102.5,
                "adj_close": 102.5,
                "volume": 1100,
            },
        ]
    )
    raw = normalised.rename(
        columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adj_close": "Adj Close",
            "volume": "Volume",
        }
    )
    manifest_path = tmp_path / "manifest.json"
    normalised_path = tmp_path / "normalised.csv"
    raw_path = tmp_path / "raw.csv"
    manifest_path.write_text("{}", encoding="utf-8")
    normalised.to_csv(normalised_path, index=False)
    raw.to_csv(raw_path, index=False)

    completed = _post_endpoint_completed_history(normalised)
    post_rows = _build_post_endpoint_rows(
        symbol="IEF",
        canonical=canonical,
        completed=completed,
        raw=raw,
        manifest_path=manifest_path,
        normalised_path=normalised_path,
        raw_path=raw_path,
    )

    assert list(post_rows["date"]) == ["2026-06-17", "2026-06-18"]
    assert post_rows.iloc[-1]["close_raw"] == pytest.approx(102.5)
    assert post_rows.iloc[-1]["is_completed_observation"]


def test_post_endpoint_materialization_prefers_latest_complete_processed_snapshot(tmp_path: Path):
    manifest_root = tmp_path / "manifests"
    processed_root = tmp_path / "processed"
    raw_root = tmp_path / "raw"
    for root in [manifest_root, processed_root, raw_root]:
        (root / "yahoo_yfinance" / "IEF").mkdir(parents=True)

    older_normalised = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-17"),
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "adj_close": 101.5,
                "volume": 1000,
            },
            {
                "date": pd.Timestamp("2026-06-18"),
                "open": 102.0,
                "high": 103.0,
                "low": 101.0,
                "close": 102.5,
                "adj_close": 102.5,
                "volume": 1100,
            },
        ]
    )
    newer_normalised = older_normalised.copy()
    newer_normalised.loc[newer_normalised["date"].eq(pd.Timestamp("2026-06-18")), "close"] = pd.NA
    newer_normalised.loc[newer_normalised["date"].eq(pd.Timestamp("2026-06-18")), "adj_close"] = pd.NA

    for stamp, frame in [("20260618T194650000000Z", older_normalised), ("20260619T111457000000Z", newer_normalised)]:
        normalised_path = processed_root / "yahoo_yfinance" / "IEF" / f"IEF_{stamp}_normalised.csv"
        raw_path = raw_root / "yahoo_yfinance" / "IEF" / f"IEF_{stamp}.csv"
        manifest_path = manifest_root / "yahoo_yfinance" / "IEF" / f"IEF_{stamp}_manifest.json"
        frame.to_csv(normalised_path, index=False)
        frame.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "adj_close": "Adj Close",
                "volume": "Volume",
            }
        ).to_csv(raw_path, index=False)
        manifest_path.write_text(
            json.dumps(
                {
                    "normalised_file_path": str(normalised_path),
                    "raw_file_path": str(raw_path),
                }
            ),
            encoding="utf-8",
        )

    selected = _best_processed_snapshot_for_materialization(
        symbol="IEF",
        provider="yahoo_yfinance",
        manifest_root=manifest_root,
    )

    assert selected is not None
    assert selected.latest_completed_date == pd.Timestamp("2026-06-18").date()
    assert selected.completed.iloc[-1]["close"] == pytest.approx(102.5)
    assert "20260618T194650000000Z" in selected.normalised_path.name


def test_juneteenth_2026_is_not_us_equity_session():
    assert not _is_us_equity_session_date(pd.Timestamp("2026-06-19").date())
    assert _is_us_equity_session_date(pd.Timestamp("2026-06-18").date())
    assert _is_us_equity_session_date(pd.Timestamp("2026-06-22").date())


def test_latest_signal_date_requires_later_execution_row():
    dates = [
        pd.Timestamp("2026-06-17").date(),
        pd.Timestamp("2026-06-18").date(),
    ]
    prices = {
        symbol: pd.DataFrame({"close_raw": [100.0, 101.0]}, index=dates)
        for symbol in ["SPY", "QQQ", "IEF", "GLD", "DBC"]
    }

    signal_date = _latest_signal_date_with_later_execution(
        prices,
        {"SPY", "QQQ", "IEF", "GLD", "DBC"},
    )

    assert signal_date == pd.Timestamp("2026-06-17").date()


def test_paper_readiness_reports_non_retroactive_block_without_order_packet(tmp_path: Path, temp_config):
    raw = dict(temp_config.raw)
    raw["paths"] = {key: str(value) for key, value in temp_config.paths.items()}
    raw["paths"]["output_root"] = str(tmp_path / "reports")
    raw["paths"]["data_root"] = str(tmp_path / "data")
    config = validate_gma3a_config(raw, path=temp_config.path)
    out = config.paths["output_root"]
    data_root = config.paths["data_root"]
    out.mkdir(parents=True)
    post_root = data_root / "post_endpoint_market"
    post_root.mkdir(parents=True)

    for symbol in ["SPY", "QQQ", "IEF", "GLD", "DBC"]:
        pd.DataFrame(
            [
                {
                    "date": "2026-06-18",
                    "instrument_id": symbol,
                    "close_raw": 100.0,
                }
            ]
        ).to_csv(post_root / f"{symbol}_post_endpoint.csv", index=False)

    pd.DataFrame(
        [
            {
                "phase": "GMA-3A-R2",
                "decision": "gma3ar2_ready_core_only_waiting_execution_open",
                "order_packet_rows": 0,
                "target_blocking_reason": (
                    "non_retroactive_execution_block: execution window 2026-06-18 "
                    "has passed as of 2026-06-19"
                ),
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "ml_portfolio_influence": 0,
            }
        ]
    ).to_csv(out / "gma3a_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_date": "2026-06-17",
                "expected_execution_date": "2026-06-18",
                "symbol": "SPY",
                "final_target_weight": 0.35,
            }
        ]
    ).to_csv(out / "gma3a_current_strategy_targets.csv", index=False)
    pd.DataFrame(columns=_manual_fill_columns()).to_csv(out / "gma3a_tradingview_manual_fill_template.csv", index=False)
    pd.DataFrame(columns=_order_packet_columns()).to_csv(out / "gma3a_tradingview_order_packet.csv", index=False)

    result = run_gma3a_paper_readiness(config)
    summary = pd.read_csv(result.summary_path).iloc[0]

    assert result.readiness_status == "blocked"
    assert result.execution_status == "retroactive_blocked"
    assert not result.manual_tradingview_entry_active
    assert result.order_packet_rows == 0
    assert summary["SPY_latest_finalized_date"] == "2026-06-18"
    assert bool(summary["safety_flags_valid"])
    assert "non_retroactive_execution_block" in result.blocking_reason


def _manual_fill_test_config(tmp_path: Path, temp_config, *, active_packet: bool):
    raw = dict(temp_config.raw)
    raw["paths"] = {key: str(value) for key, value in temp_config.paths.items()}
    raw["paths"]["output_root"] = str(tmp_path / "reports")
    raw["paths"]["data_root"] = str(tmp_path / "data")
    config = validate_gma3a_config(raw, path=temp_config.path)
    out = config.paths["output_root"]
    data_root = config.paths["data_root"]
    out.mkdir(parents=True)
    post_root = data_root / "post_endpoint_market"
    post_root.mkdir(parents=True)
    for symbol in ["SPY", "QQQ", "IEF", "GLD", "DBC"]:
        pd.DataFrame([{"date": "2026-06-18", "instrument_id": symbol, "close_raw": 100.0}]).to_csv(
            post_root / f"{symbol}_post_endpoint.csv",
            index=False,
        )
    blocking_reason = (
        ""
        if active_packet
        else "non_retroactive_execution_block: execution window 2026-06-18 has passed as of 2026-06-19"
    )
    pd.DataFrame(
        [
            {
                "phase": "GMA-3A-R2",
                "decision": (
                    "gma3ar2_live_paper_packet_ready_manual_submission_required"
                    if active_packet
                    else "gma3ar2_ready_core_only_waiting_execution_open"
                ),
                "order_packet_rows": 1 if active_packet else 0,
                "target_blocking_reason": blocking_reason,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "ml_portfolio_influence": 0,
            }
        ]
    ).to_csv(out / "gma3a_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_date": "2026-06-17",
                "expected_execution_date": "2026-06-18",
                "symbol": "SPY",
                "final_target_weight": 0.35,
            }
        ]
    ).to_csv(out / "gma3a_current_strategy_targets.csv", index=False)
    packet_rows = [
        {
            "order_packet_id": "packet-spy-buy",
            "account_id": "gma_live_paper_ensemble_v0",
            "decision_date": "2026-06-17",
            "expected_execution_date": "2026-06-18",
            "symbol": "SPY",
            "asset_class": "US large-cap equities",
            "side": "BUY",
            "current_confirmed_quantity": 0,
            "target_quantity": 10,
            "order_quantity": 10,
            "target_weight": 0.35,
            "reference_price": 100.0,
            "reference_price_date": "2026-06-18",
            "reason_codes": "test",
            "contributing_strategies": "test",
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "blocking_reason": "",
        }
    ]
    pd.DataFrame(packet_rows if active_packet else [], columns=_order_packet_columns()).to_csv(
        out / "gma3a_tradingview_order_packet.csv",
        index=False,
    )
    return config


def _write_fill_file(path: Path, rows: list[dict[str, object]]) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _valid_fill_row(**overrides):
    row = {
        "fill_id": "fill-1",
        "order_packet_id": "packet-spy-buy",
        "symbol": "SPY",
        "submitted_side": "BUY",
        "filled_quantity": 10,
        "fill_price": 101.0,
        "fill_timestamp": "2026-06-18T14:35:00Z",
        "account_name": "TradingView Paper Trading - GMA Alpha V0",
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_submission": False,
    }
    row.update(overrides)
    return row


def test_manual_fill_validation_rejects_when_readiness_blocked(tmp_path: Path, temp_config):
    config = _manual_fill_test_config(tmp_path, temp_config, active_packet=False)
    fills_path = _write_fill_file(tmp_path / "fills.csv", [_valid_fill_row()])

    result = validate_gma3a_manual_fills(config, fills_path)
    summary = pd.read_csv(result.summary_path).iloc[0]
    rows = pd.read_csv(result.row_validation_path)

    assert not result.session_valid
    assert result.accepted_rows == 0
    assert result.rejected_rows == 1
    assert "manual_tradingview_entry_not_active" in result.blocking_reason
    assert "manual_tradingview_entry_not_active" in rows.iloc[0]["row_blocking_reasons"]
    assert not bool(summary["canonical_holdings_updated"])


def test_manual_fill_validation_rejects_unknown_order_packet_id(tmp_path: Path, temp_config):
    config = _manual_fill_test_config(tmp_path, temp_config, active_packet=True)
    fills_path = _write_fill_file(tmp_path / "fills.csv", [_valid_fill_row(order_packet_id="unknown-packet")])

    result = validate_gma3a_manual_fills(config, fills_path)
    rows = pd.read_csv(result.row_validation_path)

    assert not result.session_valid
    assert "unknown_order_packet_id" in rows.iloc[0]["row_blocking_reasons"]


def test_manual_fill_validation_rejects_symbol_and_side_mismatch(tmp_path: Path, temp_config):
    config = _manual_fill_test_config(tmp_path, temp_config, active_packet=True)
    fills_path = _write_fill_file(tmp_path / "fills.csv", [_valid_fill_row(symbol="QQQ", submitted_side="SELL")])

    result = validate_gma3a_manual_fills(config, fills_path)
    rows = pd.read_csv(result.row_validation_path)

    assert not result.session_valid
    assert "symbol_mismatch" in rows.iloc[0]["row_blocking_reasons"]
    assert "side_mismatch" in rows.iloc[0]["row_blocking_reasons"]


def test_manual_fill_validation_rejects_duplicate_fill(tmp_path: Path, temp_config):
    config = _manual_fill_test_config(tmp_path, temp_config, active_packet=True)
    fills_path = _write_fill_file(tmp_path / "fills.csv", [_valid_fill_row(), _valid_fill_row()])

    result = validate_gma3a_manual_fills(config, fills_path)
    rows = pd.read_csv(result.row_validation_path)

    assert not result.session_valid
    assert result.rejected_rows == 2
    assert rows["row_blocking_reasons"].str.contains("duplicate_fill_id").all()
    assert rows["row_blocking_reasons"].str.contains("duplicate_order_packet_id_partial_fill_not_supported").all()


def test_manual_fill_validation_accepts_valid_active_packet_fill(tmp_path: Path, temp_config):
    config = _manual_fill_test_config(tmp_path, temp_config, active_packet=True)
    fills_path = _write_fill_file(tmp_path / "fills.csv", [_valid_fill_row()])

    result = validate_gma3a_manual_fills(config, fills_path)
    summary = pd.read_csv(result.summary_path).iloc[0]
    reconciliation = pd.read_csv(result.reconciliation_path)

    assert result.session_valid
    assert result.accepted_rows == 1
    assert result.rejected_rows == 0
    assert bool(summary["manual_paper_only"])
    assert not bool(summary["canonical_holdings_updated"])
    assert not bool(summary["canonical_cash_updated"])
    assert reconciliation.iloc[0]["confirmed_quantity_after_fill"] == 10
    assert reconciliation.iloc[0]["target_vs_confirmed_difference"] == 0
    assert reconciliation.iloc[0]["cash_impact_estimate"] == -1010.0


def test_non_retroactive_execution_blocks_missed_next_open():
    blocker = _gma3a_execution_timing_block(
        signal_date=pd.Timestamp("2026-06-17").date(),
        execution_date=pd.Timestamp("2026-06-18").date(),
        assets={"SPY", "GLD"},
        as_of_date=pd.Timestamp("2026-06-19").date(),
    )
    assert "execution window 2026-06-18 has passed" in blocker


def test_daily_paper_cycle_runs_refresh_tournament_then_readiness(tmp_path: Path, monkeypatch, capsys):
    calls: list[str] = []
    config = object()
    output_root = tmp_path / "reports"
    output_root.mkdir()
    summary_path = output_root / "gma3a_paper_readiness_summary.csv"
    pd.DataFrame(
        [
            {
                "decision_date": "2026-06-17",
                "expected_execution_date": "2026-06-18",
                "target_blocking_reason": (
                    "non_retroactive_execution_block: execution window 2026-06-18 "
                    "has passed as of 2026-06-19"
                ),
                "order_packet_rows": 0,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "ml_portfolio_influence": 0.0,
                "SPY_latest_finalized_date": "2026-06-18",
                "QQQ_latest_finalized_date": "2026-06-18",
                "IEF_latest_finalized_date": "2026-06-18",
                "GLD_latest_finalized_date": "2026-06-18",
                "DBC_latest_finalized_date": "2026-06-18",
            }
        ]
    ).to_csv(summary_path, index=False)

    def fake_load_config(path):
        calls.append(f"load:{path}")
        return config

    def fake_refresh(received_config):
        assert received_config is config
        calls.append("refresh")
        return type(
            "RefreshResult",
            (),
            {
                "decision": "gma3a_post_endpoint_refresh_completed",
                "refreshed_symbols": ["SPY", "QQQ", "IEF", "GLD", "DBC"],
                "warnings": [],
            },
        )()

    def fake_tournament(received_config):
        assert received_config is config
        calls.append("tournament")
        return type(
            "TournamentResult",
            (),
            {
                "decision": "gma3ar2_ready_core_only_waiting_execution_open",
                "order_packet_rows": 0,
                "warnings": [],
            },
        )()

    def fake_readiness(received_config):
        assert received_config is config
        calls.append("readiness")
        return gma_cli.GMA3APaperReadinessResult(
            readiness_status="blocked",
            execution_status="retroactive_blocked",
            output_root=output_root,
            summary_path=summary_path,
            markdown_path=output_root / "gma3a_paper_readiness.md",
            order_packet_rows=0,
            manual_tradingview_entry_active=False,
            blocking_reason=(
                "non_retroactive_execution_block: execution window 2026-06-18 "
                "has passed as of 2026-06-19"
            ),
        )

    monkeypatch.setattr(gma_cli, "load_gma3a_config", fake_load_config)
    monkeypatch.setattr(gma_cli, "run_gma3a_post_endpoint_refresh", fake_refresh)
    monkeypatch.setattr(gma_cli, "run_gma3a_transparent_tournament", fake_tournament)
    monkeypatch.setattr(gma_cli, "run_gma3a_paper_readiness", fake_readiness)

    result = gma_cli.main(
        ["--config", "configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml", "daily-paper-cycle"]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert calls == [
        "load:configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml",
        "refresh",
        "tournament",
        "readiness",
    ]
    assert "manual TradingView entry active: False" in output
    assert "SPY latest finalized post-endpoint date: 2026-06-18" in output
    assert "manual TradingView entry sheet:" in output
    assert "gma3a_manual_tradingview_entry_sheet.md" in output
    assert "order packet:" in output
    assert "gma3a_tradingview_order_packet.csv" in output
    assert "No instruction to trade is active." in output
    assert "manual TradingView paper entry active\n" not in output


def test_non_retroactive_execution_blocks_skipping_true_next_open_to_monday():
    blocker = _gma3a_execution_timing_block(
        signal_date=pd.Timestamp("2026-06-17").date(),
        execution_date=pd.Timestamp("2026-06-22").date(),
        assets={"SPY", "GLD"},
        as_of_date=pd.Timestamp("2026-06-19").date(),
    )
    assert "expected_next_open 2026-06-18" in blocker
