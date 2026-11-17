# V5 — Intraday overshoot fade, 2026-11-17

New hypothesis: 07:00–10:00 UTC directional displacement may mean-revert between 10:00–12:00 UTC. Signal is based only on completed OHLC bars. Entry at 10:00 UTC open, stop 1.5 times previous 20-bar median range, target 1.5R, otherwise time exit. Stop-first on ambiguous OHLC. No live or demo orders.

Private Eplanet M15 CSV: 23,643 bars; SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. 60/40 chronological split; holdout starts 2026-06-15 05:45 UTC. Threshold = training median of absolute 07–10 move divided by median 20-bar range = 1.6519353373923185; frozen for holdout.

| Metric | Holdout base | Holdout risk guard |
|---|---:|---:|
| Opportunities | 48 | 48 |
| Trades | 18 | 0 |
| Gross USD | -28.36 | 0 |
| Estimated costs USD | 26.28 | 0 |
| Net USD | **-54.64** | **0** |
| Max closed-equity drawdown USD | 75.21 | 0 |
| Days with >= $50 net | 0 | 0 |
| Days evaluated | 103 | 103 |

Training base: 77 opportunities, 25 trades, gross -$84.03, costs $36.50, net -$120.53. Initial capital $1000, risk-based lots floored to 0.01, 100 oz/lot, $1.46 per oz estimated round-trip costs. Executed holdout lots were 0.01. Risk guard requires 0.5% equity risk, no oversized move (ratio >3), and stop distance <=$10; it rejected every trade. Thus it is only a loss-avoidance control, not an alpha strategy. No real broker spreads, tick paths, slippage, margin checks, or intrabar equity drawdown verified.

**Decision: REJECT for MT5 demo.** Neither branch reaches the $50 net per trading day objective. Research code and full trade ledger produced locally; this commit records the summary only; private data not published.
