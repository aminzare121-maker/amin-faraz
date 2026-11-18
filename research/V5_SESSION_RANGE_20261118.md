# V5 session opening range — 2026-11-18

Hypothesis: breakout of 01:00–01:45 UTC range; enter next M15 open after first breakout close between 02:00–11:45 UTC. Exit at stop (1.2 ATR), target (1.6x stop), or 8 bars. Protective role independently excludes abnormal range/volume. Split: chronological 60/40, 23,643 M15 candles. Capital $1,000, lot variable 0.01–0.08. Cost model $0.30/oz/side * 100 oz/lot, not verified broker execution. Stop-first OHLC assumptions. No real or demo trades.

| Metric | Train baseline | Train guard | OOS baseline | OOS guard |
|---|---:|---:|---:|---:|
| Days |156|156|104|104|
| Opportunities |313|335|265|290|
| Trades |313|153|265|124|
| Gross USD |537.07|162.15|143.91|156.92|
| Cost USD |216.60|96.00|181.80|82.80|
| Net USD |320.47|66.15|-37.89|74.12|
| Closed-equity drawdown USD |204.66|126.07|283.66|124.62|
| Days >= $50 net |3|1|0|0|

Conclusion: guard improves OOS results but still fails $50 net/day target. Reject for MT5 demo. Caveats: bar-level ambiguity, intrabar floating DD, actual spread/slippage/commission and walk-forward robustness unverified. Source code and private data not uploaded to this branch; local artifacts exist for this run.
