from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev


CLEAN_RUN_ID = "gma5_clean_execution_20260622T075912Z_v1"
COMMON_OOS_START = "2012-05-31"
LEARNED_ONLY_START = "2015-05-29"
LEARNED_ONLY_END = "2026-05-01"
PRE_MODEL_POLICY = "no_allocation_before_training"
GFC_COVERAGE_STATUS = "unavailable_before_common_oos_start"
BIL = "BIL"

VARIANTS = [
    "gma5_equal_weight_atomic_sleeves_v1",
    "gma5_risk_weighted_atomic_sleeves_v1",
    "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
]

COST_SCENARIOS = [
    "baseline_1bps",
    "stressed_10bps",
    "stressed_25bps",
    "severe_50bps",
]

COMPARATORS = [
    "gma4_benchmark_bil_buy_hold_v1",
    "gma4_benchmark_spy_buy_hold_v1",
    "gma4_benchmark_equal_weight_22_monthly_v1",
    "gma4_abs_trend_12m_equal_weight_v1",
    "gma4_xsmom_12m_top5_inverse_vol_v1",
    "gma4_defensive_drawdown_guard_v1",
    "gma4_defensive_spy_200d_rotation_v1",
    "gma4_blend_equal_abs10_xsmom6_defensive_v1",
]

SCOREBOARD_FIELDS = [
    "variant_id",
    "cost_scenario",
    "period_start",
    "period_end",
    "session_count",
    "net_cagr",
    "annualised_volatility",
    "sharpe",
    "maximum_drawdown",
    "cumulative_net_return",
    "annualised_turnover",
    "cost_drag",
    "measurement_status",
    "source_run_id",
    "source_file",
]

TRANSITION_FIELDS = [
    "common_oos_start_date",
    "first_true_learned_ridge_decision_date",
    "pre_model_end_date",
    "pre_model_policy",
    "actual_pre_model_target_state",
    "actual_pre_model_cash_or_bil_state",
    "first_learned_weight_date",
    "first_learned_replay_date",
    "learned_only_window_start_date",
    "gfc_coverage_status",
]

COMPARATOR_FIELDS = [
    "comparator_id",
    "learned_only_path_available",
    "evidence_source",
    "availability_status",
    "reason",
]


class LearnedOnlyPostprocessError(RuntimeError):
    pass


@dataclass(frozen=True)
class PostprocessResult:
    run_dir: Path
    root_dir: Path
    scoreboard_rows: list[dict[str, str]]
    transition_rows: list[dict[str, str]]
    comparator_rows: list[dict[str, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean-run-dir",
        default="reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1",
    )
    return parser.parse_args()


def read_csv_rows(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise LearnedOnlyPostprocessError(f"missing required input: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LearnedOnlyPostprocessError(f"missing CSV header: {path.name}")
        missing = sorted(required_columns - set(reader.fieldnames))
        if missing:
            raise LearnedOnlyPostprocessError(f"missing columns in {path.name}: {missing}")
        return list(reader)


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise LearnedOnlyPostprocessError(f"missing required input: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join("---" for _ in headers) + " |")
    table.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(table)


def write_scoreboard_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# GMA-5 Learned-Only Ridge Fair-Window Scoreboard v1",
        "",
        "`2012-05-31` to `2015-05-29` is a ridge pre-model segment and is excluded "
        "from learned-only metrics.",
        "",
        "The learned-only window is a fairer comparison between ridge, equal-weight, "
        "and risk-weighted variants. This remains observed_development_evidence and "
        "not_a_pristine_final_holdout. Highest historical CAGR or Sharpe alone is "
        "not a selection rule, and no execution or promotion decision is produced. "
        "This task does not tune, expand, retire, or promote the ridge model.",
        "",
        markdown_table(
            [
                "variant_id",
                "cost_scenario",
                "period",
                "net_cagr",
                "sharpe",
                "measurement_status",
            ],
            [
                [
                    row["variant_id"],
                    row["cost_scenario"],
                    f"{row['period_start']} to {row['period_end']}",
                    row["net_cagr"],
                    row["sharpe"],
                    row["measurement_status"],
                ]
                for row in rows
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_transition_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    row = rows[0]
    lines = [
        "# GMA-5 Ridge Pre-Model Transition Audit v1",
        "",
        markdown_table(
            ["field", "value"],
            [[field, row[field]] for field in TRANSITION_FIELDS],
        ),
        "",
        "The pre-model state is read from saved clean-execution targets and ledger rows, "
        "not from assumptions. No fallback label is used unless explicitly evidenced.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_comparator_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# GMA-5 Learned-Only Comparator Availability v1",
        "",
        "Comparator paths are marked available only when saved date-indexed artifacts "
        "support learned-only measurement. No GMA-4 replay or path reconstruction is used.",
        "",
        markdown_table(
            ["comparator_id", "available", "status", "reason"],
            [
                [
                    row["comparator_id"],
                    row["learned_only_path_available"],
                    row["availability_status"],
                    row["reason"],
                ]
                for row in rows
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def date_in_window(value: str) -> bool:
    return LEARNED_ONLY_START <= value <= LEARNED_ONLY_END


def empty_score_row(variant_id: str, cost_scenario: str, reason: str) -> dict[str, str]:
    return {
        "variant_id": variant_id,
        "cost_scenario": cost_scenario,
        "period_start": LEARNED_ONLY_START,
        "period_end": LEARNED_ONLY_END,
        "session_count": "",
        "net_cagr": "",
        "annualised_volatility": "",
        "sharpe": "",
        "maximum_drawdown": "",
        "cumulative_net_return": "",
        "annualised_turnover": "",
        "cost_drag": "",
        "measurement_status": "not_available_from_saved_artifacts",
        "source_run_id": CLEAN_RUN_ID,
        "source_file": reason,
    }


def returns_from_portfolio_values(rows: list[dict[str, str]]) -> list[float]:
    ordered = sorted(rows, key=lambda item: item["date"])
    values = [float(row["portfolio_value"]) for row in ordered if row.get("portfolio_value", "")]
    if len(values) < 2:
        return []
    return [(right / left) - 1.0 for left, right in zip(values, values[1:], strict=False)]


def calculate_metrics(rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    if "net_return" in rows[0] and any(row.get("net_return", "") != "" for row in rows):
        returns = [float(row["net_return"]) for row in sorted(rows, key=lambda item: item["date"])]
    elif "portfolio_value" in rows[0] and any(row.get("portfolio_value", "") != "" for row in rows):
        returns = returns_from_portfolio_values(rows)
    else:
        return None
    if not returns:
        return None
    cumulative_curve = []
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for item in returns:
        wealth *= 1.0 + item
        cumulative_curve.append(wealth)
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, (wealth / peak) - 1.0)
    cumulative_return = cumulative_curve[-1] - 1.0
    years = max(len(returns) / 252.0, 1 / 252.0)
    net_cagr = (1.0 + cumulative_return) ** (1.0 / years) - 1.0
    annualised_vol = stdev(returns) * math.sqrt(252.0) if len(returns) > 1 else 0.0
    sharpe = (
        (mean(returns) / stdev(returns)) * math.sqrt(252.0)
        if len(returns) > 1 and stdev(returns)
        else 0.0
    )
    turnover = sum(abs(float(row.get("trade_delta", "0") or 0.0)) for row in rows) / years
    cost_drag = sum(float(row.get("transaction_cost", "0") or 0.0) for row in rows)
    return {
        "session_count": str(len(returns)),
        "net_cagr": str(net_cagr),
        "annualised_volatility": str(annualised_vol),
        "sharpe": str(sharpe),
        "maximum_drawdown": str(max_drawdown),
        "cumulative_net_return": str(cumulative_return),
        "annualised_turnover": str(turnover),
        "cost_drag": str(cost_drag),
    }


def build_scoreboard_rows(ledger_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    has_required = (
        {"variant_id", "cost_scenario", "date"} <= set(ledger_rows[0]) if ledger_rows else False
    )
    has_path = (
        bool(ledger_rows)
        and has_required
        and ("net_return" in ledger_rows[0] or "portfolio_value" in ledger_rows[0])
    )
    rows = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    if has_path:
        for row in ledger_rows:
            if (row["variant_id"] in VARIANTS or row["variant_id"] in COMPARATORS) and row[
                "cost_scenario"
            ] in COST_SCENARIOS:
                if date_in_window(row["date"]):
                    grouped[(row["variant_id"], row["cost_scenario"])].append(row)
    for variant_id in VARIANTS + COMPARATORS:
        for cost_scenario in COST_SCENARIOS:
            metrics = calculate_metrics(grouped[(variant_id, cost_scenario)]) if has_path else None
            if metrics is None:
                if variant_id in COMPARATORS:
                    continue
                reason = (
                    "gma5_composite_replay_ledger_v2.csv lacks cost_scenario and "
                    "date-indexed portfolio_value/net_return evidence"
                    if not has_path
                    else "gma5_composite_replay_ledger_v2.csv lacks usable rows for this variant/cost"
                )
                rows.append(empty_score_row(variant_id, cost_scenario, reason))
            else:
                rows.append(
                    {
                        "variant_id": variant_id,
                        "cost_scenario": cost_scenario,
                        "period_start": LEARNED_ONLY_START,
                        "period_end": LEARNED_ONLY_END,
                        **metrics,
                        "measurement_status": "available_from_saved_artifacts",
                        "source_run_id": CLEAN_RUN_ID,
                        "source_file": "gma5_composite_replay_ledger_v2.csv",
                    }
                )
    return rows


def classify_pre_model_target_state(target_rows: list[dict[str, str]]) -> tuple[str, str, str]:
    ridge_rows = [
        row
        for row in target_rows
        if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
        and COMMON_OOS_START <= row["decision_date"] < LEARNED_ONLY_START
    ]
    if not ridge_rows:
        return "not_available_from_saved_artifacts", "not_available_from_saved_artifacts", ""
    dates = sorted({row["decision_date"] for row in ridge_rows})
    all_bil_only = True
    for date_value in dates:
        daily = [row for row in ridge_rows if row["decision_date"] == date_value]
        bil_weight = sum(
            float(row["composite_etf_target_weight"]) for row in daily if row["symbol"] == BIL
        )
        non_bil = sum(
            abs(float(row["composite_etf_target_weight"])) for row in daily if row["symbol"] != BIL
        )
        if abs(bil_weight - 1.0) > 1e-10 or non_bil > 1e-10:
            all_bil_only = False
            break
    if all_bil_only:
        return "bil_only_targets", "bil_weight_100_percent", dates[-1]
    return "mixed_or_non_bil_targets", "not_bil_only", dates[-1]


def first_available_weight_date(weight_rows: list[dict[str, str]]) -> str:
    dates = sorted(
        {
            row["decision_date"]
            for row in weight_rows
            if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
            and row["status"] == "available"
            and any(
                float(candidate["sleeve_allocation_weight"]) > 0
                for candidate in weight_rows
                if candidate["variant_id"] == row["variant_id"]
                and candidate["decision_date"] == row["decision_date"]
            )
        }
    )
    return dates[0] if dates else ""


def first_replay_date(ledger_rows: list[dict[str, str]]) -> str:
    dates = sorted(
        {
            row["date"]
            for row in ledger_rows
            if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
            and row["date"] >= LEARNED_ONLY_START
        }
    )
    return dates[0] if dates else ""


def build_transition_rows(
    target_rows: list[dict[str, str]],
    weight_rows: list[dict[str, str]],
    ledger_rows: list[dict[str, str]],
    training_rows: list[dict[str, str]],
    manifest: dict[str, object],
) -> list[dict[str, str]]:
    learned_start = str(manifest.get("first_true_learned_ridge_decision", LEARNED_ONLY_START))
    if learned_start != LEARNED_ONLY_START:
        raise LearnedOnlyPostprocessError(
            f"unexpected learned-only start: {learned_start}; expected {LEARNED_ONLY_START}"
        )
    target_state, bil_state, pre_model_end = classify_pre_model_target_state(target_rows)
    first_weight = first_available_weight_date(weight_rows)
    first_training = min((row["decision_date"] for row in training_rows), default="")
    if first_weight and first_training and first_weight != first_training:
        raise LearnedOnlyPostprocessError(
            f"first learned weight date {first_weight} does not match training audit {first_training}"
        )
    return [
        {
            "common_oos_start_date": COMMON_OOS_START,
            "first_true_learned_ridge_decision_date": learned_start,
            "pre_model_end_date": pre_model_end,
            "pre_model_policy": PRE_MODEL_POLICY,
            "actual_pre_model_target_state": target_state,
            "actual_pre_model_cash_or_bil_state": bil_state,
            "first_learned_weight_date": first_weight,
            "first_learned_replay_date": first_replay_date(ledger_rows),
            "learned_only_window_start_date": LEARNED_ONLY_START,
            "gfc_coverage_status": GFC_COVERAGE_STATUS,
        }
    ]


def build_comparator_rows(ledger_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    available_ids = set()
    if (
        ledger_rows
        and {"variant_id", "cost_scenario", "date"} <= set(ledger_rows[0])
        and ("net_return" in ledger_rows[0] or "portfolio_value" in ledger_rows[0])
    ):
        available_ids = {
            row["variant_id"]
            for row in ledger_rows
            if row["variant_id"] in COMPARATORS and date_in_window(row["date"])
        }
    rows = []
    for comparator_id in COMPARATORS:
        available = comparator_id in available_ids
        rows.append(
            {
                "comparator_id": comparator_id,
                "learned_only_path_available": str(available).lower(),
                "evidence_source": "gma5_composite_replay_ledger_v2.csv",
                "availability_status": "available_from_saved_artifacts"
                if available
                else "not_available_from_saved_artifacts",
                "reason": "saved date-indexed comparator path exists"
                if available
                else "clean execution artifacts contain variant composite paths only; no saved comparator learned-only return path",
            }
        )
    return rows


def copy_latest(run_path: Path, root_path: Path) -> None:
    root_path.write_bytes(run_path.read_bytes())


def run_postprocess(clean_run_dir: Path) -> PostprocessResult:
    root_dir = clean_run_dir.parents[1]
    ledger_rows = read_csv_rows(
        clean_run_dir / "gma5_composite_replay_ledger_v2.csv", {"date", "variant_id"}
    )
    weight_rows = read_csv_rows(
        clean_run_dir / "gma5_ensemble_monthly_sleeve_weights.csv",
        {"variant_id", "decision_date", "sleeve_id", "sleeve_allocation_weight", "status"},
    )
    target_rows = read_csv_rows(
        clean_run_dir / "gma5_ensemble_monthly_etf_targets.csv",
        {"variant_id", "decision_date", "symbol", "composite_etf_target_weight"},
    )
    training_rows = read_csv_rows(
        clean_run_dir / "gma5_ensemble_training_audit.csv",
        {"decision_date", "sleeve_id", "training_row_count", "ridge_alpha"},
    )
    manifest = read_json(clean_run_dir / "gma5_clean_execution_manifest_v1.json")
    read_json(clean_run_dir / "gma5_runtime_replay_trace_v1.json")
    read_csv_rows(clean_run_dir / "gma5_clean_execution_comparison_v1.csv", {"artifact", "status"})

    scoreboard_rows = build_scoreboard_rows(ledger_rows)
    transition_rows = build_transition_rows(
        target_rows, weight_rows, ledger_rows, training_rows, manifest
    )
    comparator_rows = build_comparator_rows(ledger_rows)

    output_specs = [
        (
            "gma5_learned_only_window_scoreboard_v1.csv",
            scoreboard_rows,
            SCOREBOARD_FIELDS,
        ),
        (
            "gma5_ridge_pre_model_transition_audit_v1.csv",
            transition_rows,
            TRANSITION_FIELDS,
        ),
        (
            "gma5_learned_only_comparator_availability_v1.csv",
            comparator_rows,
            COMPARATOR_FIELDS,
        ),
    ]
    for name, rows, fields in output_specs:
        run_output = clean_run_dir / name
        root_output = root_dir / name
        write_csv(run_output, rows, fields)
        copy_latest(run_output, root_output)

    markdown_specs = [
        (
            clean_run_dir / "gma5_learned_only_window_scoreboard_v1.md",
            root_dir / "gma5_learned_only_window_scoreboard_v1.md",
            lambda path: write_scoreboard_markdown(path, scoreboard_rows),
        ),
        (
            clean_run_dir / "gma5_ridge_pre_model_transition_audit_v1.md",
            root_dir / "gma5_ridge_pre_model_transition_audit_v1.md",
            lambda path: write_transition_markdown(path, transition_rows),
        ),
        (
            clean_run_dir / "gma5_learned_only_comparator_availability_v1.md",
            root_dir / "gma5_learned_only_comparator_availability_v1.md",
            lambda path: write_comparator_markdown(path, comparator_rows),
        ),
    ]
    for run_output, root_output, writer in markdown_specs:
        writer(run_output)
        copy_latest(run_output, root_output)

    return PostprocessResult(
        run_dir=clean_run_dir,
        root_dir=root_dir,
        scoreboard_rows=scoreboard_rows,
        transition_rows=transition_rows,
        comparator_rows=comparator_rows,
    )


def main() -> None:
    args = parse_args()
    run_postprocess(Path(args.clean_run_dir))


if __name__ == "__main__":
    main()
