from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from market_strats.analysis.dynamic_opportunity_return_enhancement import (
    V2_STRATEGIES,
    save_phase22c_dynamic_opportunity_return_enhancement,
)


def _write_price(
    root: Path,
    symbol: str,
    dates: pd.DatetimeIndex,
    drift: float,
    shock: float = 0.0,
) -> None:
    output_dir = root / "data" / "fresh" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    seasonal = np.sin(np.arange(len(dates)) / 18) * 0.001
    values = 100.0 * (1.0 + drift + seasonal).cumprod()
    if shock:
        values[-60:] *= 1.0 + shock
    pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": values * 1.01,
            "low": values * 0.99,
            "close": values,
            "adj_close": values,
            "volume": 1000,
        }
    ).to_parquet(output_dir / f"{symbol}.parquet", index=False)


def _write_benchmark_equity(root: Path, dates: pd.DatetimeIndex) -> None:
    output_dir = (
        root
        / "reports"
        / "paper_trading"
        / "regime_informed_tracking"
        / "performance"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    names = [
        "SPY Buy & Hold Benchmark",
        "phase6b_loose_relief_execution_realistic_overlay",
        "canonical_spy_qqq_gld_tlt_50_30_10_10",
        "canonical_inverse_vol_63d_btc_usd_qqq_spy",
        "canonical_spy_qqq_60_40",
    ]
    for index, name in enumerate(names):
        values = 10_000 * (1.0 + 0.0002 + index * 0.00001) ** np.arange(len(dates))
        for date, value in zip(dates, values):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "canonical_candidate_id": name,
                    "portfolio_value": value,
                }
            )
    pd.DataFrame(rows).to_csv(
        output_dir / "regime_informed_historical_daily_equity.csv",
        index=False,
    )


def _fixture_root(tmp_path: Path) -> Path:
    dates = pd.bdate_range("2020-01-01", periods=620)
    for symbol, values in {
        "SPY": (0.00035, 0.00),
        "QQQ": (0.00055, 0.03),
        "IWM": (0.00025, 0.01),
        "EFA": (0.00018, 0.00),
        "EEM": (0.00020, 0.01),
        "TLT": (0.00008, 0.00),
        "IEF": (0.00006, 0.00),
        "AGG": (0.00004, 0.00),
        "GLD": (0.00012, 0.00),
        "SLV": (0.00010, 0.02),
        "DBC": (0.00015, 0.03),
        "USO": (0.00020, 0.08),
        "VNQ": (0.00017, 0.00),
        "UUP": (0.00005, 0.00),
        "BTC-USD": (0.00070, 0.18),
    }.items():
        drift, shock = values
        _write_price(tmp_path, symbol, dates, drift, shock)
    _write_benchmark_equity(tmp_path, dates)
    return tmp_path




def _write_prior_phase_outputs(root: Path, dates: pd.DatetimeIndex) -> None:
    phase22a_dir = (
        root / "reports" / "strategy_factory" / "dynamic_opportunity_engine"
    )
    phase22b_dir = (
        root
        / "reports"
        / "strategy_factory"
        / "dynamic_opportunity_engine_diagnostics"
    )
    phase22a_dir.mkdir(parents=True, exist_ok=True)
    phase22b_dir.mkdir(parents=True, exist_ok=True)

    v0_rows = []
    for name, drift in {
        "dynamic_top3_technical_opportunity_v0": 0.00018,
        "dynamic_top5_technical_opportunity_v0": 0.00019,
        "dynamic_defensive_opportunity_v0": 0.00012,
    }.items():
        values = 10_000 * (1.0 + drift) ** np.arange(len(dates))
        for date, value in zip(dates, values):
            v0_rows.append(
                {
                    "date": date.date().isoformat(),
                    "strategy_name": name,
                    "portfolio_value": value,
                }
            )
    pd.DataFrame(v0_rows).to_csv(
        phase22a_dir / "phase22a_dynamic_strategy_daily_equity.csv",
        index=False,
    )

    v1_rows = []
    v1_drifts = {
        "dynamic_top5_opportunity_v1_sticky": 0.00020,
        "dynamic_top5_opportunity_v1_balanced": 0.00021,
        "dynamic_top3_opportunity_v1_growth_guarded": 0.00022,
        "dynamic_adaptive_core_satellite_v1": 0.00019,
    }
    for name, drift in v1_drifts.items():
        values = 10_000 * (1.0 + drift) ** np.arange(len(dates))
        for date, value in zip(dates, values):
            v1_rows.append(
                {
                    "date": date.date().isoformat(),
                    "strategy_name": name,
                    "portfolio_value": value,
                }
            )
    pd.DataFrame(v1_rows).to_csv(
        phase22b_dir / "phase22b_v1_daily_equity.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {"strategy_name": name, "CAGR": drift * 252 * 100}
            for name, drift in v1_drifts.items()
        ]
    ).to_csv(phase22b_dir / "phase22b_v1_strategy_metrics.csv", index=False)


def _config(tmp_path: Path) -> dict:
    return {
        "phase22a_dynamic_multi_asset_opportunity_engine": {
            "enabled": True,
            "output_dir": str(
                tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"
            ),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "starting_cash": 10_000,
            "transaction_cost_bps_cases": [0, 10, 25],
            "max_single_asset_weight": 0.50,
            "max_btc_weight": 0.05,
            "max_oil_weight": 0.10,
            "max_commodity_weight": 0.20,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        "phase22b_dynamic_opportunity_diagnostics": {
            "enabled": True,
            "input_dir": str(
                tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"
            ),
            "output_dir": str(
                tmp_path
                / "reports"
                / "strategy_factory"
                / "dynamic_opportunity_engine_diagnostics"
            ),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "starting_cash": 10_000,
            "transaction_cost_bps_cases": [0, 10, 25],
            "max_btc_weight": 0.05,
            "max_oil_weight": 0.10,
            "max_commodity_weight": 0.20,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
        "phase22c_dynamic_opportunity_return_enhancement": {
            "enabled": True,
            "phase22a_input_dir": str(
                tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"
            ),
            "phase22b_input_dir": str(
                tmp_path
                / "reports"
                / "strategy_factory"
                / "dynamic_opportunity_engine_diagnostics"
            ),
            "output_dir": str(
                tmp_path
                / "reports"
                / "strategy_factory"
                / "dynamic_opportunity_return_enhancement"
            ),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "starting_cash": 10_000,
            "transaction_cost_bps_cases": [0, 10, 25],
            "max_single_asset_weight": 0.50,
            "max_btc_weight": 0.05,
            "max_oil_weight": 0.10,
            "max_commodity_weight": 0.20,
            "min_cagr_improvement_vs_v1_pp": 0.25,
            "max_drawdown_worsening_vs_spy_pp": 5.0,
            "max_25bps_cagr_drag_pp": 1.0,
            "min_rolling_3y_win_rate_vs_spy": 45.0,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        },
    }


@pytest.fixture(scope="module")
def phase22c_run(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("phase22c")
    _fixture_root(tmp_path)
    dates = pd.bdate_range("2020-01-01", periods=620)
    _write_prior_phase_outputs(tmp_path, dates)
    config = _config(tmp_path)
    outputs = save_phase22c_dynamic_opportunity_return_enhancement(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    return tmp_path, outputs


def test_phase22c_writes_v2_outputs_scorecard_and_charts(phase22c_run):
    tmp_path, outputs = phase22c_run
    output_dir = (
        tmp_path
        / "reports"
        / "strategy_factory"
        / "dynamic_opportunity_return_enhancement"
    )

    for path in [
        output_dir / "phase22c_v2_strategy_metrics.csv",
        output_dir / "phase22c_v2_daily_equity.csv",
        output_dir / "phase22c_v2_daily_weights.csv",
        output_dir / "phase22c_v2_rebalance_event_log.csv",
        output_dir / "phase22c_v2_transaction_cost_sensitivity.csv",
        output_dir / "phase22c_return_enhancement_scorecard.csv",
        output_dir / "phase22c_latest_allocation_audit.csv",
        output_dir / "visuals" / "phase22c_v2_equity_curves.png",
        output_dir / "visuals" / "phase22c_return_enhancement_bar.png",
    ]:
        assert path.exists()

    assert set(outputs["v2_metrics"]["strategy_name"]) == set(V2_STRATEGIES)
    assert set(outputs["return_enhancement_scorecard"]["strategy_name"]) == set(
        V2_STRATEGIES
    )


def test_phase22c_v2_caps_and_cost_cases(phase22c_run):
    _tmp_path, outputs = phase22c_run
    weights = outputs["v2_weights"]
    costs = outputs["transaction_cost_sensitivity"]

    assert set(costs["transaction_cost_bps"]) == {0, 10, 25}
    assert weights.groupby(["date", "strategy_name"])["weight"].sum().sub(1.0).abs().max() < 1e-8
    assert weights.groupby(["date", "strategy_name"])["weight"].max().max() <= 0.500001

    btc = weights.loc[weights["asset"] == "BTC-USD"].groupby("strategy_name")["weight"].max()
    oil = weights.loc[weights["asset"] == "USO"].groupby("strategy_name")["weight"].max()
    commodities = (
        weights.loc[weights["asset"].isin(["GLD", "SLV", "DBC", "USO"])]
        .groupby(["date", "strategy_name"])["weight"]
        .sum()
    )
    assert btc.max() <= 0.050001
    assert oil.max() <= 0.100001
    assert commodities.max() <= 0.200001


def test_phase22c_events_preserve_next_day_execution_and_explanations(phase22c_run):
    _tmp_path, outputs = phase22c_run
    events = outputs["v2_events"].copy()

    assert not events.empty
    assert (pd.to_datetime(events["execution_date"]) > pd.to_datetime(events["signal_date"])).all()
    assert events["allocation_reason"].astype(str).str.len().gt(0).all()
    assert events["positive_trend_breadth"].between(0.0, 1.0).all()
    assert events["risk_budget"].between(0.0, 1.0).all()


def test_phase22c_comparison_and_safety_flags(phase22c_run):
    _tmp_path, outputs = phase22c_run
    names = set(outputs["comparison"]["strategy_name"])
    summary = outputs["summary"].iloc[0]

    assert "SPY Buy & Hold Benchmark" in names
    assert "dynamic_top5_opportunity_v1_balanced" in names
    assert set(V2_STRATEGIES).issubset(names)
    assert not bool(summary["promotion_allowed"])
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])


def test_phase22c_focused_runner_flag_exists_and_daily_runner_skips_phase22c():
    run_backtest_path = Path(__file__).resolve().parents[1] / "src" / "market_strats" / "run_backtest.py"
    source = run_backtest_path.read_text(encoding="utf-8")

    assert "--phase22c-only" in source
    assert "_run_phase22c_dynamic_opportunity_return_enhancement(" in source
    daily_start = source.index("def _run_daily_paper_workflow")
    daily_end = source.index("def main()")
    daily_source = source[daily_start:daily_end]
    assert "phase22c_dynamic_opportunity_return_enhancement" not in daily_source
