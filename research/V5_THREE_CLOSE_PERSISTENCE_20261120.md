# V5 three-close persistence — 2026-11-20

Hypothesis: three consecutive moderate same-direction M15 candle bodies may reflect order splitting and short-term continuation. Entry next candle open; stop 0.8 x previous 48-bar median true range, target 1.3R, time exit 4 bars, stop-first conservative OHLC. Risk max $10 per trade, variable 0.01–0.10 lots; assumed 100 oz/lot and $87 round-trip/lot. No live trading.

Dataset SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604 ; 23643 candles, chronological 60/40 split.

| Segment | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Max closed DD USD | Days >= $50 / total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 382 | 240 | 92.89 | 238.38 | -145.49 | 201.95 | 0/156 |
| Train | Daily -$15 entry guard | 382 | 230 | 67.10 | 227.94 | -160.84 | 206.96 | 0/156 |
| Holdout | Base | 330 | 251 | -89.45 | 237.51 | -326.96 | 326.96 | 0/104 |
| Holdout | Daily -$15 entry guard | 330 | 243 | -71.16 | 236.64 | -307.80 | 307.80 | 0/104 |

Verdict: reject signal. Guard improves holdout but worsens train; no independent evidence of robust protective value. Costs are assumed, not broker-confirmed. No tick-level intrabar reconstruction, margin validation, or MT5 demo activation. Private data excluded.

Local reproducibility artifacts generated: v5_three_close_persistence_20261120.py and v5_three_close_persistence_20261120_results.json; code has not yet been committed to this branch.
