from __future__ import annotations

import pandas as pd


def run_independent_core_satellite_strategy(
    core_result: pd.DataFrame,
    satellite_result: pd.DataFrame,
    initial_capital: float,
    core_weight: float,
    satellite_weight: float,
    strategy_name: str,
) -> pd.DataFrame:
    """
    Blend two independent sleeves without rebalancing.

    Core sleeve:
    - Starts with initial_capital * core_weight.
    - Then compounds independently.

    Satellite sleeve:
    - Starts with initial_capital * satellite_weight.
    - Then compounds independently.

    There is no capital transfer between sleeves after inception.
    This avoids accidentally rebalancing cash into SPY during downtrends.
    """
    if not 0 <= core_weight <= 1:
        raise ValueError("core_weight must be between 0 and 1")

    if not 0 <= satellite_weight <= 1:
        raise ValueError("satellite_weight must be between 0 and 1")

    if round(core_weight + satellite_weight, 10) != 1.0:
        raise ValueError("core_weight + satellite_weight must equal 1")

    required_columns = {"date", "equity", "strategy_return", "position", "turnover"}

    missing_core_columns = required_columns - set(core_result.columns)
    missing_satellite_columns = required_columns - set(satellite_result.columns)

    if missing_core_columns:
        raise ValueError(f"core_result missing columns: {sorted(missing_core_columns)}")

    if missing_satellite_columns:
        raise ValueError(
            f"satellite_result missing columns: {sorted(missing_satellite_columns)}"
        )

    core = core_result.copy()
    satellite = satellite_result.copy()

    core["date"] = pd.to_datetime(core["date"])
    satellite["date"] = pd.to_datetime(satellite["date"])

    core = core.sort_values("date").reset_index(drop=True)
    satellite = satellite.sort_values("date").reset_index(drop=True)

    df = pd.merge(
        core[
            [
                "date",
                "adj_close",
                "equity",
                "strategy_return",
                "position",
                "turnover",
            ]
        ],
        satellite[
            [
                "date",
                "equity",
                "strategy_return",
                "position",
                "cash_position",
                "turnover",
            ]
        ],
        on="date",
        how="inner",
        suffixes=("_core", "_satellite"),
    )

    if df.empty:
        raise ValueError("No overlapping dates between core and satellite results")

    core_start_equity = float(df["equity_core"].iloc[0])
    satellite_start_equity = float(df["equity_satellite"].iloc[0])

    if core_start_equity == 0 or satellite_start_equity == 0:
        raise ValueError("Core and satellite starting equity must be non-zero")

    df["core_sleeve_equity"] = (
        initial_capital * core_weight * (df["equity_core"] / core_start_equity)
    )
    df["satellite_sleeve_equity"] = (
        initial_capital
        * satellite_weight
        * (df["equity_satellite"] / satellite_start_equity)
    )

    df["equity"] = df["core_sleeve_equity"] + df["satellite_sleeve_equity"]
    df["strategy_return"] = df["equity"].pct_change().fillna(0.0)

    df["current_core_weight"] = df["core_sleeve_equity"] / df["equity"]
    df["current_satellite_weight"] = df["satellite_sleeve_equity"] / df["equity"]

    df["position"] = (
        df["current_core_weight"] * df["position_core"]
        + df["current_satellite_weight"] * df["position_satellite"]
    )

    df["cash_position"] = 1.0 - df["position"]

    df["turnover"] = (
        df["current_satellite_weight"] * df["turnover_satellite"].fillna(0.0)
    )
    df.loc[df.index[0], "turnover"] = 1.0

    df["core_initial_weight"] = core_weight
    df["satellite_initial_weight"] = satellite_weight
    df["strategy_name"] = strategy_name

    return df[
        [
            "date",
            "adj_close",
            "strategy_return",
            "equity",
            "position",
            "cash_position",
            "turnover",
            "core_sleeve_equity",
            "satellite_sleeve_equity",
            "current_core_weight",
            "current_satellite_weight",
            "core_initial_weight",
            "satellite_initial_weight",
            "strategy_name",
        ]
    ].reset_index(drop=True)