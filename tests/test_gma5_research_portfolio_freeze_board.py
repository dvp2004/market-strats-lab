import json
from pathlib import Path
from market_strats.global_multi_asset.gma5_research_portfolio_freeze_board import (
    generate_freeze_board,
)


def test_freeze_board_artifacts_are_deterministic_and_compliant(tmp_path: Path):
    report_root = Path("reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1")

    # Run first time
    generate_freeze_board(report_root)

    csv_path = report_root / "gma5_research_portfolio_freeze_board_v1.csv"
    md_path = report_root / "gma5_research_portfolio_freeze_board_v1.md"
    json_path = report_root / "gma5_research_portfolio_locks_v1.json"

    csv_1 = csv_path.read_bytes()
    md_1 = md_path.read_bytes()
    json_1 = json_path.read_bytes()

    # Run second time
    generate_freeze_board(report_root)

    assert csv_path.read_bytes() == csv_1
    assert md_path.read_bytes() == md_1
    assert json_path.read_bytes() == json_1

    with open(json_path) as f:
        locks = json.load(f)

    frozen = [v for v in locks["variants"] if v["classification"] == "frozen_research_portfolio"]
    assert len(frozen) == 2

    rw = next(
        v for v in locks["variants"] if v["variant_id"] == "gma5_risk_weighted_atomic_sleeves_v1"
    )
    assert rw["classification"] == "archived_from_gma5_v1"

    ridge = next(
        v
        for v in locks["variants"]
        if v["variant_id"] == "gma5_fixed_alpha_ridge_atomic_ensemble_v1"
    )
    assert (
        "cost_sensitive" in " ".join(ridge["known_limitations"])
        or "materially_weaker_severe_cost_cagr" in ridge["known_limitations"]
    )

    for v in locks["variants"]:
        assert "gma5_config_hash" in v
        assert "gma5_source_hash" in v
        assert "composite_target_input_hash" in v
        assert "full_common_oos_period" in v
        assert "learned_only_ridge_window" in v

    for v in locks["variants"]:
        text_to_check = (v["classification"] + " " + v["role"] + " " + " ".join(v.get("known_limitations", []))).lower()
        for word in ["winner", "approved", "candidate", "recommended", "deployable", "live-ready", "promoted"]:
            assert word not in text_to_check


def test_master_report_labels():
    md_path = Path("reports/global_multi_asset_alpha/gma_research_latest_v1.md")
    if not md_path.exists():
        return
    text = md_path.read_text()
    assert "limited_nonconclusive_reproduction_check" in text
    assert "clean_execution_verification_source_of_record" in text
