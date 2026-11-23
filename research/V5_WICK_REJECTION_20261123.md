# V5 wick rejection, 2026-11-23

Data: private Eplanet M15 CSV, 23,643 candles; not committed. Training before 2026-06-15, holdout from 2026-06-15. Hypothesis: long rejection wick >=55% of range and close in opposite extreme 20%, trade next open toward rejection. Range 0.7-3x prior 24-bar median. Stop max(0.8x prior median, $1/oz), target 1.5R, six bars max, stop-first OHLC. Variable lots 0.01 steps, <=0.10, <=1% equity risk estimated including costs. 1 lot=100 oz assumed. Costs: signal spread points x $0.01/oz + $0.20/oz slippage + $7/lot commission; broker assumptions unverified.

| Metric | Train base | Train guard | Holdout base | Holdout guard |
|---|---:|---:|---:|---:|
| Opportunities |793|801|489|502|
| Rejected |439|499|68|190|
| Trades |354|302|421|312|
| Gross gains USD |1040.60|960.40|1306.51|1064.51|
| Gross losses USD |-1203.03|-1053.61|-1377.01|-1038.22|
| Costs USD |238.73|191.66|287.82|198.23|
| Net USD |-401.17|-284.87|-358.32|-171.94|
| Max closed drawdown USD |442.75|310.72|417.40|334.19|
| Days >= $50 net |0|0|0|0|

Guard independently excludes signal spread above min(32 points, 1.3x prior 48-bar median) or candle range >1.8x prior 24-bar median. Guard reduces losses but does not create profitability. Opportunity counts vary with occupied trade windows. Reject both as profit engines; no demo/live orders. Local reproducible code `v5_wick_rejection_20261123.py` and JSON were run, but are not committed in this change. No CI, tick-level drawdown or real contract cost validation.