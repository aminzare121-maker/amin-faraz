# V5 compression-expansion research — 2026-11-23

New hypothesis: after six-bar range compression (range <= 2.1 * lagged ATR20), a close beyond the preceding six-bar extreme can produce directional continuation. Signal is evaluated at candle close; entry at next bar open.

Training: before 2026-06-15 UTC. Holdout: from 2026-06-15 UTC. Private Eplanet M15 CSV is NOT committed.

Risk model: initial equity $1,000 per segment, variable lots floored to 0.01, 1% stop-risk budget, maximum 0.10 lots; 100 oz/lot assumed. SL 1.1 ATR (minimum $2/oz), TP 1.8x SL, maximum 8 bars. Stop first if both stop and target touched. Estimated round-trip cost: recorded spread points * $0.01/oz + $0.20/oz slippage + $7/lot. No tick-level fills or broker contract verification.

| Metric | Train alpha | Holdout alpha | Train guard | Holdout guard |
|---|---:|---:|---:|---:|
| Opportunities | 1100 | 777 | 1214 | 862 |
| Trades | 354 | 383 | 151 | 246 |
| Blocked | 746 | 394 | 1063 | 616 |
| Gross wins USD | 1601.06 | 1633.86 | 546.34 | 1153.24 |
| Gross losses USD | -1571.07 | -1552.78 | -711.85 | -1035.29 |
| Estimated costs USD | 212.78 | 250.72 | 86.04 | 145.82 |
| Net USD | -182.78 | -169.63 | -251.55 | -27.87 |
| Max closed drawdown USD | 325.32 | 300.54 | 295.65 | 122.28 |
| Active days | 107 | 96 | 67 | 98 |
| Days >= $50 net | 0 | 1 | 0 | 0 |

Guard separately filters UTC hours outside 07–16, ATR > 1.8x its lagged 96-bar median, and spread > 35 points. It reduced holdout losses and closed drawdown, but remains unprofitable. Opportunity counts differ because the backtester excludes signals while trades are active.

**Decision:** Reject alpha and guard as deployable strategy. Target $50 net every trading day not met. No demo or live trading authorized.

Local reproducible files: v5_compression_expansion_20261123.py and v5_compression_expansion_20261123.json; these have not been uploaded to this branch. No independent CI verification.