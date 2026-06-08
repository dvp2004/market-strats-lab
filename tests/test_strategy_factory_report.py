from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.strategy_factory_report import (
    classify_strategy,
    save_phase17a_strategy_factory_report,
)


def _synthetic_price_data() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-02", periods=700)
    specs = {
        "SPY": (0.00045, 0.010),
        "QQQ": (0.00075, 0.014),
        "GLD": (0.00020, 0.008),
        "TLT": (0.00010, 0.007),
        "BTC-USD": (0.00110, 0.030),
    }
    out = {}
    for idx, (ticker, (mean, vol)) in enumerate(specs.items()):
        rng = np.random.default_rng(200 + idx)
        returns = rng.normal(mean, vol, len(dates))
        returns[:240] = abs(returns[:240]) + mean
        prices = 100 * (1 + pd.Series(returns)).cumprod()
        out[ticker] = pd.DataFrame({"date": dates, "adj_close": prices})
    return out


def _config(tmp_path: Path) -> dict:
    return {
        "start_date": "2020-01-02",
        "end_date": None,
        "use_cash_yield": False,
        "phase17a_strategy_factory": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "strategy_factory"),
            "chart_dir": str(tmp_path / "reports" / "strategy_factory" / "charts"),
            "dashboard_dir": str(tmp_path / "reports" / "strategy_factory" / "dashboard"),
            "initial_capital": 10000,
            "universe": ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"],
            "include_cash": True,
            "btc_max_weight": 0.10,
            "qqq_satellite_max_weight": 0.40,
            "rebalance_frequency": "M",
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        },
    }


def test_strategy_factory_report_writes_outputs_and_charts(tmp_path):
    outputs = save_phase17a_strategy_factory_report(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    output_dir = tmp_path / "reports" / "strategy_factory"
    chart_dir = output_dir / "charts"
    dashboard_dir = output_dir / "dashboard"

    assert not outputs["metrics"].empty
    assert bool(outputs["conclusion"].iloc[0]["all_gates_passed"])
    for path in [
        output_dir / "phase17a_strategy_factory_summary.csv",
        output_dir / "phase17a_strategy_factory_metrics.csv",
        output_dir / "phase17a_strategy_factory_benchmark_comparison.csv",
        output_dir / "equity_curves.csv",
        output_dir / "drawdown_curves.csv",
        output_dir / "allocation_timeline.csv",
        output_dir / "rolling_relative_performance.csv",
        output_dir / "trade_turnover_summary.csv",
        output_dir / "money_made_lost.csv",
        chart_dir / "equity_curves.png",
        chart_dir / "drawdown_curves.png",
        chart_dir / "rolling_relative_performance.png",
        chart_dir / "allocation_timeline.png",
        dashboard_dir / "index.md",
    ]:
        assert path.exists()


def test_strategy_factory_benchmark_comparison_columns_exist(tmp_path):
    outputs = save_phase17a_strategy_factory_report(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    required = {
        "candidate_minus_spy_end_value",
        "candidate_minus_spy_cagr_pct",
        "candidate_max_drawdown_advantage_vs_spy_pct_points",
        "candidate_calmar_advantage_vs_spy",
    }
    assert required.issubset(outputs["benchmark_comparison"].columns)


def test_strategy_factory_gate_classification_rules():
    benchmark = pd.Series({"cagr_pct": 10.0, "end_value": 20000.0, "max_drawdown_pct": -45.0})

    assert (
        classify_strategy(
            pd.Series({"cagr_pct": 11.0, "end_value": 22000.0, "max_drawdown_pct": -50.0}),
            benchmark,
        )
        == "growth_candidate"
    )
    assert (
        classify_strategy(
            pd.Series({"cagr_pct": 9.6, "end_value": 19000.0, "max_drawdown_pct": -30.0}),
            benchmark,
        )
        == "balanced_candidate"
    )
    assert (
        classify_strategy(
            pd.Series({"cagr_pct": 8.0, "end_value": 17000.0, "max_drawdown_pct": -20.0}),
            benchmark,
        )
        == "defensive_candidate"
    )
    assert (
        classify_strategy(
            pd.Series({"cagr_pct": 7.0, "end_value": 14000.0, "max_drawdown_pct": -44.0}),
            benchmark,
        )
        == "rejected"
    )


def test_strategy_factory_output_safety_flags_remain_false(tmp_path):
    outputs = save_phase17a_strategy_factory_report(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
        price_data=_synthetic_price_data(),
    )

    conclusion = outputs["conclusion"].iloc[0]
    gates = outputs["gate_report"]
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])
    assert not bool(gates["live_trading_allowed"].any())
    assert not bool(gates["real_money_allowed"].any())
    assert not bool(gates["broker_api_integration_allowed"].any())
