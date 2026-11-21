# V5: tick-volume confirmation of 24-bar breakout (research only)
2026-11-21. Source: private Eplanet M15 CSV, 23,643 candles. 60% chronological train / 40% holdout. No private data committed.

Hypothesis: breakout accompanied by broker tick-volume >= 1.5x or 2.0x prior 32-bar median may reflect greater participation and improve net expectancy. Completed candle only; next candle open entry.

Execution: 24-bar prior high/low breakout; ATR prior 32-bar median, stop 1.5 ATR clamped 3-20 USD/oz, TP 1.8R, maximum 12 candles, stop-first for ambiguous OHLC. Variable 0.01-0.10 lots, 1% equity risk cap, 100 oz/lot, estimated round-trip $87/lot. Initial $1,000. Separate 3-candle low-MFE guard evaluated.

| Holdout | Opportunities | Trades | Gross before cost | Estimated costs | Net | Max closed DD | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Breakout unfiltered | 972 | 172 | -90.92 | 149.64 | -240.56 | 279.22 | 0 |
| Volume >= 1.5x | 972 | 109 | 29.48 | 96.57 | -67.09 | 164.62 | 0 |
| Volume >= 2.0x | 972 | 30 | -27.90 | 26.10 | -54.00 | 89.27 | 0 |
| Volume >= 1.5x + guard | 972 | 110 | 21.44 | 96.57 | -75.13 | 169.09 | 0 |

Holdout: 104 market days. Training net: unfiltered -162.26; 1.5x -165.32; 2.0x +14.56; guard -165.32. Volume filters reduced losses but did not create positive holdout expectancy; guard failed independently. Reject all for demo.

Limitations: OHLC not tick-level; broker tick_volume is not exchange volume; estimated execution cost; no intrabar floating DD. No live or demo orders. Full reproducible local Python source and JSON retained as conversation artifacts; source not yet committed to GitHub.
