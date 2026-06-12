from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd


TRACKING_RELATIVE_DIR = Path("reports/paper_trading/regime_informed_tracking")
TEMPLATE_FILENAME = "regime_informed_manual_session_template.csv"
TARGETS_FILENAME = "regime_informed_paper_targets.csv"
FILLED_FILENAME = "regime_informed_manual_session_filled.csv"

TRACKED_CANDIDATES = (
    "phase6b_loose_relief_execution_realistic_overlay",
    "canonical_spy_qqq_gld_tlt_50_30_10_10",
    "canonical_inverse_vol_63d_btc_usd_qqq_spy",
    "canonical_spy_qqq_60_40",
)
BTC_CANDIDATE_ID = "canonical_inverse_vol_63d_btc_usd_qqq_spy"
SAFETY_COLUMNS = (
    "live_trading_allowed",
    "real_money_allowed",
    "broker_api_integration_allowed",
    "promotion_allowed",
)
ACKNOWLEDGEMENT_COLUMNS = (
    "tear_sheet_reviewed",
    "warnings_acknowledged",
    "btc_caveat_acknowledged",
    "reference_only_acknowledged",
    "inception_limited_acknowledged",
)
REQUIRED_TEMPLATE_COLUMNS = {
    "session_date",
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "target_notional_usd",
    "paper_order_allowed",
    "candidate_caveats",
    *ACKNOWLEDGEMENT_COLUMNS,
    "manual_decision",
    "manual_execution_status",
    "paper_account_value",
    "paper_fill_price",
    "paper_fill_quantity",
    "actual_notional_usd",
    "deviation_from_preview_usd",
    "deviation_from_preview_pct",
    "override_reason",
    "notes",
    *SAFETY_COLUMNS,
}
REQUIRED_TARGET_COLUMNS = {
    "selected_signal_date",
    "canonical_candidate_id",
    "candidate_role",
    "asset",
    "target_weight",
    "candidate_caveats",
}

PriceLoader = Callable[[str, str | None], tuple[float, str, Path]]


class EnteredSessionFillError(ValueError):
    """Raised when a safe, complete paper-session fill cannot be produced."""


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _read_required_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        raise EnteredSessionFillError(f"required CSV is missing: {path}")
    frame = pd.read_csv(path)
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise EnteredSessionFillError(
            f"{path.name} is missing required columns: {', '.join(missing)}"
        )
    if frame.empty:
        raise EnteredSessionFillError(f"required CSV is empty: {path}")
    return frame


def _candidate_asset_keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    return {
        (_text(row.get("canonical_candidate_id")), _text(row.get("asset")).upper())
        for row in frame.to_dict("records")
    }


def _validate_candidate_scope(template: pd.DataFrame, targets: pd.DataFrame) -> None:
    template_candidates = set(template["canonical_candidate_id"].astype(str))
    target_candidates = set(targets["canonical_candidate_id"].astype(str))
    expected = set(TRACKED_CANDIDATES)

    if template_candidates != expected:
        missing = sorted(expected - template_candidates)
        unexpected = sorted(template_candidates - expected)
        raise EnteredSessionFillError(
            "manual template candidate scope mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if target_candidates != expected:
        missing = sorted(expected - target_candidates)
        unexpected = sorted(target_candidates - expected)
        raise EnteredSessionFillError(
            "paper targets candidate scope mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )

    template_keys = _candidate_asset_keys(template)
    target_keys = _candidate_asset_keys(targets)
    if template_keys != target_keys:
        raise EnteredSessionFillError(
            "template and target candidate/asset rows do not match; "
            f"template_only={sorted(template_keys - target_keys)}, "
            f"targets_only={sorted(target_keys - template_keys)}"
        )
    if template.duplicated(["canonical_candidate_id", "asset"]).any():
        raise EnteredSessionFillError("manual template contains duplicate candidate/asset rows")
    if targets.duplicated(["canonical_candidate_id", "asset"]).any():
        raise EnteredSessionFillError("paper targets contain duplicate candidate/asset rows")


def _price_paths(root: Path, symbol: str) -> list[Path]:
    return [
        root / "data" / "fresh" / "processed" / f"{symbol}.parquet",
        root / "data" / "processed" / f"{symbol}.parquet",
        root / "data" / "fresh" / "processed" / f"{symbol}.csv",
        root / "data" / "processed" / f"{symbol}.csv",
    ]


def load_latest_local_price(
    root: Path,
    symbol: str,
    as_of_date: str | None = None,
) -> tuple[float, str, Path]:
    """Load the latest positive local adjusted close, falling back to raw close."""
    source_path = next((path for path in _price_paths(root, symbol) if path.exists()), None)
    if source_path is None:
        searched = ", ".join(str(path) for path in _price_paths(root, symbol))
        raise EnteredSessionFillError(f"missing local price file for {symbol}; searched: {searched}")

    if source_path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(source_path)
    else:
        frame = pd.read_csv(source_path)

    if "date" not in frame.columns:
        raise EnteredSessionFillError(f"{source_path} is missing date column")
    price_column = "adj_close" if "adj_close" in frame.columns else "close"
    if price_column not in frame.columns:
        raise EnteredSessionFillError(
            f"{source_path} is missing both adj_close and close columns"
        )

    prices = frame[["date", price_column]].copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices[price_column] = pd.to_numeric(prices[price_column], errors="coerce")
    prices = prices.dropna(subset=["date", price_column])
    prices = prices.loc[prices[price_column] > 0]
    if as_of_date:
        prices = prices.loc[prices["date"] <= pd.to_datetime(as_of_date)]
    prices = prices.sort_values("date").drop_duplicates("date", keep="last")
    if prices.empty:
        raise EnteredSessionFillError(
            f"no positive price for {symbol} on or before {as_of_date or 'latest'}"
        )

    latest = prices.iloc[-1]
    return (
        round(float(latest[price_column]), 4),
        pd.Timestamp(latest["date"]).date().isoformat(),
        source_path,
    )


def _round_quantity_down(value: float, decimals: int) -> float:
    if not math.isfinite(value) or value <= 0:
        return 0.0
    factor = 10**decimals
    return math.floor(value * factor + 1e-12) / factor


def _row_notes(candidate_id: str, candidate_role: str, asset: str) -> str:
    parts = [
        "First entered simulated paper session.",
        "Manual paper only.",
        "No live trading, no real money, no broker/API.",
    ]
    if "reference_only" in candidate_role.lower():
        parts.append("reference_only_candidate.")
    if candidate_id == BTC_CANDIDATE_ID:
        parts.append("btc_high_caveat_acknowledged.")
    if asset == "CASH":
        parts.append("cash_residual.")
    return " ".join(parts)


def build_entered_session(
    *,
    template: pd.DataFrame,
    targets: pd.DataFrame,
    paper_account_value: float,
    session_date: str,
    price_loader: PriceLoader,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a safe filled session and a price-source audit table."""
    if not math.isfinite(paper_account_value) or paper_account_value <= 0:
        raise EnteredSessionFillError("paper_account_value must be positive")
    _validate_candidate_scope(template, targets)

    target_lookup = {
        (_text(row["canonical_candidate_id"]), _text(row["asset"]).upper()): row
        for row in targets.to_dict("records")
    }
    filled = template.copy()

    # Blank manual-entry fields can be inferred as pandas/pyarrow string columns
    # (for example when future.infer_string is enabled).  Normalise the columns
    # we populate numerically before assigning float values row by row.
    numeric_columns = [
        "target_weight",
        "target_notional_usd",
        "paper_account_value",
        "paper_fill_price",
        "paper_fill_quantity",
        "actual_notional_usd",
        "deviation_from_preview_usd",
        "deviation_from_preview_pct",
    ]
    for column in numeric_columns:
        filled[column] = pd.to_numeric(filled[column], errors="coerce").astype(float)

    text_columns = [
        "session_date",
        "selected_signal_date",
        "canonical_candidate_id",
        "candidate_role",
        "asset",
        "candidate_caveats",
        "manual_decision",
        "manual_execution_status",
        "override_reason",
        "notes",
    ]
    for column in text_columns:
        filled[column] = filled[column].astype("object")
    audit_rows: list[dict[str, object]] = []

    for row_index, row in filled.iterrows():
        candidate_id = _text(row["canonical_candidate_id"])
        asset = _text(row["asset"]).upper()
        target_row = target_lookup[(candidate_id, asset)]
        candidate_role = _text(target_row.get("candidate_role", row.get("candidate_role", "")))
        target_weight = float(pd.to_numeric(target_row.get("target_weight"), errors="raise"))
        if target_weight < 0 or target_weight > 1:
            raise EnteredSessionFillError(
                f"invalid target weight for {candidate_id}/{asset}: {target_weight}"
            )
        if not _bool_value(row.get("paper_order_allowed", False)):
            raise EnteredSessionFillError(
                f"paper order is not allowed for {candidate_id}/{asset}"
            )

        target_notional = round(paper_account_value * target_weight, 2)
        selected_signal_date = _text(target_row.get("selected_signal_date")) or _text(
            row.get("selected_signal_date")
        )
        candidate_caveats = _text(target_row.get("candidate_caveats")) or _text(
            row.get("candidate_caveats")
        )

        filled.at[row_index, "session_date"] = session_date
        filled.at[row_index, "selected_signal_date"] = selected_signal_date
        filled.at[row_index, "candidate_role"] = candidate_role
        filled.at[row_index, "asset"] = asset
        filled.at[row_index, "target_weight"] = target_weight
        filled.at[row_index, "target_notional_usd"] = target_notional
        filled.at[row_index, "candidate_caveats"] = candidate_caveats
        for column in ACKNOWLEDGEMENT_COLUMNS:
            filled.at[row_index, column] = True
        filled.at[row_index, "manual_decision"] = "enter_paper_trade"
        filled.at[row_index, "paper_account_value"] = round(paper_account_value, 2)
        filled.at[row_index, "override_reason"] = (
            "first_entered_regime_informed_paper_session"
        )
        filled.at[row_index, "notes"] = _row_notes(candidate_id, candidate_role, asset)
        for column in SAFETY_COLUMNS:
            filled.at[row_index, column] = False

        if asset == "CASH":
            fill_price = 1.0
            fill_quantity = target_notional
            actual_notional = target_notional
            price_date = session_date
            source_path = Path("cash_residual")
            execution_status = "cash_residual"
        else:
            fill_price, price_date, source_path = price_loader(asset, session_date)
            if selected_signal_date and pd.Timestamp(price_date) < pd.Timestamp(
                selected_signal_date
            ):
                raise EnteredSessionFillError(
                    f"latest local price for {asset} is stale: price_date={price_date}, "
                    f"selected_signal_date={selected_signal_date}. Refresh local data first."
                )
            decimals = 8 if asset == "BTC-USD" else 4
            fill_quantity = _round_quantity_down(target_notional / fill_price, decimals)
            if fill_quantity <= 0:
                raise EnteredSessionFillError(
                    f"computed non-positive paper quantity for {candidate_id}/{asset}"
                )
            actual_notional = round(fill_price * fill_quantity, 2)
            execution_status = "entered"

        deviation_usd = round(actual_notional - target_notional, 2)
        deviation_pct = (
            round(deviation_usd / target_notional * 100.0, 4)
            if target_notional > 0
            else 0.0
        )
        filled.at[row_index, "manual_execution_status"] = execution_status
        filled.at[row_index, "paper_fill_price"] = fill_price
        filled.at[row_index, "paper_fill_quantity"] = fill_quantity
        filled.at[row_index, "actual_notional_usd"] = actual_notional
        filled.at[row_index, "deviation_from_preview_usd"] = deviation_usd
        filled.at[row_index, "deviation_from_preview_pct"] = deviation_pct

        audit_rows.append(
            {
                "session_date": session_date,
                "selected_signal_date": selected_signal_date,
                "canonical_candidate_id": candidate_id,
                "candidate_role": candidate_role,
                "asset": asset,
                "target_weight": target_weight,
                "target_notional_usd": target_notional,
                "paper_fill_price": fill_price,
                "paper_fill_price_date": price_date,
                "paper_fill_price_source": str(source_path),
                "paper_fill_quantity": fill_quantity,
                "actual_notional_usd": actual_notional,
                "manual_execution_status": execution_status,
            }
        )

    for candidate_id, group in filled.groupby("canonical_candidate_id"):
        total_weight = float(pd.to_numeric(group["target_weight"]).sum())
        if total_weight > 1.0 + 1e-9:
            raise EnteredSessionFillError(
                f"target weights exceed 1.0 for {candidate_id}: {total_weight}"
            )
        actual_entered = pd.to_numeric(
            group.loc[group["manual_execution_status"] == "entered", "actual_notional_usd"]
        ).sum()
        if float(actual_entered) > paper_account_value + 0.01:
            raise EnteredSessionFillError(
                f"entered notional exceeds paper account for {candidate_id}"
            )

    return filled, pd.DataFrame(audit_rows)


def fill_regime_informed_entered_session(
    *,
    root: Path,
    tracking_dir: Path | None = None,
    paper_account_value: float = 10_000.0,
    force: bool = False,
    session_date: str | None = None,
) -> tuple[Path, pd.DataFrame, pd.DataFrame]:
    root = Path(root).resolve()
    tracking_dir = (
        root / TRACKING_RELATIVE_DIR if tracking_dir is None else Path(tracking_dir).resolve()
    )
    template_path = tracking_dir / TEMPLATE_FILENAME
    targets_path = tracking_dir / TARGETS_FILENAME
    output_path = tracking_dir / FILLED_FILENAME

    if output_path.exists() and not force:
        rollover_status_path = (
            tracking_dir / "regime_informed_session_rollover_status.csv"
        )
        replacement_allowed = False

        if rollover_status_path.exists() and rollover_status_path.is_file():
            try:
                rollover_status = pd.read_csv(rollover_status_path)
            except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
                rollover_status = pd.DataFrame()

            if not rollover_status.empty:
                rollover_row = rollover_status.iloc[0]
                archive_path_text = _text(rollover_row.get("archive_path"))
                archive_path = Path(archive_path_text) if archive_path_text else None

                if archive_path is not None and not archive_path.is_absolute():
                    root_relative_archive = root / archive_path
                    tracking_relative_archive = tracking_dir / archive_path
                    if root_relative_archive.exists():
                        archive_path = root_relative_archive
                    elif tracking_relative_archive.exists():
                        archive_path = tracking_relative_archive

                archived_and_ingested = (
                    _bool_value(rollover_row.get("filled_already_ingested", False))
                    and _bool_value(rollover_row.get("filled_session_valid", False))
                    and _text(rollover_row.get("rollover_action"))
                    == "valid_already_ingested_session_archived"
                )
                archive_matches_existing = False
                if (
                    archived_and_ingested
                    and archive_path is not None
                    and archive_path.exists()
                    and archive_path.is_file()
                ):
                    try:
                        archive_matches_existing = (
                            archive_path.read_bytes() == output_path.read_bytes()
                        )
                    except OSError:
                        archive_matches_existing = False

                replacement_allowed = archived_and_ingested and archive_matches_existing

        if not replacement_allowed:
            raise FileExistsError(
                f"filled session already exists: {output_path}. "
                "Archive/roll it over first or rerun with --force."
            )

    template = _read_required_csv(template_path, REQUIRED_TEMPLATE_COLUMNS)
    targets = _read_required_csv(targets_path, REQUIRED_TARGET_COLUMNS)
    effective_session_date = session_date or datetime.now(timezone.utc).date().isoformat()
    try:
        effective_session_date = pd.Timestamp(effective_session_date).date().isoformat()
    except ValueError as exc:
        raise EnteredSessionFillError(
            f"invalid session date: {effective_session_date}"
        ) from exc

    filled, audit = build_entered_session(
        template=template,
        targets=targets,
        paper_account_value=paper_account_value,
        session_date=effective_session_date,
        price_loader=lambda symbol, as_of: load_latest_local_price(root, symbol, as_of),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filled.to_csv(output_path, index=False)
    return output_path, filled, audit


def _print_summary(output_path: Path, filled: pd.DataFrame, audit: pd.DataFrame) -> None:
    print(f"Wrote filled regime-informed paper session: {output_path}")
    print(f"Session date: {filled['session_date'].iloc[0]}")
    print(f"Selected signal date: {filled['selected_signal_date'].iloc[0]}")
    print("\nFilled rows:")
    display_columns = [
        "canonical_candidate_id",
        "asset",
        "target_weight",
        "paper_fill_price",
        "paper_fill_quantity",
        "actual_notional_usd",
        "manual_execution_status",
    ]
    print(audit[display_columns].to_string(index=False))

    print("\nCandidate totals:")
    totals = []
    for candidate_id, group in audit.groupby("canonical_candidate_id"):
        entered = group.loc[group["manual_execution_status"] == "entered"]
        entered_notional = float(entered["actual_notional_usd"].sum())
        paper_account = float(
            filled.loc[
                filled["canonical_candidate_id"] == candidate_id,
                "paper_account_value",
            ].iloc[0]
        )
        totals.append(
            {
                "canonical_candidate_id": candidate_id,
                "entered_notional_usd": round(entered_notional, 2),
                "cash_residual_usd": round(paper_account - entered_notional, 2),
            }
        )
    print(pd.DataFrame(totals).to_string(index=False))
    print("\nSafety: manual paper only; no live trading, real money, broker/API, or promotion.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fill the first entered regime-informed manual paper session."
    )
    parser.add_argument("--root", default=".", help="Project repository root.")
    parser.add_argument(
        "--tracking-dir",
        default=None,
        help="Override regime-informed tracking directory.",
    )
    parser.add_argument(
        "--paper-account-value",
        type=float,
        default=10_000.0,
        help="Independent notional paper account value per candidate.",
    )
    parser.add_argument(
        "--session-date",
        default=None,
        help="Override UTC session date (YYYY-MM-DD); defaults to today.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing filled session file.",
    )
    args = parser.parse_args(argv)

    output_path, filled, audit = fill_regime_informed_entered_session(
        root=Path(args.root),
        tracking_dir=Path(args.tracking_dir) if args.tracking_dir else None,
        paper_account_value=args.paper_account_value,
        force=args.force,
        session_date=args.session_date,
    )
    _print_summary(output_path, filled, audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
