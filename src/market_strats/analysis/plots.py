from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from market_strats.analysis.metrics import calculate_drawdown


def plot_equity_curves(results: dict[str, pd.DataFrame], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))

    for name, df in results.items():
        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        plt.plot(plot_df["date"], plot_df["equity"], label=name)

    plt.title("Equity Curve Comparison")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_drawdowns(results: dict[str, pd.DataFrame], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))

    for name, df in results.items():
        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        drawdown = calculate_drawdown(plot_df["equity"])
        plt.plot(plot_df["date"], drawdown * 100, label=name)

    plt.title("Drawdown Comparison")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()