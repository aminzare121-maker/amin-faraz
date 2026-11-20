# V5 liquidity sweep — 2026-11-20
Hypothesis: sweep of prior 12-bar high/low by >0.1 trailing median TR, close back inside with 70% rejection position; reverse at next M15 open. Exit at 1.2 median TR stop (clipped $2.5-$14), 1.5R target or 8 bars. Stop-first OHLC. No lookahead for signal. Split first 60% train, last 40% holdout. Contract 100 oz/lot, lot 0.01-0.1, risk <=min($10,1% equity), round-trip estimated $87/lot. Separate guard halts new entries once realized daily net <=-$15. Starting equity $1000 independently per segment.

Data SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; candles 23643; split 14185.

| Segment | Variant | Opportunities | Trades | Gross USD | Estimated costs USD | Net USD | Closed-equity DD USD | Days >=$50 / total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | base | 566 | 206 | 39.18 | 183.57 | -144.39 | 283.05 | 0/156 |
| train | guard | 566 | 193 | 42.19 | 171.39 | -129.20 | 257.41 | 0/156 |
| holdout | base | 434 | 247 | -16.61 | 214.89 | -231.50 | 249.81 | 0/104 |
| holdout | guard | 434 | 233 | 13.03 | 202.71 | -189.68 | 214.27 | 0/104 |

Research decision: reject signal. Guard reduces losses but does not produce profitable system. Cost estimates are not independently verified with broker execution; intrabar order is unknown. No demo/live trades. Private data not committed. Local reproducibility script and JSON generated in run, not yet pushed to repository.
