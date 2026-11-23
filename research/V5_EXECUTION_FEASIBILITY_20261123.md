# V5 execution feasibility — 2026-11-23
Data: private Eplanet M15 2025-11-05 to 2026-11-05, 23,643 candles. Never commit data.
Split: train before 2026-06-15 UTC; test from that date.
Hypothesis: shortening ATR-based invalidation from 1.4 ATR to 0.7 ATR permits more 0.01+ lot orders under 0.75% equity risk; check whether execution-frequency gains overcome losses and costs.
Signal: 24-bar close breakout + 0.1 ATR and tick volume >1.35x trailing median. Next-open entry; stop-first for intrabar stop/target collision; time exit after 8 vs 5 bars. Risk sizing floored to .01 lot, max .15, contract 100oz/lot. Costs: observed spread points * $0.01/oz + $0.60/oz; approximation only.
| variant | split | opportunities | trades | blocked min lot | gross profit | gross loss | costs | net | max closed DD | days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| wide | train | 486 | 36 | 437 | 104.04 | -135.37 | 32.91 | -64.24 | 74.80 | 0 |
| wide | test | 371 | 37 | 318 | 129.46 | -135.77 | 35.56 | -41.87 | 53.53 | 0 |
| near | train | 486 | 215 | 196 | 770.26 | -766.49 | 229.94 | -226.17 | 279.27 | 0 |
| near | test | 371 | 249 | 40 | 876.58 | -803.51 | 264.20 | -191.13 | 215.42 | 0 |
| near + shock guard | train | 486 | 131 | 22 | 604.89 | -436.65 | 137.95 | +30.29 | 123.01 | 0 |
| near + shock guard | test | 371 | 137 | 22 | 483.40 | -451.95 | 135.41 | -103.97 | 160.30 | 0 |
Guard: reject bar range >2.2 ATR or spread >35 points. Train improvement did not transfer out of sample. All variants rejected for demo. Risk of gaps, slippage, stop-fill accuracy, and intra-candle floating DD not resolved. No real or demo trades.
Run: python research/v5_execution_feasibility.py PRIVATE_EPLANET_CSV
