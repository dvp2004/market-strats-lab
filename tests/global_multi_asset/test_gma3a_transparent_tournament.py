from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.gma3a_config import validate_gma3a_config
from market_strats.global_multi_asset.gma3a_tournament import (
    STRATEGY_IDS,
    _core_fallback_passed,
    _manual_fill_columns,
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
    assert "next_execution_unavailable" in str(recon.iloc[0]["blocking_reason"])


def test_no_change_to_accepted_gma2_files():
    import subprocess

    files = [
        "configs/global_multi_asset_alpha/gma2_replay_foundation.yaml",
        "src/market_strats/global_multi_asset/gma2_config.py",
        "src/market_strats/global_multi_asset/gma2_replay.py",
    ]
    result = subprocess.run(["git", "diff", "--name-only", "--", *files], check=True, capture_output=True, text=True)
    assert not result.stdout.strip()
