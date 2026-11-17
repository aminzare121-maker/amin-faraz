# V5 extreme-bar contrarian reversal — 2026-11-18

Hypothesis: unusually large 15-minute directional displacement can reverse due to temporary liquidity imbalance. Signal at closed candle (absolute body / median prior 32 ranges >=1.8), contrarian entry next candle open, 1.25x prior median-range stop, 1.5x target, maximum 4 candles. Stop wins same-bar ambiguity. Initial $1000, 1% risk, variable lots rounded down to 0.01, assumed $1.46/oz roundtrip costs. No delayed signals.

Dataset: private Eplanet merged M15 CSV, 23,643 rows; chronological 60/40 train/OOS.

| Segment | Variant | Opportunities | Trades | Gross USD | Cost USD | Net USD | Closed drawdown USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 515 | 169 | 49.09 | 255.50 | -206.41 | 278.19 | 0 |
| Train | Guard | 538 | 75 | 12.16 | 115.34 | -103.18 | 144.18 | 0 |
| OOS | Base | 357 | 206 | 35.33 | 302.22 | -266.89 | 301.56 | 0 |
| OOS | Guard | 410 | 0 | 0 | 0 | 0 | 0 | 0 |

Guard excludes signal candles with range >3x trailing median range or spread >30 raw feed units. Opportunity counts differ because skipped trades permit additional signals. Guard abstention is not a profitable strategy. Both approaches fail target. Gross results cannot cover assumed transaction costs. Intrabar path and actual broker fees unverified. Private dataset not uploaded. Executed local source: v5_extreme_reversal_20261118.py; local result ledger: v5_extreme_reversal_20261118_results.json. Code not yet committed to GitHub. No demo or real orders.
