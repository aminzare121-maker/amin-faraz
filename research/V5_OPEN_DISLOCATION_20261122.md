# V5 open dislocation — 2026-11-22

Research only; NOT approved for MT5 demo or live.

Source: private Eplanet M15 CSV, 23,643 rows, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Data intentionally excluded from GitHub.

Hypothesis: small 15-minute open discontinuities (12–65% of lagged ATR) following uninterrupted 900-second bars may predict mean reversion (fade) or continuation (follow). Entry uses only candle-open and earlier information. Guard excludes high-volume or oversized prior candle.

Chronological split 60% / 40%, OOS 104 trading days. Starting equity $1,000; variable 0.01-step lots, minimum 0.01; 100 oz/lot; 1% risk; assumed $0.15 adverse entry slippage plus $45/lot round-trip friction; 0.75 ATR or $2 stop, 1.5R target, 4-bar maximum hold; stop-first OHLC approximation. No tick-level verification.

| Mode | Opportunities | Trades | Gross gains | Gross losses | Costs | Net | Closed DD | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Fade | 10 | 10 | 59.11 | -36.19 | 6.30 | +16.63 | 25.54 | 0 |
| Fade + guard | 10 | 4 | 13.17 | -22.13 | 2.70 | -11.66 | 16.61 | 0 |
| Follow | 10 | 10 | 33.19 | -53.47 | 6.30 | -26.58 | 34.51 | 0 |
| Follow + guard | 10 | 4 | 33.19 | -8.78 | 2.70 | +21.71 | 9.68 | 0 |

The guard improves the follow subset but sample size (four trades) is inadequate for an edge claim; no variant meets the $50 net/day objective. Reject all variants for demo.

Limitations: proxy costs; open execution cannot be guaranteed; stop-first OHLC; no true intrabar equity drawdown; only one chronological split. Do not publish the raw Eplanet data. Local reproducible script and JSON exist in run artifacts, but are not part of this commit.
