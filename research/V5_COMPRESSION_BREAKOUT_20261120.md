# V5 compression breakout — 2026-11-20

Hypothesis: after 8 M15 bars of compression (range <1.5 times prior 64-bar median true range), a completed close outside the consolidation may initiate price discovery. Enter next bar open, 0.8 ATR stop clipped to $2-$12, 1.8R target, stop-first intrabar ordering, five-bar maximum hold. Risk $10 or 1% equity, lot 0.01-0.10. Estimated cost $0.80/oz round trip plus $7/lot. Contract assumption 100 oz/lot. Chronological 60/40 split, 23,643 Eplanet M15 candles. Private CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604.

| Split | Variant | Opportunities | Trades | Gross USD | Cost USD | Net USD | Closed DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train (156 days) | Base | 150 | 107 | 131.20 | 113.97 | +17.23 | 122.52 | 0 |
| Train | -$20 daily guard | 150 | 107 | 131.20 | 113.97 | +17.23 | 122.52 | 0 |
| Holdout (104 days) | Base | 102 | 88 | -26.62 | 89.61 | -116.23 | 131.18 | 0 |
| Holdout | -$20 daily guard | 102 | 88 | -26.62 | 89.61 | -116.23 | 131.18 | 0 |

The guard never triggered; no independent loss reduction. Rejected for demo: holdout loss and insufficient daily return. Historical OHLC cannot establish tick ordering; broker friction and contract specs unverified. Local reproducible Python and JSON generated in this run; code is not committed in this commit. No private data uploaded and no orders sent.
