# V5 adverse-wick gate — 2026-11-20
Hypothesis: rejection wick against continuation direction >=45% of current candle true range signals failed follow-through. Signals use only closed candles. Fixed 60/40 chronological split; 23,643 Eplanet M15 candles, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604.
Capital $1,000, variable 0.01–0.10 lots, 1% risk cap, 12-bar hold, stop-first OHLC approximation, $87 per lot round-trip estimated cost.
| Segment | Variant | Opportunities | Trades | Gross | Cost | Net | Closed DD | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | baseline |2061|132|97.38|118.32|-20.94|175.17|0/156|
| train | adverse wick |2061 (480 excluded)|124|107.16|111.36|-4.20|143.69|0/156|
| holdout | baseline |1526|177|169.61|153.99|15.62|138.77|1/104|
| holdout | adverse wick |1526 (350 excluded)|159|228.86|138.33|90.53|64.73|0/104|
| holdout | adverse wick + $15 daily loss guard |1526|155|187.48|134.85|52.63|82.62|0/104|
New finding: wick gate increases holdout net $74.91 and reduces closed DD $74.04 relative to same-code baseline; guard harms results. Training gate still loses $4.20. Does NOT meet $50 net per trading day. Not approved for demo or real orders. Execution is OHLC only, intrabar stop-first, no broker-verified spread/ticks. Separate local research code includes explicit opportunity/exclusion counts; repository script uses same entry condition and baseline engine. Private market CSV intentionally excluded.
