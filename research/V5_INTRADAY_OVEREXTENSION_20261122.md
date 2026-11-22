# V5 — Intraday overextension failure (2026-11-22)

Source: private Eplanet M15 merged CSV (23,643 bars). Private data intentionally excluded. Fixed out-of-sample starts 2026-06-15 UTC, 104 trading dates.

Hypothesis: after 8-bar displacement exceeding 1.8 ATR, failed breach of the preceding 8-bar extreme followed by opposite candle body predicts short-term reversal. Entries next candle open, 7–19 UTC; stop 1.2 ATR, target 1.8 ATR, max 8 candles. Risk 1% equity, variable lots rounded down to 0.01. No trade if minimum lot violates risk. Contract assumed 100 oz/lot. Spread points assumed 0.01 USD; plus 0.12 USD/oz roundtrip slippage and 7 USD/lot commission. Stop-first on ambiguous bars. No tick verification.

| OOS | Baseline | Stop after two daily losses |
|---|---:|---:|
| Opportunities | 166 | 167 |
| Trades | 90 | 82 |
| Blocked | 76 | 85 |
| Gross wins | $401.50 | $355.80 |
| Gross losses | -$417.56 | -$383.94 |
| Costs | $45.74 | $41.66 |
| Net | -$61.80 | -$69.80 |
| Closed drawdown | $127.65 | $132.81 |
| Active days | 56 | 54 |
| Days >= $50 net | 0/104 | 0/104 |

Both rejected for demo. Loss guard worsened net and drawdown. The local research script and trade ledger are not yet committed; no GitHub CI validation. Equity reset to $1000 at OOS start. Intrabar drawdown not measured. No real/demo orders.
