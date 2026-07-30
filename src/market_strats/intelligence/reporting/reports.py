"""Markdown and JSON reports for MI-1 coverage and availability audits."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_strats.intelligence.contracts import AvailabilityAuditRow, CoverageAuditRow


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def write_coverage_reports(
    *,
    report_root: Path,
    run_id: str,
    rows: list[CoverageAuditRow],
    common_research_start_date: date | None,
    blocked_reason: str,
    evidence_counts: Counter[str],
) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "coverage_report.json"
    md_path = report_root / "coverage_report.md"
    payload = {
        "run_id": run_id,
        "common_research_start_date": common_research_start_date,
        "blocked_reason": blocked_reason,
        "evidence_level_counts": dict(evidence_counts),
        "rows": [asdict(row) for row in rows],
    }
    write_json(json_path, payload)

    lines = [
        "# MI-1 Coverage Report",
        "",
        f"- run_id: `{run_id}`",
        f"- common_research_start_date: `{common_research_start_date or ''}`",
        f"- blocked_reason: `{blocked_reason}`",
        "",
        "## Availability Evidence Counts",
        "",
    ]
    for level, count in sorted(evidence_counts.items()):
        lines.append(f"- `{level}`: {count}")
    lines.extend(
        [
            "",
            "## Coverage Rows",
            "",
            "| instrument_id | first | last | eligible | missing | coverage_ratio | longest | "
            "start_date_eligible |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            f"{row.instrument_id} | {row.first_observed_session or ''} | "
            f"{row.last_observed_session or ''} | {row.eligible_sessions} | "
            f"{row.missing_sessions} | {row.coverage_ratio:.6f} | "
            f"{row.continuous_history_sessions} | {row.start_date_eligible} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def write_availability_reports(
    *,
    report_root: Path,
    run_id: str,
    rows: list[AvailabilityAuditRow],
) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "availability_report.json"
    md_path = report_root / "availability_report.md"
    evidence_counts = Counter(row.availability_evidence_level for row in rows)
    eligibility_counts = Counter("eligible" if row.eligible else "ineligible" for row in rows)
    payload = {
        "run_id": run_id,
        "row_count": len(rows),
        "evidence_level_counts": dict(evidence_counts),
        "eligibility_counts": dict(eligibility_counts),
        "rows": [asdict(row) for row in rows],
    }
    write_json(json_path, payload)

    lines = [
        "# MI-1 Availability Report",
        "",
        f"- run_id: `{run_id}`",
        f"- row_count: {len(rows)}",
        "",
        "## Evidence Levels",
        "",
    ]
    for level, count in sorted(evidence_counts.items()):
        lines.append(f"- `{level}`: {count}")
    lines.extend(["", "## Eligibility", ""])
    for label, count in sorted(eligibility_counts.items()):
        lines.append(f"- `{label}`: {count}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path
