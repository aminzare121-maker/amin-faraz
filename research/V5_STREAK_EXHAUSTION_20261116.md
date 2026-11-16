# V5 — three-candle exhaustion, 2026-11-16

Independent hypothesis: after three moderate same-direction M15 candles, enter reversal on next open and exit next close or at ATR(32) stop. Optional filter excludes high tick volume (>80th percentile of prior 32 bars) or spread >26 points.

Dataset: private Eplanet M15 CSV, 23,643 bars; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split at row 14185. No dataset uploaded.

Assumptions: 100 oz/lot, initial $1000, 1% equity risk, minimum 0.01 lot, maximum 0.20 lot; skip when risk-based size below 0.01; spread $0.26/oz + slippage $0.30/oz per side; commission assumed zero. Intrabar stop touch is pessimistically counted; gap-through-stop and live broker execution not modeled.

| OOS (104 dates) | Base | Risk filter |
|---|---:|---:|
| Raw opportunities | 1353 | 1353 |
| Executed trades | 480 | 0 |
| Gross P&L USD | -53.03 | 0 |
| Estimated cost USD | 412.80 | 0 |
| Net P&L USD | -465.83 | 0 |
| Closed-equity max drawdown USD | 469.05 | 0 |
| Days net >= $50 | 0 | 0 |

Training: base 402 trades net -387.49, filter 330 trades net -279.01. Filtering eliminated all OOS trades, which is not evidence of a profitable strategy. REJECT for demo. The full locally executed Python source and JSON output were produced as conversation artifacts; this commit contains the audit summary only.
