# V5 exit-horizon experiment — 2026-11-20

Hypothesis: directional efficiency momentum alpha decays rapidly, so shorter holding periods might improve risk-adjusted net results. This tests an **execution/exit change** to the prior efficiency-pause entry, not another identical signal rerun.

Data: Eplanet 23,643 M15 bars; CSV SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Chronological 60/40 split, 156 training days and 104 holdout days. Signals use only completed OHLC bars. Enter next bar open. Stop-first intrabar, 1.5 median TR stop, 1% equity / $10 risk cap, 0.01–0.1 lot, 100 oz/lot. Estimated round-trip fee $87/lot, not verified Eplanet execution.

| Variant | Train net | Holdout trades | Holdout gross | Holdout fees | Holdout net | Holdout max closed DD | Holdout days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 12 bars, 1.8R (control) | +72.86 | 158 | +233.52 | 137.46 | +96.06 | 119.54 | 1/104 |
| 6 bars, 1R | -6.31 | 211 | +221.78 | 183.57 | +38.21 | 57.70 | 0/104 |
| 4 bars, 1R | +4.46 | 223 | +131.73 | 194.01 | -62.28 | 142.92 | 0/104 |

Each variant observed 2070 training and 1526 holdout signal bars before overlap and minimum-lot restrictions. Shortening to six bars reduces holdout drawdown but lowers net profit, increases trade count and estimated fees, and fails training. Four bars fails holdout. Neither is suitable for demo.

Limitations: no tick-level fill, spread variability, slippage stress test, or contract specification confirmation. Max DD is closed-equity DD, not intratrade. This report records an actual local Python run; the local Python source and full JSON were not committed in this change. Private CSV is not included. No orders placed.