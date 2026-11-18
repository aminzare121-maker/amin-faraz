# V5 — failed-auction reclaim — 2026-11-18

Hypothesis: a 15-minute candle breaches the preceding 12-bar extreme but closes back inside with a rejection wick >55% of its range; order-flow exhaustion may generate a short-term reversal. Signal only after candle close; fill next bar open. ATR proxy: prior 24-bar median true range. Stop 1.5x proxy (minimum $2 price move); target 2R; timeout eight bars; stop-first if both touched. 1% equity risk with 0.01-lot increments; assume 100 oz/lot; reject trades below minimum lot. Initial capital $1,000. Execution guard independently rejects spread >30 raw units or signal candle range >2.5x volatility proxy. Estimated all-in roundtrip cost $1.46 per 0.01 lot; not verified against Eplanet. 60/40 chronological split; 23,643 private candles. Closed-equity drawdown only, no tick/slippage validation.

| Segment | Variant | Opportunities | Trades | Gross USD | Cost USD | Net USD | Closed DD USD | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 1168 | 210 | 202.87 | 306.60 | -103.73 | 254.16 | 0/156 |
| Train | Guard | 1183 | 165 | 117.32 | 243.82 | -126.50 | 213.19 | 0/156 |
| OOS | Base | 847 | 160 | -59.80 | 233.60 | -293.40 | 293.40 | 0/104 |
| OOS | Guard | 915 | 0 | 0 | 0 | 0 | 0 | 0/104 |

Opportunity counts differ because open positions block subsequent signals. Guard reduces train drawdown but worsens train net and blocks all OOS orders; it is not an independently profitable method. No evidence of viable trading edge. Research rejected; do not enable MT5 demo or live orders. Source code: research/v5_failed_auction.py; private market data and trade ledger are not committed. Reproduce with python research/v5_failed_auction.py /path/to/private.csv.