# V5 pullback-limit execution hypothesis — 2026-11-20

Source: private Eplanet_M15_20251105_20261105_merged.csv (23,643 M15 bars). No private data committed. 60/40 chronological split, 156 train days / 104 holdout days. Reused efficiency/pause signals, modified *entry execution* only. Compare next-open market against limit buy/sell at 0.25 or 0.50 times prior median true range away from next open, valid for one candle. 1% equity risk, variable 0.01–0.10 lot, 100 oz/lot, 1.5 median TR stop clipped $3–20, 1.8R target, maximum 12 candles, stop-first. Estimated roundtrip friction $87 per lot. OHLC touch fills are optimistic; real limit fill probability and tick ordering unverified.

| Segment | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Max closed DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Market | 2061 | 132 | 97.38 | 118.32 | -20.94 | 175.17 | 0/156 |
| Train | Limit .25 | 2061 | 113 | 44.07 | 100.92 | -56.85 | 174.89 | 0/156 |
| Train | Limit .50 | 2061 | 87 | -56.67 | 77.43 | -134.10 | 202.03 | 0/156 |
| Holdout | Market | 1526 | 177 | 169.61 | 153.99 | 15.62 | 138.77 | 1/104 |
| Holdout | Limit .25 | 1526 | 128 | -82.92 | 111.36 | -194.28 | 256.21 | 0/104 |
| Holdout | Limit .50 | 1526 | 144 | 165.18 | 125.28 | 39.90 | 91.80 | 0/104 |

Result: reject .25 limit. .50 limit has better holdout aggregate PnL and lower drawdown but negative training performance and zero $50 holdout days; reject for deployment. Do not enable demo or live trading. Execution simulation cannot establish live profitability. Reproducible Python and JSON are retained as local artifacts of this run; code not yet committed to GitHub.
