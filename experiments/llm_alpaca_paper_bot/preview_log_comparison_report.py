from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "paper_bot_logs"

PARALLEL_PREVIEW_LOG = LOG_DIR / "ma_parallel_signal_preview.jsonl"
CONFIG_SIGNAL_LOG = LOG_DIR / "config_driven_paper_signal.jsonl"

SUMMARY_OUT = LOG_DIR / "preview_log_comparison_summary.csv"
DISAGREEMENTS_OUT = LOG_DIR / "preview_log_comparison_disagreements.csv"
REPORT_OUT = LOG_DIR / "preview_log_comparison_report.md"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _timestamp(row: dict[str, Any]) -> str:
    return str(row.get("timestamp_utc", ""))


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=_timestamp)[-1]


def _normalize_strategy(strategy: str) -> str:
    out = strategy.strip()
    suffixes = [
        "_current_default",
        "_candidate",
        "_raw_highest_score",
        "_conservative",
        "_current",
    ]
    for suffix in suffixes:
        if out.endswith(suffix):
            out = out[: -len(suffix)]
    return out


def _flatten_parallel(row: dict[str, Any] | None) -> pd.DataFrame:
    if row is None:
        return pd.DataFrame()
    records = []
    for item in row.get("results", []):
        if not isinstance(item, dict):
            continue
        strategy = str(item.get("strategy", ""))
        records.append(
            {
                "source": "ma_parallel_signal_preview",
                "timestamp_utc": row.get("timestamp_utc", ""),
                "mode": row.get("mode", ""),
                "strategy": strategy,
                "normalized_strategy": _normalize_strategy(strategy),
                "role": "parallel_preview",
                "preview_action": item.get("preview_action", ""),
                "signal_in_market": bool(item.get("signal_in_market", False)),
                "latest_bar_timestamp": item.get("latest_bar_timestamp", ""),
                "latest_close": item.get("latest_close", ""),
            }
        )
    return pd.DataFrame(records)


def _flatten_config_previews(row: dict[str, Any] | None) -> pd.DataFrame:
    if row is None:
        return pd.DataFrame()
    records = []
    for item in row.get("results", []):
        if not isinstance(item, dict):
            continue
        strategy = str(item.get("strategy", ""))
        records.append(
            {
                "source": "config_driven_preview",
                "timestamp_utc": row.get("timestamp_utc", ""),
                "mode": row.get("mode", ""),
                "strategy": strategy,
                "normalized_strategy": _normalize_strategy(strategy),
                "role": item.get("role", ""),
                "preview_action": item.get("preview_action", ""),
                "signal_in_market": bool(item.get("signal_in_market", False)),
                "latest_bar_timestamp": item.get("latest_bar_timestamp", ""),
                "latest_close": item.get("latest_close", ""),
            }
        )
    return pd.DataFrame(records)


def _latest_config_preview(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    previews = [row for row in rows if "results" in row and "active_strategy" in row]
    return _latest(previews)


def _latest_config_signal(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    signals = [row for row in rows if "signal" in row and "execution" in row]
    return _latest(signals)


def _find_disagreements(previews: pd.DataFrame) -> pd.DataFrame:
    if previews.empty:
        return pd.DataFrame(
            columns=[
                "comparison_group",
                "strategy",
                "normalized_strategy",
                "issue",
                "active_action",
                "candidate_action",
            ]
        )

    disagreements = []
    for source, group in previews.groupby("source"):
        active_rows = group[group["role"].astype(str).eq("active_default")]
        if active_rows.empty and source == "ma_parallel_signal_preview":
            active_rows = group[group["normalized_strategy"].eq("QQQ_50_200_cross")]
        if active_rows.empty:
            continue
        active_action = str(active_rows.iloc[0]["preview_action"])
        for _, row in group.iterrows():
            candidate_action = str(row["preview_action"])
            if candidate_action != active_action:
                disagreements.append(
                    {
                        "comparison_group": source,
                        "strategy": row["strategy"],
                        "normalized_strategy": row["normalized_strategy"],
                        "issue": "candidate_action_differs_from_active",
                        "active_action": active_action,
                        "candidate_action": candidate_action,
                    }
                )
    return pd.DataFrame(disagreements)


def _promotion_status(
    config_preview: dict[str, Any] | None,
    config_signal: dict[str, Any] | None,
    disagreements: pd.DataFrame,
) -> tuple[bool, str]:
    reasons = []
    if config_signal is None:
        reasons.append("missing_config_paper_signal_log")
    if config_preview is None and config_signal is None:
        reasons.append("missing_active_reference_log")
    if not disagreements.empty:
        reasons.append("active_candidate_disagreement")
    if config_signal is not None:
        execution = config_signal.get("execution", {})
        safety = config_signal.get("safety", {})
        open_orders = config_signal.get("open_orders_before_execution", [])
        if isinstance(open_orders, list) and open_orders:
            reasons.append("open_order_exists")
        if isinstance(execution, dict) and execution.get("submitted") is True:
            reasons.append("new_order_was_submitted_in_latest_log")
        if isinstance(safety, dict):
            if safety.get("dry_run") is not True:
                reasons.append("dry_run_not_true")
            if safety.get("config_orders_enabled") is True or safety.get("env_orders_enabled") is True:
                reasons.append("orders_enabled")
            if safety.get("paper_only") is not True:
                reasons.append("paper_only_not_true")
    if not reasons:
        reasons.append("no_blocking_reason_detected")
    blocked = reasons != ["no_blocking_reason_detected"]
    return blocked, "; ".join(reasons)


def _write_report(
    summary: pd.DataFrame,
    previews: pd.DataFrame,
    disagreements: pd.DataFrame,
    config_signal: dict[str, Any] | None,
) -> None:
    latest_action = summary.iloc[0]["latest_action"] if not summary.empty else "unknown"
    promotion_blocked = summary.iloc[0]["promotion_blocked"] if not summary.empty else True
    promotion_blocking_reason = (
        summary.iloc[0]["promotion_blocking_reason"] if not summary.empty else "missing_summary"
    )

    action_table = (
        previews[
            [
                "source",
                "role",
                "strategy",
                "preview_action",
                "signal_in_market",
                "latest_bar_timestamp",
            ]
        ].to_markdown(index=False)
        if not previews.empty
        else "No preview rows available."
    )
    disagreement_table = (
        disagreements.to_markdown(index=False)
        if not disagreements.empty
        else "No active/candidate action disagreements found."
    )

    open_order_count = 0
    latest_execution_reason = "unknown"
    if config_signal is not None:
        open_orders = config_signal.get("open_orders_before_execution", [])
        open_order_count = len(open_orders) if isinstance(open_orders, list) else 0
        execution = config_signal.get("execution", {})
        if isinstance(execution, dict):
            latest_execution_reason = str(execution.get("reason", ""))

    lines = [
        "# Preview Log Comparison Report",
        "",
        "Research/reporting only. No broker calls, no orders, no config changes.",
        "",
        "## Summary",
        "",
        f"- Latest action: `{latest_action}`",
        f"- Promotion blocked: `{promotion_blocked}`",
        f"- Blocking reason: `{promotion_blocking_reason}`",
        f"- Open order count in latest config-driven paper signal log: `{open_order_count}`",
        f"- Latest execution guard reason: `{latest_execution_reason}`",
        "",
        "## Active/Candidate Preview Actions",
        "",
        action_table,
        "",
        "## Disagreements",
        "",
        disagreement_table,
        "",
        "## Decision",
        "",
        "Keep the active config unchanged. Candidate promotion is blocked while an accepted/unfilled QQQ paper order exists, even if active and preview signals agree.",
        "",
        "## Safety",
        "",
        "- No orders submitted.",
        "- No Alpaca API calls made.",
        "- No secrets read or printed.",
        "- No config files modified.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    parallel_rows = _load_jsonl(PARALLEL_PREVIEW_LOG)
    config_rows = _load_jsonl(CONFIG_SIGNAL_LOG)

    latest_parallel = _latest(parallel_rows)
    latest_config_preview = _latest_config_preview(config_rows)
    latest_config_signal = _latest_config_signal(config_rows)

    previews = pd.concat(
        [
            _flatten_parallel(latest_parallel),
            _flatten_config_previews(latest_config_preview),
        ],
        ignore_index=True,
    )
    disagreements = _find_disagreements(previews)
    promotion_blocked, promotion_blocking_reason = _promotion_status(
        latest_config_preview,
        latest_config_signal,
        disagreements,
    )

    latest_action = ""
    active_strategy = ""
    active_action = ""
    active_preview_action = ""
    all_preview_agree = bool(disagreements.empty and not previews.empty)
    open_order_count = 0
    order_submitted = False
    execution_reason = ""
    if latest_config_preview is not None:
        active_strategy = str(latest_config_preview.get("active_strategy", ""))
        active_preview_action = str(latest_config_preview.get("active_action", ""))
        all_preview_agree = bool(latest_config_preview.get("all_preview_strategies_agree_with_active", False))
        latest_action = active_preview_action
    if latest_config_signal is not None:
        latest_action = str(latest_config_signal.get("action", latest_action))
        signal = latest_config_signal.get("signal", {})
        if isinstance(signal, dict):
            active_strategy = str(signal.get("strategy", active_strategy))
            active_preview_action = (
                "TARGET_QQQ" if bool(signal.get("signal_in_market", False)) else "TARGET_CASH"
            )
        active_action = latest_action
        open_orders = latest_config_signal.get("open_orders_before_execution", [])
        open_order_count = len(open_orders) if isinstance(open_orders, list) else 0
        execution = latest_config_signal.get("execution", {})
        if isinstance(execution, dict):
            order_submitted = bool(execution.get("submitted", False))
            execution_reason = str(execution.get("reason", ""))

    summary = pd.DataFrame(
        [
            {
                "latest_parallel_preview_timestamp_utc": _timestamp(latest_parallel or {}),
                "latest_config_preview_timestamp_utc": _timestamp(latest_config_preview or {}),
                "latest_config_signal_timestamp_utc": _timestamp(latest_config_signal or {}),
                "active_strategy": active_strategy,
                "active_action": active_action,
                "active_preview_action": active_preview_action,
                "latest_action": latest_action,
                "all_preview_strategies_agree_with_active": all_preview_agree,
                "disagreement_count": int(len(disagreements)),
                "open_order_count": int(open_order_count),
                "latest_order_submitted": bool(order_submitted),
                "latest_execution_reason": execution_reason,
                "promotion_blocked": bool(promotion_blocked),
                "promotion_blocking_reason": promotion_blocking_reason,
                "recommended_action": "keep_active_config_unchanged_continue_no_order_preview",
            }
        ]
    )

    summary.to_csv(SUMMARY_OUT, index=False)
    disagreements.to_csv(DISAGREEMENTS_OUT, index=False)
    _write_report(summary, previews, disagreements, latest_config_signal)

    print("Preview log comparison complete.")
    print(f"Summary: {SUMMARY_OUT}")
    print(f"Disagreements: {DISAGREEMENTS_OUT}")
    print(f"Report: {REPORT_OUT}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
