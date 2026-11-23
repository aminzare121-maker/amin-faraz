# V5 failed-auction reversal — 2026-11-23

Dataset: Eplanet M15, 23,643 candles; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Private dataset NOT committed.

Hypothesis: candle probes previous 16-bar high/low by 0.15 ATR then closes back inside; enter next bar open in reversal direction. Risk 1% equity, variable lot floor 0.01, max 0.10. Conservative stop-first OHLC, 6-bar maximum holding. Assumed 100oz/lot, 0.01 USD/point, $0.25/oz slippage and $7/lot roundtrip commission; broker terms not verified.

| Period | Variant | Opportunities | Trades | Gross profit | Gross loss | Costs | Net | Max closed DD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | base | 506 | 129 | 401.39 | -490.93 | 78.99 | -168.53 | 175.21 | 0 |
| Train | guard | 506 | 117 | 342.22 | -447.29 | 71.09 | -176.16 | 182.84 | 0 |
| Holdout | base | 367 | 123 | 309.25 | -511.24 | 82.51 | -284.50 | 307.62 | 0 |
| Holdout | guard | 370 | 113 | 295.61 | -456.74 | 73.11 | -234.24 | 259.74 | 0 |

Guard: exclude spread > 1.15x trailing median or bar range >1.8x trailing ATR. Opportunities differ due to position occupancy. Many candidates skipped because 0.01 minimum lot exceeds 1% risk budget. Intrabar/tick drawdown unavailable. Neither variant passes the $50/day criterion. NO demo/live trading authorized.

Reproduction code and JSON were executed in the assistant container; source code was not committed here. No independent GitHub CI run.
