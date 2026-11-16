# V5 pullback resumption — 2026-11-16
Source: private Eplanet M15 CSV (not committed). SHA256: `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. 23643 rows; chronological split at row 14185 (60/40).
Hypothesis: recross EMA48 in direction of EMA48/EMA192 trend after a shallow pullback. Entry next candle open, exit four candles later at open. Independent guard excludes large-range, low-tick-volume, high-ATR candles.
1000 USD initial equity; lot sizing with 0.01 minimum and 0.10 maximum, 100 oz per lot; 0.86 USD/oz assumed round-trip cost. No broker execution, intrabar stop, margin modeling or live spread.
| Sample | Variant | Opportunities | Trades | Gross USD | Cost USD | Net USD | Closed-equity max DD USD | Days >=50 USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 309 | 10 | 4.79 | 8.60 | -3.81 | 17.97 | 0 |
| Train | Guard | 309 | 6 | 6.40 | 5.16 | +1.24 | 4.28 | 0 |
| OOS | Base | 212 | 12 | -29.10 | 10.32 | -39.42 | 55.08 | 0 |
| OOS | Guard | 213 | 3 | +5.63 | 2.58 | +3.05 | 3.70 | 0 |
All filled trades were 0.01 lots. Opportunities are signal candidates, not trades; guarded opportunity count differs due to the simulation's skip-after-entry.
Decision: reject as trade engine. The guarded OOS result is positive on only 3 trades and does not meet $50 net/day or establish robustness. No demo/live activation.
Reproduce: `python research/v5_pullback_resumption.py /path/to/private/Eplanet_M15_20251105_20261105_merged.csv`.
