from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.run_backtest as run_backtest
from market_strats.analysis.dynamic_multi_asset_opportunity_engine import (
    save_phase22a_dynamic_multi_asset_opportunity_engine,
)
from market_strats.analysis.dynamic_opportunity_diagnostics import (
    save_phase22b_dynamic_opportunity_diagnostics,
)


def _write_price(root: Path, symbol: str, dates: pd.DatetimeIndex, drift: float, shock: float = 0.0) -> None:
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
        "QQQ": (0.00045, 0.02),
        "IWM": (0.00025, 0.01),
        "EFA": (0.00018, 0.00),
        "EEM": (0.00020, 0.01),
        "TLT": (0.00008, 0.00),
        "AGG": (0.00004, 0.00),
        "GLD": (0.00012, 0.00),
        "SLV": (0.00010, 0.02),
        "DBC": (0.00015, 0.03),
        "USO": (0.00020, 0.08),
        "VNQ": (0.00017, 0.00),
        "BTC-USD": (0.00060, 0.20),
    }.items():
        drift, shock = values
        _write_price(tmp_path, symbol, dates, drift, shock)
    _write_benchmark_equity(tmp_path, dates)
    return tmp_path


def _config(tmp_path: Path) -> dict:
    return {
        "phase22a_dynamic_multi_asset_opportunity_engine": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"),
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
            "input_dir": str(tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"),
            "output_dir": str(tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine_diagnostics"),
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
    }


def _run_phase22a_then_b(tmp_path: Path) -> dict[str, pd.DataFrame]:
    _fixture_root(tmp_path)
    config = _config(tmp_path)
    save_phase22a_dynamic_multi_asset_opportunity_engine(
        config=config,
        reports_dir=tmp_path / "reports",
    )
    return save_phase22b_dynamic_opportunity_diagnostics(
        config=config,
        reports_dir=tmp_path / "reports",
    )


def test_phase22b_diagnostics_outputs_and_explanations(tmp_path):
    outputs = _run_phase22a_then_b(tmp_path)
    output_dir = tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine_diagnostics"

    assert (output_dir / "phase22b_latest_score_to_weight_audit.csv").exists()
    assert (output_dir / "phase22b_cash_allocation_audit.csv").exists()
    assert (output_dir / "phase22b_turnover_diagnostics.csv").exists()
    assert (output_dir / "phase22b_asset_contribution_summary.csv").exists()
    audit = outputs["score_to_weight_audit"]
    assert not audit.empty
    assert "allocation_explanation" in audit.columns
    assert audit["allocation_explanation"].astype(str).str.len().gt(0).all()


def test_phase22b_v1_strategies_caps_and_cost_sensitivity(tmp_path):
    outputs = _run_phase22a_then_b(tmp_path)
    output_dir = tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine_diagnostics"
    weights = pd.read_csv(output_dir / "phase22b_v1_daily_weights.csv")
    metrics = outputs["v1_metrics"]
    tc = outputs["transaction_cost_sensitivity"]
    turnover = pd.read_csv(output_dir / "phase22b_turnover_diagnostics.csv")

    assert len(metrics["strategy_name"].unique()) >= 3
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
    assert weights.groupby(["date", "strategy_name"])["weight"].max().max() <= 0.500001
    assert set(tc["transaction_cost_bps"]) == {0, 10, 25}
    turnover_lookup = turnover.set_index("strategy")["annualized_turnover"].to_dict()
    assert (
        turnover_lookup["dynamic_top5_opportunity_v1_sticky"]
        <= turnover_lookup["dynamic_top5_technical_opportunity_v0"]
    )


def test_phase22b_benchmark_comparison_includes_current_v0_and_v1(tmp_path):
    outputs = _run_phase22a_then_b(tmp_path)
    names = set(outputs["comparison"]["strategy_name"])

    assert "SPY Buy & Hold Benchmark" in names
    assert "phase6b_loose_relief_execution_realistic_overlay" in names
    assert "canonical_spy_qqq_gld_tlt_50_30_10_10" in names
    assert "canonical_inverse_vol_63d_btc_usd_qqq_spy" in names
    assert "canonical_spy_qqq_60_40" in names
    assert "dynamic_top5_technical_opportunity_v0" in names
    assert "dynamic_top5_opportunity_v1_balanced" in names


def test_phase22b_writes_dashboard_charts_and_safety_flags(tmp_path):
    outputs = _run_phase22a_then_b(tmp_path)
    output_dir = tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine_diagnostics"
    dashboard_path = tmp_path / "reports" / "paper_trading" / "dashboard" / "phase22b_dynamic_opportunity_diagnostics_status.csv"

    assert dashboard_path.exists()
    assert (output_dir / "visuals" / "phase22b_v1_equity_curves.png").exists()
    assert (output_dir / "visuals" / "phase22b_latest_score_to_weight.png").exists()
    summary = outputs["summary"].iloc[0]
    assert not summary["promotion_allowed"]
    assert not summary["live_trading_allowed"]
    assert not summary["real_money_allowed"]
    assert not summary["broker_api_integration_allowed"]


def test_phase22b_focused_runner_flag_exists_and_daily_runner_skips_phase22b():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    assert "--phase22b-only" in source
    assert "_run_phase22b_dynamic_opportunity_diagnostics(" in source
    daily_start = source.index("def _run_daily_paper_workflow")
    daily_end = source.index("def main()")
    daily_source = source[daily_start:daily_end]
    assert "phase22b_dynamic_opportunity_diagnostics" not in daily_source
