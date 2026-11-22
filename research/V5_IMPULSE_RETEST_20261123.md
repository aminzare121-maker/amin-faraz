# V5 impulse-retest research — 2026-11-23

Hypothesis: high tick-volume directional impulse (>1.8 previous ATR20, tick volume >1.25x rolling median40) followed within three candles by a pullback of 0.35 impulse ATR and a same-direction candle closing beyond EMA20. Signal after close; enter next bar open. Stop 1.25 ATR, target 2 ATR, exit by 9 bars; stop-first for ambiguous OHLC. No overlapping trades.

Dataset private: Eplanet_M15_20251105_20261105_merged.csv, 23,643 M15 candles. Train before 2026-06-15 UTC, OOS from that date. Equity resets to $1000 each partition; variable lots 0.01 increments, cap 0.10; 1% equity risk and skip when minimum lot exceeds risk. Assumed 100oz/lot. Costs = spread points * $0.01/oz plus $0.30/oz roundtrip. No swap; not verified broker contract.

| Metric | Train base | Train guard | OOS base | OOS guard |
|---|---:|---:|---:|---:|
| Opportunities |195|197|127|127|
| Diagnostic trades |50|45|46|42|
| Gross wins $ |265.96|220.54|192.24|166.90|
| Gross losses $ |-207.72|-187.98|-198.45|-184.06|
| Costs $ |29.62|26.82|30.50|27.36|
| Net $ |28.62|5.75|-36.71|-44.52|
| Closed equity drawdown $ |84.60|74.19|108.77|110.77|
| Days >= $50 |0|0|0|0|

Guard excludes ATR above rolling 500-bar 80th percentile and Fridays after 16:00 UTC. Guard worsened OOS net and drawdown. REJECTED: no demo orders authorized. OOS is diagnostic, not a live execution claim.

Limitations: OHLC intrabar path unknown, spread units/contract size unverified, fees assumed, swap excluded, no tick-based drawdown; training used to decide research rejection. Full local simulator and JSON generated but are not yet committed. Do not publish private candles or trade history.
