from __future__ import annotations

from market_strats.analysis.regime_informed_portfolio_dashboard import (
    build_regime_informed_portfolio_dashboard,
)


def main() -> None:
    outputs = build_regime_informed_portfolio_dashboard()
    print(f"Wrote notebook: {outputs['notebook']}")
    print(f"Wrote performance dir: {outputs['performance_dir']}")
    print(f"Wrote visuals dir: {outputs['visuals_dir']}")
    for key, path in outputs.items():
        if key.startswith("csv_") or key.startswith("chart_"):
            print(f"Wrote {key}: {path}")


if __name__ == "__main__":
    main()
