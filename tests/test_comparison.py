import pandas as pd

from market_strats.analysis.comparison import (
    create_strategy_scorecard,
    create_strategy_verdicts,
    minmax_score,
)


def test_minmax_score_higher_is_better():
    scores = minmax_score(pd.Series([10, 20, 30]), higher_is_better=True)

    assert scores.iloc[0] == 0.0
    assert scores.iloc[1] == 50.0
    assert scores.iloc[2] == 100.0


def test_minmax_score_lower_is_better():
    scores = minmax_score(pd.Series([10, 20, 30]), higher_is_better=False)

    assert scores.iloc[0] == 100.0
    assert scores.iloc[1] == 50.0
    assert scores.iloc[2] == 0.0


def test_create_strategy_scorecard_ranks_high_quality_strategy_first():
    full_period_metrics = pd.DataFrame(
        {
            "strategy": ["Weak", "Strong"],
            "end_value": [10000, 20000],
            "cagr_pct": [2.0, 10.0],
            "max_drawdown_pct": [-50.0, -20.0],
            "sharpe": [0.2, 1.0],
            "sortino": [0.3, 1.2],
            "trade_count": [100, 10],
        }
    )

    rolling_summary = pd.DataFrame(
        {
            "window_years": [3, 3, 5, 5],
            "strategy": ["Weak", "Strong", "Weak", "Strong"],
            "avg_cagr_pct": [1.0, 9.0, 1.5, 8.0],
            "worst_cagr_pct": [-20.0, -5.0, -15.0, -3.0],
            "avg_max_drawdown_pct": [-30.0, -10.0, -35.0, -12.0],
            "positive_windows_pct": [50.0, 95.0, 60.0, 97.0],
        }
    )

    scorecard = create_strategy_scorecard(full_period_metrics, rolling_summary)

    assert scorecard.iloc[0]["strategy"] == "Strong"
    assert scorecard.iloc[0]["composite_rank"] == 1


def test_create_strategy_verdicts_adds_verdict_column():
    scorecard = pd.DataFrame(
        {
            "strategy": ["Buy and Hold"],
            "composite_score": [80.0],
        }
    )

    result = create_strategy_verdicts(scorecard)

    assert "verdict" in result.columns
    assert "raw compounding" in result["verdict"].iloc[0]