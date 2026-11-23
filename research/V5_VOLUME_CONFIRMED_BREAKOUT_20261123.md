# V5 volume-confirmed 24-bar breakout — 2026-11-23
Research-only; no MT5 orders. Source: private Eplanet M15 CSV, 23,643 bars; not committed.
Hypothesis: breakouts above/below prior 24-bar extremes accompanied by tick volume >=1.35x prior 24-bar median may reflect persistent order flow. Independent risk guard excludes oversized bars, elevated quoted spread and late UTC hours.
Fixed predeclared train/test cutoff 2026-06-15 UTC. Starting equity $1000, variable 0.01-lot increments, 0.75% risk budget, assumed 100 oz/lot. Stop 1.4 ATR, target 2.2 ATR, maximum 8 bars, pessimistic stop-first on ambiguous bars. Estimated transaction cost = lot*100*(0.60 USD/oz + recorded spread*0.01 USD/point); actual broker spread point scale, commissions, slippage, tick-path and margin constraints remain unverified.
| Variant | Period | Trades | Gross profit | Gross loss | Cost | Net | Closed DD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Base | Train | 36 | 104.04 | -135.37 | 32.91 | -64.24 | 74.80 | 0 |
| Base | Test | 25 | 85.82 | -85.74 | 24.08 | -24.00 | 43.89 | 0 |
| Guard | Train | 19 | 71.28 | -64.78 | 17.36 | -10.86 | 29.11 | 0 |
| Guard | Test | 19 | 112.24 | -54.68 | 17.78 | +39.77 | 29.74 | 0 |
The initial local diagnostic counted 857 raw qualifying bars over the full dataset (not split-specific and not executable trades). Do not interpret as test opportunities. Guard improves test P&L by $63.77 and reduces closed DD $14.15, but test has only 19 trades and no $50 days. Research gate FAILED; no demo deployment. Intrabar DD not measured. No hyperparameter search or robust walk-forward validation.
Reproduce: python research/v5_volume_confirmed_breakout.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
