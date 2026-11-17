# V5 rolling tick-volume-weighted mean reversion — 2026-11-18

Hypothesis: a large departure from 32-bar tick-volume-weighted typical price in a low-trend environment may revert. Signal after candle close; next-open execution; no COT/sentiment. This is a distinct price-anchor hypothesis, not a repeat of prior breakout or shock signals.

Private Eplanet M15: 23,643 rows, chronological 60/40 split; $1,000 starting capital; variable 0.01-step lots, 1% risk budget, 100 oz/lot assumed; fixed roundtrip cost $1.46 per 0.01 lot (NOT verified Eplanet fees). Stops evaluated pessimistically when target and stop hit same candle. Hold <=6 candles. Base: absolute deviation / prior 32-bar median range >1.7, rolling weighted-anchor drift <1.2 ranges in 16 bars. Guard independently rejects high-range candles (>1.5x previous median) and raw spread >30.

|Segment|Variant|Opportunities|Trades|Gross $|Estimated costs $|Net $|Closed drawdown $|Days >= $50|Trading days|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|Train|Base|1919|189|-32.19|280.32|-312.51|335.45|0|156|
|Train|Guard|1961|150|25.76|233.60|-207.84|236.21|0|156|
|OOS|Base|1320|190|-134.08|277.40|-411.48|422.76|0|104|
|OOS|Guard|1633|0|0|0|0|0|0|104|

The guard's zero trades OOS is abstention, not profitability. Neither variant meets $50 net per trading day. OOS rejection; NO DEMO ORDERS. Source and detailed private ledger generated locally as v5_vwap_proxy_20261118.py and v5_vwap_proxy_20261118_results.json; code and private ledger are not committed in this report commit. Intrabar mark-to-market drawdown, actual fees, tick-level execution not verified. No private price data published.
