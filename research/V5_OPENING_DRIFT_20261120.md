# V5 opening drift — 2026-11-20

New hypothesis: at 08:00 UTC, prior four M15 candles' direction predicts the next hour if absolute 4-bar move exceeds 0.65 times lagged 32-bar ATR. Enter at following M15 open, hold four bars or stop at 1.5 ATR, stop-first OHLC. Risk target $12, 0.01-lot increments, max 0.10 lot. Assume $100 per $1 move per 1 lot; $0.66 per 0.01 lot roundtrip. No parameter optimization on holdout. Guard: prior ATR below rolling 20-day 80th percentile.

Private merged Eplanet M15: 23,643 bars; 60/40 chronological split at epoch 1781502300; capital $1,000. Do not commit market data.

| Metric | Train base | Train guard | Test base | Test guard |
|---|---:|---:|---:|---:|
| trades | 45 | 43 | 44 | 44 |
| gross USD | -96.93 | -112.09 | 89.92 | 89.92 |
| cost USD | 31.02 | 29.70 | 29.04 | 29.04 |
| net USD | -127.95 | -141.79 | 60.88 | 60.88 |
| max closed drawdown USD | 149.48 | 149.48 | 39.31 | 39.31 |
| days >= $50 | 0/156 | 0/156 | 0/104 | 0/104 |

143 candidate opportunities overall, 89 filled trades. Out-of-sample positive net but train negative, 0 target days. Guard has no out-of-sample effect. REJECT for demo. Friction assumed, M15 stop-first approximation, margin and Eplanet tick execution unverified. Local code: v5_opening_drift_20261120.py, results JSON and trades CSV; code not yet uploaded to repository. No orders placed.
