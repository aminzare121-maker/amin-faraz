# V5 directional close-location test — 2026-11-21

Research only; no MT5 orders. Hypothesis: a signal candle closing near its directional extreme may indicate stronger continuation. Directional close location = (close-low)/(high-low) for buy, (high-close)/(high-low) for sell, known at signal-bar close. Test >=0.60 and >=0.80 independently against unchanged comparator. Roles: entry selection vs loss reduction evaluated through net PnL and drawdown.

Private Eplanet M15 CSV (23,643 candles), chronological 60/40 split. Initial $1,000, variable 0.01-lot step, round-trip cost estimate $87/lot, stop-first OHLC assumptions, next-bar open entry. Baseline includes adverse-wick exclusion and three-bar stagnation exit.

| Sample | Variant | Opportunities | Trades | Gross $ | Estimated costs $ | Net $ | Max closed DD $ | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 2059 | 137 | 168.84 | 122.67 | 46.17 | 128.41 | 1/156 |
| Train | CLV >=0.60 | 2059 | 123 | 126.91 | 110.49 | 16.42 | 94.58 | 1/156 |
| Train | CLV >=0.80 | 2059 | 99 | 189.53 | 89.61 | 99.92 | 53.64 | 1/156 |
| Holdout | Base | 1517 | 165 | 276.95 | 143.55 | 133.40 | 54.11 | 0/104 |
| Holdout | CLV >=0.60 | 1517 | 149 | 161.12 | 129.63 | 31.49 | 70.19 | 0/104 |
| Holdout | CLV >=0.80 | 1517 | 113 | 73.15 | 98.31 | -25.16 | 66.55 | 0/104 |

Decision: reject both filters. Apparent training improvement for 0.80 does not generalize. No $50/day qualification. Counts of opportunities are signal occurrences, not necessarily executable positions. Costs are estimates; no tick-by-tick intrabar order, actual entry spread, floating DD, or live execution validation. CSV is NOT committed.

Reproduce locally: `python research/v5_close_location_20261121.py --csv /private/path/Eplanet_M15_20251105_20261105_merged.csv --out /tmp/close_location.json`. Compare JSON values with this table; execution of committed GitHub version has not independently been verified.
