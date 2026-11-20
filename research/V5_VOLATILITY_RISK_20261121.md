# V5 volatility risk sizing — 2026-11-21
Research only; no demo/live orders.

Hypothesis: during high volatility (ATR from completed bars above trailing 96-ATR 75th percentile), reduce position risk to 50% or 25% of baseline. Role: loss reduction, not signal generation.

Dataset: private Eplanet M15, 23,643 rows, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split. Initial balance $1,000, variable 0.01-lot-step position sizing; $87 roundtrip per 1 lot assumed; conservative stop-first within OHLC candles. Entry only on next bar open. No delayed sentiment/COT.

| Sample | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Max closed DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 2059 | 137 | 168.84 | 122.67 | 46.17 | 128.41 | 1/156 |
| Train | Half risk | 2059 | 131 | 165.19 | 117.45 | 47.74 | 121.44 | 1/156 |
| Train | Quarter risk | 2059 | 131 | 165.19 | 117.45 | 47.74 | 121.44 | 1/156 |
| Holdout | Base | 1517 | 165 | 276.95 | 143.55 | 133.40 | 54.11 | 0/104 |
| Holdout | Half risk | 1517 | 161 | 259.04 | 140.07 | 118.97 | 58.70 | 0/104 |
| Holdout | Quarter risk | 1517 | 161 | 259.04 | 140.07 | 118.97 | 58.70 | 0/104 |

Decision: reject both high-volatility risk scaling variants. Quarter and half risk have identical outcomes because 0.01-lot minimum / flooring makes the intended different exposure ineffective; this is an implementation/market-size limitation, not independent validation. Baseline is a research comparator, not demo approved. No claim of $50 net daily success.

Reproducibility: local script v5_volatility_risk_20261121.py and JSON generated in conversation artifacts. The script is NOT yet committed to this branch; this report alone is a GitHub record. OHLC cannot validate tick order, floating DD, or actual execution costs. No private data uploaded.