# V5 volume acceleration — 2026-11-23

New hypothesis: directional close-location plus tick-volume acceleration predicts continuation for two M15 bars. Risk guard separately rejects spread >30 points or candle range >1.7 prior ATR.

Data: private Eplanet M15 CSV, 23643 rows, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Split 2026-06-15 UTC. Assumptions: 100 oz/lot, spread point 0.01 USD/oz, additional $0.30/oz round trip, stop-first ambiguity, dynamic 1% risk lots capped 0.10. No tick execution validation.

| Segment | Variant | Opportunities | Trades | Gross profit | Gross loss | Costs | Net | Closed drawdown | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Base |144|126|376.73|-488.75|102.27|-214.29|235.38|0|
| Train | Guard |153|23|75.02|-84.71|19.84|-29.53|60.77|0|
| OOS | Base |84|84|329.90|-273.53|74.26|-17.89|87.94|0|
| OOS | Guard |97|0|0|0|0|0|0|0|

Guard reduces exposure, not evidence of profitable trades. Opportunity counts differ due to non-overlapping positions. REJECT; no demo or live orders. Private CSV is not committed.
