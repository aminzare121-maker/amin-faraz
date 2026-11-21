# Failed-auction reversal: independent OOS recheck (2026-11-21)

Research only. Private Eplanet M15 CSV: 23,643 bars; 155 train days, 104 chronological OOS days. No private market data included.

Signal: sweep prior 16-bar high/low by 0.15 of lagged ATR(32), then close back inside, enter opposite at next bar open. Stop 1.25 ATR, target 1 ATR, five-bar timeout, stop-first when ambiguous. Dynamic lots: 1% equity risk, 100 oz/lot, min 0.01, cap 0.20. Cost proxy: $0.46/oz roundtrip. Separate risk veto skips signal candle range >2 ATR.

|OOS metric|Entry|Entry + veto|
|---|---:|---:|
|Opportunities|625|633|
|Trades|242|181|
|Below min lot|383|355|
|Vetoed|0|97|
|Gross profit USD|692.39|478.41|
|Gross loss USD|-821.45|-627.68|
|Estimated costs USD|111.32|83.26|
|Net USD|-240.38|-232.54|
|Maximum closed drawdown USD|269.60|271.41|
|Days net >= $50|0|0|
|Losing days|48|43|

Training net: -163.92 entry, -149.78 veto. Neither variant qualifies for MT5 demo. Veto reduced losing days but not drawdown. Local code and JSON generated in conversation, not yet committed to GitHub. OHLC stop-first fills, no true tick sequence, estimated costs, no full floating drawdown. No orders placed.
