# V5 volume-surprise continuation — 2026-11-19

Hypothesis: a sudden increase in tick activity combined with directional M15 body represents information arrival and could lead to continuation. Signals use completed candle only; entry next open.

Private CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23,643 rows. Chronological 60/40 split at row 14,185. 12 candidate combinations (volume ratio 1.5,2,2.5,3 and body/lagged ATR 0.4,0.7,1). Training selection: volume ratio 3, body >=0.4 ATR.

Train: 11 signals, 5 trades, gross +$31.35, estimated costs $6.51, net +$24.84, max closed drawdown $8.80.

Holdout (104 trading dates): 2 signals, 2 trades, gross +$0.13, estimated costs $2.79, net -$2.66, max closed drawdown $10.23, 0 days >=$50. Risk guard (ATR <=12 and volume shock <=8): unchanged 2 trades, net -$2.66.

Starting equity $1000, variable lot 0.01 increments capped 0.15, 1% risk, stop 1 lagged ATR, target 1.5 ATR, max 4 candles, conservative stop-first OHLC collision. Model $0.26/oz spread, $0.30/oz slippage each way, $7/lot roundtrip commission. Swap and tick-accurate fills not validated. The small sample cannot establish an edge; reject for demo. Private data and trade ledger intentionally excluded.
