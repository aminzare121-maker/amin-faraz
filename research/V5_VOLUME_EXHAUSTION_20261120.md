# V5 volume exhaustion reversal — 2026-11-20

New hypothesis: an unusually high tick-volume directional M15 impulse that fails on the next completed bar may indicate exhausted liquidity. Enter against impulse at following bar open, stop-first OHLC, 4-bar horizon. Signal: tick volume >2x previous 64-bar median, range >1.5x prior median, body >60% range, next close crosses impulse midpoint against direction. Stop clip(0.5 impulse range, $2,$12), target 1.5R. Variable lot capped 0.10, minimum 0.01 only if stop risk <=1% equity. $100/oz/lot contract assumed. Estimated round-trip friction $0.8/oz plus $7/lot. Chronological 60/40 train/holdout, 23,643 M15 candles.

| Segment | Variant | Opportunities | Nonoverlap | Trades | Gross | Cost | Net | Closed DD | Days >=$50 / days |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Base |47|42|23|54.32|20.88|33.44|52.97|0/156|
| Train | -$20 daily guard |47|42|23|54.32|20.88|33.44|52.97|0/156|
| Holdout | Base |9|9|8|-4.73|7.83|-12.56|21.36|0/104|
| Holdout | -$20 daily guard |9|9|8|-4.73|7.83|-12.56|21.36|0/104|

Guard did not change outcomes. Hypothesis rejected: holdout net negative, very low opportunity frequency. No demo or real orders. Broker friction and intrabar ordering unverified; stop-first convention used. Source Python and private trade logs retained locally, not uploaded in this commit. No private Eplanet data published.
