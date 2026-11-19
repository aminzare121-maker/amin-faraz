# V5 — Three-candle range deceleration, 2026-11-19

Hypothesis: three same-direction M15 candles with sequentially shrinking ranges may represent exhaustion (reversal) or controlled continuation. Select direction and shrink ratio on first 60%, test final 40% chronologically.

Data: Eplanet_M15_20251105_20261105_merged.csv, 23643 rows, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Private data not committed.

Selection: ratio 1.4; continuation direction (reversal_if_1 = -1). Each successive range must be smaller than prior range / 1.4; total three bodies >1.2 prior ATR20; next-open entry; 1 ATR stop, 1.5 ATR target; maximum 4 M15 candles; stop first on ambiguous OHLC. Risk 1% of current equity; 0.01 lot increments, cap 0.15 lot, 100 oz/lot.

Training: 34 opportunities, 20 trades, gross +$3.82, costs $19.53, net -$15.71, closed drawdown $40.71.

Holdout (104 trading days): 22 opportunities, 21 trades, gross +$16.22, costs $21.39, net -$5.17, closed drawdown $31.30, approximate intrabar drawdown $34.87, 0/104 days >= $50 net.

Guard (ATR>9 or last range<0.35 ATR excluded): 22 raw opportunities, 20 trades, gross +$10.11, costs $20.46, net -$10.35, closed drawdown $31.30. Guard worsened results.

Costs: commission $7/lot roundtrip, spread $0.26/oz, slippage $0.30/oz each side; swap excluded. No tick data. Cost and intrabar risk estimates are not broker verified.

Decision: REJECT. No MT5 demo or live activation. Local executed Python and full JSON results retained as conversation artifacts, not yet committed.