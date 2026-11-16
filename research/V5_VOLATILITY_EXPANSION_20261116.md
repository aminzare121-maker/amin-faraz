# V5 compression-expansion research (2026-11-16)

Dataset: private Eplanet M15 CSV, 23643 bars; chronological 60/40 split (14185 / 9458). Data not committed.

Hypothesis: directional high-tick-volume candle after an 8-bar compression (range <= 2.8x previous ATR20) may persist for 8 bars. Signal requires candle range >=1.25x previous ATR20 and close in outer 20% of range. Entry at next candle open, stop 1x ATR, target 1.8x ATR; stop-first if both hit. Risk sizing 1% of current equity, 0.01 minimum, 0.10 maximum, 100oz/lot assumed. Estimated cost $0.86/oz round trip. Independent execution gate excludes next-open gaps >0.25 ATR and candles >2.5 ATR.

| OOS | Raw | Execution gate |
|---|---:|---:|
| Opportunities | 295 | 296 |
| Trades | 262 | 232 |
| Gross USD | 14.52 | 9.98 |
| Cost USD | 243.38 | 215.00 |
| Net USD | -228.86 | -205.02 |
| Max closed-equity drawdown USD | 323.41 | 321.00 |
| Days >= $50 net | 0/104 | 0/104 |

Train raw net -201.26; gate net -174.59. OOS gate reduces net loss by $23.84 but remains negative. Model rejects under $50/day requirement. No MT5/demo/live orders. Caveats: no intrabar equity drawdown, broker contract and slippage unverified, commission beyond assumed cost not modeled. Research script artifact retained separately; no private dataset uploaded.