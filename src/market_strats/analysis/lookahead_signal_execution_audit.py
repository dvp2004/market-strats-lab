from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.regime_switch_overlay_offensive_relief_validation import (
    _create_overlay_for_variant,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
)


def _phase7b_config(config: dict) -> dict:
    return config.get("phase7_lookahead_signal_execution_audit", {})


def _find_relief_profile(config: dict, profile_name: str) -> dict:
    profiles = config.get("phase6_offensive_relief_validation", {}).get(
        "relief_profiles",
        [],
    )

    for profile in profiles:
        if str(profile["name"]) == profile_name:
            return profile

    raise ValueError(f"Could not find relief profile: {profile_name}")


def _create_audited_overlay_result(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7b_config(config)
    audited_variant = str(phase_config.get("audited_variant", "loose_relief"))

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    relief_profile = _find_relief_profile(
        config=config,
        profile_name=audited_variant,
    )

    overlay_result = _create_overlay_for_variant(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        config=config,
        variant_name=audited_variant,
        relief_profile=relief_profile,
    )

    overlay_result = overlay_result.copy()
    overlay_result["date"] = pd.to_datetime(overlay_result["date"])
    overlay_result = overlay_result.sort_values("date").reset_index(drop=True)

    return overlay_result


def _validate_required_columns(
    overlay_result: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7b_config(config)
    required_columns = [
        str(column) for column in phase_config.get("required_columns", [])
    ]

    rows: list[dict] = []

    for column in required_columns:
        exists = column in overlay_result.columns

        rows.append(
            {
                "check": f"Required column exists: {column}",
                "column": column,
                "status": "Passed" if exists else "Failed",
                "reason": "" if exists else "Column missing from audited overlay result.",
            }
        )

    return pd.DataFrame(rows)


def _create_trend_sma_audit(
    overlay_result: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7b_config(config)
    overlay_config = config.get("regime_switch_overlay", {})

    trend_sma_days = int(overlay_config.get("trend_sma_days", 200))
    tolerance = float(phase_config.get("trend_sma_tolerance", 0.000001))
    ignored_warmup_rows = int(
        phase_config.get("ignored_initial_sma_warmup_rows", trend_sma_days)
    )
    max_allowed_mismatches = int(
        phase_config.get("max_allowed_trend_sma_mismatches", 0)
    )

    result = overlay_result.copy()

    required = {"date", "signal_price", "trend_sma"}
    missing = required - set(result.columns)

    if missing:
        return pd.DataFrame(
            [
                {
                    "audit": "trend_sma_reconstruction",
                    "status": "Failed",
                    "row_count_checked": 0,
                    "mismatch_count": "",
                    "max_abs_diff": "",
                    "reason": f"Missing required columns: {sorted(missing)}",
                }
            ]
        )

    result["computed_trend_sma"] = (
        result["signal_price"].astype(float).rolling(trend_sma_days).mean()
    )

    comparable = result.iloc[ignored_warmup_rows:].copy()
    comparable = comparable[
        comparable["trend_sma"].notna() & comparable["computed_trend_sma"].notna()
    ].copy()

    if comparable.empty:
        return pd.DataFrame(
            [
                {
                    "audit": "trend_sma_reconstruction",
                    "status": "Failed",
                    "row_count_checked": 0,
                    "mismatch_count": "",
                    "max_abs_diff": "",
                    "reason": "No comparable rows after warmup.",
                }
            ]
        )

    comparable["abs_diff"] = (
        comparable["trend_sma"].astype(float)
        - comparable["computed_trend_sma"].astype(float)
    ).abs()

    mismatch_count = int((comparable["abs_diff"] > tolerance).sum())
    max_abs_diff = float(comparable["abs_diff"].max())

    passed = mismatch_count <= max_allowed_mismatches

    return pd.DataFrame(
        [
            {
                "audit": "trend_sma_reconstruction",
                "status": "Passed" if passed else "Failed",
                "trend_sma_days": trend_sma_days,
                "ignored_warmup_rows": ignored_warmup_rows,
                "row_count_checked": int(len(comparable)),
                "mismatch_count": mismatch_count,
                "max_allowed_mismatches": max_allowed_mismatches,
                "max_abs_diff": round(max_abs_diff, 10),
                "tolerance": tolerance,
                "reason": (
                    "Reported trend_sma matches trailing rolling reconstruction."
                    if passed
                    else "Reported trend_sma differs from trailing rolling reconstruction."
                ),
            }
        ]
    )


def _reconstruct_raw_defensive_state(
    overlay_result: pd.DataFrame,
    confirmation_days: int,
) -> pd.Series:
    result = overlay_result.copy()

    signal_price = result["signal_price"].astype(float)
    trend_sma = result["trend_sma"].astype(float)

    above_trend = signal_price > trend_sma
    below_trend = signal_price < trend_sma

    confirmed_above = (
        above_trend.rolling(confirmation_days).sum() >= confirmation_days
    ).fillna(False)
    confirmed_below = (
        below_trend.rolling(confirmation_days).sum() >= confirmation_days
    ).fillna(False)

    state = False
    states: list[bool] = []

    for below, above in zip(confirmed_below, confirmed_above, strict=True):
        if bool(below):
            state = True
        elif bool(above):
            state = False

        states.append(state)

    return pd.Series(states, index=result.index)


def _create_confirmation_reconstruction_audit(
    overlay_result: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7b_config(config)
    overlay_config = config.get("regime_switch_overlay", {})

    confirmation_days = int(overlay_config.get("confirmation_days", 3))
    max_allowed_mismatches = int(
        phase_config.get("max_allowed_confirmation_mismatches", 0)
    )

    required = {
        "signal_price",
        "trend_sma",
        "raw_signal_use_defensive",
    }
    missing = required - set(overlay_result.columns)

    if missing:
        return pd.DataFrame(
            [
                {
                    "audit": "raw_confirmation_reconstruction",
                    "status": "Failed",
                    "row_count_checked": 0,
                    "mismatch_count": "",
                    "reason": f"Missing required columns: {sorted(missing)}",
                }
            ]
        )

    reconstructed = _reconstruct_raw_defensive_state(
        overlay_result=overlay_result,
        confirmation_days=confirmation_days,
    )
    reported = overlay_result["raw_signal_use_defensive"].astype(bool).reset_index(
        drop=True
    )

    mismatch_mask = reconstructed.astype(bool).ne(reported)
    mismatch_count = int(mismatch_mask.sum())

    first_mismatch_date = ""

    if mismatch_count:
        first_mismatch_idx = int(np.flatnonzero(mismatch_mask.to_numpy())[0])
        first_mismatch_date = pd.to_datetime(
            overlay_result.loc[first_mismatch_idx, "date"]
        ).date().isoformat()

    passed = mismatch_count <= max_allowed_mismatches

    return pd.DataFrame(
        [
            {
                "audit": "raw_confirmation_reconstruction",
                "status": "Passed" if passed else "Failed",
                "confirmation_days": confirmation_days,
                "row_count_checked": int(len(overlay_result)),
                "mismatch_count": mismatch_count,
                "max_allowed_mismatches": max_allowed_mismatches,
                "first_mismatch_date": first_mismatch_date,
                "reason": (
                    "Raw defensive signal can be reconstructed from trailing confirmation logic."
                    if passed
                    else "Raw defensive signal does not match trailing confirmation reconstruction."
                ),
            }
        ]
    )


def _selected_mode_to_defensive_state(selected_mode: pd.Series) -> pd.Series:
    return selected_mode.astype(str).str.contains("defensive", case=False, na=False)


def _create_switch_timing_audit(
    overlay_result: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7b_config(config)
    max_allowed_before_trend = int(
        phase_config.get("max_allowed_switches_before_trend_available", 0)
    )

    required = {
        "date",
        "selected_mode",
        "trend_sma",
        "raw_signal_use_defensive",
        "guarded_signal_use_defensive",
    }
    missing = required - set(overlay_result.columns)

    if missing:
        return pd.DataFrame(
            [
                {
                    "switch_date": "",
                    "from_mode": "",
                    "to_mode": "",
                    "status": "Failed",
                    "reason": f"Missing required columns: {sorted(missing)}",
                }
            ]
        )

    result = overlay_result.copy()
    result["date"] = pd.to_datetime(result["date"])
    result["selected_defensive"] = _selected_mode_to_defensive_state(
        result["selected_mode"]
    )
    result["previous_selected_mode"] = result["selected_mode"].shift(1)
    result["previous_selected_defensive"] = result["selected_defensive"].shift(1)

    switch_mask = (
        result["previous_selected_defensive"].notna()
        & result["selected_defensive"].ne(result["previous_selected_defensive"])
    )

    rows: list[dict] = []

    for idx, row in result.loc[switch_mask].iterrows():
        prior_idx = int(idx) - 1

        prior_guarded_signal = (
            bool(result.loc[prior_idx, "guarded_signal_use_defensive"])
            if prior_idx >= 0
            else None
        )
        current_guarded_signal = bool(row["guarded_signal_use_defensive"])
        current_selected_defensive = bool(row["selected_defensive"])
        trend_available = pd.notna(row["trend_sma"])

        prior_signal_matches_new_mode = (
            prior_guarded_signal == current_selected_defensive
            if prior_guarded_signal is not None
            else False
        )
        current_signal_matches_new_mode = (
            current_guarded_signal == current_selected_defensive
        )

        status = "Passed" if trend_available else "Failed"

        rows.append(
            {
                "switch_date": row["date"].date().isoformat(),
                "from_mode": row["previous_selected_mode"],
                "to_mode": row["selected_mode"],
                "trend_available": trend_available,
                "prior_guarded_signal_matches_new_mode": prior_signal_matches_new_mode,
                "current_guarded_signal_matches_new_mode": current_signal_matches_new_mode,
                "raw_signal_use_defensive": bool(row["raw_signal_use_defensive"]),
                "guarded_signal_use_defensive": current_guarded_signal,
                "status": status,
                "reason": (
                    "Switch occurred after trend_sma was available."
                    if trend_available
                    else "Switch occurred before trend_sma was available."
                ),
            }
        )

    if not rows:
        return pd.DataFrame(
            [
                {
                    "switch_date": "",
                    "from_mode": "",
                    "to_mode": "",
                    "trend_available": "",
                    "prior_guarded_signal_matches_new_mode": "",
                    "current_guarded_signal_matches_new_mode": "",
                    "raw_signal_use_defensive": "",
                    "guarded_signal_use_defensive": "",
                    "status": "Review",
                    "reason": "No switches found.",
                }
            ]
        )

    audit = pd.DataFrame(rows)

    before_trend_count = int((audit["trend_available"] == False).sum())  # noqa: E712

    if before_trend_count > max_allowed_before_trend:
        audit.loc[audit["trend_available"] == False, "status"] = "Failed"  # noqa: E712

    return audit


def _create_slippage_turnover_audit(
    overlay_result: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "date",
        "selected_mode",
        "overlay_turnover",
        "overlay_slippage_cost",
        "applied_overlay_slippage_bps",
    }
    missing = required - set(overlay_result.columns)

    if missing:
        return pd.DataFrame(
            [
                {
                    "audit": "slippage_turnover_alignment",
                    "status": "Failed",
                    "row_count_checked": 0,
                    "slippage_rows": "",
                    "turnover_rows": "",
                    "reason": f"Missing required columns: {sorted(missing)}",
                }
            ]
        )

    result = overlay_result.copy()
    result["date"] = pd.to_datetime(result["date"])
    result["selected_mode_changed"] = result["selected_mode"].ne(
        result["selected_mode"].shift(1)
    )
    result.loc[result.index[0], "selected_mode_changed"] = False

    result["overlay_turnover"] = result["overlay_turnover"].astype(float)
    result["overlay_slippage_cost"] = result["overlay_slippage_cost"].astype(float)
    result["applied_overlay_slippage_bps"] = result[
        "applied_overlay_slippage_bps"
    ].astype(float)

    slippage_rows = result[result["overlay_slippage_cost"] > 0].copy()
    turnover_rows = result[result["overlay_turnover"] > 0].copy()

    slippage_without_turnover = slippage_rows[
        slippage_rows["overlay_turnover"] <= 0
    ]
    positive_bps_without_cost_or_turnover = result[
        (result["applied_overlay_slippage_bps"] > 0)
        & (result["overlay_turnover"] <= 0)
        & (result["overlay_slippage_cost"] <= 0)
    ]

    return pd.DataFrame(
        [
            {
                "audit": "slippage_turnover_alignment",
                "status": "Passed"
                if slippage_without_turnover.empty
                else "Failed",
                "row_count_checked": int(len(result)),
                "mode_switch_rows": int(result["selected_mode_changed"].sum()),
                "slippage_rows": int(len(slippage_rows)),
                "turnover_rows": int(len(turnover_rows)),
                "slippage_without_turnover_rows": int(len(slippage_without_turnover)),
                "positive_bps_without_cost_or_turnover_rows": int(
                    len(positive_bps_without_cost_or_turnover)
                ),
                "reason": (
                    "No slippage-cost rows occurred without positive overlay turnover."
                    if slippage_without_turnover.empty
                    else "Some slippage-cost rows occurred without positive overlay turnover."
                ),
            }
        ]
    )


def _create_lookahead_conclusion(
    column_audit: pd.DataFrame,
    trend_sma_audit: pd.DataFrame,
    confirmation_audit: pd.DataFrame,
    switch_timing_audit: pd.DataFrame,
    slippage_turnover_audit: pd.DataFrame,
) -> pd.DataFrame:
    column_failed = column_audit[column_audit["status"] == "Failed"]
    trend_failed = trend_sma_audit[trend_sma_audit["status"] == "Failed"]
    confirmation_failed = confirmation_audit[
        confirmation_audit["status"] == "Failed"
    ]
    switch_failed = switch_timing_audit[switch_timing_audit["status"] == "Failed"]
    slippage_failed = slippage_turnover_audit[
        slippage_turnover_audit["status"] == "Failed"
    ]

    core_passed = (
        column_failed.empty
        and trend_failed.empty
        and confirmation_failed.empty
        and switch_failed.empty
        and slippage_failed.empty
    )

    return pd.DataFrame(
        [
            {
                "claim": "Audited overlay contains required signal/execution columns.",
                "status": "Passed" if column_failed.empty else "Failed",
                "evidence_quality": "Checked final candidate overlay result schema",
                "interpretation": (
                    "All required columns are present."
                    if column_failed.empty
                    else f"{len(column_failed)} required column check(s) failed."
                ),
            },
            {
                "claim": "Trend SMA can be reconstructed using trailing signal prices.",
                "status": "Passed" if trend_failed.empty else "Failed",
                "evidence_quality": "Recomputed trailing SMA from signal_price and compared with reported trend_sma",
                "interpretation": (
                    "The trend SMA matches trailing reconstruction after warmup."
                    if trend_failed.empty
                    else "The trend SMA does not match trailing reconstruction."
                ),
            },
            {
                "claim": "Raw 3D confirmation signal can be reconstructed without future data.",
                "status": "Passed" if confirmation_failed.empty else "Failed",
                "evidence_quality": "Rebuilt raw defensive state from trailing 3D above/below trend confirmation",
                "interpretation": (
                    "Raw signal state matches trailing reconstruction."
                    if confirmation_failed.empty
                    else "Raw signal state does not match trailing reconstruction."
                ),
            },
            {
                "claim": "Regime switches occur only after trend data is available.",
                "status": "Passed" if switch_failed.empty else "Failed",
                "evidence_quality": "Checked switch rows for available trend_sma",
                "interpretation": (
                    "No switch occurred before trend_sma availability."
                    if switch_failed.empty
                    else f"{len(switch_failed)} switch row(s) failed timing checks."
                ),
            },
            {
                "claim": "Slippage costs align with positive overlay turnover.",
                "status": "Passed" if slippage_failed.empty else "Failed",
                "evidence_quality": "Checked slippage-cost rows against overlay turnover",
                "interpretation": (
                    "No slippage-cost rows occurred without positive overlay turnover."
                    if slippage_failed.empty
                    else "Some slippage-cost rows occurred without positive overlay turnover."
                ),
            },
            {
                "claim": "No obvious lookahead issue was found in the audited final candidate.",
                "status": "Passed" if core_passed else "Not yet",
                "evidence_quality": "Research-grade signal reconstruction and execution-alignment audit",
                "interpretation": (
                    "The audited final candidate passed the Phase 7B lookahead checks."
                    if core_passed
                    else "Fix failed lookahead checks before making stronger claims."
                ),
            },
        ]
    )


def write_lookahead_audit_markdown(
    column_audit: pd.DataFrame,
    trend_sma_audit: pd.DataFrame,
    confirmation_audit: pd.DataFrame,
    switch_timing_audit: pd.DataFrame,
    slippage_turnover_audit: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Lookahead / Signal-Execution Audit

This Phase 7B report audits whether the final execution-realistic candidate's signal logic can be reconstructed from trailing/current data.

It is a research-grade anti-lookahead audit, not a production-readiness guarantee.

## Required Column Audit

{column_audit.to_markdown(index=False) if not column_audit.empty else "No column audit available."}

## Trend SMA Reconstruction Audit

{trend_sma_audit.to_markdown(index=False) if not trend_sma_audit.empty else "No trend SMA audit available."}

## Confirmation Reconstruction Audit

{confirmation_audit.to_markdown(index=False) if not confirmation_audit.empty else "No confirmation audit available."}

## Switch Timing Audit

{switch_timing_audit.to_markdown(index=False) if not switch_timing_audit.empty else "No switch timing audit available."}

## Slippage / Turnover Audit

{slippage_turnover_audit.to_markdown(index=False) if not slippage_turnover_audit.empty else "No slippage/turnover audit available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_lookahead_signal_execution_audit(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7b_config(config)

    if not phase_config.get("enabled", False):
        return {
            "column_audit": pd.DataFrame(),
            "trend_sma_audit": pd.DataFrame(),
            "confirmation_audit": pd.DataFrame(),
            "switch_timing_audit": pd.DataFrame(),
            "slippage_turnover_audit": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    overlay_result = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    column_audit = _validate_required_columns(
        overlay_result=overlay_result,
        config=config,
    )
    trend_sma_audit = _create_trend_sma_audit(
        overlay_result=overlay_result,
        config=config,
    )
    confirmation_audit = _create_confirmation_reconstruction_audit(
        overlay_result=overlay_result,
        config=config,
    )
    switch_timing_audit = _create_switch_timing_audit(
        overlay_result=overlay_result,
        config=config,
    )
    slippage_turnover_audit = _create_slippage_turnover_audit(
        overlay_result=overlay_result,
    )
    conclusion = _create_lookahead_conclusion(
        column_audit=column_audit,
        trend_sma_audit=trend_sma_audit,
        confirmation_audit=confirmation_audit,
        switch_timing_audit=switch_timing_audit,
        slippage_turnover_audit=slippage_turnover_audit,
    )

    return {
        "column_audit": column_audit,
        "trend_sma_audit": trend_sma_audit,
        "confirmation_audit": confirmation_audit,
        "switch_timing_audit": switch_timing_audit,
        "slippage_turnover_audit": slippage_turnover_audit,
        "conclusion": conclusion,
    }


def save_lookahead_signal_execution_audit(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_lookahead_signal_execution_audit(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    column_audit = outputs["column_audit"]
    trend_sma_audit = outputs["trend_sma_audit"]
    confirmation_audit = outputs["confirmation_audit"]
    switch_timing_audit = outputs["switch_timing_audit"]
    slippage_turnover_audit = outputs["slippage_turnover_audit"]
    conclusion = outputs["conclusion"]

    if conclusion.empty:
        return outputs

    column_path = reports_dir / "lookahead_required_column_audit.csv"
    trend_path = reports_dir / "lookahead_trend_sma_audit.csv"
    confirmation_path = reports_dir / "lookahead_confirmation_reconstruction_audit.csv"
    switch_path = reports_dir / "lookahead_switch_timing_audit.csv"
    slippage_path = reports_dir / "lookahead_slippage_turnover_audit.csv"
    conclusion_path = reports_dir / "lookahead_signal_execution_conclusion.csv"
    markdown_path = reports_dir / "lookahead_signal_execution_audit.md"

    column_audit.to_csv(column_path, index=False)
    trend_sma_audit.to_csv(trend_path, index=False)
    confirmation_audit.to_csv(confirmation_path, index=False)
    switch_timing_audit.to_csv(switch_path, index=False)
    slippage_turnover_audit.to_csv(slippage_path, index=False)
    conclusion.to_csv(conclusion_path, index=False)

    write_lookahead_audit_markdown(
        column_audit=column_audit,
        trend_sma_audit=trend_sma_audit,
        confirmation_audit=confirmation_audit,
        switch_timing_audit=switch_timing_audit,
        slippage_turnover_audit=slippage_turnover_audit,
        conclusion=conclusion,
        output_path=markdown_path,
    )

    print("\nLookahead required-column audit:")
    print(column_audit.to_string(index=False))

    print("\nLookahead trend SMA audit:")
    print(trend_sma_audit.to_string(index=False))

    print("\nLookahead confirmation reconstruction audit:")
    print(confirmation_audit.to_string(index=False))

    print("\nLookahead switch timing audit:")
    print(switch_timing_audit.to_string(index=False))

    print("\nLookahead slippage/turnover audit:")
    print(slippage_turnover_audit.to_string(index=False))

    print("\nLookahead signal-execution conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved lookahead required-column audit to: {column_path}")
    print(f"Saved lookahead trend SMA audit to: {trend_path}")
    print(f"Saved lookahead confirmation audit to: {confirmation_path}")
    print(f"Saved lookahead switch timing audit to: {switch_path}")
    print(f"Saved lookahead slippage/turnover audit to: {slippage_path}")
    print(f"Saved lookahead conclusion to: {conclusion_path}")
    print(f"Saved lookahead markdown report to: {markdown_path}")

    return outputs