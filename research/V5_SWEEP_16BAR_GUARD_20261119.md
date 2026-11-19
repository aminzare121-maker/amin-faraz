# V5 16-bar liquidity sweep test — 2026-11-19

Private Eplanet merged CSV: 23643 M15 rows, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Data NOT published.

Hypothesis: 16-bar extreme sweep rejected by a wick >=55% candle range, candle range >=0.7 lagged ATR32, predicts reversal. Next-open entry; stop=max(0.8 ATR, $2/oz); TP=1.5R; 8-bar timeout, stop-first. Risk sizing 1% equity with 0.01 lot increments, maximum 0.1 lot, $1000 starting capital. Estimated all-in roundtrip $0.80/oz, not verified with Eplanet. Chronological 60/40 split. Separate risk guard: skip new trades after realized daily PnL <=-$20.

|Metric|Train|OOS base|OOS guard|
|---|---:|---:|---:|
|Opportunities|466|302|302|
|Trades|251|282|274|
|Gross USD|-49.67|3.12|8.10|
|Costs USD|230.40|266.40|259.20|
|Net USD|-280.08|-263.28|-251.10|
|Max closed DD USD|329.92|376.62|364.45|
|Days >=$50|0/156|0/104|0/104|

REJECT. Neither role passes. Local executed Python and full JSON ledger available as ChatGPT run artifacts; source code not yet uploaded to this GitHub branch. Intrabar DD, broker spread/commission, slippage and margin unverified. No demo/live orders.
