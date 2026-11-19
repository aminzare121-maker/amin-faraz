# V5 prior-day liquidity sweep — 2026-11-19

Private Eplanet M15 dataset: 23,643 rows, chronological 60/40 split. Hypothesis: liquidity sweep of prior UTC day's high/low followed by close back inside, then reversal at next open. One opportunity/day. Four-bar horizon; ATR-based stop and 1.5R take-profit, stop-first when both touched. Risk 1% of equity, lot clipped to 0.01–0.15. Assumed roundtrip $0.40/oz (not verified with broker). No tick execution, margin validation, or real fills.

| Metric | Training | OOS primary | OOS volatility guard |
|---|---:|---:|---:|
| Opportunities | 116 | 84 | 84 |
| Trades | 116 | 84 | 23 |
| Gross USD | -111.33 | +21.19 | +94.09 |
| Costs USD | 65.20 | 63.60 | 14.80 |
| Net USD | -176.53 | -42.41 | +79.29 |
| Closed-equity drawdown USD | 269.90 | 148.85 | 25.79 |
| Days >= $50 net | 0 | 0 | 0 |
| Days evaluated | 156 | 104 | 104 |

Guard excludes sweep candle range >1.5x prior 14-bar mean range. This guard was inspected on OOS; its apparent gain is exploratory, NOT independently validated or approved for trading. Gross is net of price moves before estimated costs. Original executable plus JSON ledger retained locally, private CSV not committed. GitHub reproducer is research-only. No live or demo orders. Rejected against $50 net per trading day requirement.
