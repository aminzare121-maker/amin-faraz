# V5 low-participation drift reversal — 2026-11-22

Hypothesis: a three-bar directional drift of at least 0.8 ATR with current tick volume below 65% of the trailing 32-bar median is vulnerable to short-horizon mean reversion. Signal uses only completed M15 bars; enter next open, stop and target at 1.1 ATR, exit after five bars maximum. Variable lot risk sizing: 1% equity, 0.01 increments, cap 0.30 lots. Independent guard rejects candles wider than 1.8 ATR.

Private Eplanet CSV: 23,643 M15 candles, NOT uploaded. Out-of-sample starts 2026-06-15 with independently reset $1000 equity. Assumptions: 0.01 lot=1 oz, $0.56/oz estimated roundtrip friction, stop-first on ambiguous candles. No tick execution validation.

| OOS | Baseline | Range guard |
|---|---:|---:|
| Opportunities | 225 | 227 |
| Blocked | 0 | 5 |
| Trades | 207 | 205 |
| Gross profits USD | 702.52 | 687.07 |
| Gross losses USD | -578.30 | -579.47 |
| Estimated friction USD | 146.16 | 143.92 |
| Net USD | -21.94 | -36.32 |
| Max closed drawdown USD | 59.10 | 66.95 |
| Trading days | 97 | 96 |
| Days net >= $50 | 0 | 0 |

Both fail. The guard worsened results. Do not enable demo or live trades. Local Python and JSON artifacts generated; not yet committed as code. Actual Eplanet contract specifications and costs unverified.