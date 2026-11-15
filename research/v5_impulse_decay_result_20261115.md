# V5 impulse-rejection experiment — 2026-11-15

Data: private Eplanet M15 CSV (not committed), 23,643 candles. Split: first 70% development; remaining 30% holdout starting 2026-07-21 06:30 UTC.

Hypothesis: A candle whose body exceeds 1.8 times the previous 32-bar median true range, with rejection wick >27% of range and body >45% of range, may exhaust short-term order flow. Wait for a subsequent opposite-direction candle close; enter next open against impulse. Stop = max($1,1.2 x prior median TR); target 1.3R; timeout 6 bars. One position at a time; stop-first on ambiguous OHLC bars.

Sizing: $1,000 initial equity per partition; 1% equity risk per trade; 0.01 lot increments, maximum 1 lot. Assumed $100 per $1 gold movement per lot, spread = CSV spread * $0.01, round-trip slippage $0.60 price, commission $7 per lot. These execution assumptions require broker validation.

Development: 49 signals, 24 trades, 9 winners; gross positive $86.11, gross negative -$108.75, costs $22.98, net -$45.62, maximum drawdown 8.74%, 22 active days, zero days >=$50.

Holdout: 12 signals, 11 trades, 5 winners; gross positive $37.63, gross negative -$34.71, costs $10.96, net -$8.04, maximum drawdown 1.95%, 10 active days, zero days >=$50.

Decision: reject as standalone alpha. No demo activation. Full locally executed Python source and holdout trade log are delivered as conversation artifacts, not uploaded to this branch. No private market data published.
