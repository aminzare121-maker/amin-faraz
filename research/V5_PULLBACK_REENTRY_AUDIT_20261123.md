# V5 Trend pullback / reclaim — 2026-11-23
Dataset: private Eplanet M15 CSV (23643 rows), not committed. Run: python research/v5_pullback_reentry_audit.py /path/to/Eplanet_M15_20251105_20261105_merged.csv

Hypothesis: a short countertrend candle followed by reclaim of its extreme in an EMA48 trend captures renewed directional demand. Guard separately excludes extreme or weak range and spreads >30.

Train before 2026-06-15; out-of-sample from 2026-06-15. Start $1000, dynamic lots 0.01 increments capped 0.10, risk budget 1% equity divided by 1.2 ATR; 4-bar time exit. Estimated costs: spread points x $0.01/oz, $0.10/oz slippage and $7/lot round trip. No stop fill simulation; risk budget is sizing proxy, NOT a hard loss limit.

| Model | Period | Trades | Gross profit | Gross loss | Costs | Net | Closed DD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Entry | train | 146 | 487.35 | -708.46 | 67.69 | -288.80 | 388.59 | 0 |
| Entry | OOS | 53 | 169.71 | -196.52 | 30.10 | -56.91 | 98.59 | 0 |
| Guard | train | 89 | 239.05 | -361.73 | 38.92 | -161.60 | 215.75 | 0 |
| Guard | OOS | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Caveats: guard has no OOS trades, not evidence of profit; OOS equity carries training losses. Commission/spread conversion not verified against contract; no tick drawdown, intrabar stops, actual broker fills, or independent CI. No demo or live activation. Rejected as profit engine.
