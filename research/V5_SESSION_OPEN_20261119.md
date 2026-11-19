# V5 session opening-range experiment — 2026-11-19

Private Eplanet M15 CSV: 23,643 bars; chronological 60/40 split (14,185 / 9,458 bars). Data deliberately not committed.

New hypothesis: 12:00–14:00 UTC opening range contains price discovery; a close-confirmed break between 14:00–19:00 UTC may continue. Signal at candle close; entry at next candle open; 1.5R target, 1R stop; 8-bar maximum holding. Minimum stop distance $2/oz, maximum $12/oz, median prior 20 bar range *1.2. Equity starts $1000 per partition; risk 0.5% equity, 0.01-lot minimum, 0.10 maximum. If minimum lot exceeds risk, skip. Contract assumed 100 oz/lot.

Independent risk control: skip breakouts when signal bar range / prior 20-bar median range >2 or prior 4-bar maximum >3. Same holdout is used for risk-control comparison; NOT an independent validation of the control.

| Metric | Train | Holdout | Holdout with volatility guard |
|---|---:|---:|---:|
| Opportunities | 153 | 102 | 102 |
| Trades | 5 | 2 | 1 |
| Skipped | 147 | 100 | 101 |
| Gross USD | -23.66 | +2.46 | +7.20 |
| Estimated roundtrip cost USD | 4.00 | 1.60 | 0.80 |
| Net USD | -27.66 | +0.86 | +6.40 |
| Closed equity drawdown USD | 27.66 | 5.54 | 0 |
| Trading days | 156 | 104 | 104 |
| Days with net >= $50 | 0 | 0 | 0 |

Cost assumption: $0.80 per ounce roundtrip, including estimated spread, commissions and slippage, NOT verified with broker. Conservative stop-first on candles touching both TP and SL. OHLC-only model cannot validate tick execution, swap, margin, intrabar drawdown or news gaps. Data time interpreted UTC. The backtest script and full JSON ledger are locally generated, not yet synchronized to GitHub.

Decision: reject for demo activation. No real or demo orders placed.