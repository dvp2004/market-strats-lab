from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PHASE19B_SECTION = "phase19b_strategy_factory_finalist_validation"
REQUIRED_PHASE19A_FILES = {
    "finalists": "phase19a_finalist_shortlist.csv",
    "candidate_metrics": "phase19a_candidate_metrics.csv",
    "leaderboard": "phase19a_leaderboard.csv",
    "entity_summary": "phase19a_entity_contribution_summary.csv",
    "period_metrics": "phase19a_period_metrics.csv",
    "robustness_flags": "phase19a_robustness_flags.csv",
}
EXPANDED_ASSETS = {"IWM", "EFA", "EEM", "AGG", "VNQ", "DBC"}
SAFETY_FALSE_COLUMNS = [
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
]
LOW_DRAWDOWN_TIERS = {"low_drawdown", "moderate_drawdown"}
HIGH_DRAWDOWN_TIERS = {"high_drawdown", "severe_drawdown"}


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE19B_SECTION, {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _write_csv(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def drawdown_quality_tier(worst_max_drawdown: float) -> str:
    drawdown = float(worst_max_drawdown)
    if drawdown >= -25.0:
        return "low_drawdown"
    if drawdown >= -35.0:
        return "moderate_drawdown"
    if drawdown >= -45.0:
        return "high_drawdown"
    return "severe_drawdown"


def drawdown_label_warning(tier: str) -> str:
    if tier == "severe_drawdown":
        return "severe_historical_drawdown_not_defensive"
    if tier == "high_drawdown":
        return "high_historical_drawdown_not_defensive"
    return ""


def _source_paths(source_dir: Path) -> dict[str, Path]:
    return {name: source_dir / filename for name, filename in REQUIRED_PHASE19A_FILES.items()}


def _load_required_sources(source_dir: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for name, path in _source_paths(source_dir).items():
        if not path.exists():
            missing.append(str(path))
            continue
        frames[name] = pd.read_csv(path)
    return frames, missing


def _universe_assets(universe_name: str, uses_btc: bool) -> list[str]:
    if universe_name == "core_us_growth":
        return ["SPY", "QQQ", "CASH"]
    if universe_name == "defensive_multi_asset":
        return ["SPY", "QQQ", "GLD", "TLT", "CASH"]
    if universe_name == "btc_capped_growth":
        return ["SPY", "QQQ", "BTC-USD", "CASH"]
    if universe_name == "expanded_liquid_etf":
        return ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "TLT", "AGG", "VNQ", "DBC", "CASH"]
    if universe_name == "expanded_liquid_etf_with_btc":
        return [
            "SPY",
            "QQQ",
            "IWM",
            "EFA",
            "EEM",
            "GLD",
            "TLT",
            "AGG",
            "VNQ",
            "DBC",
            "BTC-USD",
            "CASH",
        ]
    assets = ["SPY", "QQQ", "CASH"]
    if uses_btc:
        assets.insert(2, "BTC-USD")
    return assets


def _active_assets_for_candidate(row: pd.Series) -> list[str]:
    candidate_id = str(row["candidate_id"])
    universe_name = str(row["universe_name"])
    uses_btc = float(row.get("BTC_max_weight", 0.0) or 0.0) > 0
    universe_assets = _universe_assets(universe_name, uses_btc)

    if "spy_buy_hold" in candidate_id:
        assets = ["SPY"]
    elif "spy_qqq_btc_cap" in candidate_id:
        assets = ["SPY", "QQQ", "BTC-USD", "CASH"]
    elif "spy_qqq_60_40" in candidate_id:
        assets = ["SPY", "QQQ"]
    elif "spy_qqq_70_30" in candidate_id:
        assets = ["SPY", "QQQ"]
    elif "spy_qqq_50_50" in candidate_id:
        assets = ["SPY", "QQQ"]
    elif "spy_qqq_gld_tlt" in candidate_id:
        assets = ["SPY", "QQQ", "GLD", "TLT"]
    elif "topk_momentum" in candidate_id or "inverse_vol" in candidate_id:
        assets = [asset for asset in universe_assets if asset != "CASH"]
        if uses_btc and "BTC-USD" not in assets:
            assets.append("BTC-USD")
    else:
        assets = [asset for asset in universe_assets if asset != "CASH"]

    if uses_btc and "BTC-USD" not in assets:
        assets.append("BTC-USD")
    return sorted(dict.fromkeys(assets))


def _canonical_id(candidate_id: str, active_assets: list[str]) -> str:
    if "spy_qqq_60_40" in candidate_id:
        return "canonical_spy_qqq_60_40"
    if "spy_qqq_70_30" in candidate_id:
        return "canonical_spy_qqq_70_30"
    if "spy_qqq_50_50" in candidate_id:
        return "canonical_spy_qqq_50_50"
    if "spy_qqq_btc_cap_05" in candidate_id:
        return "canonical_spy_qqq_btc_cap_05"
    if "spy_qqq_btc_cap_10" in candidate_id:
        return "canonical_spy_qqq_btc_cap_10"
    if "inverse_vol_63d" in candidate_id:
        return f"canonical_inverse_vol_63d_{'_'.join(active_assets).lower().replace('-', '_')}"
    if "inverse_vol_126d" in candidate_id:
        return f"canonical_inverse_vol_126d_{'_'.join(active_assets).lower().replace('-', '_')}"
    if "topk_momentum" in candidate_id:
        return f"canonical_{candidate_id}"
    return f"canonical_{candidate_id}"


def canonicalise_phase19a_finalists(finalists: pd.DataFrame) -> pd.DataFrame:
    if finalists.empty:
        return pd.DataFrame()

    out = finalists.copy()
    active_asset_rows: list[str] = []
    canonical_ids: list[str] = []
    uses_btc_values: list[bool] = []
    uses_expanded_values: list[bool] = []
    equivalent_groups: list[str] = []

    for _idx, row in out.iterrows():
        active_assets = _active_assets_for_candidate(row)
        active_asset_text = ",".join(active_assets)
        uses_btc = "BTC-USD" in active_assets or float(row.get("BTC_max_weight", 0.0) or 0.0) > 0
        uses_expanded = any(asset in EXPANDED_ASSETS for asset in active_assets)
        canonical = _canonical_id(str(row["candidate_id"]), active_assets)
        group = f"{canonical}|{active_asset_text}|{row.get('strategy_family', '')}"
        active_asset_rows.append(active_asset_text)
        canonical_ids.append(canonical)
        uses_btc_values.append(uses_btc)
        uses_expanded_values.append(uses_expanded)
        equivalent_groups.append(group)

    out["canonical_candidate_id"] = canonical_ids
    out["candidate_family"] = out["strategy_family"].astype(str)
    out["universe"] = out["universe_name"].astype(str)
    out["uses_btc"] = uses_btc_values
    out["uses_expanded_assets"] = uses_expanded_values
    out["active_assets"] = active_asset_rows
    out["equivalent_candidate_group"] = equivalent_groups
    out["canonical_representative"] = False

    representatives = out.groupby("equivalent_candidate_group")["average_score"].idxmax()
    out.loc[representatives, "canonical_representative"] = True
    return out


def _transaction_complexity_tables(reports_dir: Path) -> dict[str, pd.DataFrame]:
    transactions_dir = reports_dir / "strategy_factory" / "transactions"
    tables: dict[str, pd.DataFrame] = {}
    for name, filename in {
        "drift": "strategy_drift_rebalance_summary.csv",
        "target": "strategy_rebalance_summary.csv",
    }.items():
        path = transactions_dir / filename
        if path.exists():
            tables[name] = pd.read_csv(path)
    return tables


def _transaction_complexity_for_candidate(
    candidate_id: str,
    tables: dict[str, pd.DataFrame],
) -> dict[str, float | str]:
    strategy_map = {
        "sf19_spy_qqq_60_40": "sf_spy_qqq_60_40_monthly_rebalanced",
        "sf19_spy_qqq_btc_cap_05": "sf_spy_qqq_btc_capped_offensive",
        "sf19_spy_qqq_btc_cap_10": "sf_spy_qqq_btc_capped_offensive",
    }
    mapped = strategy_map.get(candidate_id)
    if mapped is None:
        return {
            "transaction_source": "phase19a_turnover_metrics",
            "transaction_rows": 0.0,
            "drift_rebalance_rows": 0.0,
            "transaction_turnover": 0.0,
        }

    target = tables.get("target", pd.DataFrame())
    drift = tables.get("drift", pd.DataFrame())
    target_row = target.loc[target.get("strategy_id", pd.Series(dtype=str)).astype(str) == mapped]
    drift_row = drift.loc[drift.get("strategy_id", pd.Series(dtype=str)).astype(str) == mapped]

    return {
        "transaction_source": mapped,
        "transaction_rows": float(target_row["transaction_rows"].iloc[0])
        if not target_row.empty and "transaction_rows" in target_row
        else 0.0,
        "drift_rebalance_rows": float(drift_row["rebalance_trade_rows"].iloc[0])
        if not drift_row.empty and "rebalance_trade_rows" in drift_row
        else 0.0,
        "transaction_turnover": float(drift_row["total_turnover_required"].iloc[0])
        if not drift_row.empty and "total_turnover_required" in drift_row
        else 0.0,
    }


def build_phase19b_deep_stress_metrics(
    canonical_finalists: pd.DataFrame,
    candidate_metrics: pd.DataFrame,
    *,
    reports_dir: Path,
    section: dict[str, Any],
) -> pd.DataFrame:
    if canonical_finalists.empty:
        return pd.DataFrame()

    stress = section.get("stress_tests", {}) or {}
    btc_gap_penalty_enabled = _bool_value(stress.get("btc_weekend_gap_penalty_enabled", True))
    btc_gap_penalty_pct = float(stress.get("btc_gap_penalty_pct", 2.0))
    transaction_tables = _transaction_complexity_tables(reports_dir)

    rows: list[dict[str, Any]] = []
    for group, members in canonical_finalists.groupby("equivalent_candidate_group", sort=False):
        representative = members.sort_values("average_score", ascending=False).iloc[0]
        period_rows = candidate_metrics.merge(
            members[["universe_name", "candidate_id"]],
            on=["universe_name", "candidate_id"],
            how="inner",
        )
        period_rows = period_rows.loc[
            ~period_rows.get("missing_data_flag", pd.Series(False, index=period_rows.index))
            .fillna(False)
            .astype(bool)
        ]
        complexity = _transaction_complexity_for_candidate(
            str(representative["candidate_id"]),
            transaction_tables,
        )
        mean_turnover = float(pd.to_numeric(members["mean_turnover"], errors="coerce").mean())
        transaction_burden = (
            float(complexity["transaction_rows"]) * 0.20
            + float(complexity["drift_rebalance_rows"]) * 0.05
            + float(complexity["transaction_turnover"]) * 1.50
        )
        execution_complexity_score = round(
            min(100.0, mean_turnover * 2.0 + transaction_burden),
            2,
        )
        simplicity_score = round(max(0.0, 100.0 - execution_complexity_score), 2)
        uses_btc = bool(representative["uses_btc"])
        btc_gap_penalty = btc_gap_penalty_pct if uses_btc and btc_gap_penalty_enabled else 0.0
        latest_period = period_rows.loc[
            period_rows["period_name"].astype(str) == "post_2021"
        ]
        latest_period_score = (
            float(pd.to_numeric(latest_period["score"], errors="coerce").mean())
            if not latest_period.empty
            else float(pd.to_numeric(members["average_score"], errors="coerce").mean())
        )
        number_passed = int(
            (
                (pd.to_numeric(period_rows["CAGR_edge_vs_SPY"], errors="coerce") > 0)
                & (
                    pd.to_numeric(period_rows["max_drawdown_difference_vs_SPY"], errors="coerce")
                    >= -5.0
                )
            ).sum()
        )
        number_failed = int(max(0, len(period_rows) - number_passed))
        base_score = float(pd.to_numeric(members["average_score"], errors="coerce").mean()) * 100.0
        rolling_score = float(
            pd.to_numeric(members["mean_rolling_3y_beat_SPY_pct"], errors="coerce").mean()
        )
        overall_score = round(
            base_score
            + min(10.0, rolling_score / 10.0)
            + min(10.0, max(0.0, float(representative["mean_CAGR_edge_vs_SPY"]) * 2.0))
            - execution_complexity_score * 0.12
            - btc_gap_penalty,
            2,
        )
        worst_max_drawdown = round(
            float(pd.to_numeric(members["worst_max_drawdown"], errors="coerce").min()),
            2,
        )
        quality_tier = drawdown_quality_tier(worst_max_drawdown)
        label_warning = drawdown_label_warning(quality_tier)
        rows.append(
            {
                "canonical_candidate_id": representative["canonical_candidate_id"],
                "equivalent_candidate_group": group,
                "representative_universe": representative["universe_name"],
                "representative_candidate_id": representative["candidate_id"],
                "candidate_family": representative["candidate_family"],
                "active_assets": representative["active_assets"],
                "uses_btc": uses_btc,
                "uses_expanded_assets": bool(representative["uses_expanded_assets"]),
                "mean_cagr": round(
                    float(pd.to_numeric(members["mean_CAGR"], errors="coerce").mean()),
                    3,
                ),
                "worst_period_cagr": round(
                    float(pd.to_numeric(period_rows["CAGR"], errors="coerce").min())
                    if not period_rows.empty
                    else np.nan,
                    3,
                ),
                "mean_calmar": round(
                    float(pd.to_numeric(members["mean_Calmar"], errors="coerce").mean()),
                    4,
                ),
                "worst_max_drawdown": worst_max_drawdown,
                "drawdown_quality_tier": quality_tier,
                "is_low_drawdown_candidate": quality_tier == "low_drawdown",
                "is_high_drawdown_candidate": quality_tier in HIGH_DRAWDOWN_TIERS,
                "drawdown_label_warning": label_warning,
                "mean_rolling_3y_beat_spy_pct": round(rolling_score, 3),
                "latest_period_score": round(latest_period_score, 4),
                "turnover_score": round(max(0.0, 100.0 - mean_turnover * 2.0), 2),
                "number_of_periods_passed": number_passed,
                "number_of_periods_failed": number_failed,
                "btc_max_weight": round(
                    float(pd.to_numeric(members["BTC_max_weight"], errors="coerce").max()),
                    4,
                ),
                "btc_average_weight": round(
                    float(pd.to_numeric(members["BTC_average_weight"], errors="coerce").mean()),
                    4,
                ),
                "btc_gap_penalty_applied": btc_gap_penalty > 0,
                "btc_gap_penalty_report_only": bool(uses_btc and btc_gap_penalty_enabled),
                "btc_gap_penalised_score": round(overall_score, 2),
                "execution_complexity_score": execution_complexity_score,
                "simplicity_score": simplicity_score,
                "overall_finalist_score": overall_score,
                "transaction_source": complexity["transaction_source"],
                "paper_only": True,
                "promotion_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["overall_finalist_score", "mean_cagr"],
        ascending=[False, False],
    )


def select_phase19b_paper_candidates(
    stress_metrics: pd.DataFrame,
    *,
    max_paper_candidates: int,
    include_benchmark_baseline: bool,
) -> pd.DataFrame:
    if stress_metrics.empty:
        return pd.DataFrame()

    selected_rows: list[pd.Series] = []
    selected_groups: set[str] = set()

    def add_role(candidates: pd.DataFrame, role: str) -> None:
        if len(selected_rows) >= max_paper_candidates or candidates.empty:
            return
        for _idx, row in candidates.sort_values(
            ["overall_finalist_score", "mean_cagr"],
            ascending=[False, False],
        ).iterrows():
            group = str(row["equivalent_candidate_group"])
            if group in selected_groups:
                continue
            selected = row.copy()
            selected["paper_candidate_role"] = role
            selected_rows.append(selected)
            selected_groups.add(group)
            return

    no_btc = stress_metrics.loc[~stress_metrics["uses_btc"].astype(bool)]
    simple_no_btc = no_btc.loc[
        no_btc["representative_candidate_id"].astype(str).str.contains("60_40")
    ]
    if simple_no_btc.empty:
        simple_no_btc = no_btc.loc[
            no_btc["representative_candidate_id"].astype(str).str.contains("70_30|50_50")
        ]
    add_role(
        simple_no_btc if not simple_no_btc.empty else no_btc,
        "primary_paper_candidate_clean_growth",
    )

    clean_worst_drawdown = None
    if selected_rows:
        clean_worst_drawdown = float(selected_rows[0].get("worst_max_drawdown", np.nan))

    defensive = no_btc.loc[
        (
            no_btc["candidate_family"].astype(str).str.contains("volatility|drawdown", regex=True)
            | no_btc["representative_candidate_id"].astype(str).str.contains("inverse_vol")
        )
        & no_btc["drawdown_quality_tier"].astype(str).isin(LOW_DRAWDOWN_TIERS)
        & (pd.to_numeric(no_btc["mean_rolling_3y_beat_spy_pct"], errors="coerce") >= 60.0)
    ]
    if clean_worst_drawdown is not None and np.isfinite(clean_worst_drawdown):
        defensive = defensive.loc[
            pd.to_numeric(defensive["worst_max_drawdown"], errors="coerce")
            >= clean_worst_drawdown + 10.0
        ]
    add_role(defensive, "secondary_paper_candidate_defensive")

    btc = stress_metrics.loc[stress_metrics["uses_btc"].astype(bool)]
    add_role(btc, "high_growth_high_caveat_btc_candidate")

    if include_benchmark_baseline:
        benchmark = no_btc.loc[
            no_btc["representative_candidate_id"].astype(str).str.contains("60_40")
        ]
        add_role(benchmark if not benchmark.empty else no_btc, "benchmark_reference")

    selected = pd.DataFrame(selected_rows).head(max_paper_candidates)
    if selected.empty:
        return selected
    selected["paper_candidate_only"] = True
    selected["promotion_allowed"] = False
    selected["paper_trading_ready"] = False
    selected["live_trading_allowed"] = False
    selected["real_money_allowed"] = False
    selected["broker_api_integration_allowed"] = False
    selected["major_caveats"] = selected.apply(_candidate_caveats, axis=1)
    selected["selection_reason"] = selected.apply(_selection_reason, axis=1)
    selected["selection_limitations"] = selected.apply(_selection_limitations, axis=1)
    selected["why_not_promoted"] = (
        "research/paper-tracking candidate only; no final model promotion; "
        "Phase18 safety gates remain mandatory"
    )
    return selected


def _candidate_caveats(row: pd.Series) -> str:
    caveats = []
    tier = str(row.get("drawdown_quality_tier", ""))
    if tier == "severe_drawdown":
        caveats.append("severe historical drawdown; not defensive")
    elif tier == "high_drawdown":
        caveats.append("high historical drawdown; not defensive")
    if _bool_value(row.get("uses_btc")):
        caveats.append("BTC weekend/gap risk and BTC-cap dependency")
    if _bool_value(row.get("uses_expanded_assets")):
        caveats.append("expanded-universe implementation complexity")
    if float(row.get("execution_complexity_score", 0.0) or 0.0) > 50:
        caveats.append("high execution/turnover complexity")
    if not caveats:
        caveats.append("paper-selection only; no promotion")
    return "; ".join(caveats)


def _selection_reason(row: pd.Series) -> str:
    role = str(row.get("paper_candidate_role", ""))
    if role == "primary_paper_candidate_clean_growth":
        return "simple clean no-BTC growth reference with strong CAGR and rolling beat rate"
    if role == "secondary_paper_candidate_defensive":
        return "no-BTC drawdown-control candidate that met drawdown quality and rolling beat-rate requirements"
    if role == "high_growth_high_caveat_btc_candidate":
        return "best risk-adjusted return/drawdown trade-off among finalists with BTC exposure"
    if role == "benchmark_reference":
        return "reference candidate for paper-tracking comparison"
    if role == "primary_paper_candidate_risk_adjusted":
        return "best risk-adjusted paper candidate by Phase 19B stress score"
    return "research-only paper candidate"


def _selection_limitations(row: pd.Series) -> str:
    limitations = []
    tier = str(row.get("drawdown_quality_tier", ""))
    if tier == "severe_drawdown":
        limitations.append("severe historical drawdown; not defensive")
    elif tier == "high_drawdown":
        limitations.append("high historical drawdown; not defensive")
    if _bool_value(row.get("uses_btc")):
        limitations.append("BTC weekend/gap risk; BTC allocation caveat; paper preview only")
    if not limitations:
        limitations.append("paper preview only; no promotion")
    return "; ".join(limitations)


def build_rejected_or_research_only(
    stress_metrics: pd.DataFrame,
    selected: pd.DataFrame,
) -> pd.DataFrame:
    if stress_metrics.empty:
        return pd.DataFrame()
    selected_groups = set(selected.get("equivalent_candidate_group", pd.Series(dtype=str)).astype(str))
    out = stress_metrics.loc[
        ~stress_metrics["equivalent_candidate_group"].astype(str).isin(selected_groups)
    ].copy()
    out["phase19b_classification"] = np.where(
        out["overall_finalist_score"].astype(float) >= 60.0,
        "research_only",
        "rejected",
    )
    out["promotion_allowed"] = False
    out["paper_trading_ready"] = False
    return out


def build_recommended_paper_tracking_set(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    recommended = selected.copy()
    recommended["recommended_tracking_order"] = range(1, len(recommended) + 1)
    recommended["recommended_tracking_status"] = "paper_tracking_candidate_only"
    recommended["automatic_order_allowed"] = False
    recommended["manual_review_required"] = True
    return recommended


def build_entity_roster_recommendation(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame(
            [
                {
                    "recommended_primary_roster": "",
                    "recommended_secondary_roster": "",
                    "include_spy": False,
                    "include_qqq": False,
                    "include_btc": False,
                    "include_gld": False,
                    "include_tlt": False,
                    "include_expanded_assets": False,
                    "rationale": "No Phase 19B paper candidates selected.",
                }
            ]
        )

    primary = selected.loc[
        selected["paper_candidate_role"].astype(str)
        == "primary_paper_candidate_clean_growth"
    ]
    btc = selected.loc[selected["uses_btc"].astype(bool)]
    primary_assets = (
        primary["active_assets"].iloc[0].split(",") if not primary.empty else ["SPY", "QQQ"]
    )
    secondary_assets = btc["active_assets"].iloc[0].split(",") if not btc.empty else primary_assets
    all_assets = sorted(
        {
            asset
            for text in selected["active_assets"].astype(str)
            for asset in text.split(",")
            if asset
        }
    )

    include_expanded = any(asset in EXPANDED_ASSETS for asset in all_assets)
    return pd.DataFrame(
        [
            {
                "recommended_primary_roster": ",".join(primary_assets),
                "recommended_secondary_roster": ",".join(secondary_assets),
                "include_spy": "SPY" in all_assets,
                "include_qqq": "QQQ" in all_assets,
                "include_btc": "BTC-USD" in all_assets,
                "include_gld": "GLD" in all_assets,
                "include_tlt": "TLT" in all_assets,
                "include_expanded_assets": include_expanded,
                "rationale": (
                    "SPY/QQQ remains the primary clean roster; BTC is optional/high-caveat "
                    "when selected; GLD/TLT and expanded assets are excluded unless they "
                    "appear in selected paper candidates."
                ),
            }
        ]
    )


def _plot_bar(frame: pd.DataFrame, *, value_col: str, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    if not frame.empty:
        plot_frame = frame.sort_values(value_col, ascending=False).head(12)
        labels = plot_frame["canonical_candidate_id"].astype(str)
        ax.bar(labels, pd.to_numeric(plot_frame[value_col], errors="coerce"))
        ax.tick_params(axis="x", labelrotation=45)
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_risk_return(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    if not frame.empty:
        ax.scatter(
            pd.to_numeric(frame["worst_max_drawdown"], errors="coerce"),
            pd.to_numeric(frame["mean_cagr"], errors="coerce"),
            s=60,
            alpha=0.75,
        )
    ax.set_title("Phase 19B Candidate Risk/Return")
    ax.set_xlabel("Worst max drawdown (%)")
    ax.set_ylabel("Mean CAGR (%)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    selected: pd.DataFrame,
    roster: pd.DataFrame,
) -> None:
    no_defensive_selected = not (
        selected.get("paper_candidate_role", pd.Series(dtype=str)).astype(str)
        == "secondary_paper_candidate_defensive"
    ).any()
    lines = [
        "# Phase 19B Finalist Validation",
        "",
        "Finalist validation only.",
        "",
        "- NO LIVE TRADING",
        "- NO REAL MONEY",
        "- NO BROKER/API",
        "- No model is promoted.",
        "- Paper candidates are candidates to track, not auto-trade.",
        "- Phase 18 safety gates remain mandatory before any paper use.",
        "- No-BTC clean candidates are growth candidates, not drawdown-protection candidates.",
        "- BTC inverse-vol has the best return/drawdown trade-off but remains high-caveat.",
        "",
        "## Selected Paper Candidates",
        "",
    ]
    if selected.empty:
        lines.append("No paper candidates were selected.")
    else:
        for row in selected.to_dict("records"):
            lines.append(
                f"- `{row['canonical_candidate_id']}`: {row['paper_candidate_role']} "
                f"({row.get('drawdown_quality_tier', 'unknown_drawdown')}; "
                "promotion_allowed=False, paper_trading_ready=False)"
            )
    if no_defensive_selected:
        lines.extend(
            [
                "",
                "## Defensive Candidate Status",
                "",
                "No no-BTC defensive candidate was selected.",
                "",
                "Reason: `no_candidate_met_drawdown_quality_requirement`.",
            ]
        )
    lines.extend(["", "## Entity Roster", ""])
    if not roster.empty:
        row = roster.iloc[0]
        lines.append(f"- Primary roster: `{row['recommended_primary_roster']}`")
        lines.append(f"- Secondary roster: `{row['recommended_secondary_roster']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _failure_outputs(
    *,
    output_dir: Path,
    dashboard_dir: Path,
    missing_sources: list[str],
    safety_flags: dict[str, bool],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    reason = "missing_required_phase19a_sources:" + ";".join(missing_sources)
    outputs = {
        "summary": _write_csv(
            output_dir / "phase19b_summary.csv",
            pd.DataFrame(
                [
                    {
                        "phase19b_decision": "strategy_factory_finalist_validation_failed_closed",
                        "missing_sources": ";".join(missing_sources),
                        "paper_candidates_selected": 0,
                        **safety_flags,
                    }
                ]
            ),
        ),
        "canonical_finalists": _write_csv(
            output_dir / "phase19b_canonical_finalists.csv",
            pd.DataFrame(),
        ),
        "deep_stress_metrics": _write_csv(
            output_dir / "phase19b_deep_stress_metrics.csv",
            pd.DataFrame(),
        ),
        "paper_candidate_shortlist": _write_csv(
            output_dir / "phase19b_paper_candidate_shortlist.csv",
            pd.DataFrame(),
        ),
        "recommended_paper_tracking_set": _write_csv(
            output_dir / "phase19b_recommended_paper_tracking_set.csv",
            pd.DataFrame(),
        ),
        "rejected_or_research_only": _write_csv(
            output_dir / "phase19b_rejected_or_research_only.csv",
            pd.DataFrame(),
        ),
        "entity_roster_recommendation": _write_csv(
            output_dir / "phase19b_entity_roster_recommendation.csv",
            build_entity_roster_recommendation(pd.DataFrame()),
        ),
        "gate_report": _write_csv(
            output_dir / "phase19b_gate_report.csv",
            pd.DataFrame(
                [
                    {"gate": "required_phase19a_sources_present", "passed": False, "notes": reason},
                    {"gate": "live_trading_false", "passed": not safety_flags["live_trading_allowed"]},
                    {"gate": "real_money_false", "passed": not safety_flags["real_money_allowed"]},
                    {"gate": "broker_api_false", "passed": not safety_flags["broker_api_integration_allowed"]},
                ]
            ),
        ),
        "conclusion": _write_csv(
            output_dir / "phase19b_conclusion.csv",
            pd.DataFrame(
                [
                    {
                        "phase19b_decision": "strategy_factory_finalist_validation_failed_closed",
                        "paper_selection_completed": False,
                        "promotion_allowed": False,
                        "paper_trading_ready": False,
                        "notes": reason,
                        **safety_flags,
                    }
                ]
            ),
        ),
    }
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        selected=pd.DataFrame(),
        roster=build_entity_roster_recommendation(pd.DataFrame()),
    )
    outputs["dashboard_index"] = dashboard_dir / "index.md"
    return outputs


def save_phase19b_strategy_factory_finalist_validation(
    *,
    config: dict[str, Any],
    reports_dir: Path,
) -> dict[str, Path]:
    section = _phase_config(config)
    output_dir = Path(
        section.get("output_dir", reports_dir / "strategy_factory/finalist_validation")
    )
    dashboard_dir = Path(section.get("dashboard_dir", output_dir / "dashboard"))
    source_dir = Path(
        section.get("source_multiverse_dir", reports_dir / "strategy_factory/multiverse")
    )
    safety_flags = {
        "paper_only": _bool_value(section.get("paper_only", True)),
        "live_trading_allowed": _bool_value(section.get("live_trading_allowed", False)),
        "real_money_allowed": _bool_value(section.get("real_money_allowed", False)),
        "broker_api_integration_allowed": _bool_value(
            section.get("broker_api_integration_allowed", False)
        ),
    }
    frames, missing_sources = _load_required_sources(source_dir)
    if missing_sources:
        return _failure_outputs(
            output_dir=output_dir,
            dashboard_dir=dashboard_dir,
            missing_sources=missing_sources,
            safety_flags=safety_flags,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    canonical = canonicalise_phase19a_finalists(frames["finalists"])
    stress_metrics = build_phase19b_deep_stress_metrics(
        canonical,
        frames["candidate_metrics"],
        reports_dir=reports_dir,
        section=section,
    )
    max_paper_candidates = int(section.get("max_paper_candidates", 4))
    selected = select_phase19b_paper_candidates(
        stress_metrics,
        max_paper_candidates=max_paper_candidates,
        include_benchmark_baseline=_bool_value(section.get("include_benchmark_baseline", True)),
    )
    recommended_tracking_set = build_recommended_paper_tracking_set(selected)
    rejected = build_rejected_or_research_only(stress_metrics, selected)
    roster = build_entity_roster_recommendation(selected)
    defensive_candidate_selected = (
        not selected.empty
        and (
            selected["paper_candidate_role"].astype(str)
            == "secondary_paper_candidate_defensive"
        ).any()
    )
    defensive_selection_reason = (
        "defensive_candidate_selected"
        if defensive_candidate_selected
        else "no_candidate_met_drawdown_quality_requirement"
    )
    gate_passed = (
        not canonical.empty
        and not stress_metrics.empty
        and not selected.empty
        and len(selected) <= max_paper_candidates
        and safety_flags["paper_only"]
        and not safety_flags["live_trading_allowed"]
        and not safety_flags["real_money_allowed"]
        and not safety_flags["broker_api_integration_allowed"]
    )

    outputs: dict[str, Path] = {}
    outputs["summary"] = _write_csv(
        output_dir / "phase19b_summary.csv",
        pd.DataFrame(
            [
                {
                    "phase19b_decision": "strategy_factory_finalist_validation_completed_no_promotion"
                    if gate_passed
                    else "strategy_factory_finalist_validation_failed_closed",
                    "canonical_groups": int(canonical["equivalent_candidate_group"].nunique()),
                    "paper_candidates_selected": len(selected),
                    "defensive_candidate_selected": defensive_candidate_selected,
                    "defensive_selection_reason": defensive_selection_reason,
                    "promotion_allowed": False,
                    "paper_trading_ready": False,
                    **safety_flags,
                }
            ]
        ),
    )
    outputs["canonical_finalists"] = _write_csv(
        output_dir / "phase19b_canonical_finalists.csv",
        canonical,
    )
    outputs["deep_stress_metrics"] = _write_csv(
        output_dir / "phase19b_deep_stress_metrics.csv",
        stress_metrics,
    )
    outputs["paper_candidate_shortlist"] = _write_csv(
        output_dir / "phase19b_paper_candidate_shortlist.csv",
        selected,
    )
    outputs["recommended_paper_tracking_set"] = _write_csv(
        output_dir / "phase19b_recommended_paper_tracking_set.csv",
        recommended_tracking_set,
    )
    outputs["rejected_or_research_only"] = _write_csv(
        output_dir / "phase19b_rejected_or_research_only.csv",
        rejected,
    )
    outputs["entity_roster_recommendation"] = _write_csv(
        output_dir / "phase19b_entity_roster_recommendation.csv",
        roster,
    )
    outputs["gate_report"] = _write_csv(
        output_dir / "phase19b_gate_report.csv",
        pd.DataFrame(
            [
                {"gate": "required_phase19a_sources_present", "passed": True},
                {"gate": "canonical_finalists_written", "passed": outputs["canonical_finalists"].exists()},
                {"gate": "deep_stress_metrics_written", "passed": outputs["deep_stress_metrics"].exists()},
                {"gate": "paper_candidate_shortlist_written", "passed": outputs["paper_candidate_shortlist"].exists()},
                {"gate": "recommended_paper_tracking_set_written", "passed": outputs["recommended_paper_tracking_set"].exists()},
                {"gate": "paper_candidate_limit_respected", "passed": len(selected) <= max_paper_candidates},
                {"gate": "paper_only_true", "passed": safety_flags["paper_only"]},
                {"gate": "live_trading_false", "passed": not safety_flags["live_trading_allowed"]},
                {"gate": "real_money_false", "passed": not safety_flags["real_money_allowed"]},
                {"gate": "broker_api_false", "passed": not safety_flags["broker_api_integration_allowed"]},
                {"gate": "promotion_allowed_false", "passed": True},
            ]
        ),
    )
    outputs["conclusion"] = _write_csv(
        output_dir / "phase19b_conclusion.csv",
        pd.DataFrame(
            [
                {
                    "phase19b_decision": "strategy_factory_finalist_validation_completed_no_promotion"
                    if gate_passed
                    else "strategy_factory_finalist_validation_failed_closed",
                    "paper_selection_completed": gate_passed,
                    "defensive_candidate_selected": defensive_candidate_selected,
                    "defensive_selection_reason": defensive_selection_reason,
                    "final_model_promoted": False,
                    "promotion_allowed": False,
                    "paper_trading_ready": False,
                    "notes": "Research/paper-selection only. Phase18 safety gates remain mandatory.",
                    **safety_flags,
                }
            ]
        ),
    )

    outputs["dashboard_shortlist"] = _write_csv(
        dashboard_dir / "paper_candidate_shortlist.csv",
        selected,
    )
    outputs["dashboard_candidate_role_summary"] = _write_csv(
        dashboard_dir / "candidate_role_summary.csv",
        selected[
            [
                "paper_candidate_role",
                "canonical_candidate_id",
                "representative_candidate_id",
                "drawdown_quality_tier",
                "selection_reason",
                "selection_limitations",
            ]
        ]
        if not selected.empty
        else pd.DataFrame(),
    )
    outputs["dashboard_entity_roster"] = _write_csv(
        dashboard_dir / "entity_roster_recommendation.csv",
        roster,
    )
    outputs["dashboard_stress_table"] = _write_csv(
        dashboard_dir / "candidate_stress_table.csv",
        stress_metrics,
    )
    outputs["dashboard_caveats"] = _write_csv(
        dashboard_dir / "candidate_caveats.csv",
        selected[
            [
                "canonical_candidate_id",
                "drawdown_quality_tier",
                "drawdown_label_warning",
                "major_caveats",
                "selection_limitations",
            ]
        ]
        if not selected.empty
        else pd.DataFrame(),
    )
    _plot_bar(
        stress_metrics,
        value_col="overall_finalist_score",
        title="Phase 19B Top Finalist Scores",
        path=dashboard_dir / "top_finalists_score.png",
    )
    _plot_risk_return(stress_metrics, dashboard_dir / "candidate_risk_return.png")
    _plot_bar(
        stress_metrics,
        value_col="worst_max_drawdown",
        title="Phase 19B Drawdown Comparison",
        path=dashboard_dir / "candidate_drawdown_comparison.png",
    )
    _plot_bar(
        stress_metrics,
        value_col="execution_complexity_score",
        title="Phase 19B Execution Complexity",
        path=dashboard_dir / "candidate_complexity_score.png",
    )
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        selected=selected,
        roster=roster,
    )
    outputs["dashboard_index"] = dashboard_dir / "index.md"
    outputs["top_finalists_score"] = dashboard_dir / "top_finalists_score.png"
    outputs["candidate_risk_return"] = dashboard_dir / "candidate_risk_return.png"
    outputs["candidate_drawdown_comparison"] = dashboard_dir / "candidate_drawdown_comparison.png"
    outputs["candidate_complexity_score"] = dashboard_dir / "candidate_complexity_score.png"

    return outputs
