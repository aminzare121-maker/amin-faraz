# V5 volume surprise — 2026-11-18

New hypothesis: unusually high tick-volume (>=1.8x trailing 64-bar median), a large directional M15 candle (range >=1.2x lagged median TR), body >=65% of range and close near extreme might lead to follow-through. Signal uses closed candle only; entry next M15 open. No COT/sentiment.

Data: private Eplanet M15 CSV, 23,643 candles. Chronological 60/40 split; final 104 trading days out of sample. No parameters optimized on test set. Capital $1,000, variable lot, 1% nominal stop risk, SL 1.25x lagged median TR, TP 1.8x, max 6 candles. Cost estimate: recorded spread in points /100 + $0.30 adverse slippage per ounce, plus $7 per lot commission. Conservative stop-first when both touched in one candle. OHLC path unknown.

| Metric | Base | Independent risk guard (ATR<=7, volume ratio<=4, spread/ATR<=.07) |
|---|---:|---:|
| Opportunities | 96 | 96 |
| Executed simulated trades | 51 | 42 |
| Gross P/L | -$155.60 | -$71.27 |
| Estimated costs | $37.97 | $28.99 |
| Net P/L | -$193.57 | -$100.26 |
| Closed equity max drawdown | $193.87 | $110.19 |
| Approx intrabar drawdown | $203.17 | $117.06 |
| Days net >=$50 | 0/104 | 0/104 |

**REJECTED**: neither passes profitability or $50/day goal. Guard reduces losses but does not create a profitable edge. No demo/live trading. Local reproducible script and trade ledger generated; source CSV and ledger not committed because private. Limitations: approximated execution, M15 intrabar ambiguity, estimated broker fees, no real tick-level floating DD. Research only.
