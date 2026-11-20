# V5 entry confirmation — 2026-11-20

Hypothesis: wait for one fully closed bar in signal direction before entering at following open, to filter false continuation. This is a new execution-timing test, not a new signal.

Dataset SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23,643 Eplanet M15 bars; chronological 60/40 split (14,185 index).

Assumptions: initial equity $1,000; variable 0.01–0.1 lots, 1% equity risk cap; estimated round-trip friction $87 per lot; OHLC stop-first if both levels touched; 12-bar hold; no tick execution validation.

| Holdout (104 trading days) | Immediate | One-bar confirmation | Confirmation + daily -$15 guard |
|---|---:|---:|---:|
| Opportunities | 1526 | 1526 | 1526 |
| Trades | 177 | 123 | 117 |
| Gross P&L USD | 169.61 | 79.19 | 54.64 |
| Costs USD | 153.99 | 107.01 | 101.79 |
| Net USD | +15.62 | -27.82 | -47.15 |
| Closed-equity drawdown USD | 138.77 | 119.29 | 148.70 |
| Days net >= $50 | 1 | 0 | 0 |

Train net: immediate -$20.94; confirmation +$79.94; confirmation+guard +$85.96. Train-only improvement did not generalize. Both proposed variants REJECTED. No demo/live orders. No private data uploaded.

The local executable source and machine-readable JSON are generated separately; this commit contains the audit summary only, not a claim that the code is uploaded. OHLC intrabar ambiguity and broker friction remain unverified.
