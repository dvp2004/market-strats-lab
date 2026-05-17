from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def _phase7_config(config: dict) -> dict:
    return config.get("phase7_report_integrity_audit", {})


def _read_csv_safely(path: Path) -> tuple[pd.DataFrame, str]:
    try:
        return pd.read_csv(path), ""
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), str(exc)


def _create_report_manifest(reports_dir: str | Path) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    rows: list[dict] = []

    for path in sorted(reports_dir.glob("*")):
        if not path.is_file():
            continue

        stat = path.stat()
        modified_utc = datetime.fromtimestamp(
            stat.st_mtime,
            tz=UTC,
        ).isoformat()

        rows.append(
            {
                "file_name": path.name,
                "file_suffix": path.suffix,
                "size_bytes": stat.st_size,
                "modified_utc": modified_utc,
            }
        )

    return pd.DataFrame(rows)


def _create_expected_report_audit(
    reports_dir: str | Path,
    expected_reports: list[str],
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    rows: list[dict] = []

    for report_name in expected_reports:
        path = reports_dir / report_name

        rows.append(
            {
                "report_name": report_name,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "status": "Passed" if path.exists() else "Missing",
            }
        )

    return pd.DataFrame(rows)


def _create_endpoint_audit(
    reports_dir: str | Path,
    pinned_end_date: str,
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    pinned = pd.Timestamp(pinned_end_date)

    rows: list[dict] = []

    for path in sorted(reports_dir.glob("*.csv")):
        data, error = _read_csv_safely(path)

        if error:
            rows.append(
                {
                    "file_name": path.name,
                    "has_end_date_column": False,
                    "row_count": "",
                    "max_end_date": "",
                    "bad_row_count": "",
                    "status": "Read error",
                    "reason": error,
                }
            )
            continue

        if "end_date" not in data.columns:
            rows.append(
                {
                    "file_name": path.name,
                    "has_end_date_column": False,
                    "row_count": len(data),
                    "max_end_date": "",
                    "bad_row_count": 0,
                    "status": "No end_date column",
                    "reason": "",
                }
            )
            continue

        parsed = pd.to_datetime(data["end_date"], errors="coerce")
        bad_mask = parsed.notna() & (parsed > pinned)
        max_end_date = parsed.max()

        rows.append(
            {
                "file_name": path.name,
                "has_end_date_column": True,
                "row_count": len(data),
                "max_end_date": (
                    max_end_date.date().isoformat()
                    if pd.notna(max_end_date)
                    else ""
                ),
                "bad_row_count": int(bad_mask.sum()),
                "status": "Passed" if not bad_mask.any() else "Failed",
                "reason": (
                    ""
                    if not bad_mask.any()
                    else f"Contains end_date later than {pinned_end_date}"
                ),
            }
        )

    return pd.DataFrame(rows)


def _get_single_row(
    data: pd.DataFrame,
    filters: dict[str, str],
) -> pd.Series:
    filtered = data.copy()

    for column, value in filters.items():
        if column not in filtered.columns:
            raise ValueError(f"Missing expected column: {column}")

        filtered = filtered[filtered[column].astype(str) == str(value)]

    if filtered.empty:
        raise ValueError(f"No row found for filters: {filters}")

    if len(filtered) > 1:
        raise ValueError(f"Multiple rows found for filters: {filters}")

    return filtered.iloc[0]


def _metric_matches(
    actual: float,
    expected: float,
    tolerance: float,
) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def _create_final_checkpoint_claim_audit(
    reports_dir: str | Path,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7_config(config)
    expected = phase_config.get("expected_final_candidate", {})

    comparison_path = Path(reports_dir) / "final_candidate_comparison.csv"

    if not comparison_path.exists():
        return pd.DataFrame(
            [
                {
                    "claim": "Final candidate comparison report exists.",
                    "status": "Failed",
                    "expected": "final_candidate_comparison.csv",
                    "actual": "Missing",
                    "reason": "Cannot audit final candidate claims without comparison report.",
                }
            ]
        )

    comparison = pd.read_csv(comparison_path)

    try:
        row = _get_single_row(
            comparison,
            filters={
                "period": str(expected.get("period", "full")),
                "candidate_name": str(expected["candidate_name"]),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(
            [
                {
                    "claim": "Expected final candidate row exists.",
                    "status": "Failed",
                    "expected": str(expected),
                    "actual": "Missing",
                    "reason": str(exc),
                }
            ]
        )

    checks = [
        {
            "claim": "Final candidate CAGR matches expected checkpoint value.",
            "metric": "cagr_pct",
            "expected": float(expected["cagr_pct"]),
            "actual": float(row["cagr_pct"]),
            "tolerance": 0.01,
        },
        {
            "claim": "Final candidate Calmar matches expected checkpoint value.",
            "metric": "calmar",
            "expected": float(expected["calmar"]),
            "actual": float(row["calmar"]),
            "tolerance": 0.001,
        },
        {
            "claim": "Final candidate max drawdown matches expected checkpoint value.",
            "metric": "max_drawdown_pct",
            "expected": float(expected["max_drawdown_pct"]),
            "actual": float(row["max_drawdown_pct"]),
            "tolerance": 0.01,
        },
        {
            "claim": "Final candidate end value matches expected checkpoint value.",
            "metric": "end_value",
            "expected": float(expected["end_value"]),
            "actual": float(row["end_value"]),
            "tolerance": 0.10,
        },
        {
            "claim": "Final candidate metric trade count matches expected checkpoint value.",
            "metric": "trade_count",
            "expected": int(expected["trade_count"]),
            "actual": int(row["trade_count"]),
            "tolerance": 0,
        },
    ]

    rows: list[dict] = []

    for check in checks:
        passed = _metric_matches(
            actual=float(check["actual"]),
            expected=float(check["expected"]),
            tolerance=float(check["tolerance"]),
        )

        rows.append(
            {
                "claim": check["claim"],
                "metric": check["metric"],
                "status": "Passed" if passed else "Failed",
                "expected": check["expected"],
                "actual": check["actual"],
                "tolerance": check["tolerance"],
                "reason": "" if passed else "Metric differs from checkpoint value.",
            }
        )
    overlay_switch_count = expected.get("overlay_switch_count")

    if overlay_switch_count is not None:
        switch_report_name = str(
            expected.get(
                "overlay_switch_report",
                "regime_switch_overlay_offensive_relief_event_summary.csv",
            )
        )
        switch_variant_name = str(
            expected.get("overlay_switch_variant_name", "loose_relief")
        )
        switch_report_path = Path(reports_dir) / switch_report_name

        if not switch_report_path.exists():
            rows.append(
                {
                    "claim": "Final candidate overlay switch count report exists.",
                    "metric": "overlay_switch_count",
                    "status": "Failed",
                    "expected": int(overlay_switch_count),
                    "actual": "",
                    "tolerance": 0,
                    "reason": f"{switch_report_name} is missing.",
                }
            )
        else:
            switch_report = pd.read_csv(switch_report_path)

            try:
                switch_row = _get_single_row(
                    switch_report,
                    filters={"variant_name": switch_variant_name},
                )
                actual_switch_count = int(switch_row["switch_count"])
                passed = actual_switch_count == int(overlay_switch_count)

                rows.append(
                    {
                        "claim": "Final candidate overlay switch count matches expected checkpoint value.",
                        "metric": "overlay_switch_count",
                        "status": "Passed" if passed else "Failed",
                        "expected": int(overlay_switch_count),
                        "actual": actual_switch_count,
                        "tolerance": 0,
                        "reason": ""
                        if passed
                        else "Overlay switch count differs from checkpoint value.",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "claim": "Final candidate overlay switch count row exists.",
                        "metric": "overlay_switch_count",
                        "status": "Failed",
                        "expected": int(overlay_switch_count),
                        "actual": "",
                        "tolerance": 0,
                        "reason": str(exc),
                    }
                )

    return pd.DataFrame(rows)


def _create_readme_checkpoint_audit(
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7_config(config)

    readme_path = Path(str(phase_config.get("readme_path", "README.md")))

    expected_phrases = [
        "SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief",
        "Best execution-realistic candidate",
        "10.35%",
        "0.429",
        "-24.12%",
        "SPY buy-and-hold remains the raw wealth winner",
        "Phase 6C",
        "Breadth confirmation is rejected for promotion",
        "Defensive stress confirmation is rejected",
    ]

    if not readme_path.exists():
        return pd.DataFrame(
            [
                {
                    "phrase": phrase,
                    "present": False,
                    "status": "Failed",
                    "reason": f"{readme_path} does not exist.",
                }
                for phrase in expected_phrases
            ]
        )

    text = readme_path.read_text(encoding="utf-8")

    rows: list[dict] = []

    for phrase in expected_phrases:
        present = phrase in text

        rows.append(
            {
                "phrase": phrase,
                "present": present,
                "status": "Passed" if present else "Failed",
                "reason": "" if present else "Expected phrase not found in README.",
            }
        )

    return pd.DataFrame(rows)


def _create_integrity_conclusion(
    endpoint_audit: pd.DataFrame,
    expected_report_audit: pd.DataFrame,
    claim_audit: pd.DataFrame,
    readme_audit: pd.DataFrame,
) -> pd.DataFrame:
    endpoint_failures = endpoint_audit[endpoint_audit["status"] == "Failed"]
    missing_reports = expected_report_audit[
        expected_report_audit["status"] == "Missing"
    ]
    failed_claims = claim_audit[claim_audit["status"] == "Failed"]
    failed_readme = readme_audit[readme_audit["status"] == "Failed"]

    checkpoint_ready = (
        endpoint_failures.empty
        and missing_reports.empty
        and failed_claims.empty
        and failed_readme.empty
    )

    return pd.DataFrame(
        [
            {
                "claim": "No report endpoint drift beyond pinned checkpoint.",
                "status": "Passed" if endpoint_failures.empty else "Failed",
                "evidence_quality": "Scanned CSV reports for end_date later than pinned endpoint",
                "interpretation": (
                    "No CSV report contains end_date later than the pinned checkpoint."
                    if endpoint_failures.empty
                    else f"{len(endpoint_failures)} report(s) contain endpoint drift."
                ),
            },
            {
                "claim": "All expected checkpoint reports exist.",
                "status": "Passed" if missing_reports.empty else "Failed",
                "evidence_quality": "Checked configured expected report list",
                "interpretation": (
                    "All expected reports exist."
                    if missing_reports.empty
                    else f"{len(missing_reports)} expected report(s) are missing."
                ),
            },
            {
                "claim": "Final candidate headline metrics match checkpoint values.",
                "status": "Passed" if failed_claims.empty else "Failed",
                "evidence_quality": "Compared final_candidate_comparison.csv to configured checkpoint values",
                "interpretation": (
                    "Final candidate headline metrics match expected checkpoint values."
                    if failed_claims.empty
                    else f"{len(failed_claims)} final candidate metric check(s) failed."
                ),
            },
            {
                "claim": "README contains final Phase 6C checkpoint story.",
                "status": "Passed" if failed_readme.empty else "Failed",
                "evidence_quality": "Checked README for required final checkpoint phrases",
                "interpretation": (
                    "README contains the expected final checkpoint language."
                    if failed_readme.empty
                    else f"{len(failed_readme)} README phrase check(s) failed."
                ),
            },
            {
                "claim": "Checkpoint is ready to commit and tag.",
                "status": "Passed" if checkpoint_ready else "Not yet",
                "evidence_quality": "Requires endpoint, report, metric, and README checks to pass",
                "interpretation": (
                    "The Phase 6C checkpoint is internally consistent."
                    if checkpoint_ready
                    else "Fix failed integrity checks before tagging the checkpoint."
                ),
            },
        ]
    )


def write_final_checkpoint_summary_markdown(
    manifest: pd.DataFrame,
    endpoint_audit: pd.DataFrame,
    expected_report_audit: pd.DataFrame,
    claim_audit: pd.DataFrame,
    readme_audit: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Final Checkpoint Integrity Summary

This report audits whether the final Phase 6C checkpoint is internally consistent, endpoint-pinned, and ready to commit/tag.

## Report Manifest

{manifest.to_markdown(index=False) if not manifest.empty else "No reports found."}

## Endpoint Audit

{endpoint_audit.to_markdown(index=False) if not endpoint_audit.empty else "No endpoint audit available."}

## Expected Report Audit

{expected_report_audit.to_markdown(index=False) if not expected_report_audit.empty else "No expected report audit available."}

## Final Candidate Claim Audit

{claim_audit.to_markdown(index=False) if not claim_audit.empty else "No claim audit available."}

## README Checkpoint Audit

{readme_audit.to_markdown(index=False) if not readme_audit.empty else "No README audit available."}

## Integrity Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_report_integrity_audit(
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7_config(config)

    if not phase_config.get("enabled", False):
        return {
            "manifest": pd.DataFrame(),
            "endpoint_audit": pd.DataFrame(),
            "expected_report_audit": pd.DataFrame(),
            "claim_audit": pd.DataFrame(),
            "readme_audit": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    pinned_end_date = str(phase_config.get("pinned_end_date", "2026-05-01"))
    expected_reports = [
        str(report_name)
        for report_name in phase_config.get("expected_reports", [])
    ]

    manifest = _create_report_manifest(reports_dir)
    endpoint_audit = _create_endpoint_audit(
        reports_dir=reports_dir,
        pinned_end_date=pinned_end_date,
    )
    expected_report_audit = _create_expected_report_audit(
        reports_dir=reports_dir,
        expected_reports=expected_reports,
    )
    claim_audit = _create_final_checkpoint_claim_audit(
        reports_dir=reports_dir,
        config=config,
    )
    readme_audit = _create_readme_checkpoint_audit(config=config)
    conclusion = _create_integrity_conclusion(
        endpoint_audit=endpoint_audit,
        expected_report_audit=expected_report_audit,
        claim_audit=claim_audit,
        readme_audit=readme_audit,
    )

    return {
        "manifest": manifest,
        "endpoint_audit": endpoint_audit,
        "expected_report_audit": expected_report_audit,
        "claim_audit": claim_audit,
        "readme_audit": readme_audit,
        "conclusion": conclusion,
    }


def save_report_integrity_audit(
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_report_integrity_audit(
        config=config,
        reports_dir=reports_dir,
    )

    manifest = outputs["manifest"]
    endpoint_audit = outputs["endpoint_audit"]
    expected_report_audit = outputs["expected_report_audit"]
    claim_audit = outputs["claim_audit"]
    readme_audit = outputs["readme_audit"]
    conclusion = outputs["conclusion"]

    if manifest.empty and conclusion.empty:
        return outputs

    manifest_path = reports_dir / "report_manifest.csv"
    endpoint_path = reports_dir / "report_endpoint_audit.csv"
    expected_path = reports_dir / "expected_report_audit.csv"
    claim_path = reports_dir / "final_checkpoint_claim_audit.csv"
    readme_path = reports_dir / "readme_checkpoint_audit.csv"
    conclusion_path = reports_dir / "final_checkpoint_integrity_conclusion.csv"
    markdown_path = reports_dir / "final_checkpoint_summary.md"

    manifest.to_csv(manifest_path, index=False)
    endpoint_audit.to_csv(endpoint_path, index=False)
    expected_report_audit.to_csv(expected_path, index=False)
    claim_audit.to_csv(claim_path, index=False)
    readme_audit.to_csv(readme_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_final_checkpoint_summary_markdown(
        manifest=manifest,
        endpoint_audit=endpoint_audit,
        expected_report_audit=expected_report_audit,
        claim_audit=claim_audit,
        readme_audit=readme_audit,
        conclusion=conclusion,
        output_path=markdown_path,
    )

    print("\nReport endpoint audit:")
    print(endpoint_audit.to_string(index=False))

    print("\nExpected report audit:")
    print(expected_report_audit.to_string(index=False))

    print("\nFinal checkpoint claim audit:")
    print(claim_audit.to_string(index=False))

    print("\nREADME checkpoint audit:")
    print(readme_audit.to_string(index=False))

    print("\nFinal checkpoint integrity conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved report manifest to: {manifest_path}")
    print(f"Saved endpoint audit to: {endpoint_path}")
    print(f"Saved expected report audit to: {expected_path}")
    print(f"Saved final checkpoint claim audit to: {claim_path}")
    print(f"Saved README checkpoint audit to: {readme_path}")
    print(f"Saved final checkpoint integrity conclusion to: {conclusion_path}")
    print(f"Saved final checkpoint summary markdown to: {markdown_path}")

    return outputs