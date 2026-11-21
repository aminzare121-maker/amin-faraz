# V5 — Rolling fair-value dislocation (2026-11-21)

Research-only, no MT5 execution. Data: private Eplanet M15 merged CSV, 23,643 rows, chronological 155 train / 104 out-of-sample trading days. Do not commit private price data.

## Economic hypothesis
Prior 32-bar tick-volume-weighted typical-price fair value may attract price after a 1–2 ATR displacement; require a directional candle toward the lagged fair value, then enter next bar open. No delayed sentiment/COT. Exit at 1 ATR target, 1.5 ATR stop, or after six bars. Conservative stop-first when both barriers hit same candle.

Risk: initial $1,000, 1% equity risk, min 0.01 lot, max 0.20 lot, 100 oz/lot, roundtrip $0.45/oz assumed transaction cost. ATR from 32 previous candles. Guard tested separately: early exit at adverse 0.75 ATR after at least one bar. These are OHLC-only results, not broker-tick verified.

## Out-of-sample results (USD)
|Threshold|Guard|Opportunities|Trades|Gross profit|Gross loss|Costs|Net|Closed drawdown|Intrabar DD proxy|Days >= $50|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|1.0 ATR|No|see JSON|see JSON|see JSON|see JSON|see JSON|see JSON|see JSON|see JSON|0|
|1.0 ATR|Yes|2938|136|271.60|-489.27|61.20|-278.86|296.02|298.60|0|
|1.5 ATR|No|2046|181|549.11|-598.66|81.45|-130.99|165.69|168.59|0|
|1.5 ATR|Yes|2126|127|276.04|-415.50|57.15|-196.61|213.18|219.46|0|
|2.0 ATR|No|1467|142|434.75|-471.04|63.90|-100.19|145.01|146.72|0|
|2.0 ATR|Yes|1516|118|286.29|-370.67|53.10|-137.48|169.85|171.56|0|

The guard reduces the number of losing days in some settings but worsens net and closed drawdown. All variants rejected for demo. The opportunity count includes candidates below minimum lot; it is not a tradable frequency estimate. Local Python and complete JSON produced in conversation artifacts, not committed to this branch. Independent GitHub execution not verified.

## Caveats
Costs proxy, potential intrabar ambiguity, no tick-by-tick verification, variable volume subject to broker lot specifications. The intrabar DD figure is an OHLC proxy rather than a fully accurate mark-to-market drawdown. Goal of at least $50 net on every trading day not met. No live/demo trades opened.
