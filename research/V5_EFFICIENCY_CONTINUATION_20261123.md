# V5 directional efficiency continuation — 2026-11-23

Dataset: private Eplanet M15 merged CSV, no raw data committed. Train before 2026-06-15 UTC; test from 2026-06-15 UTC. Initial capital $1000 separately per split.

Hypothesis: 12-candle efficiency ratio |close-close[-12]| / sum(abs(close.diff()),12) >= 0.55 with final candle confirming drift; enter next candle open in drift direction. SL=1.2 ATR20, TP=2.4 ATR20, maximum 6 bars; stop first if both touched. 1% equity risk; lot steps .01, max .10. Approximate costs: recorded spread in points assumed $0.01/point, $0.20/oz slippage, $7/lot commission. Contract assumed 100 oz/lot; broker confirmation pending. Risk guard independently excludes spread >35, candle range >1.8 ATR, and UTC hours 21-23.

|Metric|Alpha train|Alpha OOS|Guard train|Guard OOS|
|---|---:|---:|---:|---:|
|Opportunities scanned|989|556|1058|716|
|Trades|217|264|162|134|
|Gross profit USD|943.26|1261.83|741.54|546.15|
|Gross loss USD|-885.40|-963.39|-649.32|-493.90|
|Estimated costs USD|130.59|172.17|92.21|79.63|
|Net USD|-72.72|+126.26|+0.01|-27.38|
|Max closed drawdown USD|136.85|106.63|113.34|111.30|
|Days >= $50 net|0|1|0|0|
|Active trading days|93|91|76|66|

Note: opportunity counts differ between variants because entries are skipped while each variant holds a position. OOS positive alpha is not evidence of daily target success; guard deteriorates OOS net and drawdown. OHLC bars cannot confirm intrabar execution, spreads, or floating drawdown. Not authorized for demo or live execution. The executable Python and JSON are held as local artifacts; GitHub CI not run.
