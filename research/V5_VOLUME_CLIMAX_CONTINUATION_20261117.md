# V5 volume-climax continuation — 2026-11-17
Research-only. Not approved for MT5 demo.

Hypothesis: unusually high tick volume, range expansion, and a strong directional close may indicate persistent order-flow imbalance. Enter at next M15 open in candle direction; exit after four bars or at stop. Independent risk-only guard excludes high spread versus trailing median and excessively large candle ranges.

Eplanet private CSV: 23,643 rows; chronological 60/40 split. Code executed locally; source code and result JSON are separate local artifacts, not committed in this report.

| OOS metric | Base | Risk guard |
|---|---:|---:|
| Opportunities | 28 | 28 |
| Trades | 23 | 11 |
| Gross USD | -41.21 | +8.57 |
| Estimated costs USD | 19.78 | 9.46 |
| Net USD | -60.99 | -0.89 |
| Closed-equity max drawdown USD | 74.12 | 29.95 |
| Days >= $50 net | 0 | 0 |
| Active days | 21 | 11 |

Training base: 66 trades, net -$220.30, drawdown $250.20.

Assumptions: $1,000 initial equity; 100 oz/lot; $0.86/oz estimated roundtrip cost; target 1% risk, hard 2% risk cap, 0.01–0.05 lot bounds; OOS realized lots 0.01; stop prioritized in OHLC. Broker spread/commission execution, intrabar equity drawdown, margin and tick replay unverified. No live or demo trading.

Decision: reject. Guard reduces loss but does not create an economically viable strategy.