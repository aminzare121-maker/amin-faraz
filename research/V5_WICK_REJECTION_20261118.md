# V5 Wick rejection — 2026-11-18

New hypothesis: a long rejection wick opposing the preceding 3-bar move may reflect temporary exhaustion. Entry next M15 open; hold up to 3 bars; 1.3 ATR stop. 1% equity risk, lot step 0.01, cap 0.05, 100 oz/lot assumed. Estimated round-trip costs 0.86 USD/oz. Separate volatility guard rejects ATR > 1.25 times lagged 96-bar median. Only completed candles used. Chronological 60/40 split, 23,643 private Eplanet candles.

|Out of sample|Signal|Volatility guard|
|---|---:|---:|
|Opportunities|264|264|
|Trades|99|99|
|Gross USD|-49.43|-49.43|
|Estimated costs USD|86.00|86.00|
|Net USD|-135.43|-135.43|
|Closed equity drawdown USD|171.19|171.19|
|Days >= 50 USD|0|0|
|Days with trades|59|59|

Training: 89 trades, -135.28 USD net without guard; 88 trades, -137.30 USD net with guard. Guard did not help. No evidence of edge, reject for demo. Local executable Python and trade-level JSON were produced; they are not yet committed. Private market data not committed. OHLC stops, estimated fees and assumed contract size limit validity; intrabar equity drawdown not measured. No orders placed.
