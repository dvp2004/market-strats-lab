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

def run_annual_rebalanced_core_satellite_strategy(
    core_result: pd.DataFrame,
    satellite_result: pd.DataFrame,
    initial_capital: float,
    core_weight: float,
    satellite_weight: float,
    strategy_name: str,
    slippage_bps: float,
    rebalance_month: int = 12,
) -> pd.DataFrame:
    """
    Blend two sleeves and rebalance back to target weights at each year-end.

    Core sleeve:
    - Usually buy-and-hold SPY.

    Satellite sleeve:
    - Usually SPY 12-month absolute momentum.

    Rebalancing:
    - At the final trading day of each calendar year, after daily returns are applied,
      reset sleeve values back to the target core/satellite weights.
    - This can move cash-protected satellite capital back into the core during bear markets.
    - That is exactly the behaviour we want to test.

    This is different from independent sleeves, where no capital moves between sleeves
    after inception.
    """
    if not 0 <= core_weight <= 1:
        raise ValueError("core_weight must be between 0 and 1")

    if not 0 <= satellite_weight <= 1:
        raise ValueError("satellite_weight must be between 0 and 1")

    if round(core_weight + satellite_weight, 10) != 1.0:
        raise ValueError("core_weight + satellite_weight must equal 1")
    
    if not 1 <= rebalance_month <= 12:
        raise ValueError("rebalance_month must be between 1 and 12")

    required_columns = {
        "date",
        "adj_close",
        "strategy_return",
        "position",
        "cash_position",
        "turnover",
    }

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
                "strategy_return",
                "position",
                "cash_position",
                "turnover",
            ]
        ],
        satellite[
            [
                "date",
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

    df = df.sort_values("date").reset_index(drop=True)

    year = df["date"].dt.year
    month = df["date"].dt.month
    next_year = year.shift(-1)
    next_month = month.shift(-1)

    is_rebalance_day = (
        (month == rebalance_month)
        & (
            (next_month != rebalance_month)
            | (next_year != year)
        )
    )
    is_rebalance_day.iloc[-1] = False

    core_sleeve_equity = initial_capital * core_weight
    satellite_sleeve_equity = initial_capital * satellite_weight

    rows: list[dict] = []

    previous_total_equity = initial_capital

    for index, row in df.iterrows():
        core_sleeve_equity *= 1.0 + float(row["strategy_return_core"])
        satellite_sleeve_equity *= 1.0 + float(row["strategy_return_satellite"])

        total_equity_before_rebalance = core_sleeve_equity + satellite_sleeve_equity

        rebalance_turnover = 0.0
        core_sleeve_equity_before_rebalance = core_sleeve_equity
        satellite_sleeve_equity_before_rebalance = satellite_sleeve_equity
        core_weight_before_rebalance = (
            core_sleeve_equity_before_rebalance / total_equity_before_rebalance
        )
        satellite_weight_before_rebalance = (
            satellite_sleeve_equity_before_rebalance / total_equity_before_rebalance
        )

        if bool(is_rebalance_day.iloc[index]):
            target_core_equity = total_equity_before_rebalance * core_weight
            target_satellite_equity = total_equity_before_rebalance * satellite_weight

            rebalance_turnover = (
                abs(target_core_equity - core_sleeve_equity)
                + abs(target_satellite_equity - satellite_sleeve_equity)
            ) / total_equity_before_rebalance

            rebalance_cost = rebalance_turnover * (slippage_bps / 10_000.0)
            total_equity_after_cost = total_equity_before_rebalance * (
                1.0 - rebalance_cost
            )

            core_sleeve_equity = total_equity_after_cost * core_weight
            satellite_sleeve_equity = total_equity_after_cost * satellite_weight
        else:
            total_equity_after_cost = total_equity_before_rebalance

        strategy_return = (
            0.0
            if index == 0
            else (total_equity_after_cost / previous_total_equity) - 1.0
        )

        total_equity = core_sleeve_equity + satellite_sleeve_equity

        current_core_weight = core_sleeve_equity / total_equity
        current_satellite_weight = satellite_sleeve_equity / total_equity

        position = (
            current_core_weight * float(row["position_core"])
            + current_satellite_weight * float(row["position_satellite"])
        )

        cash_position = (
            current_core_weight * float(row["cash_position_core"])
            + current_satellite_weight * float(row["cash_position_satellite"])
        )

        strategy_turnover = (
            current_satellite_weight * float(row["turnover_satellite"])
            + rebalance_turnover
        )

        if index == 0:
            strategy_turnover = 1.0

        rows.append(
            {
                "date": row["date"],
                "adj_close": row["adj_close"],
                "strategy_return": strategy_return,
                "equity": total_equity,
                "position": position,
                "cash_position": cash_position,
                "turnover": strategy_turnover,
                "core_sleeve_equity": core_sleeve_equity,
                "satellite_sleeve_equity": satellite_sleeve_equity,
                "current_core_weight": current_core_weight,
                "current_satellite_weight": current_satellite_weight,
                "core_initial_weight": core_weight,
                "satellite_initial_weight": satellite_weight,
                "rebalance_turnover": rebalance_turnover,
                "is_rebalance_day": bool(is_rebalance_day.iloc[index]),
                "rebalance_month": rebalance_month,
                "total_equity_before_rebalance": total_equity_before_rebalance,
                "core_sleeve_equity_before_rebalance": core_sleeve_equity_before_rebalance,
                "satellite_sleeve_equity_before_rebalance": satellite_sleeve_equity_before_rebalance,
                "core_weight_before_rebalance": core_weight_before_rebalance,
                "satellite_weight_before_rebalance": satellite_weight_before_rebalance,
                "strategy_name": strategy_name,
            }
        )

        previous_total_equity = total_equity

    return pd.DataFrame(rows).reset_index(drop=True)