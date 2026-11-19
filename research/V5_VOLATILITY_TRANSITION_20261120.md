# V5 volatility shock continuation — 2026-11-20

Hypothesis: unusually wide directional M15 bars may predict short-lived continuation because volatility clusters. Entry at next bar open, four-bar horizon, stop-first OHLC execution. Trigger: bar range > 2.3 * prior 32-bar median range and absolute body > 65% of bar range. Stop distance clip(0.65*shock range,2,15) USD/oz; target 1.8R. Position size floor to 0.01 lot, min 0.01, max 0.10, 1% current-equity risk target. Contract assumption $100 per $1/oz per lot. Estimated round-trip friction $0.8/oz plus $7 per lot. Chronological 60/40 split; 23,643 M15 Eplanet candles. Overlapping signals suppressed. Guard independently stops further entries after -$20 realized daily PnL.

| Segment | Variant | Opportunities | Trades | Gross USD | Cost USD | Net USD | Closed DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Training | Base | 446 | 322 | 60.06 | 280.14 | -220.08 | 302.66 | 4/156 |
| Training | Guard | 446 | 305 | -12.91 | 265.35 | -278.26 | 406.63 | 4/156 |
| Holdout | Base | 320 | 228 | 79.79 | 198.36 | -118.57 | 309.74 | 3/104 |
| Holdout | Guard | 320 | 213 | 98.65 | 185.31 | -86.66 | 259.15 | 3/104 |

Both variants fail financial objective; guard reduces holdout loss but worsens training and is not a validated standalone edge. No MT5 demo activation. No live trading.

Limitations: Eplanet OHLC bars do not establish intrabar ordering; conservative stop-first. No real broker tick execution or verified spreads. Minimum 0.01 lot may exceed intended risk. Private market data and trade logs intentionally excluded from repository. Local executable Python and JSON output retained separately.