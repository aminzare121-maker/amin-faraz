# V5 passive limit execution — 2026-11-22

Private Eplanet M15 dataset: 23,643 rows; SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Data not committed. Chronological 60/40 split, OOS from 2026-06-15. Hypothesis: after a directional expansion candle, next-bar passive entry on a 35% body retracement can improve price and reduce execution friction relative to buying/selling immediately at next open. Directional candle: body >=0.9 previous ATR20, range >=1.1 ATR20, body/range >=0.65. 1% equity risk, 100 oz/lot, 0.01 min and step, stop 0.8 ATR or $2, target 1.6R, six-bar maximum holding, stop-first OHLC. $0.63/oz market vs hypothetical $0.43/oz passive round-trip costs. OOS capital reset to $1000.

| OOS | Market | Passive limit |
|---|---:|---:|
| Opportunities | 916 | 969 |
| Trades | 671 | 511 |
| Unfilled | 0 | 436 |
| Min-lot rejected | 243 | 19 |
| Gross profit USD | 2192.61 | 2343.09 |
| Gross loss USD | -2244.46 | -2076.09 |
| Estimated costs USD | 450.45 | 296.70 |
| Net USD | -502.30 | -29.70 |
| Max closed drawdown USD | 545.08 | 155.79 |
| Days >= $50 | 1 | 2 |

Training market net -429.79, passive limit +311.69. **OOS passive fails profitability and $50/day target; REJECT both for demo.** Different candidate counts arise from sequential nonoverlapping trade blocking. Important limitations: OHLC cannot determine actual limit-fill sequence, adverse selection, real spread/commission, or tick-level floating drawdown; hypothetical passive cost advantage is not verified with broker. Local script `v5_limit_execution_20261122.py` executed and results JSON created but script is not yet committed. No live or demo orders placed.