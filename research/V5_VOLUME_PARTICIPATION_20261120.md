# V5 relative tick-volume participation — 2026-11-20

Dataset: private Eplanet M15, 23,643 bars, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Raw data deliberately excluded.

Hypothesis: high relative tick volume on completed signal candle confirms participation in directional efficiency-pause setup. Relative volume = current tick_volume / median(previous 32 candles). High >=1.2; low <=0.8. Next-bar open execution; 12-bar max hold; conservative stop-first OHLC; 100 oz/lot; estimated round-trip friction $87/lot; dynamic risk cap $10 and max lot 0.1; initial equity $1000. 60/40 chronological split. No delayed sources.

| Holdout 104 trading days | Base | High participation | Low participation |
|---|---:|---:|---:|
| Opportunities | 1526 | 306 | 418 |
| Trades | 158 | 83 | 46 |
| Gross USD | 233.52 | 161.02 | 11.14 |
| Costs USD | 137.46 | 72.21 | 40.02 |
| Net USD | +96.06 | +88.81 | -28.88 |
| Closed-equity drawdown USD | 119.54 | 83.19 | 69.00 |
| Days net >= $50 | 1 | 0 | 0 |

Training 156 trading days: baseline +$72.86 (136 trades); high +$0.36 (81 trades); low +$3.89 (45 trades). High filter lowers drawdown but removes almost all training profit; no robust advantage. Reject both filters for demo. Results are bar-based estimates, not tick-level fills or live broker costs. Do not trade.

Executable local artifact: v5_volume_participation_20261120.py; full machine-readable output v5_volume_participation_20261120_results.json. These files were generated locally; this report does not imply executable source is committed to GitHub.
