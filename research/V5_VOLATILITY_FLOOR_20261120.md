# V5 volatility floor research — 2026-11-20

Data SHA256: `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`; 23643 M15 bars; 60/40 chronological split. Data intentionally not committed.

Hypothesis: exclude signals when lagged 32-bar median true range is below 80% of its preceding 96-bar median, to avoid weak moves where execution friction dominates. No COT/sentiment.

| Holdout, 104 trading days | Baseline | Volatility floor | Floor + daily -$15 guard |
|---|---:|---:|---:|
| Opportunities | 1526 | 1267 | 1267 |
| Trades | 177 | 130 | 126 |
| Gross USD | 169.61 | 112.53 | 74.83 |
| Costs USD | 153.99 | 113.10 | 109.62 |
| Net USD | +15.62 | -0.57 | -34.79 |
| Closed-equity max DD USD | 138.77 | 112.87 | 140.47 |
| Days >= $50 | 1 | 1 | 1 |

Training net USD: baseline -20.94; floor -56.78; floor + guard -61.98. Capital $1000, dynamic 0.01–0.10 lots, $87 roundtrip per lot estimated, stop-first OHLC fill assumptions. No verified tick execution, actual broker spread or slippage. Baseline net differs from earlier reports: reconcile implementation before deployment. Filter reduces drawdown but harms profitability; guard also harms it. Reject both. No demo or real orders. Reproduce with `python research/v5_volatility_floor_20261120.py --csv <PRIVATE_EPLANET_CSV> --out results.json`.
