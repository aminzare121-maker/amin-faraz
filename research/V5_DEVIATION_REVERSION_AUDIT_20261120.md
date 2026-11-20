# V5 deviation-reversion audit — 2026-11-20

Hypothesis: after a >2 standard-deviation departure from prior 24 M15 closes, a reversal candle during low trend-efficiency conditions may mean-revert. Entry next candle open; stop-first conservative OHLC simulation; max 8 bars; 1.2 reward/risk; dynamic lot 0.01–0.10; initial equity $1000; round-trip estimated $87/lot. Features use only contemporaneous or past data.

Input SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604 (private CSV not committed). 23643 candles, chronological 60/40 split.

| Sample | Opportunities | Trades | Gross | Estimated costs | Net | Closed drawdown | >=$50 days |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train base | 209 | 55 | -96.38 | 48.72 | -145.10 | 145.10 | 0/156 |
| Holdout base | 118 | 72 | -58.04 | 62.64 | -120.68 | 139.55 | 0/104 |
| Holdout daily-loss guard -$12 | 118 | 70 | -64.08 | 60.90 | -124.98 | 143.85 | 0/104 |

Guard worsens holdout by $4.30. Reject signal and guard. Not eligible for MT5 demo. No live orders. Costs approximate; no tick-level fills or verified broker contract. Local executable code and JSON exist as run artifacts; code has NOT been committed to GitHub. No private price data included here.
