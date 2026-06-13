from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
    build_calculated_feature_registry,
    build_pilot_panel_and_targets,
    calculate_security_features,
    save_phase23f_pilot_individual_equity_feature_calculation,
    validate_membership_manifest,
    validate_pilot_panel,
    validate_price_frame,
)


def _price_frame(multiplier: float = 1.0, rows: int = 420) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=rows)
    trend = np.linspace(100.0, 180.0, rows) * multiplier
    wave = np.sin(np.arange(rows) / 15.0) * multiplier
    close = trend + wave
    return pd.DataFrame(
        {
            "date": dates,
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "adj_close": close,
            "volume": np.full(rows, 2_000_000.0),
        }
    )


def _manifest() -> pd.DataFrame:
    rows = []
    for index, ticker in enumerate(["AAA", "BBB", "CCC"], start=1):
        rows.append(
            {
                "universe_id": "SP500_PILOT_NONCANONICAL",
                "permanent_security_id": f"SEC{index}",
                "permanent_company_id": f"COMP{index}",
                "ticker": ticker,
                "sector": "Technology",
                "industry": "Software",
                "membership_start_date": "2020-01-01",
                "membership_end_date": "",
                "membership_known_timestamp_utc": "2020-01-01T00:00:00Z",
                "price_file": f"{ticker}.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            }
        )
    return pd.DataFrame(rows)


def _phase_config() -> dict:
    return {
        "pilot_start_date": "2023-01-03",
        "pilot_end_date": "2024-08-01",
        "decision_weekday": "FRIDAY",
        "decision_time_utc": "22:00:00",
        "market_data_available_time_utc": "21:05:00",
        "minimum_securities": 3,
        "minimum_price_rows": 320,
        "minimum_average_dollar_volume": 1_000_000.0,
        "feature_set_version": "phase23f_test_v1",
        "target_set_version": "phase23f_targets_test_v1",
    }


def test_manifest_validator_accepts_explicit_noncanonical_research_pilot():
    report = validate_membership_manifest(_manifest())
    assert report["passed"].all()


def test_manifest_validator_rejects_canonical_claim_before_phase23b():
    manifest = _manifest()
    manifest.loc[0, "canonical_membership"] = True
    report = validate_membership_manifest(manifest)
    row = report.loc[report["gate"].eq("pilot_is_noncanonical")].iloc[0]
    assert not bool(row["passed"])


def test_price_validator_and_feature_calculation_produce_core_metrics():
    prices = _price_frame()
    report = validate_price_frame(prices, minimum_price_rows=320)
    assert report["passed"].all()
    features = calculate_security_features(prices, benchmark=_price_frame(0.95))
    latest = features.iloc[-1]
    assert latest["momentum_21d"] > 0
    assert latest["momentum_63d"] > 0
    assert pd.notna(latest["momentum_252d_skip21d"])
    assert pd.notna(latest["beta_252d"])
    assert latest["average_dollar_volume_20d"] > 1_000_000


def test_feature_registry_matches_phase23e_pilot_subset():
    registry = build_calculated_feature_registry()
    assert set(CORE_FEATURE_COLUMNS) == set(registry["feature_name"])
    assert set(registry["feature_family"]) == {
        "technical",
        "liquidity_risk",
        "market_stress",
    }


def test_end_to_end_pilot_builder_calculates_panel_targets_and_leak_safe_clocks():
    prices = {
        "SEC1": _price_frame(1.00),
        "SEC2": _price_frame(1.05),
        "SEC3": _price_frame(0.95),
    }
    panel, targets, inventory = build_pilot_panel_and_targets(
        manifest=_manifest(),
        price_frames=prices,
        benchmark=_price_frame(0.90),
        phase_config=_phase_config(),
    )
    assert not panel.empty
    assert not targets.empty
    assert len(inventory) == 3
    assert panel["permanent_security_id"].nunique() == 3
    assert "ticker" in panel.columns
    assert panel["ticker"].astype(str).str.strip().ne("").all()
    assert panel["ticker"].astype(str).eq(panel["ticker_asof"].astype(str)).all()
    assert set(CORE_FEATURE_COLUMNS).issubset(panel.columns)
    assert not any(
        column.startswith("forward_") or column.startswith("target_")
        for column in panel.columns
    )
    assert "forward_20d_excess_return_vs_universe" in set(targets["target_name"])
    assert "forward_20d_positive_alpha_probability" in set(targets["target_name"])
    assert not targets.duplicated(["panel_row_id", "target_name"]).any()
    assert (
        pd.to_datetime(panel["feature_max_available_timestamp_utc"], utc=True)
        <= pd.to_datetime(panel["model_cutoff_timestamp_utc"], utc=True)
    ).all()
    validation = validate_pilot_panel(panel, targets)
    assert validation["passed"].all()
    expected_gates = {
        "nonblank_ticker_and_identifiers",
        "ticker_matches_ticker_asof",
        "one_stock_row_per_decision_timestamp",
        "target_unique_per_panel_row_and_name",
        "no_target_columns_in_predictor_panel",
        "feature_values_finite",
        "cross_sectional_breadth_and_dispersion_consistent",
        "no_model_or_order_outputs",
    }
    assert expected_gates.issubset(set(validation["gate"]))


def test_pilot_validator_rejects_future_feature_availability():
    prices = {
        "SEC1": _price_frame(1.00),
        "SEC2": _price_frame(1.05),
        "SEC3": _price_frame(0.95),
    }
    panel, targets, _ = build_pilot_panel_and_targets(
        manifest=_manifest(),
        price_frames=prices,
        benchmark=_price_frame(0.90),
        phase_config=_phase_config(),
    )
    panel.loc[0, "feature_max_available_timestamp_utc"] = "2030-01-01T00:00:00Z"
    report = validate_pilot_panel(panel, targets)
    row = report.loc[
        report["gate"].eq("feature_availability_not_after_cutoff")
    ].iloc[0]
    assert not bool(row["passed"])


def test_phase23f_without_inputs_writes_templates_and_pending_summary(tmp_path: Path):
    config = {
        "phase23f_pilot_individual_equity_feature_calculation": {
            "enabled": True,
            "output_dir": (
                "reports/individual_equity_decision_system/"
                "phase23f_pilot_feature_calculation"
            ),
            "dashboard_status_path": (
                "reports/paper_trading/dashboard/"
                "phase23f_pilot_feature_calculation_status.csv"
            ),
            "input_dir": "data/individual_equity_pilot",
            "membership_manifest_path": (
                "data/individual_equity_pilot/pilot_membership_manifest.csv"
            ),
            "benchmark_path": "data/individual_equity_pilot/benchmark_SPY.csv",
        }
    }
    outputs = save_phase23f_pilot_individual_equity_feature_calculation(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    summary = outputs["summary"].iloc[0]
    assert bool(summary["feature_calculation_engine_ready"])
    assert not bool(summary["pilot_input_data_ready"])
    assert not bool(summary["pilot_panel_built"])
    assert not bool(summary["model_training_allowed"])
    assert not bool(summary["backtest_allowed"])
    assert not bool(summary["live_trading_allowed"])
    output_dir = (
        tmp_path
        / "reports"
        / "individual_equity_decision_system"
        / "phase23f_pilot_feature_calculation"
    )
    assert (output_dir / "phase23f_summary.csv").exists()
    assert (output_dir / "phase23f_pilot_membership_manifest_template.csv").exists()
    assert (output_dir / "phase23f_pilot_price_template.csv").exists()
    assert not (tmp_path / "reports" / "reports").exists()


def test_phase23f_with_local_inputs_writes_panel_and_targets(tmp_path: Path):
    input_dir = tmp_path / "data" / "individual_equity_pilot"
    input_dir.mkdir(parents=True)
    manifest = _manifest()
    manifest.to_csv(input_dir / "pilot_membership_manifest.csv", index=False)
    for index, ticker in enumerate(["AAA", "BBB", "CCC"], start=1):
        _price_frame(0.9 + index * 0.05).to_csv(input_dir / f"{ticker}.csv", index=False)
    _price_frame(0.9).to_csv(input_dir / "benchmark_SPY.csv", index=False)

    config = {
        "phase23f_pilot_individual_equity_feature_calculation": {
            "enabled": True,
            "output_dir": "reports/phase23f",
            "dashboard_status_path": "reports/dashboard/phase23f.csv",
            "input_dir": "data/individual_equity_pilot",
            "membership_manifest_path": (
                "data/individual_equity_pilot/pilot_membership_manifest.csv"
            ),
            "benchmark_path": "data/individual_equity_pilot/benchmark_SPY.csv",
            **_phase_config(),
        }
    }
    outputs = save_phase23f_pilot_individual_equity_feature_calculation(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    summary = outputs["summary"].iloc[0]
    assert bool(summary["pilot_input_data_ready"])
    assert bool(summary["pilot_panel_built"])
    assert bool(summary["pilot_panel_validation_passed"])
    assert (
        summary["phase23f_decision"]
        == "phase23f_pilot_panel_validated_ready_for_phase23g"
    )
    assert (
        summary["next_phase"]
        == "Phase 23G first interpretable cross-sectional stock-ranking model"
    )
    assert int(summary["pilot_security_count"]) == 3
    output_dir = tmp_path / "reports" / "phase23f"
    assert (output_dir / "phase23f_pilot_feature_panel.csv").exists()
    assert (output_dir / "phase23f_pilot_targets.csv").exists()
