from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from market_strats.global_multi_asset.gma4_replay_adapter import (
    GMA4ReplayAdapterResult,
    GMA4ReplayConfig,
    run_gma4_replay_adapter,
)
from market_strats.global_multi_asset.gma5_atomic_sleeve_ensemble import (
    _metrics,
    load_gma4_bundle_prices_cash,
)


CLEAN_RUN_ID = "gma5_clean_execution_20260622T075912Z_v1"
LEARNED_DECISION_DATE = "2015-05-29"
LEARNED_WINDOW_END = "2026-05-01"
BIL = "BIL"
TOLERANCE = 1e-12

VARIANTS = [
    "gma5_equal_weight_atomic_sleeves_v1",
    "gma5_risk_weighted_atomic_sleeves_v1",
    "gma5_fixed_alpha_ridge_atomic_ensemble_v1",
]

COST_SCENARIOS = {
    "baseline_1bps": 1.0,
    "stressed_10bps": 10.0,
    "stressed_25bps": 25.0,
    "severe_50bps": 50.0,
}

RECONCILE_METRICS = [
    ("net CAGR", "net_cagr"),
    ("maximum drawdown", "max_drawdown"),
    ("cumulative net return", "cumulative_net_return"),
    ("annualised turnover", "annualised_turnover"),
    ("cost drag", "cost_drag"),
]

PATH_EXPORT_FIELDS = [
    "date",
    "variant_id",
    "cost_scenario",
    "portfolio_value",
    "net_return",
    "gross_return",
    "turnover",
    "transaction_cost",
    "cash_weight",
    "source_target_hash",
    "replay_adapter_source_hash",
]

LEARNED_SCOREBOARD_FIELDS = [
    "variant_id",
    "cost_scenario",
    "evaluation_scope",
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


class CostScenarioPathExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportResult:
    run_dir: Path
    root_dir: Path
    path_rows: list[dict[str, str]]
    reconciliation_rows: list[dict[str, str]]
    learned_rows: list[dict[str, str]]
    scope_rows: list[dict[str, str]]
    manifest: dict[str, Any]
    journal: dict[str, Any]


ReplayFunction = Callable[..., GMA4ReplayAdapterResult]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean-run-dir",
        default="reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1/runs/"
        "gma5_clean_execution_20260622T075912Z_v1",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise CostScenarioPathExportError(f"missing required input: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise CostScenarioPathExportError(f"missing CSV header: {path}")
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise CostScenarioPathExportError(f"missing columns in {path.name}: {missing}")
        return list(reader)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CostScenarioPathExportError(f"missing required input: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join("---" for _ in headers) + " |")
    table.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(table)


def copy_latest(run_path: Path, root_path: Path) -> None:
    root_path.write_bytes(run_path.read_bytes())


def target_lookup(target_rows: list[dict[str, str]]) -> dict[Any, dict[str, dict[str, float]]]:
    lookup: dict[Any, dict[str, dict[str, float]]] = {}
    for row in target_rows:
        date_value = pd.to_datetime(row["decision_date"]).date()
        lookup.setdefault(row["variant_id"], {}).setdefault(date_value, {})[row["symbol"]] = float(
            row["composite_etf_target_weight"]
        )
    return lookup


def make_resolver(
    variant_targets: dict[Any, dict[str, float]],
) -> Callable[[Any, Any], dict[str, float]]:
    def resolver(signal_date: Any, _prices: Any) -> dict[str, float]:
        key = pd.to_datetime(signal_date).date()
        return variant_targets.get(key, {BIL: 1.0})

    return resolver


def verify_target_hash(target_path: Path, provenance: dict[str, Any]) -> str:
    target_hash = sha256_file(target_path)
    expected = provenance.get("composite_target_input_hash")
    if target_hash != expected:
        raise CostScenarioPathExportError(
            f"saved target hash mismatch: calculated={target_hash}; expected={expected}"
        )
    return target_hash


def aggregate_costs(result: GMA4ReplayAdapterResult) -> dict[str, dict[str, float]]:
    if result.costs.empty:
        return {}
    costs = result.costs.copy()
    date_column = "execution_date" if "execution_date" in costs.columns else costs.columns[0]
    grouped: dict[str, dict[str, float]] = {}
    for date_value, frame in costs.groupby(date_column):
        key = str(pd.to_datetime(date_value).date())
        grouped[key] = {
            "transaction_cost": float(frame.get("transaction_cost", pd.Series(dtype=float)).sum()),
            "turnover": float(frame.get("trade_notional_abs", pd.Series(dtype=float)).sum()),
        }
    return grouped


def export_rows_for_result(
    *,
    result: GMA4ReplayAdapterResult,
    variant_id: str,
    cost_scenario: str,
    target_hash: str,
    replay_adapter_hash: str,
) -> list[dict[str, str]]:
    costs_by_date = aggregate_costs(result)
    rows = []
    equity = result.equity.copy()
    for row in equity.to_dict("records"):
        date_value = str(pd.to_datetime(row["valuation_date"]).date())
        costs = costs_by_date.get(date_value, {})
        net_return = float(row.get("daily_return", 0.0) or 0.0)
        rows.append(
            {
                "date": date_value,
                "variant_id": variant_id,
                "cost_scenario": cost_scenario,
                "portfolio_value": str(float(row["portfolio_value"])),
                "net_return": str(net_return),
                "gross_return": str(net_return),
                "turnover": str(costs.get("turnover", 0.0)),
                "transaction_cost": str(costs.get("transaction_cost", 0.0)),
                "cash_weight": "",
                "source_target_hash": target_hash,
                "replay_adapter_source_hash": replay_adapter_hash,
            }
        )
    return rows


def metric_row_from_result(
    *,
    result: GMA4ReplayAdapterResult,
    variant_id: str,
    cost_scenario: str,
    start: str,
    end: str,
    scope: str,
) -> dict[str, Any]:
    return _metrics(
        entity_id=variant_id,
        entity_type="ensemble_variant",
        cost_scenario=cost_scenario,
        result=result,
        start=pd.to_datetime(start).date(),
        end=pd.to_datetime(end).date(),
        scope=scope,
        window_id=scope,
    )


def replay_saved_targets(
    *,
    target_rows: list[dict[str, str]],
    target_hash: str,
    replay_adapter_hash: str,
    replay_function: ReplayFunction,
) -> tuple[list[dict[str, str]], dict[tuple[str, str], dict[str, Any]], int]:
    prices, cash, _inventory = load_gma4_bundle_prices_cash()
    first_target_date = min(pd.to_datetime(row["decision_date"]).date() for row in target_rows)
    lookup = target_lookup(target_rows)
    path_rows: list[dict[str, str]] = []
    full_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    invocation_count = 0
    for variant_id in VARIANTS:
        for cost_scenario, bps in COST_SCENARIOS.items():
            result = replay_function(
                prices=prices,
                cash=cash,
                macro=pd.DataFrame(),
                target_resolver=make_resolver(lookup.get(variant_id, {})),
                rebalance_schedule="monthly_last_session_next_open",
                strategy_id=variant_id,
                strategy_version="gma5a5_saved_target_replay_v1",
                config=GMA4ReplayConfig(cost_bps_per_notional=bps),
                minimum_signal_date=first_target_date,
            )
            invocation_count += 1
            path_rows.extend(
                export_rows_for_result(
                    result=result,
                    variant_id=variant_id,
                    cost_scenario=cost_scenario,
                    target_hash=target_hash,
                    replay_adapter_hash=replay_adapter_hash,
                )
            )
            full_metrics[(variant_id, cost_scenario)] = metric_row_from_result(
                result=result,
                variant_id=variant_id,
                cost_scenario=cost_scenario,
                start="2012-05-31",
                end=LEARNED_WINDOW_END,
                scope="full_common_oos",
            )
    return path_rows, full_metrics, invocation_count


def rows_by_variant_cost(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["variant_id"], row["cost_scenario"]), []).append(row)
    return grouped


def metric_from_path_rows(
    rows: list[dict[str, str]],
    *,
    variant_id: str,
    cost_scenario: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    filtered = [
        row
        for row in rows
        if row["variant_id"] == variant_id
        and row["cost_scenario"] == cost_scenario
        and start <= row["date"] <= end
    ]
    equity = pd.DataFrame(
        {
            "valuation_date": [pd.to_datetime(row["date"]).date() for row in filtered],
            "portfolio_value": [float(row["portfolio_value"]) for row in filtered],
            "daily_return": [float(row["net_return"]) for row in filtered],
        }
    )
    costs = pd.DataFrame(
        {
            "execution_date": [pd.to_datetime(row["date"]).date() for row in filtered],
            "trade_notional_abs": [float(row["turnover"]) for row in filtered],
            "transaction_cost": [float(row["transaction_cost"]) for row in filtered],
        }
    )
    result = GMA4ReplayAdapterResult(
        equity=equity,
        drawdown=pd.DataFrame(),
        holdings=pd.DataFrame(),
        orders=pd.DataFrame(),
        fills=pd.DataFrame(),
        costs=costs,
        signals=pd.DataFrame(),
        signal_dates=[],
        execution_dates=[],
    )
    return metric_row_from_result(
        result=result,
        variant_id=variant_id,
        cost_scenario=cost_scenario,
        start=start,
        end=end,
        scope="learned_only_ridge_window",
    )


def reconcile_full_period(
    clean_run_dir: Path,
    full_metrics: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str, list[dict[str, str]]]:
    scoreboard = read_csv(
        clean_run_dir / "gma5_ensemble_scoreboard.csv",
        {"entity_id", "cost_scenario", "evaluation_scope", "status"},
    )
    standard = {
        (row["entity_id"], row["cost_scenario"]): row
        for row in scoreboard
        if row["evaluation_scope"] == "full_common_oos" and row["status"] == "evaluated"
    }
    rows = []
    overall = "full_period_path_reconciliation_passed"
    for variant_id in VARIANTS:
        for cost_scenario in COST_SCENARIOS:
            source_row = standard.get((variant_id, cost_scenario))
            metric_row = full_metrics[(variant_id, cost_scenario)]
            for metric_name, column in RECONCILE_METRICS:
                status = "pass"
                detail = ""
                if source_row is None or source_row.get(column, "") == "":
                    status = "insufficient_saved_scoreboard_metric"
                    overall = (
                        "insufficient_saved_scoreboard_metric"
                        if overall != "full_period_path_reconciliation_failed"
                        else overall
                    )
                    detail = "metric absent from saved standard scoreboard"
                else:
                    difference = abs(float(metric_row[column]) - float(source_row[column]))
                    if difference > TOLERANCE:
                        status = "fail"
                        overall = "full_period_path_reconciliation_failed"
                        detail = f"absolute_difference={difference}"
                rows.append(
                    {
                        "variant_id": variant_id,
                        "cost_scenario": cost_scenario,
                        "metric_name": metric_name,
                        "exported_value": str(metric_row.get(column, "")),
                        "saved_scoreboard_value": ""
                        if source_row is None
                        else source_row.get(column, ""),
                        "status": status,
                        "detail": detail,
                    }
                )
    return overall, rows


def learned_effective_dates(path_rows: list[dict[str, str]]) -> dict[str, str]:
    ridge_rows = [
        row
        for row in path_rows
        if row["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
        and row["cost_scenario"] == "baseline_1bps"
        and row["date"] >= LEARNED_DECISION_DATE
    ]
    first_path = min((row["date"] for row in ridge_rows), default=LEARNED_DECISION_DATE)
    return {
        "first_learned_ridge_decision_date": LEARNED_DECISION_DATE,
        "first_learned_ridge_target_effective_date": first_path,
        "first_learned_ridge_return_path_date": first_path,
        "learned_only_metric_start_date": first_path,
    }


def annualised_volatility_from_path_rows(
    rows: list[dict[str, str]],
    *,
    variant_id: str,
    cost_scenario: str,
    start: str,
    end: str,
) -> float:
    returns = [
        float(row["net_return"])
        for row in rows
        if row["variant_id"] == variant_id
        and row["cost_scenario"] == cost_scenario
        and start <= row["date"] <= end
    ]
    if len(returns) < 2:
        return 0.0
    return float(pd.Series(returns, dtype=float).std(ddof=0) * (252.0**0.5))


def build_learned_scoreboard(
    path_rows: list[dict[str, str]],
    reconciliation_status: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    dates = learned_effective_dates(path_rows)
    scope_rows = [
        {
            "evaluation_scope": "learned_only_ridge_window",
            "measurement_status": "available_from_saved_artifacts"
            if reconciliation_status == "full_period_path_reconciliation_passed"
            else "not_available_from_saved_artifacts",
            "reason": reconciliation_status,
            "external_comparator_learned_only_metrics": "not_available_from_saved_artifacts",
        }
    ]
    if reconciliation_status != "full_period_path_reconciliation_passed":
        rows = [
            {
                "variant_id": variant_id,
                "cost_scenario": cost_scenario,
                "evaluation_scope": "learned_only_ridge_window",
                "period_start": dates["learned_only_metric_start_date"],
                "period_end": LEARNED_WINDOW_END,
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
                "source_file": "gma5_cost_scenario_path_export_v1.csv",
            }
            for variant_id in VARIANTS
            for cost_scenario in COST_SCENARIOS
        ]
        return rows, scope_rows, dates
    rows = []
    for variant_id in VARIANTS:
        for cost_scenario in COST_SCENARIOS:
            metric = metric_from_path_rows(
                path_rows,
                variant_id=variant_id,
                cost_scenario=cost_scenario,
                start=dates["learned_only_metric_start_date"],
                end=LEARNED_WINDOW_END,
            )
            annualised_volatility = annualised_volatility_from_path_rows(
                path_rows,
                variant_id=variant_id,
                cost_scenario=cost_scenario,
                start=dates["learned_only_metric_start_date"],
                end=LEARNED_WINDOW_END,
            )
            rows.append(
                {
                    "variant_id": variant_id,
                    "cost_scenario": cost_scenario,
                    "evaluation_scope": "learned_only_ridge_window",
                    "period_start": dates["learned_only_metric_start_date"],
                    "period_end": LEARNED_WINDOW_END,
                    "session_count": str(metric["session_count"]),
                    "net_cagr": str(metric["net_cagr"]),
                    "annualised_volatility": str(annualised_volatility),
                    "sharpe": str(metric["sharpe_0rf"]),
                    "maximum_drawdown": str(metric["max_drawdown"]),
                    "cumulative_net_return": str(metric["cumulative_net_return"]),
                    "annualised_turnover": str(metric["annualised_turnover"]),
                    "cost_drag": str(metric["cost_drag"]),
                    "measurement_status": "available_from_saved_artifacts",
                    "source_run_id": CLEAN_RUN_ID,
                    "source_file": "gma5_cost_scenario_path_export_v1.csv",
                }
            )
    return rows, scope_rows, dates


def write_reconciliation_markdown(path: Path, status: str, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "\n".join(
            [
                "# GMA-5 Cost-Scenario Full-Period Reconciliation v1",
                "",
                f"Overall status: `{status}`",
                "",
                markdown_table(
                    ["variant_id", "cost_scenario", "metric", "status", "detail"],
                    [
                        [
                            row["variant_id"],
                            row["cost_scenario"],
                            row["metric_name"],
                            row["status"],
                            row["detail"],
                        ]
                        for row in rows
                    ],
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_learned_markdown(path: Path, rows: list[dict[str, str]], dates: dict[str, str]) -> None:
    path.write_text(
        "\n".join(
            [
                "# GMA-5 Learned-Only Window Scoreboard v2",
                "",
                f"First learned ridge decision date: `{dates['first_learned_ridge_decision_date']}`",
                f"First learned ridge target effective date: `{dates['first_learned_ridge_target_effective_date']}`",
                f"First learned ridge return path date: `{dates['first_learned_ridge_return_path_date']}`",
                f"Learned-only metric start date: `{dates['learned_only_metric_start_date']}`",
                "",
                "This is an internal same-window comparison across the three GMA-5 variants. "
                "It is observed_development_evidence, not_a_pristine_final_holdout, and no "
                "execution or promotion decision is produced.",
                "",
                markdown_table(
                    ["variant_id", "cost_scenario", "net_cagr", "maximum_drawdown", "status"],
                    [
                        [
                            row["variant_id"],
                            row["cost_scenario"],
                            row["net_cagr"],
                            row["maximum_drawdown"],
                            row["measurement_status"],
                        ]
                        for row in rows
                    ],
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_scope_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "\n".join(
            [
                "# GMA-5 Learned-Only Scope Availability v1",
                "",
                "External learned-only comparators remain unavailable from saved artifacts.",
                "",
                markdown_table(
                    ["evaluation_scope", "measurement_status", "reason", "external comparators"],
                    [
                        [
                            row["evaluation_scope"],
                            row["measurement_status"],
                            row["reason"],
                            row["external_comparator_learned_only_metrics"],
                        ]
                        for row in rows
                    ],
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_export(
    clean_run_dir: Path,
    replay_function: ReplayFunction = run_gma4_replay_adapter,
) -> ExportResult:
    root_dir = clean_run_dir.parents[1]
    target_path = clean_run_dir / "gma5_ensemble_monthly_etf_targets.csv"
    target_rows = read_csv(
        target_path, {"variant_id", "decision_date", "symbol", "composite_etf_target_weight"}
    )
    read_csv(
        clean_run_dir / "gma5_composite_target_netting_audit_v2.csv",
        {"variant_id", "decision_date", "ticker", "final_target_weight"},
    )
    clean_manifest = read_json(clean_run_dir / "gma5_clean_execution_manifest_v1.json")
    runtime_trace = read_json(clean_run_dir / "gma5_runtime_replay_trace_v1.json")
    provenance = read_json(clean_run_dir / "gma5_composite_replay_provenance_v1.json")
    target_hash = verify_target_hash(target_path, provenance)
    replay_adapter_hash = str(provenance["replay_adapter_source_hash"])

    path_rows, full_metrics, replay_count = replay_saved_targets(
        target_rows=target_rows,
        target_hash=target_hash,
        replay_adapter_hash=replay_adapter_hash,
        replay_function=replay_function,
    )
    write_csv(
        clean_run_dir / "gma5_cost_scenario_path_export_v1.csv", path_rows, PATH_EXPORT_FIELDS
    )
    copy_latest(
        clean_run_dir / "gma5_cost_scenario_path_export_v1.csv",
        root_dir / "gma5_cost_scenario_path_export_v1.csv",
    )

    reconciliation_status, reconciliation_rows = reconcile_full_period(clean_run_dir, full_metrics)
    learned_rows, scope_rows, learned_dates = build_learned_scoreboard(
        path_rows, reconciliation_status
    )

    path_export_hash = sha256_file(clean_run_dir / "gma5_cost_scenario_path_export_v1.csv")
    manifest = {
        "clean_execution_run_id": clean_manifest["clean_execution_run_id"],
        "target_input_hash": target_hash,
        "replay_adapter_source_hash": replay_adapter_hash,
        "cost_scenarios": list(COST_SCENARIOS),
        "variants": VARIANTS,
        "source_market_data_hashes": runtime_trace.get(
            "composite_target_input_hashes_by_variant", {}
        ),
        "source_cash_data_hash": "",
        "path_export_hash": path_export_hash,
    }
    journal = {
        "strategy_or_model_logic_invoked": False,
        "saved_target_hash_verified": True,
        "replay_adapter_invocation_count": replay_count,
        "all_cost_scenarios_exported": sorted(
            {(row["variant_id"], row["cost_scenario"]) for row in path_rows}
        )
        == sorted((variant, cost) for variant in VARIANTS for cost in COST_SCENARIOS),
    }
    write_json(clean_run_dir / "gma5_cost_scenario_path_export_manifest_v1.json", manifest)
    write_json(clean_run_dir / "gma5_cost_scenario_path_export_journal_v1.json", journal)
    copy_latest(
        clean_run_dir / "gma5_cost_scenario_path_export_manifest_v1.json",
        root_dir / "gma5_cost_scenario_path_export_manifest_v1.json",
    )
    copy_latest(
        clean_run_dir / "gma5_cost_scenario_path_export_journal_v1.json",
        root_dir / "gma5_cost_scenario_path_export_journal_v1.json",
    )

    write_csv(
        clean_run_dir / "gma5_cost_scenario_full_period_reconciliation_v1.csv",
        reconciliation_rows,
        [
            "variant_id",
            "cost_scenario",
            "metric_name",
            "exported_value",
            "saved_scoreboard_value",
            "status",
            "detail",
        ],
    )
    write_reconciliation_markdown(
        clean_run_dir / "gma5_cost_scenario_full_period_reconciliation_v1.md",
        reconciliation_status,
        reconciliation_rows,
    )
    write_csv(
        clean_run_dir / "gma5_learned_only_window_scoreboard_v2.csv",
        learned_rows,
        LEARNED_SCOREBOARD_FIELDS,
    )
    write_learned_markdown(
        clean_run_dir / "gma5_learned_only_window_scoreboard_v2.md", learned_rows, learned_dates
    )
    write_csv(
        clean_run_dir / "gma5_learned_only_scope_availability_v1.csv",
        scope_rows,
        [
            "evaluation_scope",
            "measurement_status",
            "reason",
            "external_comparator_learned_only_metrics",
        ],
    )
    write_scope_markdown(clean_run_dir / "gma5_learned_only_scope_availability_v1.md", scope_rows)
    for name in [
        "gma5_cost_scenario_full_period_reconciliation_v1.csv",
        "gma5_cost_scenario_full_period_reconciliation_v1.md",
        "gma5_learned_only_window_scoreboard_v2.csv",
        "gma5_learned_only_window_scoreboard_v2.md",
        "gma5_learned_only_scope_availability_v1.csv",
        "gma5_learned_only_scope_availability_v1.md",
    ]:
        copy_latest(clean_run_dir / name, root_dir / name)
    return ExportResult(
        run_dir=clean_run_dir,
        root_dir=root_dir,
        path_rows=path_rows,
        reconciliation_rows=reconciliation_rows,
        learned_rows=learned_rows,
        scope_rows=scope_rows,
        manifest=manifest,
        journal=journal,
    )


def main() -> None:
    args = parse_args()
    run_export(Path(args.clean_run_dir))


if __name__ == "__main__":
    main()
