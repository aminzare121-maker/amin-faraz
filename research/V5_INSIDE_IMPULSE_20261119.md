# V5 inside-bar impulse test — 2026-11-19

Hypothesis: a large directional impulse followed by an inside bar and a close-confirmed breakout in impulse direction may predict short-term continuation. Entries use next bar open, stops are evaluated on OHLC, maximum holding period 5 bars.

Private dataset: Eplanet_M15_20251105_20261105_merged.csv (not committed), 23643 rows. Chronological 60/40 split, split epoch 1781502300. Starting equity $1000 for each partition, variable lot sized by 0.5% equity risk; trades skipped if minimum 0.01 lot exceeds budget. Round-trip hypothetical cost $0.40/oz.

| Metric | Train | Holdout | Holdout daily -$15 limiter |
|---|---:|---:|---:|
| Signal opportunities | 48 | 34 | 34 |
| Executed trades | 6 | 2 | 2 |
| Gross USD | -9.09 | -8.87 | -8.87 |
| Estimated cost USD | 2.40 | 0.80 | 0.80 |
| Net USD | -11.48 | -9.67 | -9.67 |
| Closed-equity drawdown USD | 19.52 | 9.67 | 9.67 |
| Days >= $50 | 0 | 0 | 0 |

Research conclusion: rejected. The daily loss limiter had no effect. Not eligible for MT5 demo. OHLC backtest, no verified tick-level fill, broker commissions, margin, swaps or slippage. Signal and risk controls are assessed separately. Local runnable code and result JSON are available in the automation's artifacts, but have not been pushed to this branch. No private data committed.
