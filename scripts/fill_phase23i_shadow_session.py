from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_SHADOW_DIR = Path("reports/individual_equity_shadow/phase23i_prospective_shadow")


def _bool_false_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in [
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
    ]:
        frame[column] = False
    return frame


def build_filled_shadow_session(
    *,
    shadow_dir: Path,
    output_file: str,
    confirm_simulated_fill: bool,
) -> Path:
    template_path = shadow_dir / "current_manual_session_template.csv"
    if not template_path.exists():
        raise FileNotFoundError(f"Missing shadow template: {template_path}")
    template = pd.read_csv(template_path)
    filled = template.copy()
    if filled.empty:
        raise ValueError("Current shadow session template is empty.")
    if confirm_simulated_fill:
        if "paper_order_allowed" in filled.columns and not filled[
            "paper_order_allowed"
        ].astype(bool).all():
            raise ValueError(
                "Cannot mark blocked Phase23I shadow orders as entered. "
                "Review current_proposed_order_plan.csv first."
            )
        filled["manual_decision"] = "enter_simulated_shadow_trade"
        filled["session_state"] = "entered"
        filled["simulated_fill_price"] = 1.0
        filled["simulated_fill_quantity"] = (
            pd.to_numeric(filled["target_notional"], errors="coerce").fillna(0.0)
        )
        filled["override_reason"] = "explicit_user_simulated_shadow_fill_command"
        filled["notes"] = (
            "SIMULATED PAPER SHADOW FILL ONLY - no broker, no live trading, "
            "no real money"
        )
    else:
        filled["manual_decision"] = "skip_user_choice"
        filled["session_state"] = "skipped"
        filled["override_reason"] = "explicit_user_skip_shadow_session_command"
        filled["notes"] = "Skipped by explicit helper command."
    filled = _bool_false_columns(filled)
    output_path = shadow_dir / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filled.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fill the Phase23I individual-equity shadow session template. "
            "This writes a research-only CSV and never places orders."
        )
    )
    parser.add_argument("--shadow-dir", default=str(DEFAULT_SHADOW_DIR))
    parser.add_argument("--output-file", default="shadow_manual_session_filled.csv")
    parser.add_argument(
        "--confirm-simulated-fill",
        action="store_true",
        help=(
            "Mark rows as simulated entered fills using placeholder local-only "
            "fill values. This is not broker execution."
        ),
    )
    args = parser.parse_args()
    output_path = build_filled_shadow_session(
        shadow_dir=Path(args.shadow_dir),
        output_file=args.output_file,
        confirm_simulated_fill=bool(args.confirm_simulated_fill),
    )
    print(f"Wrote research-only Phase23I shadow filled session: {output_path}")


if __name__ == "__main__":
    main()
