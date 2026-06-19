# Strategy Research Log — LLM Alpaca Paper Bot

_Last updated: 2026-06-19 14:31:47_

## Current Purpose

This file tracks the separate Alpaca paper-bot strategy experiment inside:

`experiments\llm_alpaca_paper_bot`

The goal is to avoid repeating tests, losing context, or confusing older flawed results with current findings.

Important architecture correction:

- QQQ 1-share paper bot = Execution Harness V0 / Broker Plumbing Test.
- GMA = main multi-asset portfolio strategy research system.
- Do not treat `QQQ_50_200_cross` as the final project direction.
- Do not promote QQQ variants into the main project without GMA-level validation.
- Do not expand the QQQ bot into a separate portfolio system.
- Use Alpaca only as a future execution adapter for approved portfolio targets.

This log is research documentation only. It is not a live-trading approval.

---

## Current Status

- Current implemented execution-harness test signal: `QQQ_50_200_cross`
- Current paper sizing: 1 QQQ share only
- Current execution mode should remain paper-only
- Main harness question now: can the local code safely translate a signal into paper intent, detect open orders, block duplicate orders, and produce logs/reports?
- Main strategy system remains GMA, not the QQQ moving-average experiment.
- API keys were exposed earlier and should be rotated before continued broker/API use.

---

## Main Candidate Table

| category | strategy | source | symbol | rule_type | fast | slow | cagr_pct | sharpe_0rf | max_drawdown_pct | avg_exposure | trade_count | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Benchmark | SPY_buy_hold | ma_parameter_sweep | SPY | buy_hold |  |  | 11.02% | 0.639 | -55.17% | 1 | 1 | Minimum hurdle |
| Benchmark | QQQ_buy_hold | ma_parameter_sweep | QQQ | buy_hold |  |  | 15.87% | 0.781 | -53.40% | 1 | 1 | High-return but high-drawdown benchmark |
| Benchmark | XLK_buy_hold | ma_parameter_sweep | XLK | buy_hold |  |  | 16.43% | 0.779 | -53.03% | 1 | 1 | Sector concentration benchmark |
| Current paper bot | QQQ_50_200_cross | ma_parameter_sweep | QQQ | cross | 50 | 200 | 13.28% | 0.813 | -30.06% | 0.777 | 23 | Implemented 1-share paper candidate |
| Research candidate | QQQ_100_225_cross | ma_parameter_sweep | QQQ | cross | 100 | 225 | 15.25% | 0.893 | -28.56% | 0.793 | 15 | Strongest QQQ cross candidate from MA sweep |
| Research candidate | QQQ_75_300_cross | ma_parameter_sweep | QQQ | cross | 75 | 300 | 15.17% | 0.880 | -28.55% | 0.798 | 9 | Strong slow-trend candidate |
| Research candidate | QQQ_100_250_cross | ma_parameter_sweep | QQQ | cross | 100 | 250 | 14.77% | 0.864 | -28.56% | 0.793 | 11 | Strong nearby QQQ cross candidate |
| Research candidate | QQQ_50_250_cross | ma_parameter_sweep | QQQ | cross | 50 | 250 | 14.21% | 0.848 | -28.55% | 0.792 | 19 | Nearby variant showing cluster support |
| Research candidate | QQQ_40_200_cross | ma_parameter_sweep | QQQ | cross | 40 | 200 | 14.03% | 0.853 | -28.56% | 0.781 | 25 | Nearby variant showing cluster support |
| Conservative candidate | QQQ_above_175_cash | ma_parameter_sweep | QQQ | above_ma |  | 175 | 13.48% | 0.900 | -23.10% | 0.779 | 117 | Lower drawdown above-MA rule |
| Conservative candidate | QQQ_above_200_cash | ma_parameter_sweep | QQQ | above_ma |  | 200 | 12.06% | 0.811 | -25.79% | 0.781 | 119 | Simple price-above-MA rule |
| Conservative candidate | XLK_above_250_cash | ma_parameter_sweep | XLK | above_ma |  | 250 | 14.10% | 0.876 | -28.06% | 0.782 | 73 | Strong XLK above-MA candidate |
| Parked | core_inverse_vol_60d | corrected_event_replay |  |  |  |  | 10.37% | 0.969 | -24.26% | 0.971 | 1128 | Good risk metrics but too much turnover |

---

## What We Tested

### 1. Initial Historical Backtest

File: `paper_bot_logs\historical_strategy_backtest_summary.csv`  
Status: `present`

Purpose:
- Quick first-pass test on simple ETF strategies.
- Included SPY buy-and-hold, equal-weight 5 ETF, crude risk-switch, monthly momentum, and SPY pullback logic.

Result:
- Most first-pass strategies failed to beat SPY convincingly.
- This batch was useful mainly for rejecting weak simple ideas.

Top rows:

| strategy | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_buy_hold | 15.30% | 0.936 | -25.38% | 16.70% | 1 |  |
| equal_weight_5ETF | 10.53% | 0.809 | -26.31% | 13.50% | 1 |  |
| spy_200dma_risk_switch | 5.67% | 0.464 | -37.91% | 14.01% | 1 |  |
| monthly_top2_60d_momentum | 4.22% | 0.345 | -30.97% | 15.48% | 1 |  |
| spy_trend_pullback | 1.11% | 0.320 | -5.20% | 3.64% | 0.046 |  |

---

### 2. Strategy Tournament

File: `paper_bot_logs\strategy_tournament_summary.csv`  
Status: `present`

Purpose:
- Expanded the first tests to include QQQ, trend filters, momentum variants, and defensive rules.

Result:
- QQQ trend filters started showing promise.
- Early results were not enough because the initial Alpaca-data window was too short.

Top rows:

| strategy | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| QQQ_buy_hold | 19.45% | 0.899 | -35.63% | 22.61% | 0.999 |  |
| QQQ_above_200_else_cash | 15.55% | 1.087 | -19.76% | 14.23% | 0.655 |  |
| SPY_buy_hold | 15.30% | 0.936 | -25.38% | 16.70% | 0.999 |  |
| QQQ_50_200_cross | 14.88% | 0.948 | -22.84% | 15.96% | 0.658 |  |
| monthly_top1_126d_vol15 | 12.08% | 0.848 | -18.56% | 14.74% | 0.706 |  |
| defensive_top1_63d_mom | 11.52% | 0.644 | -34.44% | 20.06% | 0.999 |  |
| equal_weight_5ETF | 10.52% | 0.808 | -26.31% | 13.51% | 0.999 |  |
| monthly_top1_63d_mom | 10.33% | 0.578 | -37.02% | 20.74% | 0.999 |  |
| defensive_top1_126d_mom | 9.79% | 0.583 | -32.06% | 19.22% | 0.999 |  |
| monthly_inverse_vol_60d | 9.73% | 0.840 | -24.91% | 11.90% | 0.953 |  |

---

### 3. Robust Adjusted-Data Tournament

File: `paper_bot_logs\robust_strategy_tournament_full_summary.csv`  
Status: `present`

Purpose:
- Longer adjusted-price test from 2006 onward.
- Included QQQ, SPY, GLD, TLT, IWM, XLK, and sector ETFs.

Result:
- QQQ/XLK buy-and-hold had strong CAGR but drawdowns around the -53% zone.
- QQQ trend-following survived as a serious candidate.
- This led to event-style replay testing.

Top rows:

| strategy | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| XLK_buy_hold | 16.49% | 0.781 | -53.04% | 22.91% | 1 |  |
| QQQ_buy_hold | 15.93% | 0.784 | -53.40% | 21.94% | 1 |  |
| QQQ_200_or_GLD | 15.15% | 0.836 | -39.10% | 19.07% | 1 |  |
| QQQ_50_200_cross | 13.71% | 0.834 | -28.56% | 17.17% | 0.777 |  |
| QQQ_above_150_cash | 13.67% | 0.929 | -26.49% | 15.03% | 0.777 |  |
| QQQ_200_or_TLT_GLD | 13.33% | 0.818 | -35.79% | 17.09% | 1 |  |
| XLK_50_200_cross | 13.19% | 0.791 | -31.15% | 17.64% | 0.765 |  |
| XLK_above_200_cash | 12.42% | 0.818 | -25.37% | 15.86% | 0.774 |  |
| QQQ_above_200_cash | 12.20% | 0.830 | -26.72% | 15.27% | 0.781 |  |
| sector_top1_252d_positive | 12.13% | 0.620 | -38.49% | 22.57% | 1 |  |
| XLK_above_150_cash | 11.45% | 0.775 | -31.44% | 15.54% | 0.770 |  |
| QQQ_200_or_TLT | 11.05% | 0.684 | -44.03% | 17.59% | 1 |  |
| SPY_buy_hold | 11.04% | 0.640 | -55.19% | 19.28% | 1 |  |
| core_inverse_vol_60d | 11.03% | 0.990 | -24.21% | 11.20% | 0.988 |  |
| core_inverse_vol_120d | 10.83% | 0.972 | -24.08% | 11.23% | 0.976 |  |

---

### 4. Corrected Event-Style Replay

File: `paper_bot_logs\event_replay_tournament_summary.csv`  
Status: `present`

Purpose:
- Simulate strategy execution day-by-day through history.
- Uses target allocation changes to trigger simulated trades.
- More realistic than simple vectorized return math.

Important:
- First version overtraded.
- Corrected version fixed buy-and-hold trade counts to 1 and made replay results usable.

Top rows:

| strategy | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| XLK_buy_hold | 16.43% | 0.779 | -53.03% | 22.91% | 1 | 1 |
| QQQ_buy_hold | 15.87% | 0.781 | -53.40% | 21.93% | 1 | 1 |
| QQQ_50_200_cross | 13.28% | 0.813 | -30.06% | 17.16% | 0.777 | 23 |
| XLK_50_200_cross | 13.10% | 0.787 | -31.15% | 17.64% | 0.765 | 21 |
| QQQ_200_or_GLD | 12.57% | 0.808 | -25.79% | 16.32% | 0.820 | 135 |
| XLK_above_200_cash | 12.47% | 0.813 | -25.53% | 16.05% | 0.774 | 103 |
| QQQ_above_200_cash | 12.06% | 0.811 | -25.79% | 15.53% | 0.781 | 119 |
| QQQ_above_150_cash | 11.96% | 0.816 | -24.48% | 15.28% | 0.777 | 127 |
| SPY_buy_hold | 11.02% | 0.639 | -55.17% | 19.28% | 1 | 1 |
| core_inverse_vol_60d | 10.37% | 0.969 | -24.26% | 10.78% | 0.971 | 1128 |
| core_inverse_vol_120d | 10.37% | 0.963 | -24.52% | 10.86% | 0.965 | 1087 |
| QQQ_200_or_TLT_GLD | 7.56% | 0.684 | -33.59% | 11.64% | 0.658 | 359 |

Subperiod rows:

| period | strategy | cagr_pct | sharpe_0rf | max_drawdown_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- |
| recent_2024_now | XLK_buy_hold | 33.53% | 1.263 | -25.64% | 0.998 | 1 |
| recent_2024_now | QQQ_buy_hold | 28.14% | 1.296 | -22.77% | 0.998 | 1 |
| recent_2024_now | XLK_above_200_cash | 27.17% | 1.259 | -16.73% | 0.888 | 11 |
| covid_to_now | XLK_buy_hold | 25.14% | 0.944 | -33.56% | 0.999 | 1 |
| recent_2024_now | XLK_50_200_cross | 23.59% | 1.075 | -16.96% | 0.901 | 3 |
| recent_2024_now | QQQ_above_200_cash | 23.29% | 1.339 | -13.56% | 0.906 | 7 |
| recent_2024_now | QQQ_200_or_GLD | 23.29% | 1.339 | -13.56% | 0.906 | 7 |
| recent_2024_now | QQQ_above_150_cash | 22.54% | 1.330 | -13.44% | 0.879 | 17 |
| covid_to_now | XLK_50_200_cross | 22.24% | 0.967 | -31.15% | 0.807 | 7 |
| recent_2024_now | SPY_buy_hold | 21.82% | 1.320 | -18.71% | 0.996 | 1 |
| covid_to_now | QQQ_buy_hold | 21.46% | 0.904 | -35.11% | 0.999 | 1 |
| covid_to_now | XLK_above_200_cash | 20.87% | 1.021 | -25.52% | 0.805 | 29 |
| covid_to_now | QQQ_50_200_cross | 19.86% | 0.956 | -28.55% | 0.804 | 7 |
| recent_2024_now | QQQ_50_200_cross | 19.72% | 0.999 | -22.77% | 0.922 | 3 |
| recent_2024_now | core_inverse_vol_120d | 19.50% | 1.555 | -11.45% | 0.987 | 132 |
| recent_2024_now | core_inverse_vol_60d | 19.13% | 1.558 | -10.96% | 0.981 | 137 |
| recent_2024_now | QQQ_200_or_TLT_GLD | 18.96% | 1.250 | -13.56% | 0.794 | 17 |
| covid_to_now | QQQ_200_or_GLD | 18.47% | 1.024 | -24.89% | 0.796 | 35 |
| covid_to_now | QQQ_above_200_cash | 18.46% | 1.023 | -24.89% | 0.796 | 25 |
| covid_to_now | QQQ_above_150_cash | 18.31% | 1.029 | -24.47% | 0.786 | 33 |
| full | XLK_buy_hold | 16.43% | 0.779 | -53.03% | 1 | 1 |
| full | QQQ_buy_hold | 15.87% | 0.781 | -53.40% | 1 | 1 |
| covid_to_now | SPY_buy_hold | 15.38% | 0.806 | -33.71% | 0.999 | 1 |
| pre_2020 | QQQ_buy_hold | 13.31% | 0.716 | -53.40% | 1 | 1 |
| full | QQQ_50_200_cross | 13.28% | 0.813 | -30.06% | 0.777 | 23 |
| full | XLK_50_200_cross | 13.10% | 0.787 | -31.15% | 0.765 | 21 |
| full | QQQ_200_or_GLD | 12.57% | 0.808 | -25.79% | 0.820 | 135 |
| pre_2020 | XLK_buy_hold | 12.55% | 0.686 | -53.03% | 1 | 1 |
| full | XLK_above_200_cash | 12.47% | 0.813 | -25.53% | 0.774 | 103 |
| full | QQQ_above_200_cash | 12.06% | 0.811 | -25.79% | 0.781 | 119 |
| full | QQQ_above_150_cash | 11.96% | 0.816 | -24.48% | 0.777 | 127 |
| rate_hike_2022_2023 | XLK_50_200_cross | 11.54% | 0.782 | -18.62% | 0.533 | 3 |
| covid_to_now | core_inverse_vol_60d | 11.24% | 0.890 | -24.22% | 0.982 | 358 |
| covid_to_now | core_inverse_vol_120d | 11.10% | 0.866 | -24.45% | 0.988 | 347 |
| full | SPY_buy_hold | 11.02% | 0.639 | -55.17% | 1 | 1 |
| rate_hike_2022_2023 | QQQ_50_200_cross | 10.65% | 0.812 | -16.90% | 0.484 | 3 |
| full | core_inverse_vol_60d | 10.37% | 0.969 | -24.26% | 0.971 | 1128 |
| full | core_inverse_vol_120d | 10.37% | 0.963 | -24.52% | 0.965 | 1087 |
| pre_2020 | QQQ_50_200_cross | 10.31% | 0.736 | -30.06% | 0.764 | 17 |
| pre_2020 | core_inverse_vol_120d | 9.93% | 1.034 | -22.45% | 0.953 | 729 |

---

### 5. Moving-Average Parameter Sweep

File: `paper_bot_logs\ma_parameter_sweep_summary.csv`  
Status: `present`

Purpose:
- Test whether QQQ 50/200 is robust or just one lucky parameter.
- Symbols: QQQ, XLK
- Fast windows: 10, 20, 30, 40, 50, 75, 100
- Slow windows: 100, 125, 150, 175, 200, 225, 250, 300

Result:
- QQQ 50/200 is not isolated.
- A broader QQQ trend-following cluster exists.
- Stronger variants appeared, especially QQQ 100/225, QQQ 75/300, QQQ 100/250, QQQ 50/250, and QQQ 40/200.
- These should not replace the paper bot until walk-forward and subperiod candidate scoring are done.

Top 25 sweep rows:

| strategy | symbol | rule_type | fast | slow | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| XLK_buy_hold | XLK | buy_hold |  |  | 16.43% | 0.779 | -53.03% | 22.91% | 1 | 1 |
| QQQ_buy_hold | QQQ | buy_hold |  |  | 15.87% | 0.781 | -53.40% | 21.93% | 1 | 1 |
| QQQ_100_225_cross | QQQ | cross | 100 | 225 | 15.25% | 0.893 | -28.56% | 17.65% | 0.793 | 15 |
| QQQ_75_300_cross | QQQ | cross | 75 | 300 | 15.17% | 0.880 | -28.55% | 17.87% | 0.798 | 9 |
| XLK_100_300_cross | XLK | cross | 100 | 300 | 14.98% | 0.826 | -31.15% | 19.13% | 0.801 | 11 |
| QQQ_100_250_cross | QQQ | cross | 100 | 250 | 14.77% | 0.864 | -28.56% | 17.78% | 0.793 | 11 |
| XLK_30_300_cross | XLK | cross | 30 | 300 | 14.36% | 0.831 | -31.15% | 18.13% | 0.788 | 17 |
| QQQ_75_250_cross | QQQ | cross | 75 | 250 | 14.29% | 0.847 | -28.56% | 17.61% | 0.788 | 13 |
| QQQ_100_300_cross | QQQ | cross | 100 | 300 | 14.26% | 0.830 | -28.55% | 18.03% | 0.795 | 11 |
| QQQ_50_250_cross | QQQ | cross | 50 | 250 | 14.21% | 0.848 | -28.55% | 17.49% | 0.792 | 19 |
| QQQ_30_300_cross | QQQ | cross | 30 | 300 | 14.20% | 0.849 | -28.56% | 17.44% | 0.793 | 23 |
| XLK_20_300_cross | XLK | cross | 20 | 300 | 14.16% | 0.831 | -31.15% | 17.88% | 0.784 | 19 |
| XLK_above_250_cash | XLK | above_ma |  | 250 | 14.10% | 0.876 | -28.06% | 16.63% | 0.782 | 73 |
| QQQ_40_200_cross | QQQ | cross | 40 | 200 | 14.03% | 0.853 | -28.56% | 17.11% | 0.781 | 25 |
| QQQ_50_300_cross | QQQ | cross | 50 | 300 | 14.03% | 0.831 | -29.25% | 17.69% | 0.796 | 15 |
| QQQ_40_250_cross | QQQ | cross | 40 | 250 | 14.00% | 0.842 | -28.56% | 17.37% | 0.791 | 21 |
| XLK_75_300_cross | XLK | cross | 75 | 300 | 13.90% | 0.784 | -31.15% | 18.87% | 0.793 | 13 |
| QQQ_75_225_cross | QQQ | cross | 75 | 225 | 13.81% | 0.826 | -28.56% | 17.52% | 0.784 | 15 |
| XLK_30_250_cross | XLK | cross | 30 | 250 | 13.63% | 0.811 | -31.15% | 17.70% | 0.773 | 25 |
| XLK_100_200_cross | XLK | cross | 100 | 200 | 13.57% | 0.779 | -31.15% | 18.56% | 0.770 | 17 |
| QQQ_above_175_cash | QQQ | above_ma |  | 175 | 13.48% | 0.900 | -23.10% | 15.37% | 0.779 | 117 |
| XLK_above_225_cash | XLK | above_ma |  | 225 | 13.48% | 0.859 | -23.21% | 16.28% | 0.777 | 107 |
| XLK_40_250_cross | XLK | cross | 40 | 250 | 13.46% | 0.793 | -31.15% | 17.99% | 0.775 | 23 |
| QQQ_20_300_cross | QQQ | cross | 20 | 300 | 13.43% | 0.825 | -28.55% | 17.06% | 0.790 | 23 |
| XLK_40_200_cross | XLK | cross | 40 | 200 | 13.38% | 0.805 | -31.15% | 17.50% | 0.764 | 23 |

Viable rows:

| strategy | symbol | rule_type | fast | slow | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QQQ_100_225_cross | QQQ | cross | 100 | 225 | 15.25% | 0.893 | -28.56% | 17.65% | 0.793 | 15 |
| QQQ_75_300_cross | QQQ | cross | 75 | 300 | 15.17% | 0.880 | -28.55% | 17.87% | 0.798 | 9 |
| XLK_100_300_cross | XLK | cross | 100 | 300 | 14.98% | 0.826 | -31.15% | 19.13% | 0.801 | 11 |
| QQQ_100_250_cross | QQQ | cross | 100 | 250 | 14.77% | 0.864 | -28.56% | 17.78% | 0.793 | 11 |
| XLK_30_300_cross | XLK | cross | 30 | 300 | 14.36% | 0.831 | -31.15% | 18.13% | 0.788 | 17 |
| QQQ_75_250_cross | QQQ | cross | 75 | 250 | 14.29% | 0.847 | -28.56% | 17.61% | 0.788 | 13 |
| QQQ_100_300_cross | QQQ | cross | 100 | 300 | 14.26% | 0.830 | -28.55% | 18.03% | 0.795 | 11 |
| QQQ_50_250_cross | QQQ | cross | 50 | 250 | 14.21% | 0.848 | -28.55% | 17.49% | 0.792 | 19 |
| QQQ_30_300_cross | QQQ | cross | 30 | 300 | 14.20% | 0.849 | -28.56% | 17.44% | 0.793 | 23 |
| XLK_20_300_cross | XLK | cross | 20 | 300 | 14.16% | 0.831 | -31.15% | 17.88% | 0.784 | 19 |
| XLK_above_250_cash | XLK | above_ma |  | 250 | 14.10% | 0.876 | -28.06% | 16.63% | 0.782 | 73 |
| QQQ_40_200_cross | QQQ | cross | 40 | 200 | 14.03% | 0.853 | -28.56% | 17.11% | 0.781 | 25 |
| QQQ_50_300_cross | QQQ | cross | 50 | 300 | 14.03% | 0.831 | -29.25% | 17.69% | 0.796 | 15 |
| QQQ_40_250_cross | QQQ | cross | 40 | 250 | 14.00% | 0.842 | -28.56% | 17.37% | 0.791 | 21 |
| XLK_75_300_cross | XLK | cross | 75 | 300 | 13.90% | 0.784 | -31.15% | 18.87% | 0.793 | 13 |
| QQQ_75_225_cross | QQQ | cross | 75 | 225 | 13.81% | 0.826 | -28.56% | 17.52% | 0.784 | 15 |
| XLK_30_250_cross | XLK | cross | 30 | 250 | 13.63% | 0.811 | -31.15% | 17.70% | 0.773 | 25 |
| XLK_100_200_cross | XLK | cross | 100 | 200 | 13.57% | 0.779 | -31.15% | 18.56% | 0.770 | 17 |
| QQQ_above_175_cash | QQQ | above_ma |  | 175 | 13.48% | 0.900 | -23.10% | 15.37% | 0.779 | 117 |
| XLK_above_225_cash | XLK | above_ma |  | 225 | 13.48% | 0.859 | -23.21% | 16.28% | 0.777 | 107 |
| XLK_40_250_cross | XLK | cross | 40 | 250 | 13.46% | 0.793 | -31.15% | 17.99% | 0.775 | 23 |
| QQQ_20_300_cross | QQQ | cross | 20 | 300 | 13.43% | 0.825 | -28.55% | 17.06% | 0.790 | 23 |
| XLK_40_200_cross | XLK | cross | 40 | 200 | 13.38% | 0.805 | -31.15% | 17.50% | 0.764 | 23 |
| XLK_75_175_cross | XLK | cross | 75 | 175 | 13.36% | 0.781 | -31.15% | 18.18% | 0.767 | 21 |
| QQQ_50_200_cross | QQQ | cross | 50 | 200 | 13.28% | 0.813 | -30.06% | 17.16% | 0.777 | 23 |
| XLK_40_300_cross | XLK | cross | 40 | 300 | 13.17% | 0.761 | -31.15% | 18.53% | 0.789 | 15 |
| XLK_40_225_cross | XLK | cross | 40 | 225 | 13.16% | 0.789 | -31.15% | 17.65% | 0.767 | 21 |
| QQQ_40_125_cross | QQQ | cross | 40 | 125 | 13.14% | 0.845 | -28.56% | 16.18% | 0.752 | 31 |
| XLK_50_200_cross | XLK | cross | 50 | 200 | 13.10% | 0.787 | -31.15% | 17.64% | 0.765 | 21 |
| QQQ_50_175_cross | QQQ | cross | 50 | 175 | 13.09% | 0.805 | -28.55% | 17.11% | 0.774 | 29 |

QQQ cross cluster around 50/200:

| strategy | symbol | rule_type | fast | slow | cagr_pct | sharpe_0rf | max_drawdown_pct | ann_vol_pct | avg_exposure | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QQQ_75_250_cross | QQQ | cross | 75 | 250 | 14.29% | 0.847 | -28.56% | 17.61% | 0.788 | 13 |
| QQQ_50_250_cross | QQQ | cross | 50 | 250 | 14.21% | 0.848 | -28.55% | 17.49% | 0.792 | 19 |
| QQQ_40_200_cross | QQQ | cross | 40 | 200 | 14.03% | 0.853 | -28.56% | 17.11% | 0.781 | 25 |
| QQQ_40_250_cross | QQQ | cross | 40 | 250 | 14.00% | 0.842 | -28.56% | 17.37% | 0.791 | 21 |
| QQQ_75_225_cross | QQQ | cross | 75 | 225 | 13.81% | 0.826 | -28.56% | 17.52% | 0.784 | 15 |
| QQQ_50_200_cross | QQQ | cross | 50 | 200 | 13.28% | 0.813 | -30.06% | 17.16% | 0.777 | 23 |
| QQQ_50_175_cross | QQQ | cross | 50 | 175 | 13.09% | 0.805 | -28.55% | 17.11% | 0.774 | 29 |
| QQQ_50_225_cross | QQQ | cross | 50 | 225 | 13.01% | 0.791 | -28.55% | 17.38% | 0.786 | 21 |
| QQQ_75_200_cross | QQQ | cross | 75 | 200 | 12.93% | 0.784 | -31.10% | 17.47% | 0.779 | 19 |
| QQQ_40_225_cross | QQQ | cross | 40 | 225 | 12.68% | 0.778 | -32.11% | 17.26% | 0.787 | 25 |
| QQQ_30_250_cross | QQQ | cross | 30 | 250 | 12.63% | 0.786 | -28.56% | 16.96% | 0.790 | 23 |
| QQQ_40_150_cross | QQQ | cross | 40 | 150 | 12.50% | 0.797 | -30.13% | 16.51% | 0.770 | 27 |
| QQQ_75_150_cross | QQQ | cross | 75 | 150 | 12.48% | 0.767 | -30.06% | 17.29% | 0.760 | 27 |
| QQQ_30_150_cross | QQQ | cross | 30 | 150 | 12.44% | 0.795 | -33.05% | 16.45% | 0.769 | 33 |
| QQQ_75_175_cross | QQQ | cross | 75 | 175 | 12.32% | 0.754 | -29.67% | 17.44% | 0.774 | 23 |
| QQQ_30_200_cross | QQQ | cross | 30 | 200 | 11.98% | 0.765 | -29.68% | 16.61% | 0.777 | 29 |
| QQQ_30_225_cross | QQQ | cross | 30 | 225 | 11.96% | 0.756 | -32.30% | 16.82% | 0.787 | 23 |
| QQQ_40_175_cross | QQQ | cross | 40 | 175 | 11.74% | 0.746 | -28.56% | 16.77% | 0.776 | 27 |
| QQQ_50_150_cross | QQQ | cross | 50 | 150 | 11.60% | 0.742 | -31.49% | 16.67% | 0.766 | 27 |

---

## Current Interpretation

### Keep as Current Paper Bot Default

`QQQ_50_200_cross`

Reason:
- Already implemented.
- Survived corrected event replay.
- Low trade count.
- Better drawdown control than QQQ buy-and-hold.
- Good enough for 1-share paper monitoring.

### Strongest Research Candidate

`QQQ_100_225_cross`

Reason:
- Strongest non-buy-hold candidate in current MA sweep.
- Higher CAGR and Sharpe than QQQ 50/200 in the sweep.
- Still needs walk-forward validation before promotion.

### Other Serious Candidates

- `QQQ_75_300_cross`
- `QQQ_100_250_cross`
- `QQQ_50_250_cross`
- `QQQ_40_200_cross`
- `QQQ_above_175_cash`
- `XLK_above_250_cash`

### Parked

- `core_inverse_vol_60d`
- `core_inverse_vol_120d`

Reason:
- Good risk-adjusted metrics.
- Too much turnover for the current first paper-bot implementation.

---

## Rejections / Not First Priority

| Strategy group | Reason |
|---|---|
| SPY buy-and-hold | Benchmark only. Lower return than viable QQQ/XLK trend candidates. |
| QQQ buy-and-hold | Strong CAGR but very large drawdown. Useful benchmark, not controlled strategy. |
| XLK buy-and-hold | Strong CAGR but sector concentration and very large drawdown. |
| Initial 5-ETF simple strategies | Mostly failed against SPY in first-pass tests. |
| SPY trend-pullback | Low drawdown but weak return/exposure profile. |
| QQQ 200 or TLT/GLD | Weaker after corrected replay than initial vectorized result suggested. |
| Inverse-vol variants | Not rejected permanently; parked due to turnover/operational complexity. |

---

## 2026-06-19 Checkpoint — Candidate Selection and Config-Driven Preview

### New Files Created

Codex created the candidate-selection endpoint:

* `experiments\llm_alpaca_paper_bot\select_paper_candidates.py`
* `paper_bot_logs\paper_candidate_selection_summary.csv`
* `paper_bot_logs\paper_candidate_selection_rejections.csv`
* `paper_bot_logs\paper_candidate_selection_report.md`

Config-driven paper-bot files were also added:

* `experiments\llm_alpaca_paper_bot\paper_bot_config.yaml`
* `experiments\llm_alpaca_paper_bot\check_paper_bot_config.py`
* updated `experiments\llm_alpaca_paper_bot\ma_parallel_signal_preview.py`

### Candidate-Selection Result

| Role                             | Strategy             | Interpretation                                                          |
| -------------------------------- | -------------------- | ----------------------------------------------------------------------- |
| Primary robust-cluster candidate | `QQQ_75_250_cross`   | Best robust-cluster candidate selected by the scoring/reporting layer.  |
| Raw highest score                | `QQQ_100_225_cross`  | Best raw score, but not selected as the primary robust-cluster default. |
| Conservative candidate           | `QQQ_above_175_cash` | Lower-drawdown defensive candidate.                                     |
| Aggressive candidate             | `QQQ_100_225_cross`  | Higher-return challenger, but not the immediate default.                |

### Config Validation

`paper_bot_config.yaml` was created and validated.

| Field              | Value                                                         |
| ------------------ | ------------------------------------------------------------- |
| `paper_only`       | `true`                                                        |
| `orders_enabled`   | `false`                                                       |
| `max_shares`       | `1`                                                           |
| Active strategy    | `QQQ_50_200_cross`                                            |
| Preview strategies | `QQQ_75_250_cross`, `QQQ_100_225_cross`, `QQQ_above_175_cash` |

### Config-Driven Parallel Signal Preview

The preview script now reads strategies from `paper_bot_config.yaml`.

Latest preview result:

| Role              | Strategy             | Signal       |
| ----------------- | -------------------- | ------------ |
| Active default    | `QQQ_50_200_cross`   | `TARGET_QQQ` |
| Preview candidate | `QQQ_75_250_cross`   | `TARGET_QQQ` |
| Preview candidate | `QQQ_100_225_cross`  | `TARGET_QQQ` |
| Preview candidate | `QQQ_above_175_cash` | `TARGET_QQQ` |

Result:

`All previews agree with active: True`

Interpretation:

* There is no signal conflict right now.
* The active bot and all preview candidates agree that QQQ remains in-market.
* No new paper orders were submitted.
* The current default should not be replaced while the existing 1-share QQQ 50/200 paper test is still open/being observed.

### Config-Driven Paper Signal

`config_driven_paper_signal.py` was added.

Latest result:

| Field | Value |
|---|---|
| Active strategy | `QQQ_50_200_cross` |
| Signal | `BUY` / target 1 QQQ |
| Current QQQ position | `0` |
| Target QQQ position | `1` |
| Existing open order | Yes |
| Open order status | `accepted`, filled qty `0` |
| Market open | `false` |
| Execution result | No order submitted |
| Block reason | Open order already exists; duplicate submission refused |

Interpretation:

- The config-driven paper signal is working.
- The strategy wants 1 QQQ share.
- The bot correctly refused a duplicate order because the earlier 1-share paper order is still open.
- The market-hours guard also confirms the market is closed.
- No more order code should be added until the open order fills or is cancelled.

### Walk-Forward Integrated Candidate Selection

`select_paper_candidates.py` was updated to incorporate walk-forward validation outputs.

Updated files:

- `experiments\llm_alpaca_paper_bot\select_paper_candidates.py`
- `paper_bot_logs\paper_candidate_selection_summary.csv`
- `paper_bot_logs\paper_candidate_selection_rejections.csv`
- `paper_bot_logs\paper_candidate_selection_report.md`

Final recommendation:

| Role | Strategy | Status |
|---|---|---|
| Active default | `QQQ_50_200_cross` | Keep active |
| Replacement candidate | `QQQ_75_250_cross` | `preview_replacement_candidate` |
| Aggressive candidate | `QQQ_100_225_cross` | `aggressive_preview_only` |
| Conservative candidate | `QQQ_above_175_cash` | `conservative_preview_only` |

Reason:

- Walk-forward adaptive selection did not beat fixed QQQ 50/200.
- `QQQ_75_250_cross` beat QQQ 50/200 in fixed walk-forward checks, but not enough for automatic promotion.
- There is already an accepted/unfilled 1-share QQQ paper BUY order.
- Therefore `paper_bot_config.yaml` remains unchanged.

Current decision:

- Do not submit more orders.
- Do not promote `QQQ_75_250_cross` yet.
- Continue no-order preview comparison.
- Reassess after the current QQQ paper order fills or is cancelled.

### Preview Log Comparison Report

`preview_log_comparison_report.py` was added.

Created outputs:

- `paper_bot_logs\preview_log_comparison_summary.csv`
- `paper_bot_logs\preview_log_comparison_disagreements.csv`
- `paper_bot_logs\preview_log_comparison_report.md`

Latest result:

| Field | Value |
|---|---|
| Latest config-driven action | `BUY` |
| Active preview action | `TARGET_QQQ` |
| Preview agreement | `True` |
| Disagreements | `0` |
| Open order count | `1` |
| Promotion blocked | `True` |
| Blocking reason | `open_order_exists` |

Decision:

- Keep `QQQ_50_200_cross` active.
- Keep `QQQ_75_250_cross` as no-order replacement preview.
- Do not promote while the accepted/unfilled QQQ paper order exists.
- Continue monitoring after market opens.

## Current Decision

Do not replace the active paper bot yet.

Current active default remains:

`QQQ_50_200_cross`

Primary replacement candidate:

`QQQ_75_250_cross`

Aggressive preview-only candidate:

`QQQ_100_225_cross`

Conservative preview-only candidate:

`QQQ_above_175_cash`

Current recommendation:

`observe_then_reassess_after_order_resolution`

Meaning:

1. Keep `QQQ_50_200_cross` as the active paper-bot default.
2. Keep `QQQ_75_250_cross` running as the no-order replacement preview.
3. Keep `QQQ_100_225_cross` as aggressive preview only.
4. Keep `QQQ_above_175_cash` as conservative preview only.
5. Do not submit more orders while the existing 1-share QQQ paper BUY order is accepted/unfilled.
6. Do not promote `QQQ_75_250_cross` yet, even though it beat QQQ 50/200 in fixed walk-forward checks.
7. Any future promotion should happen through `paper_bot_config.yaml`, not by hardcoding a new strategy in Python.

---

## Next Required Work

1. Wait until the market reopens and the current QQQ paper order either fills, cancels, expires, or otherwise resolves.

2. Run the safe daily cycle after market open:

   ```powershell
   .\experiments\llm_alpaca_paper_bot\run_safe_daily_cycle.ps1
   .\experiments\llm_alpaca_paper_bot\run_safe_daily_cycle.ps1 -CandidatePreview
   ```

3. Regenerate the preview-log comparison report:

   ```powershell
   .\.venv\Scripts\python.exe experiments\llm_alpaca_paper_bot\preview_log_comparison_report.py
   ```

4. Confirm whether the active strategy and replacement candidate still agree.

5. If the order fills, confirm the bot moves from `BUY` to `HOLD`.

6. Keep `orders_enabled: false` and `ENABLE_PAPER_ORDERS=false` unless deliberately testing one controlled paper execution.

7. Do not scale above 1 paper share.

8. Do not push to remote until exposed API keys are rotated and `.env` is confirmed untracked.

---

## Generated Files Checked

| File | Status |
|---|---|
| `historical_strategy_backtest_summary.csv` | present |
| `strategy_tournament_summary.csv` | present |
| `robust_strategy_tournament_full_summary.csv` | present |
| `robust_strategy_tournament_period_summary.csv` | present |
| `event_replay_tournament_summary.csv` | present |
| `event_replay_tournament_period_summary.csv` | present |
| `ma_parameter_sweep_summary.csv` | present |
| `ma_parameter_sweep_viable.csv` | present |
| `ma_parameter_sweep_qcc_cluster.csv` | present |
| `qqq_50_200_paper_signal.jsonl` | present |
| `paper_candidate_selection_summary.csv` | present |
| `paper_candidate_selection_rejections.csv` | present |
| `paper_candidate_selection_report.md` | present |
| `walk_forward_ma_validation_summary.csv` | present |
| `walk_forward_ma_validation_report.md` | present |
| `ma_parallel_signal_preview.jsonl` | present |
| `latest_ma_parallel_signal_preview.csv` | present |
| `config_driven_paper_signal.jsonl` | present |
| `daily_paper_status_report.md` | present |
| `daily_paper_status_snapshot.json` | present |
| `daily_paper_status_history.jsonl` | present |
| `preview_log_comparison_summary.csv` | present |
| `preview_log_comparison_disagreements.csv` | present |
| `preview_log_comparison_report.md` | present |