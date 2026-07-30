import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from market_strats.intelligence.mi2.technical_baseline import (
    FEATURE_COLUMNS,
    RIDGE_ALPHA,
    RISK_FREE_INSTRUMENT_ID,
    build_feature_panel,
    derive_common_research_start,
    fit_ridge_predict,
    load_mi1_inputs,
    validate_mi1_contract,
)

NEW_YORK_TZ = ZoneInfo("America/New_York")
OPERATING_BRANCH = "shadow/mi8-v1"
OPERATING_TAG = "mi8-shadow-v1"
EXPECTED_MI1_INSTRUMENT_IDS = {
    "mi1_etf_agg",
    "mi1_etf_bil",
    "mi1_etf_dbc",
    "mi1_etf_eem",
    "mi1_etf_efa",
    "mi1_etf_gld",
    "mi1_etf_hyg",
    "mi1_etf_ief",
    "mi1_etf_iwm",
    "mi1_etf_lqd",
    "mi1_etf_qqq",
    "mi1_etf_spy",
    "mi1_etf_tlt",
    "mi1_etf_xlb",
    "mi1_etf_xle",
    "mi1_etf_xlf",
    "mi1_etf_xli",
    "mi1_etf_xlk",
    "mi1_etf_xlp",
    "mi1_etf_xlu",
    "mi1_etf_xlv",
    "mi1_etf_xly",
}
REQUIRED_LATEST_BAR_COLUMNS = [
    "instrument_id",
    "session_date",
    "open_raw",
    "high_raw",
    "low_raw",
    "close_raw",
    "volume_raw",
    "vendor_adjusted_close",
    "available_at_utc",
    "availability_evidence_level",
    "snapshot_id",
]


class ProspectiveShadowStartGuardError(ValueError):
    """Raised when a prospective shadow run would not be a valid live record."""


def _normalize_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column]).dt.normalize()
    return frame


def calculate_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def dict_to_stable_json(d: Any) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def _get_git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _get_head_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _get_tag_commit(tag_name: str = OPERATING_TAG) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{tag_name}^{{commit}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _get_tag_object_type(tag_name: str = OPERATING_TAG) -> str | None:
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", tag_name],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _is_git_clean() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return False


def _get_code_version_hash() -> str:
    # We hash the contents of mi2/technical_baseline.py and mi8/shadow_record.py.
    mi2_path = Path(__file__).parent.parent / "mi2" / "technical_baseline.py"
    mi8_path = Path(__file__)
    content = ""
    if mi2_path.exists():
        content += mi2_path.read_text(encoding="utf-8")
    if mi8_path.exists():
        content += mi8_path.read_text(encoding="utf-8")
    return calculate_hash(content.encode("utf-8"))


def _get_model_version_hash() -> str:
    # Hash of active model set and constants
    config = {
        "models": [
            "zero_forward_excess_return",
            "persistence_last_observed_return",
            "ridge_technical_only_alpha_1_0",
        ],
        "ridge_alpha": RIDGE_ALPHA,
        "features": FEATURE_COLUMNS,
    }
    return calculate_hash(dict_to_stable_json(config).encode("utf-8"))


def build_protocol_manifest() -> dict[str, Any]:
    return {
        "active_model_set": [
            "zero_forward_excess_return",
            "persistence_last_observed_return",
            "ridge_technical_only_alpha_1_0",
        ],
        "constants": {"ridge_alpha": RIDGE_ALPHA, "features": FEATURE_COLUMNS},
        "universe": "fixed_22_etf_v1",
        "input_schema": "mi1_normalized_v1",
        "target_convention": "next_session_close_to_close_v1",
        "code_version_hash": _get_code_version_hash(),
        "model_version_hash": _get_model_version_hash(),
    }


def _current_new_york_timestamp() -> pd.Timestamp:
    return pd.Timestamp.now(tz=NEW_YORK_TZ)


def check_frozen_manifest(mi8_data_root: Path, current_manifest: dict[str, Any]) -> None:
    manifest_path = mi8_data_root / "manifests" / "frozen_protocol_manifest.json"
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(current_manifest, indent=2), encoding="utf-8")
    else:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing != current_manifest:
            raise ValueError("Prospective run differs from frozen protocol manifest.")


@dataclass
class ScheduleInfo:
    prediction_date: pd.Timestamp
    decision_timestamp: pd.Timestamp
    execution_start_date: pd.Timestamp
    horizons: dict[int, dict[str, pd.Timestamp]]


def _build_schedule(sessions: list[pd.Timestamp]) -> dict[pd.Timestamp, ScheduleInfo]:
    from pandas.tseries.offsets import BDay

    schedule = {}
    session_list = sorted(sessions)
    for i, s in enumerate(session_list):
        if i + 1 < len(session_list):
            exec_start = session_list[i + 1]
        else:
            exec_start = s + BDay(1)

        horizons = {}
        for h in [1, 5, 20]:
            if i + 1 + h < len(session_list):
                maturity = session_list[i + 1 + h]
            else:
                missing_sessions = (i + 1 + h) - (len(session_list) - 1)
                maturity = session_list[-1] + BDay(missing_sessions)

            horizons[h] = {
                "outcome_maturity_date": maturity,
                "realized_label_availability_date": pd.Timestamp(
                    maturity.strftime("%Y-%m-%d") + " 20:00:00", tz="America/New_York"
                ),
            }

        schedule[s] = ScheduleInfo(
            prediction_date=s,
            decision_timestamp=pd.Timestamp(
                s.strftime("%Y-%m-%d") + " 20:00:00", tz="America/New_York"
            ),
            execution_start_date=exec_start,
            horizons=horizons,
        )
    return schedule


def _calculate_target_returns(
    eligible_bars: pd.DataFrame, schedule: dict[pd.Timestamp, ScheduleInfo]
) -> pd.DataFrame:
    # We need to compute returns from execution_start_date to outcome_maturity_date.
    # Return = adjusted_close(outcome_maturity_date) / adjusted_close(execution_start_date) - 1.0
    # BIL is used for excess return.
    prices = eligible_bars.pivot(
        index="session_date", columns="instrument_id", values="vendor_adjusted_close"
    )

    rows = []
    for s, info in schedule.items():
        if info.execution_start_date not in prices.index:
            continue
        exec_prices = prices.loc[info.execution_start_date]
        if RISK_FREE_INSTRUMENT_ID not in exec_prices or pd.isna(
            exec_prices[RISK_FREE_INSTRUMENT_ID]
        ):
            continue

        for h, h_info in info.horizons.items():
            maturity = h_info["outcome_maturity_date"]
            if maturity not in prices.index:
                continue
            mat_prices = prices.loc[maturity]
            if RISK_FREE_INSTRUMENT_ID not in mat_prices or pd.isna(
                mat_prices[RISK_FREE_INSTRUMENT_ID]
            ):
                continue

            bil_ret = (
                mat_prices[RISK_FREE_INSTRUMENT_ID] / exec_prices[RISK_FREE_INSTRUMENT_ID] - 1.0
            )

            for inst in prices.columns:
                if inst == RISK_FREE_INSTRUMENT_ID:
                    continue
                if pd.notna(exec_prices[inst]) and pd.notna(mat_prices[inst]):
                    inst_ret = mat_prices[inst] / exec_prices[inst] - 1.0
                    excess = inst_ret - bil_ret
                    rows.append(
                        {
                            "session_date": s,
                            "instrument_id": inst,
                            "horizon": h,
                            "target_value": excess,
                            "realized_label_availability_date": h_info[
                                "realized_label_availability_date"
                            ],
                        }
                    )
    return pd.DataFrame(rows)


def _validate_prospective_operating_release() -> None:
    branch = _get_git_branch()
    if branch != OPERATING_BRANCH:
        raise ProspectiveShadowStartGuardError(
            f"Prospective shadow can only run on '{OPERATING_BRANCH}' branch; "
            f"current branch is '{branch}'."
        )

    head_commit = _get_head_commit()
    tag_commit = _get_tag_commit()
    tag_object_type = _get_tag_object_type()
    if tag_commit is None or tag_object_type != "tag":
        raise ProspectiveShadowStartGuardError(
            f"Prospective shadow requires annotated tag '{OPERATING_TAG}' to resolve."
        )
    if head_commit is None:
        raise ProspectiveShadowStartGuardError("Prospective shadow requires HEAD to resolve.")
    if head_commit != tag_commit:
        raise ProspectiveShadowStartGuardError(
            f"Prospective shadow requires HEAD to match {OPERATING_TAG}^{{commit}}."
        )

    if not _is_git_clean():
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow requires a clean Git working tree."
        )


def _validate_latest_session_bars(eligible_bars: pd.DataFrame, decision_date: pd.Timestamp) -> None:
    missing_columns = [
        column for column in REQUIRED_LATEST_BAR_COLUMNS if column not in eligible_bars.columns
    ]
    if missing_columns:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest-session MI-1 bars are missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    latest_session = pd.Timestamp(eligible_bars["session_date"].max()).normalize()
    if latest_session != decision_date:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow requires the latest eligible MI-1 session to equal the "
            f"decision date; latest eligible session is {latest_session.date()} and "
            f"decision date is {decision_date.date()}."
        )

    latest = eligible_bars[eligible_bars["session_date"] == decision_date].copy()
    counts = latest["instrument_id"].value_counts()
    observed = set(counts.index.astype(str))
    missing = EXPECTED_MI1_INSTRUMENT_IDS - observed
    unexpected = observed - EXPECTED_MI1_INSTRUMENT_IDS
    duplicates = sorted(
        instrument_id
        for instrument_id in EXPECTED_MI1_INSTRUMENT_IDS
        if int(counts.get(instrument_id, 0)) > 1
    )
    if missing:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest MI-1 session is missing expected ETFs: "
            + ", ".join(sorted(missing))
        )
    if unexpected:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest MI-1 session contains unexpected instruments: "
            + ", ".join(sorted(unexpected))
        )
    if duplicates:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest MI-1 session has duplicate ETF bars: "
            + ", ".join(duplicates)
        )

    required_values = latest[REQUIRED_LATEST_BAR_COLUMNS]
    null_rows = required_values[required_values.isna().any(axis=1)]
    if not null_rows.empty:
        affected = sorted(null_rows["instrument_id"].astype(str).unique().tolist())
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest MI-1 session has null required bar values for: "
            + ", ".join(affected)
        )

    unverified = latest[latest["availability_evidence_level"] == "unverified"]
    if not unverified.empty:
        affected = sorted(unverified["instrument_id"].astype(str).unique().tolist())
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest MI-1 session admitted unverified bars for: "
            + ", ".join(affected)
        )


def _validate_latest_feature_coverage(
    feature_panel: pd.DataFrame, decision_date: pd.Timestamp
) -> None:
    latest_features = feature_panel[feature_panel["session_date"] == decision_date].copy()
    predicted_ids = EXPECTED_MI1_INSTRUMENT_IDS - {RISK_FREE_INSTRUMENT_ID}
    counts = latest_features["instrument_id"].value_counts()
    observed = set(counts.index.astype(str))
    missing = predicted_ids - observed
    duplicates = sorted(
        instrument_id for instrument_id in predicted_ids if int(counts.get(instrument_id, 0)) > 1
    )
    if missing:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest feature panel is missing predicted risk ETFs: "
            + ", ".join(sorted(missing))
        )
    if duplicates:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest feature panel has duplicate predicted risk ETFs: "
            + ", ".join(duplicates)
        )

    risk_features = latest_features[latest_features["instrument_id"].isin(predicted_ids)]
    unavailable = risk_features[~risk_features["feature_available"]]
    if not unavailable.empty:
        affected = sorted(unavailable["instrument_id"].astype(str).unique().tolist())
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow latest feature panel is not usable for predicted risk ETFs: "
            + ", ".join(affected)
        )


def _latest_usable_feature_session(feature_panel: pd.DataFrame) -> pd.Timestamp:
    usable_sessions = feature_panel.loc[feature_panel["feature_available"], "session_date"].dropna()
    if usable_sessions.empty:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow requires at least one usable frozen feature-panel session."
        )
    return pd.Timestamp(usable_sessions.max()).normalize()


def _resolve_prospective_decision_date(
    *,
    start_date: str,
    end_date: str,
    feature_panel: pd.DataFrame,
    new_york_now: pd.Timestamp | None = None,
) -> pd.Timestamp:
    if start_date != "auto" or end_date != "auto":
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow requires --start-date auto and --end-date auto; "
            "historical date ranges are only permitted for historical replay."
        )

    decision_date = _latest_usable_feature_session(feature_panel)
    now_ny = (
        pd.Timestamp(new_york_now) if new_york_now is not None else _current_new_york_timestamp()
    )
    if now_ny.tzinfo is None:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow clock must be timezone-aware in America/New_York."
        )
    now_ny = now_ny.tz_convert(NEW_YORK_TZ)

    current_ny_date = now_ny.normalize()
    if decision_date.date() != current_ny_date.date():
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow decision date must equal the current America/New_York "
            f"calendar date; latest usable feature date is {decision_date.date()} and "
            f"current New York date is {current_ny_date.date()}."
        )

    cutoff = pd.Timestamp(f"{now_ny.date()} 20:00:00", tz=NEW_YORK_TZ)
    if now_ny < cutoff:
        raise ProspectiveShadowStartGuardError(
            "Prospective shadow may only run at or after 20:00 America/New_York "
            f"on the decision date; current New York time is {now_ny.isoformat()}."
        )

    return decision_date


def run_shadow_record(
    mode: str,
    start_date: str,
    end_date: str,
    mi1_data_root: Path,
    mi8_data_root: Path,
    report_root: Path,
    new_york_now: pd.Timestamp | None = None,
) -> None:
    if mode == "prospective-shadow":
        if start_date != "auto" or end_date != "auto":
            raise ProspectiveShadowStartGuardError(
                "Prospective shadow requires --start-date auto and --end-date auto; "
                "historical date ranges are only permitted for historical replay."
            )
        _validate_prospective_operating_release()
        evidence_class = "prospective_shadow"
        promotion_eligible = True
    elif mode == "historical-replay":
        evidence_class = "historical_shadow_replay"
        promotion_eligible = False
    else:
        raise ValueError(f"Unknown mode: {mode}")

    protocol_manifest = build_protocol_manifest()

    inputs = load_mi1_inputs(mi1_data_root)
    eligible_bars = validate_mi1_contract(inputs)
    instrument_ids = sorted(eligible_bars["instrument_id"].unique())
    corporate_actions = _normalize_dates(inputs["corporate_action_event"], ["session_date"])

    # Deriving research start
    # "historical replay beginning on: 2026-01-01"
    # Feature panel still needs minimum history
    min_sessions = 252  # Based on MI-2
    research_start = derive_common_research_start(eligible_bars, instrument_ids, min_sessions)
    feature_panel = build_feature_panel(eligible_bars, corporate_actions, research_start)

    sessions = sorted(eligible_bars["session_date"].unique())
    schedule = _build_schedule(sessions)

    if mode == "prospective-shadow":
        decision_date = _resolve_prospective_decision_date(
            start_date=start_date,
            end_date=end_date,
            feature_panel=feature_panel,
            new_york_now=new_york_now,
        )
        _validate_latest_session_bars(eligible_bars, decision_date)
        _validate_latest_feature_coverage(feature_panel, decision_date)
        check_frozen_manifest(mi8_data_root, protocol_manifest)
        start_ts = decision_date
        end_ts = decision_date
        decision_dates = [decision_date]
    else:
        if start_date != "auto":
            start_ts = pd.Timestamp(start_date).normalize()
        else:
            start_ts = pd.Timestamp("2026-01-01").normalize()

        if end_date == "auto":
            # "use the latest complete eligible decision date available in MI-1 data"
            # That means a date where features are available.
            end_ts = feature_panel["session_date"].max()
        else:
            end_ts = pd.Timestamp(end_date).normalize()

        decision_dates = [s for s in sessions if start_ts <= s <= end_ts]

    # We filter target panel computation only up to available labels.
    targets = _calculate_target_returns(eligible_bars, schedule)

    universe_hash = calculate_hash(dict_to_stable_json(instrument_ids).encode("utf-8"))
    model_version_hash = protocol_manifest["model_version_hash"]
    code_version_hash = protocol_manifest["code_version_hash"]

    mi8_data_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    ledger_dir = mi8_data_root / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    batches_dir = ledger_dir / "prediction_batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    manifests_dir = mi8_data_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = ledger_dir / "prediction_batch_manifest.jsonl"

    report_data = {
        "mode": mode.replace("-", "_"),
        "evidence_class": evidence_class,
        "promotion_eligible": promotion_eligible,
        "decision_date_range": f"{start_ts.strftime('%Y-%m-%d')} to {end_ts.strftime('%Y-%m-%d')}",
        "prediction_batch_count": 0,
        "prediction_row_count_by_model_and_horizon": {},
        "new_batches": 0,
        "no_op_batches": 0,
        "conflicts": 0,
        "frozen_protocol_hash": calculate_hash(
            dict_to_stable_json(protocol_manifest).encode("utf-8")
        ),
        "known_limitations": [
            "Historical replay is not prospective promotion evidence.",
            "The historical holdout is an observed development holdout.",
            "No portfolio, trading, candidate, or GMA decision is produced.",
            "MI-8 does not establish forecast skill or economic value.",
        ],
    }

    def add_count(model, horizon, count):
        key = f"{model}_{horizon}_session"
        report_data["prediction_row_count_by_model_and_horizon"][key] = (
            report_data["prediction_row_count_by_model_and_horizon"].get(key, 0) + count
        )

    # Pre-process snapshot IDs and feature hash
    snapshot_ids = json.dumps(inputs["market_eod_bar"]["snapshot_id"].dropna().unique().tolist())

    # Model training and prediction
    for d_date in decision_dates:
        if d_date not in schedule:
            continue
        info = schedule[d_date]
        decision_timestamp = info.decision_timestamp

        # Features available up to d_date
        d_features = feature_panel[feature_panel["session_date"] == d_date]
        if d_features.empty or not d_features["feature_available"].any():
            continue

        feature_snapshot_hash = calculate_hash(d_features.to_json().encode("utf-8"))

        for horizon in [1, 5, 20]:
            if horizon not in info.horizons:
                continue
            h_info = info.horizons[horizon]

            # Train on rows where realized_label_availability_date < decision_timestamp
            if not targets.empty:
                train_targets = targets[
                    (targets["horizon"] == horizon)
                    & (targets["realized_label_availability_date"] < decision_timestamp)
                ]
            else:
                train_targets = pd.DataFrame()

            train_features = feature_panel[feature_panel["session_date"] < d_date]

            if not train_targets.empty and not train_features.empty:
                train_data = pd.merge(
                    train_features, train_targets, on=["session_date", "instrument_id"]
                )
                train_data = train_data[
                    train_data["feature_available"] & train_data["target_value"].notna()
                ]
            else:
                train_data = pd.DataFrame()

            test_data = d_features[
                d_features["feature_available"]
                & (d_features["instrument_id"] != RISK_FREE_INSTRUMENT_ID)
            ]

            predictions = []

            # Zero model
            for _, row in test_data.iterrows():
                predictions.append((row["instrument_id"], "zero_forward_excess_return", 0.0))

            # Persistence model (raw_return_21)
            for _, row in test_data.iterrows():
                predictions.append(
                    (row["instrument_id"], "persistence_last_observed_return", row["raw_return_21"])
                )

            # Ridge
            if not train_data.empty and not test_data.empty:
                try:
                    ridge_preds = fit_ridge_predict(
                        train_data[FEATURE_COLUMNS],
                        train_data["target_value"],
                        test_data[FEATURE_COLUMNS],
                        alpha=RIDGE_ALPHA,
                    )
                    for (_, row), p in zip(test_data.iterrows(), ridge_preds):
                        predictions.append(
                            (row["instrument_id"], "ridge_technical_only_alpha_1_0", p)
                        )
                except Exception:
                    pass
            else:
                for _, row in test_data.iterrows():
                    predictions.append(
                        (row["instrument_id"], "ridge_technical_only_alpha_1_0", 0.0)
                    )

            if not predictions:
                continue

            batch_id = (
                f"{d_date.strftime('%Y-%m-%d')}_{model_version_hash}_{horizon}_{universe_hash}"
            )

            batch_file = batches_dir / f"{batch_id}.parquet"

            if batch_file.exists():
                try:
                    existing_df = pd.read_parquet(batch_file)
                    now_ts = existing_df["prediction_written_timestamp"].iloc[0]
                except Exception:
                    now_ts = pd.Timestamp.utcnow().isoformat()
            else:
                now_ts = pd.Timestamp.utcnow().isoformat()

            batch_rows = []

            for inst, model_id, p_val in predictions:
                row_dict = {
                    "prediction_batch_identity": batch_id,
                    "decision_date": d_date.strftime("%Y-%m-%d"),
                    "decision_timestamp": decision_timestamp.isoformat(),
                    "prediction_written_timestamp": now_ts,
                    "mode": mode.replace("-", "_"),
                    "evidence_class": evidence_class,
                    "promotion_eligible": promotion_eligible,
                    "model_id": model_id,
                    "model_version_hash": model_version_hash,
                    "code_version_hash": code_version_hash,
                    "model_constants_json": dict_to_stable_json(protocol_manifest["constants"]),
                    "universe_hash": universe_hash,
                    "universe_id": protocol_manifest["universe"],
                    "instrument_id": inst,
                    "target_horizon": horizon,
                    "source_snapshot_ids_json": snapshot_ids,
                    "feature_snapshot_hash": feature_snapshot_hash,
                    "availability_evidence_json": "{}",
                    "feature_cutoff_timestamp": decision_timestamp.isoformat(),
                    "execution_start_date": info.execution_start_date.strftime("%Y-%m-%d"),
                    "outcome_maturity_date": h_info["outcome_maturity_date"].strftime("%Y-%m-%d"),
                    "realized_label_availability_date": h_info[
                        "realized_label_availability_date"
                    ].isoformat(),
                    "prediction_value": float(p_val),
                }
                # To calculate content hash, we serialize first
                # Actually, requirement: "prediction_content_hash" -> The hash of the row content
                # We will compute it:
                row_str = dict_to_stable_json(row_dict)
                row_dict["prediction_content_hash"] = calculate_hash(row_str.encode("utf-8"))
                batch_rows.append(row_dict)
                add_count(model_id, horizon, 1)

            batch_df = pd.DataFrame(batch_rows)
            # deterministic path
            batch_file = batches_dir / f"{batch_id}.parquet"

            # calculate content hash of the batch df
            # To be reproducible, save to a buffer
            import io

            buf = io.BytesIO()
            batch_df.to_parquet(buf, index=False)
            new_hash = calculate_hash(buf.getvalue())

            report_data["prediction_batch_count"] += 1

            if batch_file.exists():
                existing_hash = calculate_hash(batch_file.read_bytes())
                if new_hash == existing_hash:
                    report_data["no_op_batches"] += 1
                    continue
                else:
                    report_data["conflicts"] += 1
                    raise RuntimeError(
                        f"Conflict error: Batch {batch_id} exists but content differs!"
                    )
            else:
                batch_file.write_bytes(buf.getvalue())
                report_data["new_batches"] += 1

                # Append to manifest
                with manifest_file.open("a", encoding="utf-8") as f:
                    manifest_entry = {
                        "prediction_batch_identity": batch_id,
                        "decision_date": d_date.strftime("%Y-%m-%d"),
                        "mode": mode.replace("-", "_"),
                        "evidence_class": evidence_class,
                        "promotion_eligible": promotion_eligible,
                        "model_version_hash": model_version_hash,
                        "universe_hash": universe_hash,
                        "target_horizon": horizon,
                        "model_ids": sorted(list(set(m for _, m, _ in predictions))),
                        "prediction_content_hash": new_hash,
                        "batch_path": str(batch_file.relative_to(mi8_data_root)),
                        "written_at": now_ts,
                    }
                    f.write(dict_to_stable_json(manifest_entry) + "\n")

    report_root.mkdir(parents=True, exist_ok=True)
    with (report_root / "mi8_shadow_recording_summary.json").open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    md_lines = [
        "# MI-8 Shadow Recording Summary",
        "",
        f"- Mode: {report_data['mode']}",
        f"- Evidence class: {report_data['evidence_class']}",
        f"- Promotion eligible: {report_data['promotion_eligible']}",
        f"- Decision date range: {report_data['decision_date_range']}",
        f"- Prediction batch count: {report_data['prediction_batch_count']}",
        f"- New batches: {report_data['new_batches']}",
        f"- No-op batches: {report_data['no_op_batches']}",
        f"- Conflicts: {report_data['conflicts']}",
        f"- Frozen protocol hash: {report_data['frozen_protocol_hash']}",
        "",
        "## Counts by model and horizon",
        "",
    ]
    for k, v in report_data["prediction_row_count_by_model_and_horizon"].items():
        md_lines.append(f"- {k}: {v}")

    md_lines.append("")
    md_lines.append("## Known limitations")
    md_lines.append("")
    for lim in report_data["known_limitations"]:
        md_lines.append(f"- {lim}")

    (report_root / "mi8_shadow_recording_summary.md").write_text(
        "\n".join(md_lines), encoding="utf-8"
    )
