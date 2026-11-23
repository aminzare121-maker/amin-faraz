# V5 reopening gap reversion — 2026-11-23
Research only; no demo or live orders.

## Economic hypothesis
After a trading interruption of at least 3 hours, a price gap may represent temporary inventory imbalance. Fade the gap only when the first completed M15 bar rejects its direction. Entry is the next bar open. No COT, sentiment, or future information is used.

## Reproduction
The full executable Python backtest is delivered separately as `v5_gap_reversion_20261123.py`; this report does **not** claim that executable is committed here. Input is private Eplanet M15 CSV (not published). Split: train 2025-11-05 to 2026-06-14, out-of-sample 2026-06-15 to 2026-11-05.

## OOS results (USD)
| Metric | Base | Guard |
|---|---:|---:|
| Signal opportunities | 7 | 7 |
| Trades | 3 | 0 |
| Gross profit | 12.83 | 0 |
| Gross loss | 0 | 0 |
| Estimated costs | 2.88 | 0 |
| Net | +9.95 | 0 |
| Max closed drawdown | 0 | 0 |
| Days >= $50 | 0 | 0 |

Training: base 14 opportunities, 5 trades, net -17.63, max closed drawdown 17.63; guard 14 opportunities, 2 trades, net -5.73, max closed drawdown 7.50.

Assumptions: 100 oz per lot, 0.01 lot steps, variable sizing at 1% risk, maximum 0.10 lots; spread points * $0.01/oz, $7/lot roundtrip commission, $0.25/oz roundtrip slippage; stop/target evaluated OHLC adverse-first, exit after up to 12 bars. Guard excludes spread >35 points, gap >4x historical median range, or signal bar >3x range. Tick-level intrabar drawdown and actual Eplanet contract parameters remain unverified.

**Decision:** Reject for demo. Three OOS trades are statistically inadequate and target of $50 net on each trading day fails. The guard removes all OOS trades; it is not evidence of a profitable protective strategy. No private dataset is committed.
