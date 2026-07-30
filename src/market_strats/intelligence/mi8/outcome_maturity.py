import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.intelligence.mi2.technical_baseline import (
    RISK_FREE_INSTRUMENT_ID,
    load_mi1_inputs,
    validate_mi1_contract,
)


def calculate_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def dict_to_stable_json(d: Any) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def run_outcome_maturity(
    mi1_data_root: Path, mi8_data_root: Path, report_root: Path, as_of_timestamp: str | None = None
) -> None:
    if as_of_timestamp is not None:
        current_as_of_ts = pd.Timestamp(as_of_timestamp).tz_convert("America/New_York")
    else:
        current_as_of_ts = pd.Timestamp.now(tz="America/New_York")

    inputs = load_mi1_inputs(mi1_data_root)
    eligible_bars = validate_mi1_contract(inputs)
    prices = eligible_bars.pivot(
        index="session_date", columns="instrument_id", values="vendor_adjusted_close"
    )

    mi8_data_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    ledger_dir = mi8_data_root / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    batches_dir = ledger_dir / "prediction_batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    manifests_dir = mi8_data_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = ledger_dir / "prediction_batch_manifest.jsonl"

    maturity_manifest_file = ledger_dir / "outcome_maturity_manifest.jsonl"
    maturity_batches_dir = ledger_dir / "outcome_maturity_batches"
    maturity_batches_dir.mkdir(parents=True, exist_ok=True)

    if not manifest_file.exists():
        return  # No predictions to mature

    matured_by_horizon = {1: 0, 5: 0, 20: 0}
    unmatured_by_horizon = {1: 0, 5: 0, 20: 0}
    unmatured_dates = []

    report_data = {
        "as_of_timestamp": current_as_of_ts.isoformat(),
        "earliest_unmatured_realized_label_availability_date": None,
        "latest_unmatured_realized_label_availability_date": None,
        "matured_outcomes_by_horizon": {},
        "unmatured_outcomes_by_horizon": {},
        "new_batches": 0,
        "no_op_batches": 0,
        "conflicts": 0,
    }

    with manifest_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            batch_path = mi8_data_root / entry["batch_path"]
            if not batch_path.exists():
                continue

            batch_df = pd.read_parquet(batch_path)

            if "mode" in batch_df.columns:
                batch_mode = batch_df["mode"].iloc[0]
                if batch_mode == "prospective_shadow" and as_of_timestamp is not None:
                    raise ValueError(
                        "A supplied --as-of-timestamp is permitted only for "
                        "deterministic historical-replay testing; it must be "
                        "rejected in prospective-shadow mode."
                    )

            batch_id = batch_df["prediction_batch_identity"].iloc[0]
            mat_file = maturity_batches_dir / f"maturity_{batch_id}.parquet"
            if mat_file.exists():
                try:
                    mat_ts = str(pd.read_parquet(mat_file)["matured_at"].iloc[0])
                except Exception:
                    mat_ts = pd.Timestamp.utcnow().isoformat()
            else:
                mat_ts = pd.Timestamp.utcnow().isoformat()

            maturity_rows = []

            for _, row in batch_df.iterrows():
                h = row["target_horizon"]
                inst = row["instrument_id"]
                exec_date = pd.Timestamp(row["execution_start_date"])
                mat_date = pd.Timestamp(row["outcome_maturity_date"])
                label_ts = pd.Timestamp(row["realized_label_availability_date"]).tz_convert(
                    "America/New_York"
                )

                # Check if we have data for execution and maturity and maturity time has passed
                if (
                    current_as_of_ts >= label_ts
                    and exec_date in prices.index
                    and mat_date in prices.index
                ):
                    exec_prices = prices.loc[exec_date]
                    mat_prices = prices.loc[mat_date]

                    if (
                        pd.notna(exec_prices.get(inst))
                        and pd.notna(mat_prices.get(inst))
                        and pd.notna(exec_prices.get(RISK_FREE_INSTRUMENT_ID))
                        and pd.notna(mat_prices.get(RISK_FREE_INSTRUMENT_ID))
                    ):
                        inst_ret = mat_prices[inst] / exec_prices[inst] - 1.0
                        bil_ret = (
                            mat_prices[RISK_FREE_INSTRUMENT_ID]
                            / exec_prices[RISK_FREE_INSTRUMENT_ID]
                            - 1.0
                        )
                        excess = inst_ret - bil_ret

                        maturity_rows.append(
                            {
                                "prediction_batch_identity": row["prediction_batch_identity"],
                                "instrument_id": inst,
                                "realized_bil_excess_outcome": float(excess),
                                "matured_at": mat_ts,
                            }
                        )
                        matured_by_horizon[h] = matured_by_horizon.get(h, 0) + 1
                    else:
                        unmatured_by_horizon[h] = unmatured_by_horizon.get(h, 0) + 1
                        unmatured_dates.append(label_ts)
                else:
                    unmatured_by_horizon[h] = unmatured_by_horizon.get(h, 0) + 1
                    unmatured_dates.append(label_ts)

            if maturity_rows:
                mat_df = pd.DataFrame(maturity_rows)
                batch_id = batch_df["prediction_batch_identity"].iloc[0]
                mat_file = maturity_batches_dir / f"maturity_{batch_id}.parquet"

                import io

                buf = io.BytesIO()
                mat_df.to_parquet(buf, index=False)
                new_hash = calculate_hash(buf.getvalue())

                if mat_file.exists():
                    existing_hash = calculate_hash(mat_file.read_bytes())
                    if new_hash == existing_hash:
                        report_data["no_op_batches"] += 1
                        continue
                    else:
                        report_data["conflicts"] += 1
                        raise RuntimeError(
                            f"Conflict error: Maturity batch {batch_id} exists but content differs!"
                        )
                else:
                    mat_file.write_bytes(buf.getvalue())
                    report_data["new_batches"] += 1

                    with maturity_manifest_file.open("a", encoding="utf-8") as f_out:
                        mat_entry = {
                            "prediction_batch_identity": batch_id,
                            "maturity_batch_path": str(mat_file.relative_to(mi8_data_root)),
                            "content_hash": new_hash,
                            "written_at": pd.Timestamp.utcnow().isoformat(),
                        }
                        f_out.write(dict_to_stable_json(mat_entry) + "\n")

    for h in [1, 5, 20]:
        report_data["matured_outcomes_by_horizon"][f"{h}_session"] = matured_by_horizon[h]
        report_data["unmatured_outcomes_by_horizon"][f"{h}_session"] = unmatured_by_horizon[h]

    if unmatured_dates:
        report_data["earliest_unmatured_realized_label_availability_date"] = min(
            unmatured_dates
        ).isoformat()
        report_data["latest_unmatured_realized_label_availability_date"] = max(
            unmatured_dates
        ).isoformat()

    report_root.mkdir(parents=True, exist_ok=True)
    with (report_root / "mi8_outcome_maturity_summary.json").open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    md_lines = [
        "# MI-8 Outcome Maturity Summary",
        "",
        f"- As of timestamp: {report_data['as_of_timestamp']}",
        f"- New batches: {report_data['new_batches']}",
        f"- No-op batches: {report_data['no_op_batches']}",
        f"- Conflicts: {report_data['conflicts']}",
    ]
    if report_data["earliest_unmatured_realized_label_availability_date"]:
        earliest = report_data["earliest_unmatured_realized_label_availability_date"]
        latest = report_data["latest_unmatured_realized_label_availability_date"]
        md_lines.extend(
            [
                f"- Earliest unmatured date: {earliest}",
                f"- Latest unmatured date: {latest}",
            ]
        )
    md_lines.extend(
        [
            "",
            "## Matured outcomes by horizon",
        ]
    )
    for k, v in report_data["matured_outcomes_by_horizon"].items():
        md_lines.append(f"- {k}: {v}")

    md_lines.append("")
    md_lines.append("## Unmatured outcomes by horizon")
    for k, v in report_data["unmatured_outcomes_by_horizon"].items():
        md_lines.append(f"- {k}: {v}")

    (report_root / "mi8_outcome_maturity_summary.md").write_text(
        "\n".join(md_lines), encoding="utf-8"
    )
