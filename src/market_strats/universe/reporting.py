"""Local-only Parquet, JSON, and Markdown qualification outputs."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.universe.contracts import require_explicit_root

REQUIRED_PARQUET_OUTPUTS = (
    "security_identity_map.parquet",
    "ticker_identity_intervals.parquet",
    "membership_events.parquet",
    "membership_intervals.parquet",
    "membership_source_conflicts.parquet",
    "membership_sample_reconciliation.parquet",
    "corporate_action_events.parquet",
    "price_coverage.parquet",
    "delisting_coverage.parquet",
    "monthly_decision_calendar.parquet",
    "decision_date_eligibility.parquet",
    "exclusions_with_reason_codes.parquet",
)


def _json_default(value: Any) -> Any:
    if isinstance(value, date | datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def records_to_frame(records: list[Any], columns: list[str] | None = None) -> pd.DataFrame:
    rows = [asdict(row) if is_dataclass(row) else dict(row) for row in records]
    return pd.DataFrame(rows, columns=columns)


def write_qualification_outputs(
    *,
    report_root: Path,
    source_snapshot_manifest: dict[str, Any],
    source_licence_audit: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    qualification_summary: dict[str, Any],
) -> dict[str, Path]:
    root = require_explicit_root(report_root, "report_root")
    root.mkdir(parents=True, exist_ok=True)
    expected = set(REQUIRED_PARQUET_OUTPUTS)
    missing = sorted(expected - tables.keys())
    unexpected = sorted(tables.keys() - expected)
    if missing or unexpected:
        raise ValueError(f"Output table mismatch; missing={missing}, unexpected={unexpected}")

    outputs: dict[str, Path] = {}
    for filename in REQUIRED_PARQUET_OUTPUTS:
        path = root / filename
        tables[filename].to_parquet(path, index=False)
        outputs[filename] = path

    manifest_path = root / "source_snapshot_manifest.json"
    licence_path = root / "source_licence_audit.json"
    summary_json = root / "qualification_summary.json"
    summary_md = root / "qualification_summary.md"
    write_json(manifest_path, source_snapshot_manifest)
    write_json(licence_path, source_licence_audit)
    write_json(summary_json, qualification_summary)
    lines = [
        "# Free Point-in-Time S&P 500 Universe Qualification",
        "",
        f"- verdict: `{qualification_summary['verdict']}`",
        f"- monthly_decision_dates: {qualification_summary['monthly_decision_dates']}",
        f"- unique_securities: {qualification_summary['unique_securities']}",
        (
            "- qualified_decision_range: "
            f"`{qualification_summary['earliest_qualified_decision_date']}` through "
            f"`{qualification_summary['latest_qualified_decision_date']}`"
        ),
        "",
        "## Blocking Reasons",
        "",
    ]
    reasons = qualification_summary["blocking_reasons"]
    lines.extend(f"- `{reason}`" for reason in reasons)
    if not reasons:
        lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    outputs.update(
        {
            manifest_path.name: manifest_path,
            licence_path.name: licence_path,
            summary_json.name: summary_json,
            summary_md.name: summary_md,
        }
    )
    return outputs
