# V5 failed-auction reversal — 2026-11-24
Input: private Eplanet-derived 23,643 M15 OHLC observations (ARTIN_EPLANET_REAL_23643_M15_OBSERVATIONS_PRIVATE.jsonl). Private data NOT committed.
Hypothesis: a sweep of the previous 12-bar extreme followed by a close back inside represents rejected liquidity-taking and can mean-revert within six bars. Independent guard excludes oversized bars and elevated ATR.
Split: nominal 2026-06-15 epoch boundary; source timezone offset not certified. Train and test separated chronologically. Next bar open entry, 1% current equity risk, 0.01 lot minimum, 0.15 lot cap, 100oz/lot, 1.5R target, 6-bar timeout, stop-first if both hit in same OHLC candle. Cost proxy $0.90/oz round trip (historical spread not available).
|metric|base train|base OOS|guard train|guard OOS|
|---|---:|---:|---:|---:|
|opportunities|1131|754|1131|754|
|trades|394|346|355|326|
|gross profit USD|1385.94|1016.74|1254.19|1028.35|
|gross loss USD|-1361.90|-1137.60|-1245.32|-1090.21|
|cost USD|460.80|376.20|423.90|370.80|
|net USD|-436.75|-497.07|-415.02|-432.67|
|max closed drawdown USD|471.82|500.18|451.10|439.40|
|days >= $50|0|0|0|0|
Guard reduces OOS loss by $64.40 but does not produce positive expectancy. Both entry versions REJECTED for demo.
Limitations: no certified UTC offset, no bid/ask ticks, cost proxy, OHLC path ambiguity, max intratrade drawdown not fully measurable. GitHub source is an independently readable reproduction script, not a verified CI run. No real/demo orders.
