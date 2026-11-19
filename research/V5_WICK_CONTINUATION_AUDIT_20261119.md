# V5 wick rejection audit — 2026-11-19

Hypothesis: an extreme rejection wick opposing a preceding four-bar move may predict next-bar reversal. Signal only at bar close; entry at next bar open; exit at next close or stop-first intrabar. Fixed $5 risk sizing, 0.01 lot step, maximum 0.10 lot, $1000 starting balance. Friction model: $0.30 price per ounce roundtrip plus $0.40 per 0.01 lot commission. Historical private Eplanet M15 CSV is NOT committed.

Split chronologically 60/40 of 23643 bars. Test 104 trading days. Base: 225 trades, gross -$42.42, friction $158.20, net -$200.62, closed-equity max drawdown $205.74, 92 winners / 133 losers, 0 days >=$50. Train 156 days: 208 trades, gross -$90.53, costs $147, net -$237.53, drawdown $252.75. Volatility guard (past median range <= 70th percentile train) did not filter any trades; same results. This is NOT a profitable system. Execution on M15 OHLC is approximate, broker spread/commission and intrabar ordering unverified. No trading enabled.

Research code artifact: v5_range_position_20261119.py (local execution; not yet synchronized to this branch).