from __future__ import annotations

from pathlib import Path

import pandas as pd


def _prepare_result(result: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"date", "position", "cash_position"}

    missing_columns = required_columns - set(result.columns)

    if missing_columns:
        raise ValueError(f"result missing columns: {sorted(missing_columns)}")

    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


def _first_risky_position_date(df: pd.DataFrame) -> str:
    risky = df[df["position"].astype(float) > 0.000001]

    if risky.empty:
        return ""

    return risky.iloc[0]["date"].date().isoformat()


def create_candidate_portfolio_warmup_audit(
    component_results: dict[str, pd.DataFrame],
    expected_warmup_trading_days: dict[str, int],
    common_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    """
    Audit whether strategy sleeves are active before their expected warmup period.

    Example:
    - 12M momentum should not hold risky exposure before enough lookback exists.
    - 200D SMA should not hold risky exposure before enough daily SMA history exists.

    This is a contamination check before candidate portfolio testing.
    """
    if not component_results:
        return pd.DataFrame()

    if not common_dates:
        raise ValueError("common_dates cannot be empty")

    common_start = pd.to_datetime(min(common_dates))
    rows: list[dict] = []

    for component_name, result in component_results.items():
        df = _prepare_result(result)

        expected_warmup = int(expected_warmup_trading_days.get(component_name, 0))

        if expected_warmup < 0:
            raise ValueError("expected warmup cannot be negative")

        if expected_warmup == 0:
            warmup_end_date = df.iloc[0]["date"]
            warmup_slice = df.iloc[0:0]
        else:
            warmup_index = min(expected_warmup, len(df) - 1)
            warmup_end_date = df.iloc[warmup_index]["date"]
            warmup_slice = df.iloc[:expected_warmup]

        active_before_expected_warmup = bool(
            (warmup_slice["position"].astype(float) > 0.000001).any()
        )

        common_row = df[df["date"] >= common_start].head(1)

        if common_row.empty:
            position_at_common_start = float("nan")
            cash_at_common_start = float("nan")
        else:
            position_at_common_start = float(common_row.iloc[0]["position"])
            cash_at_common_start = float(common_row.iloc[0]["cash_position"])

        common_start_before_warmup_completed = common_start < warmup_end_date

        if active_before_expected_warmup:
            status = "Fail: active before expected warmup completed"
        else:
            status = "Pass"

        rows.append(
            {
                "component": component_name,
                "component_start_date": df.iloc[0]["date"].date().isoformat(),
                "common_start_date": common_start.date().isoformat(),
                "expected_warmup_trading_days": expected_warmup,
                "expected_warmup_end_date": warmup_end_date.date().isoformat(),
                "first_risky_position_date": _first_risky_position_date(df),
                "active_before_expected_warmup": active_before_expected_warmup,
                "common_start_before_warmup_completed": (
                    common_start_before_warmup_completed
                ),
                "position_at_common_start": position_at_common_start,
                "cash_position_at_common_start": cash_at_common_start,
                "warmup_status": status,
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(4)

    return output.reset_index(drop=True)


def write_candidate_portfolio_warmup_audit_markdown(
    warmup_audit: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if warmup_audit.empty:
        output_path.write_text(
            "# Candidate Portfolio Warmup Audit\n\nNo data available.\n",
            encoding="utf-8",
        )
        return output_path

    table = warmup_audit.to_markdown(index=False)

    content = f"""# Candidate Portfolio Warmup Audit

This report checks whether candidate portfolio sleeves become active before their expected lookback warmup periods are complete.

## Warmup Audit

{table}

## Interpretation Notes

- 12-month momentum sleeves should remain out of risky exposure until enough history exists.
- 200-day SMA sleeves should remain out of risky exposure until enough moving-average history exists.
- If a sleeve is active before warmup is complete, the candidate portfolio result may be contaminated.
- If common_start_before_warmup_completed is true but active_before_expected_warmup is false, the sleeve was included during warmup but stayed in cash, which is acceptable.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path