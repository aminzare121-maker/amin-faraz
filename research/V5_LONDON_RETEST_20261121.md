# V5 London range retest — 2026-11-21

Research-only; **REJECTED for demo**. Private Eplanet data are not committed.

## New hypothesis
After a 06:00–08:00 UTC range breakout, require a subsequent retest and rejection of the broken boundary between 08:00 and 13:00 UTC. Signal uses only closed candles. Enter at next candle open. Independent risk guard vetoes signal candles with range >1.5 lagged ATR(32).

Data: Eplanet M15 23,643 rows, 155 chronological train days, 104 held-out days. Starting equity $1,000. Dynamic position size 1% equity risk, 100 oz/lot, minimum 0.01 lot, maximum 0.20 lot. Stop >=1.1 ATR, target 1.8R, max 9 candles, OHLC stop-first on ambiguous bars, $0.46/oz estimated round-trip spread/slippage.

| OOS metric | Entry | Entry + guard |
|---|---:|---:|
| Opportunities | 67 | 67 |
| Trades | 49 | 43 |
| Min-lot skips | 18 | 15 |
| Guard skips | 0 | 9 |
| Gross profit | $198.93 | $174.83 |
| Gross loss | -$231.91 | -$210.35 |
| Estimated costs | $23.00 | $20.24 |
| Net | **-$55.98** | **-$55.76** |
| Closed drawdown | $93.16 | $92.94 |
| Intrabar drawdown proxy | $96.98 | $96.76 |
| Days >= $50 net | 0 | 0 |

Training net +$104.70 baseline and +$120.84 guarded, but both lost money out of sample. No demo or live orders. Tick-level execution and true floating drawdown unverified. Local executable Python and JSON exist in the automation runtime; source upload to GitHub is still pending, and independent GitHub execution is not claimed.