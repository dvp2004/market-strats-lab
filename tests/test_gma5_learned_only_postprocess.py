from market_strats.global_multi_asset.gma5_learned_only_postprocess import (
    LEARNED_ONLY_START,
    PRE_MODEL_POLICY,
    VARIANTS,
    build_scoreboard_rows,
    build_transition_rows,
)


def test_metrics_calculated_only_from_saved_paths_and_absent_paths() -> None:
    # 1. metrics are calculated only from date-indexed saved clean-run paths
    # 2. absent path data produces not_available_from_saved_artifacts
    rows = build_scoreboard_rows([])
    for row in rows:
        if row["variant_id"] in VARIANTS:
            assert row["measurement_status"] == "not_available_from_saved_artifacts"
            assert row["net_cagr"] == ""

    # Provide valid paths
    valid_rows = [
        {
            "date": "2015-05-29",
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "cost_scenario": "baseline_1bps",
            "portfolio_value": "1.0",
            "trade_delta": "0.1",
            "transaction_cost": "0.001",
        },
        {
            "date": "2016-05-29",
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "cost_scenario": "baseline_1bps",
            "portfolio_value": "1.1",
            "trade_delta": "0.1",
            "transaction_cost": "0.001",
        },
    ]
    res = build_scoreboard_rows(valid_rows)
    found = False
    for row in res:
        if (
            row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
            and row["cost_scenario"] == "baseline_1bps"
        ):
            assert row["measurement_status"] == "available_from_saved_artifacts"
            assert float(row["net_cagr"]) > 0
            found = True
    assert found


def test_learned_only_start_and_ridge_pre_model_state() -> None:
    # 3. learned-only start is exactly 2015-05-29
    # 5. ridge pre-model state is read from saved targets/ledger
    target_rows = [
        {
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "decision_date": "2012-05-31",
            "symbol": "BIL",
            "composite_etf_target_weight": "1.0",
        },
        {
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "decision_date": "2015-04-30",
            "symbol": "BIL",
            "composite_etf_target_weight": "1.0",
        },
    ]
    weight_rows = [
        {
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "decision_date": "2015-05-29",
            "sleeve_id": "s1",
            "sleeve_allocation_weight": "0.5",
            "status": "available",
        },
    ]
    ledger_rows = [
        {
            "variant_id": "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
            "date": "2015-05-29",
            "cost_scenario": "baseline_1bps",
            "portfolio_value": "1.0",
        },
    ]
    training_rows = [
        {
            "decision_date": "2015-05-29",
            "sleeve_id": "s1",
            "training_row_count": "100",
            "ridge_alpha": "1.0",
        }
    ]
    manifest = {"first_true_learned_ridge_decision": "2015-05-29"}

    transition = build_transition_rows(
        target_rows, weight_rows, ledger_rows, training_rows, manifest
    )
    assert len(transition) == 1
    assert transition[0]["learned_only_window_start_date"] == LEARNED_ONLY_START
    assert transition[0]["actual_pre_model_target_state"] == "bil_only_targets"
    assert transition[0]["pre_model_policy"] == PRE_MODEL_POLICY
