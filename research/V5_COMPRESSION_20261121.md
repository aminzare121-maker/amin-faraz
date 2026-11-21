# V5 compression-conditioned breakout — 2026-11-21
Private Eplanet M15 CSV SHA256: `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`; 23,643 candles; chronological 60/40 split. No private data committed.

Hypothesis: breakouts after *previously observed* volatility compression may have higher continuation expectancy than ordinary breakouts. 24-candle range break, prior 32-candle median true range / prior 96-candle median ATR <= 0.8 or <=0.6; signal on completed bar, enter next open. A separate 3-bar low-favorable-excursion exit guard was tested. 1% equity risk, variable 0.01-0.10 lots, $1000 initial equity, 100oz/lot, estimated roundtrip $87/lot, 1.5ATR stop clamped $3-$20, 1.8R target, max 12 bars, stop-first ambiguous OHLC.

| Holdout (104 market days) | Trades | Gross wins | Gross losses | Estimated costs | Net | Max closed DD | Days net >=$50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Unfiltered breakout | 172 | 746.93 | -837.85 | 149.64 | -240.56 | 279.22 | 0 |
| Compression <=0.8 | 94 | 472.81 | -418.63 | 83.52 | -29.35 | 155.73 | 0 |
| Compression <=0.6 | 7 | 18.71 | -28.84 | 6.09 | -16.22 | 33.19 | 0 |
| Compression <=0.8 + exit guard | 95 | 472.81 | -411.00 | 84.39 | -22.58 | 155.49 | 0 |

972 raw breakout opportunities in holdout; 775 filtered at 0.8; 959 at 0.6. Compression improves loss avoidance, but is not profitable net of costs. Guard modestly improves net but not enough. **Reject all for MT5 demo.**

Limitations: OHLC bar path ambiguity, estimated rather than verified execution costs, no intrabar floating DD, risk-lot rounding/minimum volume blocks many entries. Local executable Python and JSON generated in conversation environment; code has not been committed to GitHub. No orders placed.