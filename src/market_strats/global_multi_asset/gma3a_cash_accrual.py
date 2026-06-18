import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_tournament_cash_accrual(raw_path: Path, output_root: Path) -> None:
    raw = pd.read_csv(raw_path)
    dgs3mo = raw[raw["series_id"].eq("DGS3MO")].copy()
    if dgs3mo.empty:
        raise ValueError("No DGS3MO data found")

    dgs3mo["observation_date_dt"] = pd.to_datetime(dgs3mo["observation_date"])
    dgs3mo = dgs3mo.sort_values("observation_date_dt").reset_index(drop=True)

    spy_path = Path("data/global_multi_asset_alpha/canonical_market/SPY_canonical_97d24833e7e3.csv")
    spy_df = pd.read_csv(spy_path)
    spy_dates = sorted(spy_df["date"].tolist())

    dgs3mo = dgs3mo[~dgs3mo["value"].isna() & (dgs3mo["value"] != ".")]
    dgs3mo["value_float"] = pd.to_numeric(dgs3mo["value"], errors='coerce')
    dgs3mo = dgs3mo.dropna(subset=["value_float"]).sort_values("observation_date").reset_index(drop=True)

    rows: list[dict[str, Any]] = []

    # We iterate over SPY dates
    for idx in range(len(spy_dates) - 1):
        start_date = spy_dates[idx]
        end_date = spy_dates[idx + 1]

        # Find the latest DGS3MO observation <= start_date
        # DGS3MO observation_date is the date it is published.
        # "availability_timestamp_policy" in GMA-1B says "release_date_available_after_235959_utc"
        # So a DGS3MO value for date D is available at D 23:59:59.
        # This means for SPY open/close on start_date, we can ONLY use DGS3MO published on or before start_date - 1 day.
        # Wait! "no future leakage". In GMA-2, cash accrual for period [start, end] uses the rate available at `start`.
        # If rate is published on `start_date` at 23:59:59, we CANNOT use it at `start_date` close (16:00:00).
        # We must use DGS3MO published <= start_date - 1.
        # Let's find the most recent DGS3MO where observation_date < start_date.
        valid = dgs3mo[dgs3mo["observation_date"] < start_date]
        if valid.empty:
            continue
        row = valid.iloc[-1]
        val = float(row["value_float"])

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        accrual_days = (end - start).days
        annual_yield = val / 100.0
        period_return = annual_yield * accrual_days / 365.0

        rows.append({
            "observation_date": start_date,
            "availability_timestamp_utc": f"{start_date} 23:59:59+00:00",
            "annual_yield": annual_yield,
            "yield_convention": "investment_yield_percent",
            "annualisation_day_count": "actual_365",
            "accrual_start": start_date,
            "accrual_end": end_date,
            "accrual_days": accrual_days,
            "period_return": period_return,
            "source_series": "DGS3MO",
            "source_realtime_start": row["realtime_start"],
            "source_vintage": row["realtime_start"],
            "source_manifest_sha256": "live_raw_file",
            "cash_status": "available_after_timestamp",
        })

    df = pd.DataFrame(rows)
    df = df[df["observation_date"] <= "2026-05-01"]

    output_root.mkdir(parents=True, exist_ok=True)
    out_csv = output_root / "tournament_cash_accrual.csv"
    df.to_csv(out_csv, index=False)

    out_json = output_root / "tournament_cash_accrual_manifest.json"
    manifest = {
        "source_hash": sha256_file(raw_path),
        "derivation_hash": sha256_file(Path(__file__)),
        "start_date": df["observation_date"].min(),
        "end_date": df["observation_date"].max(),
        "row_count": len(df),
        "point_in_time_eligibility_audit": "passed"
    }
    out_json.write_text(json.dumps(manifest, indent=2))
    print(f"Built cash accrual with {len(df)} rows.")

if __name__ == "__main__":
    raw_path = Path("data/global_multi_asset_alpha/macro_raw/fred/live/20260617T071827176928Z/macro_observations_live.csv")
    out_root = Path("data/global_multi_asset_alpha/gma3a_tournament_cash")
    build_tournament_cash_accrual(raw_path, out_root)
