import pandas as pd

from market_strats.analysis.regime_switch_overlay_audit import (
    create_regime_switch_overlay_audit,
    create_regime_switch_overlay_audit_summary,
)


def make_base_result(
    dates: pd.DatetimeIndex,
    daily_return: float,
) -> pd.DataFrame:
    returns = [0.0] + [daily_return] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0] * len(dates),
            "cash_position": [0.0] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def make_overlay_result(dates: pd.DatetimeIndex) -> pd.DataFrame:
    returns = [0.0] + [0.0003] * (len(dates) - 1)
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    selected_modes = []

    for index, _ in enumerate(dates):
        if index < 10:
            selected_modes.append("offensive_spy")
        elif index < 20:
            selected_modes.append("defensive_allocator")
        else:
            selected_modes.append("offensive_spy")

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": [1.0] * len(dates),
            "cash_position": [0.0] * len(dates),
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
            "selected_mode": selected_modes,
            "trend_sma": [100.0] * len(dates),
            "overlay_turnover": [0.0] * len(dates),
            "offensive_weight": [
                1.0 if mode == "offensive_spy" else 0.0
                for mode in selected_modes
            ],
            "defensive_weight": [
                1.0 if mode == "defensive_allocator" else 0.0
                for mode in selected_modes
            ],
        }
    )


def test_create_regime_switch_overlay_audit_detects_switches_and_whipsaws():
    dates = pd.bdate_range("2020-01-01", periods=40)

    overlay = make_overlay_result(dates)
    offensive = make_base_result(dates, 0.0005)
    defensive = make_base_result(dates, 0.0002)

    audit = create_regime_switch_overlay_audit(
        overlay_result=overlay,
        offensive_result=offensive,
        defensive_result=defensive,
        whipsaw_days=30,
        future_return_horizons=[5],
    )

    assert len(audit) == 2
    assert audit["whipsaw_flag"].iloc[0]
    assert "overlay_next_5d_return_pct" in audit.columns
    assert "spy_next_5d_return_pct" in audit.columns
    assert "defensive_next_5d_return_pct" in audit.columns


def test_create_regime_switch_overlay_audit_summary_runs():
    audit = pd.DataFrame(
        {
            "switch_year": [2011, 2011, 2018],
            "whipsaw_flag": [True, False, True],
            "to_mode": [
                "defensive_allocator",
                "offensive_spy",
                "defensive_allocator",
            ],
            "days_until_next_switch": [10, 60, None],
            "overlay_drawdown_at_switch_pct": [-5.0, -2.0, -8.0],
            "spy_drawdown_at_switch_pct": [-6.0, -3.0, -9.0],
            "spy_distance_from_200d_pct": [-1.0, 1.0, -2.0],
            "defensive_allocator_cash_at_switch_pct": [50.0, 40.0, 60.0],
        }
    )

    summary = create_regime_switch_overlay_audit_summary(
        audit=audit,
        focus_years=[2011, 2018],
    )

    assert not summary.empty
    assert "total_switches" in set(summary["metric"])
    assert "whipsaw_count" in set(summary["metric"])
    assert "switches_by_year" in set(summary["metric"])