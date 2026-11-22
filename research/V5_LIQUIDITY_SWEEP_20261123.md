# V5 liquidity sweep reversal — 2026-11-23

New hypothesis: a wick beyond the previous 20-bar extreme, followed by a close back inside, may represent a failed breakout/liquidity sweep. Enter opposite direction at the next M15 open; previous 20-bar ATR, 1.1 ATR stop, 1.5 ATR target, maximum eight bars, stop-first when OHLC ambiguous. Independent guard excludes high candle range (>2.5 ATR), spread >35 points, or tick-volume spike (>2.2x preceding 20-bar median).

Data: private Eplanet merged CSV, 23,643 M15 bars; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Train before 2026-06-15 UTC, OOS 2026-06-15 through 2026-11-05 UTC. Independent starting equity $1000 each partition, 1% equity risk, variable lots in 0.01 steps, max 0.10 lots, 100 oz/lot assumed. Roundtrip estimated cost = spread points * $0.01/oz + $0.30/oz. No private candles committed.

| Metric | Train base | Train guard | OOS base | OOS guard |
|---|---:|---:|---:|---:|
| Opportunities | 790 | 794 | 483 | 489 |
| Diagnostic trades | 241 | 210 | 322 | 250 |
| Gross profit USD | 922.84 | 822.78 | 1286.15 | 974.29 |
| Gross loss USD | -972.83 | -861.06 | -1224.07 | -989.28 |
| Estimated costs USD | 152.15 | 129.78 | 222.40 | 158.91 |
| Net USD | -202.14 | -168.06 | -160.32 | -173.90 |
| Max closed drawdown USD | 335.87 | 290.65 | 229.08 | 206.44 |
| Days net >= $50 | 0 | 0 | 0 | 0 |

Guard decreases OOS closed drawdown by $22.64 but increases OOS net loss by $13.58; this is only risk-filter evidence, not profitable edge. Both training and OOS negative. REJECT. OOS results are diagnostic only; no demo/live trades.

Limitations: OHLC not tick-level, stop-first ambiguity, unverified Eplanet contract size/point conversion, modeled commission and slippage, no verified swap or intrabar floating drawdown. Full local Python runner and ledger produced separately; GitHub CI not run. Opportunity count differs between variants because sequential non-overlapping position schedules differ.
