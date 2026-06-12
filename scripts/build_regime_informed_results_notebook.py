from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK = ROOT / "notebooks" / "regime_informed_results_dashboard.ipynb"
DEFAULT_VISUALS_DIR = (
    ROOT / "reports" / "paper_trading" / "regime_informed_tracking" / "visuals"
)

DATA_SOURCES = {
    "candidate_summary": Path(
        "reports/strategy_factory/regime_stress/phase21a_candidate_regime_summary.csv"
    ),
    "robustness_scores": Path(
        "reports/strategy_factory/regime_stress/phase21a_regime_robustness_scores.csv"
    ),
    "score_components": Path(
        "reports/strategy_factory/regime_stress/"
        "phase21a_regime_robustness_score_components.csv"
    ),
    "regime_metrics": Path(
        "reports/strategy_factory/regime_stress/phase21a_regime_metrics.csv"
    ),
    "shortlist": Path(
        "reports/strategy_factory/regime_reconciliation/"
        "phase21b_paper_shortlist_recommendation.csv"
    ),
    "targets": Path(
        "reports/paper_trading/regime_informed_tracking/"
        "regime_informed_paper_targets.csv"
    ),
    "tear_sheet": Path(
        "reports/paper_trading/regime_informed_tracking/"
        "regime_informed_daily_tracking_tear_sheet.csv"
    ),
    "discipline": Path(
        "reports/paper_trading/regime_informed_tracking/"
        "regime_informed_session_discipline_summary.csv"
    ),
    "ledger": Path(
        "reports/paper_trading/regime_informed_tracking/"
        "regime_informed_manual_session_ledger.csv"
    ),
    "session_ingestion_status": Path(
        "reports/paper_trading/dashboard/"
        "regime_informed_session_ingestion_status.csv"
    ),
    "daily_runtime": Path("reports/paper_trading/dashboard/daily_paper_runtime_status.csv"),
}

EXPECTED_PNGS = {
    "robustness": "robustness_scores.png",
    "drawdowns": "worst_drawdowns.png",
    "scatter": "return_vs_drawdown.png",
    "return_heatmap": "regime_return_heatmap.png",
    "drawdown_heatmap": "regime_drawdown_heatmap.png",
    "allocations": "current_allocations.png",
    "ledger": "ledger_decisions.png",
    "runtime": "daily_runtime.png",
}

SECTION_HEADINGS = [
    "Project Status",
    "Current Regime-Informed Shortlist",
    "Why SPY/QQQ 60/40 Was Downgraded",
    "Phase6 vs Multi-Asset vs BTC Candidates",
    "Regime Robustness Scores",
    "Worst Drawdown Comparison",
    "Regime Return Heatmap",
    "Regime Drawdown Heatmap",
    "Current Target Allocations",
    "Paper Discipline / Ledger Status",
    "Daily Runtime Status",
    "Next Action Checklist",
]


def _read_csv(root: Path, relative_path: Path) -> pd.DataFrame:
    path = root / relative_path
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _short_label(value: object, max_len: int = 42) -> str:
    text = str(value)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _placeholder_chart(path: Path, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _save_bar_chart(
    frame: pd.DataFrame,
    *,
    label_col: str,
    value_col: str,
    output_path: Path,
    title: str,
    ylabel: str,
) -> None:
    if frame.empty or label_col not in frame.columns or value_col not in frame.columns:
        _placeholder_chart(output_path, title, f"Missing {label_col}/{value_col} data")
        return
    plot_frame = frame[[label_col, value_col]].copy()
    plot_frame[value_col] = _as_numeric(plot_frame[value_col])
    plot_frame = plot_frame.dropna(subset=[value_col]).head(12)
    if plot_frame.empty:
        _placeholder_chart(output_path, title, f"No numeric {value_col} values available")
        return
    labels = [_short_label(value) for value in plot_frame[label_col]]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(labels, plot_frame[value_col])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _save_scatter(
    frame: pd.DataFrame,
    *,
    output_path: Path,
) -> None:
    title = "Mean Return vs Worst Drawdown"
    required = {"canonical_candidate_id", "mean_total_return_pct", "worst_max_drawdown_pct"}
    if frame.empty or not required.issubset(frame.columns):
        _placeholder_chart(output_path, title, "Missing candidate return/drawdown data")
        return
    plot_frame = frame[list(required)].copy()
    plot_frame["mean_total_return_pct"] = _as_numeric(plot_frame["mean_total_return_pct"])
    plot_frame["worst_max_drawdown_pct"] = _as_numeric(
        plot_frame["worst_max_drawdown_pct"]
    )
    plot_frame = plot_frame.dropna(
        subset=["mean_total_return_pct", "worst_max_drawdown_pct"]
    )
    if plot_frame.empty:
        _placeholder_chart(output_path, title, "No numeric return/drawdown values available")
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(
        plot_frame["worst_max_drawdown_pct"],
        plot_frame["mean_total_return_pct"],
        s=55,
    )
    for row in plot_frame.itertuples(index=False):
        ax.annotate(
            _short_label(row.canonical_candidate_id, 24),
            (row.worst_max_drawdown_pct, row.mean_total_return_pct),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_title(title)
    ax.set_xlabel("Worst max drawdown (%)")
    ax.set_ylabel("Mean total return (%)")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _save_heatmap(
    frame: pd.DataFrame,
    *,
    value_col: str,
    output_path: Path,
    title: str,
) -> None:
    required = {"canonical_candidate_id", "regime_name", value_col}
    if frame.empty or not required.issubset(frame.columns):
        _placeholder_chart(output_path, title, f"Missing regime {value_col} data")
        return
    plot_frame = frame.loc[frame.get("regime_available", True).astype(bool)].copy()
    plot_frame[value_col] = _as_numeric(plot_frame[value_col])
    pivot = plot_frame.pivot_table(
        index="canonical_candidate_id",
        columns="regime_name",
        values=value_col,
        aggfunc="mean",
    )
    pivot = pivot.dropna(how="all").head(12)
    if pivot.empty:
        _placeholder_chart(output_path, title, f"No numeric {value_col} values available")
        return
    fig_width = max(10, len(pivot.columns) * 1.2)
    fig_height = max(5, len(pivot.index) * 0.45)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(pivot.fillna(0.0), aspect="auto")
    ax.set_title(title)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([_short_label(col, 18) for col in pivot.columns], rotation=45)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([_short_label(index, 38) for index in pivot.index])
    fig.colorbar(image, ax=ax, label=value_col)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _save_allocation_chart(frame: pd.DataFrame, output_path: Path) -> None:
    title = "Current Target Allocations"
    required = {"canonical_candidate_id", "asset", "target_weight"}
    if frame.empty or not required.issubset(frame.columns):
        _placeholder_chart(output_path, title, "Missing current target allocation data")
        return
    plot_frame = frame[list(required)].copy()
    plot_frame["target_weight"] = _as_numeric(plot_frame["target_weight"])
    pivot = plot_frame.pivot_table(
        index="canonical_candidate_id",
        columns="asset",
        values="target_weight",
        aggfunc="sum",
    ).fillna(0.0)
    if pivot.empty:
        _placeholder_chart(output_path, title, "No target weights available")
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bottom = pd.Series(0.0, index=pivot.index)
    x_labels = [_short_label(index, 38) for index in pivot.index]
    for asset in pivot.columns:
        ax.bar(x_labels, pivot[asset], bottom=bottom, label=asset)
        bottom = bottom + pivot[asset]
    ax.set_title(title)
    ax.set_ylabel("Target weight")
    ax.tick_params(axis="x", labelrotation=45)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _save_ledger_chart(frame: pd.DataFrame, output_path: Path) -> None:
    title = "Manual Ledger Decision Counts"
    if frame.empty or "manual_decision" not in frame.columns:
        _placeholder_chart(output_path, title, "Missing manual paper ledger data")
        return
    counts = frame["manual_decision"].fillna("missing").astype(str).value_counts()
    if counts.empty:
        _placeholder_chart(output_path, title, "No manual decisions recorded")
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(counts.index, counts.values)
    ax.set_title(title)
    ax.set_ylabel("Rows")
    ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _save_runtime_chart(frame: pd.DataFrame, output_path: Path) -> None:
    title = "Daily Paper Runtime"
    if frame.empty or "runtime_seconds" not in frame.columns:
        _placeholder_chart(output_path, title, "Daily runtime status has not been written")
        return
    value = pd.to_numeric(frame.iloc[0].get("runtime_seconds"), errors="coerce")
    if pd.isna(value):
        _placeholder_chart(output_path, title, "Runtime seconds is not numeric")
        return
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.bar(["daily-paper-only"], [float(value)])
    ax.set_title(title)
    ax.set_ylabel("Runtime seconds")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _generate_visuals(root: Path, visuals_dir: Path) -> dict[str, Path]:
    data = {name: _read_csv(root, path) for name, path in DATA_SOURCES.items()}
    visuals_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: visuals_dir / filename for name, filename in EXPECTED_PNGS.items()}

    robustness = data["robustness_scores"].sort_values(
        "regime_robustness_score", ascending=False
    ) if "regime_robustness_score" in data["robustness_scores"].columns else data[
        "robustness_scores"
    ]
    _save_bar_chart(
        robustness,
        label_col="canonical_candidate_id",
        value_col="regime_robustness_score",
        output_path=paths["robustness"],
        title="Regime Robustness Scores",
        ylabel="Score",
    )
    _save_bar_chart(
        data["candidate_summary"].sort_values("worst_max_drawdown_pct")
        if "worst_max_drawdown_pct" in data["candidate_summary"].columns
        else data["candidate_summary"],
        label_col="canonical_candidate_id",
        value_col="worst_max_drawdown_pct",
        output_path=paths["drawdowns"],
        title="Worst Drawdown by Candidate",
        ylabel="Worst drawdown (%)",
    )
    _save_scatter(data["candidate_summary"], output_path=paths["scatter"])
    _save_heatmap(
        data["regime_metrics"],
        value_col="total_return_pct",
        output_path=paths["return_heatmap"],
        title="Regime Total Return Heatmap",
    )
    _save_heatmap(
        data["regime_metrics"],
        value_col="max_drawdown_pct",
        output_path=paths["drawdown_heatmap"],
        title="Regime Drawdown Heatmap",
    )
    _save_allocation_chart(data["targets"], paths["allocations"])
    _save_ledger_chart(data["ledger"], paths["ledger"])
    _save_runtime_chart(data["daily_runtime"], paths["runtime"])
    return paths


def _markdown_cell(source: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def _code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(True),
    }


def _image_markdown(root: Path, image_path: Path) -> str:
    notebook_dir = root / "notebooks"
    try:
        rel = image_path.relative_to(notebook_dir)
    except ValueError:
        try:
            rel = Path("..") / image_path.relative_to(root)
        except ValueError:
            rel = image_path
    if not image_path.exists():
        return f"**Missing image:** `{rel.as_posix()}`"
    return f"![{image_path.stem}]({rel.as_posix()})"


def _notebook_json(root: Path, visuals: dict[str, Path]) -> dict[str, Any]:
    cells = [
        _markdown_cell(
            "# Regime-Informed Results Dashboard\n\n"
            "NO LIVE TRADING\n\n"
            "NO REAL MONEY\n\n"
            "NO BROKER/API\n\n"
            "NO STRATEGY PROMOTION\n\n"
            "This notebook reads local CSV reports only and summarizes research "
            "selection, regime reconciliation, and shortlist context. The separate "
            "regime_informed_portfolio_performance_dashboard.ipynb is the "
            "portfolio/performance dashboard.\n\n"
            "If a PNG is missing, the affected section displays `Missing image: ...` "
            "instead of silently rendering a broken image."
        ),
        _code_cell(
            "from pathlib import Path\n"
            "import pandas as pd\n\n"
            "ROOT = Path('..').resolve()\n"
            "DATA = {\n"
            "    'candidate_summary': ROOT / 'reports/strategy_factory/regime_stress/phase21a_candidate_regime_summary.csv',\n"
            "    'robustness_scores': ROOT / 'reports/strategy_factory/regime_stress/phase21a_regime_robustness_scores.csv',\n"
            "    'score_components': ROOT / 'reports/strategy_factory/regime_stress/phase21a_regime_robustness_score_components.csv',\n"
            "    'regime_metrics': ROOT / 'reports/strategy_factory/regime_stress/phase21a_regime_metrics.csv',\n"
            "    'shortlist': ROOT / 'reports/strategy_factory/regime_reconciliation/phase21b_paper_shortlist_recommendation.csv',\n"
            "    'targets': ROOT / 'reports/paper_trading/regime_informed_tracking/regime_informed_paper_targets.csv',\n"
            "    'tear_sheet': ROOT / 'reports/paper_trading/regime_informed_tracking/regime_informed_daily_tracking_tear_sheet.csv',\n"
            "    'discipline': ROOT / 'reports/paper_trading/regime_informed_tracking/regime_informed_session_discipline_summary.csv',\n"
            "    'ledger': ROOT / 'reports/paper_trading/regime_informed_tracking/regime_informed_manual_session_ledger.csv',\n"
            "    'session_ingestion_status': ROOT / 'reports/paper_trading/dashboard/regime_informed_session_ingestion_status.csv',\n"
            "    'daily_runtime': ROOT / 'reports/paper_trading/dashboard/daily_paper_runtime_status.csv',\n"
            "}\n\n"
            "def read_csv(path):\n"
            "    if not path.exists():\n"
            "        return pd.DataFrame({'missing_file': [str(path)]})\n"
            "    return pd.read_csv(path)\n\n"
            "frames = {name: read_csv(path) for name, path in DATA.items()}\n"
            "pd.DataFrame({'source': list(DATA), 'path': [str(path) for path in DATA.values()], 'exists': [path.exists() for path in DATA.values()]})"
        ),
        _markdown_cell("## 1. Project Status"),
        _code_cell(
            "frames['daily_runtime'].head() if not frames['daily_runtime'].empty else 'Daily runtime status missing'"
        ),
        _markdown_cell("## 2. Current Regime-Informed Shortlist"),
        _code_cell(
            "frames['shortlist'].head(10) if not frames['shortlist'].empty else 'Shortlist report missing'"
        ),
        _markdown_cell("## 3. Why SPY/QQQ 60/40 Was Downgraded"),
        _code_cell(
            "summary = frames['candidate_summary']\n"
            "summary[summary.get('canonical_candidate_id', pd.Series(dtype=str)).astype(str).eq('canonical_spy_qqq_60_40')] if not summary.empty else 'Candidate summary missing'"
        ),
        _markdown_cell("## 4. Phase6 vs Multi-Asset vs BTC Candidates"),
        _code_cell(
            "targets = frames['targets']\n"
            "targets[['canonical_candidate_id','candidate_role','asset','target_weight','candidate_caveats']].head(40) if {'canonical_candidate_id','candidate_role','asset','target_weight','candidate_caveats'}.issubset(targets.columns) else targets.head()"
        ),
        _markdown_cell(
            "## 5. Regime Robustness Scores\n\n"
            + _image_markdown(root, visuals["robustness"])
        ),
        _markdown_cell(
            "## 6. Worst Drawdown Comparison\n\n"
            + _image_markdown(root, visuals["drawdowns"])
            + "\n\n"
            + _image_markdown(root, visuals["scatter"])
        ),
        _markdown_cell(
            "## 7. Regime Return Heatmap\n\n"
            + _image_markdown(root, visuals["return_heatmap"])
        ),
        _markdown_cell(
            "## 8. Regime Drawdown Heatmap\n\n"
            + _image_markdown(root, visuals["drawdown_heatmap"])
        ),
        _markdown_cell(
            "## 9. Current Target Allocations\n\n"
            + _image_markdown(root, visuals["allocations"])
        ),
        _markdown_cell("## 10. Paper Discipline / Ledger Status"),
        _code_cell(
            "ledger = frames['ledger']\n"
            "ledger.tail(20) if not ledger.empty else 'Manual session ledger missing or empty'"
        ),
        _markdown_cell(_image_markdown(root, visuals["ledger"])),
        _markdown_cell("## 11. Daily Runtime Status"),
        _code_cell(
            "frames['daily_runtime'].head() if not frames['daily_runtime'].empty else 'Daily runtime report missing'"
        ),
        _markdown_cell(_image_markdown(root, visuals["runtime"])),
        _markdown_cell(
            "## 12. Next Action Checklist\n\n"
            "- Open the latest regime-informed tear sheet.\n"
            "- Confirm data warnings and blocks before paper tracking.\n"
            "- Confirm BTC caveats when BTC target weight is positive.\n"
            "- Use manual paper entries only after review.\n"
            "- Keep Phase18/20/21 safety gates in force.\n"
            "- Do not use live trading, real money, broker/API, or promotion."
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_notebook(
    *,
    root: Path | None = None,
    output_notebook: Path | None = None,
    visuals_dir: Path | None = None,
) -> dict[str, Path]:
    root = ROOT if root is None else Path(root)
    output_notebook = DEFAULT_NOTEBOOK if output_notebook is None else Path(output_notebook)
    visuals_dir = DEFAULT_VISUALS_DIR if visuals_dir is None else Path(visuals_dir)
    if not output_notebook.is_absolute():
        output_notebook = root / output_notebook
    if not visuals_dir.is_absolute():
        visuals_dir = root / visuals_dir
    output_notebook.parent.mkdir(parents=True, exist_ok=True)
    visuals = _generate_visuals(root, visuals_dir)
    notebook = _notebook_json(root, visuals)
    output_notebook.write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")
    return {"notebook": output_notebook, **visuals}


def main() -> None:
    outputs = build_notebook()
    print(f"Wrote notebook: {outputs['notebook']}")
    for name, path in outputs.items():
        if name != "notebook":
            print(f"Wrote {name}: {path}")


if __name__ == "__main__":
    main()
