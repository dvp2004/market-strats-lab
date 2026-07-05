# P-1C Local Adjusted-Price Snapshot Contract V1

P-1C defines and validates the local adjusted-price snapshot format required for future manual intake.
No actual manual snapshot or intake manifest was supplied to this run.
No signal, sleeve weight, ETF target, paper decision, paper session, performance result, broker instruction, or real-money action is produced.
P-1 remains a separate manual-paper observation programme for the frozen GMA-5 equal-weight atomic sleeve portfolio.

Snapshot header: `session_date,SPY,QQQ,IWM,XLB,XLE,XLF,XLI,XLK,XLP,XLU,XLV,XLY,EFA,EEM,BIL,IEF,TLT,AGG,LQD,HYG,GLD,DBC`
P-1C minimum required snapshot sessions: `253`
Required history registry SHA-256: `cbebdb107c6a1330f8dc2d5ae373769776a8f7c77658d8e508e2953b8eed036b`

P-1C uses the local XNYS calendar only for future validation and fails closed if the calendar is unavailable.
It accepts adjusted-close values as supplied or rejects the snapshot; it does not repair, backfill, normalize, adjust, filter, or substitute data.
