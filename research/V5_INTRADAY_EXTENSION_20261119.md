# V5 intraday extension mean-reversion — 2026-11-19

Private Eplanet M15 merged CSV: 23643 rows. Do not commit dataset.

Hypothesis: fade an unusually large 12:00–16:00 UTC move at 16:00 UTC, close at 19:00 UTC, with 2x prior 24-bar high-low mean stop. Eligibility: move >=1.5x prior range. Lot rounded to 0.01 with $15 nominal stop risk, max 0.10 lot. Conservative stop-first OHLC. Estimated roundtrip friction $0.66/0.01 lot. Chronological 60/40 split: 2026-06-15 05:45 UTC. Guard independently suppresses entry after three consecutive losing signals (past outcomes only).

| metric | train base | test base | train guard | test guard |
|---|---:|---:|---:|---:|
| trades | 18 | 26 | 14 | 18 |
| gross USD | -83.74 | -20.96 | -80.49 | 19.64 |
| costs USD | 11.88 | 17.16 | 9.24 | 11.88 |
| net USD | -95.62 | -38.12 | -89.73 | 7.76 |
| max closed drawdown USD | 111.78 | 107.81 | 105.89 | 65.58 |
| days >= $50 | 0 | 1 | 0 | 1 |

Guard was examined on holdout; apparent improvement is not independently validated. Not suitable for demo. Costs are assumptions, OHLC lacks tick ordering, margin/execution unverified. Initial capital $1000; goal $50 net per trading day not met. No live trades. Local reproducible script and results saved as v5_intraday_extension_20261119.py / _results.json; script not yet committed.
