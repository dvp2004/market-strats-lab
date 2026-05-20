from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE8F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "claim_context": {
        "project_scope": "Research-grade systematic strategy lab",
        "production_ready": False,
        "live_trading_claim": False,
        "final_candidate": "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief",
        "final_candidate_role": "Best execution-realistic risk-adjusted candidate built so far",
        "raw_wealth_benchmark": "SPY Buy & Hold",
        "simple_defensive_benchmark": "SPY 12M Momentum",
        "canonical_start_date": "2006-04-28",
        "canonical_end_date": "2026-05-01",
    },
    "gates": {
        "require_not_production_ready": True,
        "require_no_live_trading_claim": True,
        "min_critical_blockers": 5,
        "require_data_risk_documented": True,
        "require_execution_risk_documented": True,
        "require_tax_risk_documented": True,
        "require_operational_risk_documented": True,
        "require_monitoring_risk_documented": True,
        "require_human_review_required": True,
    },
    "blockers": [],
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase8f_production_readiness_boundary_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE8F_CONFIG, user_config)


def build_phase8f_blocker_inventory(phase_config: dict[str, Any]) -> pd.DataFrame:
    blockers = phase_config.get("blockers", [])

    columns = [
        "category",
        "area",
        "severity",
        "status",
        "production_gap",
        "current_project_state",
        "required_for_production",
        "recommended_next_step",
    ]

    if not blockers:
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(blockers).copy()
    missing_columns = set(columns).difference(frame.columns)

    if missing_columns:
        raise ValueError(
            "Phase 8F blocker inventory is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    for column in columns:
        frame[column] = frame[column].astype(str)

    return frame[columns]


def _normalise_text(value: Any) -> str:
    return str(value).strip().lower()


def build_phase8f_summary(
    blocker_inventory: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    claim_context = phase_config.get("claim_context", {})

    total_items = int(len(blocker_inventory))

    if blocker_inventory.empty:
        critical_count = 0
        major_count = 0
        blocker_count = 0
        gap_count = 0
        caveat_count = 0
        categories_documented = 0
    else:
        severity = blocker_inventory["severity"].map(_normalise_text)
        status = blocker_inventory["status"].map(_normalise_text)
        critical_count = int((severity == "critical").sum())
        major_count = int((severity == "major").sum())
        blocker_count = int((status == "blocker").sum())
        gap_count = int((status == "gap").sum())
        caveat_count = int((status == "caveat").sum())
        categories_documented = int(blocker_inventory["category"].nunique())

    declared_production_ready = bool(claim_context.get("production_ready", False))
    live_trading_claim = bool(claim_context.get("live_trading_claim", False))

    production_ready_after_audit = (
        declared_production_ready
        and critical_count == 0
        and blocker_count == 0
        and not live_trading_claim
    )

    if production_ready_after_audit:
        verdict = "Potentially production-ready"
    else:
        verdict = "Research-only / not production-ready"

    return pd.DataFrame(
        [
            {
                "project_scope": claim_context.get("project_scope"),
                "final_candidate": claim_context.get("final_candidate"),
                "final_candidate_role": claim_context.get("final_candidate_role"),
                "raw_wealth_benchmark": claim_context.get("raw_wealth_benchmark"),
                "simple_defensive_benchmark": claim_context.get(
                    "simple_defensive_benchmark"
                ),
                "canonical_start_date": claim_context.get("canonical_start_date"),
                "canonical_end_date": claim_context.get("canonical_end_date"),
                "declared_production_ready": declared_production_ready,
                "live_trading_claim": live_trading_claim,
                "production_ready_after_audit": production_ready_after_audit,
                "production_readiness_verdict": verdict,
                "total_boundary_items": total_items,
                "critical_items": critical_count,
                "major_items": major_count,
                "blocker_items": blocker_count,
                "gap_items": gap_count,
                "caveat_items": caveat_count,
                "categories_documented": categories_documented,
            }
        ]
    )


def build_phase8f_category_summary(blocker_inventory: pd.DataFrame) -> pd.DataFrame:
    if blocker_inventory.empty:
        return pd.DataFrame(
            columns=[
                "category",
                "items",
                "critical_items",
                "major_items",
                "blocker_items",
                "gap_items",
                "caveat_items",
            ]
        )

    rows: list[dict[str, Any]] = []

    for category, group in blocker_inventory.groupby("category", sort=False):
        severity = group["severity"].map(_normalise_text)
        status = group["status"].map(_normalise_text)

        rows.append(
            {
                "category": category,
                "items": int(len(group)),
                "critical_items": int((severity == "critical").sum()),
                "major_items": int((severity == "major").sum()),
                "blocker_items": int((status == "blocker").sum()),
                "gap_items": int((status == "gap").sum()),
                "caveat_items": int((status == "caveat").sum()),
            }
        )

    return pd.DataFrame(rows)


def build_phase8f_boundary_statement(
    summary: pd.DataFrame,
    blocker_inventory: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    row = summary.iloc[0]

    if bool(row["production_ready_after_audit"]):
        statement = (
            "The audit did not identify critical production blockers. This would require "
            "separate human review before any production claim."
        )
    else:
        statement = (
            "Market Strats Lab remains a research-grade systematic strategy lab, not a "
            "production trading system, not financial advice, and not a live-trading "
            "recommendation. The final candidate is a research result with documented "
            "data, execution, tax, monitoring, operational, validation, governance, and "
            "compliance blockers."
        )

    critical_areas = (
        "; ".join(
            blocker_inventory.loc[
                blocker_inventory["severity"].map(_normalise_text) == "critical",
                "area",
            ].tolist()
        )
        if not blocker_inventory.empty
        else ""
    )

    return pd.DataFrame(
        [
            {
                "boundary_area": "Production-readiness boundary",
                "recommended_statement": statement,
                "critical_blocker_areas": critical_areas,
            }
        ]
    )


def _has_category(blocker_inventory: pd.DataFrame, category: str) -> bool:
    if blocker_inventory.empty:
        return False

    return category.lower() in set(blocker_inventory["category"].map(_normalise_text))


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase8f_gate_report(
    blocker_inventory: pd.DataFrame,
    summary: pd.DataFrame,
    boundary_statement: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 8F summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]

    require_not_ready = bool(gates.get("require_not_production_ready", True))
    require_no_live_claim = bool(gates.get("require_no_live_trading_claim", True))
    min_critical = int(gates.get("min_critical_blockers", 5))

    critical_count = int(row["critical_items"])
    production_ready = bool(row["production_ready_after_audit"])
    live_trading_claim = bool(row["live_trading_claim"])

    require_data = bool(gates.get("require_data_risk_documented", True))
    require_execution = bool(gates.get("require_execution_risk_documented", True))
    require_tax = bool(gates.get("require_tax_risk_documented", True))
    require_ops = bool(gates.get("require_operational_risk_documented", True))
    require_monitoring = bool(gates.get("require_monitoring_risk_documented", True))
    require_human_review = bool(gates.get("require_human_review_required", True))

    governance_or_compliance_documented = _has_category(
        blocker_inventory,
        "Governance",
    ) or _has_category(blocker_inventory, "Compliance")

    rows = [
        _gate_row(
            "Audit explicitly preserves non-production status",
            (not require_not_ready) or not production_ready,
            f"production_ready_after_audit={production_ready}",
        ),
        _gate_row(
            "Audit makes no live-trading claim",
            (not require_no_live_claim) or not live_trading_claim,
            f"live_trading_claim={live_trading_claim}",
        ),
        _gate_row(
            "Critical production blockers are documented",
            critical_count >= min_critical,
            f"{critical_count} critical items; required >= {min_critical}",
        ),
        _gate_row(
            "Data risk is documented",
            (not require_data) or _has_category(blocker_inventory, "Data"),
            "Data category present",
        ),
        _gate_row(
            "Execution risk is documented",
            (not require_execution) or _has_category(blocker_inventory, "Execution"),
            "Execution category present",
        ),
        _gate_row(
            "Tax risk is documented",
            (not require_tax) or _has_category(blocker_inventory, "Tax"),
            "Tax category present",
        ),
        _gate_row(
            "Operational/configuration risk is documented",
            (not require_ops) or _has_category(blocker_inventory, "Operations"),
            "Operations category present",
        ),
        _gate_row(
            "Monitoring risk is documented",
            (not require_monitoring) or _has_category(blocker_inventory, "Monitoring"),
            "Monitoring category present",
        ),
        _gate_row(
            "Human review / governance boundary is documented",
            (not require_human_review) or governance_or_compliance_documented,
            "Governance or Compliance category present",
        ),
        _gate_row(
            "Boundary statement is produced",
            not boundary_statement.empty,
            "Boundary statement table created",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8f_conclusion(
    gate_report: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if summary.empty:
        verdict = "Failed — missing production-boundary summary"
        interpretation = "Phase 8F could not evaluate the production-readiness boundary."
    elif all_passed:
        verdict = "Completed — research-only boundary documented"
        interpretation = (
            "The project documented why the final candidate remains research-only and "
            "not production-ready. This is a boundary-control pass, not a production "
            "approval."
        )
    else:
        verdict = "Failed boundary discipline"
        interpretation = (
            "The project did not satisfy every production-boundary audit gate. Do not "
            "move to richer signals until the non-production boundary is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8F",
                "diagnostic": "Production-readiness / non-production boundary audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8f_markdown(
    blocker_inventory: pd.DataFrame,
    category_summary: pd.DataFrame,
    summary: pd.DataFrame,
    boundary_statement: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8F — Production-Readiness / Non-Production Boundary Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit documents why Market Strats Lab remains a research-grade "
            "systematic strategy lab rather than a production trading system."
        ),
        "",
        (
            "This is not a production approval. A pass means the non-production "
            "boundary was documented clearly."
        ),
        "",
        "## Blocker Inventory",
        "",
        blocker_inventory.to_markdown(index=False),
        "",
        "## Category Summary",
        "",
        category_summary.to_markdown(index=False),
        "",
        "## Production-Boundary Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Boundary Statement",
        "",
        boundary_statement.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is not a broker, legal, tax, or compliance review.",
        "- This is not a production approval.",
        "- This does not make the strategy live-tradable.",
        "- This audit documents blockers; it does not solve them.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase8f_production_readiness_boundary_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "blocker_inventory": empty,
            "category_summary": empty,
            "summary": empty,
            "boundary_statement": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    blocker_inventory = build_phase8f_blocker_inventory(phase_config)
    category_summary = build_phase8f_category_summary(blocker_inventory)
    summary = build_phase8f_summary(blocker_inventory, phase_config)
    boundary_statement = build_phase8f_boundary_statement(summary, blocker_inventory)
    gate_report = build_phase8f_gate_report(
        blocker_inventory,
        summary,
        boundary_statement,
        phase_config,
    )
    conclusion = build_phase8f_conclusion(gate_report, summary)

    blocker_inventory.to_csv(
        reports_path / "phase8f_production_boundary_blocker_inventory.csv",
        index=False,
    )
    category_summary.to_csv(
        reports_path / "phase8f_production_boundary_category_summary.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase8f_production_boundary_summary.csv",
        index=False,
    )
    boundary_statement.to_csv(
        reports_path / "phase8f_production_boundary_statement.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase8f_production_boundary_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8f_production_boundary_conclusion.csv",
        index=False,
    )

    write_phase8f_markdown(
        blocker_inventory=blocker_inventory,
        category_summary=category_summary,
        summary=summary,
        boundary_statement=boundary_statement,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8f_production_readiness_boundary_audit.md",
    )

    print("Wrote Phase 8F production-readiness boundary audit reports.")

    return {
        "blocker_inventory": blocker_inventory,
        "category_summary": category_summary,
        "summary": summary,
        "boundary_statement": boundary_statement,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }