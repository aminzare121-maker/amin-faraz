# V5 compression-release audit — 2026-11-23
Dataset: private Eplanet M15 CSV (23,643 candles). NOT committed. Split: 2026-06-15 UTC. Starting equity $1,000, dynamic 0.01 minimum lot, risk 0.75% per trade, 8-bar maximum holding period. Entry next bar open, stop 1 ATR, target 1.8 ATR, stop-first ambiguity convention. Estimated costs: recorded spread points x $0.01/oz + $0.60/oz extra; contract assumed 100 oz/lot. Not a broker-validated fill model.
Hypothesis: four-bar volatility compression followed by a volume-confirmed directional close may trigger order-flow continuation. Independent guard rejects candle range >1.7 ATR or spread >45 points.
| Segment | Variant | Raw opportunities | Executed | Gross wins | Gross losses | Costs | Net | Closed drawdown | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | base | 109 | 17 | 40.56 | -70.94 | 14.99 | -45.37 | 57.35 | 0 |
| Train | guard | 109 | 10 | 12.84 | -45.32 | 8.90 | -41.38 | 53.36 | 0 |
| Test | base | 63 | 18 | 36.62 | -81.78 | 17.51 | -62.67 | 73.60 | 0 |
| Test | guard | 63 | 9 | 28.85 | -37.45 | 8.27 | -16.88 | 38.61 | 0 |
Test blocked by minimum lot: base 45, guard 32; guard additionally rejected 22 opportunities. Results negative even with guard. NO DEMO deployment.
Caveats: tick-level intrabar execution, broker contract specification, margin, swaps, slippage and commissions unverified; drawdown is close-to-close equity, not true intratrade drawdown. Source CSV private. The executable GitHub reproduction code and local detailed trade JSON are distinct outputs; independent CI not verified.
