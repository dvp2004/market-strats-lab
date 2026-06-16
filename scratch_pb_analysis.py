"""Provider-basis analysis for GMA-1A-R."""
import glob
import pandas as pd

CANON = "data/global_multi_asset_alpha/canonical_market"
PB = ["EFA", "VGK", "EWJ", "EEM", "VWO", "HYG", "DBC", "VNQ", "ACWI"]

for sym in PB:
    key = sym.replace("-", "_")
    hits = glob.glob(f"{CANON}/{key}_canonical_*.csv")
    if not hits:
        print(f"{sym}: no file")
        continue
    df = pd.read_csv(hits[0])
    df["date"] = pd.to_datetime(df["date"])
    df2 = (
        df[df["is_completed_observation"]]
        .sort_values("date")
        .reset_index(drop=True)
    )
    df2["adj_ret"] = df2["adj_close_provider"] / df2["adj_close_provider"].shift(1)
    df2["diff_bps"] = (df2["total_return_factor"] - df2["adj_ret"]).abs() * 10000
    tol = 0.5
    mat = df2[df2["diff_bps"] > tol].copy()
    n = len(mat)
    div_on_mat = (mat["dividend_cash"].fillna(0) > 0).sum()
    zero_div_on_mat = n - div_on_mat
    max_diff = mat["diff_bps"].max() if n > 0 else 0
    med_diff = mat["diff_bps"].median() if n > 0 else 0
    print(
        f"{sym}: n_material={n} on_div_dates={div_on_mat} "
        f"off_div_dates={zero_div_on_mat} max={max_diff:.3f}bps "
        f"med={med_diff:.3f}bps"
    )
    if n > 0:
        # Show worst 3
        worst = mat.nlargest(3, "diff_bps")[
            [
                "date",
                "diff_bps",
                "total_return_factor",
                "adj_ret",
                "dividend_cash",
                "split_ratio",
            ]
        ]
        for _, r in worst.iterrows():
            print(
                f"  {str(r['date'].date())} diff={r['diff_bps']:.3f}bps "
                f"tr={r['total_return_factor']:.8f} adj={r['adj_ret']:.8f} "
                f"div={r['dividend_cash']} spl={r['split_ratio']}"
            )
    print()
