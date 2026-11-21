# V5 low-participation pullback — 2026-11-21

Research-only, **REJECTED for MT5 demo**. No private Eplanet data published.

Hypothesis: a shallow countertrend candle on unusually low tick volume within a 16-bar directional move may represent temporary profit-taking rather than trend reversal. Use closed candles only, enter next M15 open. Independent risk guard vetoes signal candle range above 0.85 lagged ATR32.

Data: Eplanet M15 CSV, 23,643 bars, chronological 155 train days / 104 out-of-sample days. Capital $1,000; dynamic 1% equity risk, 0.01-lot steps, 0.01–0.20 lot; 100oz/lot; stop >=1.05 ATR; target 1.6R; max eight bars; OHLC stop-first; estimated friction $0.46/oz round-trip.

| OOS metric | Entry | Entry + range guard |
|---|---:|---:|
| Opportunities | 203 | 205 |
| Executed trades | 138 | 127 |
| Skipped min-lot | 65 | 57 |
| Guard vetoes | 0 | 21 |
| Gross profits | $560.94 | $532.61 |
| Gross losses | -$555.53 | -$501.49 |
| Estimated costs | $64.40 | $59.34 |
| Net | **-$58.99** | **-$28.21** |
| Closed-equity max drawdown | $114.39 | $103.44 |
| Intrabar OHLC drawdown proxy | $118.94 | $109.73 |
| Days >= $50 net | 0 | 0 |

Training net -$44.45 entry / -$18.84 guarded. Guard improves OOS loss by $30.78 but remains unprofitable. No demo or live orders. True tick-level execution and floating drawdown are unverified. Local Python and JSON created; code has not yet been uploaded to GitHub. The OHLC test is not a production backtest.