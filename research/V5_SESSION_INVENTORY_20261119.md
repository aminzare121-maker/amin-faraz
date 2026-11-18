# V5 Session Inventory Unwind — 2026-11-19

Hypothesis: after a 2-hour directional displacement at fixed UTC session times, inventory unwind may cause a 1-hour contrarian move. Unlike prior single-candle, gap, or breakout tests, this tests a time-conditioned multi-bar reversal.

Private Eplanet M15 CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split at 2026-06-15 05:45 UTC. Training selects from UTC hours 08/12/16/20 and displacement thresholds 1/1.5/2 lagged ATR. Selected 08 UTC, threshold 1 ATR. 104 holdout trading days.

Holdout baseline: 48 opportunities, 48 trades, gross -$223.48, modeled costs $68.82, net -$292.30, closed-equity max drawdown $316.53, 29 losing dates, 0 dates net >= $50.

Independent risk guard (exclude anomalous recent ranges or ATR>12): 48 opportunities, 44 trades, gross -$197.99, costs $65.10, net -$263.09, max drawdown $287.32, 26 losing dates, 0 dates >= $50. Guard reduces loss by $29.21 but does not produce positive edge.

Assumptions: starting $1000, variable 0.01 lot steps capped at 0.15, 3% stop risk, 1.5 ATR stop and target, enter next M15 open, maximum 4-bar hold, stop-first on ambiguous OHLC, modeled spread $0.26/oz, slippage $0.30/oz each way, $7/lot roundtrip commission; swap excluded. Tick-level execution and actual broker costs not verified. Research rejected; no MT5 demo/live orders.

Reproduction source and private ledger remain local; this report intentionally excludes private price data.