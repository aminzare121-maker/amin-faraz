# V5 weighted reclaim — 2026-11-19
New hypothesis: directional recross of rolling 32-bar tick-volume-weighted typical price with positive/negative four-bar slope. Signals use completed candles; next candle open is the assumed fill. Exit on stop or after four bars. No COT/sentiment.
Private Eplanet M15 CSV: 23,643 candles, chronological 60/40 split. Capital $1,000, lot 0.01–0.10, nominal 0.5% risk sizing. Assumed round-trip execution cost $0.40/oz (spread/slippage proxy); broker commissions, swaps, real spreads and tick-by-tick stop fills NOT verified.
Local prototype results:
TRAIN: 429 trades; gross +$617.47; proxy costs $171.60; net +$445.87; closed-equity drawdown $164.22; 8 days >= $50.
HOLDOUT: 276 trades; gross +$221.02; proxy costs $110.40; net +$110.62; closed-equity drawdown $142.95; 2 days >= $50 across 96 active days.
Separate loss-limiter: after closed daily P/L <= -$15, suppress subsequent trades that day. 254 holdout trades; gross +$221.44; costs $101.60; net +$119.84; closed-equity drawdown $128.85; 2 days >= $50.
Caution: the protective variant was inspected on the same holdout, and therefore cannot be claimed independently validated. Prototype uses fixed-bar execution and may understate costs. The committed reproducibility script was not separately executed through GitHub Actions; local prototype was executed. No private data committed.
DECISION: FAIL $50 net each trading day; no MT5 demo activation, no real orders.
