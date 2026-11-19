# V5 CLV persistence — 2026-11-19

Hypothesis: persistent close-location pressure over three completed M15 candles predicts next-bar continuation. Trend alignment over prior bars. Parameters selected on first 60%; final 40% untouched until evaluation. Entry at next bar open. Conservative stop-first OHLC execution. Starting capital $1000, variable lots floored to 0.01, max 0.10, risk target $10, assumed 100 oz/lot and $0.65/oz roundtrip costs. Separate volatility guard tested without OOS tuning.

Data: private Eplanet M15 CSV, 23643 rows, SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`; no private data committed.

OOS 104 days; threshold 0.6 selected on training.

| Metric | Base | Volatility guard |
|---|---:|---:|
| Signal opportunities | 740 | 740 |
| Trades | 467 | 450 |
| Gross USD | 58.88 | 67.75 |
| Estimated cost USD | 340.60 | 329.55 |
| Net USD | -281.72 | -261.80 |
| Closed-equity drawdown USD | 396.70 | 391.71 |
| Approx intrabar drawdown USD | 401.48 | 395.72 |
| Days >= $50 net | 1/104 | 1/104 |

Both variants rejected. Costs are modeled, not verified Eplanet fills; M15 bars cannot validate tick-level execution. No demo/live trading enabled. Reproduction script exists locally as `v5_clv_persistence_20261119.py` but is not committed in this commit; do not treat this report as independent code reproduction.