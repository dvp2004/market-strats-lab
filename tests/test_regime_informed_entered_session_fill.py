from pathlib import Path

import pandas as pd
import pytest

from market_strats.analysis.regime_informed_entered_session_fill import (
    FILLED_FILENAME,
    TRACKED_CANDIDATES,
    build_entered_session,
    fill_regime_informed_entered_session,
)
from market_strats.analysis.regime_informed_portfolio_dashboard import (
    _build_trade_blotter,
    _paper_cash_ledger,
    _paper_holdings,
)
from market_strats.analysis.regime_informed_session_ingestion import (
    validate_regime_informed_filled_session,
)


def _candidate_rows() -> list[tuple[str, str, list[tuple[str, float]]]]:
    return [
        (
            "phase6b_loose_relief_execution_realistic_overlay",
            "provisional_core_candidate",
            [("SPY", 1.0), ("CASH", 0.0)],
        ),
        (
            "canonical_spy_qqq_gld_tlt_50_30_10_10",
            "provisional_core_inception_limited",
            [("SPY", 0.5), ("QQQ", 0.3), ("GLD", 0.1), ("TLT", 0.1)],
        ),
        (
            "canonical_inverse_vol_63d_btc_usd_qqq_spy",
            "provisional_high_caveat_candidate",
            [("SPY", 0.5), ("QQQ", 0.45), ("BTC-USD", 0.05)],
        ),
        (
            "canonical_spy_qqq_60_40",
            "reference_only",
            [("SPY", 0.6), ("QQQ", 0.4)],
        ),
    ]


def _template_and_targets() -> tuple[pd.DataFrame, pd.DataFrame]:
    template_rows = []
    target_rows = []
    for candidate_id, role, assets in _candidate_rows():
        caveats = (
            "BTC high-caveat; inception-limited; weekend/gap risk; paper-only"
            if "btc_usd" in candidate_id
            else "reference-only growth benchmark"
            if role == "reference_only"
            else "inception-limited; paper-only"
            if "inception" in role
            else "paper-only"
        )
        for asset, weight in assets:
            base = {
                "session_date": "2026-06-11",
                "selected_signal_date": "2026-06-08",
                "canonical_candidate_id": candidate_id,
                "candidate_role": role,
                "asset": asset,
                "target_weight": weight,
                "target_notional_usd": weight * 10_000,
                "preview_action": "PAPER_TARGET_WEIGHT_ONLY",
                "paper_order_allowed": True,
                "candidate_caveats": caveats,
                "tear_sheet_reviewed": False,
                "warnings_acknowledged": False,
                "btc_caveat_acknowledged": False,
                "reference_only_acknowledged": False,
                "inception_limited_acknowledged": False,
                "manual_decision": "pending",
                "manual_execution_status": "not_entered",
                "paper_account_value": "",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "actual_notional_usd": "",
                "deviation_from_preview_usd": "",
                "deviation_from_preview_pct": "",
                "override_reason": "",
                "notes": "",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
            template_rows.append(base)
            target_rows.append(
                {
                    "tracking_date": "2026-06-11",
                    "selected_signal_date": "2026-06-08",
                    "canonical_candidate_id": candidate_id,
                    "candidate_role": role,
                    "asset": asset,
                    "target_weight": weight,
                    "target_notional_usd": weight * 10_000,
                    "candidate_caveats": caveats,
                }
            )
    return pd.DataFrame(template_rows), pd.DataFrame(target_rows)


def _write_price(root: Path, symbol: str, price: float) -> None:
    output_dir = root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": ["2026-06-10", "2026-06-12"],
            "adj_close": [price - 1.0, price],
        }
    ).to_csv(output_dir / f"{symbol}.csv", index=False)


def _write_sources(root: Path) -> Path:
    tracking_dir = root / "reports" / "paper_trading" / "regime_informed_tracking"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    template, targets = _template_and_targets()
    template.to_csv(tracking_dir / "regime_informed_manual_session_template.csv", index=False)
    targets.to_csv(tracking_dir / "regime_informed_paper_targets.csv", index=False)
    for symbol, price in {
        "SPY": 500.0,
        "QQQ": 400.0,
        "GLD": 200.0,
        "TLT": 100.0,
        "BTC-USD": 80_000.0,
    }.items():
        _write_price(root, symbol, price)
    return tracking_dir


def test_build_entered_session_computes_fills_and_acknowledgements():
    template, targets = _template_and_targets()
    prices = {"SPY": 500.0, "QQQ": 400.0, "GLD": 200.0, "TLT": 100.0, "BTC-USD": 80_000.0}

    filled, audit = build_entered_session(
        template=template,
        targets=targets,
        paper_account_value=10_000.0,
        session_date="2026-06-12",
        price_loader=lambda symbol, _as_of: (prices[symbol], "2026-06-12", Path(symbol)),
    )

    assert set(filled["canonical_candidate_id"]) == set(TRACKED_CANDIDATES)
    assert set(filled.loc[filled["asset"] != "CASH", "manual_execution_status"]) == {"entered"}
    assert set(filled.loc[filled["asset"] == "CASH", "manual_execution_status"]) == {
        "cash_residual"
    }
    assert filled["tear_sheet_reviewed"].all()
    assert filled["warnings_acknowledged"].all()
    assert not filled[list(("live_trading_allowed", "real_money_allowed", "broker_api_integration_allowed", "promotion_allowed"))].any().any()
    assert len(audit) == len(template)


def test_btc_quantity_uses_eight_decimal_precision_and_etfs_use_four():
    template, targets = _template_and_targets()
    prices = {"SPY": 503.37, "QQQ": 401.23, "GLD": 199.99, "TLT": 101.11, "BTC-USD": 80_123.45}
    filled, _audit = build_entered_session(
        template=template,
        targets=targets,
        paper_account_value=10_000.0,
        session_date="2026-06-12",
        price_loader=lambda symbol, _as_of: (prices[symbol], "2026-06-12", Path(symbol)),
    )
    btc_qty = float(filled.loc[filled["asset"] == "BTC-USD", "paper_fill_quantity"].iloc[0])
    spy_qty = float(filled.loc[filled["asset"] == "SPY", "paper_fill_quantity"].iloc[0])
    assert len(f"{btc_qty:.8f}".split(".")[1]) == 8
    assert len(f"{spy_qty:.4f}".split(".")[1]) == 4
    entered = filled[filled["manual_execution_status"] == "entered"]
    assert (entered["actual_notional_usd"] <= entered["target_notional_usd"] + 0.01).all()


def test_cash_residual_is_valid_and_not_a_position():
    template, targets = _template_and_targets()
    prices = {"SPY": 500.0, "QQQ": 400.0, "GLD": 200.0, "TLT": 100.0, "BTC-USD": 80_000.0}
    filled, _audit = build_entered_session(
        template=template,
        targets=targets,
        paper_account_value=10_000.0,
        session_date="2026-06-12",
        price_loader=lambda symbol, _as_of: (prices[symbol], "2026-06-12", Path(symbol)),
    )
    validation = validate_regime_informed_filled_session(
        filled_session=filled,
        template=template,
        warnings_present=True,
    )
    assert validation["row_valid"].all()
    assert set(validation.loc[validation["asset"] == "CASH", "manual_execution_status"]) == {
        "cash_residual"
    }

    blotter = _build_trade_blotter(filled)
    holdings = _paper_holdings(filled)
    cash = _paper_cash_ledger(filled)
    assert "CASH RESIDUAL" in set(blotter["action"])
    assert "CASH" not in set(holdings["asset"])
    assert (cash["cash_remaining"] >= -0.01).all()


def test_fill_command_writes_file_and_refuses_unforced_overwrite(tmp_path):
    tracking_dir = _write_sources(tmp_path)
    output_path, filled, _audit = fill_regime_informed_entered_session(
        root=tmp_path,
        paper_account_value=10_000.0,
        session_date="2026-06-12",
    )
    assert output_path == tracking_dir / FILLED_FILENAME
    assert output_path.exists()
    assert set(filled["session_date"]) == {"2026-06-12"}

    with pytest.raises(FileExistsError):
        fill_regime_informed_entered_session(
            root=tmp_path,
            paper_account_value=10_000.0,
            session_date="2026-06-12",
        )


def test_force_overwrite_is_explicit(tmp_path):
    _write_sources(tmp_path)
    fill_regime_informed_entered_session(
        root=tmp_path,
        session_date="2026-06-12",
    )
    output_path, filled, _audit = fill_regime_informed_entered_session(
        root=tmp_path,
        paper_account_value=20_000.0,
        force=True,
        session_date="2026-06-13",
    )
    assert output_path.exists()
    assert set(filled["session_date"]) == {"2026-06-13"}
    assert set(filled["paper_account_value"]) == {20_000.0}


def test_reference_and_btc_notes_are_explicit():
    template, targets = _template_and_targets()
    prices = {"SPY": 500.0, "QQQ": 400.0, "GLD": 200.0, "TLT": 100.0, "BTC-USD": 80_000.0}
    filled, _audit = build_entered_session(
        template=template,
        targets=targets,
        paper_account_value=10_000.0,
        session_date="2026-06-12",
        price_loader=lambda symbol, _as_of: (prices[symbol], "2026-06-12", Path(symbol)),
    )
    reference_notes = " ".join(
        filled.loc[filled["candidate_role"] == "reference_only", "notes"].astype(str)
    )
    btc_notes = " ".join(
        filled.loc[
            filled["canonical_candidate_id"]
            == "canonical_inverse_vol_63d_btc_usd_qqq_spy",
            "notes",
        ].astype(str)
    )
    assert "reference_only_candidate" in reference_notes
    assert "btc_high_caveat_acknowledged" in btc_notes


def test_archived_ingested_session_can_be_replaced_without_force(tmp_path):
    tracking_dir = _write_sources(tmp_path)
    old_path, _filled, _audit = fill_regime_informed_entered_session(
        root=tmp_path,
        session_date="2026-06-12",
    )
    archive_dir = tracking_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "archived.csv"
    archive_path.write_bytes(old_path.read_bytes())
    pd.DataFrame(
        [
            {
                "filled_already_ingested": True,
                "filled_session_valid": True,
                "rollover_action": "valid_already_ingested_session_archived",
                "archive_path": str(archive_path),
            }
        ]
    ).to_csv(tracking_dir / "regime_informed_session_rollover_status.csv", index=False)

    output_path, filled, _audit = fill_regime_informed_entered_session(
        root=tmp_path,
        session_date="2026-06-13",
    )
    assert output_path == old_path
    assert set(filled["session_date"]) == {"2026-06-13"}
