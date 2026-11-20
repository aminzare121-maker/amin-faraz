# V5 — Completed-bar cost-breakeven protective stop (2026-11-20)

Research-only experiment. Input Eplanet M15 23643 candles SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split. Capital $1000; variable 0.01–0.1 lot; estimated $87/lot roundtrip; stop-first OHLC.

New hypothesis: after a completed M15 bar achieves 0.75R or 1R favorable excursion, move stop at start of NEXT candle to entry plus estimated transaction cost (direction-adjusted). Retain adverse-wick gate and 3-bar stagnation exit. No use of future bar data for stop adjustment.

| Holdout 104 days | Stagnation baseline | Protect 1R | Protect 0.75R |
|---|---:|---:|---:|
| Opportunities | 1526 | 1526 | 1526 |
| Trades | 165 | 172 | 181 |
| Gross USD | 276.95 | 271.24 | 223.50 |
| Costs USD | 143.55 | 149.64 | 157.47 |
| Net USD | 133.40 | 121.60 | 66.03 |
| Closed-equity drawdown USD | 54.11 | 61.47 | 80.77 |
| Days >= $50 | 0 | 0 | 0 |

Training net USD: baseline +46.17, 1R +8.68, 0.75R -34.60. Training drawdown: baseline 128.41, 1R 97.40, 0.75R 130.55. The 1R protective stop reduced TRAIN drawdown but worsened HOLDOUT drawdown and net. Both overlays rejected for demo.

Executable code generated and run locally as v5_profit_protection_20261120.py; not yet committed to GitHub. Do not claim source-code reproducibility from GitHub. The data are private and not committed. OHLC simulation cannot resolve true tick sequence, spread or slippage. No demo/real orders.
