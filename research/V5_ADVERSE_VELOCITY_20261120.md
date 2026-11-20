# V5 adverse-velocity early-exit research — 2026-11-20

Input: private Eplanet M15 CSV, SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`; 23,643 bars; chronological 60/40 split. Local executable: `v5_adverse_velocity_20261120.py` (not yet committed).

**New economic hypothesis:** after entry, if the second completed 15-minute candle closes more than 0.50 initial stop distance against the position, exit at that candle close, otherwise retain existing 3-bar stagnation exit. Both variants use the same 45% adverse-wick gate. Signals use only completed candles.

Assumptions: initial $1,000, variable 0.01–0.10 lot, 1% risk cap, $87/lot estimated round-trip costs, stop-first OHLC, 12-bar maximum holding period. No real tick execution.

| Metric | Train baseline | Train new | Holdout baseline | Holdout new |
|---|---:|---:|---:|---:|
| Opportunities | 2061 | 2061 | 1526 | 1526 |
| Trades | 137 | 138 | 165 | 169 |
| Gross USD | 168.84 | 193.55 | 276.95 | 209.09 |
| Costs USD | 122.67 | 123.54 | 143.55 | 147.03 |
| Net USD | +46.17 | +70.01 | +133.40 | +62.06 |
| Closed drawdown USD | 128.41 | 128.26 | 54.11 | 78.60 |
| Days net >= $50 | 1/156 | 1/156 | 0/104 | 0/104 |

**Decision: REJECT.** New exit improves training net by $23.84 but worsens holdout net by $71.34 and holdout drawdown by $24.49. No demo orders. $50 net per trading day requirement not met. Data private, not committed. Source and result JSON generated locally, pending GitHub code upload.