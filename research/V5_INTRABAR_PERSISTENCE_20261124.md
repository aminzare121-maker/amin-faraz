# V5 intrabar persistence — 2026-11-24
Hypothesis: directional candle closing near its extreme and with above-median tick volume has next-bar continuation; independent guard removes elevated volatility. Signal uses only completed bar data. Entry next bar open; one-bar exit with stop-first OHLC convention.
Source: private Eplanet M15 CSV (23,643 rows), NOT committed. Split epoch 1781481600 (2026-06-15 UTC). Starting equity $1,000 per split, variable lots 0.01 minimum, 1% risk, 0.8 ATR stop/target, $0.90 per ounce round-trip assumed cost. Tick-level execution and real commissions unavailable.
| Metric | Base train | Guard train | Base test | Guard test |
|---|---:|---:|---:|---:|
| Raw opportunities |818|818|679|679|
| Trades |345|242|395|246|
| Gross profit |677.15|510.11|745.48|405.41|
| Gross loss |-715.59|-526.44|-886.88|-578.64|
| Costs |354.60|251.10|369.00|230.40|
| Net |-393.04|-267.43|-510.40|-403.64|
| Closed drawdown |403.06|267.43|534.16|408.62|
| Days >= $50 |0|0|0|0|
Decision: reject signal for demo. Guard reduces loss but is not a standalone alpha strategy. Code locally executed; GitHub CI not verified. No private CSV committed; no live/demo trades placed.
