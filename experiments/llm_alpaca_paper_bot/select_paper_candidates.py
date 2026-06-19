from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "paper_bot_logs"

SUMMARY_OUT = LOG_DIR / "paper_candidate_selection_summary.csv"
REJECTIONS_OUT = LOG_DIR / "paper_candidate_selection_rejections.csv"
REPORT_OUT = LOG_DIR / "paper_candidate_selection_report.md"

FULL_SUMMARY_FILES = [
    LOG_DIR / "event_replay_tournament_summary.csv",
    LOG_DIR / "ma_parameter_sweep_summary.csv",
]
PERIOD_SUMMARY_FILES = [
    LOG_DIR / "event_replay_tournament_period_summary.csv",
]
SWEEP_EQUITY_FILE = LOG_DIR / "ma_parameter_sweep_equity_curves.csv"
SWEEP_VIABLE_FILE = LOG_DIR / "ma_parameter_sweep_viable.csv"
SWEEP_CLUSTER_FILE = LOG_DIR / "ma_parameter_sweep_qcc_cluster.csv"
WALK_FORWARD_FIXED_FILE = LOG_DIR / "walk_forward_ma_validation_fixed_candidates.csv"
WALK_FORWARD_SUMMARY_FILE = LOG_DIR / "walk_forward_ma_validation_summary.csv"
WALK_FORWARD_WINDOWS_FILE = LOG_DIR / "walk_forward_ma_validation_windows.csv"


@dataclass(frozen=True)
class Baselines:
    spy_cagr: float
    spy_sharpe: float
    spy_pre_2020_cagr: float
    qqq_buy_hold_drawdown: float


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _to_float(value: Any, default: float = np.nan) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if pd.notna(parsed) else default


def _to_int(value: Any, default: int = 0) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return int(float(parsed)) if pd.notna(parsed) else default


def _load_full_summaries() -> pd.DataFrame:
    frames = []
    for path in FULL_SUMMARY_FILES:
        frame = _read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["source_file"] = path.name
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No candidate summary CSV files found in paper_bot_logs")
    full = pd.concat(frames, ignore_index=True)
    full = full.drop_duplicates("strategy", keep="last")
    numeric = [
        "final_equity",
        "total_return_pct",
        "cagr_pct",
        "ann_vol_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "avg_exposure",
        "active_days",
        "trade_count",
        "fast",
        "slow",
    ]
    for column in numeric:
        if column in full.columns:
            full[column] = pd.to_numeric(full[column], errors="coerce")
    return full


def _load_period_summaries() -> pd.DataFrame:
    frames = []
    for path in PERIOD_SUMMARY_FILES:
        frame = _read_csv(path)
        if not frame.empty:
            frame = frame.copy()
            frame["source_file"] = path.name
            frames.append(frame)
    if frames:
        periods = pd.concat(frames, ignore_index=True)
    else:
        periods = pd.DataFrame()
    if not periods.empty:
        for column in ["cagr_pct", "sharpe_0rf", "max_drawdown_pct", "trade_count"]:
            if column in periods.columns:
                periods[column] = pd.to_numeric(periods[column], errors="coerce")
    return periods


def _metric_from_equity(curve: pd.DataFrame, strategy: str, start: str, end: str) -> dict[str, float]:
    if strategy not in curve.columns:
        return {
            "cagr_pct": np.nan,
            "sharpe_0rf": np.nan,
            "max_drawdown_pct": np.nan,
            "days": 0,
        }
    working = curve[["Date", strategy]].copy()
    working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    values = pd.to_numeric(working[strategy], errors="coerce")
    mask = working["Date"].between(pd.Timestamp(start), pd.Timestamp(end))
    sample = pd.DataFrame({"date": working.loc[mask, "Date"], "equity": values.loc[mask]}).dropna()
    if len(sample) < 3:
        return {
            "cagr_pct": np.nan,
            "sharpe_0rf": np.nan,
            "max_drawdown_pct": np.nan,
            "days": int(len(sample)),
        }
    start_value = float(sample["equity"].iloc[0])
    end_value = float(sample["equity"].iloc[-1])
    years = max((sample["date"].iloc[-1] - sample["date"].iloc[0]).days / 365.25, 1e-9)
    cagr = (end_value / start_value) ** (1.0 / years) - 1.0 if start_value > 0 else np.nan
    returns = sample["equity"].pct_change().dropna()
    vol = float(returns.std(ddof=0) * np.sqrt(252)) if len(returns) else np.nan
    mean = float(returns.mean() * 252) if len(returns) else np.nan
    sharpe = mean / vol if vol and np.isfinite(vol) and vol > 0 else np.nan
    drawdown = sample["equity"] / sample["equity"].cummax() - 1.0
    return {
        "cagr_pct": float(cagr * 100),
        "sharpe_0rf": float(sharpe) if np.isfinite(sharpe) else np.nan,
        "max_drawdown_pct": float(drawdown.min() * 100),
        "days": int(len(sample)),
    }


def _period_lookup_from_curves(full: pd.DataFrame) -> pd.DataFrame:
    curve = _read_csv(SWEEP_EQUITY_FILE)
    if curve.empty:
        return pd.DataFrame()
    rows = []
    periods = {
        "pre_2020": ("2006-01-03", "2019-12-31"),
        "post_2020": ("2020-01-01", "2026-06-17"),
    }
    for strategy in full["strategy"].astype(str):
        if strategy not in curve.columns:
            continue
        for period, (start, end) in periods.items():
            metrics = _metric_from_equity(curve, strategy, start, end)
            rows.append(
                {
                    "strategy": strategy,
                    "period": period,
                    "start": start,
                    "end": end,
                    **metrics,
                    "source_file": SWEEP_EQUITY_FILE.name,
                }
            )
    return pd.DataFrame(rows)


def _build_period_table(full: pd.DataFrame) -> pd.DataFrame:
    period_summary = _load_period_summaries()
    sweep_periods = _period_lookup_from_curves(full)
    frames = [frame for frame in [period_summary, sweep_periods] if not frame.empty]
    if not frames:
        return pd.DataFrame()
    periods = pd.concat(frames, ignore_index=True)
    periods = periods.drop_duplicates(["strategy", "period"], keep="last")
    return periods


def _baseline_values(full: pd.DataFrame, periods: pd.DataFrame) -> Baselines:
    spy = full.loc[full["strategy"].astype(str).eq("SPY_buy_hold")]
    qqq = full.loc[full["strategy"].astype(str).eq("QQQ_buy_hold")]
    if spy.empty or qqq.empty:
        raise ValueError("SPY_buy_hold and QQQ_buy_hold baselines are required")
    spy_pre = periods.loc[
        periods["strategy"].astype(str).eq("SPY_buy_hold")
        & periods["period"].astype(str).eq("pre_2020")
    ]
    return Baselines(
        spy_cagr=_to_float(spy.iloc[0]["cagr_pct"]),
        spy_sharpe=_to_float(spy.iloc[0]["sharpe_0rf"]),
        spy_pre_2020_cagr=_to_float(spy_pre.iloc[0]["cagr_pct"]) if not spy_pre.empty else np.nan,
        qqq_buy_hold_drawdown=_to_float(qqq.iloc[0]["max_drawdown_pct"]),
    )


def _period_metric(periods: pd.DataFrame, strategy: str, period: str, metric: str) -> float:
    if periods.empty:
        return np.nan
    rows = periods.loc[
        periods["strategy"].astype(str).eq(strategy)
        & periods["period"].astype(str).eq(period)
    ]
    if rows.empty or metric not in rows.columns:
        return np.nan
    return _to_float(rows.iloc[0][metric])


def _cluster_members() -> set[str]:
    cluster = _read_csv(SWEEP_CLUSTER_FILE)
    if cluster.empty or "strategy" not in cluster.columns:
        return set()
    return set(cluster["strategy"].astype(str))


def _viable_members() -> set[str]:
    viable = _read_csv(SWEEP_VIABLE_FILE)
    if viable.empty or "strategy" not in viable.columns:
        return set()
    return set(viable["strategy"].astype(str))


def _load_walk_forward_summary() -> pd.DataFrame:
    wf = _read_csv(WALK_FORWARD_SUMMARY_FILE)
    if wf.empty or "strategy" not in wf.columns:
        return pd.DataFrame()
    wf = wf.copy()
    numeric = [
        "chained_total_return_pct",
        "worst_test_drawdown_pct",
        "mean_test_cagr_pct",
        "mean_test_sharpe",
        "total_test_trades",
        "wins_vs_qqq_50_200",
    ]
    for column in numeric:
        if column in wf.columns:
            wf[column] = pd.to_numeric(wf[column], errors="coerce")
    wf = wf.sort_values(
        ["chained_total_return_pct", "mean_test_sharpe"],
        ascending=False,
    ).reset_index(drop=True)
    wf["walk_forward_rank"] = range(1, len(wf) + 1)
    return wf


def _walk_forward_lookup(wf: pd.DataFrame, strategy: str) -> pd.Series | None:
    if wf.empty:
        return None
    rows = wf.loc[wf["strategy"].astype(str).eq(strategy)]
    if rows.empty:
        return None
    return rows.iloc[0]


def _adaptive_selector_underperformed(wf: pd.DataFrame) -> bool:
    selected = _walk_forward_lookup(wf, "walk_forward_selected")
    current = _walk_forward_lookup(wf, "QQQ_50_200_cross")
    if selected is None or current is None:
        return False
    return _to_float(selected.get("chained_total_return_pct")) < _to_float(
        current.get("chained_total_return_pct")
    )


def _walk_forward_note(strategy: str, wf_row: pd.Series | None) -> str:
    if wf_row is None:
        return "not_evaluated_in_fixed_walk_forward_set"
    if strategy == "QQQ_buy_hold":
        return "benchmark_only_high_return_high_drawdown_not_deployable"
    if strategy == "SPY_buy_hold":
        return "benchmark_only_reference_not_deployable"
    if strategy == "QQQ_75_250_cross":
        return "walk_forward_supported_preview_replacement_candidate"
    if strategy == "QQQ_100_225_cross":
        return "walk_forward_strong_aggressive_preview_only"
    if strategy == "QQQ_above_175_cash":
        return "walk_forward_supported_conservative_preview_only"
    if strategy == "QQQ_50_200_cross":
        return "current_active_default_walk_forward_baseline"
    return "walk_forward_fixed_candidate_evaluated"


def _classify_candidate(row: pd.Series) -> str:
    strategy = str(row["strategy"])
    if "buy_hold" in strategy:
        return "buy_hold_reference"
    if str(row.get("symbol", "")).upper() == "QQQ" and str(row.get("rule_type", "")) == "cross":
        return "qqq_ma_cross"
    if str(row.get("symbol", "")).upper() == "QQQ":
        return "qqq_trend_following"
    if str(row.get("symbol", "")).upper() == "XLK":
        return "xlk_trend_following"
    return "event_or_defensive_strategy"


def _score_candidates(full: pd.DataFrame, periods: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baselines = _baseline_values(full, periods)
    cluster = _cluster_members()
    viable = _viable_members()
    wf = _load_walk_forward_summary()
    qqq_50_wf = _walk_forward_lookup(wf, "QQQ_50_200_cross")
    qqq_50_wf_return = (
        _to_float(qqq_50_wf.get("chained_total_return_pct")) if qqq_50_wf is not None else np.nan
    )
    adaptive_underperformed = _adaptive_selector_underperformed(wf)
    rows = []
    rejected = []
    for _, row in full.iterrows():
        strategy = str(row["strategy"])
        wf_row = _walk_forward_lookup(wf, strategy)
        cagr = _to_float(row.get("cagr_pct"))
        sharpe = _to_float(row.get("sharpe_0rf"))
        drawdown = _to_float(row.get("max_drawdown_pct"))
        trade_count = _to_int(row.get("trade_count"))
        cagr_edge = cagr - baselines.spy_cagr
        sharpe_edge = sharpe - baselines.spy_sharpe
        drawdown_improvement = drawdown - baselines.qqq_buy_hold_drawdown
        pre_cagr = _period_metric(periods, strategy, "pre_2020", "cagr_pct")
        post_cagr = _period_metric(periods, strategy, "post_2020", "cagr_pct")
        pre_sharpe = _period_metric(periods, strategy, "pre_2020", "sharpe_0rf")
        pre_drawdown = _period_metric(periods, strategy, "pre_2020", "max_drawdown_pct")
        post_only_penalty = 0.0
        post_only_flag = False
        if np.isfinite(pre_cagr) and np.isfinite(post_cagr):
            if pre_cagr < baselines.spy_pre_2020_cagr and post_cagr > cagr:
                post_only_penalty = 10.0
                post_only_flag = True
            if pre_cagr <= 0 and post_cagr > baselines.spy_cagr:
                post_only_penalty += 10.0
                post_only_flag = True
        trade_penalty = max(0.0, (trade_count - 150) / 10.0)
        drawdown_penalty = max(0.0, abs(min(drawdown + 35.0, 0.0)) * 1.5)
        buy_hold_penalty = 25.0 if "buy_hold" in strategy else 0.0
        cluster_bonus = 8.0 if strategy in cluster else (3.0 if strategy in viable else 0.0)
        walk_forward_chained_return = (
            _to_float(wf_row.get("chained_total_return_pct")) if wf_row is not None else np.nan
        )
        walk_forward_drawdown = (
            _to_float(wf_row.get("worst_test_drawdown_pct")) if wf_row is not None else np.nan
        )
        walk_forward_rank = _to_int(wf_row.get("walk_forward_rank"), default=0) if wf_row is not None else 0
        walk_forward_delta_vs_current = (
            walk_forward_chained_return - qqq_50_wf_return
            if np.isfinite(walk_forward_chained_return) and np.isfinite(qqq_50_wf_return)
            else 0.0
        )
        walk_forward_bonus = 0.0
        if np.isfinite(walk_forward_chained_return):
            walk_forward_bonus += max(-8.0, min(8.0, walk_forward_delta_vs_current / 25.0))
        if np.isfinite(walk_forward_drawdown):
            walk_forward_bonus += max(-4.0, min(4.0, (walk_forward_drawdown - drawdown) / 4.0))
        adaptive_underperformance_penalty = (
            2.0
            if adaptive_underperformed
            and strategy != "QQQ_50_200_cross"
            and "buy_hold" not in strategy
            and wf_row is not None
            else 0.0
        )
        missing_walk_forward_penalty = (
            6.0
            if wf_row is None
            and strategy.startswith("QQQ_")
            and "buy_hold" not in strategy
            else 0.0
        )
        score = (
            5.0 * cagr_edge
            + 18.0 * sharpe_edge
            + 0.55 * drawdown_improvement
            + cluster_bonus
            + walk_forward_bonus
            - trade_penalty
            - drawdown_penalty
            - post_only_penalty
            - buy_hold_penalty
            - adaptive_underperformance_penalty
            - missing_walk_forward_penalty
        )
        candidate_type = _classify_candidate(row)
        reasons = []
        if cagr_edge <= 0:
            reasons.append("CAGR did not beat SPY")
        if sharpe_edge <= 0:
            reasons.append("Sharpe did not beat SPY")
        if drawdown <= -35:
            reasons.append("max drawdown worse than -35%")
        if trade_count > 150:
            reasons.append("trade count above 150")
        if post_only_flag:
            reasons.append("pre-2020 robustness weak versus SPY")
        if "buy_hold" in strategy:
            reasons.append("pure buy-and-hold reference, not deployable trend rule")
        if wf_row is None and strategy.startswith("QQQ_"):
            reasons.append("not covered by fixed-candidate walk-forward validation")
        accepted = not reasons or (
            cagr_edge > 0
            and sharpe_edge > 0
            and drawdown > -35
            and trade_count <= 150
            and "buy_hold" not in strategy
        )
        out = {
            "rank_score": score,
            "strategy": strategy,
            "candidate_type": candidate_type,
            "symbol": row.get("symbol", ""),
            "rule_type": row.get("rule_type", ""),
            "fast": row.get("fast", ""),
            "slow": row.get("slow", ""),
            "cagr_pct": cagr,
            "cagr_edge_vs_spy_pct": cagr_edge,
            "sharpe_0rf": sharpe,
            "sharpe_edge_vs_spy": sharpe_edge,
            "max_drawdown_pct": drawdown,
            "drawdown_improvement_vs_qqq_bh_pp": drawdown_improvement,
            "trade_count": trade_count,
            "pre_2020_cagr_pct": pre_cagr,
            "pre_2020_sharpe": pre_sharpe,
            "pre_2020_max_drawdown_pct": pre_drawdown,
            "post_2020_cagr_pct": post_cagr,
            "robust_cluster_member": strategy in cluster,
            "viable_sweep_member": strategy in viable,
            "trade_penalty": trade_penalty,
            "drawdown_penalty": drawdown_penalty,
            "post_only_penalty": post_only_penalty,
            "buy_hold_penalty": buy_hold_penalty,
            "cluster_bonus": cluster_bonus,
            "walk_forward_chained_return_pct": walk_forward_chained_return,
            "walk_forward_worst_drawdown_pct": walk_forward_drawdown,
            "walk_forward_rank": walk_forward_rank if walk_forward_rank else np.nan,
            "walk_forward_delta_vs_qqq_50_200_pct": walk_forward_delta_vs_current,
            "walk_forward_bonus": walk_forward_bonus,
            "walk_forward_adaptive_underperformance_penalty": adaptive_underperformance_penalty,
            "missing_walk_forward_penalty": missing_walk_forward_penalty,
            "walk_forward_notes": _walk_forward_note(strategy, wf_row),
            "accepted_for_research_shortlist": accepted,
            "rejection_reasons": "; ".join(reasons),
        }
        rows.append(out)
        if reasons:
            rejected.append(
                {
                    "strategy": strategy,
                    "candidate_type": candidate_type,
                    "cagr_pct": cagr,
                    "sharpe_0rf": sharpe,
                    "max_drawdown_pct": drawdown,
                    "trade_count": trade_count,
                    "rejection_reasons": "; ".join(reasons),
                }
            )
    summary = pd.DataFrame(rows).sort_values("rank_score", ascending=False).reset_index(drop=True)
    summary.insert(0, "rank", range(1, len(summary) + 1))
    summary["candidate_recommendation"] = "research_candidate"
    summary.loc[summary["strategy"].eq("QQQ_50_200_cross"), "candidate_recommendation"] = (
        "active_default_keep_unchanged"
    )
    summary.loc[summary["strategy"].eq("QQQ_75_250_cross"), "candidate_recommendation"] = (
        "preview_replacement_candidate"
    )
    summary.loc[summary["strategy"].eq("QQQ_100_225_cross"), "candidate_recommendation"] = (
        "aggressive_preview_only"
    )
    summary.loc[summary["strategy"].eq("QQQ_above_175_cash"), "candidate_recommendation"] = (
        "conservative_preview_only"
    )
    summary.loc[summary["strategy"].str.contains("buy_hold", na=False), "candidate_recommendation"] = (
        "benchmark_only_not_deployable"
    )
    rejections = pd.DataFrame(rejected).sort_values(["candidate_type", "strategy"]).reset_index(drop=True)
    return summary, rejections


def _select_roles(summary: pd.DataFrame) -> dict[str, pd.Series]:
    accepted = summary[summary["accepted_for_research_shortlist"].astype(bool)].copy()
    roles: dict[str, pd.Series] = {}
    if accepted.empty:
        return roles
    robust = accepted[accepted["robust_cluster_member"].astype(bool)]
    roles["primary"] = (robust if not robust.empty else accepted).sort_values("rank_score", ascending=False).iloc[0]
    conservative_pool = accepted[
        (accepted["max_drawdown_pct"] >= -26.0)
        & (accepted["cagr_edge_vs_spy_pct"] > 0)
    ]
    if conservative_pool.empty:
        conservative_pool = accepted.sort_values(["max_drawdown_pct", "rank_score"], ascending=[False, False])
    roles["conservative"] = conservative_pool.sort_values("rank_score", ascending=False).iloc[0]
    aggressive_pool = accepted[
        (accepted["max_drawdown_pct"] > -35.0)
        & (accepted["trade_count"] <= 75)
    ]
    if aggressive_pool.empty:
        aggressive_pool = accepted
    roles["aggressive"] = aggressive_pool.sort_values(["cagr_pct", "rank_score"], ascending=False).iloc[0]
    qqq_50 = summary[summary["strategy"].eq("QQQ_50_200_cross")]
    if not qqq_50.empty:
        roles["current_default"] = qqq_50.iloc[0]
    qqq_75 = summary[summary["strategy"].eq("QQQ_75_250_cross")]
    if not qqq_75.empty:
        roles["preview_replacement"] = qqq_75.iloc[0]
    qqq_100 = summary[summary["strategy"].eq("QQQ_100_225_cross")]
    if not qqq_100.empty:
        roles["aggressive_preview"] = qqq_100.iloc[0]
    qqq_above_175 = summary[summary["strategy"].eq("QQQ_above_175_cash")]
    if not qqq_above_175.empty:
        roles["conservative_preview"] = qqq_above_175.iloc[0]
    return roles


def _replacement_recommendation(roles: dict[str, pd.Series]) -> tuple[str, str]:
    current = roles.get("current_default")
    replacement = roles.get("preview_replacement")
    if current is None or replacement is None:
        return (
            "insufficient_data",
            "Could not compare the current QQQ 50/200 default against QQQ 75/250.",
        )
    cagr_gain = float(replacement["cagr_pct"]) - float(current["cagr_pct"])
    sharpe_ok = float(replacement["sharpe_0rf"]) >= float(current["sharpe_0rf"]) - 0.03
    drawdown_ok = float(replacement["max_drawdown_pct"]) >= float(current["max_drawdown_pct"]) - 2.0
    wf_gain = float(replacement.get("walk_forward_delta_vs_qqq_50_200_pct", 0.0))
    wf_ok = (
        np.isfinite(wf_gain)
        and wf_gain > 0
        and float(replacement.get("walk_forward_worst_drawdown_pct", -100.0))
        >= float(current.get("walk_forward_worst_drawdown_pct", -100.0)) - 2.0
    )
    if cagr_gain >= 0.75 and sharpe_ok and drawdown_ok and wf_ok and bool(replacement["robust_cluster_member"]):
        return (
            "keep_active_config_unchanged_preview_replacement",
            (
                f"{replacement['strategy']} clearly beats QQQ 50/200 in full-period and fixed "
                "walk-forward checks, but it should remain a no-order preview replacement candidate. "
                "Keep the active config unchanged while the existing accepted/unfilled paper order is open."
            ),
        )
    return (
        "keep_active_config_unchanged",
        (
            "QQQ 50/200 remains the safer live paper-bot default until the stronger candidate "
            "passes a no-order dry-run and implementation review."
        ),
    )


def _format_candidate(row: pd.Series | None) -> str:
    if row is None:
        return "not available"
    return (
        f"`{row['strategy']}`: score {float(row['rank_score']):.2f}, "
        f"CAGR {float(row['cagr_pct']):.2f}%, Sharpe {float(row['sharpe_0rf']):.3f}, "
        f"max DD {float(row['max_drawdown_pct']):.2f}%, trades {int(row['trade_count'])}"
    )


def _write_report(summary: pd.DataFrame, rejections: pd.DataFrame, roles: dict[str, pd.Series]) -> None:
    decision, rationale = _replacement_recommendation(roles)
    top_rejected = rejections.head(12)
    current = roles.get("current_default")
    replacement = roles.get("preview_replacement")
    aggressive = roles.get("aggressive_preview")
    conservative = roles.get("conservative_preview")
    lines = [
        "# Paper Candidate Selection Report",
        "",
        "Research-only. No broker calls, no Alpaca orders, no live trading, no real money.",
        "",
        "## Current Deployment Decision",
        "",
        "- Active default remains `QQQ_50_200_cross`.",
        "- Replacement candidate remains `QQQ_75_250_cross` as a no-order preview only.",
        "- `QQQ_100_225_cross` remains aggressive preview only.",
        "- `QQQ_above_175_cash` remains conservative preview only.",
        "- The no-order preview path is working and should continue running in parallel.",
        "- Do not submit more orders while the current QQQ paper BUY order is accepted/unfilled.",
        "- Next step: observe after market open/fill, then reassess with fresh paper status.",
        "",
        "## Scoring Rubric",
        "",
        "- Reward CAGR above SPY.",
        "- Reward Sharpe above SPY.",
        "- Reward lower max drawdown than QQQ buy-and-hold.",
        "- Reward fixed-candidate walk-forward performance versus QQQ 50/200.",
        "- Penalize trade count above 150.",
        "- Penalize max drawdown worse than -35%.",
        "- Penalize candidates that rely on post-2020 strength while failing pre-2020.",
        "- Penalize pure buy-and-hold strategies.",
        "- Penalize automatic replacement confidence because the adaptive walk-forward selector underperformed fixed QQQ 50/200.",
        "- Prefer robust QQQ moving-average clusters over isolated parameter points.",
        "",
        "## Selected Roles",
        "",
        f"- Best primary paper candidate: {_format_candidate(roles.get('primary'))}",
        f"- Preview replacement candidate: {_format_candidate(replacement)}",
        f"- Conservative preview only: {_format_candidate(conservative)}",
        f"- Aggressive preview only: {_format_candidate(aggressive)}",
        f"- Current live paper-bot default: {_format_candidate(current)}",
        "",
        "## Default Recommendation",
        "",
        f"- Recommendation: `{decision}`",
        f"- Rationale: {rationale}",
        "",
        "## Top Ranked Candidates",
        "",
        summary.head(12)[
            [
                "rank",
                "strategy",
                "rank_score",
                "cagr_pct",
                "sharpe_0rf",
                "max_drawdown_pct",
                "trade_count",
                "walk_forward_chained_return_pct",
                "walk_forward_worst_drawdown_pct",
                "walk_forward_rank",
                "candidate_recommendation",
                "robust_cluster_member",
                "rejection_reasons",
            ]
        ].to_markdown(index=False),
        "",
        "## Rejected Candidates",
        "",
        top_rejected[
            ["strategy", "candidate_type", "cagr_pct", "max_drawdown_pct", "trade_count", "rejection_reasons"]
        ].to_markdown(index=False)
        if not top_rejected.empty
        else "No candidates were rejected by the scoring guardrails.",
        "",
        "## Data Sufficiency",
        "",
        "Available data covers full-period summaries, event period summaries, MA sweep summaries, "
        "and MA sweep equity curves. Subperiod robustness is computed for MA candidates from equity curves. "
        "The missing next test is a no-order parallel paper-signal dry-run for the proposed replacement "
        "candidate before changing the live paper-bot default.",
        "",
        "## Exact Recommended Next Implementation Step",
        "",
        "Add a no-order parallel signal preview for the selected primary candidate alongside the existing "
        "QQQ 50/200 bot, with `DRY_RUN=true` and `ENABLE_PAPER_ORDERS` not enabled. Compare the generated "
        "signal, target quantity, and risk notes before replacing the current default.",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    full = _load_full_summaries()
    periods = _build_period_table(full)
    summary, rejections = _score_candidates(full, periods)
    roles = _select_roles(summary)
    summary.to_csv(SUMMARY_OUT, index=False)
    rejections.to_csv(REJECTIONS_OUT, index=False)
    _write_report(summary, rejections, roles)
    primary = roles.get("primary")
    decision, _rationale = _replacement_recommendation(roles)
    print("Paper candidate selection complete.")
    print(f"Summary: {SUMMARY_OUT}")
    print(f"Rejections: {REJECTIONS_OUT}")
    print(f"Report: {REPORT_OUT}")
    if primary is not None:
        print(f"Top candidate: {primary['strategy']}")
    print(f"Default recommendation: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
