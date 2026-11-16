# V5 absorption reversal — 2026-11-17

Research-only, NOT approved for MT5 demo.

Hypothesis: unusually high tick volume with a narrow candle body relative to range signals absorption; trade opposite preceding four-bar momentum at next candle open, exit after three candles or stop at 1.2× prior 24-bar median range. Risk filter excludes candle range >2.5× prior median or tick volume >3× prior 48-bar median. Only past/closed candles used. 60/40 chronological split, 23,643 Eplanet M15 rows.

## Out of sample

| Metric | Baseline | Risk filter |
|---|---:|---:|
| Raw opportunities | 59 | 59 |
| Trades | 50 | 44 |
| Gross USD | 40.06 | 112.01 |
| Estimated costs USD | 44.72 | 39.56 |
| Net USD | -4.66 | +72.45 |
| Closed-equity max drawdown USD | 70.69 | 54.70 |
| Active days | 39 | 35 |
| Days >= $50 net | 0 | 0 |
| Lot range | 0.01–0.02 | 0.01–0.02 |

Training baseline: 95 trades, net -$9.16, closed drawdown $144.27.

Assumptions: $1000 starting equity, 100 oz/lot, $0.86 per ounce all-in estimated round-trip cost, 1% equity risk target with minimum 0.01 lot (minimum may exceed risk target), stop prioritized within OHLC bar. No tick replay, broker fill, real commission, spread time series, margin validation or intrabar equity drawdown. Results exploratory; no tuning of filter on holdout permitted. Positive filtered net is insufficient: zero days reach the $50 target. No trade execution.

Code artifact generated locally: v5_absorption.py; JSON result: v5_absorption_results.json. These files are not yet committed to GitHub. Private Eplanet data must not be committed.
