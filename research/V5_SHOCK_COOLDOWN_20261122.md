# V5 shock cooldown — 2026-11-22
New hypothesis: after a candle range exceeds 2.5 times lagged ATR(20), volatility clustering makes new breakout entries risky. An independent 8-bar cooldown veto was tested against an 8-bar directional breakout baseline.
Data: Eplanet M15, 23,643 candles, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological split 60/40, OOS begins 2026-06-15.
Assumptions: $1000 initial; variable lot floor to 0.01, 100oz/lot, 1% risk, 1.1 ATR stop, 1.8R target, next open entry, 8-bar max holding, stop-first on ambiguous OHLC, estimated $0.70/oz round trip.
| OOS metric | baseline | cooldown |
|---|---:|---:|
| opportunities | 1130 | 1135 |
| trades | 594 | 569 |
| vetoed | 0 | 227 |
| gross profit USD | 2587.13 | 2582.02 |
| gross loss USD | -2387.98 | -2301.07 |
| estimated cost USD | 430.50 | 415.10 |
| net USD | -231.35 | -134.14 |
| maximum closed drawdown USD | 379.38 | 306.68 |
| days >= $50 | 1 | 1 |
| days with trades | 101 | 102 |
Training net: baseline -331.94, cooldown -314.03.
Cooldown reduced OOS loss by $97.21 and closed drawdown by $72.70, but is not profitable and is **REJECTED** for demo. OOS opportunities differ because positions suppress overlapping signals. Tick path, live spread, slippage, commission, swap and broker contract settings unverified. No private candles committed. Local script v5_shock_cooldown_20261122.py and JSON produced; source script not yet committed.