# V5 shock absorption — 2026-11-19
Source: private Eplanet M15 CSV (23643 rows), NOT committed.
Hypothesis: unusually large true range (>1.8x prior 48-bar median) with tick volume (>1.5x prior 48-bar median), failed break of prior 12-bar extreme. Fade on next candle open. Fixed rules; no holdout tuning.
Risk: initial equity $1000 per split; lot floor to 0.01, 0.01–0.10, 1% equity risk with stop clipped to $2–$8/oz, 1.5R target, six-bar timeout, stop-first OHLC ambiguity.
Proxy friction $0.65/oz round trip, NOT verified Eplanet spread/slippage/commission. No swaps or margin validation.
Chronological 60/40 split.
| Metric | Train base | Holdout base | Holdout daily loss guard |
|---|---:|---:|---:|
| Trades | 104 | 73 | 73 |
| Gross USD | -201.39 | +9.42 | +9.42 |
| Proxy costs USD | 83.20 | 70.20 | 70.20 |
| Net USD | -284.59 | -60.78 | -60.78 |
| Max closed equity drawdown USD | 285.70 | 119.46 | 119.46 |
| Active days | 66 | 56 | 56 |
| Days >= $50 net | 0 | 0 | 0 |
Independent daily guard (stop new entries after day's realized PnL <= -$15) did not improve holdout.
Rejected. No demo or live trades. No private market data uploaded.
Local reproducibility file: v5_shock_absorption_20261119.py (not yet committed); JSON trade ledger local only.
Limitations: bar-only stop-first model, uncertain execution fees, swaps, margin, and intra-bar drawdown.