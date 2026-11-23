# V5 trend pullback — 2026-11-23
Private source: Eplanet_M15_20251105_20261105_merged.csv, 23,643 M15 rows. No market data committed.
Hypothesis: continuation following two countertrend candles and a recovery candle in the direction of EMA20/EMA80 trend. Independent guard: spread <=35 points, previous candle range/ATR <=1.5, and no entry at 21-23 UTC.
Split: before 2026-06-15 train; from that date test. Fill next candle open; stop 1.2 ATR; target 2.4 ATR; max eight candles; pessimistic stop-first OHLC. 1% balance risk, lot 0.01 increments, max .10, assumed contract 100 oz/lot. Costs: spread points assumed .01 price unit, slippage .20 USD/oz roundtrip and commission 7 USD/lot roundtrip. These assumptions require broker verification.
Results (local execution):
Alpha train: 1005 opportunities, 211 trades, gross profit 873.32, gross loss -863.45, costs 122.00, net -112.13, max closed DD 230.55.
Alpha OOS: 614 opportunities, 272 trades, gross profit 1103.04, gross loss -1117.86, costs 180.08, net -194.89, max closed DD 280.88, days >=50 net: 0.
Guard train: 1008 opportunities, 176 trades, gross profit 825.68, gross loss -671.02, costs 97.98, net +56.67, max closed DD 165.53.
Guard OOS: 639 opportunities, 177 trades, gross profit 733.64, gross loss -757.78, costs 107.27, net -131.41, max closed DD 211.93, days >=50 net: 0.
Opportunity counts differ across variants because an open trade blocks new signals.
The guard reduces OOS loss by 63.48 USD and closed drawdown by 68.95 USD, but neither method passes profitability. Do not enable demo orders.
Limitations: no tick-level intrabar drawdown, no independently verified broker contract or fills, no GitHub CI run. Local test script and repository reproduction script implement same logic but GitHub copy has not yet been independently executed.
