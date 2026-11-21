# V5 rejection-wick research — 2026-11-21

Private Eplanet M15 dataset: 23643 candles. 155 training days, 104 out-of-sample days. No private market data committed.

Hypothesis: a long rejection wick followed by a close away from the rejected extreme reflects absorption and predicts a short 3-bar reversal. Entry next bar open; ATR(32) shifted one bar; variable lot using 1% equity risk and 1.25 ATR stop for sizing, minimum 0.01 lot, maximum 0.20. Assumed round-trip costs $0.45/oz and 100 oz per lot. Independent ATR stop guard tested; OHLC-only execution cannot establish intrabar ordering.

Out-of-sample:

| Variant | Opportunities | Trades | Gross profit | Gross loss | Estimated costs | Net | Max closed DD | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Wick >= 0.65 range, no guard | 508 | 196 | 667.15 | -762.31 | 88.20 | -183.36 | 279.74 | 0 |
| Wick >= 0.65 range, ATR guard | 509 | 241 | 776.27 | -798.83 | 108.90 | -131.46 | 268.23 | 0 |

The different opportunity and trade counts reflect position occupancy and guard exits. The guard lowers net loss by $51.90 but does not make the strategy profitable. Both variants fail the financial gate and are forbidden for demo deployment. This report is not an independent GitHub CI execution; local source and JSON are separate artifacts. No live or demo orders.
