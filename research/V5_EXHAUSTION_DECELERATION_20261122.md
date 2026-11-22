# V5 exhaustion deceleration — 2026-11-22

New hypothesis: three same-direction M15 candle bodies with strictly declining absolute size and cumulative displacement >= 0.8 ATR(20), followed by a reversal entry at the next bar open. This tests temporary order-flow exhaustion, not prior breakout rules.

Source: private Eplanet M15 CSV, 23,643 bars; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Private CSV deliberately not committed.

Chronological 60/40 split: 14,185 train bars, 9,458 test bars. Initial equity $1000 separately for each partition; variable lots 0.01 increments, 0.01 min, 0.10 max; risk 2% equity, 100oz per lot; stop 0.85 ATR, take profit 1.5 stop distance, maximum four bars, stop-first on ambiguous bars. Estimated $0.36/oz roundtrip spread and slippage. Costs not broker verified.

| Out-of-sample metric | Base | ATR gate |
|---|---:|---:|
| Opportunities | 235 | 238 |
| Trades | 231 | 212 |
| Gross profit USD | 1044.07 | 955.80 |
| Gross loss USD | -1405.83 | -1337.57 |
| Estimated costs USD | 153.00 | 142.92 |
| Net USD | -514.76 | -524.69 |
| Max closed-equity drawdown USD | 555.04 | 564.97 |
| Days >= $50 net | 0/104 | 0/104 |

ATR gate rejects signals when ATR exceeds 1.5x trailing 80-bar median; it worsened net performance and drawdown. Neither component passes. No demo/live orders. Tick-level floating drawdown, broker costs and independent GitHub execution remain unverified. Local runnable source and JSON outputs were produced in the automation workspace; this commit records evidence only, not the source code.
