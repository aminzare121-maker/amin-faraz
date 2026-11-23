# V5 low-volume dislocation — 2026-11-23
Source: private Eplanet M15 CSV (23,643 bars), SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Do not upload source data.
Hypothesis: a 3-bar displacement exceeding 1.25x prior 32-bar median true range, 1.75x away from prior 32-bar close median, on tick volume below 0.85x prior 32-bar median volume, may revert. Enter opposite direction at next open. Stop 1.15x ATR, take profit 1.3x ATR, max eight bars; stop-first ambiguous OHLC. Risk 1% equity; lot step 0.01, maximum 0.10, 100oz/lot assumption. Costs: spread points x $0.01/oz, $0.25/oz slippage and $7/lot roundtrip. Guard: spread <= min(35, 1.15x previous median) and current range <=2x ATR.
|Segment|Variant|Opportunities|Trades|Gross profit|Gross loss|Costs|Net|Closed DD|Days >=$50|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|Train|Base|232|53|126.41|-239.78|35.70|-149.07|155.85|0|
|Train|Guard|243|41|95.80|-189.62|25.17|-119.00|126.08|0|
|Holdout|Base|103|66|220.94|-239.19|48.67|-66.92|92.77|0|
|Holdout|Guard|111|51|185.66|-167.25|33.33|-14.92|50.89|0|
Train 2025-11-05 through 2026-06-14; holdout 2026-06-15 through 2026-11-05 UTC. Different opportunity counts arise from trade occupancy. The guard reduces loss and closed drawdown, but does not create positive expectancy. Reject entry strategy; guard remains research-only. Intrabar/tick drawdown and broker contract specifications unverified. No demo or live orders.
