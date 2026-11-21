# V5 compression-expansion research — 2026-11-21

Status: **REJECTED**, research only; no MT5 orders. Source data is private and not uploaded.

Hypothesis: volatility compression (prior 8-bar mean true range / prior 64-bar mean true range <0.72) followed by an impulse bar (>1.15 lagged ATR32) closing beyond previous 8-bar high/low may signal a directional expansion. Entry next bar open. Exit stop 1.15 ATR or target 1.8R or after 9 bars, stop-first OHLC. 1% equity risk, 0.01 lot increments, 100oz/lot, 0.46 USD/oz roundtrip estimated friction. Independent guard vetoes impulses exceeding 2 ATR.

Eplanet M15 23,643 bars; chronological split at 2026-06-15. 1000 USD starting equity independently per segment. Note: the guard changes the trade path and thus opportunities counted.

| Segment | Variant | Opportunities | Trades | Gross profit | Gross loss | Costs | Net | Closed DD | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | entry | 224 | 110 | 510.77 | 466.82 | 53.36 | -9.41 | 79.31 | 0 |
| Train | guard | 224 | 80 | 384.49 | 309.21 | 38.64 | +36.64 | 57.28 | 0 |
| OOS | entry | 148 | 122 | 574.91 | 562.97 | 59.34 | -47.40 | 122.80 | 0 |
| OOS | guard | 150 | 87 | 341.18 | 423.44 | 40.48 | -122.74 | 139.81 | 0 |

The guard helped in training but harmed OOS, demonstrating non-robustness. Neither passes financial objective. Local Python implementation and JSON output were executed, but full source has not been committed in this branch. This is not independently CI-verified. Limitations: no real bid/ask tick fills, swap, broker contract verification, or intrabar floating DD; estimates cannot be treated as live results.
