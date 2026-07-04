# GMA-8C Frozen ETF/ETP Historical Tournament V1

GMA-8C executes the frozen historical ETF/ETP strategy tournament using GMA-8A rules and GMA-8B verified immutable adjusted-price evidence.
All results are observed development evidence, not a pristine final holdout.
Highest historical CAGR or Sharpe alone is not a selection rule.
No execution or promotion decision is produced.

The bounded run executes 80 fixed rule templates in each of the Core-22 and Expanded-29 arms. It applies the four frozen transaction-cost scenarios and reports full-history, five chronological-block, rolling three-year, rolling five-year, and seven preregistered regime measurements. Historical gates are evaluated only at 10 bps.

Signals use information through the decision-session adjusted close. Targets become effective at the next tradable session close, and strategy returns begin after that close. Turnover is the one-way absolute weight change against drifted prior weights; the associated cost is deducted once on the effective session.

The implementation reads only explicit GMA-8A and GMA-8B files and the 29 immutable per-ticker paths recorded by GMA-8B. Each market-data file is re-hashed before use. It performs no directory discovery, data fetch, model fit, parameter search, target export, paper session, broker action, or real-money action.
