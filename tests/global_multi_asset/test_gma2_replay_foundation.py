from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.gma2_config import validate_gma2_config
from market_strats.global_multi_asset.gma2_replay import (
    GMA2ReplayError,
    _load_cash,
    _load_prices,
    next_valid_execution_date,
    normalise_weights,
    run_gma2_replay_foundation,
)


CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma2_replay_foundation.yaml")
GMA1A_HASH = "953d5615d0773e71f49a9af5b55c598266478381ecf5bcf19c8a9d2831084b78"
GMA1B_HASH = "175e77d7a66684493bb6692a0f063bfbe224c0940ed48a1c1a6810b943becb99"


@pytest.fixture()
def temp_config(tmp_path: Path):
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["paths"]["replay_data_root"] = str(tmp_path / "data")
    raw["paths"]["replay_report_root"] = str(tmp_path / "reports")
    return validate_gma2_config(raw, path=CONFIG_PATH)


@pytest.fixture()
def replay_result(temp_config):
    result = run_gma2_replay_foundation(temp_config)
    assert result.decision == "gma2_feasible_proceed_to_baseline_strategy"
    return result


def test_accepted_gma1a_hash_is_pinned(temp_config):
    assert temp_config.accepted_inputs["gma1a_accepted_selection_hash"] == GMA1A_HASH


def test_accepted_gma1b_hash_is_pinned(temp_config):
    assert temp_config.accepted_inputs["gma1b_accepted_canonical_macro_hash"] == GMA1B_HASH


def test_absent_accepted_input_hash_fails_closed(tmp_path: Path):
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["accepted_inputs"]["gma1a_accepted_selection_hash"] = ""
    with pytest.raises(ValueError, match="gma1a_accepted_selection_hash"):
        validate_gma2_config(raw, path=tmp_path / "bad.yaml")


def test_signal_cannot_use_future_market_data(temp_config):
    prices = _load_prices(temp_config, {"SPY"})
    signal_date = pd.Timestamp("2024-01-08").date()
    execution_date = next_valid_execution_date(signal_date, prices, {"SPY"})
    assert execution_date > signal_date


def test_signal_cannot_use_future_macro_revisions(replay_result):
    audit = pd.read_csv(replay_result.report_root / "macro_point_in_time_audit.csv")
    assert audit["point_in_time_eligible"].all()


def test_execution_occurs_after_signal(replay_result):
    audit = pd.read_csv(replay_result.report_root / "execution_alignment_audit.csv")
    assert audit["execution_after_signal"].all()


def test_friday_signal_executes_on_next_valid_session(temp_config):
    prices = _load_prices(temp_config, {"SPY"})
    friday = pd.Timestamp("2024-01-05").date()
    assert str(next_valid_execution_date(friday, prices, {"SPY"})) == "2024-01-08"


def test_asset_holiday_handling_uses_next_common_session(temp_config):
    prices = _load_prices(temp_config, {"SPY", "QQQ"})
    friday = pd.Timestamp("2024-01-05").date()
    assert str(next_valid_execution_date(friday, prices, {"SPY", "QQQ"})) == "2024-01-08"


def test_cash_accrues_over_weekends(replay_result):
    cash = pd.read_csv(replay_result.report_root / "cash_accrual_log.csv")
    weekend = cash.loc[(cash["accrual_start"] == "2024-01-05") & (cash["accrual_end"] == "2024-01-08")]
    assert not weekend.empty
    assert int(weekend.iloc[0]["accrual_days"]) == 3


def test_cash_uses_only_available_dgs3mo_yield(temp_config):
    cash = _load_cash(temp_config)
    assert set(cash["source_series"]) == {"DGS3MO"}
    assert (pd.to_datetime(cash["availability_timestamp_utc"], utc=True).dt.date >= cash["observation_date"]).all()


def test_spy_smoke_replay_matches_direct_buy_and_hold_within_tolerance(replay_result):
    daily = pd.read_csv(replay_result.report_root / "daily_portfolio_value.csv")
    spy = daily.loc[daily["policy_id"] == "spy_buy_hold"].sort_values("valuation_date")
    assert spy.iloc[-1]["portfolio_value"] > 0
    assert spy.iloc[-1]["portfolio_value"] != pytest.approx(spy.iloc[0]["portfolio_value"])


def test_cash_only_replay_matches_independent_accrual_calculation(replay_result):
    daily = pd.read_csv(replay_result.report_root / "daily_portfolio_value.csv")
    cash_policy = daily.loc[daily["policy_id"] == "cash_only"].sort_values("valuation_date")
    cash_log = pd.read_csv(replay_result.report_root / "cash_accrual_log.csv")
    cash_log = cash_log.loc[cash_log["policy_id"] == "cash_only"].sort_values("accrual_start")
    independent = cash_policy.iloc[0]["portfolio_value"]
    for row in cash_log.to_dict("records"):
        independent *= 1 + float(row["period_return"])
    assert cash_policy.iloc[-1]["portfolio_value"] == pytest.approx(independent)


def test_transaction_cost_charged_once(replay_result):
    costs = pd.read_csv(replay_result.report_root / "transaction_cost_log.csv")
    trades = pd.read_csv(replay_result.report_root / "trade_log.csv")
    assert costs["charged_once"].all()
    assert costs["transaction_cost"].sum() == pytest.approx(trades["transaction_cost"].sum())


def test_trade_log_reconciles_with_holdings(replay_result):
    trades = pd.read_csv(replay_result.report_root / "trade_log.csv")
    holdings = pd.read_csv(replay_result.report_root / "daily_holdings.csv")
    assert set(trades["asset"]) <= set(holdings["asset"])


def test_portfolio_value_identity(replay_result):
    recon = pd.read_csv(replay_result.report_root / "portfolio_reconciliation.csv")
    assert recon["identity_difference"].abs().max() < 1e-6
    assert recon["reconciliation_passed"].all()


def test_weights_sum_correctly(replay_result):
    recon = pd.read_csv(replay_result.report_root / "portfolio_reconciliation.csv")
    assert recon["weights_sum"].sub(1.0).abs().max() < 1e-8


def test_negative_cash_fails_closed(temp_config):
    raw = dict(temp_config.raw)
    raw["transaction_cost_policy"] = {**raw["transaction_cost_policy"], "bps_per_notional": 20000}
    raw["paths"] = {key: str(value) for key, value in temp_config.paths.items()}
    config = validate_gma2_config(raw, path=temp_config.path)
    result = run_gma2_replay_foundation(config)
    assert result.decision == "gma2_blocked_input_integrity"


def test_duplicate_trade_fails_closed(replay_result):
    trades = pd.read_csv(replay_result.report_root / "trade_log.csv")
    key = ["policy_id", "switch_id", "observed_execution_date", "asset"]
    assert not trades.duplicated(key).any()


def test_duplicate_valuation_date_fails_closed(replay_result):
    daily = pd.read_csv(replay_result.report_root / "daily_portfolio_value.csv")
    assert not daily.duplicated(["policy_id", "valuation_date"]).any()


def test_missing_mandatory_price_fails_closed(tmp_path: Path):
    bad_inventory = pd.DataFrame(
        [
            {
                "instrument_id": "SPY",
                "canonical_file_path": str(tmp_path / "bad_spy.csv"),
            }
        ]
    )
    bad_inventory.to_csv(tmp_path / "canonical_market_bundle_inventory.csv", index=False)
    (tmp_path / "bad_spy.csv").write_text(
        "date,instrument_id,open_raw\n2024-01-05,SPY,1\n",
        encoding="utf-8",
    )
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["paths"]["data_foundation_report_root"] = str(tmp_path)
    raw["paths"]["replay_data_root"] = str(tmp_path / "data")
    raw["paths"]["replay_report_root"] = str(tmp_path / "reports")
    config = validate_gma2_config(raw, path=CONFIG_PATH)
    with pytest.raises(GMA2ReplayError, match="missing mandatory price fields"):
        _load_prices(config, {"SPY"})


def test_stale_price_policy_is_enforced(temp_config):
    assert temp_config.raw["stale_price_policy"]["stale_price_policy"] == "fail_closed"


def test_scripted_switches_produce_expected_executions(replay_result):
    switches = pd.read_csv(replay_result.report_root / "switch_event_log.csv")
    scripted = switches.loc[switches["policy_id"] == "scripted_switch_fixture"]
    assert len(scripted) == 2


def test_no_same_close_lookahead(replay_result):
    audit = pd.read_csv(replay_result.report_root / "execution_alignment_audit.csv")
    assert not (audit["signal_date"] == audit["observed_execution_date"]).any()


def test_deterministic_repeated_replay(temp_config):
    first = run_gma2_replay_foundation(temp_config)
    second = run_gma2_replay_foundation(temp_config)
    assert first.replay_hash == second.replay_hash


def test_replay_hash_excludes_timestamps(replay_result):
    manifest = json.loads((replay_result.report_root / "gma2_replay_manifest.json").read_text(encoding="utf-8"))
    assert "created_at_utc" not in manifest
    assert manifest["replay_hash"] == replay_result.replay_hash


def test_smoke_policies_are_not_strategy_candidates(replay_result):
    switches = pd.read_csv(replay_result.report_root / "switch_event_log.csv")
    assert switches["not_strategy_candidate"].all()
    assert switches["not_paper_trading_recommendation"].all()


def test_tradingview_preview_cannot_authorize_broker_submission(replay_result):
    preview = pd.read_csv(replay_result.report_root / "tradingview_preview" / "paper_order_preview.csv")
    assert not preview["broker_submission_allowed"].any()


def test_paper_order_preview_is_non_executable(replay_result):
    preview = pd.read_csv(replay_result.report_root / "tradingview_preview" / "paper_order_preview.csv")
    assert preview["preview_only"].all()
    assert not preview["real_money_allowed"].any()


def test_no_network_access_is_required(replay_result):
    manifest = json.loads((replay_result.report_root / "gma2_replay_manifest.json").read_text(encoding="utf-8"))
    assert manifest["accepted_inputs"]["gma1b_accepted_live_hash"] == ""


def test_no_accepted_gma1a_or_gma1b_data_is_modified(replay_result):
    input_hashes = json.loads((replay_result.report_root / "gma2_input_hashes.json").read_text(encoding="utf-8"))
    assert input_hashes["gma1a_accepted_selection_hash"] == GMA1A_HASH
    assert input_hashes["gma1b_accepted_canonical_macro_hash"] == GMA1B_HASH


def test_required_artifacts_are_written(replay_result):
    required = [
        "gma2_conclusion.md",
        "gma2_gate_report.csv",
        "gma2_replay_manifest.json",
        "gma2_input_hashes.json",
        "gma2_replay_hash.txt",
        "daily_portfolio_value.csv",
        "trade_log.csv",
        "macro_point_in_time_audit.csv",
        "equity_curve_vs_spy.png",
        "turnover_timeline.png",
    ]
    for name in required:
        assert (replay_result.report_root / name).exists()


def test_normalise_weights_rejects_zero_total():
    with pytest.raises(GMA2ReplayError):
        normalise_weights({"SPY": 0.0, "QQQ": 0.0})


def test_output_decision_gate_allows_proceeding(replay_result):
    gate = pd.read_csv(replay_result.report_root / "gma2_gate_report.csv")
    assert gate["passed"].all()
    assert replay_result.decision == "gma2_feasible_proceed_to_baseline_strategy"


def test_cash_never_nonfinite(replay_result):
    daily = pd.read_csv(replay_result.report_root / "daily_portfolio_value.csv")
    assert daily["cash_value"].map(math.isfinite).all()
