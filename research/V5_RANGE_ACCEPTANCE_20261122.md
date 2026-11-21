# V5 range acceptance — 2026-11-22

Hypothesis: a close beyond the previous 12 M15 bars with strong close location (above 85% / below 15%) and tick volume >=1.25x previous 32-bar median indicates directional acceptance. Enter next bar open; ATR20-based stop max(0.75 ATR, $1.20/oz), TP 1.5R, maximum 12 bars, conservative stop-first on ambiguous bars. Independently test an early adverse-close exit after 2 bars. Risk 1% equity, initial $1000, variable lots 0.01 steps, maximum 0.05 lot. Estimated roundtrip cost $0.45 per ounce. 1 lot assumed 100 oz. Historical data private, not committed.

Dataset: Eplanet_M15_20251105_20261105_merged.csv, 23,643 M15 bars. Chronological 60/40 split at row 14,185. Backtest executed locally in Python. No broker tick execution or real spread validation.

| Sample | Method | Opportunities | Min-lot rejected | Trades | Gross profit | Gross loss | Cost | Net | Closed drawdown | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 188 | 45 | 143 | 603.95 | -628.30 | 82.35 | -106.70 | 212.99 | 0 |
| Train | Protective exit | 188 | 45 | 143 | 581.69 | -615.56 | 82.35 | -116.22 | 210.60 | 0 |
| OOS | Base | 157 | 18 | 139 | 541.54 | -567.45 | 76.95 | -102.86 | 185.68 | 0 |
| OOS | Protective exit | 157 | 18 | 139 | 515.50 | -552.63 | 76.50 | -113.63 | 199.36 | 0 |

**Decision: reject both.** Neither produces a net positive edge or achieves the $50/day objective. No demo or live trading enabled. Local Python code and JSON output were generated in this run; they are not committed in this branch. Research report only. Drawdown is closed-equity drawdown, not tick-level floating drawdown. Costs are modeled, not verified against Eplanet execution.