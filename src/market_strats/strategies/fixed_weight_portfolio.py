from __future__ import annotations

import pandas as pd


def _validate_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise ValueError("weights cannot be empty")

    if any(weight < 0 for weight in weights.values()):
        raise ValueError("weights cannot contain negative values")

    total_weight = sum(weights.values())

    if round(total_weight, 10) != 1.0:
        raise ValueError("weights must sum to 1")


def _prepare_component_result(result: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "date",
        "adj_close",
        "strategy_return",
        "equity",
        "position",
        "cash_position",
        "turnover",
    }

    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(f"component result missing columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


def get_common_strategy_dates(component_results: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    if not component_results:
        raise ValueError("component_results cannot be empty")

    common_dates: set[pd.Timestamp] | None = None

    for result in component_results.values():
        df = _prepare_component_result(result)
        dates = set(pd.to_datetime(df["date"]))

        if common_dates is None:
            common_dates = dates
        else:
            common_dates = common_dates.intersection(dates)

    if not common_dates:
        raise ValueError("No common dates across component results")

    return sorted(common_dates)


def rebase_strategy_result_to_dates(
    result: pd.DataFrame,
    dates: list[pd.Timestamp],
    initial_capital: float,
) -> pd.DataFrame:
    """
    Rebase an existing strategy result to a chosen date set.

    This is used to compare benchmarks over the exact same common period as
    the multi-asset candidate portfolio.
    """
    df = _prepare_component_result(result)
    date_set = set(pd.to_datetime(dates))
    df = df[pd.to_datetime(df["date"]).isin(date_set)].copy()

    if df.empty:
        raise ValueError("No overlapping dates when rebasing strategy result")

    df = df.sort_values("date").reset_index(drop=True)
    df["strategy_return"] = df["strategy_return"].astype(float)
    df.loc[df.index[0], "strategy_return"] = 0.0
    df["equity"] = initial_capital * (1.0 + df["strategy_return"]).cumprod()

    return df


def run_independent_weighted_portfolio(
    component_results: dict[str, pd.DataFrame],
    weights: dict[str, float],
    initial_capital: float,
    portfolio_name: str,
) -> pd.DataFrame:
    """
    Combine strategy sleeves into an independent fixed-weight portfolio.

    Each sleeve receives its starting weight at inception and then evolves
    independently. There is no rebalancing after inception.

    This isolates the effect of combining validated strategy signals without
    introducing an additional rebalance rule.
    """
    _validate_weights(weights)

    if set(component_results) != set(weights):
        raise ValueError("component_results keys must match weights keys")

    common_dates = get_common_strategy_dates(component_results)

    prepared_components = {
        name: rebase_strategy_result_to_dates(
            result=result,
            dates=common_dates,
            initial_capital=initial_capital,
        )
        for name, result in component_results.items()
    }

    sleeve_values = {
        name: initial_capital * weights[name]
        for name in component_results
    }

    rows: list[dict] = []
    previous_total_equity = initial_capital

    for index, date in enumerate(common_dates):
        total_equity = 0.0
        weighted_position = 0.0
        weighted_cash_position = 0.0
        weighted_turnover = 0.0
        current_sleeve_values: dict[str, float] = {}

        for name, component in prepared_components.items():
            component_row = component[component["date"] == date].iloc[0]

            if index > 0:
                sleeve_values[name] *= 1.0 + float(component_row["strategy_return"])

            current_sleeve_values[name] = sleeve_values[name]
            total_equity += sleeve_values[name]

        if total_equity <= 0:
            raise ValueError("Portfolio equity became non-positive")

        for name, component in prepared_components.items():
            component_row = component[component["date"] == date].iloc[0]
            current_weight = current_sleeve_values[name] / total_equity

            weighted_position += current_weight * float(component_row["position"])
            weighted_cash_position += current_weight * float(component_row["cash_position"])
            weighted_turnover += current_weight * float(component_row["turnover"])

        strategy_return = (
            0.0
            if index == 0
            else (total_equity / previous_total_equity) - 1.0
        )

        representative_component = next(iter(prepared_components.values()))
        representative_row = representative_component[
            representative_component["date"] == date
        ].iloc[0]

        row = {
            "date": date,
            "adj_close": float(representative_row["adj_close"]),
            "strategy_return": strategy_return,
            "equity": total_equity,
            "position": weighted_position,
            "cash_position": weighted_cash_position,
            "turnover": weighted_turnover if index > 0 else 1.0,
            "portfolio_name": portfolio_name,
        }

        for name in component_results:
            safe_name = (
                name.lower()
                .replace(" ", "_")
                .replace("/", "_")
                .replace("-", "_")
            )
            row[f"{safe_name}_sleeve_value"] = current_sleeve_values[name]
            row[f"{safe_name}_current_weight"] = (
                current_sleeve_values[name] / total_equity
            )

        rows.append(row)
        previous_total_equity = total_equity

    return pd.DataFrame(rows).reset_index(drop=True)