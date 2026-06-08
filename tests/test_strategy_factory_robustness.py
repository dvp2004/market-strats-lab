from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.strategy_factory_robustness import (
    apply_turnover_friction,
    create_btc_weekend_gap_diagnostic,
    save_phase17b_strategy_factory_robustness,
)
from market_strats.strategies.strategy_factory import (
    StrategyFactoryConfig,
    build_strategy_factory_price_panel,
    run_strategy_factory_candidates,
)


def _synthetic_price_data(periods: int = 1100) -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2018-01-02", periods=periods)
    specs = {
        "SPY": (0.00042, 0.010),
        "QQQ": (0.00072, 0.014),
        "GLD": (0.00018, 0.008),
        "TLT": (0.00008, 0.007),
        "BTC-USD": (0.00105, 0.030),
    }
    out = {}
    for idx, (ticker, (mean, vol)) in enumerate(specs.items()):
        rng = np.random.default_rng(700 + idx)
        returns = rng.normal(mean, vol, len(dates))
        returns[:260] = abs(returns[:260]) + mean
        prices = 100 * (1 + pd.Series(returns)).cumprod()
        out[ticker] = pd.DataFrame({"date": dates, "adj_close": prices})
    return out


def _config(tmp_path: Path, *, live_flag: bool = False) -> dict:
    output_dir = tmp_path / "reports" / "strategy_factory"
    return {
        "start_date": "2018-01-02",
        "end_date": None,
        "use_cash_yield": False,
        "phase17a_strategy_factory": {
            "enabled": True,
            "output_dir": str(output_dir),
            "chart_dir": str(output_dir / "charts"),
            "dashboard_dir": str(output_dir / "dashboard"),
            "initial_capital": 10000,
            "universe": ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"],
            "include_cash": True,
            "btc_max_weight": 0.10,
            "qqq_satellite_max_weight": 0.40,
            "rebalance_frequency": "M",
            "momentum_lookback_days": 126,
            "trend_lookback_days": 200,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
        "phase17b_strategy_factory_robustness": {
            "enabled": True,
            "output_dir": str(output_dir),
            "chart_dir": str(output_dir / "charts"),
            "dashboard_dir": str(output_dir / "dashboard"),
            "friction_scenarios": {
                "no_extra_cost": {"bps_per_turnover": 0},
                "low": {"bps_per_turnover": 5},
                "moderate": {"bps_per_turnover": 15},
                "realistic_stress": {"bps_per_turnover": 25},
                "stress": {"bps_per_turnover": 50},
            },
            "btc_specific_extra_bps": {
                "low": 10,
                "moderate": 25,
                "realistic_stress": 50,
                "stress": 75,
            },
            "rolling_windows_trading_days": [252, 756],
            "subperiods": {
                "covid_inflation": {"start": "2020-01-01", "end": "2021-12-31"},
                "post_2021": {"start": "2021-01-01", "end": None},
            },
            "live_trading_allowed": live_flag,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
    }


def test_phase17b_friction_costs_reduce_or_do_not_increase_returns():
    panel = build_strategy_factory_price_panel(_synthetic_price_data())
    results, _status = run_strategy_factory_candidates(
        panel,
        config=StrategyFactoryConfig(initial_capital=10000),
    )
    result = results["sf_spy_qqq_60_40_monthly_rebalanced"]

    no_cost = apply_turnover_friction(
        result,
        bps_per_turnover=0,
        scenario_name="no_extra_cost",
    )
    stress = apply_turnover_friction(
        result,
        bps_per_turnover=50,
        scenario_name="stress",
    )

    assert float(stress["equity"].iloc[-1]) <= float(no_cost["equity"].iloc[-1])
    assert float(stress["friction_cost_return"].sum()) > 0.0


def test_phase17b_writes_outputs_and_charts(tmp_path):
    outputs = save_phase17b_strategy_factory_robustness(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    output_dir = tmp_path / "reports" / "strategy_factory"
    chart_dir = output_dir / "charts"
    dashboard_dir = output_dir / "dashboard"

    assert not outputs["friction_metrics"].empty
    assert bool(outputs["conclusion"].iloc[0]["all_gates_passed"])
    for path in [
        output_dir / "phase17b_strategy_factory_robustness_summary.csv",
        output_dir / "phase17b_friction_metrics.csv",
        output_dir / "phase17b_friction_scenario_comparison.csv",
        output_dir / "phase17b_non_btc_long_period_metrics.csv",
        output_dir / "phase17b_btc_cap_sensitivity.csv",
        output_dir / "phase17b_btc_weekend_gap_diagnostic.csv",
        output_dir / "phase17b_rolling_relative_summary.csv",
        output_dir / "phase17b_subperiod_metrics.csv",
        output_dir / "phase17b_shortlist_decision.csv",
        output_dir / "phase17b_gate_report.csv",
        output_dir / "phase17b_conclusion.csv",
        chart_dir / "phase17b_friction_cagr.png",
        chart_dir / "phase17b_friction_max_drawdown.png",
        chart_dir / "phase17b_btc_cap_sensitivity.png",
        chart_dir / "phase17b_btc_weekend_gap_distribution.png",
        chart_dir / "phase17b_non_btc_long_period_equity.png",
        chart_dir / "phase17b_rolling_relative_1y.png",
        chart_dir / "phase17b_rolling_relative_3y.png",
        dashboard_dir / "index.md",
    ]:
        assert path.exists()

    assert "realistic_stress" in set(outputs["friction_metrics"]["friction_scenario"])
    assert bool(outputs["btc_weekend_gap_diagnostic"].iloc[0]["diagnostic_available"])


def test_phase17b_btc_cap_sensitivity_respects_caps(tmp_path):
    outputs = save_phase17b_strategy_factory_robustness(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    sensitivity = outputs["btc_cap_sensitivity"]
    assert set(sensitivity["btc_max_weight"].round(2)) == {0.00, 0.05, 0.10}
    assert (
        sensitivity["max_observed_btc_weight"].astype(float)
        <= sensitivity["btc_max_weight"].astype(float) + 1e-10
    ).all()


def test_phase17b_non_btc_long_period_excludes_btc_candidate(tmp_path):
    outputs = save_phase17b_strategy_factory_robustness(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    metrics = outputs["non_btc_long_period_metrics"]
    assert "sf_spy_qqq_btc_capped_offensive" not in set(metrics["strategy"])
    assert not bool(metrics["btc_included"].any())


def test_phase17b_shortlist_and_safety_flags_are_generated(tmp_path):
    outputs = save_phase17b_strategy_factory_robustness(
        config=_config(tmp_path, live_flag=True),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    shortlist = outputs["shortlist_decision"]
    gates = outputs["gate_report"]
    conclusion = outputs["conclusion"].iloc[0]
    assert not shortlist.empty
    assert "phase17b_classification" in shortlist.columns
    assert "promotion_allowed" in shortlist.columns
    assert not bool(shortlist["promotion_allowed"].any())
    assert "rolling_3y_beats_spy_reference_threshold" in shortlist.columns
    assert "rolling_3y_beats_spy_reference_passed" in shortlist.columns
    btc_row = shortlist.loc[shortlist["strategy"] == "sf_spy_qqq_btc_capped_offensive"].iloc[0]
    assert bool(btc_row["btc_cap_dependency_flag"])
    assert "failed" in set(gates["gate_status"])
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])


def test_phase17b_rolling_summary_includes_active_cagr_fields(tmp_path):
    outputs = save_phase17b_strategy_factory_robustness(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    required = {
        "rolling_1y_candidate_beats_spy_pct",
        "rolling_3y_candidate_beats_spy_pct",
        "worst_1y_active_cagr",
        "worst_3y_active_cagr",
        "median_1y_active_cagr",
        "median_3y_active_cagr",
        "latest_1y_active_cagr",
        "latest_3y_active_cagr",
    }
    assert required.issubset(outputs["rolling_relative_summary"].columns)


def test_phase17b_btc_weekend_gap_placeholder_writes_when_data_unavailable():
    summary, gaps = create_btc_weekend_gap_diagnostic(
        None,
        btc_source_path="missing/BTC-USD.parquet",
    )

    row = summary.iloc[0]
    assert not bool(row["diagnostic_available"])
    assert row["blocking_reason"] == "btc_price_data_missing"
    assert gaps.empty
