# V5 wick rejection reversal research (2026-11-16)

Source: private Eplanet_M15_20251105_20261105_merged.csv, 23,643 M15 candles, never committed.

Hypothesis: unusually wide candle with opposing rejection wick signals short-horizon reversal. Previous 32-bar median high-low range, lagged one bar. Signal: bullish body and upper wick >0.8 body, or bearish body and lower wick >0.8 body; candle range >1.5 median. Contrarian entry at next open, exit after two bars; stop 1.2 median range, target 1.6 stop; intrabar stop first. Risk 1% equity, lot floor to 0.01, min 0.01 max 0.10, $100 per $1/lot. Cost $0.26 spread + $0.30 slippage each side = $0.86 per oz round trip. Split first 60% training, last 40% holdout, no optimization on holdout.

| Segment | Trades | Gross USD | Cost USD | Net USD | Max closed drawdown | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|
| Train | 661 | -70.18 | 575.34 | -645.52 | 741.47 | 4 |
| Holdout baseline | 420 | 178.07 | 362.06 | -183.99 | 263.59 | 0 |
| Holdout risk gate | 385 | 245.20 | 337.12 | -91.92 | 157.53 | 0 |

Risk gate independently removes range >3x prior median and 21/22 UTC signal hours. It reduced losses but did not produce profitability. Reject for demo. Limitations: OHLC stop-first, no tick execution, minimum 0.01 lot can exceed nominal risk; cost assumptions not measured broker fills. Research code local artifact v5_intraday_reversal.py (not committed in this report).
