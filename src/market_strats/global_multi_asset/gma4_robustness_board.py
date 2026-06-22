"""Post-process a completed GMA-4 tournament into robustness research views."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

BOARD_COLUMNS = [
    "run_id",
    "trial_id",
    "strategy_id",
    "family",
    "baseline_full_history_net_cagr",
    "baseline_full_history_sharpe",
    "baseline_full_history_max_drawdown",
    "baseline_full_history_annualised_turnover",
    "baseline_full_history_cost_drag",
    "baseline_full_history_maximum_hhi_concentration",
    "severe_cost_full_history_net_cagr",
    "cost_sensitivity_cagr_change",
    "worst_rolling_3_year_net_cagr",
    "median_rolling_3_year_net_cagr",
    "positive_rolling_3_year_fraction",
    "worst_rolling_5_year_net_cagr",
    "median_rolling_5_year_net_cagr",
    "positive_rolling_5_year_fraction",
    "positive_sequential_walk_forward_fraction",
    "worst_predefined_regime_net_cagr",
    "positive_predefined_regime_fraction",
    "parameter_neighbour_support",
    "concentration_measurement_status",
    "pareto_dominated",
    "historical_research_status",
    "research_notes",
]

SCOREBOARD_REQUIRED_COLUMNS = {
    "run_id",
    "trial_id",
    "strategy_id",
    "family",
    "cost_scenario",
    "evaluation_scope",
    "window_id",
    "regime_id",
    "evaluation_effective_start_date",
    "regime_coverage_status",
    "net_cagr",
    "sharpe_0rf",
    "max_drawdown",
    "annualised_turnover",
    "cost_drag",
    "maximum_hhi_concentration",
    "status",
}

EVALUATION_DETAIL_REQUIRED_COLUMNS = {"trial_id", "cost_scenario"}
REJECTIONS_REQUIRED_COLUMNS = {"trial_id", "cost_scenario", "rejection_reason"}
MANIFEST_REQUIRED_FIELDS = {
    "run_id",
    "evidence_class",
    "holdout_status",
    "common_history_start",
    "common_history_end",
}

RUN_BOARD_CSV = "gma4_robustness_board_v1.csv"
RUN_BOARD_MD = "gma4_robustness_board_v1.md"
RUN_SHORTLIST_CSV = "gma4_historical_research_shortlist_v1.csv"
LATEST_BOARD_CSV = "gma4_latest_robustness_board_v1.csv"
LATEST_BOARD_MD = "gma4_latest_robustness_board_v1.md"
LATEST_SHORTLIST_CSV = "gma4_latest_historical_research_shortlist_v1.csv"
DISCUSSION_FILE = "gma4_results_discussion_latest_v1.md"
START_MARKER = "<!-- GMA4F_ROBUSTNESS_START -->"
END_MARKER = "<!-- GMA4F_ROBUSTNESS_END -->"

REGIME_NAMES = {
    "gfc_stress": "GFC",
    "euro_us_debt_stress": "2011 debt stress",
    "low_vol_calm_2017": "2017 calm conditions",
    "covid_crash": "COVID crash",
    "covid_recovery": "COVID recovery",
    "inflation_rate_shock_2022": "2022 inflation/rate shock",
    "geopolitical_stress_descriptive": "post-October 2023 geopolitical stress",
}


class GMA4RobustnessBoardError(RuntimeError):
    """Fail-closed robustness-board error."""


@dataclass(frozen=True)
class GMA4RobustnessBoardResult:
    run_id: str
    run_dir: Path
    board: pd.DataFrame
    shortlist: pd.DataFrame
    output_paths: dict[str, Path]


def _read_csv_required(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise GMA4RobustnessBoardError(f"required input missing: {path.name}")
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise GMA4RobustnessBoardError(f"malformed CSV input: {path.name}: {exc}") from exc
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise GMA4RobustnessBoardError(f"{path.name} missing required columns: {missing}")
    return frame


def _read_rejections(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise GMA4RobustnessBoardError(f"required input missing: {path.name}")
    if not path.read_text(encoding="utf-8").strip():
        return pd.DataFrame(columns=sorted(REJECTIONS_REQUIRED_COLUMNS))
    return _read_csv_required(path, REJECTIONS_REQUIRED_COLUMNS)


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise GMA4RobustnessBoardError(f"required input missing: {path.name}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GMA4RobustnessBoardError(f"malformed JSON input: {path.name}: {exc}") from exc
    missing = sorted(field for field in MANIFEST_REQUIRED_FIELDS if field not in manifest)
    if missing:
        raise GMA4RobustnessBoardError(f"{path.name} missing required fields: {missing}")
    return manifest


def _numeric_series(frame: pd.DataFrame, column: str, context: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise GMA4RobustnessBoardError(f"non-numeric {column} in {context}")
    return values


def _finite_or_none(value: Any) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def _single_evaluated_row(scoreboard: pd.DataFrame, trial_id: str, **filters: Any) -> pd.Series:
    mask = (scoreboard["trial_id"].astype(str) == trial_id) & (scoreboard["status"] == "evaluated")
    for column, value in filters.items():
        mask &= scoreboard[column].fillna("").astype(str) == str(value)
    rows = scoreboard.loc[mask]
    if len(rows) != 1:
        raise GMA4RobustnessBoardError(
            f"expected one evaluated row for {trial_id} with {filters}, found {len(rows)}"
        )
    return rows.iloc[0]


def _scope_rows(scoreboard: pd.DataFrame, trial_id: str, scope: str) -> pd.DataFrame:
    rows = scoreboard.loc[
        (scoreboard["trial_id"].astype(str) == trial_id)
        & (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["evaluation_scope"] == scope)
        & (scoreboard["status"] == "evaluated")
    ].copy()
    if rows.empty:
        raise GMA4RobustnessBoardError(f"missing evaluated {scope} rows for {trial_id}")
    rows["net_cagr"] = _numeric_series(rows, "net_cagr", f"{trial_id} {scope}")
    return rows


def _positive_fraction(values: pd.Series) -> float:
    if values.empty:
        raise GMA4RobustnessBoardError("cannot compute positive fraction from empty values")
    return float((values > 0).mean())


def _trial_neighbour_group(trial_id: str, family: str) -> str | None:
    if family == "absolute_trend":
        return "absolute_trend_parameter_neighbours"
    if family == "cross_sectional_momentum":
        return "cross_sectional_momentum_parameter_neighbours"
    if family == "short_horizon_mean_reversion":
        return "mean_reversion_parameter_neighbours"
    if family == "simple_blend":
        return "blend_parameter_neighbours"
    if "defensive_" in trial_id:
        return "defensive_rule_variants"
    return None


def _apply_parameter_neighbour_labels(board: pd.DataFrame) -> pd.DataFrame:
    labels: dict[str, str] = {}
    grouped: dict[str, list[str]] = {}
    for row in board.to_dict("records"):
        group = _trial_neighbour_group(str(row["trial_id"]), str(row["family"]))
        if group is not None:
            grouped.setdefault(group, []).append(str(row["trial_id"]))
        else:
            labels[str(row["trial_id"])] = "not_applicable"

    for trial_ids in grouped.values():
        if len(trial_ids) < 2:
            labels[trial_ids[0]] = "isolated_variant"
            continue
        subset = board.loc[board["trial_id"].isin(trial_ids)]
        baseline_span = (
            subset["baseline_full_history_net_cagr"].max()
            - subset["baseline_full_history_net_cagr"].min()
        )
        severe_positive = bool((subset["severe_cost_full_history_net_cagr"] > 0).all())
        rolling_positive = bool((subset["positive_rolling_3_year_fraction"] >= 0.5).all())
        label = (
            "broadly_consistent"
            if baseline_span <= 0.04 and severe_positive and rolling_positive
            else "mixed"
        )
        for trial_id in trial_ids:
            labels[trial_id] = label

    board = board.copy()
    board["parameter_neighbour_support"] = board["trial_id"].map(labels).fillna("not_applicable")
    return board


def _pareto_flags(board: pd.DataFrame) -> pd.Series:
    dominated: dict[str, bool] = {}
    dimensions = [
        "baseline_full_history_net_cagr",
        "severe_cost_full_history_net_cagr",
        "baseline_full_history_max_drawdown",
        "positive_rolling_3_year_fraction",
        "baseline_full_history_annualised_turnover",
    ]
    for row in board.to_dict("records"):
        trial_id = str(row["trial_id"])
        dominated[trial_id] = False
        if str(row["concentration_measurement_status"]) != "concentration_measurement_available":
            continue
        for other in board.to_dict("records"):
            if other["trial_id"] == row["trial_id"]:
                continue
            if (
                str(other["concentration_measurement_status"])
                != "concentration_measurement_available"
            ):
                continue
            comparisons = {
                "baseline_full_history_net_cagr": other[dimensions[0]] >= row[dimensions[0]],
                "severe_cost_full_history_net_cagr": other[dimensions[1]] >= row[dimensions[1]],
                "baseline_full_history_max_drawdown": other[dimensions[2]] >= row[dimensions[2]],
                "positive_rolling_3_year_fraction": other[dimensions[3]] >= row[dimensions[3]],
                "baseline_full_history_annualised_turnover": other[dimensions[4]]
                <= row[dimensions[4]],
            }
            strict = [
                other[dimensions[0]] > row[dimensions[0]],
                other[dimensions[1]] > row[dimensions[1]],
                other[dimensions[2]] > row[dimensions[2]],
                other[dimensions[3]] > row[dimensions[3]],
                other[dimensions[4]] < row[dimensions[4]],
            ]
            if all(comparisons.values()) and any(strict):
                dominated[trial_id] = True
                break
    return board["trial_id"].map(dominated).fillna(False)


def build_robustness_board(scoreboard: pd.DataFrame) -> pd.DataFrame:
    scoreboard = scoreboard.copy()
    evaluated_mask = scoreboard["status"] == "evaluated"
    for column in [
        "net_cagr",
        "sharpe_0rf",
        "max_drawdown",
        "annualised_turnover",
        "cost_drag",
    ]:
        evaluated_values = pd.to_numeric(scoreboard.loc[evaluated_mask, column], errors="coerce")
        if evaluated_values.isna().any():
            raise GMA4RobustnessBoardError(f"non-numeric {column} in evaluated rows")
        scoreboard[column] = pd.to_numeric(scoreboard[column], errors="coerce")

    trial_rows = (
        scoreboard[["run_id", "trial_id", "strategy_id", "family"]]
        .drop_duplicates()
        .sort_values("trial_id")
    )
    if trial_rows["trial_id"].duplicated().any():
        raise GMA4RobustnessBoardError("trial metadata is not one row per trial")

    rows: list[dict[str, Any]] = []
    for trial in trial_rows.to_dict("records"):
        trial_id = str(trial["trial_id"])
        baseline = _single_evaluated_row(
            scoreboard,
            trial_id,
            cost_scenario="baseline_1bps",
            evaluation_scope="full_common_history",
            window_id="full_common_history",
        )
        severe = _single_evaluated_row(
            scoreboard,
            trial_id,
            cost_scenario="severe_50bps",
            evaluation_scope="full_common_history",
            window_id="full_common_history",
        )
        rolling_3 = _scope_rows(scoreboard, trial_id, "rolling_3_year")
        rolling_5 = _scope_rows(scoreboard, trial_id, "rolling_5_year")
        sequential = _scope_rows(scoreboard, trial_id, "sequential_walk_forward")
        regimes = _scope_rows(scoreboard, trial_id, "predefined_regime")

        hhi = _finite_or_none(baseline["maximum_hhi_concentration"])
        concentration_status = (
            "concentration_measurement_available"
            if hhi is not None
            else "concentration_measurement_missing"
        )
        partial_regime_count = int(
            (
                regimes["regime_coverage_status"].fillna("") != "full_decision_eligible_coverage"
            ).sum()
        )
        cost_change = float(severe["net_cagr"] - baseline["net_cagr"])
        turnover_fragile = float(baseline["annualised_turnover"]) > 25.0
        cost_fragile = cost_change < -0.03 or (
            float(baseline["net_cagr"]) > 0 and float(severe["net_cagr"]) <= 0
        )
        notes = [
            f"partial_regime_rows={partial_regime_count}",
            f"turnover_fragile={str(turnover_fragile).lower()}",
            f"cost_fragile={str(cost_fragile).lower()}",
        ]
        if concentration_status == "concentration_measurement_missing":
            notes.append("concentration_not_fully_assessable")

        rows.append(
            {
                "run_id": trial["run_id"],
                "trial_id": trial_id,
                "strategy_id": trial["strategy_id"],
                "family": trial["family"],
                "baseline_full_history_net_cagr": float(baseline["net_cagr"]),
                "baseline_full_history_sharpe": float(baseline["sharpe_0rf"]),
                "baseline_full_history_max_drawdown": float(baseline["max_drawdown"]),
                "baseline_full_history_annualised_turnover": float(baseline["annualised_turnover"]),
                "baseline_full_history_cost_drag": float(baseline["cost_drag"]),
                "baseline_full_history_maximum_hhi_concentration": "" if hhi is None else hhi,
                "severe_cost_full_history_net_cagr": float(severe["net_cagr"]),
                "cost_sensitivity_cagr_change": cost_change,
                "worst_rolling_3_year_net_cagr": float(rolling_3["net_cagr"].min()),
                "median_rolling_3_year_net_cagr": float(rolling_3["net_cagr"].median()),
                "positive_rolling_3_year_fraction": _positive_fraction(rolling_3["net_cagr"]),
                "worst_rolling_5_year_net_cagr": float(rolling_5["net_cagr"].min()),
                "median_rolling_5_year_net_cagr": float(rolling_5["net_cagr"].median()),
                "positive_rolling_5_year_fraction": _positive_fraction(rolling_5["net_cagr"]),
                "positive_sequential_walk_forward_fraction": _positive_fraction(
                    sequential["net_cagr"]
                ),
                "worst_predefined_regime_net_cagr": float(regimes["net_cagr"].min()),
                "positive_predefined_regime_fraction": _positive_fraction(regimes["net_cagr"]),
                "parameter_neighbour_support": "",
                "concentration_measurement_status": concentration_status,
                "pareto_dominated": False,
                "historical_research_status": "",
                "research_notes": "; ".join(notes),
            }
        )

    board = pd.DataFrame(rows)
    board = _apply_parameter_neighbour_labels(board)
    board["pareto_dominated"] = _pareto_flags(board)
    board["historical_research_status"] = board.apply(
        lambda row: (
            "insufficient_measurement"
            if row["concentration_measurement_status"] != "concentration_measurement_available"
            else (
                "historically_dominated"
                if bool(row["pareto_dominated"])
                else "historical_non_dominated"
            )
        ),
        axis=1,
    )
    return board[BOARD_COLUMNS].sort_values("trial_id").reset_index(drop=True)


def _shortlist(board: pd.DataFrame) -> pd.DataFrame:
    return (
        board.loc[board["historical_research_status"] == "historical_non_dominated"]
        .sort_values(
            [
                "baseline_full_history_net_cagr",
                "severe_cost_full_history_net_cagr",
                "positive_rolling_3_year_fraction",
            ],
            ascending=[False, False, False],
        )
        .reset_index(drop=True)
    )


def _format_float(value: Any) -> str:
    if value == "" or pd.isna(value):
        return ""
    return f"{float(value):.6f}"


def _view_table(rows: pd.DataFrame, metric_columns: list[str]) -> list[str]:
    headers = ["trial_id", *metric_columns, "historical_research_status"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|---" + "|---:" * len(metric_columns) + "|---|",
    ]
    for row in rows.to_dict("records"):
        values = [str(row["trial_id"])]
        values.extend(_format_float(row[column]) for column in metric_columns)
        values.append(str(row["historical_research_status"]))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _all_trial_summary_table(board: pd.DataFrame) -> list[str]:
    columns = [
        "baseline_full_history_net_cagr",
        "severe_cost_full_history_net_cagr",
        "positive_rolling_3_year_fraction",
        "worst_predefined_regime_net_cagr",
    ]
    return _view_table(
        board.sort_values("baseline_full_history_net_cagr", ascending=False), columns
    )


def _ranked_views(board: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    growth = board.sort_values("baseline_full_history_net_cagr", ascending=False)
    resilience = board.sort_values(
        ["baseline_full_history_max_drawdown", "positive_rolling_3_year_fraction"],
        ascending=[False, False],
    )
    cost = board.sort_values(
        ["severe_cost_full_history_net_cagr", "cost_sensitivity_cagr_change"],
        ascending=[False, False],
    )
    return growth, resilience, cost


def _markdown_board(board: pd.DataFrame, manifest: dict[str, Any]) -> str:
    growth, resilience, cost = _ranked_views(board)
    missing_concentration = board.loc[
        board["concentration_measurement_status"] == "concentration_measurement_missing",
        "trial_id",
    ].tolist()
    lines = [
        "# GMA-4 Historical Robustness Board",
        "",
        f"Run ID: `{manifest['run_id']}`",
        f"Evidence: `{manifest['evidence_class']}`",
        f"Holdout interpretation: `{manifest['holdout_status']}`",
        "",
        "This is post-processing of saved tournament outputs only. highest historical CAGR or Sharpe alone is not a selection rule.",
        "no execution or promotion decision is produced.",
        "",
        "## Growth View",
        "",
        *_view_table(
            growth,
            [
                "baseline_full_history_net_cagr",
                "baseline_full_history_sharpe",
                "baseline_full_history_max_drawdown",
            ],
        ),
        "",
        "## Resilience View",
        "",
        *_view_table(
            resilience,
            [
                "baseline_full_history_max_drawdown",
                "positive_rolling_3_year_fraction",
                "worst_predefined_regime_net_cagr",
            ],
        ),
        "",
        "## Cost-Resilience View",
        "",
        *_view_table(
            cost,
            [
                "severe_cost_full_history_net_cagr",
                "cost_sensitivity_cagr_change",
                "baseline_full_history_annualised_turnover",
            ],
        ),
        "",
        "## Concentration Measurement",
        "",
        "- missing: " + (", ".join(missing_concentration) if missing_concentration else "none"),
    ]
    return "\n".join(lines) + "\n"


def _regime_summary(scoreboard: pd.DataFrame, regime_id: str) -> pd.DataFrame:
    rows = scoreboard.loc[
        (scoreboard["cost_scenario"] == "baseline_1bps")
        & (scoreboard["evaluation_scope"] == "predefined_regime")
        & (scoreboard["regime_id"].fillna("").astype(str) == regime_id)
        & (scoreboard["status"] == "evaluated")
    ].copy()
    if rows.empty:
        return pd.DataFrame(columns=["trial_id", "net_cagr", "max_drawdown"])
    rows["net_cagr"] = pd.to_numeric(rows["net_cagr"], errors="coerce")
    rows["max_drawdown"] = pd.to_numeric(rows["max_drawdown"], errors="coerce")
    return rows.sort_values("net_cagr", ascending=False)[["trial_id", "net_cagr", "max_drawdown"]]


def _regime_lines(scoreboard: pd.DataFrame, regime_id: str) -> list[str]:
    summary = _regime_summary(scoreboard, regime_id)
    if summary.empty:
        return ["No evaluated rows were available for this predefined regime."]
    rows = summary.head(5)
    lines = [
        "| trial_id | net_cagr | max_drawdown |",
        "|---|---:|---:|",
    ]
    for row in rows.to_dict("records"):
        lines.append(
            f"| {row['trial_id']} | {float(row['net_cagr']):.6f} | {float(row['max_drawdown']):.6f} |"
        )
    return lines


def _discussion_section(
    board: pd.DataFrame, scoreboard: pd.DataFrame, manifest: dict[str, Any]
) -> str:
    growth, resilience, cost = _ranked_views(board)
    missing_concentration = board.loc[
        board["concentration_measurement_status"] == "concentration_measurement_missing",
        "trial_id",
    ].tolist()
    lines = [
        START_MARKER,
        "## Robustness Across Time Periods and Regimes",
        "",
        "`observed_development_evidence` and `not_a_pristine_final_holdout` remain the interpretation constraints for this board.",
        "The board compares full-history baseline rows with rolling 3-year and 5-year windows, calendar-like sequential blocks, 50 bps transaction costs, and predefined historical regimes.",
        "highest historical CAGR or Sharpe alone is not a selection rule, and no execution or promotion decision is produced.",
        "",
        "### Compact All-Trial Summary",
        "",
        *_all_trial_summary_table(board),
        "",
        "### GFC",
        "",
        *_regime_lines(scoreboard, "gfc_stress"),
        "",
        "### COVID Crash",
        "",
        *_regime_lines(scoreboard, "covid_crash"),
        "",
        "### COVID Recovery",
        "",
        *_regime_lines(scoreboard, "covid_recovery"),
        "",
        "### 2022 Inflation/Rate Shock",
        "",
        *_regime_lines(scoreboard, "inflation_rate_shock_2022"),
        "",
        "### Post-October 2023 Geopolitical Stress",
        "",
        "This geopolitical-stress window is descriptive historical context, not a causal attribution.",
        "",
        *_regime_lines(scoreboard, "geopolitical_stress_descriptive"),
        "",
        "### Concentration Measurement Missing",
        "",
        "- " + (", ".join(missing_concentration) if missing_concentration else "none"),
        "",
        "### Growth View",
        "",
        *_view_table(
            growth,
            [
                "baseline_full_history_net_cagr",
                "baseline_full_history_sharpe",
                "baseline_full_history_max_drawdown",
            ],
        ),
        "",
        "### Resilience View",
        "",
        *_view_table(
            resilience,
            [
                "baseline_full_history_max_drawdown",
                "positive_rolling_3_year_fraction",
                "worst_predefined_regime_net_cagr",
            ],
        ),
        "",
        "### Cost-Resilience View",
        "",
        *_view_table(
            cost,
            [
                "severe_cost_full_history_net_cagr",
                "cost_sensitivity_cagr_change",
                "baseline_full_history_annualised_turnover",
            ],
        ),
        "",
        "## Ensemble Model Roadmap",
        "",
        "The ensemble model is the planned central next phase.",
        "GMA-4F does not train or evaluate an ML model.",
        "GMA-5 will use strictly walk-forward training.",
        "Every training decision will use only information available at that historical decision time.",
        "The ensemble will be evaluated against the fixed GMA-4 rule-based baselines.",
        "GMA-4F does not automatically choose which sleeves enter the ensemble.",
        "",
        f"Generated from run `{manifest['run_id']}`.",
        END_MARKER,
    ]
    return "\n".join(lines) + "\n"


def _update_discussion_file(path: Path, section: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if START_MARKER in text and END_MARKER in text:
        before, rest = text.split(START_MARKER, 1)
        _old, after = rest.split(END_MARKER, 1)
        updated = before.rstrip() + "\n\n" + section.rstrip() + "\n" + after
    elif "## Update Protocol" in text:
        before, after = text.split("## Update Protocol", 1)
        updated = before.rstrip() + "\n\n" + section.rstrip() + "\n\n## Update Protocol" + after
    else:
        updated = text.rstrip() + "\n\n" + section.rstrip() + "\n"
    path.write_text(updated, encoding="utf-8")


def _safe_write_run_file(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing != encoded:
            raise GMA4RobustnessBoardError(f"run-specific output already exists: {path.name}")
        return
    path.write_bytes(encoded)


def _safe_write_run_csv(path: Path, frame: pd.DataFrame) -> None:
    content = frame.to_csv(index=False)
    _safe_write_run_file(path, content)


def build_gma4_robustness_outputs(run_dir: Path) -> GMA4RobustnessBoardResult:
    scoreboard_path = run_dir / "gma4_tournament_scoreboard.csv"
    detail_path = run_dir / "gma4_evaluation_detail.csv"
    rejections_path = run_dir / "gma4_rejections.csv"
    manifest_path = run_dir / "gma4_run_manifest.json"

    scoreboard = _read_csv_required(scoreboard_path, SCOREBOARD_REQUIRED_COLUMNS)
    _read_csv_required(detail_path, EVALUATION_DETAIL_REQUIRED_COLUMNS)
    _read_rejections(rejections_path)
    manifest = _read_manifest(manifest_path)
    if set(scoreboard["run_id"].astype(str)) != {str(manifest["run_id"])}:
        raise GMA4RobustnessBoardError("scoreboard run_id does not match manifest run_id")

    board = build_robustness_board(scoreboard)
    shortlist = _shortlist(board)
    markdown = _markdown_board(board, manifest)
    run_board_csv = run_dir / RUN_BOARD_CSV
    run_board_md = run_dir / RUN_BOARD_MD
    run_shortlist_csv = run_dir / RUN_SHORTLIST_CSV
    _safe_write_run_csv(run_board_csv, board)
    _safe_write_run_file(run_board_md, markdown)
    _safe_write_run_csv(run_shortlist_csv, shortlist)

    report_root = run_dir.parent.parent
    report_root.mkdir(parents=True, exist_ok=True)
    latest_board_csv = report_root / LATEST_BOARD_CSV
    latest_board_md = report_root / LATEST_BOARD_MD
    latest_shortlist_csv = report_root / LATEST_SHORTLIST_CSV
    board.to_csv(latest_board_csv, index=False)
    latest_board_md.write_text(markdown, encoding="utf-8")
    shortlist.to_csv(latest_shortlist_csv, index=False)
    _update_discussion_file(
        report_root / DISCUSSION_FILE,
        _discussion_section(board, scoreboard, manifest),
    )

    return GMA4RobustnessBoardResult(
        run_id=str(manifest["run_id"]),
        run_dir=run_dir,
        board=board,
        shortlist=shortlist,
        output_paths={
            "run_board_csv": run_board_csv,
            "run_board_md": run_board_md,
            "run_shortlist_csv": run_shortlist_csv,
            "latest_board_csv": latest_board_csv,
            "latest_board_md": latest_board_md,
            "latest_shortlist_csv": latest_shortlist_csv,
            "discussion": report_root / DISCUSSION_FILE,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m market_strats.global_multi_asset.gma4_robustness_board"
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_gma4_robustness_outputs(args.run_dir)
    print(f"run_id: {result.run_id}")
    print(f"trial_count: {len(result.board)}")
    print(f"historical_non_dominated_count: {len(result.shortlist)}")
    for label, path in result.output_paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
