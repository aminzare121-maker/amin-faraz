# V5 run-length exhaustion — 2026-11-22
Private Eplanet M15 CSV: 23,643 candles; not committed.
New hypothesis: fade four consecutive same-direction M15 candles at next bar open, exit after four bars. Independent guard: reject final signal candle range >=1.5x lagged 20-bar ATR.
Training: before 2026-06-15. OOS: from 2026-06-15. Price-only signal, no future leakage in signal.
Estimated round-trip cost per ounce: reported spread points * 0.01 USD plus 0.30 USD. Contract assumption 100 oz/lot, 0.01 lot step; 1% equity risk proxy / (2 ATR), cap 0.10 lots. Reset OOS capital to USD 1000. No intrabar stops, no actual broker fills.
Training baseline: 1484 observations, mean -0.903875 USD/oz; guard 1193, mean -1.193009 USD/oz. Entry authorization gate >=100 training samples and mean >0.30 USD/oz: BOTH FAIL.
OOS diagnostic baseline: 1082 raw opportunities, 30 sized non-overlapping trades, gross profit 74.07, gross loss -103.78, estimated costs 22.00, net -51.71, max closed DD 54.47; 0 days >=50 USD.
OOS diagnostic guard: 880 raw opportunities, 23 trades, gross profit 27.39, gross loss -77.42, estimated costs 17.24, net -67.27, max closed DD 69.54; 0 days >=50 USD.
Both strategies REJECTED; authorized trades 0. No demo or live orders.
Limitations: diagnostic has no intrabar stop execution, sizing risk is a proxy, assumed broker contract/point value and costs require verification. No tick-level drawdown. The training gate precludes trading regardless of diagnostic OOS results.
