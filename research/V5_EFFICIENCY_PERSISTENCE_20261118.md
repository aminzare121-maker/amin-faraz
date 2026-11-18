# V5 path efficiency persistence — 2026-11-18
New economic hypothesis: high 8-bar directional path efficiency (Kaufman efficiency ratio >=0.72), without an oversized final candle, indicates sustained order-flow rather than isolated impulse. Entry next bar open. Stop 1.3 lagged median TR, target 2 TR, timeout five bars; OHLC stop-first. Independent risk guard: spread/ATR <=.045, ATR <=8, efficiency >=.82.
Dataset: private Eplanet M15 23,643 rows, held outside GitHub. Chronological last 40%, from 2026-06-15 05:45 UTC, 104 days. $1000 initial, 1% equity risk, lots .01-.05 step .01, 100oz/lot.
Costs estimated: spread points/100, $0.30/oz roundtrip slippage, $7/lot commission.
| Metric | Base | Guard |
|---|---:|---:|
| opportunities | 522 | 790 |
| trades | 262 | 22 |
| gross USD | 318.14 | 24.84 |
| estimated costs USD | 190.01 | 15.13 |
| net USD | 128.13 | 9.71 |
| max closed drawdown USD | 111.30 | 67.28 |
| days >= $50 net / 104 | 2 | 0 |
Different opportunity counts arise from occupied-position filtering; do not compare as raw identical candidate totals.
Result: base positive in held-out sample, but fails $50/day requirement; guard reduces drawdown and also removes most return. No demo activation. Intrabar drawdown, true tick execution, actual broker costs not validated. Code is reproducible with CSV path argument.