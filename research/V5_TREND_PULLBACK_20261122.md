# V5 trend pullback, 2026-11-22
Hypothesis: a 48-bar EMA trend with 12-bar slope above 0.25 ATR, two countertrend closes, then recovery beyond previous candle high/low may capture trend resumption. Next-bar open entry, 1.2 ATR stop, 2 ATR target, 12-bar maximum holding. Risk sizing 1% of running equity, 0.01-lot increments, 100 oz/lot, reject orders below minimum 0.01 lot. Spread points * 0.01 price plus 0.30 price round-trip slippage. Stop-first on ambiguous OHLC bars. OOS starts 2026-06-15 UTC.

Eplanet M15 CSV: 23,643 bars, 2025-11-05 through 2026-11-05. No private dataset committed.

| OOS metric | Base | ATR guard |
|---|---:|---:|
| OOS trades | 160 | 133 |
| Gross profit USD | 774.23 | 559.20 |
| Gross loss USD | -787.99 | -642.13 |
| Estimated costs USD | 112.90 | 92.67 |
| Net USD | -126.65 | -175.61 |
| Max closed drawdown USD | 192.17 | 220.75 |
| Days with trades | 87 | 78 |
| Days net >= 50 USD | 0 | 0 |

Full-period opportunities: 606 (base), 608 (guard); guard blocks 156. These are not OOS-only opportunity counts. Position sizing was run continuously from the start, so OOS equity was not reset to USD 1000. Tick-level drawdown and fills are unverified. Guard removes high ATR relative to previous 100-bar 75th percentile. Both rejected; no demo/real trading enabled. Local executable and JSON artifacts exist outside GitHub; code is not yet committed.
